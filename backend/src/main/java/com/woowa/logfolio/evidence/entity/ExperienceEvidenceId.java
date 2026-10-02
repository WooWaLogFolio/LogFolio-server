package com.woowa.logfolio.evidence.entity;

import java.io.Serializable;
import java.util.Objects;
import java.util.UUID;

public class ExperienceEvidenceId implements Serializable {
    private UUID experienceId;
    private UUID evidenceItemId;
    private String sectionType;

    public ExperienceEvidenceId() {}

    @Override
    public boolean equals(Object value) {
        if (this == value) return true;
        if (!(value instanceof ExperienceEvidenceId other)) return false;
        return Objects.equals(experienceId, other.experienceId)
                && Objects.equals(evidenceItemId, other.evidenceItemId)
                && Objects.equals(sectionType, other.sectionType);
    }

    @Override
    public int hashCode() { return Objects.hash(experienceId, evidenceItemId, sectionType); }
}
