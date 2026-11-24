# re:portory

일기처럼 쓴 기록을 LLM이 구조화해 포트폴리오 데이터로 쌓고, 그 데이터로 목적별 문서(CV, Resume, 이력서, 포트폴리오)를 만들며, 맞춤 외부 활동을 추천하고 지원부터 결과까지 이어서 관리하는 웹서비스다.

- 명세: [docs/handoff.md](docs/handoff.md) ([PDF](docs/handoff.pdf))
- 결정 기록: [docs/decisions.md](docs/decisions.md)

## 구성

| 폴더 | 내용 |
| --- | --- |
| `web/` | Next.js(App Router) 화면. 로그인, 일기, 검토 큐, 포트폴리오, 설정, 공개 프로필 |
| `api/` | FastAPI API 서버와 작업 큐 워커(같은 코드, 실행 명령만 다르다) |
| `supabase/` | 마이그레이션, 로컬 Supabase 설정, 샘플 데이터 |

## 지금 되는 것

**Phase 1 · 핵심 순환**
- 이메일 매직링크·GitHub 로그인(Supabase Auth)
- 일기 작성 → LLM 추출 → 검토 큐(승인, 수정 후 승인, 거절, 일괄 승인, 기존 항목에 합치기)
- 후속 질문 답변, 포트폴리오 항목 관리·병합, 근거(원문 인용) 확인
- 원문에 없는 인용·숫자·날짜·항목 id는 저장하지 않는다(서버 검증)

**Phase 2 · 가져오기, 증빙, 문서**
- 온보딩 5단계(목표 → 동의 → 자료 연결 → 검토 → 첫 결과)
- 이력서 PDF·DOCX, LinkedIn ZIP, GitHub 저장소 가져오기. 여러 출처의 같은 항목은 하나로 합친다
- 증빙 업로드(PDF·이미지) → 종류·값 읽기 → 항목 연결 제안, 값이 다르면 고르기, 서명 URL 열람
- 목적별 문서 4종(국문 이력서, 영문 Resume, Academic CV, 프로젝트 포트폴리오), 버전, PDF
- 주간·월간 요약, 앱 내 알림, 데이터 내보내기(JSON Resume ZIP), 계정 삭제
- 공개 프로필 `/p/{handle}`(공개 항목, 공개 증빙, 공개 문서 PDF)

## 로컬 실행

필요한 것: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22, pnpm 10, [Supabase CLI](https://supabase.com/docs/guides/cli)(Docker 필요).

```bash
supabase start
```

`supabase start`가 출력한 `API URL`, `anon key`, `service_role key`, `JWT secret`을 아래 파일에 넣는다. 마이그레이션은 시작할 때 자동으로 적용된다.

```bash
cp .env.example api/.env
```

```bash
cp .env.example web/.env.local
```

`api/.env`에는 `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:54322/postgres`, `SUPABASE_JWT_SECRET`, `ANTHROPIC_API_KEY`를 채운다. `web/.env.local`에는 `NEXT_PUBLIC_` 값만 있으면 된다.

마이그레이션은 `supabase/migrations/` 안의 파일을 번호 순서대로 한 번씩 적용한다. Supabase 대시보드 SQL Editor를 쓴다면 `0001_init.sql`, `0002_phase2.sql` 순서로 붙여 넣어 실행한다.

문서 PDF를 만들려면 API 서버 폴더에서 Chromium을 한 번 받아 둔다.

```bash
cd api && uv run playwright install chromium
```

API 서버:

```bash
cd api && uv sync && uv run uvicorn app.main:app --reload --port 8000
```

워커(다른 터미널):

```bash
cd api && uv run python -m app.worker
```

웹(다른 터미널):

```bash
cd web && pnpm install && pnpm dev
```

http://localhost:3000 에서 로그인한다.

Anthropic 키가 아직 없으면 `api/.env`에 `LLM_PROVIDER=demo`를 넣는다. 외부 API 없이 규칙으로 후보를 만드는 데모 분석이라 품질은 낮지만, 전체 흐름(일기 → 검토 → 포트폴리오)을 확인할 수 있다. `OPENAI_API_KEY`가 비어 있으면 임베딩 없이 동작한다. 로컬 Supabase가 보낸 로그인 메일은 http://localhost:54324 (Inbucket)에서 확인한다.

## 테스트

API 테스트는 Postgres(pgvector 포함)에 테스트 DB를 새로 만들어 돌린다. 기본 접속 주소는 `postgresql://postgres@localhost:54322/postgres`이고 `TEST_DATABASE_ADMIN_URL`로 바꿀 수 있다. LLM은 mock으로 대체한다.

```bash
cd api && uv run pytest
```

```bash
cd web && pnpm lint && pnpm typecheck && pnpm test
```

`supabase/local/supabase_shim.sql`은 Supabase 없이 일반 Postgres에서 마이그레이션과 RLS를 시험하기 위한 auth·storage 대역이다. 실제 Supabase 프로젝트에는 적용하지 않는다.
