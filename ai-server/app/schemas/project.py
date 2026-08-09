from pydantic import BaseModel, ConfigDict, Field


class ProjectPeriod(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")


class ProjectInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    period: ProjectPeriod | None = None
    category: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=10_000)


class DocumentInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    id: str
    file_name: str = Field(alias="fileName", min_length=1, max_length=255)
    extracted_text: str = Field(alias="extractedText", min_length=1, max_length=50_000)


class StructureProjectRequest(BaseModel):
    project: ProjectInput
    documents: list[DocumentInput] = Field(default_factory=list, max_length=10)


class StructuredProject(BaseModel):
    summary: str
    role: str | None = None
    problems: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    collaboration: str | None = None
    results: list[str] = Field(default_factory=list)
    learnings: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class StructureProjectResponse(BaseModel):
    structured_project: StructuredProject = Field(serialization_alias="structuredProject")
    missing_contexts: list[str] = Field(serialization_alias="missingContexts")
    warnings: list[str] = Field(default_factory=list)
