package com.woowa.logfolio.analysis.controller;

import com.woowa.logfolio.analysis.service.AnalysisService;
import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Tag(name = "Analysis", description = "AI 분석, 신규/기존 경험 판단, 사용자 검토 및 확정 API")
@SecurityRequirement(name = "sessionCookie")
public class AnalysisController {
    private final AnalysisService service;

    @PostMapping("/projects/{projectId}/analysis-runs")
    @ResponseStatus(HttpStatus.ACCEPTED)
    @Operation(summary = "프로젝트 AI 분석 요청", description = "첫 분석은 PROJECT_INITIAL, 이후 분석은 PROJECT_INCREMENTAL로 자동 지정됩니다.")
    public AnalysisService.AnalysisRunResponse start(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                     @PathVariable UUID projectId,
                                                     @Valid @RequestBody(required = false) StartRequest body) {
        StartRequest request = body == null ? new StartRequest(null, List.of(), List.of()) : body;
        return service.start(principal.getUserId(), projectId, request.runType(), request.fileIds(), request.quickLogIds());
    }

    @GetMapping("/projects/{projectId}/analysis-runs")
    @Operation(summary = "프로젝트 분석 이력 조회")
    public List<AnalysisService.AnalysisRunResponse> list(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                          @PathVariable UUID projectId) {
        return service.list(principal.getUserId(), projectId);
    }

    @GetMapping("/analysis-runs/{runId}")
    @Operation(summary = "분석 진행 상태 조회", description = "QUEUED → REVIEW_READY → FINALIZED 상태를 확인합니다.")
    public AnalysisService.AnalysisRunResponse get(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                   @PathVariable UUID runId) {
        return service.get(principal.getUserId(), runId);
    }

    @PostMapping("/analysis-runs/{runId}/results")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "AI 분석 결과 저장", description = "AI 작업 결과와 신규/기존 경험 판단을 저장하고 실행 상태를 REVIEW_READY로 변경합니다. 현재는 사용자 세션 인증을 사용합니다.")
    public List<AnalysisService.CandidateResponse> saveResults(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                               @PathVariable UUID runId,
                                                               @Valid @RequestBody AnalysisResultRequest body) {
        return service.saveResults(principal.getUserId(), runId, body.modelVersion(),
                body.candidates().stream().map(CandidateResultRequest::toService).toList());
    }

    @PostMapping("/analysis-runs/{runId}/fail")
    @Operation(summary = "AI 분석 실패 처리")
    public AnalysisService.AnalysisRunResponse fail(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                    @PathVariable UUID runId) {
        return service.fail(principal.getUserId(), runId);
    }

    @GetMapping("/analysis-runs/{runId}/candidates")
    @Operation(summary = "AI가 발견한 경험 후보 목록")
    public List<AnalysisService.CandidateResponse> candidates(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                              @PathVariable UUID runId) {
        return service.candidates(principal.getUserId(), runId);
    }

    @PutMapping("/experience-candidates/{candidateId}/decision")
    @Operation(summary = "경험 후보 사용자 결정", description = "CREATE_NEW, MERGE_EXISTING, EXCLUDED 중 하나를 선택합니다. 기존 경험 보강 시 targetExperienceId가 필요합니다.")
    public AnalysisService.CandidateResponse decide(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                    @PathVariable UUID candidateId,
                                                    @Valid @RequestBody CandidateDecisionRequest body) {
        return service.decide(principal.getUserId(), candidateId, body.title(), body.summary(), body.draftContent(),
                body.decision(), body.targetExperienceId());
    }

    @Deprecated
    @PutMapping("/experience-candidates/{candidateId}")
    @Operation(summary = "경험 후보 수정 및 포함 여부 결정(구버전)", deprecated = true,
            description = "기존 INCLUDED 요청을 CREATE_NEW 또는 MERGE_EXISTING 결정으로 변환합니다. 새 API 사용을 권장합니다.")
    public AnalysisService.CandidateResponse review(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                    @PathVariable UUID candidateId,
                                                    @Valid @RequestBody CandidateReviewRequest body) {
        return service.reviewCandidate(principal.getUserId(), candidateId, body.title(), body.summary(), body.draftContent(), body.status());
    }

    @PostMapping("/analysis-runs/{runId}/finalize")
    @Operation(summary = "사용자 결정을 경험 카드에 반영", description = "CREATE_NEW는 새 경험을 만들고 MERGE_EXISTING은 기존 경험을 보강하며, 분석 입력 자료를 근거로 연결합니다.")
    public FinalizeResponse finalizeRun(@AuthenticationPrincipal LogfolioOAuth2User principal, @PathVariable UUID runId) {
        AnalysisService.FinalizeResult result = service.finalizeDecisions(principal.getUserId(), runId);
        return new FinalizeResponse(result.createdExperienceIds(), result.updatedExperienceIds());
    }

    public record StartRequest(
            @Schema(allowableValues = {"PROJECT_INITIAL", "PROJECT_INCREMENTAL"}) String runType,
            List<UUID> fileIds, List<UUID> quickLogIds) {}

    public record AnalysisResultRequest(@NotBlank String modelVersion,
                                        @NotNull @Valid List<CandidateResultRequest> candidates) {}

    public record CandidateResultRequest(
            @NotBlank @Schema(allowableValues = {"NEW", "ENHANCE_EXISTING"}) String candidateType,
            UUID targetExperienceId,
            @Schema(minimum = "0", maximum = "1") BigDecimal matchConfidence,
            String matchReason,
            @NotBlank @Size(max = 255) String title,
            String summary,
            Map<String, Object> draftContent) {
        AnalysisService.CandidateInput toService() {
            return new AnalysisService.CandidateInput(candidateType, targetExperienceId, matchConfidence,
                    matchReason, title, summary, draftContent);
        }
    }

    public record CandidateDecisionRequest(
            @NotBlank @Schema(allowableValues = {"CREATE_NEW", "MERGE_EXISTING", "EXCLUDED"}) String decision,
            UUID targetExperienceId, String title, String summary, Map<String, Object> draftContent) {}

    public record CandidateReviewRequest(String title, String summary, Map<String, Object> draftContent,
                                         @NotBlank String status) {}
    public record FinalizeResponse(List<UUID> createdExperienceIds, List<UUID> updatedExperienceIds) {}
}
