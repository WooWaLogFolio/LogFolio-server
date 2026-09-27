package com.woowa.logfolio.review.controller;

import com.woowa.logfolio.auth.model.LogfolioOAuth2User;
import com.woowa.logfolio.review.service.ReviewService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Tag(name = "Review", description = "AI 다듬기, 검토 항목, 보완 질문 API")
@SecurityRequirement(name = "sessionCookie")
public class ReviewController {
    private final ReviewService service;

    @PostMapping("/experiences/{experienceId}/review-sessions")
    @ResponseStatus(HttpStatus.ACCEPTED)
    @Operation(summary = "경험 카드 AI 다듬기 요청")
    public ReviewService.SessionResponse start(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                               @PathVariable UUID experienceId) {
        return service.startRefinement(principal.getUserId(), experienceId);
    }

    @GetMapping("/review-sessions/{sessionId}")
    @Operation(summary = "다듬기 진행 상태와 검토 항목 조회")
    public ReviewService.SessionResponse session(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                 @PathVariable UUID sessionId) {
        return service.session(principal.getUserId(), sessionId);
    }

    @PutMapping("/review-items/{itemId}")
    @Operation(summary = "AI 제안 승인·직접 수정·거절")
    public ReviewService.ReviewItemResponse decide(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                   @PathVariable UUID itemId,
                                                   @RequestBody DecisionRequest body) {
        return service.decide(principal.getUserId(), itemId, body.decision(), body.confirmedContent());
    }

    @PostMapping("/review-sessions/{sessionId}/complete")
    @Operation(summary = "다듬기 검토 완료")
    public ReviewService.SessionResponse complete(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                  @PathVariable UUID sessionId) {
        return service.complete(principal.getUserId(), sessionId);
    }

    @GetMapping("/experiences/{experienceId}/gap-questions")
    @Operation(summary = "경험 카드 보완 질문 조회")
    public List<ReviewService.QuestionResponse> questions(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                                          @PathVariable UUID experienceId) {
        return service.questions(principal.getUserId(), experienceId);
    }

    @PostMapping("/gap-questions/{questionId}/answers")
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "보완 질문 답변 저장")
    public ReviewService.AnswerResponse answer(@AuthenticationPrincipal LogfolioOAuth2User principal,
                                               @PathVariable UUID questionId,
                                               @Valid @RequestBody AnswerRequest body) {
        return service.answer(principal.getUserId(), questionId, body.answer(), body.answerType());
    }

    public record DecisionRequest(@NotBlank String decision, String confirmedContent) {}
    public record AnswerRequest(String answer, @NotBlank String answerType) {}
}
