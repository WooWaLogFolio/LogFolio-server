# Spring–FastAPI 분석 계약

이 문서는 Spring 서버가 LogFolio FastAPI AI 서버를 호출할 때 사용하는 내부 계약입니다. 사용자 인증과 프로젝트 접근 권한은 Spring이 먼저 확인하며, FastAPI는 브라우저에서 직접 호출하지 않습니다.

## Endpoint

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
  "documents": [
    {
      "projectFileId": "30000000-0000-0000-0000-000000000001",
      "originalName": "project-report.pdf",
      "mimeType": "application/pdf",
      "pages": [
        {
          "pageNumber": 1,
          "text": "프로젝트 팀은 사용자 인터뷰를 진행했다."
        }
      ]
    }
  ]
}
```

규칙:

- 모든 ID는 UUID 문자열
- JSON 필드는 camelCase
- 파일은 1개 이상, 최대 3개
- Spring이 S3 원본을 보관하고 텍스트를 추출
- 동일 분석 작업의 재시도에는 같은 `analysisRunId` 사용
- `projectId`의 접근 권한과 삭제 상태를 Spring에서 확인한 뒤 호출

## Success response

```json
{
  "analysisRunId": "10000000-0000-0000-0000-000000000001",
  "projectId": "20000000-0000-0000-0000-000000000001",
  "summary": "프로젝트 자료를 분석한 AI 초안입니다.",
  "candidates": [
    {
      "candidateId": "40000000-0000-0000-0000-000000000001",
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
  ]
}
```

- 경험 후보는 최대 3개
- 보완 질문은 최대 2개
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
| 502, 503, 504 | 일시적 AI·DB·타임아웃 오류일 수 있으므로 동일 `analysisRunId`로 최대 1회 재시도 |
| 그 외 5xx | 실패 로그를 남기고 자동 재시도는 최대 1회로 제한 |

## Timeout

- FastAPI 전체 분석 제한: 30초
- Spring 연결 제한 권장값: 3초
- Spring 응답 제한 권장값: 35초
- 자동 재시도: 최대 1회
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
