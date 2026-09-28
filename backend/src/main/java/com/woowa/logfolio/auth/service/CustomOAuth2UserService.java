package com.woowa.logfolio.auth.service;

import com.woowa.logfolio.auth.entity.OAuthAccount;
import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import com.woowa.logfolio.auth.model.OAuthProfile;
import com.woowa.logfolio.auth.model.PendingOAuth2User;
import com.woowa.logfolio.auth.repository.OAuthAccountRepository;
import com.woowa.logfolio.user.entity.User;
import com.woowa.logfolio.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.oauth2.client.userinfo.DefaultOAuth2UserService;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserRequest;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserService;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import jakarta.servlet.http.HttpSession;
import java.util.UUID;
import java.util.List;
import java.util.Locale;

@Service
@RequiredArgsConstructor
public class CustomOAuth2UserService implements OAuth2UserService<OAuth2UserRequest, OAuth2User> {

    private final OAuthAccountRepository oauthAccountRepository;
    private final UserRepository userRepository;
    private final DefaultOAuth2UserService delegate = new DefaultOAuth2UserService();

    @Override
    @Transactional
    public OAuth2User loadUser(OAuth2UserRequest request) throws OAuth2AuthenticationException {
        OAuth2User oauth2User = delegate.loadUser(request);
        OAuthProfile profile = OAuthProfile.from(
                request.getClientRegistration().getRegistrationId(), oauth2User.getAttributes());

        UUID linkingUserId = linkingUserId();
        User user;
        if (linkingUserId != null) {
            user = linkToSignedInUser(linkingUserId, profile);
        } else {
            OAuthAccount existingAccount = oauthAccountRepository
                    .findByProviderAndProviderUserId(profile.provider(), profile.providerUserId())
                    .orElse(null);
            if (existingAccount == null && isBlank(profile.email())) {
                return new PendingOAuth2User(
                        profile.provider(), profile.providerUserId(), profile.name(), oauth2User.getAttributes());
            }
            user = existingAccount == null ? linkOrCreateUser(profile) : existingAccount.getUser();
        }

        if (user.getDeletedAt() != null) {
            throw new OAuth2AuthenticationException(
                    new OAuth2Error("withdrawn_user"), "탈퇴한 계정입니다.");
        }

        return new LogfolioOAuth2User(
                user.getId(), user.getEmail(), List.of(new SimpleGrantedAuthority("ROLE_USER")),
                oauth2User.getAttributes());
    }

    @Transactional
    public LogfolioOAuth2User completeSignup(PendingOAuth2User pendingUser, String email) {
        String normalizedEmail = email.trim().toLowerCase(Locale.ROOT);
        if (oauthAccountRepository.findByProviderAndProviderUserId(
                pendingUser.getProvider(), pendingUser.getProviderUserId()).isPresent()) {
            throw new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.CONFLICT, "이미 가입 완료된 소셜 계정입니다.");
        }
        if (userRepository.existsByEmail(normalizedEmail)) {
            throw new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.CONFLICT,
                    "이미 가입된 이메일입니다. 기존 계정으로 로그인한 뒤 소셜 계정을 연동해주세요.");
        }

        User user = userRepository.save(new User(normalizedEmail, signupName(pendingUser, normalizedEmail)));
        oauthAccountRepository.save(new OAuthAccount(
                pendingUser.getProvider(), pendingUser.getProviderUserId(), null, null, user));
        return new LogfolioOAuth2User(
                user.getId(), user.getEmail(), List.of(new SimpleGrantedAuthority("ROLE_USER")),
                pendingUser.getAttributes());
    }

    private User linkOrCreateUser(OAuthProfile profile) {
        User user = userRepository.findByEmailAndDeletedAtIsNull(profile.email())
                .orElseGet(() -> userRepository.save(new User(profile.email(), profile.name())));
        oauthAccountRepository.save(new OAuthAccount(
                profile.provider(), profile.providerUserId(), profile.email(), null, user));
        return user;
    }

    private User linkToSignedInUser(UUID userId, OAuthProfile profile) {
        User target = userRepository.findByIdAndDeletedAtIsNull(userId)
                .orElseThrow(() -> new OAuth2AuthenticationException(
                        new OAuth2Error("link_target_not_found"), "연동할 사용자를 찾을 수 없습니다."));
        oauthAccountRepository.findByProviderAndProviderUserId(profile.provider(), profile.providerUserId())
                .ifPresentOrElse(existing -> {
                    if (!existing.getUser().getId().equals(userId)) {
                        throw new OAuth2AuthenticationException(
                                new OAuth2Error("already_linked"), "이미 다른 사용자에게 연동된 소셜 계정입니다.");
                    }
                }, () -> oauthAccountRepository.save(new OAuthAccount(
                        profile.provider(), profile.providerUserId(), profile.email(), null, target)));
        clearLinkingUserId();
        return target;
    }

    private UUID linkingUserId() {
        HttpSession session = currentSession();
        Object value = session == null ? null : session.getAttribute("LINK_AUTH_ACCOUNT_USER_ID");
        return value instanceof UUID id ? id : null;
    }

    private void clearLinkingUserId() {
        HttpSession session = currentSession();
        if (session != null) session.removeAttribute("LINK_AUTH_ACCOUNT_USER_ID");
    }

    private HttpSession currentSession() {
        if (RequestContextHolder.getRequestAttributes() instanceof ServletRequestAttributes attributes) {
            return attributes.getRequest().getSession(false);
        }
        return null;
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private String signupName(PendingOAuth2User pendingUser, String email) {
        String name = isBlank(pendingUser.getSuggestedName()) ? email : pendingUser.getSuggestedName().trim();
        return name.length() <= 100 ? name : name.substring(0, 100);
    }

}
