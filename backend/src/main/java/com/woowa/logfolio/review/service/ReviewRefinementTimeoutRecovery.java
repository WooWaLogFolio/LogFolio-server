package com.woowa.logfolio.review.service;

import com.woowa.logfolio.review.entity.ReviewSession;
import com.woowa.logfolio.review.repository.ReviewSessionRepository;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/** Prevents crashed or abandoned AI jobs from leaving the UI polling forever. */
@Component
@RequiredArgsConstructor
public class ReviewRefinementTimeoutRecovery {
    private static final Logger log = LoggerFactory.getLogger(ReviewRefinementTimeoutRecovery.class);
    private static final long STALE_AFTER_MINUTES = 5;
    private final ReviewSessionRepository sessionRepository;

    @Scheduled(fixedDelayString = "${app.ai.refinement-recovery-interval-ms:60000}")
    @Transactional
    public void failStaleSessions() {
        var stale = sessionRepository.findAllByStatusAndStartedAtBefore(
                "IN_PROGRESS", LocalDateTime.now().minusMinutes(STALE_AFTER_MINUTES));
        stale.forEach(ReviewSession::fail);
        if (!stale.isEmpty()) {
            log.warn("Marked stale AI refinement sessions as FAILED: count={}", stale.size());
        }
    }
}
