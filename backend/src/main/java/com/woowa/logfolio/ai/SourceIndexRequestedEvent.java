package com.woowa.logfolio.ai;

import java.util.List;
import java.util.UUID;

public record SourceIndexRequestedEvent(
        UUID projectId,
        UUID sourceId,
        String sourceType,
        String sourceName,
        String mimeType,
        String contentHash,
        List<AiServerContract.Page> pages
) {
    public static SourceIndexRequestedEvent quickLog(UUID projectId, UUID sourceId, String content) {
        return new SourceIndexRequestedEvent(
                projectId,
                sourceId,
                "QUICK_LOG",
                "30초 기록",
                "text/plain",
                sha256(content),
                List.of(new AiServerContract.Page(null, content))
        );
    }
    private static String sha256(String content) {
        try {
            byte[] hash = java.security.MessageDigest.getInstance("SHA-256")
                    .digest(content.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(64);
            for (byte value : hash) result.append(String.format("%02x", value));
            return result.toString();
        } catch (java.security.NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256을 사용할 수 없습니다.", exception);
        }
    }
}
