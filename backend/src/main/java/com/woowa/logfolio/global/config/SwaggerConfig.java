package com.woowa.logfolio.global.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {

    @Bean
    public OpenAPI logfolioOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("LogFolio API")
                        .description("LogFolio API 문서입니다. OAuth2 로그인 후 JSESSIONID 쿠키와, "
                                + "상태 변경 요청에는 /api/auth/csrf에서 받은 X-XSRF-TOKEN을 함께 전송하세요. "
                                + "소셜 공급자가 이메일을 제공하지 않으면 /api/auth/oauth2/pending-signup 조회 후 "
                                + "/api/auth/oauth2/complete-signup으로 가입을 완료합니다.")
                        .version("v1"))
                .components(new Components().addSecuritySchemes("sessionCookie",
                        new SecurityScheme()
                                .type(SecurityScheme.Type.APIKEY)
                                .in(SecurityScheme.In.COOKIE)
                                .name("JSESSIONID")
                                .description("OAuth2 로그인으로 발급되는 세션 쿠키")));
    }
}
