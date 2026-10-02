# AI Evaluation

이 디렉터리는 LogFolio AI Policy의 회귀 평가 데이터를 관리합니다. 각 케이스에는 사용자가 업로드할 수 있는 예시 문장, LLM이 반환했다고 가정한 초안과 정책 적용 후 기대 상태가 포함됩니다.

현재 정책 회귀 데이터셋은 18개 사례를 포함합니다.

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

`product_core_v1`은 실제 Provider가 LogFolio의 제품 판단을 수행하는지 확인하는 첫 Gold Dataset입니다.

- `NEW_01`: 신규 Experience
- `UPDATE_01`: 기존 Experience 보강
- `CONTEXT_01`: 개인 맥락 질문
- `ATTRIBUTION_01`: TEAM → USER 오귀속 방지
- `MERGE_01`: 여러 Source를 하나의 Experience로 구성

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

가격은 코드에 고정하지 않습니다. 공식 Provider 가격과 사용할 환율을 확인한 뒤 `pricing.example.json`을 복사하여 로컬 파일로 작성합니다. Token 정보가 없거나 가격표에 모델이 없으면 비용은 임의 계산하지 않고 `null`로 남깁니다. `evals/results/`는 모델 응답이 포함될 수 있어 Git에서 제외합니다.
