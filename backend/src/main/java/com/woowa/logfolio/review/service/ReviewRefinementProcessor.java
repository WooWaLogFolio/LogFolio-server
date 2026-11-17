package com.woowa.logfolio.review.service;

import com.woowa.logfolio.ai.AiServerClient;
import com.woowa.logfolio.evidence.entity.EvidenceItem;
import com.woowa.logfolio.evidence.repository.EvidenceItemRepository;
import com.woowa.logfolio.experience.entity.Experience;
import com.woowa.logfolio.experience.service.ExperienceService;
import com.woowa.logfolio.review.entity.GapQuestion;
import com.woowa.logfolio.review.entity.ReviewItem;
import com.woowa.logfolio.review.entity.ReviewSession;
import com.woowa.logfolio.review.repository.GapQuestionRepository;
import com.woowa.logfolio.review.repository.ReviewItemRepository;
import com.woowa.logfolio.review.repository.ReviewSessionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ReviewRefinementProcessor {
    private final ReviewSessionRepository sessionRepository;
    private final ReviewItemRepository itemRepository;
    private final GapQuestionRepository questionRepository;
    private final EvidenceItemRepository evidenceRepository;
    private final ExperienceService experienceService;
    private final AiServerClient aiServerClient;

    @Transactional
    public void process(ReviewRefinementRequestedEvent event) {
        ReviewSession session = sessionRepository
                .findByIdAndProjectUserId(event.reviewSessionId(), event.userId())
                .orElseThrow(() -> new IllegalStateException("AI 다듬기 세션을 찾을 수 없습니다."));
        if (!"IN_PROGRESS".equals(session.getStatus())) return;

        Experience experience = experienceService.findOwned(event.userId(), event.experienceId());
        if (!experience.getProject().getId().equals(session.getProject().getId())) {
            throw new IllegalStateException("AI 다듬기 세션과 경험의 프로젝트가 일치하지 않습니다.");
        }

        List<EvidenceItem> evidences = evidenceRepository.findAllForExperience(experience.getId(), event.userId());
        List<UUID> sourceIds = evidences.stream()
                .map(this::indexedSourceId)
                .filter(Objects::nonNull)
                .distinct()
                .toList();
        if (sourceIds.isEmpty()) {
            throw new IllegalStateException("경험에 연결된 INDEXED Evidence Source가 없습니다.");
        }

        JsonNode response = aiServerClient.refineExperience(buildRequest(session, experience, evidences, sourceIds));
        validateResponse(response, session, experience);
        storeResponse(response, session, experience, event.userId());
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void fail(ReviewRefinementRequestedEvent event) {
        sessionRepository.findByIdAndProjectUserId(event.reviewSessionId(), event.userId())
                .filter(session -> "IN_PROGRESS".equals(session.getStatus()))
                .ifPresent(ReviewSession::fail);
    }

    private Map<String, Object> buildRequest(ReviewSession session, Experience experience,
                                             List<EvidenceItem> evidences, List<UUID> sourceIds) {
        Map<String, Object> request = new LinkedHashMap<>();
        request.put("reviewSessionId", session.getId());
        request.put("projectId", experience.getProject().getId());
        request.put("sourceIds", sourceIds);
        request.put("experience", experiencePayload(experience, evidences));
        request.put("projectContext", Map.of(
                "name", experience.getProject().getName(),
                "description", nullToEmpty(experience.getProject().getDescription()),
                "activityType", nullToEmpty(experience.getProject().getActivityType()),
                "userRole", nullToEmpty(experience.getProject().getUserRole())));
        request.put("corrections", List.of());
        request.put("answers", List.of());
        return request;
    }

    private Map<String, Object> experiencePayload(Experience experience, List<EvidenceItem> evidences) {
        List<Map<String, String>> claims = new ArrayList<>();
        addClaim(claims, "CONTEXT", experience.getContext());
        addClaim(claims, "CONTRIBUTION", experience.getContribution());
        addClaim(claims, "DECISION_REASON", experience.getDecisionReason());
        addClaim(claims, "ACTION", experience.getAction());
        addClaim(claims, "RESULT", experience.getResult());
        addClaim(claims, "LEARNING", experience.getLearning());

        List<Map<String, Object>> evidenceReferences = evidences.stream()
                .filter(evidence -> evidence.getChunkId() != null && indexedSourceId(evidence) != null)
                .map(evidence -> Map.<String, Object>of(
                        "evidenceId", evidence.getId(),
                        "sourceId", indexedSourceId(evidence),
                        "chunkId", evidence.getChunkId()))
                .toList();

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("experienceId", experience.getId());
        payload.put("title", experience.getTitle());
        payload.put("summary", experience.getSummary());
        payload.put("claims", claims);
        payload.put("evidenceIds", evidences.stream().map(EvidenceItem::getId).toList());
        payload.put("evidences", evidenceReferences);
        return payload;
    }

    private void storeResponse(JsonNode response, ReviewSession session, Experience experience, UUID userId) {
        int itemOrder = 0;
        List<ReviewItem> items = new ArrayList<>();
        for (JsonNode item : response.path("reviewItems")) {
            String type = item.path("itemType").asText();
            String proposed = item.path("proposedContent").asText();
            if (type.isBlank() || proposed.isBlank()) continue;
            items.add(new ReviewItem(session, experience, type, proposed, itemOrder++));
        }
        itemRepository.saveAll(items);

        int questionOrder = questionRepository
                .findAllByExperienceIdAndExperienceProjectUserIdOrderByDisplayOrder(experience.getId(), userId)
                .stream().mapToInt(GapQuestion::getDisplayOrder).max().orElse(-1) + 1;
        List<GapQuestion> questions = new ArrayList<>();
        for (JsonNode question : response.path("questions")) {
            UUID questionId = uuid(question, "questionId");
            String targetSection = question.path("targetSection").asText();
            String text = question.path("question").asText();
            if (targetSection.isBlank() || text.isBlank()) continue;
            questions.add(new GapQuestion(questionId, experience, targetSection, text,
                    strings(question.path("suggestedAnswers")), questionOrder++));
        }
        questionRepository.saveAll(questions);

        String status = response.path("status").asText();
        if ("REVIEW_READY".equals(status) && (!items.isEmpty() || !questions.isEmpty())) {
            session.reviewReady();
        } else if (List.of("NO_UPDATE", "NEEDS_ADDITIONAL_SOURCE").contains(status)) {
            session.finishWithoutReview();
        } else {
            throw new IllegalStateException("AI 경험 다듬기 응답 상태와 결과가 일치하지 않습니다: " + status);
        }
    }

    private void validateResponse(JsonNode response, ReviewSession session, Experience experience) {
        if (!session.getId().equals(uuid(response, "reviewSessionId"))) {
            throw new IllegalStateException("AI 응답의 reviewSessionId가 요청과 일치하지 않습니다.");
        }
        if (!experience.getProject().getId().equals(uuid(response, "projectId"))) {
            throw new IllegalStateException("AI 응답의 projectId가 요청과 일치하지 않습니다.");
        }
        if (!experience.getId().equals(uuid(response, "experienceId"))) {
            throw new IllegalStateException("AI 응답의 experienceId가 요청과 일치하지 않습니다.");
        }
    }

    private UUID indexedSourceId(EvidenceItem evidence) {
        if (evidence.getProjectFile() != null
                && "INDEXED".equals(evidence.getProjectFile().getProcessingStatus())) {
            return evidence.getProjectFile().getRetrievalSourceId();
        }
        if (evidence.getQuickLog() != null
                && "INDEXED".equals(evidence.getQuickLog().getProcessingStatus())) {
            return evidence.getQuickLog().getRetrievalSourceId();
        }
        return null;
    }

    private void addClaim(List<Map<String, String>> claims, String sectionType, String content) {
        if (content != null && !content.isBlank()) {
            claims.add(Map.of("sectionType", sectionType, "content", content));
        }
    }

    private UUID uuid(JsonNode node, String field) {
        String value = node.path(field).asText();
        if (value.isBlank()) throw new IllegalStateException("AI 응답에 " + field + "가 없습니다.");
        return UUID.fromString(value);
    }

    private List<String> strings(JsonNode node) {
        List<String> values = new ArrayList<>();
        if (node.isArray()) node.forEach(value -> values.add(value.asText()));
        return values;
    }

    private String nullToEmpty(String value) { return value == null ? "" : value; }
}
