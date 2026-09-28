package com.woowa.logfolio.global.response;

import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.Map;

@Schema(description = "공통 오류 응답")
public record ApiError(
        int status,
        String code,
        String message,
        String path,
        Instant timestamp,
        Map<String, String> fieldErrors
) {}
