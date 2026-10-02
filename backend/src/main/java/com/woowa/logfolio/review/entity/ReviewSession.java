package com.woowa.logfolio.review.entity;

import com.woowa.logfolio.analysis.entity.AnalysisRun;
import com.woowa.logfolio.project.entity.Project;
import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "review_sessions")
public class ReviewSession {
    @Id private UUID id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "project_id", nullable = false) private Project project;
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "analysis_run_id") private AnalysisRun analysisRun;
    @Column(nullable = false, length = 30) private String status;
    @Column(name = "started_at", nullable = false) private LocalDateTime startedAt;
    @Column(name = "completed_at") private LocalDateTime completedAt;
    protected ReviewSession() {}
    public ReviewSession(Project project, AnalysisRun run) {
        id = UUID.randomUUID(); this.project = project; analysisRun = run; status = "IN_PROGRESS"; startedAt = LocalDateTime.now();
    }
    public void complete() { status = "COMPLETED"; completedAt = LocalDateTime.now(); }
    public UUID getId() { return id; }
    public Project getProject() { return project; }
    public String getStatus() { return status; }
    public LocalDateTime getStartedAt() { return startedAt; }
    public LocalDateTime getCompletedAt() { return completedAt; }
}
