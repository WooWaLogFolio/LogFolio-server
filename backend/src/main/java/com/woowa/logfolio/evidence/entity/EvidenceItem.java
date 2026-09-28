package com.woowa.logfolio.evidence.entity;

import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.quicklog.entity.QuickLog;
import jakarta.persistence.*;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "evidence_items")
public class EvidenceItem {
    @Id private UUID id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "project_id", nullable = false) private Project project;
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "project_file_id") private ProjectFile projectFile;
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "quick_log_id") private QuickLog quickLog;
    @Column(columnDefinition = "text") private String excerpt;
    @Column(length = 255) private String location;
    @Column(name = "created_at", nullable = false, updatable = false) private LocalDateTime createdAt;
    protected EvidenceItem() {}
    @PrePersist void onCreate() { createdAt = LocalDateTime.now(); }
    public UUID getId() { return id; }
    public Project getProject() { return project; }
    public ProjectFile getProjectFile() { return projectFile; }
    public QuickLog getQuickLog() { return quickLog; }
    public String getExcerpt() { return excerpt; }
    public String getLocation() { return location; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
