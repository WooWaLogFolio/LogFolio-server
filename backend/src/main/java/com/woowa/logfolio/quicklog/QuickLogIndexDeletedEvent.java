package com.woowa.logfolio.quicklog;

import java.util.UUID;

/** Published after a Quick Log leaves a project or is deleted, so its private RAG chunks are removed. */
public record QuickLogIndexDeletedEvent(UUID projectId, UUID quickLogId) {}
