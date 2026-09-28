package com.woowa.logfolio.project.entity;

import com.woowa.logfolio.user.entity.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.CollectionTable;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import jakarta.persistence.OrderColumn;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.UUID;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "projects")
public class Project {

    @Id
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(nullable = false, length = 200)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private ProjectStatus status;

    @Column(name = "activity_type", length = 100)
    private String activityType;

    @Column(name = "user_role", length = 200)
    private String userRole;

    @Column(name = "team_size")
    private Integer teamSize;

    @ElementCollection
    @CollectionTable(name = "project_tags", joinColumns = @JoinColumn(name = "project_id"))
    @OrderColumn(name = "display_order")
    @Column(name = "tag", nullable = false, length = 50)
    private List<String> tags = new ArrayList<>();

    @Column(name = "started_at")
    private LocalDate startedAt;

    @Column(name = "ended_at")
    private LocalDate endedAt;

    @Column(length = 200)
    private String description;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @Column(name = "deleted_at")
    private LocalDateTime deletedAt;

    protected Project() {
    }

    public Project(User user, String name, ProjectStatus status, String activityType,
                   String userRole, Integer teamSize, List<String> tags,
                   LocalDate startedAt, LocalDate endedAt, String description) {
        this.id = UUID.randomUUID();
        this.user = user;
        this.name = name;
        this.status = status;
        this.activityType = activityType;
        this.userRole = userRole;
        this.teamSize = teamSize;
        if (tags != null) this.tags = new ArrayList<>(tags);
        this.startedAt = startedAt;
        this.endedAt = endedAt;
        this.description = description;
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
                       String userRole, Integer teamSize, List<String> tags,
                       LocalDate startedAt, LocalDate endedAt, String description) {
        this.name = name;
        this.status = status;
        this.activityType = activityType;
        this.userRole = userRole;
        this.teamSize = teamSize;
        this.tags.clear();
        if (tags != null) this.tags.addAll(tags);
        this.startedAt = startedAt;
        this.endedAt = endedAt;
        this.description = description;
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
    public Integer getTeamSize() { return teamSize; }
    public List<String> getTags() { return List.copyOf(tags); }
    public LocalDate getStartedAt() { return startedAt; }
    public LocalDate getEndedAt() { return endedAt; }
    public String getDescription() { return description; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public LocalDateTime getDeletedAt() { return deletedAt; }
}
