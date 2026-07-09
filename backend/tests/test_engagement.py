"""服务交付工作流：一次 engagement 产出完整报告 + Deliverable。"""

from __future__ import annotations

import pytest

_HTML = """
<html><head><title>keeplix — GEO 平台</title>
<meta property="og:site_name" content="keeplix"/></head>
<body><h1>keeplix</h1><h2>能力</h2>
<p>keeplix 让内容被 AI 引用，覆盖率提升 30%。</p>
<ul><li>分析</li><li>采样</li></ul>
<a href="https://zhihu.com/x">来源</a><a href="https://baike.baidu.com/y">来源2</a>
</body></html>
"""


@pytest.fixture
def _mock_fetch(monkeypatch):
    from keeplix.engines import analysis

    async def fake_fetch(url, timeout=20.0):
        return analysis.FetchResult(url=url, status=200, html=_HTML)

    monkeypatch.setattr(analysis, "fetch", fake_fetch)


def test_engagement_run_produces_report(client, _mock_fetch):
    resp = client.post(
        "/api/engagements/run",
        json={
            "url": "https://keeplix.com",
            "brand_name": "keeplix",
            "engine_ids": ["deepseek", "kimi"],
            "prompts": ["最好的中文 GEO 工具", "如何让内容被 AI 引用"],
            "brand_domains": ["keeplix.com"],
            "samples": 3,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["deliverable_id"]
    report = body["report"]
    assert 0 <= report["total"] <= 100
    assert report["brand_name"] == "keeplix"
    assert len(report["visibility"]) == 2
    assert isinstance(report["recommendations"], list)
    assert report["summary"]  # 有 executive summary


def test_engagement_persists_deliverable(client, _mock_fetch):
    # 带 project_id 时应把 Deliverable 落库
    proj = client.post("/api/projects", json={"name": "客户A", "primary_domain": "keeplix.com"})
    project_id = proj.json()["id"]

    resp = client.post(
        "/api/engagements/run",
        json={
            "url": "https://keeplix.com",
            "brand_name": "keeplix",
            "engine_ids": ["deepseek"],
            "prompts": ["最好的中文 GEO 工具"],
            "brand_domains": ["keeplix.com"],
            "samples": 2,
            "project_id": project_id,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["report"]["visibility"][0]["sample_size"] == 2
