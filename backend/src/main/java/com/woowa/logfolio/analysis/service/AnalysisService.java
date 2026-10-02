package com.woowa.logfolio.analysis.service;

import com.woowa.logfolio.analysis.entity.AnalysisRun;
import com.woowa.logfolio.analysis.entity.ExperienceCandidate;
import com.woowa.logfolio.analysis.repository.AnalysisRunRepository;
import com.woowa.logfolio.analysis.repository.ExperienceCandidateRepository;
import com.woowa.logfolio.experience.entity.Experience;
import com.woowa.logfolio.experience.repository.ExperienceRepository;
import com.woowa.logfolio.file.entity.ProjectFile;
import com.woowa.logfolio.file.service.ProjectFileService;
import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.project.service.ProjectService;
import com.woowa.logfolio.quicklog.entity.QuickLog;
import com.woowa.logfolio.quicklog.service.QuickLogService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class AnalysisService {
    private static final List<String> RUN_TYPES = List.of("PROJECT_INITIAL", "PROJECT_INCREMENTAL");
    private static final List<String> CANDIDATE_TYPES = List.of("NEW", "ENHANCE_EXISTING");
    private static final List<String> DECISIONS = List.of("PENDING", "CREATE_NEW", "MERGE_EXISTING", "EXCLUDED");

    private final AnalysisRunRepository runRepository;
    private final ExperienceCandidateRepository candidateRepository;
    private final ExperienceRepository experienceRepository;
    private final ProjectService projectService;
    private final ProjectFileService fileService;
    private final QuickLogService quickLogService;
    private final JdbcTemplate jdbcTemplate;

    @Transactional
    public AnalysisRunResponse start(UUID userId, UUID projectId, String requestedRunType,
                                     List<UUID> fileIds, List<UUID> quickLogIds) {
        Project project = projectService.findOwnedProject(userId, projectId);
        String runType = requestedRunType == null
                ? (experienceRepository.countByProjectIdAndDeletedAtIsNull(projectId) == 0
                    ? "PROJECT_INITIAL" : "PROJECT_INCREMENTAL") : requestedRunType;
        if (!RUN_TYPES.contains(runType)) throw badRequest("runType은 PROJECT_INITIAL 또는 PROJECT_INCREMENTAL이어야 합니다.");

        AnalysisRun run = runRepository.save(new AnalysisRun(project, runType));
        for (UUID fileId : safe(fileIds)) {
            ProjectFile file = fileService.findOwned(userId, fileId);
            requireSameProject(projectId, file.getProject().getId(), "분석 파일");
            run.addInputFile(file);
        }
        for (UUID logId : safe(quickLogIds)) {
            QuickLog log = quickLogService.findOwned(userId, logId);
            if (log.getProject() == null) throw badRequest("프로젝트에 연결되지 않은 Quick Log는 분석할 수 없습니다.");
            requireSameProject(projectId, log.getProject().getId(), "Quick Log");
            run.addInputLog(log);
        }
        return AnalysisRunResponse.from(run);
    }

    public AnalysisRunResponse get(UUID userId, UUID runId) { return AnalysisRunResponse.from(findRun(userId, runId)); }

    public List<AnalysisRunResponse> list(UUID userId, UUID projectId) {
        projectService.findOwnedProject(userId, projectId);
        return runRepository.findAllByProjectIdAndProjectUserIdOrderByCreatedAtDesc(projectId, userId)
                .stream().map(AnalysisRunResponse::from).toList();
    }

    public List<CandidateResponse> candidates(UUID userId, UUID runId) {
        findRun(userId, runId);
        return candidateRepository.findAllByAnalysisRunIdOrderByCreatedAt(runId).stream().map(CandidateResponse::from).toList();
    }

    @Transactional
    public List<CandidateResponse> saveResults(UUID userId, UUID runId, String modelVersion, List<CandidateInput> inputs) {
        AnalysisRun run = findRun(userId, runId);
        if (!List.of("QUEUED", "PROCESSING").contains(run.getStatus())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 분석 결과가 저장된 실행입니다.");
        }
        List<ExperienceCandidate> candidates = new ArrayList<>();
        for (CandidateInput input : safe(inputs)) {
            validateCandidate(input);
            Experience target = resolveTarget(userId, run, input.targetExperienceId());
            candidates.add(new ExperienceCandidate(run, input.candidateType(), target, input.matchConfidence(),
                    input.matchReason(), input.title(), input.summary(), input.draftContent()));
        }
        List<ExperienceCandidate> saved = candidateRepository.saveAll(candidates);
        run.reviewReady(modelVersion);
        return saved.stream().map(CandidateResponse::from).toList();
    }

    @Transactional
    public AnalysisRunResponse fail(UUID userId, UUID runId) {
        AnalysisRun run = findRun(userId, runId);
        if ("FINALIZED".equals(run.getStatus())) throw new ResponseStatusException(HttpStatus.CONFLICT, "확정된 분석은 실패 처리할 수 없습니다.");
        run.fail();
        return AnalysisRunResponse.from(run);
    }

    @Transactional
    public CandidateResponse decide(UUID userId, UUID candidateId, String title, String summary,
                                    Map<String, Object> draftContent, String decision, UUID targetExperienceId) {
        if (!DECISIONS.contains(decision)) throw badRequest("지원하지 않는 후보 결정입니다.");
        ExperienceCandidate candidate = findCandidate(userId, candidateId);
        if ("FINALIZED".equals(candidate.getStatus())) throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 확정된 후보입니다.");
        UUID resolvedTargetId = targetExperienceId != null ? targetExperienceId
                : candidate.getTargetExperience() == null ? null : candidate.getTargetExperience().getId();
        Experience target = resolveTarget(userId, candidate.getAnalysisRun(), resolvedTargetId);
        if ("MERGE_EXISTING".equals(decision) && target == null) throw badRequest("MERGE_EXISTING 결정에는 targetExperienceId가 필요합니다.");
        candidate.decide(title, summary, draftContent, decision, target);
        return CandidateResponse.from(candidate);
    }

    @Transactional
    public CandidateResponse reviewCandidate(UUID userId, UUID candidateId, String title, String summary,
                                             Map<String, Object> draftContent, String status) {
        ExperienceCandidate candidate = findCandidate(userId, candidateId);
        String decision = switch (status) {
            case "INCLUDED" -> candidate.getTargetExperience() == null ? "CREATE_NEW" : "MERGE_EXISTING";
            case "PENDING", "EXCLUDED" -> status;
            default -> throw badRequest("지원하지 않는 후보 상태입니다.");
        };
        UUID targetId = candidate.getTargetExperience() == null ? null : candidate.getTargetExperience().getId();
        return decide(userId, candidateId, title, summary, draftContent, decision, targetId);
    }

    @Transactional
    public FinalizeResult finalizeDecisions(UUID userId, UUID runId) {
        AnalysisRun run = findRun(userId, runId);
        if (!"REVIEW_READY".equals(run.getStatus())) throw new ResponseStatusException(HttpStatus.CONFLICT, "REVIEW_READY 상태의 분석만 확정할 수 있습니다.");
        List<UUID> created = new ArrayList<>();
        List<UUID> updated = new ArrayList<>();
        for (ExperienceCandidate candidate : candidateRepository.findAllByAnalysisRunIdOrderByCreatedAt(runId)) {
            Experience experience;
            if ("CREATE_NEW".equals(candidate.getStatus())) {
                if (experienceRepository.existsByCandidateId(candidate.getId())) continue;
                experience = experienceRepository.save(new Experience(run.getProject(), candidate, candidate.getTitle(), candidate.getSummary()));
                created.add(experience.getId());
            } else if ("MERGE_EXISTING".equals(candidate.getStatus())) {
                experience = candidate.getTargetExperience();
                if (experience == null || !experience.getProject().getId().equals(run.getProject().getId())) throw badRequest("기존 경험 보강 대상이 올바르지 않습니다.");
                experience.augmentFrom(candidate);
                updated.add(experience.getId());
            } else continue;
            attachRunEvidence(run, experience.getId());
            candidate.finalized();
        }
        run.finalizeRun();
        return new FinalizeResult(created, updated);
    }

    private void attachRunEvidence(AnalysisRun run, UUID experienceId) {
        for (ProjectFile file : run.getInputFiles()) {
            attachEvidence(run.getProject().getId(), experienceId, file.getId(), null);
        }
        for (QuickLog log : run.getInputLogs()) {
            attachEvidence(run.getProject().getId(), experienceId, null, log.getId());
        }
    }

    private void attachEvidence(UUID projectId, UUID experienceId, UUID fileId, UUID logId) {
        String sourceColumn = fileId != null ? "project_file_id" : "quick_log_id";
        UUID sourceId = fileId != null ? fileId : logId;
        Integer count = jdbcTemplate.queryForObject("select count(*) from evidence_items ei " +
                        "join experience_evidence ee on ee.evidence_item_id = ei.id " +
                        "where ee.experience_id = ? and ei." + sourceColumn + " = ?",
                Integer.class, experienceId, sourceId);
        if (count != null && count > 0) return;
        UUID evidenceId = UUID.randomUUID();
        jdbcTemplate.update("insert into evidence_items (id, project_id, project_file_id, quick_log_id, created_at) values (?, ?, ?, ?, ?)",
                evidenceId, projectId, fileId, logId, LocalDateTime.now());
        jdbcTemplate.update("insert into experience_evidence (experience_id, evidence_item_id, section_type) values (?, ?, ?)",
                experienceId, evidenceId, "GENERAL");
    }

    private Experience resolveTarget(UUID userId, AnalysisRun run, UUID targetId) {
        if (targetId == null) return null;
        Experience target = experienceRepository.findByIdAndProjectUserIdAndDeletedAtIsNull(targetId, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "보강 대상 경험을 찾을 수 없습니다."));
        requireSameProject(run.getProject().getId(), target.getProject().getId(), "보강 대상 경험");
        return target;
    }

    private void validateCandidate(CandidateInput input) {
        if (input == null || input.title() == null || input.title().isBlank()) throw badRequest("후보 제목은 필수입니다.");
        if (!CANDIDATE_TYPES.contains(input.candidateType())) throw badRequest("지원하지 않는 candidateType입니다.");
        if (input.matchConfidence() != null && (input.matchConfidence().compareTo(BigDecimal.ZERO) < 0
                || input.matchConfidence().compareTo(BigDecimal.ONE) > 0)) throw badRequest("matchConfidence는 0 이상 1 이하여야 합니다.");
        if ("ENHANCE_EXISTING".equals(input.candidateType()) && input.targetExperienceId() == null) throw badRequest("ENHANCE_EXISTING 후보에는 targetExperienceId가 필요합니다.");
    }

    private ExperienceCandidate findCandidate(UUID userId, UUID candidateId) {
        return candidateRepository.findByIdAndAnalysisRunProjectUserId(candidateId, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "경험 후보를 찾을 수 없습니다."));
    }
    private AnalysisRun findRun(UUID userId, UUID runId) {
        return runRepository.findByIdAndProjectUserId(runId, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "분석 실행을 찾을 수 없습니다."));
    }
    private void requireSameProject(UUID expected, UUID actual, String target) {
        if (!expected.equals(actual)) throw badRequest(target + "이(가) 분석 프로젝트에 속하지 않습니다.");
    }
    private ResponseStatusException badRequest(String message) { return new ResponseStatusException(HttpStatus.BAD_REQUEST, message); }
    private <T> List<T> safe(List<T> values) { return values == null ? List.of() : values; }

    public record CandidateInput(String candidateType, UUID targetExperienceId, BigDecimal matchConfidence,
                                 String matchReason, String title, String summary, Map<String, Object> draftContent) {}
    public record FinalizeResult(List<UUID> createdExperienceIds, List<UUID> updatedExperienceIds) {}
    public record AnalysisRunResponse(UUID id, UUID projectId, String runType, String status, String modelVersion,
                                      LocalDateTime startedAt, LocalDateTime completedAt, LocalDateTime createdAt) {
        static AnalysisRunResponse from(AnalysisRun run) {
            return new AnalysisRunResponse(run.getId(), run.getProject().getId(), run.getRunType(), run.getStatus(),
                    run.getModelVersion(), run.getStartedAt(), run.getCompletedAt(), run.getCreatedAt());
        }
    }
    public record CandidateResponse(UUID id, String candidateType, UUID targetExperienceId,
                                    BigDecimal matchConfidence, String matchReason, String title, String summary,
                                    Map<String, Object> draftContent, String status, LocalDateTime createdAt) {
        static CandidateResponse from(ExperienceCandidate candidate) {
            return new CandidateResponse(candidate.getId(), candidate.getCandidateType(),
                    candidate.getTargetExperience() == null ? null : candidate.getTargetExperience().getId(),
                    candidate.getMatchConfidence(), candidate.getMatchReason(), candidate.getTitle(), candidate.getSummary(),
                    candidate.getDraftContent(), candidate.getStatus(), candidate.getCreatedAt());
        }
    }
}
