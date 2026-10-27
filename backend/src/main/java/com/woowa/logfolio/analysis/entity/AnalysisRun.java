package com.woowa.logfolio.analysis.entity;

import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.quicklog.entity.QuickLog;
import jakarta.persistence.*;

import java.time.LocalDateTime;
import java.util.UUID;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.List;
import java.util.Map;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

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
    @Column(name = "ai_summary", columnDefinition = "text") private String aiSummary;
    @Column(name = "information_need", length = 40) private String informationNeed;
    @Column(name = "information_need_reason", columnDefinition = "text") private String informationNeedReason;
    @Column(name = "no_update_reason", columnDefinition = "text") private String noUpdateReason;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "input_source_ids", columnDefinition = "jsonb") private List<String> inputSourceIds;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "referenced_source_ids", columnDefinition = "jsonb") private List<String> referencedSourceIds;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "source_warnings", columnDefinition = "jsonb") private List<Map<String, Object>> sourceWarnings;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "ai_questions", columnDefinition = "jsonb") private List<Map<String, Object>> aiQuestions;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "ai_usage", columnDefinition = "jsonb") private Map<String, Object> aiUsage;
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
    public void recordAiResponse(String summary, String informationNeed, String informationNeedReason,
                                 String noUpdateReason, List<String> inputSourceIds,
                                 List<String> referencedSourceIds, List<Map<String, Object>> sourceWarnings,
                                 List<Map<String, Object>> aiQuestions, Map<String, Object> aiUsage) {
        this.aiSummary = summary; this.informationNeed = informationNeed;
        this.informationNeedReason = informationNeedReason; this.noUpdateReason = noUpdateReason;
        this.inputSourceIds = inputSourceIds; this.referencedSourceIds = referencedSourceIds;
        this.sourceWarnings = sourceWarnings; this.aiQuestions = aiQuestions; this.aiUsage = aiUsage;
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
    public String getAiSummary() { return aiSummary; }
    public String getInformationNeed() { return informationNeed; }
    public String getInformationNeedReason() { return informationNeedReason; }
    public String getNoUpdateReason() { return noUpdateReason; }
    public List<String> getInputSourceIds() { return inputSourceIds; }
    public List<String> getReferencedSourceIds() { return referencedSourceIds; }
    public List<Map<String, Object>> getSourceWarnings() { return sourceWarnings; }
    public List<Map<String, Object>> getAiQuestions() { return aiQuestions; }
    public Map<String, Object> getAiUsage() { return aiUsage; }
    public Set<ProjectFile> getInputFiles() { return inputFiles; }
    public Set<QuickLog> getInputLogs() { return inputLogs; }
}
