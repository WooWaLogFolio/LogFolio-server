package com.woowa.logfolio.review.entity;

import com.woowa.logfolio.experience.entity.Experience;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "gap_questions")
public class GapQuestion {
    @Id private UUID id;
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "review_item_id") private ReviewItem reviewItem;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "experience_id", nullable = false) private Experience experience;
    @Column(name = "target_section", nullable = false, length = 30) private String targetSection;
    @Column(nullable = false, columnDefinition = "text") private String question;
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "suggested_answers", columnDefinition = "jsonb") private List<String> suggestedAnswers = new ArrayList<>();
    @Column(name = "display_order", nullable = false) private int displayOrder;
    @Column(name = "created_at", nullable = false, updatable = false) private LocalDateTime createdAt;
    protected GapQuestion() {}
    @PrePersist void onCreate() { createdAt = LocalDateTime.now(); }
    public UUID getId() { return id; }
    public Experience getExperience() { return experience; }
    public String getTargetSection() { return targetSection; }
    public String getQuestion() { return question; }
    public List<String> getSuggestedAnswers() { return suggestedAnswers; }
    public int getDisplayOrder() { return displayOrder; }
}
