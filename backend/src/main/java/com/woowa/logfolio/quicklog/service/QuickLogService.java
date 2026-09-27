package com.woowa.logfolio.quicklog.service;

import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.project.service.ProjectService;
import com.woowa.logfolio.quicklog.entity.QuickLog;
import com.woowa.logfolio.quicklog.repository.QuickLogRepository;
import com.woowa.logfolio.user.entity.User;
import com.woowa.logfolio.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class QuickLogService {
    private final QuickLogRepository repository;
    private final UserService userService;
    private final ProjectService projectService;

    @Transactional
    public QuickLogResponse create(UUID userId, String content, UUID projectId) {
        User user = userService.findActiveUser(userId);
        Project project = projectId == null ? null : projectService.findOwnedProject(userId, projectId);
        return QuickLogResponse.from(repository.save(new QuickLog(user, project, content.trim())));
    }

    public QuickLogPage list(UUID userId, UUID projectId, int page, int size) {
        userService.findActiveUser(userId);
        var pageable = PageRequest.of(page, Math.min(size, 100), Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<QuickLog> result = projectId == null
                ? repository.findAllByUserIdAndDeletedAtIsNull(userId, pageable)
                : repository.findAllByUserIdAndProjectIdAndDeletedAtIsNull(userId, projectId, pageable);
        return new QuickLogPage(result.getContent().stream().map(QuickLogResponse::from).toList(),
                result.getTotalElements(), result.getNumber(), result.getSize(), result.hasNext());
    }

    @Transactional
    public QuickLogResponse updateContent(UUID userId, UUID id, String content) {
        QuickLog log = findOwned(userId, id);
        log.updateContent(content.trim());
        return QuickLogResponse.from(log);
    }

    @Transactional
    public QuickLogResponse linkProject(UUID userId, UUID id, UUID projectId) {
        QuickLog log = findOwned(userId, id);
        Project project = projectId == null ? null : projectService.findOwnedProject(userId, projectId);
        log.linkProject(project);
        return QuickLogResponse.from(log);
    }

    @Transactional
    public void delete(UUID userId, UUID id) { findOwned(userId, id).delete(); }

    public QuickLog findOwned(UUID userId, UUID id) {
        return repository.findByIdAndUserIdAndDeletedAtIsNull(id, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "30초 기록을 찾을 수 없습니다."));
    }

    public record QuickLogResponse(UUID id, UUID projectId, String projectName, String content,
                                   LocalDateTime createdAt, LocalDateTime updatedAt) {
        static QuickLogResponse from(QuickLog log) {
            return new QuickLogResponse(log.getId(), log.getProject() == null ? null : log.getProject().getId(),
                    log.getProject() == null ? null : log.getProject().getName(), log.getContent(),
                    log.getCreatedAt(), log.getUpdatedAt());
        }
    }

    public record QuickLogPage(List<QuickLogResponse> items, long totalElements,
                               int page, int size, boolean hasNext) {}
}
