package com.woowa.logfolio.review.repository;
import com.woowa.logfolio.review.entity.ReviewSession;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;
import java.util.List;
import java.time.LocalDateTime;
import java.util.UUID;
public interface ReviewSessionRepository extends JpaRepository<ReviewSession, UUID> {
    Optional<ReviewSession> findByIdAndProjectUserId(UUID id, UUID userId);
    List<ReviewSession> findAllByStatusAndStartedAtBefore(String status, LocalDateTime startedBefore);
}
