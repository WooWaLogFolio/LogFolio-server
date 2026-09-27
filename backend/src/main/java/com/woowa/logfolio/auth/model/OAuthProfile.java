package com.woowa.logfolio.auth.model;

import com.woowa.logfolio.auth.entity.OAuthProvider;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.OAuth2Error;

import java.util.Map;

public record OAuthProfile(OAuthProvider provider, String providerUserId, String email, String name) {

    public static OAuthProfile from(String registrationId, Map<String, Object> attributes) {
        return switch (registrationId.toLowerCase()) {
            case "naver" -> fromNaver(attributes);
            case "kakao" -> fromKakao(attributes);
            default -> throw error("지원하지 않는 OAuth 공급자입니다: " + registrationId);
        };
    }

    private static OAuthProfile fromNaver(Map<String, Object> attributes) {
        Map<String, Object> response = map(attributes.get("response"), "네이버 사용자 응답이 올바르지 않습니다.");
        return create(
                OAuthProvider.NAVER,
                string(response.get("id")),
                string(response.get("email")),
                firstNonBlank(string(response.get("name")), string(response.get("nickname")))
        );
    }

    private static OAuthProfile fromKakao(Map<String, Object> attributes) {
        String id = attributes.get("id") == null ? null : String.valueOf(attributes.get("id"));
        Map<String, Object> account = attributes.get("kakao_account") instanceof Map<?, ?> value
                ? map(value, "카카오 계정 응답이 올바르지 않습니다.") : Map.of();
        Map<String, Object> profile = account.get("profile") instanceof Map<?, ?> value
                ? map(value, "카카오 프로필 응답이 올바르지 않습니다.") : Map.of();
        return create(
                OAuthProvider.KAKAO,
                id,
                string(account.get("email")),
                firstNonBlank(string(profile.get("nickname")), "카카오 사용자")
        );
    }

    private static OAuthProfile create(OAuthProvider provider, String id, String email, String name) {
        if (isBlank(id)) {
            throw error(provider + " 로그인에 사용자 ID가 필요합니다.");
        }
        String resolvedName = isBlank(name)
                ? (isBlank(email) ? provider.name() + " 사용자" : email)
                : name;
        return new OAuthProfile(provider, id, isBlank(email) ? null : email, resolvedName);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> map(Object value, String message) {
        if (!(value instanceof Map<?, ?>)) {
            throw error(message);
        }
        return (Map<String, Object>) value;
    }

    private static String string(Object value) {
        return value instanceof String text ? text : null;
    }

    private static String firstNonBlank(String first, String second) {
        return isBlank(first) ? second : first;
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private static OAuth2AuthenticationException error(String message) {
        return new OAuth2AuthenticationException(new OAuth2Error("invalid_user_info"), message);
    }
}
