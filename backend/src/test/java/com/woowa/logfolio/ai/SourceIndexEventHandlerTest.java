package com.woowa.logfolio.ai;

import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.project.entity.ProjectStatus;
import com.woowa.logfolio.quicklog.entity.QuickLog;
import com.woowa.logfolio.quicklog.repository.QuickLogRepository;
import com.woowa.logfolio.user.entity.User;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SourceIndexEventHandlerTest {

    @Test
    void marksQuickLogIndexedWhenFastApiAcceptsTheSource() {
        AiServerClient client = mock(AiServerClient.class);
        QuickLogRepository repository = mock(QuickLogRepository.class);
        User user = new User("ai@example.com", "AI 사용자");
        Project project = new Project(user, "LogFolio", ProjectStatus.IN_PROGRESS,
                null, null, null, List.of(), null, null, null);
        QuickLog log = new QuickLog(user, project, "검색 구조를 결정했다.");
        log.processing();
        SourceIndexRequestedEvent event = SourceIndexRequestedEvent.quickLog(
                project.getId(), log.getId(), log.getContent()
        );
        when(repository.findById(log.getId())).thenReturn(Optional.of(log));
        when(client.indexSources(any())).thenReturn(new AiServerContract.SourceIndexResponse(
                project.getId(),
                1,
                0,
                List.of(new AiServerContract.SourceIndexItem(
                        log.getId(), "QUICK_LOG", "INDEXED", 1, null
                ))
        ));

        new SourceIndexEventHandler(client, repository).index(event);

        assertThat(log.getProcessingStatus()).isEqualTo("INDEXED");
        verify(client, times(1)).indexSources(any());
    }

    @Test
    void retriesOneTimeAndMarksQuickLogFailed() {
        AiServerClient client = mock(AiServerClient.class);
        QuickLogRepository repository = mock(QuickLogRepository.class);
        User user = new User("retry@example.com", "재시도 사용자");
        Project project = new Project(user, "LogFolio", ProjectStatus.IN_PROGRESS,
                null, null, null, List.of(), null, null, null);
        QuickLog log = new QuickLog(user, project, "재시도 테스트");
        log.processing();
        SourceIndexRequestedEvent event = SourceIndexRequestedEvent.quickLog(
                project.getId(), log.getId(), log.getContent()
        );
        when(repository.findById(log.getId())).thenReturn(Optional.of(log));
        when(client.indexSources(any())).thenThrow(
                new AiServerException("temporary", true, null)
        );

        new SourceIndexEventHandler(client, repository).index(event);

        assertThat(log.getProcessingStatus()).isEqualTo("FAILED");
        verify(client, times(2)).indexSources(any());
    }
}
