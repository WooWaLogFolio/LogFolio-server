package com.woowa.logfolio.project.dto;

import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.project.entity.ProjectStatus;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.UUID;

public record ProjectResponse(
        UUID id,
        UUID userId,
        String name,
        ProjectStatus status,
        String activityType,
        String userRole,
        LocalDate startedAt,
        LocalDate endedAt,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
    public static ProjectResponse from(Project project) {
        return new ProjectResponse(
                project.getId(), project.getUser().getId(), project.getName(), project.getStatus(),
                project.getActivityType(), project.getUserRole(), project.getStartedAt(), project.getEndedAt(),
                project.getCreatedAt(), project.getUpdatedAt()
        );
    }
}
