package com.woowa.logfolio.review.repository;
import com.woowa.logfolio.review.entity.ReviewSession;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;
import java.util.UUID;
public interface ReviewSessionRepository extends JpaRepository<ReviewSession, UUID> {
    Optional<ReviewSession> findByIdAndProjectUserId(UUID id, UUID userId);
}
