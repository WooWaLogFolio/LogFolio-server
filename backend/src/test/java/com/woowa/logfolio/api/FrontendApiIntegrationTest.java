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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
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
    void allowsCredentialedCorsRequestsFromLocalViteServer() throws Exception {
        mockMvc.perform(options("/api/auth/me")
                        .header("Origin", "http://localhost:5173")
                        .header("Access-Control-Request-Method", "GET"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "http://localhost:5173"))
                .andExpect(header().string("Access-Control-Allow-Credentials", "true"));
    }

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

    @Test
    void completesAnalysisCandidateDecisionAndExperienceConfirmationFlow() throws Exception {
        User user = userRepository.save(new User("flow-" + UUID.randomUUID() + "@example.com", "플로우 사용자"));
        var auth = authenticationFor(user);

        String projectJson = mockMvc.perform(post("/api/projects").with(authentication(auth)).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"첫 프로젝트","status":"IN_PROGRESS"}
                                """))
                .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        String projectId = JsonPath.read(projectJson, "$.id");

        String logJson = mockMvc.perform(post("/api/quick-logs").with(authentication(auth)).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"content":"사용자 인터뷰를 바탕으로 핵심 기능을 정했다.","projectId":"%s"}
                                """.formatted(projectId)))
                .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        String quickLogId = JsonPath.read(logJson, "$.id");

        String runJson = mockMvc.perform(post("/api/projects/{projectId}/analysis-runs", projectId)
                        .with(authentication(auth)).with(csrf()).contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"quickLogIds":["%s"]}
                                """.formatted(quickLogId)))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.runType").value("PROJECT_INITIAL"))
                .andReturn().getResponse().getContentAsString();
        String runId = JsonPath.read(runJson, "$.id");

        String candidatesJson = mockMvc.perform(post("/api/analysis-runs/{runId}/results", runId)
                        .with(authentication(auth)).with(csrf()).contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"modelVersion":"test-model","candidates":[{
                                  "candidateType":"NEW","matchConfidence":0.91,"matchReason":"새 경험",
                                  "title":"핵심 기능 결정","summary":"인터뷰 기반 결정",
                                  "draftContent":{"action":"우선순위를 정함","result":"MVP 범위 확정"}
                                }]}
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$[0].candidateType").value("NEW"))
                .andReturn().getResponse().getContentAsString();
        String candidateId = JsonPath.read(candidatesJson, "$[0].id");

        mockMvc.perform(put("/api/experience-candidates/{candidateId}/decision", candidateId)
                        .with(authentication(auth)).with(csrf()).contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"decision":"CREATE_NEW"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("CREATE_NEW"));

        String finalizeJson = mockMvc.perform(post("/api/analysis-runs/{runId}/finalize", runId)
                        .with(authentication(auth)).with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdExperienceIds.length()").value(1))
                .andExpect(jsonPath("$.updatedExperienceIds.length()").value(0))
                .andReturn().getResponse().getContentAsString();
        String experienceId = JsonPath.read(finalizeJson, "$.createdExperienceIds[0]");

        mockMvc.perform(get("/api/experiences/{id}/evidence", experienceId).with(authentication(auth)))
                .andExpect(status().isOk()).andExpect(jsonPath("$[0].quickLogId").value(quickLogId));
        mockMvc.perform(post("/api/experiences/{id}/confirm", experienceId)
                        .with(authentication(auth)).with(csrf()))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("SAVED"));
    }

    private UsernamePasswordAuthenticationToken authenticationFor(User user) {
        var authorities = List.of(new SimpleGrantedAuthority("ROLE_USER"));
        var principal = new LogfolioOAuth2User(user.getId(), user.getEmail(), authorities, Map.of());
        return UsernamePasswordAuthenticationToken.authenticated(principal, null, authorities);
    }
}
