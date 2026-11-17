package com.woowa.logfolio.review.service;

import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class ReviewRefinementExecutionHandlerTest {
    @Test
    void marksSessionFailedWhenRefinementThrows() {
        ReviewRefinementProcessor processor = mock(ReviewRefinementProcessor.class);
        ReviewRefinementExecutionHandler handler = new ReviewRefinementExecutionHandler(processor);
        ReviewRefinementRequestedEvent event = new ReviewRefinementRequestedEvent(
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID());
        doThrow(new IllegalStateException("failure")).when(processor).process(event);

        handler.execute(event);

        verify(processor).fail(event);
    }
}
