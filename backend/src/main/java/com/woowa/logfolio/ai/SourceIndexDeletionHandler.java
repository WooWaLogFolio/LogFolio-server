package com.woowa.logfolio.ai;

import com.woowa.logfolio.file.ProjectFileDeletedEvent;
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
        try {
            aiServerClient.deleteSourceIndex(event.projectId(), event.fileId());
        } catch (RuntimeException ignored) {
            // The original file is already deleted. A later cleanup job can safely retry this idempotent call.
        }
    }
}
