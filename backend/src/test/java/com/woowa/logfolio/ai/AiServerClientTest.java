package com.woowa.logfolio.ai;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withBadRequest;

class AiServerClientTest {

    @Test
    void preservesFastApiErrorDetailsForAnalysisDiagnostics() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://ai-server:8000");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        AiServerClient client = new AiServerClient(
                builder.build(),
                new AiServerProperties(true, "http://ai-server:8000", "test-key",
                        Duration.ofSeconds(1), Duration.ofSeconds(2))
        );
        server.expect(requestTo("http://ai-server:8000/api/v1/analyses"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withBadRequest()
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("{\"code\":\"VALIDATION_ERROR\",\"message\":\"sourceIds가 필요합니다.\"}"));

        assertThatThrownBy(() -> client.analyze(Map.of("projectId", "test-project")))
                .isInstanceOf(AiServerException.class)
                .hasMessageContaining("400 BAD_REQUEST")
                .hasMessageContaining("VALIDATION_ERROR")
                .hasMessageContaining("sourceIds가 필요합니다.");

        server.verify();
    }
}
