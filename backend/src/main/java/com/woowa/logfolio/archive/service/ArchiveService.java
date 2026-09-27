package com.woowa.logfolio.archive.service;

import com.woowa.logfolio.experience.repository.ExperienceRepository;
import com.woowa.logfolio.project.dto.ProjectResponse;
import com.woowa.logfolio.project.repository.ProjectRepository;
import com.woowa.logfolio.quicklog.repository.QuickLogRepository;
import com.woowa.logfolio.quicklog.service.QuickLogService;
import com.woowa.logfolio.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ArchiveService {
    private final UserService userService;
    private final ProjectRepository projectRepository;
    private final ExperienceRepository experienceRepository;
    private final QuickLogRepository quickLogRepository;
    private final QuickLogService quickLogService;

    public ArchiveResponse get(UUID userId) {
        userService.findActiveUser(userId);
        List<ProjectCardResponse> projects = projectRepository
                .findAllByUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(userId).stream()
                .map(project -> new ProjectCardResponse(ProjectResponse.from(project),
                        experienceRepository.countByProjectIdAndDeletedAtIsNull(project.getId())))
                .toList();
        long experienceCount = experienceRepository.countByProjectUserIdAndDeletedAtIsNull(userId);
        long quickLogCount = quickLogRepository.countByUserIdAndDeletedAtIsNull(userId);
        return new ArchiveResponse(projects.size(), experienceCount, quickLogCount, projects,
                quickLogService.list(userId, null, 0, 3).items());
    }

    public record ProjectCardResponse(ProjectResponse project, long experienceCount) {}
    public record ArchiveResponse(int projectCount, long experienceCount, long quickLogCount,
                                  List<ProjectCardResponse> projects,
                                  List<QuickLogService.QuickLogResponse> recentQuickLogs) {}
}
