package com.woowa.logfolio.experience.entity;

import com.woowa.logfolio.analysis.entity.ExperienceCandidate;
import com.woowa.logfolio.project.entity.Project;
import jakarta.persistence.*;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "experiences")
public class Experience {
    @Id private UUID id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "project_id", nullable = false) private Project project;
    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "candidate_id") private ExperienceCandidate candidate;
    @Column(nullable = false) private String title;
    @Column(columnDefinition = "text") private String summary;
    @Column(columnDefinition = "text") private String context;
    @Column(columnDefinition = "text") private String contribution;
    @Column(name = "decision_reason", columnDefinition = "text") private String decisionReason;
    @Column(columnDefinition = "text") private String action;
    @Column(columnDefinition = "text") private String result;
    @Column(columnDefinition = "text") private String learning;
    @Column(nullable = false, length = 30) private String status;
    @Column(nullable = false) private int version;
    @Column(name = "created_at", nullable = false, updatable = false) private LocalDateTime createdAt;
    @Column(name = "updated_at", nullable = false) private LocalDateTime updatedAt;
    @Column(name = "deleted_at") private LocalDateTime deletedAt;

    protected Experience() {}
    public Experience(Project project, ExperienceCandidate candidate, String title, String summary) {
        this.id = UUID.randomUUID(); this.project = project; this.candidate = candidate;
        this.title = title; this.summary = summary; this.status = "REVIEW_REQUIRED"; this.version = 1;
        if (candidate != null) applyDraft(candidate.getDraftContent());
    }
    @PrePersist void onCreate() { createdAt = LocalDateTime.now(); updatedAt = createdAt; }
    @PreUpdate void onUpdate() { updatedAt = LocalDateTime.now(); }
    public void update(String title, String summary, String context, String contribution,
                       String decisionReason, String action, String result, String learning, String status) {
        this.title = title; this.summary = summary; this.context = context; this.contribution = contribution;
        this.decisionReason = decisionReason; this.action = action; this.result = result; this.learning = learning;
        this.status = status; this.version++;
    }
    public void initializeDetails(String context, String contribution, String decisionReason,
                                  String action, String result, String learning, String status) {
        this.context = context; this.contribution = contribution; this.decisionReason = decisionReason;
        this.action = action; this.result = result; this.learning = learning; this.status = status;
    }
    private void applyDraft(Map<String, Object> draft) {
        if (draft == null) return;
        this.context = text(draft.get("context")); this.contribution = text(draft.get("contribution"));
        this.decisionReason = text(draft.get("decisionReason")); this.action = text(draft.get("action"));
        this.result = text(draft.get("result")); this.learning = text(draft.get("learning"));
    }
    private String text(Object value) { return value == null ? null : String.valueOf(value); }
    public void delete() { deletedAt = LocalDateTime.now(); }
    public UUID getId() { return id; }
    public Project getProject() { return project; }
    public ExperienceCandidate getCandidate() { return candidate; }
    public String getTitle() { return title; }
    public String getSummary() { return summary; }
    public String getContext() { return context; }
    public String getContribution() { return contribution; }
    public String getDecisionReason() { return decisionReason; }
    public String getAction() { return action; }
    public String getResult() { return result; }
    public String getLearning() { return learning; }
    public String getStatus() { return status; }
    public int getVersion() { return version; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
}
