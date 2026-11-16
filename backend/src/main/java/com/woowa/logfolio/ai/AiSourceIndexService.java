package com.woowa.logfolio.ai;

import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.file.service.ProjectFileService;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class AiSourceIndexService {
    private static final Logger log = LoggerFactory.getLogger(AiSourceIndexService.class);

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
                file.getContentHash(),
                extractedPages
        );
        try {
            AiServerContract.SourceIndexResponse response = callWithOneRetry(
                    new AiServerContract.SourceIndexRequest(
                            file.getProject().getId(), List.of(source)
                    )
            );
            AiServerContract.SourceIndexItem item = response.items() == null ? null : response.items().stream()
                    .filter(candidate -> file.getId().equals(candidate.sourceId()))
                    .findFirst().orElse(null);
            if (item != null && "INDEXED".equals(item.status()) && item.chunkCount() > 0) {
                file.indexed();
                log.info("AI source indexing accepted the project file: fileId={}, projectId={}, response={}",
                        file.getId(), file.getProject().getId(), response);
                return "INDEXED";
            }
            if (item != null && "DUPLICATE".equals(item.status()) && item.duplicateOfSourceId() != null) {
                file.indexedAsDuplicateOf(item.duplicateOfSourceId());
                log.info("AI source indexing linked a duplicate project file: fileId={}, canonicalSourceId={}",
                        file.getId(), item.duplicateOfSourceId());
                return "INDEXED";
            }
            log.warn("AI source indexing rejected the project file or returned no chunks: fileId={}, projectId={}, response={}",
                    file.getId(), file.getProject().getId(), response);
            file.failed();
            return "FAILED";
        } catch (RuntimeException exception) {
            log.error("AI source indexing request failed: fileId={}, projectId={}, name={}",
                    file.getId(), file.getProject().getId(), file.getOriginalName(), exception);
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
            log.warn("Retrying AI source indexing after a retryable failure: projectId={}, sourceIds={}",
                    request.projectId(), request.sources().stream().map(AiServerContract.Source::sourceId).toList(),
                    firstFailure);
            return aiServerClient.indexSources(request);
        }
    }
}
