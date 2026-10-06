# LogFolio

프로젝트 자료와 사용자의 답변을 근거로 경험을 발견하고, 검토 가능한 경험카드로 정리하는 서비스입니다.

## Repository structure

- `backend`: 사용자, 프로젝트, 파일, 검토 흐름과 최종 저장을 담당하는 Spring Boot 서버
- `ai-server`: 문서 검색, AI 분석, 경험 후보 및 질문 생성을 담당하는 FastAPI 서버
- `frontend`: 사용자 화면

## AI processing flow

```text
Frontend
→ Spring Boot
→ FastAPI
→ 문서 Chunk 분리
→ Embedding 생성
→ PostgreSQL/pgvector 저장 및 검색
→ 외부 LLM에 검색 근거 전달
→ Claim·Evidence·경험 후보·질문 생성
→ AI Policy 검증
→ Spring Boot
→ 사용자 검토
→ 승인된 결과만 최종 저장
```

Spring Boot는 인증, 권한, 파일 저장과 텍스트 추출, 서비스 데이터 및 최종 결과 저장을 담당합니다. FastAPI는 AI 처리 순서를 관리하고, 검색된 근거를 바탕으로 AI 초안을 생성·검증합니다.

AI 서버의 상세 설계는 [`ai-server/README.md`](ai-server/README.md)를 참고합니다.

- 앞으로의 AI 모델·Spring·전체 연동 작업: [`ai-server/docs/ai-model-spring-e2e-roadmap.md`](ai-server/docs/ai-model-spring-e2e-roadmap.md)
- 로컬·Docker·Gemini·Spring 테스트 명령: [`ai-server/docs/testing-runbook.md`](ai-server/docs/testing-runbook.md)

## Shared API contract

- ID: UUID 문자열
- JSON 필드명: camelCase
- 파일 저장: Spring Boot/S3
- 파일 텍스트 추출: Spring Boot
- AI 분석: FastAPI
- 분석 요청 추적: `analysisRunId`
- 요청당 파일: 최대 3개
- AI 질문: 최대 2개
- 경험 후보: 최대 3개
- FastAPI 타임아웃: 30초
- Spring 자동 재시도: 최대 1회
- AI 결과: 사용자 검토 후 확정 저장

ERD에 존재하는 필드와 상태값은 Spring의 정의를 따릅니다. ERD에 없는 AI 전용 필드와 Enum은 AI 서버 계약에서 정의하고 Spring과 동일한 문자열로 공유합니다.

## Branch strategy

- `main`: 최종 배포 전 검증이 끝난 안정 버전
- `develop`: Spring 담당자의 최신 MVP 기준 브랜치
- `integration/next`: MVP 이후 기능을 미리 통합하고 검증하는 브랜치
- `feature/*`: 이슈 단위 기능 개발 브랜치

AI 개발은 항상 최신 `develop`을 확인하고 그 변경을 현재 AI 기능 브랜치에 반영한 뒤 진행합니다. 완성된 AI 기능은 `integration/next`에서 먼저 통합하며, 별도 합의 전에는 `develop`이나 `main`에 병합하지 않습니다.

## Current AI MVP scope

- 프로젝트 자료 기반 Claim 및 Evidence 생성
- 의미 있는 경험 후보 최대 3개 생성
- 자료로 답할 수 없는 보완 질문 최대 2개 생성
- 팀 활동과 사용자 개인 기여 구분
- 근거 없는 성과, 직책 및 개인 기여 차단
- 사용자 승인·수정·거절을 거친 후 결과 확정

다음 항목은 현재 MVP 범위에서 제외합니다.

- Agentic RAG
- GraphRAG
- Fine-tuning
- 로컬 LLM 배포
- Reranker 및 Hybrid Search
- 복잡한 벡터 검색 최적화
