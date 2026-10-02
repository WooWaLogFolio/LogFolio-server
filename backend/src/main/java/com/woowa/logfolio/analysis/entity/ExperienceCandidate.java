package com.woowa.logfolio.analysis.entity;

import com.woowa.logfolio.experience.entity.Experience;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "experience_candidates")
public class ExperienceCandidate {
    @Id private UUID id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "analysis_run_id", nullable = false)
    private AnalysisRun analysisRun;
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "merged_into_id")
    private ExperienceCandidate mergedInto;
    @Column(name = "candidate_type", nullable = false, length = 30)
    private String candidateType;
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "target_experience_id")
    private Experience targetExperience;
    @Column(name = "match_confidence", precision = 5, scale = 4)
    private BigDecimal matchConfidence;
    @Column(name = "match_reason", columnDefinition = "text")
    private String matchReason;
    @Column(nullable = false) private String title;
    @Column(columnDefinition = "text") private String summary;
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "draft_content", columnDefinition = "jsonb")
    private Map<String, Object> draftContent = new LinkedHashMap<>();
    @Column(nullable = false, length = 30) private String status;
    @Column(name = "created_at", nullable = false, updatable = false) private LocalDateTime createdAt;

    protected ExperienceCandidate() {}
    public ExperienceCandidate(AnalysisRun run, String candidateType, Experience targetExperience,
                               BigDecimal matchConfidence, String matchReason, String title, String summary,
                               Map<String, Object> draftContent) {
        this.id = UUID.randomUUID(); this.analysisRun = run; this.title = title; this.summary = summary;
        this.candidateType = candidateType; this.targetExperience = targetExperience;
        this.matchConfidence = matchConfidence; this.matchReason = matchReason;
        if (draftContent != null) this.draftContent = new LinkedHashMap<>(draftContent);
        this.status = "PENDING";
    }
    @PrePersist void onCreate() { createdAt = LocalDateTime.now(); }
    public void review(String title, String summary, Map<String, Object> draftContent, String status) {
        if (title != null && !title.isBlank()) this.title = title;
        this.summary = summary;
        if (draftContent != null) this.draftContent = new LinkedHashMap<>(draftContent);
        this.status = status;
    }
    public void decide(String title, String summary, Map<String, Object> draftContent,
                       String decision, Experience targetExperience) {
        review(title, summary, draftContent, decision);
        this.targetExperience = targetExperience;
    }
    public void finalized() { this.status = "FINALIZED"; }
    public UUID getId() { return id; }
    public AnalysisRun getAnalysisRun() { return analysisRun; }
    public String getCandidateType() { return candidateType; }
    public Experience getTargetExperience() { return targetExperience; }
    public BigDecimal getMatchConfidence() { return matchConfidence; }
    public String getMatchReason() { return matchReason; }
    public String getTitle() { return title; }
    public String getSummary() { return summary; }
    public Map<String, Object> getDraftContent() { return draftContent; }
    public String getStatus() { return status; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
