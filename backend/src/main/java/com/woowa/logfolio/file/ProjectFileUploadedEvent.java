package com.woowa.logfolio.file;

import java.util.UUID;

/** Published after a project file is safely stored and committed. */
public record ProjectFileUploadedEvent(UUID userId, UUID fileId) {}
