package com.woowa.logfolio.auth.repository;

import com.woowa.logfolio.auth.entity.OAuthAccount;
import com.woowa.logfolio.auth.entity.OAuthProvider;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.List;
import java.util.UUID;

public interface OAuthAccountRepository extends JpaRepository<OAuthAccount, UUID> {

    Optional<OAuthAccount> findByProviderAndProviderUserId(OAuthProvider provider, String providerUserId);

    Optional<OAuthAccount> findByUserIdAndProvider(UUID userId, OAuthProvider provider);

    List<OAuthAccount> findAllByUserIdOrderByCreatedAt(UUID userId);

    long countByUserId(UUID userId);
}
