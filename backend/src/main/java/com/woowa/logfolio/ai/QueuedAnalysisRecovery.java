package com.woowa.logfolio.ai;

import com.woowa.logfolio.analysis.repository.AnalysisRunRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.data.domain.PageRequest;

/**
 * Transactional application events are in-memory. Recover runs left in QUEUED
 * by a deploy/restart or a saturated executor instead of leaving the UI polling forever.
 */
@Component
@RequiredArgsConstructor
public class QueuedAnalysisRecovery {
    private final AnalysisRunRepository runRepository;
    private final AnalysisExecutionHandler analysisExecutionHandler;

    @Scheduled(fixedDelayString = "${app.ai.queued-recovery-delay:20000}")
    public void recover() {
        runRepository.findQueuedRuns("QUEUED", PageRequest.of(0, 100)).forEach(run ->
                analysisExecutionHandler.execute(new AnalysisRequestedEvent(
                        run.getUserId(), run.getId()))
        );
    }
}
