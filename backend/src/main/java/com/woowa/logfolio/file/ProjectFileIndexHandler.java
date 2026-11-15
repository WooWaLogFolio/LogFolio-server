package com.woowa.logfolio.file;

import com.woowa.logfolio.ai.AiServerProperties;
import com.woowa.logfolio.ai.AiSourceIndexService;
import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.file.repository.ProjectFileRepository;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import java.nio.file.Path;

@Component
@RequiredArgsConstructor
public class ProjectFileIndexHandler {
    private static final Logger log = LoggerFactory.getLogger(ProjectFileIndexHandler.class);

    private final ProjectFileRepository repository;
    private final DocumentTextExtractor textExtractor;
    private final AiSourceIndexService sourceIndexService;
    private final AiServerProperties aiServerProperties;

    @Value("${app.storage.root:./storage/uploads}")
    private String storageRoot;

    @Async("aiTaskExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void index(ProjectFileUploadedEvent event) {
        if (!aiServerProperties.enabled()) {
            log.info("Project file indexing skipped because AI server is disabled: fileId={}", event.fileId());
            return;
        }
        ProjectFile file = repository.findById(event.fileId()).orElse(null);
        if (file == null) {
            log.warn("Project file indexing skipped because the file row was not found: fileId={}", event.fileId());
            return;
        }
        if (file.getDeletedAt() != null) {
            log.info("Project file indexing skipped because the file was deleted: fileId={}", file.getId());
            return;
        }

        Path root = Path.of(storageRoot).toAbsolutePath().normalize();
        Path source = root.resolve(file.getStorageKey()).normalize();
        if (!source.startsWith(root)) {
            log.error("Project file indexing rejected an invalid storage path: fileId={}, name={}, root={}, source={}",
                    file.getId(), file.getOriginalName(), root, source);
            file.failed();
            return;
        }
        try {
            log.info("Project file text extraction started: fileId={}, name={}, source={}",
                    file.getId(), file.getOriginalName(), source);
            var pages = textExtractor.extract(source, file.getOriginalName());
            log.info("Project file text extraction completed: fileId={}, name={}, pageCount={}",
                    file.getId(), file.getOriginalName(), pages.size());
            String status = sourceIndexService.indexExtractedProjectFile(event.userId(), file.getId(), pages);
            if ("INDEXED".equals(status)) {
                log.info("Project file indexing completed: fileId={}, name={}, status={}",
                        file.getId(), file.getOriginalName(), status);
            } else {
                log.warn("Project file indexing completed without success: fileId={}, name={}, status={}",
                        file.getId(), file.getOriginalName(), status);
            }
        } catch (RuntimeException exception) {
            log.error("Project file text extraction or indexing failed: fileId={}, name={}, source={}",
                    file.getId(), file.getOriginalName(), source, exception);
            file.failed();
        }
    }
}
