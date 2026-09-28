package com.woowa.logfolio.analysis.controller;

import com.woowa.logfolio.analysis.service.AnalysisService;
import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Tag(name = "Analysis", description = "AI 프로젝트 분석과 경험 후보 검토 API")
@SecurityRequirement(name = "sessionCookie")
public class AnalysisController {
    private final AnalysisService service;

    @PostMapping("/projects/{projectId}/analysis-runs")
    @ResponseStatus(HttpStatus.ACCEPTED)
    @Operation(summary = "프로젝트 AI 분석 요청", description = "작업을 QUEUED 상태로 생성합니다. AI 작업자는 비동기로 결과를 저장합니다.")
    public AnalysisService.AnalysisRunResponse start(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                     @PathVariable UUID projectId,
                                                     @RequestBody(required = false) StartRequest body) {
        StartRequest request = body == null ? new StartRequest(List.of(), List.of()) : body;
        return service.start(principal.getUserId(), projectId, request.fileIds(), request.quickLogIds());
    }

    @GetMapping("/analysis-runs/{runId}")
    @Operation(summary = "분석 진행 상태 조회")
    public AnalysisService.AnalysisRunResponse get(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                   @PathVariable UUID runId) {
        return service.get(principal.getUserId(), runId);
    }

    @GetMapping("/analysis-runs/{runId}/candidates")
    @Operation(summary = "AI가 발견한 경험 후보 목록")
    public List<AnalysisService.CandidateResponse> candidates(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                              @PathVariable UUID runId) {
        return service.candidates(principal.getUserId(), runId);
    }

    @PutMapping("/experience-candidates/{candidateId}")
    @Operation(summary = "경험 후보 수정 및 포함 여부 결정")
    public AnalysisService.CandidateResponse review(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                    @PathVariable UUID candidateId,
                                                    @RequestBody CandidateReviewRequest body) {
        return service.reviewCandidate(principal.getUserId(), candidateId, body.title(), body.summary(),
                body.draftContent(), body.status());
    }

    @PostMapping("/analysis-runs/{runId}/finalize")
    @Operation(summary = "포함한 후보로 경험 카드 생성")
    public FinalizeResponse finalizeRun(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                        @PathVariable UUID runId) {
        return new FinalizeResponse(service.finalizeIncluded(principal.getUserId(), runId));
    }

    public record StartRequest(List<UUID> fileIds, List<UUID> quickLogIds) {}
    public record CandidateReviewRequest(String title, String summary, Map<String, Object> draftContent, String status) {}
    public record FinalizeResponse(List<UUID> experienceIds) {}
}
