# LogFolio AI Server

LogFolio AI Server는 사용자가 프로젝트에 쌓은 파일과 Quick Log에서 경험을 발견하고, 기존 경험과 비교해 근거와 함께 제안하는 AI 분석 서버입니다.

단순히 자연스러운 포트폴리오 문장을 생성하는 것이 아니라, 문서에 실제로 존재하는 내용과 사용자가 직접 기여한 내용을 구분합니다. AI가 만든 결과는 초안으로 제공되며 사용자의 검토를 거친 뒤에만 최종 경험카드로 저장됩니다.

> 현재 이 디렉터리는 Spring 연동 계약, 교체 가능한 LLM·Embedding Provider, RAG, AI Policy 검증과 Docker 기반 통합 검증 환경을 포함합니다.

## Why this server exists

프로젝트 자료에는 회의 기록, 기획서, 발표 자료와 결과 보고서처럼 서로 다른 정보가 섞여 있습니다. 이 자료만으로 사용자의 역할이나 개인 성과를 단정하면 팀 활동이 개인 활동으로 잘못 기록될 수 있습니다.

LogFolio AI Server는 다음 원칙으로 이 문제를 다룹니다.

- 업로드 자료에서 관련 근거를 먼저 검색합니다.
- 자료에 명시된 사실과 AI의 추정을 구분합니다.
- 팀 활동을 사용자의 개인 기여로 자동 귀속하지 않습니다.
- 근거가 부족한 내용은 단정하지 않고 사용자에게 질문합니다.
- AI 결과를 바로 확정하지 않고 승인, 수정 또는 거절할 수 있게 합니다.

## System architecture

```text
Client
  → Spring Boot API
      → FastAPI AI Server
          → Chunking
          → Local Embedding Model
          → PostgreSQL + pgvector
          → RAG Retrieval
          → External LLM
          → Claim/Evidence Policy Validation
      → Spring Boot API
  → User Review
  → Confirmed Experience Card
```

각 서버의 책임은 다음과 같이 구분합니다.

### Spring Boot

- 사용자 인증과 프로젝트 접근 권한 확인
- 파일 업로드 및 S3 저장
- 업로드 파일의 텍스트 추출
- 프로젝트와 검토 상태 관리
- 사용자가 확정한 경험카드 저장

### FastAPI AI Server

- 추출된 문서 텍스트를 검색 가능한 단위로 분할
- 문서 조각의 Embedding 생성 및 검색
- 외부 LLM을 이용한 구조화된 분석
- Claim과 Evidence 연결
- 경험 후보와 보완 질문 생성
- 근거 및 AI Policy 검증

FastAPI는 사용자 파일의 원본 저장이나 로그인 처리를 담당하지 않습니다. Spring이 권한을 검증한 내부 요청만 처리합니다.

## How an analysis works

### 1. Index a Source automatically

Spring이 Project File 또는 Quick Log를 저장하면 텍스트와 Source 식별자를 `/api/v1/sources/index`로 전달합니다. FastAPI는 이때 Chunking과 Embedding을 수행하지만 LLM 분석은 실행하지 않습니다. 일부 Source가 실패해도 성공한 Source는 검색 가능한 상태로 유지합니다.

Spring에서 Source 삭제가 확정되면 `/api/v1/projects/{projectId}/sources/{sourceId}/index`를 `DELETE`로 호출해 해당 Source의 검색 Chunk만 제거합니다. 이 호출은 Spring DB, S3 원본, Evidence 또는 사용자 확정 Experience를 변경하지 않습니다.

사용자가 `AI 분석하기`를 선택하면 Spring이 별도의 `/api/v1/analyses` 요청을 보냅니다. 분석 요청은 `analysisRunId`로 추적하며, 새 Source ID와 현재 프로젝트의 기존 Experience 요약·Claim·Evidence 메타데이터를 함께 전달합니다. 이미 인덱싱한 Source는 다시 전처리하지 않습니다.

FastAPI는 새 Source와 기존 Experience의 제목·요약·Claim을 먼저 의미 비교합니다. 관련성이 확인된 Experience만 기존 Evidence의 정확한 Chunk를 추가 조회하고, 새 Source와 기존 원문을 함께 LLM에 전달합니다. 관련성 기준을 통과하지 못한 Experience는 보강 대상으로 강제 연결하지 않습니다.

### 2. Build searchable document chunks

FastAPI는 긴 문서를 섹션, 문단, 문장 경계를 고려해 작은 Chunk로 나눕니다. 각 Chunk에는 원문을 다시 확인할 수 있도록 다음 정보를 유지합니다.

- 프로젝트 ID
- Source ID와 Source Type (`PROJECT_FILE` 또는 `QUICK_LOG`)
- Chunk ID와 문서 내 순서
- 페이지 또는 원문 위치
- 문서 및 섹션 제목
- 원문 텍스트

초기 구현은 페이지 경계를 넘어서 Chunk를 합치지 않으며, 기본 크기 700단위와 Overlap 100단위로 시작합니다. 현재 단위 계산은 모델별 토크나이저가 아닌 가벼운 결정적 추정 방식이므로 실제 검색 품질 평가에 따라 조정합니다. 같은 Source ID·Type과 같은 원문에는 동일한 Chunk ID를 생성하여 재시도 시 중복을 줄입니다.

완전히 동일한 Source의 재업로드는 `contentHash`(SHA-256)로 판별합니다. 같은 프로젝트에 이미 동일 해시가 있으면 다시 Chunking·Embedding하지 않고 `DUPLICATE`와 기존 Source ID를 반환합니다. 비슷한 문서나 수정본을 자동 병합하는 기능은 MVP 범위가 아닙니다.

### 3. Create embeddings

각 Chunk는 로컬 Embedding 모델을 통해 의미를 나타내는 벡터로 변환됩니다. 초기 후보 모델은 한국어를 포함한 다국어 검색을 지원하는 `intfloat/multilingual-e5-base`입니다.

Embedding 모델은 답변을 작성하지 않습니다. 서로 다른 표현을 사용하더라도 의미가 비슷한 문서 조각을 찾는 데 사용됩니다.

Embedding도 교체 가능한 Provider로 분리합니다. 로컬·계약 테스트에서는 작은 결정적 Fake 벡터를 사용하고, 실제 검색 품질 검증에서는 E5를 사용합니다. E5에는 저장 문서에 `passage:`를, 검색 문장에 `query:`를 붙이고 Cosine 검색에 맞게 벡터를 정규화합니다.

### 4. Retrieve evidence with RAG

벡터와 원문 Chunk는 PostgreSQL의 pgvector 확장에 저장됩니다. 분석할 때는 목적에 맞는 Query를 만들고, 현재 프로젝트 안에서 의미가 가까운 Chunk를 검색합니다.

AI 전용 원문 조각과 벡터는 `ai_document_chunks` 테이블에서 관리합니다. Spring 소유 테이블은 FastAPI 마이그레이션이 변경하지 않습니다. Spring이 프로젝트 접근 권한을 먼저 확인하고, FastAPI 검색은 다시 `projectId`를 필수 조건으로 사용합니다. 파일 또는 프로젝트가 삭제될 때는 해당 범위의 Chunk도 함께 제거할 수 있습니다.

검색 목적의 예시는 다음과 같습니다.

- 프로젝트가 해결하려던 문제
- 사용자가 직접 담당한 역할과 행동
- 핵심 의사결정과 판단 근거
- 프로젝트의 결과와 변화
- 프로젝트를 통해 얻은 배움

현재 RAG 서비스는 이 다섯 목적을 서로 다른 Query로 검색합니다. Query Embedding은 한 번의 배치로 생성하고, 각 검색 결과는 목적과 함께 유지하여 이후 LLM이 어떤 근거를 어떤 이유로 전달받았는지 추적할 수 있게 합니다.

모든 검색은 요청받은 `projectId` 범위로 제한합니다. 다른 사용자나 다른 프로젝트의 자료가 검색 결과에 포함되지 않도록 Spring의 권한 검사와 FastAPI의 검색 범위 검사를 함께 적용합니다.

MVP는 Top K 5와 정확 Cosine 검색으로 시작합니다. HNSW는 데이터가 충분히 쌓여 검색 속도와 재현율을 측정한 뒤 추가합니다.

의미 검색 결과가 0건이면 기존 Experience를 추측으로 연결하지 않습니다. 대신 이번 Analysis Run의 `sourceIds`에 해당하는 새 Source Chunk 원문만 다시 불러와 신규 경험 가능성을 분석합니다. 해당 Chunk도 존재하지 않으면 LLM을 호출하지 않고 `NO_UPDATE`와 인덱싱 필요 사유를 반환합니다.

정보가 부족할 때는 두 경우를 구분합니다. 질문 1~2개로 보완할 수 있으면 `informationNeed=USER_ANSWER`와 질문을 반환하고, 자료가 너무 모호해 경험 자체를 특정할 수 없으면 Candidate를 만들지 않고 `informationNeed=ADDITIONAL_SOURCE`와 필요한 자료 설명을 반환합니다. 후자는 `NO_UPDATE`가 아니며, 기존 Source는 `INDEXED` 상태로 유지됩니다.

새 Source가 사용자 확정 Experience와 충돌하면 `EXISTING_UPDATE` Candidate에 `conflict=true`와 구조화된 `conflicts`를 반환합니다. 각 충돌은 Spring이 전달한 실제 기존 Claim 또는 사용자 수정값과 새 Candidate Claim을 함께 참조해야 하며, 서버 검증을 통과하지 못한 가짜 기존 값은 거부됩니다. 실제 Experience 수정은 사용자 Review 이후 Spring에서만 수행합니다.

각 분석 응답은 이번 요청의 새 자료를 `inputSourceIds`, RAG가 누적 자료에서 추가로 읽은 기존 Evidence 자료를 `referencedSourceIds`로 구분합니다. Review 진행 중 새 Source가 추가되어도 현재 입력 스냅샷에는 합치지 않으며, 새 Source는 다음 사용자 실행의 새 Analysis Run에서 처리합니다. FastAPI는 두 스냅샷을 실제 검색 결과로 확정하고 Review 상태 및 다음 실행 대상 관리는 Spring이 담당합니다.

보완 질문에 사용자가 답하면 Spring은 답변을 저장하고 다음 Analysis Run 요청의 `answers`에 전달합니다. 답변 기반 Claim은 실제 `answerId`를 `supportingAnswerIds`로 참조하고 섹션과 Provenance가 일치할 때만 `USER_INPUT` 또는 `USER_EDITED`로 인정됩니다. 존재하지 않는 답변을 AI가 참조하거나 `USER_CONFIRMED`를 위조하면 Policy Validator가 이를 신뢰하지 않습니다.

### 5. Generate a structured draft

검색된 Chunk만 외부 LLM에 근거로 전달합니다. LLM은 자유 형식의 글이 아니라 약속된 JSON 구조로 다음 결과를 생성합니다.

- 프로젝트 요약
- Claim
- Claim을 뒷받침하는 Evidence
- 최대 3개의 경험 후보
- 최대 2개의 보완 질문
- 기존 경험 보강, 새 경험, 확인 필요, 반영 없음의 분석 결과

외부 LLM은 Provider 인터페이스 뒤에 분리하여 공급자나 모델이 변경되더라도 분석 흐름 전체를 다시 작성하지 않도록 설계합니다.

분석 Orchestrator는 여러 검색 목적에서 같은 Chunk가 발견되면 한 번만 전달하고, 해당 Chunk가 어떤 목적으로 검색됐는지 함께 기록합니다. 기본적으로 거리순 최대 15개 Chunk만 LLM에 전달하며 원본 문서 전체는 전달하지 않습니다.

### LLM Provider and environments

분석 코드는 특정 LLM 공급자에 직접 의존하지 않습니다. 동일한 `LLMProvider` 계약 뒤에서 실행 환경에 따라 구현체만 선택합니다.

- `fake`: API 키와 비용 없이 고정된 응답을 반환합니다. 로컬 개발과 Spring 연동 테스트의 기본값입니다.
- `gemini`: Google Gemini API에서 JSON Schema 기반 Structured Output을 생성합니다. 실제 AI 품질 검증과 배포 환경에서 사용합니다.

Gemini Timeout, 일시적 Provider 오류, Structured Output 검증 실패는 FastAPI 내부에서 한 번만 다시 시도합니다. 인증·요청 오류와 같은 비일시적 4xx는 반복 호출하지 않습니다. 전체 30초 제한 안에 두 번의 시도가 가능하도록 개별 LLM 시도 제한은 기본 14초입니다.

환경별 운영 원칙은 다음과 같습니다.

- 로컬 및 자동 테스트: `fake`를 사용합니다.
- 개발 검증: 개발 전용 Google 프로젝트와 API 키를 사용하고, 공개 자료 또는 비식별 테스트 자료만 전송합니다.
- 운영: 운영 전용 Google 프로젝트와 유료 한도 및 API 키를 분리합니다.

무료·유료 Tier에 따라 애플리케이션 코드를 나누지 않습니다. 요금제와 한도는 Google 프로젝트에서 관리하고, 서버는 Provider·모델·키를 환경변수로 주입받습니다. API 키는 Git에 커밋하지 않습니다.

DB 주소가 없는 로컬 환경에서는 프로세스 메모리 Vector Store를 사용해 전체 RAG 흐름을 테스트합니다. `LOGFOLIO_AI_DATABASE_URL`이 설정된 환경에서만 PostgreSQL과 pgvector에 연결합니다.

### 6. Validate claims and evidence

LLM이 올바른 JSON을 반환했다고 해서 내용까지 사실인 것은 아닙니다. FastAPI는 결과를 Spring에 보내기 전에 형식과 내용을 별도로 검사합니다.

- 필수 필드와 데이터 타입이 계약에 맞는지 확인
- 허용된 Enum 값만 사용했는지 확인
- 경험 후보와 질문의 최대 개수 확인
- Evidence가 실제 파일과 Chunk를 가리키는지 확인
- 인용문이 원문에 존재하는지 확인
- 자료에 없는 성과, 수치 또는 직책이 추가됐는지 확인
- 팀 활동이 사용자 개인 기여로 변경됐는지 확인

근거가 부족한 개인 기여, 판단 이유, 성과와 배운 점은 사실로 확정하지 않고 사용자 확인 대상으로 반환합니다.

정책 검증은 프롬프트에만 의존하지 않습니다. LLM 응답을 받은 뒤 Python 검증기가 다음 규칙을 다시 적용합니다.

- 팀 활동 근거를 사용자 개인 활동으로 반환하면 주체를 `UNKNOWN`으로 낮추고 확인 대상으로 변경
- 개인 기여를 직접 뒷받침하는 표현이 없으면 `VERIFIED`로 확정하지 않음
- AI가 `USER_INPUT`, `USER_CONFIRMED`, `USER_EDITED` 상태를 생성하면 `AI_INFERRED`로 변경
- 근거 없는 역할과 성과에는 정책 위반 상태를 기록하고 사용자 확인 요구
- 이미 자료에서 검증된 항목을 다시 묻는 질문은 제거
- 질문은 개인 기여, 의사결정, 결과, 판단 근거, 배움 순으로 우선 처리

현재 요청 계약에는 사용자 이름이 포함되지 않으므로, 개인 기여는 1인칭 직접 표현이 있는 경우만 보수적으로 인정합니다. 사용자 식별 정보 계약이 추가되면 이름 기반 근거 판정도 확장할 수 있습니다.

### 7. Return a reviewable result

FastAPI가 반환한 결과는 최종 경험카드가 아닌 AI 초안입니다. Spring과 클라이언트는 사용자가 각 내용을 검토할 수 있도록 제공합니다.

Evidence 검증은 항목 단위로 적용합니다. 검색되지 않은 Chunk, 원문과 다른 인용문 또는 잘못된 페이지를 사용한 Claim은 제거하되, 동일 응답의 정상 Claim과 Candidate까지 함께 폐기하지 않습니다. 검증 가능한 Claim이 하나도 남지 않은 Candidate만 제외합니다.

사용자는 결과를 다음과 같이 처리할 수 있습니다.

- 승인: AI가 제안한 내용을 사실로 확인
- 수정: AI 제안을 사용자의 표현과 사실에 맞게 변경
- 거절: 사실이 아니거나 필요하지 않은 제안을 제외
- 답변: 자료에서 확인할 수 없는 개인 맥락을 추가

사용자의 입력과 수정은 기존 AI 추론보다 우선합니다. 승인되거나 수정된 결과만 최종 경험카드로 저장됩니다.

## Claim and evidence policy

LogFolio에서 Claim은 AI가 자료를 바탕으로 제안한 하나의 주장이고, Evidence는 그 주장을 뒷받침하는 원문 근거입니다.

예를 들어 자료에 다음 문장만 있다면:

```text
프로젝트 팀은 사용자 인터뷰를 5회 진행했다.
```

AI는 이를 다음과 같이 해석해야 합니다.

- 프로젝트에서 인터뷰가 진행된 사실: 자료로 확인 가능
- 사용자가 직접 인터뷰를 담당했다는 주장: 확인 불가능
- 필요한 처리: 팀 활동으로 기록하고 개인 참여 여부 질문

다음과 같이 바꾸어 생성해서는 안 됩니다.

```text
사용자는 인터뷰 5회를 주도했다.
```

이 구분을 위해 AI 결과에는 활동 주체, 정보의 출처, 검증 상태와 사용자 확인 필요 여부를 함께 포함합니다.

## API contract summary

Spring과 FastAPI는 다음 공통 규칙을 사용합니다.

- 식별자: UUID 문자열
- JSON 필드명: camelCase
- 분석 추적: `analysisRunId`
- 요청당 파일: 최대 3개
- 경험 후보: 최대 3개
- 보완 질문: 최대 2개
- FastAPI 응답 제한: 30초
- Source 인덱싱 재시도: Spring에서 최대 1회
- Gemini 분석 재시도: FastAPI 내부에서 최대 1회
- AI 결과 저장: 사용자 검토 후 확정

ERD에 존재하는 필드와 상태값은 Spring의 정의를 따릅니다. ERD에 없는 AI 전용 판단값은 FastAPI 계약에서 정의하고 양쪽 서버가 동일한 문자열을 사용합니다.

상세 요청 및 응답 예시는 실제 API 모델 구현과 함께 문서화할 예정입니다.

## Technology stack

- Python
- FastAPI
- Pydantic
- PostgreSQL 17
- pgvector
- `intfloat/multilingual-e5-base`
- External LLM API
- pytest

## MVP scope

MVP는 정확한 근거 추적과 사용자 검토 흐름을 우선합니다.

포함 범위:

- 최대 3개 파일 분석
- 프로젝트 범위의 벡터 검색
- Claim과 Evidence 생성
- 경험 후보 최대 3개 생성
- 보완 질문 최대 2개 생성
- AI Policy 검증
- 사용자 검토 전 초안 상태 유지

제외 범위:

- LLM 직접 학습과 Fine-tuning
- 로컬 LLM 배포
- Agentic RAG와 GraphRAG
- Reranker와 Hybrid Search
- 대규모 검색 성능 최적화

## Development status

현재 Spring–FastAPI 요청·응답 모델, Project File·Quick Log 통합 Source 인덱싱, 기존 Experience 비교 입력, 네 가지 분석 결과, 공통 오류 응답, LLM Provider, Chunking, Embedding, pgvector 저장·검색, RAG 분석, AI Policy 검증과 고정 평가 데이터셋이 구현되어 있습니다. Review 상태 저장과 승인 후 Experience 반영은 Spring이 담당합니다. Docker Compose 환경에서는 PostgreSQL 17과 pgvector를 포함한 분석 API의 Smoke Test를 실행할 수 있습니다.

Fake Provider 검증은 외부 API 비용 없이 서버 간 계약과 처리 흐름을 확인하기 위한 것입니다. 실제 검색·생성 품질은 E5와 Gemini를 켠 별도의 비식별 평가 환경에서 검증해야 합니다.

## Local development

Python 3.11 이상이 필요합니다.

```bash
cd ai-server
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
uvicorn logfolio_ai.main:app --app-dir src --reload
```

실제 로컬 E5 모델을 실행할 환경에서는 Embedding 추가 의존성을 설치합니다. 첫 실행 시 모델 파일을 내려받으므로 네트워크와 디스크 공간이 필요합니다.

```bash
python -m pip install -e '.[dev,embedding]'
```

서버 실행 후 다음 주소에서 상태와 API 문서를 확인할 수 있습니다.

- Health: `http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`

Spring 연동 요청·응답과 재시도 규칙은 [`docs/spring-fastapi-contract.md`](docs/spring-fastapi-contract.md)에 정리되어 있습니다.

테스트는 다음 명령으로 실행합니다.

```bash
pytest
```

AI Policy 회귀 평가는 실제 사용자 자료를 모사한 고정 데이터셋으로 실행합니다. 외부 LLM을 호출하지 않으므로 API 비용이 발생하지 않습니다.

```bash
python -m logfolio_ai.evaluation.runner
```

현재 평가 데이터는 팀 활동의 개인 귀속, 근거 없는 성과, 명시된 개인 기여, 사용자 확인 상태 위조와 불필요한 질문을 포함합니다. 실제 Gemini 품질과 RAG 검색 정확도 평가는 운영 데이터가 아닌 별도의 비식별 검증 자료로 확장해야 합니다.

실제 Provider의 제품 판단은 버전 관리되는 Product Gold Case로 별도 평가합니다. 결과에는 Result Type, 대상 Experience, Candidate 수, 질문 필요 여부, Critical Policy 위반과 함께 Token, Latency, Retry, 버전이 명시된 가격표 기반 추정 비용이 기록됩니다.

Experience 경계는 Source 경계가 아니라 문제·행동·결정·결과의 의미를 기준으로 판단합니다. 여러 Source가 하나의 흐름이면 한 Experience로 합치고, 하나의 Source 안에서도 독립적인 흐름이면 별도 Experience로 분리합니다. FastAPI Policy Validator는 같은 기존 Experience를 가리키는 중복 Update를 합치고, 신규 후보는 내용이 완전히 같은 경우에만 제거합니다.

Product Gold Dataset은 신규·보강·정보 부족·오귀속·병합·분리뿐 아니라 기존 확정값 충돌, 추가 Source 필요, 반영 없음, 거절값 재제안 방지와 Prompt Injection도 포함합니다. 실제 Provider 호출 전에는 이 Case들의 Schema와 자동 평가기를 오프라인 테스트로 검증합니다.

```bash
python -m logfolio_ai.evaluation.product_runner \
  --provider gemini \
  --model <model-name> \
  --output-json evals/results/result.json \
  --output-csv evals/results/result.csv
```

실제 Provider Eval은 외부 API 비용이 발생할 수 있으므로 명시적으로 실행할 때만 호출합니다. 사용법과 Dataset 관리 기준은 [`evals/README.md`](evals/README.md)를 참고합니다.

실제 프로젝트 분석에서 LLM을 호출하면 응답의 `aiUsage`에 Provider, Model, Token, Latency, Retry와 추정 비용을 반환합니다. 가격과 환율은 변할 수 있으므로 코드에 고정하지 않고 환경변수로 주입하며, 가격 설정이 불완전하면 비용을 임의 계산하지 않습니다. Spring은 이 값을 `analysisRunId` 및 인증된 사용자와 연결해 저장해야 합니다.

Prompt Injection 방어를 위해 System Policy와 Source JSON은 Gemini 요청에서 서로 다른 역할로 전달합니다. Chunk, 기존 Experience, 사용자 수정값과 답변은 모두 신뢰할 수 없는 데이터로 취급하며, Source 내부 명령은 실행하지 않습니다. 결과는 이후 Evidence 검증과 AI Policy 검증을 다시 통과해야 합니다. `PROMPT_INJECTION_01` Gold Case는 이 동작을 실제 Provider Eval에서 반복 검사합니다.

기본 설정은 외부 호출이 없는 Fake Provider입니다.

```bash
LOGFOLIO_AI_LLM_PROVIDER=fake
```

Gemini를 사용할 때만 로컬 `.env` 또는 배포 환경의 Secret에 다음 값을 설정합니다.

```bash
LOGFOLIO_AI_LLM_PROVIDER=gemini
LOGFOLIO_AI_GEMINI_API_KEY=your-api-key
LOGFOLIO_AI_GEMINI_MODEL=gemini-3.5-flash
LOGFOLIO_AI_LLM_TIMEOUT_SECONDS=14
LOGFOLIO_AI_CHUNK_SIZE_TOKENS=700
LOGFOLIO_AI_CHUNK_OVERLAP_TOKENS=100
LOGFOLIO_AI_EMBEDDING_PROVIDER=fake
LOGFOLIO_AI_EMBEDDING_MODEL=intfloat/multilingual-e5-base
LOGFOLIO_AI_EMBEDDING_BATCH_SIZE=16
LOGFOLIO_AI_DATABASE_URL=postgresql://postgres:password@localhost:5432/logfolio
LOGFOLIO_AI_VECTOR_DIMENSION=768
LOGFOLIO_AI_RETRIEVAL_TOP_K=5
LOGFOLIO_AI_MAX_GROUNDED_CHUNKS=15
LOGFOLIO_AI_EXISTING_EXPERIENCE_MATCH_DISTANCE=0.4
LOGFOLIO_AI_PROJECT_SOURCE_MATCH_DISTANCE=0.65
LOGFOLIO_AI_MAX_RELATED_EXPERIENCES=3
```

실제 로컬 E5를 사용할 때는 `LOGFOLIO_AI_EMBEDDING_PROVIDER=e5`로 변경합니다.

Vector Store 스키마는 `migrations/001_create_ai_document_chunks.sql`부터 순서대로 적용합니다. `003_support_unified_sources.sql`은 파일 전용 컬럼을 통합 Source 컬럼으로 바꾸고 Quick Log를 지원하며, `004_add_source_content_hash.sql`은 정확한 Source 중복 판별용 SHA-256을 저장합니다. Docker Compose에서는 `migrate` 서비스가 `ai_schema_migrations` 이력을 확인하고 아직 적용되지 않은 SQL만 실행한 후 FastAPI를 시작합니다. 운영 DB 적용 전에는 Spring 담당자와 실행 주체·백업·롤백 정책을 별도로 합의해야 합니다.

## Docker integration environment

이 환경은 로컬에서 Spring 연동 전에 FastAPI, PostgreSQL 17, pgvector와 내부 인증을 함께 검증하기 위한 것입니다. 기본 Provider는 `fake`이므로 Gemini API 키와 외부 API 비용이 필요하지 않습니다.

먼저 로컬 전용 환경변수 파일을 만들고 예시 비밀번호와 API 키를 변경합니다. `deploy/.env`는 Git에 커밋하지 않습니다.

```bash
cd ai-server
cp deploy/.env.example deploy/.env
```

Compose 설정을 확인한 뒤 통합 Smoke Test를 실행합니다.

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml config
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build postgres migrate ai-server
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile smoke run --rm smoke
```

성공하면 `LogFolio AI smoke test passed`가 출력됩니다. 테스트 후 컨테이너와 네트워크만 정리하고 DB 볼륨은 보존합니다.

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile smoke down
```

`down -v`는 로컬 PostgreSQL 데이터를 함께 삭제하므로 DB를 의도적으로 초기화할 때만 사용합니다.

Compose는 새 DB뿐 아니라 기존 개발 볼륨에도 미적용 마이그레이션을 순서대로 적용합니다. 기존 001~004 DB는 실제 컬럼을 확인해 초기 이력을 안전하게 구성하며, 같은 마이그레이션은 다시 실행하지 않습니다. 운영 DB에서는 자동 실행 여부를 별도로 결정해야 합니다.

실제 E5를 포함한 이미지는 `INSTALL_EMBEDDING=true`로 빌드할 수 있지만 모델 의존성 때문에 이미지 크기와 빌드 시간이 크게 늘어납니다. 운영에서는 Gemini API 키, DB 비밀번호와 내부 API 키를 이미지나 저장소에 넣지 않고 배포 플랫폼의 Secret으로 주입해야 합니다.

### E5 retrieval validation

실제 `intfloat/multilingual-e5-base` 모델이 768차원 벡터를 생성하고 한국어 Query에 관련 문서를 가장 먼저 반환하는지 고정된 소규모 데이터로 확인합니다. 이것은 모델 연결을 확인하는 Smoke Evaluation이며, 서비스 품질 기준을 대신하지 않습니다.

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile e5 run --rm e5-eval
```

첫 실행은 모델과 PyTorch 의존성을 내려받으므로 시간이 오래 걸리고 디스크를 많이 사용할 수 있습니다. Docker 이미지는 GPU가 없는 현재 배포 방향에 맞춰 PyTorch CPU 전용 Wheel을 사용하므로 CUDA 런타임을 포함하지 않습니다. Hugging Face 모델 캐시는 `logfolio-huggingface` Docker 볼륨에 보존되어 이후 실행에서 재사용됩니다. 모델 공식 사용법에 따라 문서는 `passage:`, 검색문은 `query:` 접두어를 사용하며 벡터를 정규화합니다.

### E5 and pgvector end-to-end validation

실제 E5 모델과 PostgreSQL/pgvector를 사용하되 LLM만 Fake Provider로 유지하여 전체 RAG API를 검증합니다. 서버는 E5 모델을 시작 단계에서 미리 로딩하므로 Health Check 성공 이후의 첫 분석 요청도 모델 로딩 시간을 포함하지 않습니다.

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile e5-rag up -d --build postgres migrate ai-server-e5
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile e5-rag run --rm e5-rag-smoke
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile e5-rag down
```

검증 항목은 내부 API 키 인증, 30초 이내 응답, 추적 ID 보존, pgvector Chunk 저장, 768차원 벡터, E5 모델명과 프로젝트 범위 격리입니다. Fake LLM을 사용하므로 외부 생성형 AI 비용은 발생하지 않습니다.

### Gemini free-tier validation

개발 단계에서는 `gemini-3.5-flash` 무료 티어와 비식별 합성 자료만 사용합니다. 무료 티어로 전송한 콘텐츠는 Google 제품 개선에 사용될 수 있으므로 실제 사용자 파일, 개인정보와 회사 비공개 자료를 보내지 않습니다. 운영 환경은 별도의 유료 프로젝트와 Secret으로 분리해야 합니다.

모델은 `GEMINI_MODEL` 환경변수로 교체할 수 있습니다. 예를 들어 `gemini-3.8-flash`가 안정화되면 코드 변경 없이 해당 모델로 전환할 수 있습니다.

`deploy/.env`에 Google AI Studio에서 발급한 개발용 키를 직접 입력합니다. 실제 키는 Git, 문서, 메신저 또는 실행 로그에 남기지 않습니다.

```dotenv
GEMINI_API_KEY=your-local-development-key
```

합성 자료로 실제 Structured Output과 AI Policy 흐름을 한 번 검증합니다.

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile gemini up --build --abort-on-container-exit --exit-code-from gemini-smoke gemini-smoke
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile gemini down
```

Gemini 서버는 API 키와 Provider 구성을 시작 시점에 확인합니다. Smoke Test는 30초 이내 응답, 요청 추적 ID, 후보·질문 개수 제한과 사용자 전용 출처 상태 위조 여부를 확인합니다.

### Full E5, pgvector, Gemini pipeline validation

실제 E5 Embedding, pgvector 검색, Gemini Structured Output과 AI Policy를 한 요청으로 검증합니다. 테스트는 다른 `projectId`에 격리 확인용 자료를 먼저 넣고, 해당 자료가 분석 근거나 요약에 섞이지 않는지도 확인합니다. 외부 Gemini에는 비식별 합성 자료만 전송합니다.

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile full-pipeline up -d --build postgres migrate ai-server-full-pipeline
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile full-pipeline run --rm full-pipeline-smoke
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile full-pipeline down
```

검증 항목은 30초 이내 응답, 추적 ID 보존, 경험 후보 1~3개, 질문 최대 2개, 원문과 일치하는 근거, 다른 프로젝트 자료 격리, 768차원 E5 벡터와 모델명입니다. 외부 LLM 응답 시간은 변동될 수 있으므로 첫 실패에는 동일 `analysisRunId`로 최대 1회만 재시도합니다.
