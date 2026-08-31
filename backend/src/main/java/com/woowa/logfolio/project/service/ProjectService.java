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
    public ProjectResponse create(ProjectCreateRequest request) {
        User user = userService.findActiveUser(request.userId());
        Project project = new Project(
                user, request.name(), request.status(), request.activityType(),
                request.userRole(), request.startedAt(), request.endedAt()
        );
        return ProjectResponse.from(projectRepository.save(project));
    }

    public ProjectResponse get(UUID id) {
        return ProjectResponse.from(findActiveProject(id));
    }

    public List<ProjectResponse> getByUser(UUID userId) {
        userService.findActiveUser(userId);
        return projectRepository.findAllByUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(userId)
                .stream().map(ProjectResponse::from).toList();
    }

    @Transactional
    public ProjectResponse update(UUID id, ProjectUpdateRequest request) {
        Project project = findActiveProject(id);
        project.update(
                request.name(), request.status(), request.activityType(), request.userRole(),
                request.startedAt(), request.endedAt()
        );
        return ProjectResponse.from(project);
    }

    @Transactional
    public void delete(UUID id) {
        findActiveProject(id).delete();
    }

    private Project findActiveProject(UUID id) {
        return projectRepository.findByIdAndDeletedAtIsNull(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "프로젝트를 찾을 수 없습니다."));
    }
}
