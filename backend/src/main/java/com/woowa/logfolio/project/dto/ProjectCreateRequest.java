package com.woowa.logfolio.project.dto;

import com.woowa.logfolio.project.entity.ProjectStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.LocalDate;
import java.util.UUID;

public record ProjectCreateRequest(
        @NotNull UUID userId,
        @NotBlank String name,
        @NotNull ProjectStatus status,
        @NotBlank String activityType,
        @NotBlank String userRole,
        @NotNull LocalDate startedAt,
        LocalDate endedAt
) {
}
