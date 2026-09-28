package com.woowa.logfolio.auth.entity;

import com.woowa.logfolio.user.entity.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "auth_accounts", uniqueConstraints = {
        @UniqueConstraint(name = "uk_auth_accounts_provider_user", columnNames = {"provider", "provider_user_id"})
})
public class OAuthAccount {

    @Id
    @GeneratedValue
    private UUID id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private OAuthProvider provider;

    @Column(name = "provider_user_id", nullable = false)
    private String providerUserId;

    @Column(name = "provider_email")
    private String providerEmail;

    @Column(name = "password_hash")
    private String passwordHash;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    protected OAuthAccount() {
    }

    public OAuthAccount(OAuthProvider provider, String providerUserId, User user) {
        this(provider, providerUserId, null, null, user);
    }

    public OAuthAccount(OAuthProvider provider, String providerUserId, String providerEmail,
                        String passwordHash, User user) {
        this.provider = provider;
        this.providerUserId = providerUserId;
        this.providerEmail = providerEmail;
        this.passwordHash = passwordHash;
        this.user = user;
    }

    @PrePersist
    void onCreate() {
        createdAt = LocalDateTime.now();
    }

    public User getUser() {
        return user;
    }

    public OAuthProvider getProvider() { return provider; }
    public String getProviderUserId() { return providerUserId; }
    public String getProviderEmail() { return providerEmail; }
    public String getPasswordHash() { return passwordHash; }
    public LocalDateTime getCreatedAt() { return createdAt; }

    public void changePassword(String passwordHash) {
        this.passwordHash = passwordHash;
    }
}
