package com.woowa.logfolio.analysis.repository;
import com.woowa.logfolio.analysis.entity.AnalysisRun;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.Optional;
import java.util.List;
import java.util.UUID;
public interface AnalysisRunRepository extends JpaRepository<AnalysisRun, UUID> {
    Optional<AnalysisRun> findByIdAndProjectUserId(UUID id, UUID userId);
    Optional<AnalysisRun> findFirstByProjectIdAndProjectUserIdOrderByCreatedAtDesc(UUID projectId, UUID userId);
    List<AnalysisRun> findAllByProjectIdAndProjectUserIdOrderByCreatedAtDesc(UUID projectId, UUID userId);
    List<AnalysisRun> findTop100ByStatusOrderByCreatedAtAsc(String status);
    @Modifying
    @Query("update AnalysisRun run set run.status = 'PROCESSING', run.startedAt = CURRENT_TIMESTAMP, run.modelVersion = 'ai-server' where run.id = :runId and run.status = 'QUEUED'")
    int claimQueuedRun(@Param("runId") UUID runId);
}
