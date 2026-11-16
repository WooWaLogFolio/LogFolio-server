package com.woowa.logfolio.ai;

import com.woowa.logfolio.quicklog.entity.QuickLog;
import com.woowa.logfolio.quicklog.repository.QuickLogRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import java.util.List;

@Component
@RequiredArgsConstructor
public class SourceIndexEventHandler {
    private final AiServerClient aiServerClient;
    private final QuickLogRepository quickLogRepository;

    @Async("aiTaskExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void index(SourceIndexRequestedEvent event) {
        if (!"QUICK_LOG".equals(event.sourceType())) return;
        QuickLog log = quickLogRepository.findById(event.sourceId()).orElse(null);
        if (log == null || log.getProject() == null
                || !log.getProject().getId().equals(event.projectId())) return;

        try {
            AiServerContract.SourceIndexResponse response = callWithOneRetry(event);
            AiServerContract.SourceIndexItem item = response.items() == null ? null : response.items().stream()
                    .filter(candidate -> event.sourceId().equals(candidate.sourceId()))
                    .findFirst().orElse(null);
            if (item != null && "INDEXED".equals(item.status())) log.indexed();
            else if (item != null && "DUPLICATE".equals(item.status()) && item.duplicateOfSourceId() != null) {
                log.indexedAsDuplicateOf(item.duplicateOfSourceId());
            } else log.failed();
        } catch (RuntimeException exception) {
            log.failed();
        }
    }

    private AiServerContract.SourceIndexResponse callWithOneRetry(SourceIndexRequestedEvent event) {
        AiServerContract.Source source = new AiServerContract.Source(
                event.sourceId(), event.sourceType(), event.sourceName(), event.mimeType(), event.contentHash(), event.pages()
        );
        AiServerContract.SourceIndexRequest request = new AiServerContract.SourceIndexRequest(
                event.projectId(), List.of(source)
        );
        try {
            return aiServerClient.indexSources(request);
        } catch (AiServerException firstFailure) {
            if (!firstFailure.isRetryable()) throw firstFailure;
            return aiServerClient.indexSources(request);
        }
    }
}
