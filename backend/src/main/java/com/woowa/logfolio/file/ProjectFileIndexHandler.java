package com.woowa.logfolio.file;

import com.woowa.logfolio.ai.AiServerProperties;
import com.woowa.logfolio.ai.AiSourceIndexService;
import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.file.repository.ProjectFileRepository;
import lombok.RequiredArgsConstructor;
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
        if (!aiServerProperties.enabled()) return;
        ProjectFile file = repository.findById(event.fileId()).orElse(null);
        if (file == null || file.getDeletedAt() != null) return;

        Path root = Path.of(storageRoot).toAbsolutePath().normalize();
        Path source = root.resolve(file.getStorageKey()).normalize();
        if (!source.startsWith(root)) {
            file.failed();
            return;
        }
        try {
            sourceIndexService.indexExtractedProjectFile(event.userId(), file.getId(),
                    textExtractor.extract(source, file.getOriginalName()));
        } catch (RuntimeException exception) {
            file.failed();
        }
    }
}
