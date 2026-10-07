package com.woowa.logfolio.ai;

import java.util.UUID;

/** Published only after an analysis run has been committed to PostgreSQL. */
public record AnalysisRequestedEvent(UUID userId, UUID analysisRunId) {}
