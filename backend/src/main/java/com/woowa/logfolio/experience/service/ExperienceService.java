package com.woowa.logfolio.experience.service;

import com.woowa.logfolio.evidence.entity.EvidenceItem;
import com.woowa.logfolio.evidence.repository.EvidenceItemRepository;
import com.woowa.logfolio.experience.entity.Experience;
import com.woowa.logfolio.experience.repository.ExperienceRepository;
import com.woowa.logfolio.project.entity.Project;
import com.woowa.logfolio.project.service.ProjectService;
import lombok.RequiredArgsConstructor;
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
public class ExperienceService {
    private final ExperienceRepository repository;
    private final EvidenceItemRepository evidenceRepository;
    private final ProjectService projectService;

    public List<ExperienceResponse> list(UUID userId, UUID projectId) {
        projectService.findOwnedProject(userId, projectId);
        return repository.findAllByProjectIdAndProjectUserIdAndDeletedAtIsNullOrderByUpdatedAtDesc(projectId, userId)
                .stream().map(this::response).toList();
    }

    public ExperienceResponse get(UUID userId, UUID id) { return response(findOwned(userId, id)); }

    @Transactional
    public ExperienceResponse create(UUID userId, UUID projectId, ExperienceWriteRequest body) {
        String status = body.status() == null ? "ORGANIZING" : body.status();
        validateStatus(status);
        Project project = projectService.findOwnedProject(userId, projectId);
        Experience experience = new Experience(project, null, body.title(), body.summary());
        experience.initializeDetails(body.context(), body.contribution(), body.decisionReason(),
                body.action(), body.result(), body.learning(), status);
        return response(repository.save(experience));
    }

    @Transactional
    public ExperienceResponse update(UUID userId, UUID id, ExperienceWriteRequest body) {
        validateStatus(body.status());
        Experience experience = findOwned(userId, id);
        experience.update(body.title(), body.summary(), body.context(), body.contribution(), body.decisionReason(),
                body.action(), body.result(), body.learning(), body.status());
        return response(experience);
    }

    @Transactional
    public void delete(UUID userId, UUID id) { findOwned(userId, id).delete(); }

    public List<EvidenceResponse> evidence(UUID userId, UUID experienceId) {
        findOwned(userId, experienceId);
        return evidenceRepository.findAllForExperience(experienceId, userId).stream().map(EvidenceResponse::from).toList();
    }

    public EvidenceResponse evidenceDetail(UUID userId, UUID evidenceId) {
        EvidenceItem item = evidenceRepository.findByIdAndProjectUserId(evidenceId, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "근거 자료를 찾을 수 없습니다."));
        return EvidenceResponse.from(item);
    }

    public Experience findOwned(UUID userId, UUID id) {
        return repository.findByIdAndProjectUserIdAndDeletedAtIsNull(id, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "경험 카드를 찾을 수 없습니다."));
    }

    private void validateStatus(String status) {
        if (!List.of("ORGANIZING", "REVIEW_REQUIRED", "SUPPLEMENT_REQUIRED", "SAVED").contains(status)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "지원하지 않는 경험 상태입니다.");
        }
    }

    private ExperienceResponse response(Experience e) {
        return new ExperienceResponse(e.getId(), e.getProject().getId(), e.getTitle(), e.getSummary(), e.getContext(),
                e.getContribution(), e.getDecisionReason(), e.getAction(), e.getResult(), e.getLearning(),
                e.getStatus(), e.getVersion(), evidenceRepository.findAllForExperience(e.getId(), e.getProject().getUser().getId()).size(),
                e.getCreatedAt(), e.getUpdatedAt());
    }

    public record ExperienceWriteRequest(String title, String summary, String context, String contribution,
                                         String decisionReason, String action, String result, String learning,
                                         String status) {}
    public record ExperienceResponse(UUID id, UUID projectId, String title, String summary, String context,
                                     String contribution, String decisionReason, String action, String result,
                                     String learning, String status, int version, int evidenceCount,
                                     LocalDateTime createdAt, LocalDateTime updatedAt) {}
    public record EvidenceResponse(UUID id, UUID projectFileId, String fileName, UUID quickLogId,
                                   String excerpt, String location, LocalDateTime createdAt) {
        static EvidenceResponse from(EvidenceItem e) {
            return new EvidenceResponse(e.getId(), e.getProjectFile() == null ? null : e.getProjectFile().getId(),
                    e.getProjectFile() == null ? null : e.getProjectFile().getOriginalName(),
                    e.getQuickLog() == null ? null : e.getQuickLog().getId(), e.getExcerpt(), e.getLocation(), e.getCreatedAt());
        }
    }
}
