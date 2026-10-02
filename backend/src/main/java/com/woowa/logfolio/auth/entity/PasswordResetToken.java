package com.woowa.logfolio.auth.entity;

import com.woowa.logfolio.user.entity.User;
import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "password_reset_tokens")
public class PasswordResetToken {
    @Id private UUID id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false) private User user;
    @Column(name = "token_hash", nullable = false, unique = true) private String tokenHash;
    @Column(name = "expires_at", nullable = false) private LocalDateTime expiresAt;
    @Column(name = "used_at") private LocalDateTime usedAt;
    @Column(name = "created_at", nullable = false, updatable = false) private LocalDateTime createdAt;
    protected PasswordResetToken() {}
    public PasswordResetToken(User user, String tokenHash, LocalDateTime expiresAt) {
        id = UUID.randomUUID(); this.user = user; this.tokenHash = tokenHash; this.expiresAt = expiresAt;
    }
    @PrePersist void onCreate() { createdAt = LocalDateTime.now(); }
    public boolean usable(LocalDateTime now) { return usedAt == null && expiresAt.isAfter(now); }
    public void use() { usedAt = LocalDateTime.now(); }
    public User getUser() { return user; }
}
