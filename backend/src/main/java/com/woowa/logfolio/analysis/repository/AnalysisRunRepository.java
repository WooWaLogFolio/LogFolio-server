package com.woowa.logfolio.analysis.repository;
import com.woowa.logfolio.analysis.entity.AnalysisRun;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.data.domain.Pageable;
import java.util.Optional;
import java.util.List;
import java.util.UUID;
public interface AnalysisRunRepository extends JpaRepository<AnalysisRun, UUID> {
    Optional<AnalysisRun> findByIdAndProjectUserId(UUID id, UUID userId);
    Optional<AnalysisRun> findFirstByProjectIdAndProjectUserIdOrderByCreatedAtDesc(UUID projectId, UUID userId);
    List<AnalysisRun> findAllByProjectIdAndProjectUserIdOrderByCreatedAtDesc(UUID projectId, UUID userId);
    @Query("select run.id as id, run.project.user.id as userId from AnalysisRun run " +
            "where run.status = :status order by run.createdAt asc")
    List<QueuedRun> findQueuedRuns(@Param("status") String status, Pageable pageable);
    @Modifying
    @Query("update AnalysisRun run set run.status = 'PROCESSING', run.startedAt = CURRENT_TIMESTAMP, run.modelVersion = 'ai-server' where run.id = :runId and run.status = 'QUEUED'")
    int claimQueuedRun(@Param("runId") UUID runId);
    interface QueuedRun {
        UUID getId();
        UUID getUserId();
    }
}
