from logfolio_ai.main import app


def schema_ref(operation: dict, status_code: str) -> str:
    return operation["responses"][status_code]["content"]["application/json"][
        "schema"
    ]["$ref"]


def test_openapi_exposes_spring_fastapi_success_contracts() -> None:
    schema = app.openapi()
    paths = schema["paths"]

    assert set(paths) == {
        "/health",
        "/api/v1/analyses",
        "/api/v1/sources/index",
        "/api/v1/projects/{project_id}/sources/{source_id}/index",
    }
    assert schema_ref(paths["/api/v1/analyses"]["post"], "200") == (
        "#/components/schemas/AnalysisResponse"
    )
    assert schema_ref(paths["/api/v1/sources/index"]["post"], "200") == (
        "#/components/schemas/SourceIndexResponse"
    )
    assert paths[
        "/api/v1/projects/{project_id}/sources/{source_id}/index"
    ]["delete"]["responses"]["204"]["description"] == "Successful Response"


def test_openapi_exposes_shared_error_contract_for_internal_routes() -> None:
    paths = app.openapi()["paths"]
    operations = [
        paths["/api/v1/analyses"]["post"],
        paths["/api/v1/sources/index"]["post"],
        paths["/api/v1/projects/{project_id}/sources/{source_id}/index"]["delete"],
    ]

    for operation in operations:
        for status_code in ("401", "422", "500", "502", "504"):
            assert schema_ref(operation, status_code) == (
                "#/components/schemas/ErrorResponse"
            )


def test_openapi_freezes_shared_enum_values_and_limits() -> None:
    components = app.openapi()["components"]["schemas"]

    assert components["SourceType"]["enum"] == ["PROJECT_FILE", "QUICK_LOG"]
    assert components["AnalysisResultType"]["enum"] == [
        "EXISTING_UPDATE",
        "NEW_EXPERIENCE",
        "NEEDS_CONTEXT",
        "NO_UPDATE",
    ]
    assert components["InformationNeedType"]["enum"] == [
        "USER_ANSWER",
        "ADDITIONAL_SOURCE",
    ]
    assert components["AnalysisRequest"]["properties"]["documents"][
        "maxItems"
    ] == 3
    assert components["AnalysisResponse"]["properties"]["candidates"][
        "maxItems"
    ] == 3
    assert components["AnalysisResponse"]["properties"]["questions"][
        "maxItems"
    ] == 2


def test_openapi_uses_camel_case_contract_fields() -> None:
    components = app.openapi()["components"]["schemas"]

    request_fields = set(components["AnalysisRequest"]["properties"])
    response_fields = set(components["AnalysisResponse"]["properties"])
    error_fields = set(components["ErrorResponse"]["properties"])

    assert {"analysisRunId", "projectId", "sourceIds"} <= request_fields
    assert {"inputSourceIds", "resultTypes", "aiUsage"} <= response_fields
    assert "aiUsage" in error_fields
    assert not any("_" in field for field in request_fields | response_fields)
