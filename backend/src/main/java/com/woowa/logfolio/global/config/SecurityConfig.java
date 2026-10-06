package com.woowa.logfolio.global.config;

import com.woowa.logfolio.auth.service.CustomOAuth2UserService;
import com.woowa.logfolio.auth.model.PendingOAuth2User;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.SimpleUrlAuthenticationSuccessHandler;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.security.web.authentication.logout.HttpStatusReturningLogoutSuccessHandler;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

import static org.springframework.http.HttpStatus.NO_CONTENT;

@Configuration
@RequiredArgsConstructor
public class SecurityConfig {

    private final CustomOAuth2UserService customOAuth2UserService;

    @Bean
    SecurityFilterChain securityFilterChain(
            HttpSecurity http,
            @Value("${app.oauth2.success-redirect-uri}") String successRedirectUri,
            @Value("${app.oauth2.signup-redirect-uri}") String signupRedirectUri) throws Exception {
        SimpleUrlAuthenticationSuccessHandler signedInHandler =
                new SimpleUrlAuthenticationSuccessHandler(successRedirectUri);
        SimpleUrlAuthenticationSuccessHandler pendingSignupHandler =
                new SimpleUrlAuthenticationSuccessHandler(signupRedirectUri);
        AuthenticationSuccessHandler successHandler = (request, response, authentication) -> {
            if (authentication.getPrincipal() instanceof PendingOAuth2User) {
                pendingSignupHandler.onAuthenticationSuccess(request, response, authentication);
            } else {
                signedInHandler.onAuthenticationSuccess(request, response, authentication);
            }
        };

        http
                .cors(Customizer.withDefaults())
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(
                                "/oauth2/**", "/login/**", "/api/auth/login/**", "/error",
                                "/api/auth/signup", "/api/auth/password-reset/**",
                                "/swagger-ui/**", "/swagger-ui.html", "/v3/api-docs/**", "/actuator/health")
                        .permitAll()
                        .requestMatchers(
                                "/api/auth/oauth2/pending-signup",
                                "/api/auth/oauth2/complete-signup")
                        .hasRole("OAUTH2_PENDING")
                        .requestMatchers("/api/auth/csrf", "/api/auth/logout")
                        .authenticated()
                        .anyRequest().hasRole("USER"))
                .csrf(csrf -> csrf
                        .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse())
                        .ignoringRequestMatchers("/api/auth/login", "/api/auth/signup", "/api/auth/password-reset/**"))
                .oauth2Login(oauth -> oauth
                        .userInfoEndpoint(userInfo -> userInfo.userService(customOAuth2UserService))
                        .successHandler(successHandler))
                .logout(logout -> logout
                        .logoutUrl("/api/auth/logout")
                        .logoutSuccessHandler(new HttpStatusReturningLogoutSuccessHandler(NO_CONTENT)));

        return http.build();
    }

    @Bean
    CorsConfigurationSource corsConfigurationSource(
            @Value("${app.cors.allowed-origins}") List<String> allowedOrigins) {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOrigins(allowedOrigins);
        configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of("Content-Type", "X-XSRF-TOKEN"));
        configuration.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
