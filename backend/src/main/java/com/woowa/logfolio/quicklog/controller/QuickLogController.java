package com.woowa.logfolio.quicklog.controller;

import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import com.woowa.logfolio.quicklog.service.QuickLogService;
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

import java.util.UUID;

@RestController
@RequestMapping("/api/quick-logs")
@RequiredArgsConstructor
@Tag(name = "Quick Log", description = "30초 기록 API")
@SecurityRequirement(name = "sessionCookie")
public class QuickLogController {
    private final QuickLogService service;

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "30초 기록 저장")
    public QuickLogService.QuickLogResponse create(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                   @Valid @RequestBody CreateRequest body) {
        return service.create(principal.getUserId(), body.content(), body.projectId());
    }

    @GetMapping
    @Operation(summary = "전체 또는 프로젝트별 30초 기록 조회")
    public QuickLogService.QuickLogPage list(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                             @RequestParam(required = false) UUID projectId,
                                             @RequestParam(defaultValue = "0") int page,
                                             @RequestParam(defaultValue = "20") int size) {
        return service.list(principal.getUserId(), projectId, page, size);
    }

    @PatchMapping("/{id}")
    @Operation(summary = "30초 기록 내용 수정")
    public QuickLogService.QuickLogResponse update(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                   @PathVariable UUID id,
                                                   @Valid @RequestBody ContentUpdateRequest body) {
        return service.updateContent(principal.getUserId(), id, body.content());
    }

    @PutMapping("/{id}/project")
    @Operation(summary = "30초 기록의 프로젝트 연결 또는 변경", description = "projectId가 null이면 미지정으로 변경합니다.")
    public QuickLogService.QuickLogResponse link(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                 @PathVariable UUID id,
                                                 @RequestBody ProjectLinkRequest body) {
        return service.linkProject(principal.getUserId(), id, body.projectId());
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "30초 기록 삭제")
    public void delete(@AuthenticationPrincipal LogfolioOAuth2User principal, @PathVariable UUID id) {
        service.delete(principal.getUserId(), id);
    }

    public record CreateRequest(@NotBlank @Size(max = 5000) String content, UUID projectId) {}
    public record ContentUpdateRequest(@NotBlank @Size(max = 5000) String content) {}
    public record ProjectLinkRequest(UUID projectId) {}
}
