package com.woowa.logfolio.project.controller;

import com.woowa.logfolio.project.dto.ProjectCreateRequest;
import com.woowa.logfolio.project.dto.ProjectResponse;
import com.woowa.logfolio.project.dto.ProjectUpdateRequest;
import com.woowa.logfolio.project.service.ProjectService;
import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/projects")
@RequiredArgsConstructor
@Tag(name = "Project", description = "프로젝트 관리 API")
@SecurityRequirement(name = "sessionCookie")
public class ProjectController {

    private final ProjectService projectService;

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "프로젝트 생성", responses = {
            @ApiResponse(responseCode = "201", description = "생성 성공"),
            @ApiResponse(responseCode = "400", description = "요청값 오류"),
            @ApiResponse(responseCode = "401", description = "로그인이 필요함")
    })
    public ProjectResponse create(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                  @Valid @RequestBody ProjectCreateRequest request) {
        return projectService.create(principal.getUserId(), request);
    }

    @GetMapping("/{id}")
    @Operation(summary = "내 프로젝트 단건 조회", responses = {
            @ApiResponse(responseCode = "200", description = "조회 성공"),
            @ApiResponse(responseCode = "404", description = "프로젝트가 없거나 접근 권한이 없음")
    })
    public ProjectResponse get(@AuthenticationPrincipal LogfolioOAuth2User principal,
                               @Parameter(description = "프로젝트 ID") @PathVariable UUID id) {
        return projectService.get(principal.getUserId(), id);
    }

    @GetMapping
    @Operation(summary = "내 프로젝트 목록 조회")
    public List<ProjectResponse> getByUser(@AuthenticationPrincipal LogfolioOAuth2User principal) {
        return projectService.getByUser(principal.getUserId());
    }

    @PutMapping("/{id}")
    @Operation(summary = "내 프로젝트 수정", responses = {
            @ApiResponse(responseCode = "200", description = "수정 성공"),
            @ApiResponse(responseCode = "400", description = "요청값 오류"),
            @ApiResponse(responseCode = "404", description = "프로젝트가 없거나 접근 권한이 없음")
    })
    public ProjectResponse update(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                  @PathVariable UUID id,
                                  @Valid @RequestBody ProjectUpdateRequest request) {
        return projectService.update(principal.getUserId(), id, request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "내 프로젝트 삭제", responses = {
            @ApiResponse(responseCode = "204", description = "삭제 성공"),
            @ApiResponse(responseCode = "404", description = "프로젝트가 없거나 접근 권한이 없음")
    })
    public void delete(@AuthenticationPrincipal LogfolioOAuth2User principal,
                       @PathVariable UUID id) {
        projectService.delete(principal.getUserId(), id);
    }
}
