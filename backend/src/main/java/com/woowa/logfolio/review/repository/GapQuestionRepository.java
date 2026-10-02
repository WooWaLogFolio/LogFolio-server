package com.woowa.logfolio.review.repository;
import com.woowa.logfolio.review.entity.GapQuestion;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
public interface GapQuestionRepository extends JpaRepository<GapQuestion, UUID> {
    List<GapQuestion> findAllByExperienceIdAndExperienceProjectUserIdOrderByDisplayOrder(UUID experienceId, UUID userId);
    Optional<GapQuestion> findByIdAndExperienceProjectUserId(UUID id, UUID userId);
}
