# Phase 2(문서 PDF)에서 Playwright 공식 Python 이미지로 바꾸고 Noto Sans KR을 넣는다(인계서 6장).
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
# API: 기본 명령. 워커는 같은 이미지에서 `python -m app.worker`로 띄운다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
