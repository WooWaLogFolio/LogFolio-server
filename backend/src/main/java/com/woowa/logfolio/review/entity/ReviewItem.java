package com.woowa.logfolio.review.entity;

import com.woowa.logfolio.analysis.entity.ExperienceCandidate;
import com.woowa.logfolio.experience.entity.Experience;
import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "review_items")
public class ReviewItem {
    @Id private UUID id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "review_session_id", nullable = false) private ReviewSession reviewSession;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "experience_id") private Experience experience;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "candidate_id") private ExperienceCandidate candidate;
    @Column(name = "item_type", nullable = false, length = 40) private String itemType;
    @Column(name = "proposed_content", columnDefinition = "text") private String proposedContent;
    @Column(name = "confirmed_content", columnDefinition = "text") private String confirmedContent;
    @Column(nullable = false, length = 30) private String decision;
    @Column(name = "display_order", nullable = false) private int displayOrder;
    @Column(name = "reviewed_at") private LocalDateTime reviewedAt;
    protected ReviewItem() {}
    public void decide(String decision, String confirmedContent) { this.decision = decision; this.confirmedContent = confirmedContent; reviewedAt = LocalDateTime.now(); }
    public UUID getId() { return id; }
    public ReviewSession getReviewSession() { return reviewSession; }
    public String getItemType() { return itemType; }
    public String getProposedContent() { return proposedContent; }
    public String getConfirmedContent() { return confirmedContent; }
    public String getDecision() { return decision; }
    public int getDisplayOrder() { return displayOrder; }
}
