package com.woowa.logfolio.auth.service;

import com.woowa.logfolio.auth.entity.OAuthAccount;
import com.woowa.logfolio.auth.entity.OAuthProvider;
import com.woowa.logfolio.auth.entity.PasswordResetToken;
import com.woowa.logfolio.auth.repository.OAuthAccountRepository;
import com.woowa.logfolio.auth.repository.PasswordResetTokenRepository;
import com.woowa.logfolio.user.entity.User;
import com.woowa.logfolio.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDateTime;
import java.util.HexFormat;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class PasswordResetService {
    private final UserRepository userRepository;
    private final OAuthAccountRepository accountRepository;
    private final PasswordResetTokenRepository tokenRepository;
    private final PasswordEncoder passwordEncoder;
    private final ApplicationEventPublisher eventPublisher;

    @Transactional
    public void request(String email) {
        userRepository.findByEmailAndDeletedAtIsNull(email.trim().toLowerCase(java.util.Locale.ROOT))
                .ifPresent(user -> createToken(user, email));
    }

    @Transactional
    public void confirm(String rawToken, String newPassword) {
        PasswordResetToken token = tokenRepository.findByTokenHash(hash(rawToken))
                .orElseThrow(this::invalidToken);
        if (!token.usable(LocalDateTime.now())) throw invalidToken();
        OAuthAccount account = accountRepository.findByUserIdAndProvider(token.getUser().getId(), OAuthProvider.LOCAL)
                .orElseThrow(this::invalidToken);
        account.changePassword(passwordEncoder.encode(newPassword));
        token.use();
    }

    private void createToken(User user, String email) {
        String rawToken = UUID.randomUUID() + "-" + UUID.randomUUID();
        tokenRepository.save(new PasswordResetToken(user, hash(rawToken), LocalDateTime.now().plusMinutes(30)));
        eventPublisher.publishEvent(new PasswordResetRequested(user.getId(), email, rawToken));
    }

    private String hash(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch (NoSuchAlgorithmException exception) { throw new IllegalStateException(exception); }
    }
    private ResponseStatusException invalidToken() {
        return new ResponseStatusException(HttpStatus.BAD_REQUEST, "유효하지 않거나 만료된 재설정 토큰입니다.");
    }
    public record PasswordResetRequested(UUID userId, String email, String rawToken) {}
}
