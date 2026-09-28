package com.woowa.logfolio.review.repository;
import com.woowa.logfolio.review.entity.GapAnswer;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;
public interface GapAnswerRepository extends JpaRepository<GapAnswer, UUID> {
    List<GapAnswer> findAllByQuestionIdAndUserIdOrderByCreatedAt(UUID questionId, UUID userId);
}
