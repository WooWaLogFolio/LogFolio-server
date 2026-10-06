package com.woowa.logfolio.analysis.repository;
import com.woowa.logfolio.analysis.entity.AnalysisRun;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;
import java.util.List;
import java.util.UUID;
public interface AnalysisRunRepository extends JpaRepository<AnalysisRun, UUID> {
    Optional<AnalysisRun> findByIdAndProjectUserId(UUID id, UUID userId);
    Optional<AnalysisRun> findFirstByProjectIdAndProjectUserIdOrderByCreatedAtDesc(UUID projectId, UUID userId);
    List<AnalysisRun> findAllByProjectIdAndProjectUserIdOrderByCreatedAtDesc(UUID projectId, UUID userId);
}
