# 마지막 AI 평가·비용 정책 반영 현황

## 이미 구현된 항목

- Git으로 버전 관리되는 20개 Product Gold Case와 Dataset Schema
- Provider·Model·Case·반복 횟수를 선택할 수 있는 Product Eval Runner
- Result Type, Target Experience, Candidate 수, 질문, Conflict, Evidence와 Critical Policy 자동 평가
- JSON·CSV 결과와 모델 비교 Markdown Report
- Provider, Model, Task Type, Token, Latency, Retry, 성공 여부와 비용 추정 기록
- Policy, Retrieval, 전체 Pipeline, 장애 복구와 Source 생명주기 평가
- Human Eval 8개 품질 항목과 Critical Error 판정
- 최대 1회 재시도, 30초 분석 제한, P95 25초 목표 Gate

## 이번에 추가한 항목

- Spring Usage·Review 집계 Export를 입력받는 월별 Cost Guardrail 평가
- Accepted Experience당 50원 Hard Limit 판정
- Heavy User 월 3달러 Hard Limit 판정
- 베타 월 총비용 150달러 Hard Limit과 100달러 목표 판정
- `analysisRunId` 중복 비용 합산 방지

## Spring 연동 후 구현·검증할 항목

- AI Usage를 `analysisRunId`, `projectId`, 인증된 `userId`와 연결해 영속 저장
- Review 승인 결과의 생성·보강·수정 후 승인·거절 수를 Analysis Run에 연결
- Review 중 이탈·이어하기와 Review 중 새 Source의 다음 Run 격리
- Spring ↔ FastAPI Backend Integration Eval
- 사용자별 월 비용 및 Accepted Experience 비용 Export 자동화

## 실제 모델·베타 단계에서 측정할 항목

- 실제 Gemini Product Eval과 Hard Case 3회 반복
- 실제 Token, P50/P95 Latency, Timeout·Retry·Schema 실패율
- Human Quality 평균 4.0 이상과 정확성·개인성 하한
- As-is Accept, Edit & Accept, Reject, Major Edit와 Override 비율
- Cost per Accepted & Useful Experience

## MVP 이후 항목

- Dynamic Model Routing
- Multi-model Fallback
- 사용자별 Cost Throttling과 AI Credit
- 실시간 비용 기반 모델 전환

정책에 따라 위 MVP 이후 항목은 현재 구현하지 않는다.
