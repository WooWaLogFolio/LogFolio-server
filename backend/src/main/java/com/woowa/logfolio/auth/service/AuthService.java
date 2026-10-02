package com.woowa.logfolio.auth.service;

import com.woowa.logfolio.auth.entity.OAuthAccount;
import com.woowa.logfolio.auth.entity.OAuthProvider;
import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import com.woowa.logfolio.auth.repository.OAuthAccountRepository;
import com.woowa.logfolio.user.entity.User;
import com.woowa.logfolio.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class AuthService {

    private final UserRepository userRepository;
    private final OAuthAccountRepository accountRepository;
    private final PasswordEncoder passwordEncoder;

    @Transactional
    public LogfolioOAuth2User signup(String email, String name, String password) {
        String normalizedEmail = normalizeEmail(email);
        if (userRepository.existsByEmail(normalizedEmail)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 가입된 이메일입니다.");
        }
        User user = userRepository.save(new User(normalizedEmail, name.trim()));
        accountRepository.save(new OAuthAccount(
                OAuthProvider.LOCAL, normalizedEmail, normalizedEmail,
                passwordEncoder.encode(password), user));
        return principal(user);
    }

    public LogfolioOAuth2User login(String email, String password) {
        String normalizedEmail = normalizeEmail(email);
        OAuthAccount account = accountRepository
                .findByProviderAndProviderUserId(OAuthProvider.LOCAL, normalizedEmail)
                .orElseThrow(this::badCredentials);
        if (!passwordEncoder.matches(password, account.getPasswordHash())) {
            throw badCredentials();
        }
        User user = account.getUser();
        if (user.getDeletedAt() != null) {
            throw badCredentials();
        }
        return principal(user);
    }

    @Transactional
    public void changePassword(UUID userId, String currentPassword, String newPassword) {
        OAuthAccount account = accountRepository.findByUserIdAndProvider(userId, OAuthProvider.LOCAL)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "비밀번호 로그인 계정이 없습니다."));
        if (!passwordEncoder.matches(currentPassword, account.getPasswordHash())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "현재 비밀번호가 일치하지 않습니다.");
        }
        account.changePassword(passwordEncoder.encode(newPassword));
    }

    public List<AuthAccountView> getAccounts(UUID userId) {
        return accountRepository.findAllByUserIdOrderByCreatedAt(userId).stream()
                .map(account -> new AuthAccountView(
                        account.getProvider(), account.getProviderEmail(), account.getCreatedAt()))
                .toList();
    }

    @Transactional
    public void unlink(UUID userId, OAuthProvider provider) {
        OAuthAccount account = accountRepository.findByUserIdAndProvider(userId, provider)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "연동된 계정을 찾을 수 없습니다."));
        if (accountRepository.countByUserId(userId) <= 1) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "마지막 로그인 수단은 해제할 수 없습니다.");
        }
        accountRepository.delete(account);
    }

    public UsernamePasswordAuthenticationToken authentication(LogfolioOAuth2User principal) {
        return UsernamePasswordAuthenticationToken.authenticated(
                principal, null, principal.getAuthorities());
    }

    private LogfolioOAuth2User principal(User user) {
        return new LogfolioOAuth2User(
                user.getId(), user.getEmail(), List.of(new SimpleGrantedAuthority("ROLE_USER")), java.util.Map.of());
    }

    private String normalizeEmail(String email) {
        return email.trim().toLowerCase(java.util.Locale.ROOT);
    }

    private ResponseStatusException badCredentials() {
        return new ResponseStatusException(HttpStatus.UNAUTHORIZED, "이메일 또는 비밀번호가 일치하지 않습니다.");
    }

    public record AuthAccountView(OAuthProvider provider, String email, java.time.LocalDateTime linkedAt) {}
}
