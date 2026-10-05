# LogFolio AI 서버 테스트 실행 가이드

작성 기준일: 2026-10-04

이 문서는 LogFolio AI 서버를 개발·연동·배포하기 전에 사용할 명령을 목적별로 정리한 실행 가이드다. 모든 명령은 저장소 루트가 `/Users/parksubin/Documents/ChatGPT/Logfolio`라고 가정한다.

## 0. 가장 자주 사용할 명령

### 코드 수정 후 가장 먼저

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/ai-server
source .venv/bin/activate
pytest
python -m logfolio_ai.evaluation.offline_suite_runner \
  --output-json evals/results/offline-suite.json
```

두 명령이 모두 성공하면 외부 API 없이 확인 가능한 기본 회귀 검증을 통과한 것이다.

### Docker까지 포함한 기본 통합 테스트

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/ai-server
docker compose --env-file deploy/.env -f deploy/docker-compose.yml config
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build postgres migrate ai-server
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile smoke run --rm smoke
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile smoke down
```

성공하면 `LogFolio AI offline contract smoke test passed`가 출력된다.

## 1. 최초 로컬 환경 준비

Python 3.11 이상이 필요하다.

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/ai-server
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

실제 로컬 E5 Embedding까지 실행하려면 추가 의존성을 설치한다.

```bash
python -m pip install -e '.[dev,embedding]'
```

E5 설치는 PyTorch CPU 패키지와 모델을 내려받으므로 첫 실행 시간이 길고 디스크를 사용한다.

터미널을 새로 열 때마다 가상환경을 다시 활성화한다.

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/ai-server
source .venv/bin/activate
```

## 2. 환경변수 파일 준비

Docker 테스트 전에 예시 파일을 복사한다.

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/ai-server
cp deploy/.env.example deploy/.env
```

`deploy/.env`에서 다음 값은 로컬 값으로 변경한다.

```dotenv
POSTGRES_DB=logfolio
POSTGRES_USER=logfolio
POSTGRES_PASSWORD=로컬에서만_사용할_비밀번호
LOGFOLIO_INTERNAL_API_KEY=로컬에서만_사용할_내부키
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
```

주의 사항:

- `deploy/.env`는 Git에 올리지 않는다.
- Gemini를 사용하지 않는 테스트에서는 `GEMINI_API_KEY`를 비워둬도 된다.
- 실제 API Key를 문서, 메신저, 커밋, 터미널 캡처에 노출하지 않는다.
- 무료 Gemini 테스트에는 합성·비식별 자료만 사용한다.

## 3. FastAPI 로컬 실행

외부 LLM을 호출하지 않는 Fake Provider가 기본값이다.

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/ai-server
source .venv/bin/activate
uvicorn logfolio_ai.main:app --app-dir src --reload
```

확인 주소:

- Health: `http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`

터미널에서 Health를 확인하려면 다음을 실행한다.

```bash
curl --fail http://localhost:8000/health
```

서버 종료는 실행 중인 터미널에서 `Ctrl+C`를 누른다.

## 4. 외부 API 없이 실행하는 테스트

### 4.1 전체 단위·통합 테스트

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/ai-server
source .venv/bin/activate
pytest
```

실패한 테스트를 자세히 보려면:

```bash
pytest -vv
```

특정 파일만 실행하려면:

```bash
pytest tests/test_api.py -vv
```

중단된 지점부터 다시 실행하려면:

```bash
pytest --lf
```

### 4.2 AI Policy 회귀 평가

```bash
python -m logfolio_ai.evaluation.runner
```

TEAM→USER 오귀속, 근거 없는 성과, 사용자 상태 위조, 중복 질문 등을 검사한다.

### 4.3 전체 Pipeline 평가

```bash
python -m logfolio_ai.evaluation.pipeline_runner \
  --dataset evals/datasets/pipeline_core_v1.json \
  --output-json evals/results/pipeline.json
```

새 Source, Existing Experience, Conflict, 정보 부족, Evidence 검증과 Policy 적용 흐름을 검사한다.

### 4.4 장애·재시도 평가

```bash
python -m logfolio_ai.evaluation.resilience_runner \
  --dataset evals/datasets/resilience_core_v1.json \
  --output-json evals/results/resilience.json
```

Timeout, 잘못된 JSON, 최대 1회 재시도, 재시도하지 않는 4xx와 일부 Source 실패를 검사한다.

### 4.5 Source 중복·삭제 평가

```bash
python -m logfolio_ai.evaluation.source_lifecycle_runner \
  --dataset evals/datasets/source_lifecycle_v1.json \
  --output-json evals/results/source-lifecycle.json
```

동일 Source 중복 방지, Project 격리, 삭제 후 Retrieval 제외와 재등록을 검사한다.

### 4.6 다른 프로젝트 자료 의심 평가

```bash
python -m logfolio_ai.evaluation.project_mismatch_runner \
  --dataset evals/datasets/project_mismatch_v1.json \
  --output-json evals/results/project-mismatch.json
```

관련성이 낮은 Source를 자동 삭제하지 않고 사용자 확인으로 보내는지 검사한다.

### 4.7 오프라인 전체 품질 Gate

```bash
python -m logfolio_ai.evaluation.offline_suite_runner \
  --output-json evals/results/offline-suite.json
```

Policy, Pipeline, 장애 복구, Source 생명주기, 프로젝트 불일치 평가를 한 번에 실행한다. 하나라도 실패하면 종료 코드가 `1`이므로 배포 전 필수 Gate로 사용한다.

### 4.8 비용 제한 평가

현재는 합성 예시 데이터를 사용한다.

```bash
python -m logfolio_ai.evaluation.cost_guardrail_runner \
  evals/datasets/cost_guardrail_example.json \
  --output-json evals/results/cost-guardrail.json
```

Spring에서 실제 Usage·Review Export가 준비되면 입력 파일만 실제 Export로 바꾼다.

## 5. Docker 기반 AI 서버 테스트

Docker Desktop이 실행 중이어야 한다.

### 5.1 Compose 설정 검사

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/ai-server
docker compose --env-file deploy/.env -f deploy/docker-compose.yml config
```

환경변수 누락이나 YAML 오류가 있으면 서버를 띄우기 전에 여기서 실패한다.

### 5.2 Fake LLM + PostgreSQL + pgvector Smoke Test

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build postgres migrate ai-server
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile smoke run --rm smoke
```

로그 확인:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs --tail=200 ai-server
```

종료:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile smoke down
```

`down`은 DB Volume을 보존한다. `down -v`는 DB 데이터를 삭제하므로 의도적으로 초기화할 때만 사용한다.

### 5.3 실제 E5 검색 평가

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile e5 run --rm e5-eval
```

한국어 Query에서 관련 문서를 우선 검색하고 768차원 벡터를 생성하는지 확인한다. Gemini는 호출하지 않는다.

### 5.4 실제 E5 + pgvector + Fake LLM 전체 RAG

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile e5-rag up -d --build postgres migrate ai-server-e5
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile e5-rag run --rm e5-rag-smoke
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile e5-rag down
```

외부 LLM 비용 없이 Chunk 저장, E5 Embedding, pgvector 검색, 프로젝트 격리와 FastAPI 응답을 검증한다.

## 6. 실제 Gemini 테스트

이 절의 명령은 외부 API를 호출하므로 사용량·비용이 발생할 수 있다. 반드시 합성·비식별 자료를 사용한다.

`deploy/.env`에 개발용 Key와 비교할 모델을 설정한다.

```dotenv
GEMINI_API_KEY=실제_개발용_API_KEY
GEMINI_MODEL=비교할_모델명
```

### 6.1 Gemini Provider 단독 Smoke Test

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/ai-server
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile gemini up --build --abort-on-container-exit --exit-code-from gemini-smoke gemini-smoke
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile gemini down
```

Structured Output, 30초 제한, Candidate·Question 개수와 기본 Policy를 확인한다.

### 6.2 실제 E5 + pgvector + Gemini 전체 파이프라인

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile full-pipeline up -d --build postgres migrate ai-server-full-pipeline
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile full-pipeline run --rm full-pipeline-smoke
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile full-pipeline down
```

실제 Embedding, 검색, Gemini 생성, Evidence 검증과 AI Policy를 한 요청으로 검사한다.

## 7. Gemini 모델 품질 비교

### 7.1 대표 Gold Case 하나로 먼저 확인

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/ai-server
source .venv/bin/activate
python -m logfolio_ai.evaluation.product_runner \
  --provider gemini \
  --model <model-name> \
  --case NEW_01 \
  --repeat 1 \
  --pricing evals/pricing.local.json \
  --output-json evals/results/<model-name>-new-01.json \
  --output-csv evals/results/<model-name>-new-01.csv
```

`<model-name>`은 실제 비교할 모델명으로 바꾼다. 가격표는 `evals/pricing.example.json`을 복사해 공식 요금과 환율을 입력한 로컬 파일을 사용한다.

### 7.2 전체 20개 Product Gold Case

```bash
python -m logfolio_ai.evaluation.product_runner \
  --provider gemini \
  --model <model-name> \
  --repeat 1 \
  --pricing evals/pricing.local.json \
  --output-json evals/results/<model-name>.json \
  --output-csv evals/results/<model-name>.csv
```

Hard Case는 `--case`로 선택해 최소 3회 반복한다.

```bash
python -m logfolio_ai.evaluation.product_runner \
  --provider gemini \
  --model <model-name> \
  --case PROMPT_INJECTION_01 \
  --repeat 3 \
  --pricing evals/pricing.local.json \
  --output-json evals/results/<model-name>-prompt-injection.json \
  --output-csv evals/results/<model-name>-prompt-injection.csv
```

### 7.3 모델 비교 Report

```bash
python -m logfolio_ai.evaluation.comparison_runner \
  evals/results/<model-a>.json evals/results/<model-b>.json \
  --output-json evals/results/comparison.json \
  --output-csv evals/results/comparison.csv \
  --output-markdown evals/results/comparison.md
```

Pass Rate, P50/P95, Timeout·Retry·Schema 실패율, Critical Policy 오류와 비용을 비교한다.

### 7.4 Human Eval

평가 입력 양식을 만든다.

```bash
python -m logfolio_ai.evaluation.human_runner \
  --product-report evals/results/<model-name>.json \
  --template-output evals/results/<model-name>-human-input.json
```

사람이 각 항목의 점수와 Critical Error를 입력한 후 집계한다.

```bash
python -m logfolio_ai.evaluation.human_runner \
  --input evals/results/<model-name>-human-input.json \
  --output-json evals/results/<model-name>-human-report.json \
  --output-csv evals/results/<model-name>-human-report.csv
```

## 8. Spring 서버 테스트

### 8.1 Spring 전체 테스트

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/backend
./gradlew test
```

### 8.2 Spring 빌드

```bash
./gradlew clean build
```

### 8.3 로컬 PostgreSQL 준비와 Spring 실행

PostgreSQL 17이 설치·실행 중이고 `logfolio` DB가 존재한다고 가정한다.

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/backend
export DB_USERNAME="$(whoami)"
export DB_PASSWORD='로컬_DB_비밀번호'
export AI_SERVER_ENABLED=true
export AI_SERVER_BASE_URL=http://localhost:8000
export AI_SERVER_INTERNAL_API_KEY='deploy/.env와_같은_내부키'
./gradlew bootRun --args='--spring.profiles.active=local'
```

실제 비밀번호와 내부 Key를 Git에 기록하지 않는다.

Spring 확인 주소:

- Swagger UI: `http://localhost:8080/swagger-ui.html`
- OpenAPI JSON: `http://localhost:8080/v3/api-docs`

## 9. Spring ↔ FastAPI 연동 테스트 순서

현재 자동 E2E가 완성되기 전까지는 다음 순서로 실행한다.

### 터미널 1 — Fake Provider AI 서버

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/ai-server
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build postgres migrate ai-server
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs -f ai-server
```

### 터미널 2 — Spring 서버

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio/backend
export DB_USERNAME="$(whoami)"
export DB_PASSWORD='로컬_DB_비밀번호'
export AI_SERVER_ENABLED=true
export AI_SERVER_BASE_URL=http://localhost:8000
export AI_SERVER_INTERNAL_API_KEY='deploy/.env와_같은_내부키'
./gradlew bootRun --args='--spring.profiles.active=local'
```

### 확인할 흐름

1. Spring에서 Quick Log 또는 Project File 저장
2. AI 서버 로그에서 `/api/v1/sources/index` 호출 확인
3. Spring에서 AI 분석 실행
4. AI 서버 로그에서 `/api/v1/analyses` 호출 확인
5. Spring DB에서 Analysis Run, Candidate, Review, Evidence 저장 확인
6. 사용자 승인·수정·거절 후 Experience 반영 확인

Fake 연동이 통과한 뒤에만 AI 서버를 Gemini Profile로 바꿔 같은 흐름을 다시 시험한다.

## 10. Git 작업 전후 확인

작업 시작 전:

```bash
cd /Users/parksubin/Documents/ChatGPT/Logfolio
git switch integration/next
git fetch origin develop integration/next
git pull --ff-only origin integration/next
git status --short --branch
```

문서와 코드의 공백 오류 확인:

```bash
git diff --check
```

병합 여부 확인:

```bash
git branch --merged integration/next
git branch -r --merged origin/integration/next
```

`develop`, `main`, `integration/next`는 삭제하지 않는다. 기능 브랜치는 `integration/next`에 병합됐는지 확인한 뒤 삭제한다.

## 11. 결과 파일 확인

평가 결과는 기본적으로 다음 경로에 생성한다.

```text
ai-server/evals/results/
```

결과에는 모델 응답이나 평가용 문장이 포함될 수 있으므로 Git에서 제외한다. 확인할 주요 값:

- `accepted` 또는 최종 Gate 상태
- 실패 Case ID와 실패 이유
- Critical Policy Error 수
- Schema Error 수
- P50·P95 Latency
- Timeout·Retry 비율
- 입력·출력 Token
- 예상 비용

## 12. 문제 발생 시 확인 순서

### Docker 서버가 뜨지 않을 때

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs --tail=200 postgres migrate ai-server
```

### 8000 포트가 이미 사용 중일 때

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

실행 중인 기존 AI 서버나 Compose를 먼저 정상 종료한다.

### PostgreSQL 연결 실패

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps postgres
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs --tail=200 postgres
```

### Gemini 호출 실패

- `GEMINI_API_KEY`가 비어 있지 않은지 확인
- 선택 모델명이 현재 계정에서 사용 가능한지 확인
- 실제 키를 출력하거나 화면 캡처하지 않음
- 429는 할당량, 401·403은 Key·Project 권한, 5xx는 Provider 장애 가능성을 우선 확인
- FastAPI 내부 재시도는 최대 1회이므로 반복 자동 실행하지 않음

### 완전히 새 로컬 DB가 필요할 때

`down -v`는 Docker DB Volume을 삭제하는 파괴적 명령이다. 필요한 로컬 데이터가 없고 정말 초기화하려는 경우에만 직접 실행한다.

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down -v
```

운영 DB나 팀 공유 DB에는 이 명령을 사용하지 않는다.

## 13. 권장 실행 시점

| 시점 | 실행 명령 |
| --- | --- |
| 작은 코드 수정 | `pytest` |
| Policy·Pipeline 수정 | `pytest` + `offline_suite_runner` |
| Chunk·Embedding 수정 | E5 Eval + E5 RAG Smoke |
| Gemini Prompt·Schema 수정 | 대표 Gold Case + 전체 Product Eval |
| 모델 변경 | Product Eval + Hard Case 3회 + Human Eval + 비교 Report |
| DB·Docker 수정 | Docker Fake Smoke + E5 RAG Smoke |
| Spring 계약 수정 | Spring Test + Fake Spring–FastAPI E2E |
| 배포 후보 | 전체 Test + Offline Gate + Full Pipeline + Spring E2E + 비용 Gate |

상세 계약은 `spring-fastapi-contract.md`, 전체 작업 순서는 `ai-model-spring-e2e-roadmap.md`, 평가 데이터 관리 기준은 `../evals/README.md`를 참고한다.
