# LogFolio AI Server

선택된 기록을 바탕으로 보완 질문을 만들고, 사용자 답변을 경험 카드 형태로 구조화하는 FastAPI 서버입니다.

현재 단계에서는 Spring Boot 서버와 API 연동을 먼저 확인할 수 있도록 임시 응답을 반환합니다. 실제 OpenAI 연동은 `app/services/ai_service.py` 내부 구현으로 교체합니다.

## 로컬 실행

```powershell
cd ai-server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

- 상태 확인: <http://localhost:8000/health>
- Swagger API 문서: <http://localhost:8000/docs>
- ReDoc 문서: <http://localhost:8000/redoc>

## 테스트

```powershell
pytest
```

## 환경변수

`.env.example`을 복사하여 `.env`를 만든 뒤 실제 값을 입력합니다. `.env`는 Git에 커밋하지 않습니다.

```powershell
Copy-Item .env.example .env
```

## API

- `GET /health`: 서버 상태 확인
- `POST /api/v1/ai/generate-questions`: 선택 기록 기반 보완 질문 생성
- `POST /api/v1/ai/generate-card`: 기록과 문답 기반 경험 카드 구조화

## Spring Boot 연동 시 합의할 항목

- `record.id`를 문자열로 전달
- 요청당 기록 개수는 1~20개
- 질문은 최대 2개 반환
- AI 호출 타임아웃과 재시도 정책
- 내부 서버 간 인증 방식
