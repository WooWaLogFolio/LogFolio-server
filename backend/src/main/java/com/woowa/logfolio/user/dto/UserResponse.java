package com.woowa.logfolio.user.dto;

import com.woowa.logfolio.user.entity.User;
import com.woowa.logfolio.user.entity.UserStatus;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.LocalDateTime;
import java.util.UUID;

@Schema(description = "사용자 프로필")
public record UserResponse(
        UUID id,
        String email,
        String name,
        UserStatus status,
        LocalDateTime onboardingCompletedAt,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
    public static UserResponse from(User user) {
        return new UserResponse(
                user.getId(), user.getEmail(), user.getName(), user.getStatus(),
                user.getOnboardingCompletedAt(), user.getCreatedAt(), user.getUpdatedAt()
        );
    }
}
