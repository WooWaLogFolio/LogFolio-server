package com.woowa.logfolio.quicklog.repository;

import com.woowa.logfolio.quicklog.entity.QuickLog;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface QuickLogRepository extends JpaRepository<QuickLog, UUID> {
    Optional<QuickLog> findByIdAndUserIdAndDeletedAtIsNull(UUID id, UUID userId);
    Page<QuickLog> findAllByUserIdAndDeletedAtIsNull(UUID userId, Pageable pageable);
    Page<QuickLog> findAllByUserIdAndProjectIdAndDeletedAtIsNull(UUID userId, UUID projectId, Pageable pageable);
    long countByUserIdAndDeletedAtIsNull(UUID userId);
}
