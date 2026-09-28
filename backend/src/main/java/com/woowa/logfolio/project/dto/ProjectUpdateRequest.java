package com.woowa.logfolio.project.dto;

import com.woowa.logfolio.project.entity.ProjectStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.LocalDate;
import java.util.List;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

@Schema(description = "프로젝트 전체 수정 요청")
public record ProjectUpdateRequest(
        @NotBlank @Size(max = 200) String name,
        @NotNull ProjectStatus status,
        @Size(max = 100) String activityType,
        @Size(max = 200) String userRole,
        @Min(1) @Max(999) Integer teamSize,
        @Size(max = 10) List<@Size(max = 50) String> tags,
        LocalDate startedAt,
        LocalDate endedAt,
        @Size(max = 200) String description
) {
}
