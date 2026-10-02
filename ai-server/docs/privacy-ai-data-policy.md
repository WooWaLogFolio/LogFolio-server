# 개인정보 및 AI 데이터 처리 구현 기준

이 문서는 LogFolio 개인정보 및 AI 데이터 처리 정책 v1을 FastAPI 구현과 운영 역할에 연결한다.

## FastAPI에서 강제하는 항목

- 프로젝트 범위로 Retrieval한 필요한 Chunk만 외부 LLM에 전달한다.
- 외부 LLM 호출 직전에 원본 저장 데이터의 복사본을 마스킹한다.
- 이메일, 전화번호, 주민등록번호 형태의 고유식별정보, 계좌·카드번호, 명시된 주소와 민감정보, 역할과 함께 적힌 제3자 이름, API Key 형태의 비밀정보를 마스킹한다.
- 마스킹된 값은 복원하거나 추측하지 않도록 System Policy에서 금지한다.
- Evidence 인용은 외부 Provider가 실제로 본 마스킹된 Chunk를 기준으로 검증한다.
- 로그에는 원문, 전체 Prompt, 사용자 답변을 기록하지 않고 마스킹 건수와 범주만 기록한다.
- 모든 Vector 검색과 삭제는 `projectId` 범위로 제한한다.
- Source 삭제 API는 원본 Source나 Spring 소유 Experience를 건드리지 않고 해당 Vector Index만 제거한다.

마스킹은 외부 Provider 전송을 최소화하기 위한 보조 안전장치다. 모든 자연어 개인정보를 완벽히 탐지한다고 보장하지 않으므로 업로드 안내, Spring 권한 검사, 운영 로그 통제와 함께 적용한다.

## Spring에서 담당하는 항목

- 사용자 인증과 Project 접근 권한 검사
- 원본 Source, 추출 Text와 사용자 데이터의 저장·보유·삭제
- Source 삭제 시 S3 원본·추출 Text 삭제와 FastAPI Vector Index 삭제 호출
- Experience 수정·삭제, AI 제안 거절, 계정 삭제 기능
- 사용자 승인 전 AI Draft가 기존 Experience를 변경하지 않도록 Review 상태 관리
- 개인정보 접근 로그 및 사용자 권리 요청 처리

## Provider·운영 확정 전 필수 확인

- API 입력을 범용 모델 학습에 사용하지 않는 계약과 설정
- Zero Data Retention 또는 최소 보유기간
- 처리 국가, 국외 이전 근거, 수탁자와 재수탁자
- 전송 구간 HTTPS와 Secret Manager 기반 API Key 보관
- 개인정보처리방침의 처리 항목·목적·보유기간·위탁·삭제·문의처

Provider 약관과 실제 배포 Cloud가 확정되기 전에는 위 항목을 완료로 표시하지 않는다. 실제 사용자 자료는 계약과 개인정보처리방침 확정 전 개발용 무료 티어에 전송하지 않는다.
