package com.woowa.logfolio.project.service;

import com.woowa.logfolio.project.dto.ProjectCreateRequest;
import com.woowa.logfolio.project.dto.ProjectResponse;
import com.woowa.logfolio.project.dto.ProjectUpdateRequest;
import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.project.repository.ProjectRepository;
import com.woowa.logfolio.user.entity.User;
import com.woowa.logfolio.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProjectService {

    private final ProjectRepository projectRepository;
    private final UserService userService;

    @Transactional
    public ProjectResponse create(UUID userId, ProjectCreateRequest request) {
        validateDates(request.startedAt(), request.endedAt());
        User user = userService.findActiveUser(userId);
        Project project = new Project(
                user, request.name(), request.status(), request.activityType(),
                request.userRole(), request.teamSize(), request.tags(),
                request.startedAt(), request.endedAt(), request.description()
        );
        return ProjectResponse.from(projectRepository.save(project));
    }

    public ProjectResponse get(UUID userId, UUID id) {
        return ProjectResponse.from(findOwnedProject(userId, id));
    }

    public List<ProjectResponse> getByUser(UUID userId) {
        userService.findActiveUser(userId);
        return projectRepository.findAllByUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(userId)
                .stream().map(ProjectResponse::from).toList();
    }

    @Transactional
    public ProjectResponse update(UUID userId, UUID id, ProjectUpdateRequest request) {
        validateDates(request.startedAt(), request.endedAt());
        Project project = findOwnedProject(userId, id);
        project.update(
                request.name(), request.status(), request.activityType(), request.userRole(),
                request.teamSize(), request.tags(), request.startedAt(), request.endedAt(), request.description()
        );
        return ProjectResponse.from(project);
    }

    @Transactional
    public void delete(UUID userId, UUID id) {
        findOwnedProject(userId, id).delete();
    }

    public Project findOwnedProject(UUID userId, UUID id) {
        return projectRepository.findByIdAndUserIdAndDeletedAtIsNull(id, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "프로젝트를 찾을 수 없습니다."));
    }

    private void validateDates(java.time.LocalDate startedAt, java.time.LocalDate endedAt) {
        if (startedAt != null && endedAt != null && endedAt.isBefore(startedAt)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "종료일은 시작일보다 빠를 수 없습니다.");
        }
    }
}
