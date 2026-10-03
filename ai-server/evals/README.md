# AI Evaluation

이 디렉터리는 LogFolio AI Policy의 회귀 평가 데이터를 관리합니다. 각 케이스에는 사용자가 업로드할 수 있는 예시 문장, LLM이 반환했다고 가정한 초안과 정책 적용 후 기대 상태가 포함됩니다.

현재 정책 회귀 데이터셋은 19개 사례를 포함합니다.

- 팀 활동의 개인 기여 오인 방지
- 근거 없는 역할·기여·성과의 확인 필요 처리
- 명시적인 1인칭 개인 기여 보존
- AI의 사용자 입력·확인·수정 상태 위조 방지
- AI 추론값과 수행 주체 불명확 값의 확인 필요 처리
- 이미 답이 있는 질문 제거
- 중복 질문 제거와 개인 기여 질문 우선 배치

Claim 평가는 수행 주체, 출처 상태, 검증 상태, 근거 유형, 사용자 확인 필요 여부와 정책 위반 코드를 검사합니다.

평가는 외부 LLM API를 호출하지 않으므로 비용이 발생하지 않습니다.

```bash
cd ai-server
python -m logfolio_ai.evaluation.runner
```

새로운 오류 사례를 발견하면 먼저 `evals/datasets/policy_cases.json`에 재현 케이스를 추가한 뒤 정책 코드를 수정합니다. 평가 케이스가 통과한다는 것은 현재 명시된 정책을 만족한다는 뜻이며, 실제 LLM의 전체 품질이나 검색 정확도를 보장하지는 않습니다.

## Product Model Eval

`product_core_v1`은 실제 Provider가 LogFolio의 제품 판단과 보안 정책을 수행하는지 확인하는 20개 Gold Case Dataset입니다.

- `NEW_01`: 신규 Experience
- `UPDATE_01`: 기존 Experience 보강
- `CONTEXT_01`: 개인 맥락 질문
- `ATTRIBUTION_01`: TEAM → USER 오귀속 방지
- `MERGE_01`: 여러 Source를 하나의 Experience로 구성
- `SPLIT_01`: 하나의 Source에 있는 독립 경험을 별도 Experience로 분리
- `CONFLICT_01`: 사용자 확정값과 새 Source 충돌을 Review로 전달
- `ADDITIONAL_SOURCE_01`: 질문만으로 보완 불가능한 자료 부족 처리
- `NO_UPDATE_01`: 기존 Experience에 이미 반영된 내용의 중복 생성 방지
- `REJECTED_VALUE_01`: 사용자가 거절한 Claim의 동일 근거 재제안 방지
- `PRIVACY_01`: 외부 LLM 입력과 결과의 불필요한 개인정보 노출 방지
- `PROMPT_INJECTION_01`: Source 내부 명령·역할 조작·비밀 노출 요청 무시
- `USER_EDITED_01`: 사용자 수정값 자동 덮어쓰기 방지
- `MIXED_SOURCE_01`: Quick Log와 Project File의 출처 차이를 유지한 결합
- `AMBIGUOUS_MAPPING_01`: 비슷한 기존 Experience로의 강제 병합 방지
- `ANSWERED_CONTEXT_01`: Source에 이미 있는 답을 다시 묻지 않음
- `EVIDENCE_GROUNDING_01`: Claim과 실제 Evidence Chunk 연결
- `QUICK_FILE_CONFLICT_01`: Quick Log와 파일의 충돌을 사용자 확인으로 전달
- `REJECTED_NEW_EVIDENCE_01`: 거절 Claim에 새로운 근거가 생긴 경우 재검토
- `INSUFFICIENT_MIXED_01`: 자료 수와 무관하게 내용이 부족하면 추가 Source 요청

Case의 기대값은 결과 유형뿐 아니라 필요한 Claim 핵심어, 금지 Claim 핵심어,
필수 Evidence Chunk ID도 선택적으로 검사할 수 있습니다.

Fake Provider로 실행 구조만 확인할 수 있습니다. Fake는 실제 판단을 하지 않으므로 Gold Eval 실패가 정상입니다.

```bash
python -m logfolio_ai.evaluation.product_runner \
  --provider fake \
  --case NEW_01
```

실제 Gemini 평가에는 로컬 Secret의 API 키를 사용합니다. 이 명령은 실제 외부 API를 호출하므로 사용량과 비용이 발생할 수 있습니다.

```bash
python -m logfolio_ai.evaluation.product_runner \
  --provider gemini \
  --model <model-name> \
  --repeat 1 \
  --pricing evals/pricing.local.json \
  --output-json evals/results/gemini.json \
  --output-csv evals/results/gemini.csv
```

지원 옵션:

- `--dataset`: Dataset manifest 또는 Case 배열 JSON
- `--case`: 특정 Case만 실행
- `--provider`: `fake` 또는 `gemini`
- `--model`: 비교할 실제 모델 이름
- `--repeat`: 반복 횟수. `HARD` Case는 최소 3회 실행
- `--pricing`: 버전과 환율을 명시한 가격 설정
- `--output-json`, `--output-csv`: 비교 결과 저장 경로

결과의 `acceptance`에는 정책 v1의 자동 판정 가능한 합격선이 함께 기록됩니다.

- 신규/기존 보강 및 Merge/Split 정확도 90% 이상
- 질문 필요 여부 정확도 90% 이상
- 치명 Policy 오류와 Schema 오류 0건
- P95 25초 이하
- 자동 재시도 최대 1회

Spring Review 승인 데이터가 필요한 `승인된 경험당 비용`과 사람이 직접 채점하는
`Human Quality Score`는 임의로 계산하지 않고 `NOT_EVALUATED`로 표시합니다.
하나라도 `NOT_EVALUATED`이면 전체 `accepted`는 `false`이며, 측정된 자동 Gate의
통과 여부는 개별 `status`와 집계 수치로 확인합니다.

## Retrieval Eval

`retrieval_core_v1`은 새 Source, 사용자 기여, 판단 근거, 기존 Experience 근거,
기존 Index 재사용 검색을 평가하는 버전형 데이터셋입니다. 결과에는 `Recall@K`,
첫 정답 순위, MRR(Mean Reciprocal Rank), 무관 Chunk 비율, 다른 Project Chunk 혼입
건수가 포함됩니다. Project 필터는 유사도 순위 계산 전에 적용합니다.

2026-10-03 로컬 CPU 기준 `intfloat/multilingual-e5-base` 초기 Baseline은
Recall@1 0.80, Recall@3 1.00, Cross-project 혼입 0건이었습니다. 개인 기여 Case에서는
팀 활동 Chunk가 1위, 사용자 직접 기록이 2위였으므로 Embedding 순위만으로 개인 기여를
확정하지 않고 Evidence·AI Policy 검증을 계속 적용해야 합니다.

```bash
python -m logfolio_ai.evaluation.embedding_runner \
  --dataset evals/datasets/retrieval_core_v1.json \
  --top-k 3 \
  --output-json evals/results/retrieval.json
```

이 명령은 외부 LLM API를 호출하지 않지만 로컬 E5 모델을 사용합니다.

## Pipeline Eval

`pipeline_core_v1`은 Scripted Retrieval과 Scripted Provider 출력을 실제
`AnalysisOrchestrator`에 넣어 전체 검증 순서를 확인합니다.

- 정상 Claim과 Evidence 통과
- 원문에 없는 Evidence와 Candidate 제거
- TEAM 활동을 USER 기여로 귀속한 결과의 Policy 교정
- Retrieval 근거가 없을 때 LLM을 호출하지 않고 `NO_UPDATE` 반환

```bash
python -m logfolio_ai.evaluation.pipeline_runner \
  --dataset evals/datasets/pipeline_core_v1.json \
  --output-json evals/results/pipeline.json
```

이 평가는 외부 LLM API와 운영 DB를 호출하지 않습니다. 실제 Chunking, E5 및
pgvector 자체 품질은 Retrieval Eval과 각각의 통합 테스트에서 별도로 검증합니다.

## Model Comparison Report

둘 이상의 Product Eval JSON 결과를 한 표로 비교합니다. Pass Rate, P50/P95,
Timeout/Retry/Schema 실패율, Critical Policy 오류와 예상 비용을 집계합니다.

```bash
python -m logfolio_ai.evaluation.comparison_runner \
  evals/results/model-a.json evals/results/model-b.json \
  --output-json evals/results/comparison.json \
  --output-csv evals/results/comparison.csv \
  --output-markdown evals/results/comparison.md
```

자동 Gate가 실패하면 `FAIL`, 자동 Gate는 통과했지만 Human Eval 또는 승인당 비용처럼
필요한 측정값이 남아 있으면 `READY_FOR_HUMAN_REVIEW`로 표시합니다. 필요한 값이 없는
모델을 임의로 최종 `PASS` 처리하지 않습니다.

## Human Eval

Human Eval은 사용자 기능이나 Spring API가 아니라 실제 모델 결과의 콘텐츠 품질을
사람이 확인하는 내부 평가 절차입니다. 정확성, 구체성, 핵심성, 개인성, 구조성,
비중복성, 재사용성, 과장 방지를 각각 1~5점으로 기록합니다.

Product Eval 결과에서 입력 템플릿을 생성합니다.

```bash
python -m logfolio_ai.evaluation.human_runner \
  --product-report evals/results/gemini.json \
  --template-output evals/results/gemini-human-input.json
```

사람이 점수와 `criticalError`를 입력한 후 집계합니다.

```bash
python -m logfolio_ai.evaluation.human_runner \
  --input evals/results/gemini-human-input.json \
  --output-json evals/results/gemini-human-report.json \
  --output-csv evals/results/gemini-human-report.csv
```

모든 항목이 입력되어야 완료로 인정합니다. 평균 4.0 미만, 정확성·개인성 3점 미만,
또는 Critical Error가 하나라도 있으면 Fail입니다. 미입력 항목이 있으면
`INCOMPLETE`이며 최종 합격 처리하지 않습니다.

## Resilience Eval

`resilience_core_v1`은 예외 및 실패 처리 정책의 자동 검증 가능한 핵심 동작을
실제 Provider·RAG 코드 경로로 확인합니다.

- 잘못된 첫 JSON 응답 후 1회 재시도 성공
- Timeout 발생 시 1회만 재시도하고 `LLM_TIMEOUT` 반환
- 재시도 대상이 아닌 4xx 요청 오류는 즉시 중단
- 잘못된 구조화 응답이 반복되면 `LLM_INVALID_RESPONSE` 반환
- Source 하나가 실패해도 나머지 Source 인덱싱 결과 보존

```bash
python -m logfolio_ai.evaluation.resilience_runner \
  --dataset evals/datasets/resilience_core_v1.json \
  --output-json evals/results/resilience.json
```

Scripted Client와 합성 Source만 사용하므로 외부 API와 운영 DB를 호출하지 않습니다.

## Source Lifecycle Eval

`source_lifecycle_v1`은 Source 중복·삭제 정책을 실제 `RagService`와
`MemoryVectorStore` 조합으로 검증합니다.

- 같은 Project의 내용이 완전히 동일한 Source는 `DUPLICATE`
- 동일 내용도 Project가 다르면 각각 `INDEXED`
- 삭제된 Source는 Retrieval 결과에서 제외
- 삭제된 Source의 Content Hash도 제거되어 같은 자료 재등록 가능

```bash
python -m logfolio_ai.evaluation.source_lifecycle_runner \
  --dataset evals/datasets/source_lifecycle_v1.json \
  --output-json evals/results/source-lifecycle.json
```

합성 Source와 메모리 저장소만 사용하므로 외부 API와 운영 DB를 호출하지 않습니다.

가격은 코드에 고정하지 않습니다. 공식 Provider 가격과 사용할 환율을 확인한 뒤 `pricing.example.json`을 복사하여 로컬 파일로 작성합니다. Token 정보가 없거나 가격표에 모델이 없으면 비용은 임의 계산하지 않고 `null`로 남깁니다. `evals/results/`는 모델 응답이 포함될 수 있어 Git에서 제외합니다.
