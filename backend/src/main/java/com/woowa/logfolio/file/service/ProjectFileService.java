package com.woowa.logfolio.file.service;

import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.file.ProjectFileDeletedEvent;
import com.woowa.logfolio.file.ProjectFileUploadedEvent;
import com.woowa.logfolio.file.repository.ProjectFileRepository;
import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.project.service.ProjectService;
import com.woowa.logfolio.user.entity.User;
import com.woowa.logfolio.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProjectFileService {
    private static final long MAX_FILE_SIZE = 50L * 1024 * 1024;
    private static final long DEFAULT_QUOTA = 1024L * 1024 * 1024;
    private static final Set<String> ALLOWED_EXTENSIONS = Set.of("pdf", "ppt", "pptx", "doc", "docx", "fig");

    private final ProjectFileRepository repository;
    private final ProjectService projectService;
    private final UserService userService;
    private final ApplicationEventPublisher eventPublisher;

    @Value("${app.storage.root:./storage/uploads}")
    private String storageRoot;

    @Transactional
    public FileResponse upload(UUID userId, UUID projectId, MultipartFile multipart) {
        validateFile(multipart);
        long used = repository.sumActiveSizeByUserId(userId);
        if (used + multipart.getSize() > DEFAULT_QUOTA) {
            throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE, "저장공간이 부족합니다.");
        }
        Project project = projectService.findOwnedProject(userId, projectId);
        User user = userService.findActiveUser(userId);
        String originalName = safeOriginalName(multipart.getOriginalFilename());
        String storageKey = userId + "/" + projectId + "/" + UUID.randomUUID() + extension(originalName);
        Path target = Path.of(storageRoot).toAbsolutePath().normalize().resolve(storageKey).normalize();
        if (!target.startsWith(Path.of(storageRoot).toAbsolutePath().normalize())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "올바르지 않은 파일명입니다.");
        }
        try {
            Files.createDirectories(target.getParent());
            Files.copy(multipart.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException exception) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "파일 저장에 실패했습니다.", exception);
        }
        ProjectFile file = repository.save(new ProjectFile(project, user, originalName, storageKey,
                multipart.getContentType() == null ? "application/octet-stream" : multipart.getContentType(),
                multipart.getSize()));
        eventPublisher.publishEvent(new ProjectFileUploadedEvent(userId, file.getId()));
        return FileResponse.from(file);
    }

    public List<FileResponse> listByProject(UUID userId, UUID projectId) {
        projectService.findOwnedProject(userId, projectId);
        return repository.findAllByProjectIdAndUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(projectId, userId)
                .stream().map(FileResponse::from).toList();
    }

    public StorageResponse storage(UUID userId) {
        userService.findActiveUser(userId);
        List<FileResponse> files = repository.findAllByUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(userId)
                .stream().map(FileResponse::from).toList();
        long used = repository.sumActiveSizeByUserId(userId);
        return new StorageResponse(used, DEFAULT_QUOTA, DEFAULT_QUOTA - used, files.size(), files);
    }

    @Transactional
    public void delete(UUID userId, UUID fileId) {
        ProjectFile file = repository.findByIdAndUserIdAndDeletedAtIsNull(fileId, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "파일을 찾을 수 없습니다."));
        Path target = Path.of(storageRoot).toAbsolutePath().normalize().resolve(file.getStorageKey()).normalize();
        try { Files.deleteIfExists(target); }
        catch (IOException exception) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "파일 삭제에 실패했습니다.", exception);
        }
        file.delete();
        eventPublisher.publishEvent(new ProjectFileDeletedEvent(file.getProject().getId(), file.getId()));
    }

    @Transactional
    public FileResponse retryIndexing(UUID userId, UUID fileId) {
        ProjectFile file = findOwned(userId, fileId);
        file.processing();
        eventPublisher.publishEvent(new ProjectFileUploadedEvent(userId, file.getId()));
        return FileResponse.from(file);
    }

    public ProjectFile findOwned(UUID userId, UUID fileId) {
        return repository.findByIdAndUserIdAndDeletedAtIsNull(fileId, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "파일을 찾을 수 없습니다."));
    }

    private void validateFile(MultipartFile file) {
        if (file == null || file.isEmpty()) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "파일이 비어 있습니다.");
        if (file.getSize() > MAX_FILE_SIZE) throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE, "파일은 최대 50MB입니다.");
        String ext = extensionWithoutDot(safeOriginalName(file.getOriginalFilename()));
        if (!ALLOWED_EXTENSIONS.contains(ext)) {
            throw new ResponseStatusException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "PDF, PPT, PPTX, DOC, DOCX, FIG 파일만 지원합니다.");
        }
    }

    private String safeOriginalName(String name) {
        if (name == null || name.isBlank()) return "file";
        return Path.of(name).getFileName().toString();
    }
    private String extensionWithoutDot(String name) {
        int dot = name.lastIndexOf('.');
        return dot < 0 ? "" : name.substring(dot + 1).toLowerCase(Locale.ROOT);
    }
    private String extension(String name) {
        String ext = extensionWithoutDot(name);
        return ext.isEmpty() ? "" : "." + ext;
    }

    public record FileResponse(UUID id, UUID projectId, String originalName, String mimeType,
                               long sizeBytes, String processingStatus, LocalDateTime createdAt) {
        static FileResponse from(ProjectFile file) {
            return new FileResponse(file.getId(), file.getProject().getId(), file.getOriginalName(),
                    file.getMimeType(), file.getSizeBytes(), file.getProcessingStatus(), file.getCreatedAt());
        }
    }
    public record StorageResponse(long usedBytes, long quotaBytes, long remainingBytes,
                                  int fileCount, List<FileResponse> files) {}
}
