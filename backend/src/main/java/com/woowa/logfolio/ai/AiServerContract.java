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
            String contentHash,
            List<Page> pages
    ) {
        public Source(UUID sourceId, String sourceType, String sourceName, String mimeType, List<Page> pages) {
            this(sourceId, sourceType, sourceName, mimeType, null, pages);
        }
    }

    public record SourceIndexRequest(UUID projectId, List<Source> sources) {}

    public record SourceIndexItem(
            UUID sourceId,
            String sourceType,
            String status,
            int chunkCount,
            UUID duplicateOfSourceId,
            String errorCode
    ) {
        public SourceIndexItem(UUID sourceId, String sourceType, String status, int chunkCount, String errorCode) {
            this(sourceId, sourceType, status, chunkCount, null, errorCode);
        }
    }

    public record SourceIndexResponse(
            UUID projectId,
            int indexedCount,
            int duplicateCount,
            int failedCount,
            List<SourceIndexItem> items
    ) {
        public SourceIndexResponse(UUID projectId, int indexedCount, int failedCount, List<SourceIndexItem> items) {
            this(projectId, indexedCount, 0, failedCount, items);
        }
    }
}
