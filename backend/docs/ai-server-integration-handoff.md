# Spring 담당자 확인 사항: FastAPI Source 인덱싱 연동

## 이번 브랜치에서 구현한 내용

- Spring 내부 `AiServerClient` 추가
- `POST /api/v1/sources/index` 요청·응답 DTO 추가
- `X-Internal-API-Key` 헤더 적용
- 연결 3초, 응답 35초 기본 제한 적용
- 5xx 또는 연결 실패에 대비한 자동 재시도 최대 1회 적용
- Quick Log 생성·수정·프로젝트 연결 후 트랜잭션 커밋 시 비동기 인덱싱
- Quick Log 처리 상태 `PROCESSING / INDEXED / FAILED` 저장
- Project File 텍스트 추출 완료 후 호출할 `AiSourceIndexService.indexExtractedProjectFile` 추가
- AI 연동이 꺼진 로컬·테스트 환경에서는 기존 Spring 기능에 영향이 없도록 기본 비활성화

## Spring 담당자가 반드시 확인·연결할 부분

### 1. 운영 환경변수

```text
AI_SERVER_ENABLED=true
AI_SERVER_BASE_URL=http://<fastapi-host>:8000
AI_SERVER_INTERNAL_API_KEY=<FastAPI와 동일한 Secret>
AI_SERVER_CONNECT_TIMEOUT=3s
AI_SERVER_READ_TIMEOUT=35s
```

- API 키는 저장소와 로그에 기록하지 않고 배포 환경 Secret으로 주입한다.
- Spring과 FastAPI가 서로 다른 키를 사용하면 모든 내부 요청이 401로 실패한다.

### 2. DB 마이그레이션

`V5__ai_source_index_state.sql`이 다음 내용을 적용한다.

- `quick_logs.processing_status` nullable 컬럼 추가
- Quick Log 상태값을 `PROCESSING / INDEXED / FAILED`로 제한
- Project File 상태값에 `INDEXED` 추가

운영 DB 적용 전 백업 및 기존 `project_files.processing_status` 값을 확인한다.

### 3. Project File 텍스트 추출 연결

현재 Spring 저장소에는 PDF·PPT·DOCX 텍스트 추출 구현이 없다. 파일 업로드만으로 FastAPI를 호출하면 안 된다.

텍스트 추출 기능이 완성되면 페이지별 결과를 아래 메서드에 전달한다.

```java
String status = aiSourceIndexService.indexExtractedProjectFile(userId, fileId, pages);
```

각 page는 다음 정보를 가진다.

```json
{
  "pageNumber": 1,
  "text": "추출된 원문"
}
```

### 4. 비동기 처리 정책

- Quick Log 저장 트랜잭션은 먼저 완료한다.
- FastAPI 인덱싱은 `aiTaskExecutor`에서 비동기로 실행한다.
- 인덱싱 실패가 Quick Log 저장 자체를 취소하지 않는다.
- 실패하면 `FAILED`로 남기며, 사용자 재시도 API 또는 운영 재처리 Job은 후속 구현이 필요하다.

### 5. 다음 연동 작업

이번 변경은 Source 인덱싱 단계까지다. 아래 항목은 별도 기능 브랜치에서 구현해야 한다.

- 사용자가 `AI 분석하기`를 누르면 `INDEXED`이며 아직 반영되지 않은 Source만 선택
- 기존 Experience 전체와 Claim·Evidence 메타데이터 조립
- Evidence의 `evidenceId + sourceId + chunkId` 전달
- `POST /api/v1/analyses` 호출
- `EXISTING_UPDATE / NEW_EXPERIENCE / NEEDS_CONTEXT / NO_UPDATE` 저장
- Review Session·Review Item·Gap Question 생성
- 사용자 승인·수정·거절 후 Experience 반영

## 변경하면 안 되는 원칙

- 브라우저가 FastAPI를 직접 호출하지 않는다.
- FastAPI 실패 때문에 이미 저장된 Quick Log나 파일을 삭제하지 않는다.
- AI 결과를 사용자 승인 전에 Experience 확정값으로 저장하지 않는다.
- 프로젝트 접근 권한은 Spring에서 먼저 검증한다.
