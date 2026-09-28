package com.woowa.logfolio.archive.controller;

import com.woowa.logfolio.archive.service.ArchiveService;
import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/archive")
@RequiredArgsConstructor
@Tag(name = "Archive", description = "경험 아카이브 홈 API")
@SecurityRequirement(name = "sessionCookie")
public class ArchiveController {
    private final ArchiveService service;

    @GetMapping
    @Operation(summary = "아카이브 홈 조회", description = "프로젝트 카드, 경험 카드 수, 최근 30초 기록을 한 번에 반환합니다.")
    public ArchiveService.ArchiveResponse get(@AuthenticationPrincipal LogfolioOAuth2User principal) {
        return service.get(principal.getUserId());
    }
}
