"""초기 데이터 가져오기(인계서 10.9절, 11.6절 완료 기준)."""

import base64
import io
import json
import zipfile

import docx
import httpx
import pytest

from app.importers import github as gh
from app.importers.linkedin import parse_date
from tests.conftest import drain_jobs
from tests.pdfgen import make_pdf
from tests.test_flow import pending

RESUME_LINES = [
    "Hong Gildong - Resume",
    "Education: Korea University, B.S. in Computer Science, 2021 - 2025",
    "Certification: SQLD (Korea Data Agency), acquired 2024",
    "Award: Grand Prize, OO Hackathon 2024",
    "Experience: Backend Intern at OO Corp, Jul 2024 - Aug 2024. Built REST APIs with FastAPI.",
    "Skills: Python, FastAPI, PostgreSQL, React, Docker, Git, Linux, AWS, Kubernetes",
]


def resume_extraction(v):
    text = v["ENTRY"]
    assert "Korea University" in text
    return {
        "is_relevant": True,
        "entry_summary": "이력서를 읽었다.",
        "items": [
            {
                "action": "create",
                "type": "education",
                "title": "Korea University",
                "details": {"degree": "B.S.", "major": "Computer Science"},
                "start_date": "2021-03-01",
                "end_date": "2025-02-01",
                "quote": "Korea University, B.S. in Computer Science, 2021 - 2025",
                "confidence": 0.9,
            },
            {
                "action": "create",
                "type": "certification",
                "title": "SQLD",
                "details": {"issuer": "Korea Data Agency"},
                "quote": "SQLD (Korea Data Agency), acquired 2024",
                "confidence": 0.9,
            },
            {
                "action": "create",
                "type": "award",
                "title": "OO Hackathon Grand Prize",
                "details": {"rank": "Grand Prize"},
                "quote": "Grand Prize, OO Hackathon 2024",
                "confidence": 0.9,
            },
            {
                "action": "create",
                "type": "award",
                "title": "지어낸 상",
                "quote": "National Award 2023",
                "confidence": 0.9,
            },
        ],
    }


async def test_resume_pdf_creates_education_certification_award(make_user, mock_llm):
    mock_llm.on("import_resume", resume_extraction)
    user = await make_user()
    r = await user.client.post(
        "/imports/resume", files={"file": ("resume.pdf", make_pdf(RESUME_LINES))}
    )
    assert r.status_code == 202, r.text
    await drain_jobs()
    imp = (await user.client.get(f"/imports/{r.json()['import']['id']}")).json()
    assert imp["status"] == "succeeded"
    assert imp["summary"]["items_proposed"] == 3 and imp["summary"]["dropped"] == 1
    types = sorted(p["item"]["type"] for p in await pending(user))
    assert types == ["award", "certification", "education"]


async def test_resume_docx(make_user, mock_llm):
    mock_llm.on("import_resume", resume_extraction)
    user = await make_user()
    d = docx.Document()
    for line in RESUME_LINES:
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    r = await user.client.post("/imports/resume", files={"file": ("cv.docx", buf.getvalue())})
    assert r.status_code == 202, r.text
    await drain_jobs()
    assert len(await pending(user)) == 3


def linkedin_zip(include_projects=False) -> bytes:
    files = {
        "Positions.csv": "Company Name,Title,Description,Location,Started On,Finished On\n"
        "OO Corp,Backend Intern,Built REST APIs.,Seoul,Jul 2024,Aug 2024\n",
        "Education.csv": "School Name,Start Date,End Date,Notes,Degree Name,Activities\n"
        "Korea University,2021,2025,,B.S.,\n",
        "Certifications.csv": "Name,Url,Authority,Started On,Finished On,License Number\n"
        "SQLD,,Korea Data Agency,Mar 2024,,2024-123456789\n",
        "Skills.csv": "Name\nPython\nFastAPI\n",
    }
    if include_projects:
        files["Projects.csv"] = "Title,Description,Url,Started On,Finished On\nX,,,,\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(f"Basic_LinkedInDataExport/{name}", content)
    return buf.getvalue()


async def test_linkedin_zip_rules_and_skipped_files(make_user, pg):
    user = await make_user(consent=False)  # CSV는 LLM을 쓰지 않으므로 동의 없이 된다
    r = await user.client.post("/imports/linkedin", files={"file": ("export.zip", linkedin_zip())})
    assert r.status_code == 202, r.text
    await drain_jobs()
    imp = (await user.client.get(f"/imports/{r.json()['import']['id']}")).json()
    s = imp["summary"]
    assert s["items_proposed"] == 3
    assert "Projects.csv: 파일이 없어 건너뜀" in s["skipped"]
    assert "Languages.csv: 파일이 없어 건너뜀" in s["skipped"]
    assert s["skills"] == ["Python", "FastAPI"]
    items = {p["item"]["type"]: p["item"] for p in await pending(user)}
    assert items["experience"]["organization"] == "OO Corp"
    assert items["experience"]["start_date"] == "2024-07-01"
    assert items["certification"]["details"] == {"issuer": "Korea Data Agency"}
    dumped = json.dumps(await pending(user))
    assert "123456789" not in dumped  # 자격증 번호는 저장하지 않는다


async def test_same_item_from_two_sources_is_one_proposal(make_user, mock_llm):
    mock_llm.on("import_resume", resume_extraction)
    user = await make_user()
    await user.client.post("/imports/resume", files={"file": ("r.pdf", make_pdf(RESUME_LINES))})
    await drain_jobs()
    await user.client.post("/imports/linkedin", files={"file": ("e.zip", linkedin_zip())})
    await drain_jobs()
    proposals = await pending(user)
    titles = sorted(p["item"]["title"] for p in proposals)
    # Korea University, SQLD는 두 출처에서 나왔지만 하나씩이다.
    assert titles.count("Korea University") == 1 and titles.count("SQLD") == 1
    edu = next(p for p in proposals if p["item"]["title"] == "Korea University")
    detail = (await user.client.get(f"/items/{edu['item_id']}")).json()
    assert len({s["import_id"] for s in detail["sources"]}) == 2


@pytest.fixture
def fake_github():
    repos = [
        {
            "name": f"repo{i}",
            "full_name": f"me/repo{i}",
            "html_url": f"https://github.com/me/repo{i}",
            "description": f"Repo {i} description.",
            "fork": False,
            "homepage": None,
            "created_at": "2025-01-01T00:00:00Z",
            "pushed_at": "2025-06-01T00:00:00Z",
            "languages_url": f"https://api.github.com/repos/me/repo{i}/languages",
        }
        for i in range(5)
    ] + [{"name": "forked", "full_name": "me/forked", "fork": True}]
    seen_tokens = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_tokens.append(req.headers.get("Authorization"))
        path = req.url.path
        if path == "/user/repos":
            return httpx.Response(200, json=repos)
        if path.endswith("/languages"):
            return httpx.Response(200, json={"Python": 800, "TypeScript": 200})
        if path.endswith("/readme"):
            if "repo0" in path:
                readme = "# repo0\nA FastAPI service that tracks study logs."
                return httpx.Response(
                    200, json={"content": base64.b64encode(readme.encode()).decode()}
                )
            return httpx.Response(404)
        return httpx.Response(404)

    gh.set_transport(httpx.MockTransport(handler))
    yield seen_tokens
    gh.set_transport(None)


async def test_github_import_five_repos(make_user, mock_llm, fake_github, pg):
    mock_llm.on(
        "import_github",
        lambda v: {
            "summary": "공부 기록을 관리하는 FastAPI 서비스다.",
            "skills": ["FastAPI", "Django"],
            "quote": "A FastAPI service that tracks study logs.",
            "confidence": 0.8,
        },
    )
    user = await make_user()
    r = await user.client.post("/imports/github", json={"provider_token": "gho_testtoken123"})
    assert r.status_code == 202
    await drain_jobs()
    assert set(fake_github) == {"Bearer gho_testtoken123"}
    proposals = await pending(user)
    assert len(proposals) == 5
    assert all(p["item"]["type"] == "project" for p in proposals)
    assert all(
        p["item"]["details"]["repo_url"].startswith("https://github.com/me/") for p in proposals
    )
    repo0 = next(p for p in proposals if p["item"]["title"] == "repo0")
    assert repo0["item"]["summary"] == "공부 기록을 관리하는 FastAPI 서비스다."
    assert "Django" not in repo0["item_skills"]  # README에 없는 기술은 버린다
    assert {"Python", "TypeScript", "FastAPI"} <= set(repo0["item_skills"])
    payload = await pg.fetchval(
        "select payload from jobs where user_id = $1 and type = 'import_github'", user.id
    )
    assert "provider_token" not in json.loads(payload)


async def test_import_requires_consent_except_linkedin(make_user):
    user = await make_user(consent=False)
    r = await user.client.post("/imports/resume", files={"file": ("r.pdf", make_pdf(RESUME_LINES))})
    assert r.status_code == 403


def test_parse_linkedin_dates():
    assert str(parse_date("Mar 2023")) == "2023-03-01"
    assert str(parse_date("2023-07")) == "2023-07-01"
    assert str(parse_date("3월 2023")) == "2023-03-01"
    assert str(parse_date("2021")) == "2021-01-01"
    assert parse_date("") is None and parse_date("someday") is None
