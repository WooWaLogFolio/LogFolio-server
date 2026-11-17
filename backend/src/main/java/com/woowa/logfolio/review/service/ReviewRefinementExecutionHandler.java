package com.woowa.logfolio.review.service;

import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class ReviewRefinementExecutionHandler {
    private static final Logger log = LoggerFactory.getLogger(ReviewRefinementExecutionHandler.class);
    private final ReviewRefinementProcessor processor;

    @Async("aiTaskExecutor")
    @EventListener
    public void execute(ReviewRefinementRequestedEvent event) {
        try {
            processor.process(event);
        } catch (RuntimeException exception) {
            log.error("AI experience refinement failed: sessionId={}, experienceId={}",
                    event.reviewSessionId(), event.experienceId(), exception);
            try {
                processor.fail(event);
            } catch (RuntimeException failureUpdateException) {
                log.error("Failed to mark review session as FAILED: sessionId={}",
                        event.reviewSessionId(), failureUpdateException);
            }
        }
    }
}
