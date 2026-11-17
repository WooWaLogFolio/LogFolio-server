package com.woowa.logfolio.review.service;

import com.woowa.logfolio.review.entity.ReviewSession;
import com.woowa.logfolio.review.repository.ReviewSessionRepository;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ReviewRefinementTimeoutRecoveryTest {
    @Test
    void marksStaleInProgressSessionsFailed() {
        ReviewSessionRepository repository = mock(ReviewSessionRepository.class);
        ReviewSession session = mock(ReviewSession.class);
        when(repository.findAllByStatusAndStartedAtBefore(any(), any())).thenReturn(List.of(session));

        new ReviewRefinementTimeoutRecovery(repository).failStaleSessions();

        verify(session).fail();
    }
}
