package com.woowa.logfolio.auth.controller;

import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import com.woowa.logfolio.auth.model.PendingOAuth2User;
import com.woowa.logfolio.auth.service.AuthService;
import com.woowa.logfolio.auth.service.CustomOAuth2UserService;
import com.woowa.logfolio.auth.service.PasswordResetService;
import com.woowa.logfolio.auth.entity.OAuthProvider;
import com.woowa.logfolio.user.dto.UserResponse;
import com.woowa.logfolio.user.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@Tag(name = "Auth", description = "소셜 로그인 및 인증 API")
public class AuthController {

    private final UserService userService;
    private final AuthService authService;
    private final PasswordResetService passwordResetService;
    private final CustomOAuth2UserService customOAuth2UserService;

    @PostMapping("/signup")
    @Operation(summary = "이메일 회원가입", description = "계정을 만들고 현재 세션에 바로 로그인합니다.")
    public UserResponse signup(@Valid @RequestBody SignupRequest body,
                               HttpServletRequest request, HttpServletResponse response) {
        LogfolioOAuth2User principal = authService.signup(body.email(), body.name(), body.password());
        saveAuthentication(principal, request, response);
        return userService.get(principal.getUserId());
    }

    @PostMapping("/login")
    @Operation(summary = "이메일 로그인")
    public UserResponse login(@Valid @RequestBody LoginRequest body,
                              HttpServletRequest request, HttpServletResponse response) {
        LogfolioOAuth2User principal = authService.login(body.email(), body.password());
        saveAuthentication(principal, request, response);
        return userService.get(principal.getUserId());
    }

    @PostMapping("/password-reset/request")
    @ResponseStatus(HttpStatus.ACCEPTED)
    @Operation(summary = "비밀번호 재설정 메일 요청", description = "가입 여부 노출을 막기 위해 항상 202를 반환합니다.")
    public void requestPasswordReset(@Valid @RequestBody PasswordResetRequest body) {
        passwordResetService.request(body.email());
    }

    @PostMapping("/password-reset/confirm")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "비밀번호 재설정 완료")
    public void confirmPasswordReset(@Valid @RequestBody PasswordResetConfirmRequest body) {
        passwordResetService.confirm(body.token(), body.newPassword());
    }

    @GetMapping("/login/naver")
    @Operation(
            summary = "네이버 로그인",
            description = "네이버 인증 화면으로 이동합니다. 브라우저 주소창에서 호출하세요.",
            responses = @ApiResponse(responseCode = "302", description = "네이버 OAuth2 인증 경로로 이동")
    )
    public ResponseEntity<Void> naverLogin() {
        return oauthRedirect("naver");
    }

    @GetMapping("/login/kakao")
    @Operation(
            summary = "카카오 로그인",
            description = "카카오 인증 화면으로 이동합니다. 브라우저 주소창에서 호출하세요.",
            responses = @ApiResponse(responseCode = "302", description = "카카오 OAuth2 인증 경로로 이동")
    )
    public ResponseEntity<Void> kakaoLogin() {
        return oauthRedirect("kakao");
    }

    @GetMapping("/me")
    @SecurityRequirement(name = "sessionCookie")
    @Operation(
            summary = "내 정보 조회",
            description = "현재 OAuth2 세션으로 로그인한 사용자 정보를 반환합니다.",
            responses = {
                    @ApiResponse(responseCode = "200", description = "로그인 사용자 정보"),
                    @ApiResponse(responseCode = "401", description = "로그인이 필요함", content = @Content)
            }
    )
    public UserResponse me(@AuthenticationPrincipal LogfolioOAuth2User principal) {
        return userService.get(principal.getUserId());
    }

    @GetMapping("/oauth2/pending-signup")
    @SecurityRequirement(name = "sessionCookie")
    @Operation(
            summary = "소셜 추가 가입 정보 조회",
            description = "소셜 공급자가 이메일을 제공하지 않아 추가 가입이 필요한 세션의 공급자와 추천 이름을 반환합니다.",
            responses = {
                    @ApiResponse(responseCode = "200", description = "추가 가입 정보"),
                    @ApiResponse(responseCode = "403", description = "추가 가입 대상 세션이 아님", content = @Content)
            }
    )
    public PendingSignupResponse pendingSignup(@AuthenticationPrincipal PendingOAuth2User principal) {
        return new PendingSignupResponse(principal.getProvider(), principal.getSuggestedName(), true);
    }

    @PostMapping("/oauth2/complete-signup")
    @SecurityRequirement(name = "sessionCookie")
    @Operation(
            summary = "소셜 추가 가입 완료",
            description = "사용자가 직접 입력한 이메일로 계정과 소셜 로그인 수단을 생성하고 일반 로그인 세션으로 전환합니다.",
            responses = {
                    @ApiResponse(responseCode = "200", description = "가입 완료"),
                    @ApiResponse(responseCode = "400", description = "잘못된 이메일", content = @Content),
                    @ApiResponse(responseCode = "409", description = "이미 가입된 이메일 또는 소셜 계정", content = @Content)
            }
    )
    public UserResponse completeOAuthSignup(
            @AuthenticationPrincipal PendingOAuth2User pendingUser,
            @Valid @RequestBody CompleteOAuthSignupRequest body,
            HttpServletRequest request,
            HttpServletResponse response) {
        LogfolioOAuth2User principal = customOAuth2UserService.completeSignup(pendingUser, body.email());
        saveAuthentication(principal, request, response);
        return userService.get(principal.getUserId());
    }

    @GetMapping("/csrf")
    @SecurityRequirement(name = "sessionCookie")
    @Operation(
            summary = "CSRF 토큰 발급",
            description = "상태 변경 요청에 사용할 CSRF 토큰을 반환하고 XSRF-TOKEN 쿠키를 설정합니다."
    )
    public CsrfTokenResponse csrf(CsrfToken csrfToken) {
        return new CsrfTokenResponse(csrfToken.getHeaderName(), csrfToken.getParameterName(), csrfToken.getToken());
    }

    @PostMapping("/logout")
    @SecurityRequirement(name = "sessionCookie")
    @Operation(
            summary = "로그아웃",
            description = "현재 세션을 종료합니다. X-XSRF-TOKEN 헤더가 필요합니다.",
            responses = {
                    @ApiResponse(responseCode = "204", description = "로그아웃 완료", content = @Content),
                    @ApiResponse(responseCode = "403", description = "CSRF 토큰 누락 또는 불일치", content = @Content)
            }
    )
    public void logoutDocumentationOnly(HttpServletResponse response) {
        response.setStatus(HttpStatus.NO_CONTENT.value());
    }

    private ResponseEntity<Void> oauthRedirect(String provider) {
        return ResponseEntity.status(HttpStatus.FOUND)
                .header(HttpHeaders.LOCATION, URI.create("/oauth2/authorization/" + provider).toString())
                .build();
    }

    private void saveAuthentication(LogfolioOAuth2User principal,
                                    HttpServletRequest request, HttpServletResponse response) {
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authService.authentication(principal));
        SecurityContextHolder.setContext(context);
        new HttpSessionSecurityContextRepository().saveContext(context, request, response);
    }

    @Schema(description = "이메일 회원가입 요청")
    public record SignupRequest(
            @NotBlank @Size(max = 100) String name,
            @NotBlank @Email String email,
            @NotBlank @Size(min = 8, max = 72) String password
    ) {}

    @Schema(description = "이메일 로그인 요청")
    public record LoginRequest(
            @NotBlank @Email String email,
            @NotBlank String password
    ) {}

    public record PasswordResetRequest(@NotBlank @Email String email) {}
    public record PasswordResetConfirmRequest(
            @NotBlank String token,
            @NotBlank @Size(min = 8, max = 72) String newPassword
    ) {}

    @Schema(description = "소셜 추가 가입 요청")
    public record CompleteOAuthSignupRequest(@NotBlank @Email String email) {}

    @Schema(description = "소셜 추가 가입 상태")
    public record PendingSignupResponse(
            OAuthProvider provider,
            String suggestedName,
            boolean emailRequired
    ) {}

    @Schema(description = "CSRF 토큰")
    public record CsrfTokenResponse(
            @Schema(example = "X-XSRF-TOKEN") String headerName,
            @Schema(example = "_csrf") String parameterName,
            String token
    ) {
    }
}
