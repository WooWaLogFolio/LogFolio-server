package com.woowa.logfolio.ai;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

@ConfigurationProperties(prefix = "app.ai")
public record AiServerProperties(
        boolean enabled,
        String baseUrl,
        String internalApiKey,
        Duration connectTimeout,
        Duration readTimeout
) {
    public AiServerProperties {
        baseUrl = baseUrl == null || baseUrl.isBlank() ? "http://localhost:8000" : baseUrl;
        connectTimeout = connectTimeout == null ? Duration.ofSeconds(3) : connectTimeout;
        readTimeout = readTimeout == null ? Duration.ofSeconds(35) : readTimeout;
    }
}
