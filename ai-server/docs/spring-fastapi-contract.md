# Spring–FastAPI 분석 계약

이 문서는 Spring 서버가 LogFolio FastAPI AI 서버를 호출할 때 사용하는 내부 계약입니다. 사용자 인증과 프로젝트 접근 권한은 Spring이 먼저 확인하며, FastAPI는 브라우저에서 직접 호출하지 않습니다.

## 1. Source 자동 전처리·인덱싱

Spring은 Project File 또는 Quick Log 저장이 끝나면 아래 API를 호출합니다. 이 API는 LLM 분석을 실행하지 않고 Source를 검색 가능한 상태로만 만듭니다.

```text
POST /api/v1/sources/index
Content-Type: application/json
X-Internal-API-Key: <shared-secret>
```

```json
{
  "projectId": "20000000-0000-0000-0000-000000000001",
  "sources": [
    {
      "sourceId": "30000000-0000-0000-0000-000000000001",
      "sourceType": "PROJECT_FILE",
      "sourceName": "project-report.pdf",
      "mimeType": "application/pdf",
      "contentHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "pages": [{"pageNumber": 1, "text": "프로젝트 팀은 인터뷰를 진행했다."}]
    },
    {
      "sourceId": "30000000-0000-0000-0000-000000000002",
      "sourceType": "QUICK_LOG",
      "sourceName": "30초 기록",
      "pages": [{"text": "내가 인터뷰 질문지를 작성했다."}]
    }
  ]
}
```

- `sourceType`: `PROJECT_FILE` 또는 `QUICK_LOG`
- `contentHash`: 원본 파일 바이트의 SHA-256 소문자 64자리. Quick Log는 저장된 원문 UTF-8의 SHA-256 권장
- 요청당 Source는 최대 20개
- 각 Source는 독립 처리하며 일부가 실패해도 성공한 Source는 `INDEXED`로 유지
- 같은 `projectId + sourceId`를 다시 보내면 기존 Chunk를 교체하므로 중복 저장하지 않음
- 같은 프로젝트에서 다른 `sourceId`가 동일한 `contentHash`를 가지면 임베딩하지 않고 `DUPLICATE` 반환
- `contentHash`가 없으면 FastAPI가 전달된 페이지 텍스트로 보조 해시를 계산하지만, 원본 파일 중복 판정은 Spring이 만든 해시가 더 정확함
- 유사한 자료나 수정본은 중복으로 간주하지 않으며 MVP에서는 완전히 동일한 자료만 처리

응답 예시:

```json
{
  "projectId": "20000000-0000-0000-0000-000000000001",
  "indexedCount": 1,
  "duplicateCount": 1,
  "failedCount": 0,
  "items": [
    {
      "sourceId": "30000000-0000-0000-0000-000000000001",
      "sourceType": "PROJECT_FILE",
      "status": "INDEXED",
      "chunkCount": 2,
      "duplicateOfSourceId": null,
      "errorCode": null
    },
    {
      "sourceId": "30000000-0000-0000-0000-000000000002",
      "sourceType": "PROJECT_FILE",
      "status": "DUPLICATE",
      "chunkCount": 0,
      "duplicateOfSourceId": "30000000-0000-0000-0000-000000000001",
      "errorCode": null
    }
  ]
}
```

응답의 `items[].status`는 `INDEXED`, `DUPLICATE`, `FAILED`입니다. 여기서 `DUPLICATE`는 영구적인 Source State가 아니라 인덱싱 요청 결과입니다. `DUPLICATE`이면 Spring은 새 Source가 기존 `duplicateOfSourceId`와 완전히 동일함을 사용자에게 안내하고, 새 Source를 분석 대상에 넣지 않습니다. 기존 Source와 Evidence는 그대로 유지합니다. 새 Source DB 행을 생성하기 전 해시를 검사하는 방식을 권장하며, 이미 행을 만든 뒤 FastAPI를 호출한다면 해당 행을 어떻게 정리할지는 Spring 트랜잭션 정책으로 결정해야 합니다.

## 2. 프로젝트 AI 분석

```text
POST /api/v1/analyses
Content-Type: application/json
X-Internal-API-Key: <shared-secret>
```

운영 환경에서는 Spring과 FastAPI에 동일한 내부 API 키를 Secret으로 주입합니다. 키를 Git, Notion, 로그 또는 오류 응답에 기록하지 않습니다. `/health`는 배포 상태 확인을 위해 인증 대상에서 제외합니다.

## Request

```json
{
  "analysisRunId": "10000000-0000-0000-0000-000000000001",
  "projectId": "20000000-0000-0000-0000-000000000001",
  "sourceIds": [
    "30000000-0000-0000-0000-000000000001",
    "30000000-0000-0000-0000-000000000002"
  ],
  "projectContext": {
    "name": "LogFolio",
    "description": "프로젝트 경험을 근거 중심으로 정리하는 서비스",
    "activityType": "TEAM_PROJECT",
    "userRole": "AI 서버 개발"
  },
  "confirmedSourceIds": [],
  "existingExperiences": [
    {
      "experienceId": "60000000-0000-0000-0000-000000000001",
      "title": "사용자 인터뷰 설계",
      "summary": "인터뷰 질문지를 설계한 경험",
      "claims": [{"sectionType": "ACTION", "content": "질문지를 작성했다."}],
      "evidenceIds": ["70000000-0000-0000-0000-000000000001"],
      "evidences": [
        {
          "evidenceId": "70000000-0000-0000-0000-000000000001",
          "sourceId": "30000000-0000-0000-0000-000000000003",
          "chunkId": "80000000-0000-0000-0000-000000000001"
        }
      ]
    }
  ],
  "corrections": []
}
```

규칙:

- 모든 ID는 UUID 문자열
- JSON 필드는 camelCase
- `sourceIds`는 이번 Analysis Run에 새로 반영할 `INDEXED` Source이며 최대 50개
- `projectContext`는 다른 프로젝트 자료 의심 판별에 쓰는 최소 프로젝트 설명. 없으면 FastAPI는 임의 판별하지 않음
- `confirmedSourceIds`는 사용자가 `그래도 포함`을 선택한 Source ID. 반드시 이번 `sourceIds`에 포함되어야 함
- `existingExperiences`에는 현재 프로젝트의 기존 Experience 요약·Claim·Evidence ID를 전달
- `evidences`의 `sourceId + chunkId`는 관련 Experience가 선택됐을 때 FastAPI가 기존 Evidence 원문을 정확히 다시 조회하는 키
- `corrections`에는 사용자가 이전에 수정하거나 거절한 내용을 전달
- Spring이 S3 원본을 보관하고 파일 텍스트를 추출
- 동일 분석 작업의 재시도에는 같은 `analysisRunId` 사용
- `projectId`의 접근 권한과 삭제 상태를 Spring에서 확인한 뒤 호출
- 이전 `documents` 직접 전달 방식은 하위 호환용이며 신규 연동에서는 사용하지 않음

분석 순서:

```text
새 Source 검색
→ Existing Experience 전체의 제목·요약·Claim과 의미 비교
→ 거리 기준을 통과한 관련 Experience를 최대 3개 선택
→ 선택된 Experience의 evidence chunkId로 기존 원문 조회
→ 새 Source + 관련 기존 Evidence를 LLM에 전달
→ 최종 분류
```

기본 의미 거리 기준은 `0.4`이며 운영 평가 데이터로 조정합니다. 기준을 통과하지 못한 Experience는 강제로 보강 대상으로 연결하지 않습니다.

### 다른 프로젝트 자료 의심 응답

프로젝트 Context와 Source의 가장 가까운 Chunk 거리가 설정 기준보다 크면 분석·LLM 호출을 잠시 멈추고 다음 형태로 반환합니다.

```json
{
  "analysisRunId": "10000000-0000-0000-0000-000000000001",
  "projectId": "20000000-0000-0000-0000-000000000001",
  "summary": "현재 프로젝트와 관련성이 낮아 보이는 Source가 있습니다.",
  "candidates": [],
  "questions": [],
  "sourceWarnings": [
    {
      "sourceId": "30000000-0000-0000-0000-000000000002",
      "sourceName": "other-project.pdf",
      "warningType": "POSSIBLE_PROJECT_MISMATCH",
      "distance": 0.91,
      "message": "현재 프로젝트와 관련성이 낮아 보이는 자료입니다. 이번 분석에서 제외할지, 그래도 포함할지 확인해주세요.",
      "allowedActions": ["EXCLUDE_FROM_ANALYSIS", "INCLUDE_ANYWAY"]
    }
  ],
  "resultTypes": ["NEEDS_CONTEXT"],
  "noUpdateReason": null
}
```

Spring 재호출 규칙:

- `EXCLUDE_FROM_ANALYSIS`: 해당 ID를 다음 요청의 `sourceIds`에서 제외
- `INCLUDE_ANYWAY`: 해당 ID를 `sourceIds`와 `confirmedSourceIds` 양쪽에 포함
- Source 자체는 삭제·이동하거나 `INDEXED` 상태를 변경하지 않음
- `confirmedSourceIds`는 이번 분석 요청에만 적용하며 영구적인 프로젝트 소속 확정값이 아님
- 검색 결과가 없는 Source는 이 판별에서 확정하지 않고 기존 Retrieval 0건 정책으로 처리

## Success response

```json
{
  "analysisRunId": "10000000-0000-0000-0000-000000000001",
  "projectId": "20000000-0000-0000-0000-000000000001",
  "inputSourceIds": [
    "30000000-0000-0000-0000-000000000001",
    "30000000-0000-0000-0000-000000000002"
  ],
  "referencedSourceIds": [
    "30000000-0000-0000-0000-000000000003"
  ],
  "summary": "프로젝트 자료를 분석한 AI 초안입니다.",
  "candidates": [
    {
      "candidateId": "40000000-0000-0000-0000-000000000001",
      "resultType": "EXISTING_UPDATE",
      "targetExperienceId": "60000000-0000-0000-0000-000000000001",
      "conflict": false,
      "conflicts": [],
      "title": "인증 기능 구현 경험",
      "summary": "JWT 인증 기능을 구현한 경험입니다.",
      "claims": []
    }
  ],
  "questions": [
    {
      "questionId": "50000000-0000-0000-0000-000000000001",
      "candidateId": "40000000-0000-0000-0000-000000000001",
      "targetSection": "RESULT",
      "question": "인증 기능을 적용한 후 어떤 변화가 있었나요?",
      "suggestedAnswers": []
    }
  ],
  "informationNeed": "USER_ANSWER",
  "informationNeedReason": null,
  "resultTypes": ["EXISTING_UPDATE", "NEEDS_CONTEXT"],
  "noUpdateReason": null
}
```

- `resultType`: `EXISTING_UPDATE` 또는 `NEW_EXPERIENCE`
- `inputSourceIds`: Spring이 이번 분석 대상으로 보낸 새 Source 스냅샷
- `referencedSourceIds`: RAG가 관련 기존 Experience Evidence에서 실제로 추가 조회한 누적 Source 스냅샷
- 두 목록은 LLM 출력이 아니라 FastAPI가 실제 요청·검색 결과로 확정
- 질문이 있으면 `informationNeed=USER_ANSWER`, `resultTypes`에 `NEEDS_CONTEXT` 포함
- 후보·질문이 없더라도 `informationNeed=ADDITIONAL_SOURCE`이면 자료 보완이 필요한 상태이며 `NO_UPDATE`가 아님
- `informationNeed`도 없고 후보·질문·경고가 모두 없을 때만 `NO_UPDATE`
- `EXISTING_UPDATE`는 요청에 포함된 기존 Experience의 `targetExperienceId` 필수
- 기존 사용자 확정값과 충돌하면 `conflict=true`; FastAPI가 자동 덮어쓰지 않음
- `conflict=true`이면 `conflicts`에 기존 확정 문장, 새 제안 문장, 충돌 이유를 반드시 포함
- `conflicts[].existingContent`는 요청의 해당 Existing Experience Claim 또는 사용자 수정값과 정확히 일치해야 함
- `conflicts[].proposedContent`는 같은 Candidate의 동일 `sectionType` Claim과 정확히 일치해야 함
- 경험 후보는 최대 3개
- 보완 질문은 최대 2개

### 기존 Experience 충돌 응답

```json
{
  "candidateId": "40000000-0000-0000-0000-000000000002",
  "resultType": "EXISTING_UPDATE",
  "targetExperienceId": "60000000-0000-0000-0000-000000000001",
  "conflict": true,
  "conflicts": [
    {
      "sectionType": "ACTION",
      "existingContent": "인터뷰 질문지를 설계했다.",
      "proposedContent": "인터뷰 진행까지 담당했다.",
      "reason": "기존 확정 내용과 새 자료의 담당 범위가 다릅니다."
    }
  ],
  "title": "사용자 인터뷰 경험",
  "summary": "기존 확정 내용과 새 근거의 차이를 확인해야 합니다.",
  "claims": [
    {
      "sectionType": "ACTION",
      "content": "인터뷰 진행까지 담당했다.",
      "subjectType": "UNKNOWN",
      "provenanceType": "AI_INFERRED",
      "verificationStatus": "NEEDS_CONFIRMATION",
      "evidenceType": "NONE",
      "evidences": [],
      "policyViolations": [],
      "requiresUserConfirmation": true
    }
  ]
}
```

처리 원칙:

- FastAPI는 기존 Experience를 수정하거나 새 Source를 버리지 않음
- Spring은 기존 값과 새 제안을 함께 `review_items`에 저장하고 사용자 선택을 받음
- 사용자가 승인하거나 수정한 뒤에만 최종 Experience 반영
- 사용자가 기존 값을 유지하면 새 제안을 자동으로 다시 적용하지 않도록 Correction/Review 결과를 다음 분석 요청에 전달
- AI가 요청에 없는 기존 문장을 충돌 대상으로 반환하면 `INVALID_CONFLICT_REFERENCE`로 분석 결과를 거부

### 정보 부족 분류

`NEEDS_CONTEXT`는 다음 두 흐름으로 구분합니다.

| informationNeed | 판단 | Spring UX |
| --- | --- | --- |
| `USER_ANSWER` | 의미 있는 경험 단서가 있고 질문 1~2개로 보완 가능 | 반환된 `questions`에 답변 받기 |
| `ADDITIONAL_SOURCE` | 자료가 너무 모호하여 질문 1~2개로 경험 특정 불가 | `30초 기록 남기기`, `자료 추가하기` 안내 |

추가 자료가 필요한 응답 예시:

```json
{
  "analysisRunId": "10000000-0000-0000-0000-000000000001",
  "projectId": "20000000-0000-0000-0000-000000000001",
  "summary": "아직 경험으로 정리하기에는 정보가 부족합니다.",
  "candidates": [],
  "questions": [],
  "sourceWarnings": [],
  "informationNeed": "ADDITIONAL_SOURCE",
  "informationNeedReason": "구체적인 행동이나 중요한 결정을 확인할 수 있는 기록이 필요합니다.",
  "resultTypes": ["NEEDS_CONTEXT"],
  "noUpdateReason": null
}
```

이 경우 Spring은 기존 Source를 `INDEXED`로 유지하고 별도의 보류 상태로 바꾸지 않습니다. 새 Quick Log 또는 Project File이 추가되면 다음 Analysis Run에서 기존 Source와 함께 다시 사용합니다.

### Review 진행 중 새 Source 추가

- Spring은 `analysisRunId + inputSourceIds + referencedSourceIds`를 Analysis Run 근거 스냅샷으로 저장
- Review Item은 이 Analysis Run 결과에만 연결
- Review가 진행되는 중 새 Source가 저장되면 정상적으로 전처리하여 `INDEXED`로 유지
- 새 Source를 진행 중인 Review 또는 기존 `inputSourceIds`에 추가하지 않음
- 사용자가 현재 Review를 이어갈 때는 기존 Candidate·Question을 그대로 제공
- 새 Source는 다음 사용자 실행에서 새로운 `analysisRunId`와 함께 전달
- 동일 Analysis Run의 재시도라면 최초 Source 목록을 유지하여 결과 기준이 바뀌지 않게 함

FastAPI는 응답에 실제 요청 Source 목록을 다시 넣어 반환하지만 Review Session 상태와 다음 분석 대상 여부는 Spring이 관리합니다.
- `questions[].candidateId`는 응답에 포함된 경험 후보를 가리킴
- 근거가 부족해 경험 후보 자체를 만들 수 없는 질문은 `candidateId`가 `null`일 수 있음
- 결과는 AI 초안이며 바로 경험 DB에 확정 저장하지 않음
- Spring은 사용자 승인·수정·거절 이후에만 확정 상태로 저장

## Spring persistence mapping

새로운 Claim 테이블을 만들지 않고 기존 ERD를 다음과 같이 사용합니다.

| AI response | Spring ERD |
| --- | --- |
| 경험 후보와 전체 AI 원본 | `experience_candidates`, `draft_content` |
| 검토할 Claim의 `content` | `review_items.proposed_content` |
| Claim의 `sectionType` | `review_items.item_type` |
| 사용자가 승인·수정한 내용 | `review_items.confirmed_content` |
| 승인·수정·거절 상태 | `review_items.decision` |
| Evidence의 `excerpt` | `evidence_items.excerpt` |
| Evidence와 검토 항목 연결 | `review_item_evidence` |

Spring ERD에는 연동 구현 전에 다음 변경이 필요합니다.

- `gap_questions.candidate_id` nullable 컬럼 추가
- `gap_questions.experience_id` nullable 변경
- 경험 확정 전 질문은 `candidate_id`, 확정 후에는 `experience_id`로 연결
- `evidence_items.chunk_id` nullable 컬럼 추가
- `evidence_items.page_number` nullable 컬럼 추가
- `location`은 `3페이지`처럼 사용자에게 보여줄 표현으로 유지

## Error response

```json
{
  "code": "ANALYSIS_TIMEOUT",
  "message": "AI 분석 제한 시간을 초과했습니다.",
  "details": []
}
```

Spring 처리 기준:

| HTTP 상태 | 처리 |
| --- | --- |
| 400, 401, 404, 422 | 요청·권한·계약 오류이므로 자동 재시도하지 않음 |
| 502, 503, 504 | 분석 API는 FastAPI 내부 재시도가 이미 끝난 결과이므로 Spring 자동 재시도 금지 |
| 그 외 5xx | 분석 실패 상태를 저장하고 사용자의 명시적 재실행만 허용 |

`/api/v1/sources/index`는 멱등적인 Chunk 교체 요청이므로 Spring이 일시적 오류에 최대 1회 재시도할 수 있습니다. `/api/v1/analyses`의 Gemini 호출은 FastAPI가 Timeout, 일시적 Provider 오류, Structured Output 실패에 한해 내부에서 최대 1회 재시도합니다. 인증 실패나 잘못된 요청 같은 비일시적 4xx는 재시도하지 않습니다.

Evidence 부분 실패는 HTTP 오류로 전체 분석을 중단하지 않습니다.

- 검색되지 않은 `chunkId`, 원문과 다른 인용문, 잘못된 페이지가 포함된 Claim만 제외
- 같은 Candidate에 정상 Claim이 남아 있으면 Candidate 유지
- 모든 Claim이 제외된 Candidate는 Review 대상으로 반환하지 않음
- 제외된 Candidate를 가리키던 질문은 `candidateId=null`로 유지하여 사용자 확인 가능
- 정상 Candidate와 질문이 모두 없으면 `NO_UPDATE`와 사유 반환

Retrieval 결과가 0건인 경우:

- 기존 Experience에 강제로 연결하지 않음
- 요청된 `projectId + sourceIds` 범위의 새 Source Chunk 자체를 추가 조회
- 새 Source Chunk가 있으면 `retrievalFallback=true`로 LLM에 전달하여 `NEW_EXPERIENCE / NEEDS_CONTEXT / NO_UPDATE` 판단
- 새 Source Chunk도 없으면 LLM을 호출하지 않고 `NO_UPDATE` 반환
- Source가 아직 `INDEXED`되지 않았거나 텍스트가 없는 경우를 `noUpdateReason`으로 전달

## Timeout

- FastAPI 전체 분석 제한: 30초
- Spring 연결 제한 권장값: 3초
- Spring 응답 제한 권장값: 35초
- Gemini 단일 시도 제한: 14초
- Gemini 내부 자동 재시도: 최대 1회, 총 호출 최대 2회
- Spring 분석 API 자동 재시도: 없음
- 사용자가 같은 분석을 반복 요청하는 UI 재시도와 서버 자동 재시도를 구분

Spring이 타임아웃으로 연결을 종료하더라도 FastAPI 작업이 완료됐을 가능성이 있으므로 동일 작업에는 기존 `analysisRunId`를 유지합니다.

## Environment variables

FastAPI:

```text
LOGFOLIO_AI_INTERNAL_AUTH_REQUIRED=true
LOGFOLIO_AI_INTERNAL_API_KEY=<shared-secret>
LOGFOLIO_AI_ANALYSIS_TIMEOUT_SECONDS=30
```

Spring의 환경변수 이름은 Spring 담당자가 정하되, Base URL과 내부 API 키를 코드에 하드코딩하지 않습니다.
