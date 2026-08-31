package com.woowa.logfolio.global.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {

    @Bean
    public OpenAPI logfolioOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("LogFolio API")
                        .description("LogFolio 사용자 및 프로젝트 API 문서")
                        .version("v1"));
    }
}
