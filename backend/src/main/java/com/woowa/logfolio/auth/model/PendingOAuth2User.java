package com.woowa.logfolio.auth.model;

import com.woowa.logfolio.auth.entity.OAuthProvider;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.user.OAuth2User;

import java.io.Serial;
import java.io.Serializable;
import java.util.Collection;
import java.util.List;
import java.util.Map;

public class PendingOAuth2User implements OAuth2User, Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private static final List<GrantedAuthority> AUTHORITIES =
            List.of(new SimpleGrantedAuthority("ROLE_OAUTH2_PENDING"));

    private final OAuthProvider provider;
    private final String providerUserId;
    private final String suggestedName;
    private final Map<String, Object> attributes;

    public PendingOAuth2User(OAuthProvider provider, String providerUserId, String suggestedName,
                             Map<String, Object> attributes) {
        this.provider = provider;
        this.providerUserId = providerUserId;
        this.suggestedName = suggestedName;
        this.attributes = attributes;
    }

    public OAuthProvider getProvider() {
        return provider;
    }

    public String getProviderUserId() {
        return providerUserId;
    }

    public String getSuggestedName() {
        return suggestedName;
    }

    @Override
    public String getName() {
        return provider.name().toLowerCase() + ":" + providerUserId;
    }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return AUTHORITIES;
    }

    @Override
    public Map<String, Object> getAttributes() {
        return attributes;
    }
}
