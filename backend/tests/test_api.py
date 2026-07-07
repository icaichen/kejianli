"""端到端 API：health / analyses / citations / projects / engines。"""

from __future__ import annotations


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_analyses_returns_score_and_recommendations(client, monkeypatch):
    # 避免真实网络：mock analysis.fetch 返回固定 HTML
    from keeplix.engines import analysis

    html = """
    <html><head><title>GEO 指南</title>
    <script type="application/ld+json">{}</script>
    <meta property="og:site_name" content="keeplix"/></head>
    <body><h1>GEO</h1><h2>方法</h2>
    <p>GEO 是让内容被 AI 引用的优化方法，覆盖率提升 30%。</p>
    <ul><li>结构化</li></ul>
    <a href="https://example.org/ref">来源</a>
    <a href="https://other.org/ref">来源2</a>
    </body></html>
    """

    async def fake_fetch(url, timeout=20.0):
        return analysis.FetchResult(url=url, status=200, html=html)

    monkeypatch.setattr(analysis, "fetch", fake_fetch)

    resp = client.post("/api/analyses", json={"url": "https://x.com", "brand_name": "keeplix"})
    assert resp.status_code == 200
    body = resp.json()
    assert 0 <= body["total"] <= 100
    assert "breakdown" in body
    assert isinstance(body["recommendations"], list)
    assert body["audit_run_id"]


def test_citations_run_with_stub(client):
    resp = client.post(
        "/api/citations/run",
        json={
            "engine_ids": ["deepseek", "kimi"],
            "prompts": ["最好的 GEO 工具", "中文内容优化"],
            "brand_name": "keeplix",
            "brand_domains": ["keeplix.com"],
            "samples": 3,
        },
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 2
    for r in results:
        assert r["sample_size"] == 6
        assert 0.0 <= r["entity_sov"] <= 1.0


def test_projects_crud(client):
    create = client.post("/api/projects", json={"name": "自推广", "primary_domain": "keeplix.com"})
    assert create.status_code == 200
    assert create.json()["name"] == "自推广"
    index = client.get("/api/projects")
    assert index.status_code == 200
    assert len(index.json()) >= 1


def test_engines_list_marks_stub(client):
    resp = client.get("/api/engines")
    assert resp.status_code == 200
    engines = {e["id"]: e for e in resp.json()}
    assert "deepseek" in engines
    # 无 key 时应为 stub
    assert engines["kimi"]["is_stub"] is True
