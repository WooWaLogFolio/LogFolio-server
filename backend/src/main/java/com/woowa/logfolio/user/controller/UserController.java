package com.woowa.logfolio.user.controller;

import com.woowa.logfolio.user.dto.UserResponse;
import com.woowa.logfolio.user.dto.UserUpdateRequest;
import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import com.woowa.logfolio.user.service.UserService;
import com.woowa.logfolio.auth.service.AuthService;
import com.woowa.logfolio.auth.entity.OAuthProvider;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PathVariable;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.List;
import java.net.URI;
import jakarta.servlet.http.HttpSession;

@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
@Tag(name = "User", description = "사용자 관리 API")
@SecurityRequirement(name = "sessionCookie")
public class UserController {

    private final UserService userService;
    private final AuthService authService;

    @GetMapping("/me")
    @Operation(summary = "내 프로필 조회", responses = {
            @ApiResponse(responseCode = "200", description = "조회 성공"),
            @ApiResponse(responseCode = "401", description = "로그인이 필요함")
    })
    public UserResponse get(@AuthenticationPrincipal LogfolioOAuth2User principal) {
        return userService.get(principal.getUserId());
    }

    @PutMapping("/me")
    @Operation(summary = "내 프로필 수정", responses = {
            @ApiResponse(responseCode = "200", description = "수정 성공"),
            @ApiResponse(responseCode = "400", description = "요청값 오류"),
            @ApiResponse(responseCode = "401", description = "로그인이 필요함")
    })
    public UserResponse update(@AuthenticationPrincipal LogfolioOAuth2User principal,
                               @Valid @RequestBody UserUpdateRequest request) {
        return userService.update(principal.getUserId(), request);
    }

    @DeleteMapping("/me")
    @ResponseStatus(org.springframework.http.HttpStatus.NO_CONTENT)
    @Operation(summary = "회원 탈퇴", responses = {
            @ApiResponse(responseCode = "204", description = "탈퇴 성공"),
            @ApiResponse(responseCode = "401", description = "로그인이 필요함")
    })
    public void delete(@AuthenticationPrincipal LogfolioOAuth2User principal) {
        userService.delete(principal.getUserId());
    }

    @PostMapping("/me/onboarding/complete")
    @Operation(summary = "온보딩 완료 또는 건너뛰기")
    public UserResponse completeOnboarding(@AuthenticationPrincipal LogfolioOAuth2User principal) {
        return userService.completeOnboarding(principal.getUserId());
    }

    @PatchMapping("/me/name")
    @Operation(summary = "이름 변경")
    public UserResponse updateName(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                   @Valid @RequestBody NameUpdateRequest request) {
        return userService.updateName(principal.getUserId(), request.name());
    }

    @PutMapping("/me/password")
    @ResponseStatus(org.springframework.http.HttpStatus.NO_CONTENT)
    @Operation(summary = "비밀번호 변경")
    public void changePassword(@AuthenticationPrincipal LogfolioOAuth2User principal,
                               @Valid @RequestBody PasswordChangeRequest request) {
        authService.changePassword(principal.getUserId(), request.currentPassword(), request.newPassword());
    }

    @GetMapping("/me/auth-accounts")
    @Operation(summary = "로그인 계정 연동 상태 조회")
    public List<AuthService.AuthAccountView> authAccounts(@AuthenticationPrincipal LogfolioOAuth2User principal) {
        return authService.getAccounts(principal.getUserId());
    }

    @GetMapping("/me/auth-accounts/{provider}/link")
    @Operation(summary = "소셜 계정 연동 시작", description = "선택한 공급자의 OAuth2 인증 화면으로 이동합니다.")
    public ResponseEntity<Void> link(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                     @PathVariable OAuthProvider provider,
                                     HttpSession session) {
        if (provider == OAuthProvider.LOCAL) {
            throw new org.springframework.web.server.ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "LOCAL 계정은 소셜 연동 대상이 아닙니다.");
        }
        session.setAttribute("LINK_AUTH_ACCOUNT_USER_ID", principal.getUserId());
        return ResponseEntity.status(HttpStatus.FOUND)
                .header(HttpHeaders.LOCATION,
                        URI.create("/oauth2/authorization/" + provider.name().toLowerCase()).toString())
                .build();
    }

    @DeleteMapping("/me/auth-accounts/{provider}")
    @ResponseStatus(org.springframework.http.HttpStatus.NO_CONTENT)
    @Operation(summary = "소셜 계정 연동 해제")
    public void unlink(@AuthenticationPrincipal LogfolioOAuth2User principal,
                       @PathVariable OAuthProvider provider) {
        authService.unlink(principal.getUserId(), provider);
    }

    public record NameUpdateRequest(@NotBlank @Size(max = 100) String name) {}

    public record PasswordChangeRequest(
            @NotBlank String currentPassword,
            @NotBlank @Size(min = 8, max = 72) String newPassword
    ) {}
}
