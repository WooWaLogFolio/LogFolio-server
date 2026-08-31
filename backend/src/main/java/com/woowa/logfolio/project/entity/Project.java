package com.woowa.logfolio.project.entity;

import com.woowa.logfolio.user.entity.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "projects")
public class Project {

    @Id
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(nullable = false)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ProjectStatus status;

    @Column(name = "activity_type", nullable = false)
    private String activityType;

    @Column(name = "user_role", nullable = false)
    private String userRole;

    @Column(name = "started_at", nullable = false)
    private LocalDate startedAt;

    @Column(name = "ended_at")
    private LocalDate endedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @Column(name = "deleted_at")
    private LocalDateTime deletedAt;

    protected Project() {
    }

    public Project(User user, String name, ProjectStatus status, String activityType,
                   String userRole, LocalDate startedAt, LocalDate endedAt) {
        this.id = UUID.randomUUID();
        this.user = user;
        this.name = name;
        this.status = status;
        this.activityType = activityType;
        this.userRole = userRole;
        this.startedAt = startedAt;
        this.endedAt = endedAt;
    }

    @PrePersist
    void onCreate() {
        LocalDateTime now = LocalDateTime.now();
        createdAt = now;
        updatedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = LocalDateTime.now();
    }

    public void update(String name, ProjectStatus status, String activityType,
                       String userRole, LocalDate startedAt, LocalDate endedAt) {
        this.name = name;
        this.status = status;
        this.activityType = activityType;
        this.userRole = userRole;
        this.startedAt = startedAt;
        this.endedAt = endedAt;
    }

    public void delete() {
        this.deletedAt = LocalDateTime.now();
    }

    public UUID getId() { return id; }
    public User getUser() { return user; }
    public String getName() { return name; }
    public ProjectStatus getStatus() { return status; }
    public String getActivityType() { return activityType; }
    public String getUserRole() { return userRole; }
    public LocalDate getStartedAt() { return startedAt; }
    public LocalDate getEndedAt() { return endedAt; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public LocalDateTime getDeletedAt() { return deletedAt; }
}
