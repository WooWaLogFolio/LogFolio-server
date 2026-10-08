package com.woowa.logfolio.file;

import java.util.UUID;

/** Removes the corresponding private RAG index after the source has been deleted. */
public record ProjectFileDeletedEvent(UUID projectId, UUID fileId) {}
