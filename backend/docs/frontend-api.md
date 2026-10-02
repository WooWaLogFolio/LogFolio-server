# LogFolio frontend API mapping

첨부된 로그인/온보딩, 경험 아카이브, 경험 정리하기, 경험 폴더, 설정 화면을 기준으로 정리한 API 계약입니다.

## 화면별 API

### 로그인, 회원가입, 온보딩

- `POST /api/auth/signup`: 이메일 회원가입과 세션 로그인
- `POST /api/auth/login`: 이메일 로그인
- `GET /api/auth/login/{naver|kakao}`: 소셜 로그인 시작
- `GET /api/auth/oauth2/pending-signup`: 이메일 미제공 소셜 사용자의 추가 가입 상태
- `POST /api/auth/oauth2/complete-signup`: 직접 입력한 이메일로 소셜 가입 완료
- `POST /api/auth/password-reset/request`: 비밀번호 재설정 요청
- `POST /api/auth/password-reset/confirm`: 재설정 토큰으로 비밀번호 변경
- `GET /api/auth/me`: 현재 로그인 사용자
- `POST /api/users/me/onboarding/complete`: 온보딩 완료 또는 건너뛰기

#### 이메일 미제공 소셜 가입 흐름

1. 프론트는 로그인 버튼에서 `GET /api/auth/login/{provider}`로 브라우저를 이동시킵니다.
2. 공급자가 이메일을 제공하면 기존처럼 `OAUTH2_SUCCESS_REDIRECT_URI`로 이동합니다.
3. 신규 사용자인데 이메일을 제공하지 않으면 `OAUTH2_SIGNUP_REDIRECT_URI`의 추가 가입 화면으로 이동합니다.
4. 추가 가입 화면은 `GET /api/auth/oauth2/pending-signup`을 호출해 공급자와 추천 이름을 조회합니다.
5. `GET /api/auth/csrf`에서 받은 토큰을 사용해 다음 요청을 보냅니다.

```http
POST /api/auth/oauth2/complete-signup
Content-Type: application/json
X-XSRF-TOKEN: {token}

{"email":"user@example.com"}
```

6. 성공하면 사용자 응답과 함께 세션이 일반 `ROLE_USER` 세션으로 전환됩니다. 이후 `/api/auth/me`와 일반 API를 호출할 수 있습니다.
7. 입력한 이메일이 기존 계정에 사용 중이면 `409 Conflict`를 반환합니다. 사용자는 기존 방식으로 로그인한 후 설정 화면의 소셜 계정 연동 기능을 사용해야 합니다.

모든 요청에 `credentials: "include"`를 사용해야 가입 대기 세션과 완료된 로그인 세션이 유지됩니다.

### 경험 아카이브

- `GET /api/archive`: 프로젝트/경험/30초 기록 집계와 홈 데이터
- `GET|POST /api/projects`: 내 프로젝트 목록과 생성
- `GET|PUT|DELETE /api/projects/{id}`: 프로젝트 상세, 수정, 삭제
- `GET|POST /api/quick-logs`: 전체/프로젝트별 30초 기록과 새 기록
- `PATCH /api/quick-logs/{id}`: 기록 내용 수정
- `PUT /api/quick-logs/{id}/project`: 프로젝트 연결/변경/해제
- `DELETE /api/quick-logs/{id}`: 기록 삭제

### 경험 정리하기 4단계

1. 프로젝트 정보: 프로젝트 API
2. 자료 추가: `POST /api/projects/{projectId}/files`
3. AI 해석 확인: 분석 실행 및 후보 API
4. 경험 후보: 포함 후보 확정 API

- `POST /api/projects/{projectId}/analysis-runs`: 분석 작업 생성
- `GET /api/analysis-runs/{runId}`: 처리 상태 폴링
- `GET /api/analysis-runs/{runId}/candidates`: 발견한 경험 후보
- `PUT /api/experience-candidates/{candidateId}`: 후보 수정/포함/제외
- `POST /api/analysis-runs/{runId}/finalize`: 포함 후보를 경험 카드로 생성

분석 실행 상태는 `QUEUED -> PROCESSING -> COMPLETED|FAILED`, 후보 상태는 `PENDING -> INCLUDED|EXCLUDED`입니다.

### 경험 폴더와 경험 카드

- `GET|POST /api/projects/{projectId}/experiences`: 경험 목록/직접 작성
- `GET|PUT|DELETE /api/experiences/{id}`: 경험 상세/수정/삭제
- `GET /api/experiences/{id}/evidence`: 연결된 근거 목록
- `GET /api/evidence/{id}`: 파일 페이지나 30초 기록 원문
- `POST /api/experiences/{id}/review-sessions`: AI 다듬기 시작
- `GET /api/review-sessions/{id}`: 다듬기 결과와 진행 상태
- `PUT /api/review-items/{id}`: AI 제안 승인/수정/거절
- `POST /api/review-sessions/{id}/complete`: 다듬기 완료
- `GET /api/experiences/{id}/gap-questions`: 보완 질문
- `POST /api/gap-questions/{id}/answers`: 직접/제안 답변 저장

경험 상태는 화면 필터와 동일하게 `ORGANIZING`, `REVIEW_REQUIRED`, `SUPPLEMENT_REQUIRED`, `SAVED` 값을 사용합니다.

### 설정

- `GET|PUT|DELETE /api/users/me`: 계정 조회/수정/탈퇴
- `PATCH /api/users/me/name`: 이름 변경
- `PUT /api/users/me/password`: 현재 비밀번호 확인 후 변경
- `GET /api/users/me/auth-accounts`: 소셜 연동 상태
- `GET /api/users/me/auth-accounts/{provider}/link`: 연동 시작
- `DELETE /api/users/me/auth-accounts/{provider}`: 연동 해제
- `GET /api/storage`: 사용량, 한도, 전체 파일
- `GET /api/projects/{projectId}/files`: 프로젝트 파일
- `DELETE /api/files/{fileId}`: 파일 삭제

## 공통 규칙

- 모든 사용자 데이터 API는 요청의 `userId`를 받지 않고 세션 사용자를 기준으로 접근 권한을 검사합니다.
- 다른 사용자의 리소스에는 `404`를 반환해 존재 여부를 노출하지 않습니다.
- 상태 변경 요청은 `JSESSIONID` 쿠키와 `X-XSRF-TOKEN` 헤더가 필요합니다.
- 파일은 PDF/PPT/PPTX/DOC/DOCX/FIG, 파일당 최대 50MB, 사용자당 기본 1GB입니다.
- AI 분석과 다듬기는 비동기 계약입니다. 현재 서버는 작업과 상태 저장을 담당하며 실제 모델 작업자는 별도 연동 대상입니다.
- 비밀번호 재설정은 이벤트까지 발행하며 실제 이메일 전송기는 별도 연동 대상입니다.
