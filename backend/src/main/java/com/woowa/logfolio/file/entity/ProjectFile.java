package com.woowa.logfolio.file.entity;

import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.user.entity.User;
import jakarta.persistence.*;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "project_files")
public class ProjectFile {
    @Id private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "project_id", nullable = false)
    private Project project;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "original_name", nullable = false) private String originalName;
    @Column(name = "storage_key", nullable = false, length = 500, unique = true) private String storageKey;
    @Column(name = "mime_type", nullable = false, length = 100) private String mimeType;
    @Column(name = "size_bytes", nullable = false) private long sizeBytes;
    @Column(name = "processing_status", nullable = false, length = 30) private String processingStatus;
    @Column(name = "created_at", nullable = false, updatable = false) private LocalDateTime createdAt;
    @Column(name = "deleted_at") private LocalDateTime deletedAt;

    protected ProjectFile() {}

    public ProjectFile(Project project, User user, String originalName, String storageKey,
                       String mimeType, long sizeBytes) {
        this.id = UUID.randomUUID();
        this.project = project;
        this.user = user;
        this.originalName = originalName;
        this.storageKey = storageKey;
        this.mimeType = mimeType;
        this.sizeBytes = sizeBytes;
        this.processingStatus = "UPLOADED";
    }

    @PrePersist void onCreate() { createdAt = LocalDateTime.now(); }
    public void delete() { deletedAt = LocalDateTime.now(); }
    public void processing() { processingStatus = "PROCESSING"; }
    public void processed() { processingStatus = "PROCESSED"; }
    public void failed() { processingStatus = "FAILED"; }

    public UUID getId() { return id; }
    public Project getProject() { return project; }
    public String getOriginalName() { return originalName; }
    public String getStorageKey() { return storageKey; }
    public String getMimeType() { return mimeType; }
    public long getSizeBytes() { return sizeBytes; }
    public String getProcessingStatus() { return processingStatus; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
