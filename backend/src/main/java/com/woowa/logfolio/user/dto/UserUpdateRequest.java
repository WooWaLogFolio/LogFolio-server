package com.woowa.logfolio.user.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.LocalDateTime;

@Schema(description = "내 프로필 수정 요청")
public record UserUpdateRequest(
        @Schema(example = "홍길동") @NotBlank @Size(max = 100) String name,
        @Schema(description = "온보딩 완료 시각", example = "2026-09-26T10:30:00")
        LocalDateTime onboardingCompletedAt
) {
}
