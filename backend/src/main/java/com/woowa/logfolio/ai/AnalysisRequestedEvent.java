package com.woowa.logfolio.ai;

import java.util.UUID;

/** Published by AnalysisService only after its analysis-run transaction commits. */
public record AnalysisRequestedEvent(UUID userId, UUID analysisRunId) {}
