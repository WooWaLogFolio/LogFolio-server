package com.woowa.logfolio.ai;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.Map;

@Component
@RequiredArgsConstructor
public class AiServerClient {
    private static final String INTERNAL_API_KEY_HEADER = "X-Internal-API-Key";

    private final RestClient aiRestClient;
    private final AiServerProperties properties;

    public AiServerContract.SourceIndexResponse indexSources(
            AiServerContract.SourceIndexRequest request
    ) {
        if (!properties.enabled()) {
            throw new IllegalStateException("AI server integration is disabled");
        }
        try {
            AiServerContract.SourceIndexResponse response = aiRestClient.post()
                    .uri("/api/v1/sources/index")
                    .header(INTERNAL_API_KEY_HEADER, requiredApiKey())
                    .body(request)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (httpRequest, httpResponse) -> {
                        boolean retryable = httpResponse.getStatusCode().is5xxServerError();
                        throw new AiServerException(
                                "AI Source 인덱싱 요청이 실패했습니다: " + httpResponse.getStatusCode(),
                                retryable,
                                null
                        );
                    })
                    .body(AiServerContract.SourceIndexResponse.class);
            if (response == null) {
                throw new AiServerException("AI Source 인덱싱 응답이 비어 있습니다.", true, null);
            }
            return response;
        } catch (AiServerException exception) {
            throw exception;
        } catch (RestClientException exception) {
            throw new AiServerException("AI 서버에 연결하지 못했습니다.", true, exception);
        }
    }

    /** Calls the private FastAPI analysis endpoint.  This endpoint is never exposed to browsers. */
    public JsonNode analyze(Map<String, Object> request) {
        if (!properties.enabled()) {
            throw new IllegalStateException("AI server integration is disabled");
        }
        try {
            JsonNode response = aiRestClient.post()
                    .uri("/api/v1/analyses")
                    .header(INTERNAL_API_KEY_HEADER, requiredApiKey())
                    .body(request)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (httpRequest, httpResponse) -> {
                        throw new AiServerException(
                                "AI 분석 요청이 실패했습니다: " + httpResponse.getStatusCode(),
                                httpResponse.getStatusCode().is5xxServerError(), null);
                    })
                    .body(JsonNode.class);
            if (response == null) {
                throw new AiServerException("AI 분석 응답이 비어 있습니다.", true, null);
            }
            return response;
        } catch (AiServerException exception) {
            throw exception;
        } catch (RestClientException exception) {
            throw new AiServerException("AI 서버에 연결하지 못했습니다.", true, exception);
        }
    }

    private String requiredApiKey() {
        String apiKey = properties.internalApiKey();
        if (apiKey == null || apiKey.isBlank()) {
            throw new IllegalStateException("app.ai.internal-api-key 설정이 필요합니다.");
        }
        return apiKey;
    }
}
