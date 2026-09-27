package com.woowa.logfolio.analysis.service;

import com.woowa.logfolio.analysis.entity.AnalysisRun;
import com.woowa.logfolio.analysis.entity.ExperienceCandidate;
import com.woowa.logfolio.analysis.repository.AnalysisRunRepository;
import com.woowa.logfolio.analysis.repository.ExperienceCandidateRepository;
import com.woowa.logfolio.experience.entity.Experience;
import com.woowa.logfolio.experience.repository.ExperienceRepository;
import com.woowa.logfolio.file.service.ProjectFileService;
import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.project.service.ProjectService;
import com.woowa.logfolio.quicklog.service.QuickLogService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class AnalysisService {
    private final AnalysisRunRepository runRepository;
    private final ExperienceCandidateRepository candidateRepository;
    private final ExperienceRepository experienceRepository;
    private final ProjectService projectService;
    private final ProjectFileService fileService;
    private final QuickLogService quickLogService;
    private final JdbcTemplate jdbcTemplate;

    @Transactional
    public AnalysisRunResponse start(UUID userId, UUID projectId, List<UUID> fileIds, List<UUID> quickLogIds) {
        Project project = projectService.findOwnedProject(userId, projectId);
        AnalysisRun run = runRepository.save(new AnalysisRun(project, "PROJECT_INITIAL"));
        for (UUID fileId : safe(fileIds)) {
            fileService.findOwned(userId, fileId);
            jdbcTemplate.update("insert into analysis_input_files (analysis_run_id, project_file_id) values (?, ?)",
                    run.getId(), fileId);
        }
        for (UUID logId : safe(quickLogIds)) {
            quickLogService.findOwned(userId, logId);
            jdbcTemplate.update("insert into analysis_input_logs (analysis_run_id, quick_log_id) values (?, ?)",
                    run.getId(), logId);
        }
        return AnalysisRunResponse.from(run);
    }

    public AnalysisRunResponse get(UUID userId, UUID runId) { return AnalysisRunResponse.from(findRun(userId, runId)); }

    public List<CandidateResponse> candidates(UUID userId, UUID runId) {
        findRun(userId, runId);
        return candidateRepository.findAllByAnalysisRunIdOrderByCreatedAt(runId).stream()
                .map(CandidateResponse::from).toList();
    }

    @Transactional
    public CandidateResponse reviewCandidate(UUID userId, UUID candidateId, String title, String summary,
                                             Map<String, Object> draftContent, String status) {
        if (!List.of("PENDING", "INCLUDED", "EXCLUDED").contains(status)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "지원하지 않는 후보 상태입니다.");
        }
        ExperienceCandidate candidate = candidateRepository.findByIdAndAnalysisRunProjectUserId(candidateId, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "경험 후보를 찾을 수 없습니다."));
        candidate.review(title, summary, draftContent, status);
        return CandidateResponse.from(candidate);
    }

    @Transactional
    public List<UUID> finalizeIncluded(UUID userId, UUID runId) {
        AnalysisRun run = findRun(userId, runId);
        List<UUID> created = candidateRepository.findAllByAnalysisRunIdOrderByCreatedAt(runId).stream()
                .filter(candidate -> "INCLUDED".equals(candidate.getStatus()))
                .filter(candidate -> !experienceRepository.existsByCandidateId(candidate.getId()))
                .map(candidate -> experienceRepository.save(new Experience(
                        run.getProject(), candidate, candidate.getTitle(), candidate.getSummary())).getId())
                .toList();
        run.complete();
        return created;
    }

    private AnalysisRun findRun(UUID userId, UUID runId) {
        return runRepository.findByIdAndProjectUserId(runId, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "분석 실행을 찾을 수 없습니다."));
    }
    private <T> List<T> safe(List<T> values) { return values == null ? List.of() : values; }

    public record AnalysisRunResponse(UUID id, UUID projectId, String runType, String status,
                                      String modelVersion, LocalDateTime startedAt,
                                      LocalDateTime completedAt, LocalDateTime createdAt) {
        static AnalysisRunResponse from(AnalysisRun run) {
            return new AnalysisRunResponse(run.getId(), run.getProject().getId(), run.getRunType(), run.getStatus(),
                    run.getModelVersion(), run.getStartedAt(), run.getCompletedAt(), run.getCreatedAt());
        }
    }
    public record CandidateResponse(UUID id, String title, String summary, Map<String, Object> draftContent,
                                    String status, LocalDateTime createdAt) {
        static CandidateResponse from(ExperienceCandidate candidate) {
            return new CandidateResponse(candidate.getId(), candidate.getTitle(), candidate.getSummary(),
                    candidate.getDraftContent(), candidate.getStatus(), candidate.getCreatedAt());
        }
    }
}
