package com.woowa.logfolio.review.service;

import com.woowa.logfolio.ai.AiServerClient;
import com.woowa.logfolio.evidence.entity.EvidenceItem;
import com.woowa.logfolio.evidence.repository.EvidenceItemRepository;
import com.woowa.logfolio.experience.entity.Experience;
import com.woowa.logfolio.experience.service.ExperienceService;
import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.review.entity.ReviewSession;
import com.woowa.logfolio.review.repository.GapQuestionRepository;
import com.woowa.logfolio.review.repository.ReviewItemRepository;
import com.woowa.logfolio.review.repository.ReviewSessionRepository;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ReviewRefinementProcessorTest {
    @Test
    void storesReviewItemsAndQuestionsThenMakesSessionReviewReady() throws Exception {
        ReviewSessionRepository sessions = mock(ReviewSessionRepository.class);
        ReviewItemRepository items = mock(ReviewItemRepository.class);
        GapQuestionRepository questions = mock(GapQuestionRepository.class);
        EvidenceItemRepository evidences = mock(EvidenceItemRepository.class);
        ExperienceService experiences = mock(ExperienceService.class);
        AiServerClient client = mock(AiServerClient.class);
        ReviewRefinementProcessor processor = new ReviewRefinementProcessor(
                sessions, items, questions, evidences, experiences, client);

        UUID userId = UUID.randomUUID();
        UUID sessionId = UUID.randomUUID();
        UUID experienceId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        UUID sourceId = UUID.randomUUID();
        UUID evidenceId = UUID.randomUUID();
        UUID chunkId = UUID.randomUUID();
        UUID questionId = UUID.randomUUID();
        ReviewRefinementRequestedEvent event = new ReviewRefinementRequestedEvent(userId, sessionId, experienceId);

        ReviewSession session = mock(ReviewSession.class);
        Experience experience = mock(Experience.class);
        Project project = mock(Project.class);
        EvidenceItem evidence = mock(EvidenceItem.class);
        ProjectFile file = mock(ProjectFile.class);
        when(sessions.findByIdAndProjectUserId(sessionId, userId)).thenReturn(Optional.of(session));
        when(session.getId()).thenReturn(sessionId);
        when(session.getStatus()).thenReturn("IN_PROGRESS");
        when(session.getProject()).thenReturn(project);
        when(experiences.findOwned(userId, experienceId)).thenReturn(experience);
        when(experience.getId()).thenReturn(experienceId);
        when(experience.getTitle()).thenReturn("기존 경험");
        when(experience.getProject()).thenReturn(project);
        when(project.getId()).thenReturn(projectId);
        when(project.getName()).thenReturn("LogFolio");
        when(evidences.findAllForExperience(experienceId, userId)).thenReturn(List.of(evidence));
        when(evidence.getId()).thenReturn(evidenceId);
        when(evidence.getProjectFile()).thenReturn(file);
        when(evidence.getChunkId()).thenReturn(chunkId);
        when(file.getProcessingStatus()).thenReturn("INDEXED");
        when(file.getRetrievalSourceId()).thenReturn(sourceId);
        when(questions.findAllByExperienceIdAndExperienceProjectUserIdOrderByDisplayOrder(experienceId, userId))
                .thenReturn(List.of());

        JsonNode response = JsonMapper.builder().build().readTree("""
                {"reviewSessionId":"%s","projectId":"%s","experienceId":"%s","status":"REVIEW_READY",
                 "summary":"제안","reviewItems":[{"itemType":"ACTION","proposedContent":"개선된 실행"}],
                 "questions":[{"questionId":"%s","targetSection":"RESULT","question":"성과는?",
                 "suggestedAnswers":["응답"]}]}
                """.formatted(sessionId, projectId, experienceId, questionId));
        when(client.refineExperience(any())).thenReturn(response);

        processor.process(event);

        ArgumentCaptor<Map<String, Object>> request = ArgumentCaptor.forClass(Map.class);
        verify(client).refineExperience(request.capture());
        assertThat(request.getValue().get("sourceIds")).isEqualTo(List.of(sourceId));
        verify(items).saveAll(any());
        verify(questions).saveAll(any());
        verify(session).reviewReady();
    }
}
