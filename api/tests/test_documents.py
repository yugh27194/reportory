"""목적별 문서(인계서 10.8절, 11.5절 완료 기준)."""

import io

import pdfplumber
import pytest

from app.llm.schemas import DocLine, DocSection
from app.services.documents import validate_sections
from app.storage import get_storage
from tests.conftest import drain_jobs

ITEMS = [
    {
        "type": "education",
        "title": "한국대학교",
        "organization": "한국대학교",
        "start_date": "2021-03-01",
        "end_date": "2025-02-28",
        "details": {"degree": "학사", "major": "컴퓨터학과"},
        "title_en": "Korea University",
    },
    {
        "type": "experience",
        "title": "백엔드 인턴",
        "organization": "OO회사",
        "role": "백엔드 개발",
        "start_date": "2024-07-01",
        "end_date": "2024-08-31",
        "summary": "FastAPI로 결제 API를 만들었다. 응답 시간을 30% 줄였다.",
        "metrics": [{"name": "응답 시간 감소", "value": "30%"}],
        "skills": ["FastAPI", "PostgreSQL"],
        "title_en": "Backend Intern",
    },
    {
        "type": "project",
        "title": "공부 기록 앱",
        "summary": "React로 공부 기록 앱을 만들었다.",
        "skills": ["React"],
        "details": {"team_size": 3, "repo_url": "https://github.com/me/app"},
        "title_en": "Study Log App",
    },
    {
        "type": "award",
        "title": "OO 해커톤 우수상",
        "details": {"rank": "우수상", "host": "OO재단"},
        "end_date": "2024-11-10",
        "title_en": "OO Hackathon Excellence Award",
    },
    {
        "type": "certification",
        "title": "정보처리기사",
        "details": {"issuer": "한국산업인력공단"},
        "start_date": "2024-06-15",
        "title_en": "Engineer Information Processing",
    },
    {
        "type": "language_test",
        "title": "TOEIC",
        "details": {"test": "TOEIC", "score": "905"},
        "title_en": "TOEIC",
    },
]


async def seed(user, items=ITEMS):
    ids = []
    for it in items:
        r = await user.client.post("/items", json=it)
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    await user.client.patch(
        "/me/profile",
        json={
            "display_name": "홍길동",
            "display_name_en": "Gildong Hong",
            "headline": "백엔드 개발자",
        },
    )
    await drain_jobs()
    return ids


async def make_version(user, fmt, title="문서", target=None, ids=None):
    doc = (
        await user.client.post(
            "/documents", json={"format": fmt, "title": title, "target_description": target}
        )
    ).json()
    sel = (await user.client.post(f"/documents/{doc['id']}/preview-selection")).json()["items"]
    chosen = ids or [i["id"] for i in sel if i["selected"]]
    r = await user.client.post(
        f"/documents/{doc['id']}/versions", json={"selected_item_ids": chosen}
    )
    return doc, r


async def pdf_text(user, doc_id, version=1):
    r = await user.client.get(f"/documents/{doc_id}/versions/{version}")
    body = r.json()
    assert body["status"] == "succeeded", body
    assert body["has_pdf"], body["options"]
    url = (await user.client.get(f"/documents/{doc_id}/versions/{version}/pdf")).json()["url"]
    token_path = url.removeprefix("http://test/api/v1/files/")
    meta = get_storage().verify(token_path)
    data = await get_storage().get(meta["b"], meta["p"])
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return body, len(pdf.pages), "\n".join(p.extract_text() or "" for p in pdf.pages)


@pytest.mark.parametrize("fmt", ["academic_cv", "resume_ko", "project_portfolio"])
async def test_formats_render_korean_pdf(make_user, mock_llm, fmt):
    def rewrite(v):
        return {
            "sections": [
                {
                    "item_id": i["id"],
                    "lines": [{"item_id": i["id"], "text": f"{i['title']} 경험을 정리했다."}],
                }
                for i in v["ITEMS"]
            ]
        }

    mock_llm.on("rewrite_document", rewrite)
    user = await make_user()
    await seed(user)
    doc, r = await make_version(user, fmt)
    assert r.status_code == 202, r.text
    await drain_jobs()
    body, pages, text = await pdf_text(user, doc["id"])
    assert "홍길동" in text or fmt == "project_portfolio" and "홍길동" in text
    assert "공부 기록 앱" in text  # 한글이 깨지지 않는다
    assert "�" not in text
    assert body["content"]["x-reportory"]["format"] == fmt
    if fmt == "resume_ko":
        assert "905" in text and "한국산업인력공단" in text  # 어학·자격증 표
        assert body["content"]["certificates"][0]["issuer"] == "한국산업인력공단"
    if fmt == "project_portfolio":
        assert pages >= 2  # 표지 + 프로젝트 쪽


async def test_invented_numbers_are_removed(make_user, mock_llm):
    def rewrite(v):
        intern = next(i for i in v["ITEMS"] if i["type"] == "experience")
        return {
            "sections": [
                {
                    "item_id": intern["id"],
                    "lines": [
                        {"item_id": intern["id"], "text": "응답 시간을 30% 줄였다."},
                        {"item_id": intern["id"], "text": "사용자 10만 명이 쓰는 API를 만들었다."},
                    ],
                }
            ]
        }

    mock_llm.on("rewrite_document", rewrite)
    user = await make_user()
    await seed(user)
    doc, _ = await make_version(user, "resume_ko")
    await drain_jobs()
    body = (await user.client.get(f"/documents/{doc['id']}/versions/1")).json()
    lines = [x["lines"] for x in body["content"]["x-reportory"]["items"].values() if x["lines"]]
    assert lines == [["응답 시간을 30% 줄였다."]]
    assert body["options"]["dropped_lines"] == 1
    assert any("1개를 지웠다" in w for w in body["options"]["warnings"])
    assert "10만" not in body["html"]


def test_validate_sections_unit():
    import uuid

    a, b = uuid.uuid4(), uuid.uuid4()
    items = {str(a): {"title": "A", "summary": "정확도 0.78", "metrics": [], "details": {}}}
    secs = [
        DocSection(
            item_id=a,
            lines=[
                DocLine(item_id=a, text="정확도를 0.78까지 올렸다."),
                DocLine(item_id=a, text="정확도 0.95"),
                DocLine(item_id=b, text="다른 항목 문장"),
            ],
        ),
        DocSection(item_id=b, lines=[DocLine(item_id=b, text="선택하지 않은 항목")]),
    ]
    out, dropped = validate_sections(secs, items, max_lines=4)
    assert out[str(a)]["lines"] == ["정확도를 0.78까지 올렸다."]
    assert dropped == 3


async def test_resume_en_requires_title_en_and_fits_one_page(make_user, mock_llm):
    def rewrite(v):
        return {
            "summary": "Backend developer.",
            "sections": [
                {
                    "item_id": i["id"],
                    "lines": [
                        {"item_id": i["id"], "text": f"Built {i['title_en']} feature with care."}
                    ]
                    * 6,
                }
                for i in v["ITEMS"]
            ],
        }

    mock_llm.on("rewrite_document", rewrite)
    user = await make_user()
    no_en = (
        await user.client.post("/items", json={"type": "project", "title": "영문 없음"})
    ).json()
    doc, r = await make_version(user, "resume_en", ids=[no_en["id"]])
    assert r.status_code == 422 and r.json()["error"]["code"] == "title_en_required"

    many = [
        {
            "type": "project",
            "title": f"프로젝트 {i}",
            "title_en": f"Project {i}",
            "summary": "A project.",
        }
        for i in range(25)
    ]
    ids = await seed(user, many)
    doc, r = await make_version(user, "resume_en", ids=ids)
    assert r.status_code == 202
    await drain_jobs()
    body, pages, text = await pdf_text(user, doc["id"])
    assert pages == 1
    assert body["options"]["removed_items"]
    assert any("1쪽에 맞추려고" in w for w in body["options"]["warnings"])
    first = next(iter(body["content"]["x-reportory"]["items"].values()))
    assert len(first["lines"]) == 4  # 항목당 bullet 최대 4개


async def test_access_control_and_public_document(make_user, mock_llm, anon):
    mock_llm.on("rewrite_document", lambda v: {"sections": []})
    alice, bob = await make_user(), await make_user()
    await seed(alice)
    doc, _ = await make_version(alice, "resume_ko")
    await drain_jobs()
    for path in (
        f"/documents/{doc['id']}",
        f"/documents/{doc['id']}/versions/1",
        f"/documents/{doc['id']}/versions/1/pdf",
    ):
        assert (await bob.client.get(path)).status_code == 404
    handle = f"d{alice.id.hex[:10]}"
    await alice.client.patch("/me/profile", json={"handle": handle, "public_profile_enabled": True})
    assert (await anon.get(f"/public/{handle}")).json()["documents"] == []
    await alice.client.patch(f"/documents/{doc['id']}", json={"is_public": True})
    docs = (await anon.get(f"/public/{handle}")).json()["documents"]
    assert [d["id"] for d in docs] == [doc["id"]]
    r = await anon.get(f"/public/{handle}/documents/{doc['id']}", follow_redirects=False)
    assert r.status_code == 302


async def test_preview_selection_ranks_by_format(make_user):
    user = await make_user()
    await seed(user)
    doc = (
        await user.client.post(
            "/documents", json={"format": "project_portfolio", "title": "포트폴리오"}
        )
    ).json()
    items = (await user.client.post(f"/documents/{doc['id']}/preview-selection")).json()["items"]
    assert {i["type"] for i in items} <= {"project", "activity", "experience"}
    assert [i["type"] for i in items if i["selected"]] == ["project"]


async def test_inline_edits_create_new_version(make_user, mock_llm):
    def rewrite(v):
        return {
            "sections": [
                {
                    "item_id": i["id"],
                    "lines": [{"item_id": i["id"], "text": f"{i['title']} 경험을 정리했다."}],
                }
                for i in v["ITEMS"]
            ]
        }

    mock_llm.on("rewrite_document", rewrite)
    user = await make_user()
    await seed(user)
    doc, _ = await make_version(user, "resume_ko")
    await drain_jobs()
    v1 = (await user.client.get(f"/documents/{doc['id']}/versions/1")).json()
    items = v1["content"]["x-reportory"]["items"]
    intern_id = next(k for k, v in items.items() if v["type"] == "experience")
    assert 'data-edit="line"' in v1["html"] and 'data-edit="title"' in v1["html"]

    calls_before = list(mock_llm.calls)
    r = await user.client.post(
        f"/documents/{doc['id']}/versions/1/edits",
        json={
            "items": {
                intern_id: {
                    "title": "백엔드 개발 인턴",
                    "lines": ["결제 API를 만들었다.\n응답 시간을 줄였다.", "  "],
                }
            },
        },
    )
    assert r.status_code == 202, r.text
    assert r.json()["version"]["version"] == 2
    await drain_jobs()
    assert mock_llm.calls == calls_before  # 다시 그리기는 LLM을 부르지 않는다
    body, pages, text = await pdf_text(user, doc["id"], version=2)
    edited = body["content"]["x-reportory"]["items"][intern_id]
    assert edited["title"] == "백엔드 개발 인턴"
    assert edited["lines"] == ["결제 API를 만들었다.", "응답 시간을 줄였다."]
    assert body["options"]["edited_from"] == 1
    assert "백엔드 개발 인턴" in text and "결제 API를 만들었다." in text
    work = next(w for w in body["content"]["work"] if w["x-itemId"] == intern_id)
    assert work["highlights"] == edited["lines"]
    # 원래 버전은 그대로다.
    v1_again = (await user.client.get(f"/documents/{doc['id']}/versions/1")).json()
    assert v1_again["content"]["x-reportory"]["items"][intern_id]["title"] == "백엔드 인턴"


def test_render_old_content_without_profile():
    """양식을 바꾸기 전에 저장한 내용(profile·written_on 없음)도 렌더링된다."""
    from app.services.render import render_html

    for fmt in ("resume_ko", "resume_en", "academic_cv", "project_portfolio"):
        content = {
            "basics": {"name": "홍길동"},
            "x-reportory": {"format": fmt, "language": "ko", "sections": [], "items": {}},
        }
        html = render_html(fmt, content, title="예전 문서", for_pdf=False)
        assert "<html" in html
