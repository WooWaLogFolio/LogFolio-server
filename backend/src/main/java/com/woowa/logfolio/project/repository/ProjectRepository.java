package com.woowa.logfolio.project.repository;

import com.woowa.logfolio.project.entity.Project;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ProjectRepository extends JpaRepository<Project, UUID> {

    Optional<Project> findByIdAndDeletedAtIsNull(UUID id);

    List<Project> findAllByUserIdAndDeletedAtIsNullOrderByCreatedAtDesc(UUID userId);
}
