package com.woowa.logfolio.experience.controller;

import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import com.woowa.logfolio.experience.service.ExperienceService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Tag(name = "Experience", description = "경험 카드와 근거 자료 API")
@SecurityRequirement(name = "sessionCookie")
public class ExperienceController {
    private final ExperienceService service;

    @GetMapping("/projects/{projectId}/experiences")
    @Operation(summary = "프로젝트 경험 카드 목록")
    public List<ExperienceService.ExperienceResponse> list(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                           @PathVariable UUID projectId) {
        return service.list(principal.getUserId(), projectId);
    }

    @PostMapping("/projects/{projectId}/experiences")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "경험 카드 직접 작성")
    public ExperienceService.ExperienceResponse create(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                        @PathVariable UUID projectId,
                                                        @Valid @RequestBody WriteRequest body) {
        return service.create(principal.getUserId(), projectId, body.toService());
    }

    @GetMapping("/experiences/{id}")
    @Operation(summary = "경험 카드 상세 조회")
    public ExperienceService.ExperienceResponse get(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                     @PathVariable UUID id) {
        return service.get(principal.getUserId(), id);
    }

    @PutMapping("/experiences/{id}")
    @Operation(summary = "경험 카드 전체 수정", description = "직접 수정 또는 AI 제안 반영 결과를 저장합니다.")
    public ExperienceService.ExperienceResponse update(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                        @PathVariable UUID id,
                                                        @Valid @RequestBody WriteRequest body) {
        return service.update(principal.getUserId(), id, body.toService());
    }

    @DeleteMapping("/experiences/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "경험 카드 삭제")
    public void delete(@AuthenticationPrincipal LogfolioOAuth2User principal, @PathVariable UUID id) {
        service.delete(principal.getUserId(), id);
    }

    @GetMapping("/experiences/{id}/evidence")
    @Operation(summary = "경험 카드 근거 목록")
    public List<ExperienceService.EvidenceResponse> evidence(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                             @PathVariable UUID id) {
        return service.evidence(principal.getUserId(), id);
    }

    @GetMapping("/evidence/{id}")
    @Operation(summary = "근거 원문 상세")
    public ExperienceService.EvidenceResponse evidenceDetail(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                              @PathVariable UUID id) {
        return service.evidenceDetail(principal.getUserId(), id);
    }

    public record WriteRequest(
            @NotBlank @Size(max = 255) String title,
            String summary, String context, String contribution, String decisionReason,
            String action, String result, String learning, @NotBlank String status) {
        ExperienceService.ExperienceWriteRequest toService() {
            return new ExperienceService.ExperienceWriteRequest(title, summary, context, contribution,
                    decisionReason, action, result, learning, status);
        }
    }
}
