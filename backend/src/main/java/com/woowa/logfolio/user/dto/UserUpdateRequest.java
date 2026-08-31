package com.woowa.logfolio.user.dto;

import com.woowa.logfolio.user.entity.UserStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.LocalDateTime;

public record UserUpdateRequest(
        @NotBlank String name,
        @NotNull UserStatus status,
        LocalDateTime onboardingCompletedAt
) {
}
