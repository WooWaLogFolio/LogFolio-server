package com.woowa.logfolio.analysis.entity;

import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.quicklog.entity.QuickLog;
import jakarta.persistence.*;

import java.time.LocalDateTime;
import java.util.UUID;
import java.util.LinkedHashSet;
import java.util.Set;

@Entity
@Table(name = "analysis_runs")
public class AnalysisRun {
    @Id private UUID id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "project_id", nullable = false)
    private Project project;
    @Column(name = "run_type", nullable = false, length = 30) private String runType;
    @Column(nullable = false, length = 30) private String status;
    @Column(name = "model_version", length = 100) private String modelVersion;
    @Column(name = "started_at") private LocalDateTime startedAt;
    @Column(name = "completed_at") private LocalDateTime completedAt;
    @Column(name = "created_at", nullable = false, updatable = false) private LocalDateTime createdAt;
    @ManyToMany
    @JoinTable(name = "analysis_input_files",
            joinColumns = @JoinColumn(name = "analysis_run_id"),
            inverseJoinColumns = @JoinColumn(name = "project_file_id"))
    private Set<ProjectFile> inputFiles = new LinkedHashSet<>();
    @ManyToMany
    @JoinTable(name = "analysis_input_logs",
            joinColumns = @JoinColumn(name = "analysis_run_id"),
            inverseJoinColumns = @JoinColumn(name = "quick_log_id"))
    private Set<QuickLog> inputLogs = new LinkedHashSet<>();

    protected AnalysisRun() {}
    public AnalysisRun(Project project, String runType) {
        this.id = UUID.randomUUID(); this.project = project; this.runType = runType; this.status = "QUEUED";
    }
    @PrePersist void onCreate() { createdAt = LocalDateTime.now(); }
    public void start(String modelVersion) { status = "PROCESSING"; startedAt = LocalDateTime.now(); this.modelVersion = modelVersion; }
    public void reviewReady(String modelVersion) {
        if (startedAt == null) startedAt = LocalDateTime.now();
        this.modelVersion = modelVersion; this.status = "REVIEW_READY"; this.completedAt = LocalDateTime.now();
    }
    public void finalizeRun() { status = "FINALIZED"; }
    public void fail() { status = "FAILED"; completedAt = LocalDateTime.now(); }
    public void addInputFile(ProjectFile file) { inputFiles.add(file); }
    public void addInputLog(QuickLog log) { inputLogs.add(log); }
    public UUID getId() { return id; }
    public Project getProject() { return project; }
    public String getRunType() { return runType; }
    public String getStatus() { return status; }
    public String getModelVersion() { return modelVersion; }
    public LocalDateTime getStartedAt() { return startedAt; }
    public LocalDateTime getCompletedAt() { return completedAt; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public Set<ProjectFile> getInputFiles() { return inputFiles; }
    public Set<QuickLog> getInputLogs() { return inputLogs; }
}
