# Backend

LogFolio 메인 백엔드 서버 디렉터리입니다.

## 네이버·카카오 로그인

세션 기반 Spring Security OAuth2 로그인을 사용합니다.

### 환경 변수

```text
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
KAKAO_CLIENT_ID=...
KAKAO_CLIENT_SECRET=... # 카카오 보안 설정에서 Client Secret을 사용하지 않으면 생략 가능
OAUTH2_SUCCESS_REDIRECT_URI=http://localhost:5173/oauth2/success
OAUTH2_SIGNUP_REDIRECT_URI=http://localhost:5173/oauth2/complete-signup
```

각 개발자 콘솔에 다음 Redirect URI를 등록합니다.

```text
네이버: http://localhost:8080/login/oauth2/code/naver
카카오: http://localhost:8080/login/oauth2/code/kakao
```

네이버는 회원 이름과 이메일 동의항목을 사용합니다. 카카오는 앱에 활성화되지 않은 동의항목으로 인한
`KOE205`를 피하기 위해 인가 요청에서 개인정보 scope를 강제하지 않습니다. 카카오 앱에 설정된 정보가
응답되면 사용하고, 이메일이 없으면 추가 가입 화면에서 직접 입력받습니다. 운영 환경에서는
`localhost:8080`을 실제 API 도메인으로 교체합니다.

### 엔드포인트

- 네이버 로그인: `GET /oauth2/authorization/naver`
- 카카오 로그인: `GET /oauth2/authorization/kakao`
- 로그인 사용자: `GET /api/auth/me`
- 이메일 미제공 소셜 가입 정보: `GET /api/auth/oauth2/pending-signup`
- 이메일 미제공 소셜 가입 완료: `POST /api/auth/oauth2/complete-signup`
- 내 프로필 조회/수정/탈퇴: `GET|PUT|DELETE /api/users/me`
- 내 프로젝트 목록/생성: `GET|POST /api/projects`
- 내 프로젝트 조회/수정/삭제: `GET|PUT|DELETE /api/projects/{id}`
- CSRF 토큰 발급: `GET /api/auth/csrf`
- 로그아웃: `POST /api/auth/logout`

브라우저 요청에는 세션 쿠키를 포함해야 합니다. 상태를 변경하는 요청은 `/api/auth/csrf` 응답의 토큰을 `X-XSRF-TOKEN` 헤더로 전달합니다.

소셜 공급자가 이메일을 제공하지 않은 신규 사용자는 `OAUTH2_SIGNUP_REDIRECT_URI`로 이동합니다.
이 세션은 가입 대기 권한만 가지므로 일반 사용자 API에는 접근할 수 없습니다. 프론트는
`GET /api/auth/oauth2/pending-signup`으로 공급자와 추천 이름을 표시하고, 사용자가 입력한 이메일을
`POST /api/auth/oauth2/complete-signup`의 `{ "email": "user@example.com" }` 본문으로 전송합니다.
이미 가입된 이메일은 계정 탈취를 막기 위해 자동 병합하지 않고 `409 Conflict`를 반환합니다.

프로젝트 API는 요청으로 사용자 ID를 받지 않고 로그인 세션의 사용자 ID를 사용합니다. 다른 사용자의 프로젝트는 존재 여부가 노출되지 않도록 `404 Not Found`를 반환합니다.

## 데이터베이스 스키마

- 논리 ERD: [`docs/logfolio-erd.dbml`](docs/logfolio-erd.dbml)
- 실행 스키마: [`src/main/resources/db/migration/V1__initial_schema.sql`](src/main/resources/db/migration/V1__initial_schema.sql)

스키마는 PostgreSQL을 기준으로 하며 Flyway가 적용합니다. JPA는 `validate` 모드이므로 엔티티와 실제 스키마가 다르면 애플리케이션 시작 단계에서 실패합니다. 기존에 Hibernate `ddl-auto=update`로 만든 개발 DB에는 Flyway 이력이 없으므로, 필요한 데이터를 백업한 뒤 빈 데이터베이스에서 시작하거나 별도의 데이터 마이그레이션을 작성해야 합니다.

Swagger UI는 `/swagger-ui.html`, OpenAPI JSON은 `/v3/api-docs`에서 확인할 수 있습니다. Swagger UI에서 상태 변경 API를 호출할 때도 로그인 세션과 CSRF 토큰이 필요합니다.

화면별 전체 API 대응표와 상태 전이는 [`docs/frontend-api.md`](docs/frontend-api.md)에 정리되어 있습니다.

## 패키지 구조

```text
com.woowa.logfolio
├── auth        # 이메일/소셜 인증, 비밀번호 재설정, 세션 principal
├── user        # 프로필, 온보딩, 계정 설정
├── archive     # 아카이브 홈 집계
├── project     # 프로젝트 CRUD
├── quicklog    # 30초 기록 CRUD와 프로젝트 연결
├── file        # 프로젝트 파일과 저장공간
├── analysis    # 비동기 분석 작업과 경험 후보
├── experience  # 경험 카드와 근거
├── evidence    # 파일/30초 기록에서 추출된 근거
├── review      # AI 다듬기, 검토 항목, 보완 질문/답변
└── global      # Spring Security와 Swagger 설정
```

각 기능 패키지는 `controller -> service -> repository/entity` 순서입니다. 컨트롤러는 HTTP/Swagger 계약, 서비스는 소유권과 상태 전이, 저장소는 사용자 범위가 포함된 쿼리를 담당합니다.
