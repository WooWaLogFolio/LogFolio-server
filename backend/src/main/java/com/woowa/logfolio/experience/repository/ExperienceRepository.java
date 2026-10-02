package com.woowa.logfolio.experience.repository;
import com.woowa.logfolio.experience.entity.Experience;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
public interface ExperienceRepository extends JpaRepository<Experience, UUID> {
    List<Experience> findAllByProjectIdAndProjectUserIdAndDeletedAtIsNullOrderByUpdatedAtDesc(UUID projectId, UUID userId);
    Optional<Experience> findByIdAndProjectUserIdAndDeletedAtIsNull(UUID id, UUID userId);
    boolean existsByCandidateId(UUID candidateId);
    long countByProjectUserIdAndDeletedAtIsNull(UUID userId);
    long countByProjectIdAndDeletedAtIsNull(UUID projectId);
}
