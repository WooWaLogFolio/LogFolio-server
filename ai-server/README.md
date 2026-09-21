# LogFolio AI Server

LogFolio AI Server는 사용자가 업로드한 프로젝트 자료에서 경험을 발견하고, 그 근거를 함께 제시하는 AI 분석 서버입니다.

단순히 자연스러운 포트폴리오 문장을 생성하는 것이 아니라, 문서에 실제로 존재하는 내용과 사용자가 직접 기여한 내용을 구분합니다. AI가 만든 결과는 초안으로 제공되며 사용자의 검토를 거친 뒤에만 최종 경험카드로 저장됩니다.

> 현재 이 디렉터리는 AI 서버의 기본 API 계약과 교체 가능한 LLM Provider를 구현했으며, RAG 기능은 순차적으로 구현될 예정입니다.

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

### 1. Receive extracted text

Spring이 파일 원본을 저장하고 텍스트를 추출한 뒤, 프로젝트 및 파일 식별자와 함께 FastAPI에 전달합니다.

분석 요청은 `analysisRunId`로 추적합니다. 한 번의 요청에서는 최대 3개 파일을 처리합니다.

### 2. Build searchable document chunks

FastAPI는 긴 문서를 섹션, 문단, 문장 경계를 고려해 작은 Chunk로 나눕니다. 각 Chunk에는 원문을 다시 확인할 수 있도록 다음 정보를 유지합니다.

- 프로젝트 ID
- 파일 ID
- Chunk ID와 문서 내 순서
- 페이지 또는 원문 위치
- 문서 및 섹션 제목
- 원문 텍스트

초기 구현은 페이지 경계를 넘어서 Chunk를 합치지 않으며, 기본 크기 700단위와 Overlap 100단위로 시작합니다. 현재 단위 계산은 모델별 토크나이저가 아닌 가벼운 결정적 추정 방식이므로 실제 검색 품질 평가에 따라 조정합니다. 같은 파일 ID와 같은 원문에는 동일한 Chunk ID를 생성하여 재시도 시 중복을 줄입니다.

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

### 5. Generate a structured draft

검색된 Chunk만 외부 LLM에 근거로 전달합니다. LLM은 자유 형식의 글이 아니라 약속된 JSON 구조로 다음 결과를 생성합니다.

- 프로젝트 요약
- Claim
- Claim을 뒷받침하는 Evidence
- 최대 3개의 경험 후보
- 최대 2개의 보완 질문

외부 LLM은 Provider 인터페이스 뒤에 분리하여 공급자나 모델이 변경되더라도 분석 흐름 전체를 다시 작성하지 않도록 설계합니다.

분석 Orchestrator는 여러 검색 목적에서 같은 Chunk가 발견되면 한 번만 전달하고, 해당 Chunk가 어떤 목적으로 검색됐는지 함께 기록합니다. 기본적으로 거리순 최대 15개 Chunk만 LLM에 전달하며 원본 문서 전체는 전달하지 않습니다.

### LLM Provider and environments

분석 코드는 특정 LLM 공급자에 직접 의존하지 않습니다. 동일한 `LLMProvider` 계약 뒤에서 실행 환경에 따라 구현체만 선택합니다.

- `fake`: API 키와 비용 없이 고정된 응답을 반환합니다. 로컬 개발과 Spring 연동 테스트의 기본값입니다.
- `gemini`: Google Gemini API에서 JSON Schema 기반 Structured Output을 생성합니다. 실제 AI 품질 검증과 배포 환경에서 사용합니다.

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

### 7. Return a reviewable result

FastAPI가 반환한 결과는 최종 경험카드가 아닌 AI 초안입니다. Spring과 클라이언트는 사용자가 각 내용을 검토할 수 있도록 제공합니다.

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
- Spring 자동 재시도: 최대 1회
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

현재 AI 서버는 계약 모델과 기본 실행 구조를 구현하는 단계입니다. 구현은 다음 순서로 진행합니다.

1. Spring–FastAPI 요청·응답 모델
2. FastAPI 기본 서버와 공통 오류 응답
3. 외부 LLM Provider 및 Structured Output
4. Chunking과 Embedding
5. pgvector 저장 및 프로젝트 범위 검색
6. Claim, Evidence, 경험 후보 및 질문 생성
7. AI Policy 검증과 평가
8. Spring 통합 테스트

구현이 진행되면 이 문서에 실행 방법, 환경변수, API 예시와 테스트 방법을 추가합니다.

## Local development

Python 3.9 이상이 필요합니다.

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

테스트는 다음 명령으로 실행합니다.

```bash
pytest
```

기본 설정은 외부 호출이 없는 Fake Provider입니다.

```bash
LOGFOLIO_AI_LLM_PROVIDER=fake
```

Gemini를 사용할 때만 로컬 `.env` 또는 배포 환경의 Secret에 다음 값을 설정합니다.

```bash
LOGFOLIO_AI_LLM_PROVIDER=gemini
LOGFOLIO_AI_GEMINI_API_KEY=your-api-key
LOGFOLIO_AI_GEMINI_MODEL=gemini-3.8-flash
LOGFOLIO_AI_LLM_TIMEOUT_SECONDS=30
LOGFOLIO_AI_CHUNK_SIZE_TOKENS=700
LOGFOLIO_AI_CHUNK_OVERLAP_TOKENS=100
LOGFOLIO_AI_EMBEDDING_PROVIDER=fake
LOGFOLIO_AI_EMBEDDING_MODEL=intfloat/multilingual-e5-base
LOGFOLIO_AI_EMBEDDING_BATCH_SIZE=16
LOGFOLIO_AI_DATABASE_URL=postgresql://postgres:password@localhost:5432/logfolio
LOGFOLIO_AI_VECTOR_DIMENSION=768
LOGFOLIO_AI_RETRIEVAL_TOP_K=5
LOGFOLIO_AI_MAX_GROUNDED_CHUNKS=15
```

실제 로컬 E5를 사용할 때는 `LOGFOLIO_AI_EMBEDDING_PROVIDER=e5`로 변경합니다.

Vector Store 스키마는 `migrations/001_create_ai_document_chunks.sql`에 있습니다. 이 SQL은 pgvector 확장을 활성화하므로 개발·운영 DB에 적용하기 전에 Spring 담당자와 실행 주체 및 백업 정책을 확인해야 합니다. 저장소에 추가된 것만으로 실제 DB에는 자동 적용되지 않습니다.
