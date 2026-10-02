package com.woowa.logfolio.quicklog.entity;

import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.user.entity.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "quick_logs")
public class QuickLog {

    @Id
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "project_id")
    private Project project;

    @Column(nullable = false, columnDefinition = "text")
    private String content;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @Column(name = "deleted_at")
    private LocalDateTime deletedAt;

    @Column(name = "processing_status", length = 30)
    private String processingStatus;

    protected QuickLog() {}

    public QuickLog(User user, Project project, String content) {
        this.id = UUID.randomUUID();
        this.user = user;
        this.project = project;
        this.content = content;
    }

    @PrePersist
    void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = createdAt;
    }

    @PreUpdate
    void onUpdate() { updatedAt = LocalDateTime.now(); }

    public void updateContent(String content) { this.content = content; }
    public void linkProject(Project project) { this.project = project; }
    public void processing() { this.processingStatus = "PROCESSING"; }
    public void indexed() { this.processingStatus = "INDEXED"; }
    public void failed() { this.processingStatus = "FAILED"; }
    public void delete() { this.deletedAt = LocalDateTime.now(); }

    public UUID getId() { return id; }
    public User getUser() { return user; }
    public Project getProject() { return project; }
    public String getContent() { return content; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public String getProcessingStatus() { return processingStatus; }
}
