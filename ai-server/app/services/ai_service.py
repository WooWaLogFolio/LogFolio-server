from app.schemas.models import (
    ContextType,
    ExperienceCard,
    GeneratedQuestion,
    GenerateCardRequest,
    GenerateCardResponse,
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
)
from app.schemas.project import (
    StructureProjectRequest,
    StructureProjectResponse,
    StructuredProject,
)


class AIService:
    """API 연동 확인을 위한 임시 서비스입니다.

    Spring Boot와 요청·응답 규격을 합의한 후 이 메서드 내부를
    OpenAI Structured Output 호출로 교체합니다.
    """

    async def structure_project(
        self, request: StructureProjectRequest
    ) -> StructureProjectResponse:
        evidence = [document.file_name for document in request.documents]
        return StructureProjectResponse(
            structured_project=StructuredProject(
                summary=request.project.description,
                evidence=evidence,
            ),
            missing_contexts=[
                "role",
                "problem",
                "action",
                "collaboration",
                "result",
                "learning",
            ],
            warnings=[
                "현재 응답은 API 연동 확인용 임시 결과입니다.",
                "입력 자료에서 확인되지 않은 성과는 생성하지 않았습니다.",
            ],
        )

    async def generate_questions(
        self, request: GenerateQuestionsRequest
    ) -> GenerateQuestionsResponse:
        del request
        return GenerateQuestionsResponse(
            questions=[
                GeneratedQuestion(
                    context_type=ContextType.ROLE,
                    question="이 경험에서 본인이 직접 담당한 역할은 무엇인가요?",
                ),
                GeneratedQuestion(
                    context_type=ContextType.RESULT,
                    question="실행한 행동으로 어떤 변화나 결과가 발생했나요?",
                ),
            ]
        )

    async def generate_card(self, request: GenerateCardRequest) -> GenerateCardResponse:
        first_record = request.records[0]
        return GenerateCardResponse(
            card=ExperienceCard(
                title=f"{first_record.category or '프로젝트'} 경험",
                actions=[record.content for record in request.records],
                missing_contexts=["role", "problem", "result", "learning"],
            )
        )


ai_service = AIService()
