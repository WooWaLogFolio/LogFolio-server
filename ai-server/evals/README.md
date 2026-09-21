# AI Evaluation

이 디렉터리는 LogFolio AI Policy의 회귀 평가 데이터를 관리합니다. 각 케이스에는 사용자가 업로드할 수 있는 예시 문장, LLM이 반환했다고 가정한 초안과 정책 적용 후 기대 상태가 포함됩니다.

평가는 외부 LLM API를 호출하지 않으므로 비용이 발생하지 않습니다.

```bash
cd ai-server
python -m logfolio_ai.evaluation.runner
```

새로운 오류 사례를 발견하면 먼저 `evals/datasets/policy_cases.json`에 재현 케이스를 추가한 뒤 정책 코드를 수정합니다. 평가 케이스가 통과한다는 것은 현재 명시된 정책을 만족한다는 뜻이며, 실제 LLM의 전체 품질이나 검색 정확도를 보장하지는 않습니다.
