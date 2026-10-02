package com.woowa.logfolio.project.dto;

import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.project.entity.ProjectStatus;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.UUID;
import java.util.List;

@Schema(description = "프로젝트")
public record ProjectResponse(
        UUID id,
        UUID userId,
        String name,
        ProjectStatus status,
        String activityType,
        String userRole,
        Integer teamSize,
        List<String> tags,
        LocalDate startedAt,
        LocalDate endedAt,
        String description,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
    public static ProjectResponse from(Project project) {
        return new ProjectResponse(
                project.getId(), project.getUser().getId(), project.getName(), project.getStatus(),
                project.getActivityType(), project.getUserRole(), project.getTeamSize(), project.getTags(),
                project.getStartedAt(), project.getEndedAt(),
                project.getDescription(), project.getCreatedAt(), project.getUpdatedAt()
        );
    }
}
