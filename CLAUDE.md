# CLAUDE.md

이 저장소는 개인 포트폴리오 관리 웹서비스 re:portory다. 저장소 이름과 도메인용 표기는 `reportory`를 쓴다. 전체 명세는 `docs/handoff.md`(PDF: `docs/handoff.pdf`)에 있다.

## 작업 원칙 (인계서 1.2절)

1. Phase 순서대로 진행하고, 각 Phase의 완료 기준을 테스트로 확인한 뒤 다음 Phase로 넘어간다.
2. 이 문서와 다른 결정이 필요하면 `docs/decisions.md`에 이유와 함께 기록하고, 제품 동작이 바뀌는 결정은 사용자에게 먼저 확인한다.
3. DB 변경은 항상 새 마이그레이션 파일로 한다. 이미 적용한 마이그레이션은 고치지 않는다.
4. LLM 호출은 `api/app/llm/client.py` 어댑터만 거친다. 모든 LLM 출력은 Pydantic 모델로 검증한다.
5. "원문에 없는 사실을 만들지 않는다"는 원칙(2.3절)을 프롬프트뿐 아니라 코드 검증으로 강제한다.
6. 비밀 키는 커밋하지 않는다. `.env.example`만 커밋한다.
7. UI 문구는 한국어로 쓰고, 문장은 서술체로 끝맺는다. 명사형 종결(예: "~함", "~음")은 쓰지 않는다.
8. 일기 본문, 증빙 내용 같은 사용자 데이터를 애플리케이션 로그에 남기지 않는다.
9. 단위·통합 테스트에서 LLM은 mock으로 대체한다. 실제 모델 품질 평가는 `api/scripts/eval_extraction.py`로 따로 돌린다.
10. 19장(미결정 사항)의 항목은 적힌 기본값으로 진행하고, 사용자가 다른 값을 정하면 설정값만 바꿔 대응할 수 있게 만든다.

## 진행 상황

- Phase 0(기반 구성): 대부분 끝났다. 남은 것: 실제 Supabase 프로젝트 연결, GitHub OAuth 앱 등록, CI 첫 실행 확인.
- Phase 1(핵심 순환): 일기·추출·검토 큐·후속 질문·항목·병합·공개 프로필 기본이 동작한다. 남은 것: 실제 LLM 연결 뒤 골든 일기 평가(16장, `api/scripts/eval_extraction.py`), 임베딩을 쓰는 중복 감지(0.92)·KNOWN_ITEMS 유사도 선택(임베딩 제공사는 OpenAI로 확정, 어댑터는 `api/app/embeddings.py`).
- 인계서와 다르게 정한 것은 `docs/decisions.md`에 있다.

## 명령

- API 테스트: `cd api && uv run pytest` (Postgres+pgvector 필요, 기본 `localhost:54322`, `TEST_DATABASE_ADMIN_URL`로 변경)
- API 검사: `cd api && uv run ruff check . && uv run ruff format --check .`
- 웹 검사: `cd web && pnpm lint && pnpm typecheck && pnpm test && pnpm build`

## 코드 규칙

- 사용자 데이터 쿼리는 `UserDB`(`api/app/db.py`)를 거친다. SQL에 `:user_id` 조건이 없으면 실행이 거부된다. 다른 사용자 리소스는 404다.
- jsonb 파라미터는 `as_json()`으로 넘기고 SQL에서 `cast(:x as jsonb)`로 받는다. `:x::type` 형식은 SQLAlchemy `text()`와 충돌하므로 `cast()`를 쓴다.
- 작업 핸들러는 `api/app/jobs/registry.py`에 등록하고, 두 번 실행돼도 결과가 같게 만든다.
- LLM 출력은 `api/app/llm/validators.py`를 거친 값만 저장한다.
