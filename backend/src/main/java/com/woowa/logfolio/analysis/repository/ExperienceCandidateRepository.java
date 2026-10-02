package com.woowa.logfolio.analysis.repository;
import com.woowa.logfolio.analysis.entity.ExperienceCandidate;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
public interface ExperienceCandidateRepository extends JpaRepository<ExperienceCandidate, UUID> {
    List<ExperienceCandidate> findAllByAnalysisRunIdOrderByCreatedAt(UUID runId);
    Optional<ExperienceCandidate> findByIdAndAnalysisRunProjectUserId(UUID id, UUID userId);
}
