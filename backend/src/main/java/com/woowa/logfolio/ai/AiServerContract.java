package com.woowa.logfolio.ai;

import java.util.List;
import java.util.UUID;

public final class AiServerContract {
    private AiServerContract() {}

    public record Page(Integer pageNumber, String text) {}

    public record Source(
            UUID sourceId,
            String sourceType,
            String sourceName,
            String mimeType,
            List<Page> pages
    ) {}

    public record SourceIndexRequest(UUID projectId, List<Source> sources) {}

    public record SourceIndexItem(
            UUID sourceId,
            String sourceType,
            String status,
            int chunkCount,
            String errorCode
    ) {}

    public record SourceIndexResponse(
            UUID projectId,
            int indexedCount,
            int failedCount,
            List<SourceIndexItem> items
    ) {}
}
