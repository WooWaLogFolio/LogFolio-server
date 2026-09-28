package com.woowa.logfolio.api;

import com.jayway.jsonpath.JsonPath;
import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import com.woowa.logfolio.auth.model.PendingOAuth2User;
import com.woowa.logfolio.auth.entity.OAuthProvider;
import com.woowa.logfolio.auth.repository.OAuthAccountRepository;
import com.woowa.logfolio.user.entity.User;
import com.woowa.logfolio.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class FrontendApiIntegrationTest {

    @Autowired MockMvc mockMvc;
    @Autowired UserRepository userRepository;
    @Autowired OAuthAccountRepository oauthAccountRepository;

    @Test
    void signsUpWithEmailAndStartsAuthenticatedSession() throws Exception {
        String email = "signup-" + UUID.randomUUID() + "@example.com";

        mockMvc.perform(post("/api/auth/signup")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"신규 사용자","email":"%s","password":"password123"}
                                """.formatted(email)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value(email))
                .andExpect(jsonPath("$.status").value("ACTIVE"));
    }

    @Test
    void createsProjectAndLinkedQuickLogForCurrentUser() throws Exception {
        User user = userRepository.save(new User("api-" + UUID.randomUUID() + "@example.com", "API 사용자"));
        var auth = authenticationFor(user);

        String projectJson = mockMvc.perform(post("/api/projects")
                        .with(authentication(auth)).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"공모전 서비스","status":"IN_PROGRESS","activityType":"공모전·해커톤",
                                 "userRole":"서비스 기획","startedAt":"2026-03-01","description":"MVP 기획"}
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.userId").value(user.getId().toString()))
                .andReturn().getResponse().getContentAsString();
        String projectId = JsonPath.read(projectJson, "$.id");

        mockMvc.perform(post("/api/quick-logs")
                        .with(authentication(auth)).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"content":"MVP 기능 우선순위를 정했다.","projectId":"%s"}
                                """.formatted(projectId)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.projectId").value(projectId));

        mockMvc.perform(get("/api/archive").with(authentication(auth)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.projectCount").value(1))
                .andExpect(jsonPath("$.quickLogCount").value(1));
    }

    @Test
    void completesSignupWhenOAuthProviderDoesNotReturnEmail() throws Exception {
        String providerUserId = "kakao-" + UUID.randomUUID();
        String email = "oauth-" + UUID.randomUUID() + "@example.com";
        var pendingUser = new PendingOAuth2User(
                OAuthProvider.KAKAO, providerUserId, "카카오 사용자", Map.of("id", providerUserId));
        var pendingAuth = UsernamePasswordAuthenticationToken.authenticated(
                pendingUser, null, pendingUser.getAuthorities());

        mockMvc.perform(get("/api/auth/oauth2/pending-signup")
                        .with(authentication(pendingAuth)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.provider").value("KAKAO"))
                .andExpect(jsonPath("$.suggestedName").value("카카오 사용자"))
                .andExpect(jsonPath("$.emailRequired").value(true));

        mockMvc.perform(get("/api/archive").with(authentication(pendingAuth)))
                .andExpect(status().isForbidden());

        mockMvc.perform(post("/api/auth/oauth2/complete-signup")
                        .with(authentication(pendingAuth)).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"%s"}
                                """.formatted(email)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value(email))
                .andExpect(jsonPath("$.name").value("카카오 사용자"));

        var account = oauthAccountRepository
                .findByProviderAndProviderUserId(OAuthProvider.KAKAO, providerUserId)
                .orElseThrow();
        org.assertj.core.api.Assertions.assertThat(account.getUser().getEmail()).isEqualTo(email);
        org.assertj.core.api.Assertions.assertThat(account.getProviderEmail()).isNull();
    }

    @Test
    void rejectsExistingEmailDuringPendingOAuthSignup() throws Exception {
        User existing = userRepository.save(new User(
                "existing-" + UUID.randomUUID() + "@example.com", "기존 사용자"));
        var pendingUser = new PendingOAuth2User(
                OAuthProvider.NAVER, "naver-" + UUID.randomUUID(), "네이버 사용자", Map.of());
        var pendingAuth = UsernamePasswordAuthenticationToken.authenticated(
                pendingUser, null, pendingUser.getAuthorities());

        mockMvc.perform(post("/api/auth/oauth2/complete-signup")
                        .with(authentication(pendingAuth)).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"%s"}
                                """.formatted(existing.getEmail())))
                .andExpect(status().isConflict());
    }

    private UsernamePasswordAuthenticationToken authenticationFor(User user) {
        var authorities = List.of(new SimpleGrantedAuthority("ROLE_USER"));
        var principal = new LogfolioOAuth2User(user.getId(), user.getEmail(), authorities, Map.of());
        return UsernamePasswordAuthenticationToken.authenticated(principal, null, authorities);
    }
}
