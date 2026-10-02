package com.woowa.logfolio.review.repository;
import com.woowa.logfolio.review.entity.ReviewItem;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
public interface ReviewItemRepository extends JpaRepository<ReviewItem, UUID> {
    List<ReviewItem> findAllByReviewSessionIdOrderByDisplayOrder(UUID sessionId);
    Optional<ReviewItem> findByIdAndReviewSessionProjectUserId(UUID id, UUID userId);
}
