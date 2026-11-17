package com.woowa.logfolio.review.service;

import java.util.UUID;

/** Published after the review-session transaction commits. */
public record ReviewRefinementRequestedEvent(UUID userId, UUID reviewSessionId, UUID experienceId) {}
