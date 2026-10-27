package com.woowa.logfolio.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.woowa.logfolio.analysis.entity.AnalysisRun;
import com.woowa.logfolio.analysis.repository.AnalysisRunRepository;
import com.woowa.logfolio.analysis.service.AnalysisService;
import com.woowa.logfolio.experience.entity.Experience;
import com.woowa.logfolio.experience.repository.ExperienceRepository;
import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.file.DocumentTextExtractor;
import com.woowa.logfolio.quicklog.entity.QuickLog;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Async;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.math.BigDecimal;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

/**
 * Bridges Spring's user-owned data and the private FastAPI API.
 * The listener runs after the request transaction commits, so the worker can
 * always read the run and its input sources from PostgreSQL.
 */
@Component
@RequiredArgsConstructor
public class AnalysisExecutionHandler {
    private static final Logger log = LoggerFactory.getLogger(AnalysisExecutionHandler.class);
    private final AnalysisRunRepository runRepository;
    private final ExperienceRepository experienceRepository;
    private final AnalysisService analysisService;
    private final AiServerClient aiServerClient;
    private final DocumentTextExtractor textExtractor;

    @Value("${app.storage.root:./storage/uploads}")
    private String storageRoot;

    @Async("aiTaskExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void execute(AnalysisRequestedEvent event) {
        try {
            // The event listener and queued-job recovery may race. Only one worker may own a run.
            if (!analysisService.claimQueuedRun(event.analysisRunId())) return;
            AnalysisRun run = runRepository.findByIdAndProjectUserId(event.analysisRunId(), event.userId())
                    .orElseThrow();

            List<UUID> sourceIds = indexInputSources(run);
            if (sourceIds.isEmpty()) {
                throw new IllegalStateException("분석 가능한 텍스트 자료가 없습니다.");
            }

            JsonNode response = aiServerClient.analyze(buildRequest(run, sourceIds));
            analysisService.recordAiResponse(event.userId(), run.getId(), response.path("summary").asText(null),
                    nullableText(response, "informationNeed"), nullableText(response, "informationNeedReason"),
                    nullableText(response, "noUpdateReason"), stringList(response.path("inputSourceIds")),
                    stringList(response.path("referencedSourceIds")), objectList(response.path("sourceWarnings")),
                    objectList(response.path("questions")), objectMap(response.path("aiUsage")));
            analysisService.saveResults(event.userId(), run.getId(), modelVersion(response), candidates(response));
        } catch (RuntimeException exception) {
            log.error("AI analysis failed: runId={}", event.analysisRunId(), exception);
            // A failed run must not leave the client polling QUEUED/PROCESSING forever.
            try {
                analysisService.fail(event.userId(), event.analysisRunId());
            } catch (RuntimeException ignored) {
                // Preserve the original worker failure while keeping the worker thread alive.
            }
        }
    }

    private List<UUID> indexInputSources(AnalysisRun run) {
        List<UUID> indexed = new ArrayList<>();
        for (ProjectFile file : run.getInputFiles()) {
            if ("INDEXED".equals(file.getProcessingStatus())) {
                indexed.add(file.getId());
                continue;
            }
            List<AiServerContract.Page> pages = extractPages(file);
            AiServerContract.Source source = new AiServerContract.Source(
                    file.getId(), "PROJECT_FILE", file.getOriginalName(), file.getMimeType(), file.getContentHash(), pages);
            file.processing();
            AiServerContract.SourceIndexResponse result = aiServerClient.indexSources(
                    new AiServerContract.SourceIndexRequest(run.getProject().getId(), List.of(source)));
            if (isIndexed(result, file.getId())) {
                file.indexed();
                indexed.add(file.getId());
            } else if (isDuplicate(result, file.getId())) {
                // FastAPI intentionally stores no chunks for a duplicate Source.
                // Analyze the already indexed canonical Source instead.
                file.indexed();
                duplicateOfSourceId(result, file.getId()).ifPresent(indexed::add);
            } else {
                file.failed();
                throw sourceIndexingFailure(result, file.getId(), file.getOriginalName());
            }
        }
        for (QuickLog log : run.getInputLogs()) {
            if ("INDEXED".equals(log.getProcessingStatus())) {
                indexed.add(log.getId());
                continue;
            }
            AiServerContract.Source source = new AiServerContract.Source(
                    log.getId(), "QUICK_LOG", "30초 기록", "text/plain",
                    contentHash(log.getContent()), List.of(new AiServerContract.Page(null, log.getContent())));
            log.processing();
            AiServerContract.SourceIndexResponse result = aiServerClient.indexSources(
                    new AiServerContract.SourceIndexRequest(run.getProject().getId(), List.of(source)));
            if (isIndexed(result, log.getId())) {
                log.indexed();
                indexed.add(log.getId());
            } else if (isDuplicate(result, log.getId())) {
                log.indexed();
                duplicateOfSourceId(result, log.getId()).ifPresent(indexed::add);
            } else {
                log.failed();
                throw sourceIndexingFailure(result, log.getId(), "30초 기록");
            }
        }
        return indexed.stream().distinct().toList();
    }

    private boolean isIndexed(AiServerContract.SourceIndexResponse response, UUID sourceId) {
        return response.items() != null && response.items().stream()
                .anyMatch(item -> sourceId.equals(item.sourceId())
                        && "INDEXED".equals(item.status()));
    }
    private boolean isDuplicate(AiServerContract.SourceIndexResponse response, UUID sourceId) {
        return response.items() != null && response.items().stream()
                .anyMatch(item -> sourceId.equals(item.sourceId()) && "DUPLICATE".equals(item.status()));
    }

    private Optional<UUID> duplicateOfSourceId(
            AiServerContract.SourceIndexResponse response, UUID sourceId
    ) {
        if (response.items() == null) return Optional.empty();
        return response.items().stream()
                .filter(item -> sourceId.equals(item.sourceId()) && "DUPLICATE".equals(item.status()))
                .map(AiServerContract.SourceIndexItem::duplicateOfSourceId)
                .filter(Objects::nonNull)
                .findFirst();
    }

    private IllegalStateException sourceIndexingFailure(
            AiServerContract.SourceIndexResponse response, UUID sourceId, String sourceName
    ) {
        String reason = response.items() == null ? "AI 서버 응답에 항목이 없습니다."
                : response.items().stream()
                        .filter(item -> sourceId.equals(item.sourceId()))
                        .findFirst()
                        .map(item -> "status=" + item.status()
                                + (item.errorCode() == null ? "" : ", errorCode=" + item.errorCode()))
                        .orElse("AI 서버 응답에 해당 Source가 없습니다.");
        return new IllegalStateException("AI Source 인덱싱 실패: " + sourceName + " (" + reason + ")");
    }

    private List<AiServerContract.Page> extractPages(ProjectFile file) {
        Path root = Path.of(storageRoot).toAbsolutePath().normalize();
        Path source = root.resolve(file.getStorageKey()).normalize();
        if (!source.startsWith(root)) throw new IllegalArgumentException("올바르지 않은 저장 경로입니다.");
        return textExtractor.extract(source, file.getOriginalName());
    }

    private Map<String, Object> buildRequest(AnalysisRun run, List<UUID> sourceIds) {
        Map<String, Object> request = new LinkedHashMap<>();
        request.put("analysisRunId", run.getId());
        request.put("projectId", run.getProject().getId());
        request.put("sourceIds", sourceIds);
        request.put("projectContext", Map.of(
                "name", run.getProject().getName(),
                "description", nullToEmpty(run.getProject().getDescription()),
                "activityType", nullToEmpty(run.getProject().getActivityType()),
                "userRole", nullToEmpty(run.getProject().getUserRole())));
        request.put("existingExperiences", experienceRepository
                .findAllByProjectIdAndProjectUserIdAndDeletedAtIsNullOrderByUpdatedAtDesc(
                        run.getProject().getId(), run.getProject().getUser().getId()).stream()
                .map(this::existingExperience).toList());
        request.put("corrections", List.of()); // Review history migration is introduced separately from legacy rows.
        request.put("answers", List.of());
        return request;
    }

    private Map<String, Object> existingExperience(Experience experience) {
        List<Map<String, String>> claims = new ArrayList<>();
        addClaim(claims, "CONTEXT", experience.getContext());
        addClaim(claims, "CONTRIBUTION", experience.getContribution());
        addClaim(claims, "DECISION_REASON", experience.getDecisionReason());
        addClaim(claims, "ACTION", experience.getAction());
        addClaim(claims, "RESULT", experience.getResult());
        addClaim(claims, "LEARNING", experience.getLearning());
        return Map.of("experienceId", experience.getId(), "title", experience.getTitle(),
                "summary", nullToEmpty(experience.getSummary()), "claims", claims,
                "evidenceIds", List.of(), "evidences", List.of());
    }

    private void addClaim(List<Map<String, String>> claims, String section, String content) {
        if (content != null && !content.isBlank()) claims.add(Map.of("sectionType", section, "content", content));
    }

    private List<AnalysisService.CandidateInput> candidates(JsonNode response) {
        List<AnalysisService.CandidateInput> result = new ArrayList<>();
        for (JsonNode candidate : response.path("candidates")) {
            UUID target = candidate.hasNonNull("targetExperienceId")
                    ? UUID.fromString(candidate.get("targetExperienceId").asText()) : null;
            String type = "EXISTING_UPDATE".equals(candidate.path("resultType").asText())
                    ? "ENHANCE_EXISTING" : "NEW";
            UUID aiCandidateId = UUID.fromString(candidate.path("candidateId").asText());
            result.add(new AnalysisService.CandidateInput(type, target, (BigDecimal) null,
                    "AI 분석 결과", candidate.path("title").asText(), candidate.path("summary").asText(),
                    draftContent(candidate.path("claims")), aiCandidateId, objectList(candidate.path("claims")),
                    objectList(candidate.path("conflicts"))));
        }
        return result;
    }

    private Map<String, Object> draftContent(JsonNode claims) {
        Map<String, Object> draft = new LinkedHashMap<>();
        for (JsonNode claim : claims) {
            String key = switch (claim.path("sectionType").asText()) {
                case "CONTEXT" -> "context";
                case "CONTRIBUTION" -> "contribution";
                case "DECISION_REASON" -> "decisionReason";
                case "ACTION" -> "action";
                case "RESULT" -> "result";
                case "LEARNING" -> "learning";
                default -> null;
            };
            if (key != null) draft.put(key, claim.path("content").asText());
        }
        return draft;
    }

    private String modelVersion(JsonNode response) {
        String model = response.path("aiUsage").path("model").asText();
        return model.isBlank() ? "ai-server" : model;
    }
    private List<String> stringList(JsonNode node) {
        List<String> values = new ArrayList<>();
        if (node.isArray()) node.forEach(value -> values.add(value.asText()));
        return values;
    }
    private List<Map<String, Object>> objectList(JsonNode node) {
        if (!node.isArray()) return List.of();
        List<Map<String, Object>> values = new ArrayList<>();
        node.forEach(value -> {
            if (value.isObject()) values.add(objectMap(value));
        });
        return values;
    }
    private Map<String, Object> objectMap(JsonNode node) {
        if (!node.isObject()) return Map.of();
        Map<String, Object> values = new LinkedHashMap<>();
        node.fields().forEachRemaining(entry -> values.put(entry.getKey(), nodeValue(entry.getValue())));
        return values;
    }
    private Object nodeValue(JsonNode node) {
        if (node.isNull()) return null;
        if (node.isTextual()) return node.asText();
        if (node.isBoolean()) return node.asBoolean();
        if (node.isIntegralNumber()) return node.asLong();
        if (node.isFloatingPointNumber()) return node.asDouble();
        if (node.isObject()) return objectMap(node);
        if (node.isArray()) {
            List<Object> values = new ArrayList<>();
            node.forEach(value -> values.add(nodeValue(value)));
            return values;
        }
        return node.asText();
    }
    private String nullableText(JsonNode node, String field) {
        return node.hasNonNull(field) ? node.get(field).asText() : null;
    }
    private String contentHash(String content) {
        try {
            byte[] hash = java.security.MessageDigest.getInstance("SHA-256")
                    .digest(content.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(64);
            for (byte value : hash) result.append(String.format("%02x", value));
            return result.toString();
        } catch (java.security.NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256을 사용할 수 없습니다.", exception);
        }
    }

    private String nullToEmpty(String value) { return value == null ? "" : value; }
}
