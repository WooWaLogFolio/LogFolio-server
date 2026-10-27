package com.woowa.logfolio.ai;

import com.woowa.logfolio.file.ProjectFileDeletedEvent;
import com.woowa.logfolio.quicklog.QuickLogIndexDeletedEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Component
@RequiredArgsConstructor
public class SourceIndexDeletionHandler {
    private final AiServerClient aiServerClient;

    @Async("aiTaskExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void delete(ProjectFileDeletedEvent event) {
        deleteIndex(event.projectId(), event.fileId());
    }

    @Async("aiTaskExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void delete(QuickLogIndexDeletedEvent event) {
        deleteIndex(event.projectId(), event.quickLogId());
    }

    private void deleteIndex(java.util.UUID projectId, java.util.UUID sourceId) {
        try {
            aiServerClient.deleteSourceIndex(projectId, sourceId);
        } catch (RuntimeException ignored) {
            // The original file is already deleted. A later cleanup job can safely retry this idempotent call.
        }
    }
}
