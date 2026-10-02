package com.woowa.logfolio.ai;

import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.file.service.ProjectFileService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class AiSourceIndexService {
    private final AiServerClient aiServerClient;
    private final AiServerProperties properties;
    private final ProjectFileService projectFileService;

    /**
     * File extraction is Spring-owned. Call this method only after extracted page text exists.
     */
    @Transactional
    public String indexExtractedProjectFile(
            UUID userId,
            UUID fileId,
            List<AiServerContract.Page> extractedPages
    ) {
        if (!properties.enabled()) return "DISABLED";
        if (extractedPages == null || extractedPages.isEmpty()) {
            throw new IllegalArgumentException("추출된 파일 텍스트가 필요합니다.");
        }
        ProjectFile file = projectFileService.findOwned(userId, fileId);
        file.processing();
        AiServerContract.Source source = new AiServerContract.Source(
                file.getId(),
                "PROJECT_FILE",
                file.getOriginalName(),
                file.getMimeType(),
                extractedPages
        );
        try {
            AiServerContract.SourceIndexResponse response = callWithOneRetry(
                    new AiServerContract.SourceIndexRequest(
                            file.getProject().getId(), List.of(source)
                    )
            );
            boolean indexed = response.items() != null && response.items().stream()
                    .anyMatch(item -> file.getId().equals(item.sourceId())
                            && "INDEXED".equals(item.status()));
            if (indexed) {
                file.indexed();
                return "INDEXED";
            }
            file.failed();
            return "FAILED";
        } catch (RuntimeException exception) {
            file.failed();
            return "FAILED";
        }
    }

    private AiServerContract.SourceIndexResponse callWithOneRetry(
            AiServerContract.SourceIndexRequest request
    ) {
        try {
            return aiServerClient.indexSources(request);
        } catch (AiServerException firstFailure) {
            if (!firstFailure.isRetryable()) throw firstFailure;
            return aiServerClient.indexSources(request);
        }
    }
}
