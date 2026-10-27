package com.woowa.logfolio.ai;

import com.woowa.logfolio.analysis.entity.AnalysisRun;
import com.woowa.logfolio.analysis.repository.AnalysisRunRepository;
import com.woowa.logfolio.analysis.service.AnalysisService;
import com.woowa.logfolio.experience.repository.ExperienceRepository;
import com.woowa.logfolio.file.DocumentTextExtractor;
import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.quicklog.entity.QuickLog;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class AnalysisExecutionHandlerTest {

    @Test
    void reusesAlreadyIndexedSourcesWithoutIndexingThemAgain() {
        AiServerClient client = mock(AiServerClient.class);
        DocumentTextExtractor extractor = mock(DocumentTextExtractor.class);
        AnalysisExecutionHandler handler = handler(client, extractor);
        AnalysisRun run = mock(AnalysisRun.class);
        ProjectFile file = mock(ProjectFile.class);
        QuickLog log = mock(QuickLog.class);
        UUID fileId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();

        when(file.getId()).thenReturn(fileId);
        when(file.getProcessingStatus()).thenReturn("INDEXED");
        when(log.getId()).thenReturn(logId);
        when(log.getProcessingStatus()).thenReturn("INDEXED");
        when(run.getInputFiles()).thenReturn(Set.of(file));
        when(run.getInputLogs()).thenReturn(Set.of(log));

        List<UUID> sourceIds = ReflectionTestUtils.invokeMethod(handler, "indexInputSources", run);

        assertThat(sourceIds).containsExactlyInAnyOrder(fileId, logId);
        verifyNoInteractions(client, extractor);
    }

    @Test
    void analyzesCanonicalSourceWhenQuickLogContentIsAnExactDuplicate() {
        AiServerClient client = mock(AiServerClient.class);
        AnalysisExecutionHandler handler = handler(client, mock(DocumentTextExtractor.class));
        AnalysisRun run = mock(AnalysisRun.class);
        QuickLog log = mock(QuickLog.class);
        Project project = mock(Project.class);
        UUID projectId = UUID.randomUUID();
        UUID duplicateId = UUID.randomUUID();
        UUID canonicalId = UUID.randomUUID();

        when(run.getInputFiles()).thenReturn(Set.of());
        when(run.getInputLogs()).thenReturn(Set.of(log));
        when(run.getProject()).thenReturn(project);
        when(project.getId()).thenReturn(projectId);
        when(log.getId()).thenReturn(duplicateId);
        when(log.getContent()).thenReturn("동일한 기록");
        when(client.indexSources(any())).thenReturn(new AiServerContract.SourceIndexResponse(
                projectId, 0, 1, 0,
                List.of(new AiServerContract.SourceIndexItem(
                        duplicateId, "QUICK_LOG", "DUPLICATE", 0, canonicalId, null
                ))
        ));

        List<UUID> sourceIds = ReflectionTestUtils.invokeMethod(handler, "indexInputSources", run);

        assertThat(sourceIds).containsExactly(canonicalId);
    }

    private AnalysisExecutionHandler handler(AiServerClient client, DocumentTextExtractor extractor) {
        return new AnalysisExecutionHandler(
                mock(AnalysisRunRepository.class),
                mock(ExperienceRepository.class),
                mock(AnalysisService.class),
                client,
                extractor
        );
    }
}
