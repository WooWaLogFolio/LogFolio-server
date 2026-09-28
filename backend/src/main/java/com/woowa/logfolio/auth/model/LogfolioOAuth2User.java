package com.woowa.logfolio.auth.model;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.oauth2.core.user.OAuth2User;

import java.io.Serial;
import java.io.Serializable;
import java.util.Collection;
import java.util.Map;
import java.util.UUID;

public class LogfolioOAuth2User implements OAuth2User, Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private final UUID userId;
    private final String email;
    private final Collection<? extends GrantedAuthority> authorities;
    private final Map<String, Object> attributes;

    public LogfolioOAuth2User(UUID userId, String email,
                             Collection<? extends GrantedAuthority> authorities,
                             Map<String, Object> attributes) {
        this.userId = userId;
        this.email = email;
        this.authorities = authorities;
        this.attributes = attributes;
    }

    public UUID getUserId() {
        return userId;
    }

    @Override
    public String getName() {
        return email;
    }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return authorities;
    }

    @Override
    public Map<String, Object> getAttributes() {
        return attributes;
    }
}
