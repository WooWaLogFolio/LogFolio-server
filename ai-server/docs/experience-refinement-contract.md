# Spring–FastAPI 경험 다듬기 계약

이 API는 기존 Experience 하나를 새 Source 근거로 다시 검토하여 수정 제안과 확인 질문을 반환한다. FastAPI는 Spring DB를 직접 변경하지 않으며, `review_sessions`, `review_items`, `gap_questions`의 생성·저장·상태 전이는 Spring이 담당한다.

## 호출 API

```text
POST /api/v1/experience-refinements
Content-Type: application/json
X-Internal-API-Key: <shared-secret>
```

## 호출 전 조건

- Spring이 사용자와 프로젝트 접근 권한을 확인한다.
- Spring이 `reviewSessionId`를 생성하고 세션 상태를 `IN_PROGRESS`로 저장한다.
- `sourceIds`는 `/api/v1/sources/index`에서 `INDEXED`가 확인된 Source만 전달한다.
- 대상 Experience의 기존 Claim과 Evidence 연결을 함께 전달한다.
- 기존 Experience와 연결된 Evidence를 재검색하려면 `experience.evidences[].sourceId`와 `chunkId`가 필요하다.
- `UPLOADED`, `PROCESSING`, `FAILED` Source로는 이 API를 호출하지 않는다.

## 요청 예시

```json
{
  "reviewSessionId": "10000000-0000-0000-0000-000000000001",
  "projectId": "20000000-0000-0000-0000-000000000001",
  "sourceIds": ["30000000-0000-0000-0000-000000000001"],
  "experience": {
    "experienceId": "40000000-0000-0000-0000-000000000001",
    "title": "기존 경험 제목",
    "summary": "기존 경험 요약",
    "claims": [
      {"sectionType": "ACTION", "content": "기존에 저장된 실행 내용"}
    ],
    "evidenceIds": ["50000000-0000-0000-0000-000000000001"],
    "evidences": [
      {
        "evidenceId": "50000000-0000-0000-0000-000000000001",
        "sourceId": "30000000-0000-0000-0000-000000000002",
        "chunkId": "60000000-0000-0000-0000-000000000001"
      }
    ]
  },
  "projectContext": {
    "name": "LogFolio",
    "description": "프로젝트 경험을 근거 중심으로 정리하는 서비스",
    "activityType": "TEAM_PROJECT",
    "userRole": "AI 서버 개발"
  },
  "corrections": [],
  "answers": []
}
```

## 응답 예시

```json
{
  "reviewSessionId": "10000000-0000-0000-0000-000000000001",
  "projectId": "20000000-0000-0000-0000-000000000001",
  "experienceId": "40000000-0000-0000-0000-000000000001",
  "status": "REVIEW_READY",
  "summary": "새 Source를 반영한 경험 다듬기 제안입니다.",
  "reviewItems": [
    {
      "itemType": "ACTION",
      "originalContent": "기존에 저장된 실행 내용",
      "proposedContent": "새 근거를 포함한 실행 내용",
      "evidences": [
        {
          "sourceId": "30000000-0000-0000-0000-000000000001",
          "sourceType": "PROJECT_FILE",
          "chunkId": "70000000-0000-0000-0000-000000000001",
          "pageNumber": 2,
          "excerpt": "제안 내용의 실제 원문"
        }
      ],
      "requiresUserConfirmation": false,
      "conflict": false,
      "conflictReason": null
    }
  ],
  "questions": [],
  "sourceWarnings": [],
  "noUpdateReason": null,
  "aiUsage": null
}
```

## 응답 상태와 Spring 처리

| FastAPI 상태 | 의미 | Spring 처리 |
| --- | --- | --- |
| `REVIEW_READY` | 제안 또는 확인 질문이 있음 | `review_items`, `gap_questions` 저장 후 사용자에게 표시 |
| `NO_UPDATE` | 새 근거 기반 변경점이 없음 | 빈 세션을 남기지 말고 완료 처리 또는 안내 후 종료 |
| `NEEDS_ADDITIONAL_SOURCE` | 분석 가능한 근거가 부족함 | 추가 자료 안내 후 세션 종료 |

Spring은 응답 저장이 모두 성공한 뒤 세션을 사용자 검토 가능 상태로 전환한다. FastAPI 오류나 저장 실패가 발생하면 세션을 실패 상태로 전환하고 빈 `IN_PROGRESS` 세션을 유지하지 않는다.

## 역할 경계

### FastAPI

- 프로젝트 범위 RAG 검색
- 기존 Experience와 새 Source 비교
- 근거가 있는 수정 제안 생성
- 변경 없는 Claim 제거
- 최대 2개의 확인 질문 생성
- Evidence·AI Policy 검증
- 제안·질문 응답 반환

### Spring

- 사용자 인증과 프로젝트 권한 확인
- Source 파일 저장·텍스트 추출·인덱싱 순서 보장
- Review Session 생성과 상태 전이
- FastAPI 호출과 타임아웃·재시도
- `review_items`, `gap_questions`, Evidence 관계 저장
- 사용자의 승인·수정·거절 처리
- 최종 Experience 반영

## 기존 API와의 관계

- 프로젝트 전체에서 새 경험 후보를 찾는 기능은 기존 `POST /api/v1/analyses`를 사용한다.
- 기존 경험 하나를 다듬는 기능만 `POST /api/v1/experience-refinements`를 사용한다.
- 두 API 모두 같은 RAG·LLM·Evidence·Policy 검증 파이프라인을 사용한다.
- 이 추가 API는 기존 분석 API의 요청·응답이나 Spring ERD를 변경하지 않는다.
