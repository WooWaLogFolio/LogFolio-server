package com.woowa.logfolio.project.service;

import com.woowa.logfolio.project.dto.ProjectCreateRequest;
import com.woowa.logfolio.project.dto.ProjectResponse;
import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.project.entity.ProjectStatus;
import com.woowa.logfolio.project.repository.ProjectRepository;
import com.woowa.logfolio.user.entity.User;
import com.woowa.logfolio.user.service.UserService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDate;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ProjectServiceTest {

    @Mock
    private ProjectRepository projectRepository;

    @Mock
    private UserService userService;

    @InjectMocks
    private ProjectService projectService;

    @Test
    void createsProjectForAuthenticatedUser() {
        UUID userId = UUID.randomUUID();
        User user = new User("user@example.com", "사용자");
        ProjectCreateRequest request = new ProjectCreateRequest(
                "로그폴리오", ProjectStatus.IN_PROGRESS, "팀 프로젝트", "백엔드",
                4, java.util.List.of("API", "협업"),
                LocalDate.of(2026, 9, 1), null, "개발 경험 정리 서비스");

        when(userService.findActiveUser(userId)).thenReturn(user);
        when(projectRepository.save(any(Project.class))).thenAnswer(invocation -> invocation.getArgument(0));

        ProjectResponse response = projectService.create(userId, request);

        assertThat(response.userId()).isEqualTo(user.getId());
        assertThat(response.description()).isEqualTo("개발 경험 정리 서비스");
        verify(userService).findActiveUser(userId);
    }

    @Test
    void scopesProjectLookupToAuthenticatedUser() {
        UUID userId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        when(projectRepository.findByIdAndUserIdAndDeletedAtIsNull(projectId, userId))
                .thenReturn(Optional.empty());

        assertThatThrownBy(() -> projectService.get(userId, projectId))
                .isInstanceOfSatisfying(ResponseStatusException.class,
                        exception -> assertThat(exception.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND));

        verify(projectRepository).findByIdAndUserIdAndDeletedAtIsNull(projectId, userId);
    }

    @Test
    void rejectsEndDateBeforeStartDate() {
        UUID userId = UUID.randomUUID();
        ProjectCreateRequest request = new ProjectCreateRequest(
                "로그폴리오", ProjectStatus.IN_PROGRESS, null, null,
                null, java.util.List.of(),
                LocalDate.of(2026, 9, 2), LocalDate.of(2026, 9, 1), null);

        assertThatThrownBy(() -> projectService.create(userId, request))
                .isInstanceOfSatisfying(ResponseStatusException.class,
                        exception -> assertThat(exception.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST));
    }
}
