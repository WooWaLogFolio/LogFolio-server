package com.woowa.logfolio.evidence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;

import java.util.UUID;

@Entity
@Table(name = "experience_evidence")
@IdClass(ExperienceEvidenceId.class)
public class ExperienceEvidence {
    @Id @Column(name = "experience_id", nullable = false) private UUID experienceId;
    @Id @Column(name = "evidence_item_id", nullable = false) private UUID evidenceItemId;
    @Id @Column(name = "section_type", nullable = false, length = 30) private String sectionType;

    protected ExperienceEvidence() {}
}
