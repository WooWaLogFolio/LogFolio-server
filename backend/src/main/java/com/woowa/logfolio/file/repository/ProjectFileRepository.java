package com.woowa.logfolio.file.repository;

import com.woowa.logfolio.file.entity.ProjectFile;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ProjectFileRepository extends JpaRepository<ProjectFile, UUID> {
    List<ProjectFile> findAllByProjectIdAndUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(UUID projectId, UUID userId);
    List<ProjectFile> findAllByUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(UUID userId);
    Optional<ProjectFile> findByIdAndUserIdAndDeletedAtIsNull(UUID id, UUID userId);

    @Query("select coalesce(sum(f.sizeBytes), 0) from ProjectFile f where f.user.id = :userId and f.deletedAt is null")
    long sumActiveSizeByUserId(UUID userId);
}
