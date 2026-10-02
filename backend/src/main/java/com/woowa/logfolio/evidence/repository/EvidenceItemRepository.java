package com.woowa.logfolio.evidence.repository;
import com.woowa.logfolio.evidence.entity.EvidenceItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
public interface EvidenceItemRepository extends JpaRepository<EvidenceItem, UUID> {
    Optional<EvidenceItem> findByIdAndProjectUserId(UUID id, UUID userId);
    @Query(value = "select ei.* from evidence_items ei join experience_evidence ee on ee.evidence_item_id = ei.id " +
            "join experiences e on e.id = ee.experience_id join projects p on p.id = e.project_id " +
            "where ee.experience_id = :experienceId and p.user_id = :userId order by ei.created_at", nativeQuery = true)
    List<EvidenceItem> findAllForExperience(UUID experienceId, UUID userId);
}
