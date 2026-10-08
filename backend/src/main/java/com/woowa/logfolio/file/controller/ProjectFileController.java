package com.woowa.logfolio.file.controller;

import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import com.woowa.logfolio.file.service.ProjectFileService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Tag(name = "File", description = "프로젝트 자료와 저장공간 API")
@SecurityRequirement(name = "sessionCookie")
public class ProjectFileController {
    private final ProjectFileService service;

    @PostMapping(value = "/projects/{projectId}/files", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "프로젝트 자료 업로드", description = "PDF, PPT, PPTX, DOC, DOCX, FIG 파일을 최대 50MB까지 업로드합니다.")
    public ProjectFileService.FileResponse upload(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                  @PathVariable UUID projectId,
                                                  @RequestPart("file") MultipartFile file) {
        return service.upload(principal.getUserId(), projectId, file);
    }

    @GetMapping("/projects/{projectId}/files")
    @Operation(summary = "프로젝트 자료 목록")
    public List<ProjectFileService.FileResponse> projectFiles(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                              @PathVariable UUID projectId) {
        return service.listByProject(principal.getUserId(), projectId);
    }

    @GetMapping("/storage")
    @Operation(summary = "저장공간 사용량과 전체 업로드 파일 조회")
    public ProjectFileService.StorageResponse storage(@AuthenticationPrincipal LogfolioOAuth2User principal) {
        return service.storage(principal.getUserId());
    }

    @DeleteMapping("/files/{fileId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "업로드 파일 삭제", description = "파일을 삭제하면 해당 파일에서 생성된 근거도 더 이상 노출되지 않습니다.")
    public void delete(@AuthenticationPrincipal LogfolioOAuth2User principal, @PathVariable UUID fileId) {
        service.delete(principal.getUserId(), fileId);
    }

    @PostMapping("/files/{fileId}/indexing/retry")
    @Operation(summary = "파일 AI 인덱싱 재시도")
    public ProjectFileService.FileResponse retryIndexing(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                         @PathVariable UUID fileId) {
        return service.retryIndexing(principal.getUserId(), fileId);
    }
}
