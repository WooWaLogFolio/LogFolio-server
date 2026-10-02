package com.woowa.logfolio.auth.model;

import com.woowa.logfolio.auth.entity.OAuthProvider;
import org.junit.jupiter.api.Test;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class OAuthProfileTest {

    @Test
    void parsesNaverProfile() {
        OAuthProfile profile = OAuthProfile.from("naver", Map.of(
                "response", Map.of(
                        "id", "naver-123",
                        "email", "user@example.com",
                        "name", "홍길동"
                )
        ));

        assertThat(profile.provider()).isEqualTo(OAuthProvider.NAVER);
        assertThat(profile.providerUserId()).isEqualTo("naver-123");
        assertThat(profile.email()).isEqualTo("user@example.com");
        assertThat(profile.name()).isEqualTo("홍길동");
    }

    @Test
    void parsesKakaoProfile() {
        OAuthProfile profile = OAuthProfile.from("kakao", Map.of(
                "id", 12345L,
                "kakao_account", Map.of(
                        "email", "user@example.com",
                        "profile", Map.of("nickname", "길동")
                )
        ));

        assertThat(profile.provider()).isEqualTo(OAuthProvider.KAKAO);
        assertThat(profile.providerUserId()).isEqualTo("12345");
        assertThat(profile.name()).isEqualTo("길동");
    }

    @Test
    void acceptsProfileWithoutEmailForAdditionalSignup() {
        OAuthProfile profile = OAuthProfile.from("kakao", Map.of(
                "id", 12345L,
                "kakao_account", Map.of("profile", Map.of("nickname", "길동"))
        ));

        assertThat(profile.provider()).isEqualTo(OAuthProvider.KAKAO);
        assertThat(profile.providerUserId()).isEqualTo("12345");
        assertThat(profile.email()).isNull();
        assertThat(profile.name()).isEqualTo("길동");
    }

    @Test
    void acceptsKakaoProfileWithOnlyProviderUserId() {
        OAuthProfile profile = OAuthProfile.from("kakao", Map.of("id", 12345L));

        assertThat(profile.provider()).isEqualTo(OAuthProvider.KAKAO);
        assertThat(profile.providerUserId()).isEqualTo("12345");
        assertThat(profile.email()).isNull();
        assertThat(profile.name()).isEqualTo("카카오 사용자");
    }
}
