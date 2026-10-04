# LogFolio AI 모델·Spring·전체 연동 로드맵

작성 기준일: 2026-10-04  
기준 브랜치: `integration/next`

이 문서는 현재 구현된 AI 서버를 실제 서비스 흐름에 연결하기 위해 앞으로 해야 할 일을 한곳에 정리한다. 작업 순서는 **AI 모델 확정 → Spring 계약·ERD 반영 → Spring과 FastAPI 연동 → 전체 E2E 검증 → 배포 준비**다.

## 1. 현재 완료된 범위

### AI 서버

- FastAPI 요청·응답 API와 내부 API Key 검증
- Project File·Quick Log Source 인덱싱 및 삭제
- Chunking, 로컬 `intfloat/multilingual-e5-base` Embedding, pgvector 검색
- 프로젝트 범위가 섞이지 않는 Retrieval
- 새 Source와 기존 Experience 비교
- `EXISTING_UPDATE`, `NEW_EXPERIENCE`, `NEEDS_CONTEXT`, `NO_UPDATE` 분류
- 기존 Evidence 추가 검색과 Analysis Source Snapshot 반환
- Claim·Evidence·페이지 위치 검증
- TEAM 정보를 USER 개인 기여로 잘못 귀속하지 않는 Policy 검증
- Conflict, 정보 부족, 다른 프로젝트 의심, 부분 Evidence 실패 처리
- Gemini Provider, Structured Output, 30초 제한과 최대 1회 내부 재시도
- Gold Case, Human Eval, Retrieval·Pipeline·복구·비용 평가 도구
- Fake Provider 기반 오프라인 검증

### Spring

- Project, Quick Log, Project File, Analysis Run, Candidate, Experience, Review 관련 기본 테이블
- Analysis Run과 입력 파일·Quick Log의 연결 테이블
- AI 서버 Client와 Source Index 연동 코드
- Project File 및 Quick Log의 AI 인덱싱 상태 필드와 이벤트 처리

### 아직 완료로 볼 수 없는 범위

- 실제 서비스용 Gemini 모델 최종 선정 및 전체 Gold Case 실행
- Spring ERD의 Question·Evidence·AI Usage 저장 구조 보완
- Spring이 Existing Experience, 사용자 수정·거절 이력, 답변을 포함해 분석 요청을 만드는 흐름
- AI 응답을 Candidate·Review·Evidence에 저장하는 흐름
- 사용자 승인·수정·거절 후 Experience 반영
- Spring → FastAPI → Gemini → Spring → 프론트엔드 전체 E2E 검증
- 운영 Secret, 개인정보 처리, 모니터링과 비용 제한 적용

## 2. 1단계 — 실제 AI 모델 선정 및 연동

### 2.1 모델 선정의 필수 조건

아래 조건을 하나라도 충족하지 못하면 운영 후보에서 제외한다.

- JSON Schema 기반 Structured Output 지원
- 한국어 프로젝트 문서에서 Claim·Evidence를 안정적으로 생성
- 최대 3개 Candidate와 최대 2개 Question 계약 준수
- 기존 Experience ID와 Source·Chunk ID를 임의 생성하지 않음
- Prompt Injection 문장을 명령이 아닌 Source 데이터로 취급
- 30초 서버 제한 안에서 실사용 가능한 지연 시간
- Token 사용량을 응답에서 수집 가능
- Provider 장애와 Timeout을 구분 가능
- 운영 환경에서 사용자 자료가 모델 개선에 사용되지 않는 조건 제공
- 예상 사용량에서 Cost Guardrail을 통과

### 2.2 우선 비교할 모델 후보

2026-10-04 Google 공식 모델 목록 기준으로 다음 순서로 비교한다.

| 후보 | 용도 | 판단 |
| --- | --- | --- |
| `gemini-3.5-flash` | 현재 Baseline | 이미 연결된 안정 비교 기준 |
| `gemini-3.8-flash` | 품질 우선 후보 | 기본 운영 모델 1순위 비교 대상 |
| `gemini-3.5-flash-lite` | 비용·속도 우선 후보 | 품질 Gate 통과 시 저비용 대안 |

`preview`, `experimental`, `latest` 별칭은 예고 없이 동작이 바뀔 수 있으므로 운영 기본값으로 사용하지 않는다. 정확한 모델명, 제공 상태와 요금은 최종 선택 직전에 Google 공식 문서에서 다시 확인한다.

Embedding은 우선 `intfloat/multilingual-e5-base`를 유지한다. 생성 LLM을 바꾸는 것은 기존 Embedding 재생성을 요구하지 않지만, Embedding 모델을 바꾸면 저장된 모든 Chunk 벡터를 다시 생성해야 한다.

### 2.3 모델 확정 절차

1. 개인정보 없는 대표 Gold Case 5개로 연결·Schema·지연 시간 확인
2. 통과한 후보만 전체 Product Gold Case 20개 실행
3. Conflict, TEAM→USER 귀속, 근거 없는 성과, Prompt Injection 같은 Hard Case를 3회 반복
4. Evidence 정확성, Result Type, Question 수, Policy Critical Error 자동 평가
5. 사람이 정확성·개인성·질문 유용성·문장 품질 평가
6. Token, P50/P95 지연 시간, 실패율, 재시도율, 예상 비용 비교
7. 품질 Gate를 통과한 모델 중 비용과 속도가 가장 좋은 모델 선택
8. 선택 모델명을 Secret이 아닌 환경변수 `LOGFOLIO_AI_GEMINI_MODEL`로 고정

### 2.4 무료·유료 환경 원칙

- 무료 티어: 합성·비식별 자료를 이용한 개발 테스트에만 사용
- 유료 프로젝트: 실제 사용자 자료를 처리하는 베타·운영에서 사용
- API Key는 `.env`, 배포 Secret에만 저장하고 Git에 올리지 않음
- 개발 Key와 운영 Key·Google Cloud Project 분리
- 무료 서비스에 실제 사용자 파일, 개인정보, 회사 비공개 자료를 보내지 않음
- 운영 전 Google의 데이터 처리 조건과 개인정보 동의를 최종 확인

Google 공식 문서상 무료 티어의 입력은 제품 개선에 사용될 수 있고, Billing이 연결된 Paid Service 입력은 제품 개선에 사용되지 않는다. 따라서 **무료 티어에서 실제 사용자 자료를 시험하지 않는 것**이 필수다.

### 2.5 완료 조건

- 최종 모델과 예비 모델 1개가 문서화됨
- 전체 Gold Case와 Hard Case Gate 통과
- Token·Latency·비용 Report 저장
- 실제 Gemini 실패·재시도·Schema 오류가 계약대로 처리됨
- 모델 변경이 환경변수만으로 가능함

## 3. 2단계 — Spring 요청·응답 계약 확정

### 3.1 실제 호출 순서

```text
Project File 또는 Quick Log 저장
→ Spring이 Source ID를 생성하고 텍스트 추출
→ POST /api/v1/sources/index
→ Source를 INDEXED로 기록
→ 사용자가 AI 분석하기 실행
→ Spring이 analysisRunId 생성
→ 미반영 새 Source + 기존 Experience + 답변·수정·거절 이력 구성
→ POST /api/v1/analyses
→ FastAPI가 RAG·Gemini·Policy 검증 수행
→ Spring이 Candidate·Evidence·Question·Usage를 Draft로 저장
→ 사용자 Review
→ 승인 또는 수정된 Item만 Experience에 반영
```

### 3.2 Spring이 FastAPI에 보내야 하는 데이터

- `analysisRunId`, `projectId`
- 이번 Run의 새 `sourceIds`
- 기존 Experience 전체의 ID, Summary, Claims, Evidence Metadata
- 관련 Experience의 기존 Evidence 원문 또는 이를 찾을 수 있는 Source 정보
- Gap Question에 대한 사용자 답변
- 사용자가 이전에 수정·승인·거절한 내용
- Prompt·Policy·Model 버전 추적에 필요한 버전 정보

Spring은 인증된 사용자가 해당 Project에 접근할 권한이 있는지 먼저 검사한다. FastAPI는 사용자 계정 DB를 직접 조회하지 않는다.

### 3.3 FastAPI가 Spring에 반환하는 데이터

- 요청 추적용 `analysisRunId`, `projectId`
- 실제 분석 입력인 `inputSourceIds`
- 검색으로 사용한 `referencedSourceIds`
- 최대 3개 Candidate와 Result Type
- 최대 2개 Gap Question
- Claim별 Evidence와 검증 상태
- Existing Experience Conflict
- `USER_ANSWER` 또는 `ADDITIONAL_SOURCE` 정보 부족 분류
- `NO_UPDATE` 사유
- Provider·Model·Token·Latency·Retry·비용 추정 `aiUsage`

상세 JSON과 오류 계약은 `spring-fastapi-contract.md`를 단일 기준으로 사용한다.

### 3.4 반드시 함께 확정할 계약 항목

- Analysis Run 상태 전이와 실패 코드
- Source가 다음 Run의 “새 Source”인지 판단하는 기준
- 동일 `analysisRunId` 재요청의 멱등성
- Candidate와 Review Item 생성 단위
- 사용자 답변 후 새 Run을 만드는 방식
- Review 중 새 Source가 들어왔을 때 다음 Run으로 격리하는 방식
- Source 삭제 시 FastAPI 인덱스 삭제 호출과 Evidence 보존 방식
- API Timeout, FastAPI 내부 재시도와 사용자의 재실행 규칙

## 4. Spring ERD 정합성 작업

### 4.1 이미 있는 테이블 — 새로 만들지 않음

- `analysis_runs`
- `analysis_input_files`, `analysis_input_logs`
- `experience_candidates.draft_content`
- `review_sessions`, `review_items`
- `evidence_items`, `review_item_evidence`, `experience_evidence`
- `gap_questions`, `gap_answers`

Claim 전용 테이블은 MVP에서 만들지 않는다. AI 원본은 `draft_content`, 검토 문장은 `review_items`, 근거는 `evidence_items`와 연결 테이블에 저장한다.

### 4.2 Spring에서 반드시 수정할 ERD

#### Gap Question 연결

- `gap_questions.candidate_id UUID NULL` 추가
- `gap_questions.experience_id`를 Nullable로 변경
- 경험 확정 전 질문은 `candidate_id`에 연결
- 확정된 Experience에 대한 질문은 `experience_id`에 연결
- 둘 중 최소 하나만 있도록 Check Constraint 검토

이 변경이 없으면 아직 Experience가 없는 신규 Candidate의 질문을 정상 저장할 수 없다.

#### Evidence 위치

- `evidence_items.chunk_id VARCHAR(...) NULL` 추가
- `evidence_items.page_number INT NULL` 추가
- `location`은 사용자 표시 문자열로 유지

이 변경이 없으면 인용문을 실제 RAG Chunk와 페이지까지 안정적으로 추적하기 어렵다.

#### Quick Log Source 상태 문서 동기화

- 실제 Migration V5에 존재하는 `quick_logs.processing_status`를 DBML·ERD Cloud에도 반영
- 허용값은 `PROCESSING`, `INDEXED`, `FAILED`

현재 실행 Schema에는 있지만 `backend/docs/logfolio-erd.dbml`에는 빠져 있어 문서와 DB가 어긋나 있다.

### 4.3 Spring에서 새 저장 구조를 정해야 하는 항목

#### AI Usage

별도 `ai_usage` 테이블을 권장한다. 최소 필드:

```text
analysis_run_id UNIQUE
user_id
project_id
provider
model
task_type
input_tokens
cached_input_tokens
output_tokens
reasoning_tokens
latency_ms
success
retry_count
error_type
estimated_cost_usd
estimated_cost_krw
pricing_version
created_at
```

동일 `analysisRunId` 재시도로 비용을 중복 합산하지 않도록 Unique와 Upsert가 필요하다.

#### Review 결과 지표

Analysis Run에 다음 값을 연결해서 비용 대비 유효 경험 수를 계산할 수 있어야 한다.

- 생성된 Experience 수
- 보강된 Experience 수
- 그대로 승인 수
- 수정 후 승인 수
- 거절 수
- Major Edit 수

`analysis_runs` 컬럼 확장 또는 별도 `analysis_result_metrics` 테이블 중 하나를 Spring 담당자가 선택한다.

### 4.4 Enum·상태 매핑 확인

- AI Result Type: `EXISTING_UPDATE`, `NEW_EXPERIENCE`, `NEEDS_CONTEXT`, `NO_UPDATE`
- DB Candidate Type: 현재 `NEW`, `ENHANCE_EXISTING`
- Source State: `PROCESSING`, `INDEXED`, `FAILED`
- Review Session: `IN_PROGRESS`, `COMPLETED`
- Review Item: `PENDING`, `APPROVED`, `EDITED`, `REJECTED`, `ANSWERED`

API Enum과 DB Enum의 이름이 다른 것은 가능하지만 Spring에 명시적인 Mapper가 있어야 한다. `NEEDS_CONTEXT`와 `NO_UPDATE`는 Candidate가 아니라 Question 또는 Run 결과로 저장한다.

## 5. 3단계 — Spring 기능 구현

### P0. Source 자동 인덱싱 완성

- Project File 텍스트 추출 성공 후 Source Index API 호출
- Quick Log 저장 후 Source Index API 호출
- 각각 `PROJECT_FILE`, `QUICK_LOG` Provenance 유지
- 성공 시 `INDEXED`, 실패 시 해당 Source만 `FAILED`
- 동일 Source 재시도 시 Chunk 교체로 멱등성 보장
- Source 삭제 시 FastAPI Index 삭제 호출
- 일부 Source 실패가 전체 Project 분석을 막지 않도록 처리

### P0. 프로젝트 분석 실행

- 사용자 버튼 실행 시 Spring이 `analysisRunId` 생성
- 진행 중 Review에 포함되지 않은 새 Source 선택
- 기존 Experience 전체와 Claims·Evidence Metadata 조회
- 사용자 답변과 수정·거절 기억 포함
- FastAPI 분석 호출
- 응답 Source Snapshot과 AI Usage 저장
- 성공·실패 상태와 시간을 `analysis_runs`에 기록

### P0. Draft·Review 저장

- Candidate 전체 원본을 `draft_content`에 저장
- Claim을 `review_items.proposed_content`에 저장
- Evidence를 `evidence_items`에 저장하고 `review_item_evidence`로 연결
- Question을 Candidate 또는 Experience에 연결
- AI 응답만으로 Experience 자동 생성·수정 금지

### P0. 사용자 Review 반영

- 승인: 제안 내용을 Experience에 반영
- 수정 후 승인: 사용자 수정값을 우선하여 반영
- 거절: Experience에 반영하지 않고 다음 분석의 거절 기억에 포함
- 기존 Experience와 합치기 또는 새 Experience로 분리
- Question 답변 저장 후 새 `analysisRunId`로 재판단
- 중간 이탈 시 `IN_PROGRESS`, 완료 시 `COMPLETED`

### P1. 비용·운영 정보

- 사용자·프로젝트·Analysis Run 단위 AI Usage 저장
- 월 비용 및 Accepted Experience당 비용 집계 Export
- 비용 Hard Limit 알림 또는 차단 정책 연결
- Provider 오류와 사용자 재실행 횟수 모니터링

## 6. 4단계 — 전체 E2E 연동 검증

### 반드시 통과할 시나리오

1. Quick Log 하나로 새 Experience Candidate 생성
2. Project File과 Quick Log를 함께 분석
3. 새 Source가 기존 Experience를 보강
4. 기존 사용자 확정값과 충돌하여 Review로 이동
5. 개인 기여 근거가 없어 Question 최대 2개 생성
6. 자료가 너무 부족해 `ADDITIONAL_SOURCE` 반환
7. 의미 있는 변화가 없어 `NO_UPDATE` 반환
8. 파일 3개 중 하나 실패 후 성공 Source만으로 진행
9. 다른 Project Source가 검색되지 않음
10. Review 중 새 Source가 다음 Analysis Run에만 포함
11. 답변 후 재분석에서 같은 Question이 제거됨
12. 사용자가 거절·수정한 내용을 다음 분석이 다시 덮어쓰지 않음
13. Source 삭제 후 Retrieval에서 제거되지만 확정 Experience는 유지
14. Gemini Timeout·잘못된 JSON 후 내부 1회 재시도
15. 같은 Analysis Run 재처리 시 Candidate·비용 중복 저장 없음

### 완료 기준

- Spring과 FastAPI Contract Test 통과
- 위 E2E 시나리오 자동 또는 재현 가능한 수동 테스트 통과
- 운영과 동일한 E5·pgvector·Gemini 조합 검증
- P95 지연 시간, 실패율, 재시도율과 비용 기록
- 개인정보가 Log·평가 결과·Git에 남지 않음
- 장애 시 기존 Source·Experience·Review 데이터가 유지됨

## 7. 역할 분담

### AI 담당

- Gemini 모델 비교·선정·Provider 설정
- Prompt, Structured Output, Policy Validator 관리
- Chunking·Embedding·Retrieval 품질 관리
- FastAPI 계약과 오류 응답 유지
- AI Gold Case·Human Eval·비용 평가
- Spring 통합 테스트용 요청·응답 Fixture 제공

### Spring 담당

- 사용자 권한과 Project 소유권 검증
- 파일 저장·텍스트 추출과 Quick Log 관리
- Analysis Run 생성·상태 관리
- 기존 Experience·Review·답변·Correction 조회
- FastAPI 호출과 결과 영속 저장
- ERD Migration과 멱등성 보장
- 사용자 Review 결과를 최종 Experience에 반영
- 사용자별 비용 집계

### 함께 할 일

- API·Enum·상태 전이 확정
- ERD 변경 Review
- Contract Test와 E2E Test
- 개인정보 전송 범위와 운영 Provider 계정 확정
- Timeout·장애·비용 초과 UX 확정

## 8. 권장 기능 브랜치 순서

각 브랜치는 최신 `develop`을 확인한 뒤 `integration/next`를 기준으로 만들고, 검증 후 `--no-ff`로 `integration/next`에 병합한다. `develop`에는 MVP 이후 기능을 미리 병합하지 않는다.

1. `feature/ai-model-final-validation`
   - Gemini 후보 비교, 실제 Gold Case, 최종 모델 설정
2. `feature/spring-ai-erd-alignment`
   - Question, Evidence, Quick Log 상태, AI Usage Migration
3. `feature/spring-ai-analysis-request`
   - 새 Source·기존 Experience·답변·Correction 요청 조립
4. `feature/spring-ai-result-persistence`
   - Candidate·Review·Evidence·Question·Usage 저장
5. `feature/spring-ai-review-application`
   - 승인·수정·거절·재질문·Experience 반영
6. `feature/ai-spring-e2e`
   - 실제 두 서버와 DB를 이용한 전체 통합 테스트
7. `feature/ai-production-readiness`
   - Secret, 개인정보, 모니터링, 비용 제한, 운영 문서

병합된 기능 브랜치는 `integration/next` 기록에 커밋이 남으므로 원격과 로컬에서 삭제해도 된다. 아직 병합되지 않은 브랜치와 `main`, `develop`, `integration/next`는 삭제하지 않는다.

## 9. 바로 다음 행동

1. AI 담당이 세 Gemini 후보로 대표 Gold Case 5개를 실행한다.
2. 동시에 Spring 담당이 `feature/spring-ai-erd-alignment`에서 필수 ERD 변경안을 작성한다.
3. 두 결과를 확인하고 API Enum·상태 전이를 30분 회의에서 확정한다.
4. Spring 분석 요청과 결과 저장을 각각 독립 브랜치로 구현한다.
5. Fake Provider E2E를 먼저 통과시킨 뒤 실제 Gemini E2E를 실행한다.
6. 실제 사용자 자료를 받기 전에 Paid Project, 개인정보 고지와 Secret 관리가 준비됐는지 확인한다.

## 10. 공식 참고 자료

- Gemini 모델 목록: https://ai.google.dev/gemini-api/docs/models
- Gemini API 요금: https://ai.google.dev/gemini-api/docs/pricing
- Gemini API 추가 약관과 데이터 사용: https://ai.google.dev/gemini-api/terms
- Zero Data Retention 안내: https://ai.google.dev/gemini-api/docs/zdr
- 상세 Spring–FastAPI 계약: `spring-fastapi-contract.md`
- 평가·비용 정책 반영 상태: `final-policy-implementation-status.md`
