package com.woowa.logfolio.global.config;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class OpenApiDocumentationTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void documentsSessionSecurityAndCurrentUserApis() throws Exception {
        mockMvc.perform(get("/v3/api-docs"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.components.securitySchemes.sessionCookie.name").value("JSESSIONID"))
                .andExpect(jsonPath("$.paths['/api/auth/signup'].post").exists())
                .andExpect(jsonPath("$.paths['/api/auth/login'].post").exists())
                .andExpect(jsonPath("$.paths['/api/auth/password-reset/request'].post").exists())
                .andExpect(jsonPath("$.paths['/api/auth/password-reset/confirm'].post").exists())
                .andExpect(jsonPath("$.paths['/api/auth/login/naver'].get").exists())
                .andExpect(jsonPath("$.paths['/api/auth/login/kakao'].get").exists())
                .andExpect(jsonPath("$.paths['/api/auth/me'].get").exists())
                .andExpect(jsonPath("$.paths['/api/auth/oauth2/pending-signup'].get").exists())
                .andExpect(jsonPath("$.paths['/api/auth/oauth2/complete-signup'].post").exists())
                .andExpect(jsonPath("$.paths['/api/auth/csrf'].get").exists())
                .andExpect(jsonPath("$.paths['/api/auth/logout'].post").exists())
                .andExpect(jsonPath("$.paths['/api/users/me'].get").exists())
                .andExpect(jsonPath("$.paths['/api/users/me'].put").exists())
                .andExpect(jsonPath("$.paths['/api/users/me'].delete").exists())
                .andExpect(jsonPath("$.paths['/api/users/me/onboarding/complete'].post").exists())
                .andExpect(jsonPath("$.paths['/api/users/me/name'].patch").exists())
                .andExpect(jsonPath("$.paths['/api/users/me/password'].put").exists())
                .andExpect(jsonPath("$.paths['/api/users/me/auth-accounts'].get").exists())
                .andExpect(jsonPath("$.paths['/api/users/me/auth-accounts/{provider}/link'].get").exists())
                .andExpect(jsonPath("$.paths['/api/users/me/auth-accounts/{provider}'].delete").exists())
                .andExpect(jsonPath("$.paths['/api/projects'].get").exists())
                .andExpect(jsonPath("$.paths['/api/projects'].post").exists())
                .andExpect(jsonPath("$.paths['/api/projects/{id}'].get").exists())
                .andExpect(jsonPath("$.paths['/api/projects/{id}'].put").exists())
                .andExpect(jsonPath("$.paths['/api/projects/{id}'].delete").exists())
                .andExpect(jsonPath("$.paths['/api/archive'].get").exists())
                .andExpect(jsonPath("$.paths['/api/quick-logs'].post").exists())
                .andExpect(jsonPath("$.paths['/api/quick-logs'].get").exists())
                .andExpect(jsonPath("$.paths['/api/quick-logs/{id}'].patch").exists())
                .andExpect(jsonPath("$.paths['/api/quick-logs/{id}/project'].put").exists())
                .andExpect(jsonPath("$.paths['/api/quick-logs/{id}'].delete").exists())
                .andExpect(jsonPath("$.paths['/api/projects/{projectId}/files'].post").exists())
                .andExpect(jsonPath("$.paths['/api/projects/{projectId}/files'].get").exists())
                .andExpect(jsonPath("$.paths['/api/files/{fileId}'].delete").exists())
                .andExpect(jsonPath("$.paths['/api/storage'].get").exists())
                .andExpect(jsonPath("$.paths['/api/projects/{projectId}/analysis-runs'].post").exists())
                .andExpect(jsonPath("$.paths['/api/analysis-runs/{runId}'].get").exists())
                .andExpect(jsonPath("$.paths['/api/analysis-runs/{runId}/candidates'].get").exists())
                .andExpect(jsonPath("$.paths['/api/experience-candidates/{candidateId}'].put").exists())
                .andExpect(jsonPath("$.paths['/api/analysis-runs/{runId}/finalize'].post").exists())
                .andExpect(jsonPath("$.paths['/api/projects/{projectId}/experiences'].get").exists())
                .andExpect(jsonPath("$.paths['/api/projects/{projectId}/experiences'].post").exists())
                .andExpect(jsonPath("$.paths['/api/experiences/{id}'].get").exists())
                .andExpect(jsonPath("$.paths['/api/experiences/{id}'].put").exists())
                .andExpect(jsonPath("$.paths['/api/experiences/{id}'].delete").exists())
                .andExpect(jsonPath("$.paths['/api/experiences/{id}/evidence'].get").exists())
                .andExpect(jsonPath("$.paths['/api/evidence/{id}'].get").exists())
                .andExpect(jsonPath("$.paths['/api/experiences/{experienceId}/review-sessions'].post").exists())
                .andExpect(jsonPath("$.paths['/api/review-sessions/{sessionId}'].get").exists())
                .andExpect(jsonPath("$.paths['/api/review-items/{itemId}'].put").exists())
                .andExpect(jsonPath("$.paths['/api/review-sessions/{sessionId}/complete'].post").exists())
                .andExpect(jsonPath("$.paths['/api/experiences/{experienceId}/gap-questions'].get").exists())
                .andExpect(jsonPath("$.paths['/api/gap-questions/{questionId}/answers'].post").exists())
                .andExpect(jsonPath("$.components.schemas.CompleteOAuthSignupRequest.properties.email").exists())
                .andExpect(jsonPath("$.components.schemas.PendingSignupResponse.properties.emailRequired").exists())
                .andExpect(jsonPath("$.components.schemas.ProjectCreateRequest.properties.userId").doesNotExist())
                .andExpect(jsonPath("$.components.schemas.ProjectCreateRequest.properties.description").exists());
    }
}
