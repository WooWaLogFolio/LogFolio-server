package com.woowa.logfolio.ai;

import java.util.List;
import java.util.UUID;

public record SourceIndexRequestedEvent(
        UUID projectId,
        UUID sourceId,
        String sourceType,
        String sourceName,
        String mimeType,
        List<AiServerContract.Page> pages
) {
    public static SourceIndexRequestedEvent quickLog(UUID projectId, UUID sourceId, String content) {
        return new SourceIndexRequestedEvent(
                projectId,
                sourceId,
                "QUICK_LOG",
                "30초 기록",
                "text/plain",
                List.of(new AiServerContract.Page(null, content))
        );
    }
}
