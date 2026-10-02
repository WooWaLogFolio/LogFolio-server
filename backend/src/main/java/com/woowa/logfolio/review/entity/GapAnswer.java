package com.woowa.logfolio.review.entity;

import com.woowa.logfolio.user.entity.User;
import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "gap_answers")
public class GapAnswer {
    @Id private UUID id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "question_id", nullable = false) private GapQuestion question;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false) private User user;
    @Column(columnDefinition = "text") private String answer;
    @Column(name = "answer_type", nullable = false, length = 30) private String answerType;
    @Column(name = "created_at", nullable = false, updatable = false) private LocalDateTime createdAt;
    protected GapAnswer() {}
    public GapAnswer(GapQuestion question, User user, String answer, String answerType) {
        id = UUID.randomUUID(); this.question = question; this.user = user; this.answer = answer; this.answerType = answerType;
    }
    @PrePersist void onCreate() { createdAt = LocalDateTime.now(); }
    public UUID getId() { return id; }
    public String getAnswer() { return answer; }
    public String getAnswerType() { return answerType; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
