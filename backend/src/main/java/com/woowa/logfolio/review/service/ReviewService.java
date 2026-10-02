package com.woowa.logfolio.review.service;

import com.woowa.logfolio.experience.entity.Experience;
import com.woowa.logfolio.experience.service.ExperienceService;
import com.woowa.logfolio.review.entity.*;
import com.woowa.logfolio.review.repository.*;
import com.woowa.logfolio.user.entity.User;
import com.woowa.logfolio.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ReviewService {
    private final ReviewSessionRepository sessionRepository;
    private final ReviewItemRepository itemRepository;
    private final GapQuestionRepository questionRepository;
    private final GapAnswerRepository answerRepository;
    private final ExperienceService experienceService;
    private final UserService userService;

    @Transactional
    public SessionResponse startRefinement(UUID userId, UUID experienceId) {
        Experience experience = experienceService.findOwned(userId, experienceId);
        return sessionResponse(sessionRepository.save(new ReviewSession(experience.getProject(), null)));
    }

    public SessionResponse session(UUID userId, UUID sessionId) {
        return sessionResponse(findSession(userId, sessionId));
    }

    @Transactional
    public ReviewItemResponse decide(UUID userId, UUID itemId, String decision, String confirmedContent) {
        if (!List.of("APPROVED", "EDITED", "REJECTED").contains(decision)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "지원하지 않는 검토 결정입니다.");
        }
        ReviewItem item = itemRepository.findByIdAndReviewSessionProjectUserId(itemId, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "검토 항목을 찾을 수 없습니다."));
        item.decide(decision, confirmedContent);
        return ReviewItemResponse.from(item);
    }

    @Transactional
    public SessionResponse complete(UUID userId, UUID sessionId) {
        ReviewSession session = findSession(userId, sessionId);
        session.complete();
        return sessionResponse(session);
    }

    public List<QuestionResponse> questions(UUID userId, UUID experienceId) {
        experienceService.findOwned(userId, experienceId);
        return questionRepository.findAllByExperienceIdAndExperienceProjectUserIdOrderByDisplayOrder(experienceId, userId)
                .stream().map(question -> questionResponse(question, userId)).toList();
    }

    @Transactional
    public AnswerResponse answer(UUID userId, UUID questionId, String answer, String answerType) {
        GapQuestion question = questionRepository.findByIdAndExperienceProjectUserId(questionId, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "보완 질문을 찾을 수 없습니다."));
        User user = userService.findActiveUser(userId);
        return AnswerResponse.from(answerRepository.save(new GapAnswer(question, user, answer, answerType)));
    }

    private ReviewSession findSession(UUID userId, UUID id) {
        return sessionRepository.findByIdAndProjectUserId(id, userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "검토 세션을 찾을 수 없습니다."));
    }
    private SessionResponse sessionResponse(ReviewSession session) {
        List<ReviewItemResponse> items = itemRepository.findAllByReviewSessionIdOrderByDisplayOrder(session.getId())
                .stream().map(ReviewItemResponse::from).toList();
        return new SessionResponse(session.getId(), session.getProject().getId(), session.getStatus(),
                session.getStartedAt(), session.getCompletedAt(), items);
    }
    private QuestionResponse questionResponse(GapQuestion question, UUID userId) {
        List<AnswerResponse> answers = answerRepository.findAllByQuestionIdAndUserIdOrderByCreatedAt(question.getId(), userId)
                .stream().map(AnswerResponse::from).toList();
        return new QuestionResponse(question.getId(), question.getTargetSection(), question.getQuestion(),
                question.getSuggestedAnswers(), question.getDisplayOrder(), answers);
    }

    public record SessionResponse(UUID id, UUID projectId, String status, LocalDateTime startedAt,
                                  LocalDateTime completedAt, List<ReviewItemResponse> items) {}
    public record ReviewItemResponse(UUID id, String itemType, String proposedContent, String confirmedContent,
                                     String decision, int displayOrder) {
        static ReviewItemResponse from(ReviewItem item) {
            return new ReviewItemResponse(item.getId(), item.getItemType(), item.getProposedContent(),
                    item.getConfirmedContent(), item.getDecision(), item.getDisplayOrder());
        }
    }
    public record QuestionResponse(UUID id, String targetSection, String question, List<String> suggestedAnswers,
                                   int displayOrder, List<AnswerResponse> answers) {}
    public record AnswerResponse(UUID id, String answer, String answerType, LocalDateTime createdAt) {
        static AnswerResponse from(GapAnswer answer) {
            return new AnswerResponse(answer.getId(), answer.getAnswer(), answer.getAnswerType(), answer.getCreatedAt());
        }
    }
}
