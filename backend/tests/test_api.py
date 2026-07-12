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
        assert r["entity_ci_low"] <= r["entity_sov"] <= r["entity_ci_high"]


def test_citations_keep_successful_engines_when_one_provider_fails(
    client, monkeypatch, _qualified_citation_provider
):
    from keeplix.agents import CitationAgent

    original_run = CitationAgent.run

    async def flaky_run(self, input_data):
        if input_data.engine_id == "kimi":
            error = RuntimeError("rate limited")
            error.response = type("Response", (), {"status_code": 429})()
            raise error
        return await original_run(self, input_data)

    monkeypatch.setattr(CitationAgent, "run", flaky_run)
    project = client.post(
        "/api/projects", json={"name": "部分成功", "primary_domain": "keeplix.com"}
    ).json()
    response = client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["qwen", "kimi", "baidu_ernie"],
            "prompts": ["GEO 工具"],
            "brand_name": "keeplix",
            "samples": 1,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert {result["engine_id"] for result in response.json()["results"]} == {
        "qwen",
        "baidu_ernie",
    }
    assert response.json()["errors"] == {"kimi": "HTTP 429：请求过于频繁或当前额度不可用"}
    dashboard = client.get(f"/api/projects/{project['id']}").json()
    assert dashboard["activities"][0]["status"] == "partial"
    assert {snapshot["engine_id"] for snapshot in dashboard["visibility"]} == {
        "qwen",
        "baidu_ernie",
    }


def test_projects_crud(client, _qualified_citation_provider):
    create = client.post("/api/projects", json={"name": "自推广", "primary_domain": "keeplix.com"})
    assert create.status_code == 200
    assert create.json()["name"] == "自推广"
    index = client.get("/api/projects")
    assert index.status_code == 200
    assert len(index.json()) >= 1

    detail = client.get(f"/api/projects/{create.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["citation_runs"] == 0
    assert detail.json()["visibility"] == []

    run = client.post(
        "/api/citations/run",
        json={
            "project_id": create.json()["id"],
            "engine_ids": ["kimi"],
            "prompts": ["最好的 GEO 工具有哪些", "如何提高 AI 引用率"],
            "brand_name": "keeplix",
            "brand_domains": ["keeplix.com"],
            "samples": 1,
        },
    )
    assert run.status_code == 200

    updated = client.get(f"/api/projects/{create.json()['id']}").json()
    activity = updated["activities"][0]
    assert activity["kind"] == "visibility"
    assert activity["input_snapshot"]["questions"] == [
        "最好的 GEO 工具有哪些",
        "如何提高 AI 引用率",
    ]
    assert activity["input_snapshot"]["engine_ids"] == ["kimi"]
    assert activity["output_summary"]["sample_count"] == 2
    assert updated["visibility"][0]["entity_ci_low"] is not None
    assert {item["prompt_text"] for item in updated["evidence"]} == {
        "最好的 GEO 工具有哪些",
        "如何提高 AI 引用率",
    }


def test_stub_evidence_never_enters_formal_visibility(client):
    project = client.post(
        "/api/projects", json={"name": "真实性闸门", "primary_domain": "keeplix.com"}
    ).json()
    response = client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["qwen"],
            "prompts": ["GEO 工具有哪些"],
            "brand_name": "keeplix",
            "samples": 1,
        },
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["report_eligible"] is False

    dashboard = client.get(f"/api/projects/{project['id']}").json()
    assert dashboard["visibility"] == []
    assert dashboard["evidence"][0]["report_eligible"] is False
    assert dashboard["evidence"][0]["measurement_scope"] == "stub"

    engines = client.get("/api/engines").json()
    qwen = next(engine for engine in engines if engine["id"] == "qwen")
    assert qwen["validation_status"] == "accepted"
    assert qwen["report_eligible"] is False
    assert qwen["is_stub"] is True


def test_tracking_plan_is_returned_on_project_dashboard(client, _qualified_citation_provider):
    project = client.post(
        "/api/projects",
        json={"name": "追踪项目", "primary_domain": "keeplix.com"},
    ).json()
    prompt_set = client.post(
        f"/api/projects/{project['id']}/prompt-sets",
        json={"name": "核心问题", "prompts": ["GEO 工具有哪些", "如何提高 AI 引用率"]},
    )
    assert prompt_set.status_code == 200

    plan = client.post(
        f"/api/projects/{project['id']}/tracking-plans",
        json={
            "prompt_set_id": prompt_set.json()["id"],
            "engine_ids": ["qwen", "kimi"],
            "samples": 2,
            "cadence": "weekly",
        },
    )
    assert plan.status_code == 200
    assert plan.json()["question_count"] == 2
    assert plan.json()["engine_ids"] == ["qwen", "kimi"]

    dashboard = client.get(f"/api/projects/{project['id']}").json()
    assert dashboard["tracking_plans"][0]["prompt_set_name"] == "核心问题"
    assert dashboard["tracking_plans"][0]["samples"] == 2
    assert dashboard["tracking_plans"][0]["next_run_at"] is not None

    execution = client.post(f"/api/projects/{project['id']}/tracking-plans/{plan.json()['id']}/run")
    assert execution.status_code == 200
    assert execution.json()["status"] == "done"
    assert len(execution.json()["results"]) == 2
    assert execution.json()["errors"] == {}

    tracked = client.get(f"/api/projects/{project['id']}").json()
    refreshed_plan = tracked["tracking_plans"][0]
    assert refreshed_plan["last_run_at"] is not None
    assert refreshed_plan["consecutive_failures"] == 0
    snapshots = [
        snapshot
        for snapshot in tracked["visibility"]
        if snapshot["tracking_plan_id"] == plan.json()["id"]
    ]
    assert {snapshot["engine_id"] for snapshot in snapshots} == {"qwen", "kimi"}
    scheduled_activities = [
        activity
        for activity in tracked["activities"]
        if activity["input_snapshot"].get("tracking_plan_id") == plan.json()["id"]
    ]
    assert len(scheduled_activities) == 2

    due_plan = client.post(
        f"/api/projects/{project['id']}/tracking-plans",
        json={
            "prompt_set_id": prompt_set.json()["id"],
            "engine_ids": ["qwen"],
            "samples": 1,
            "cadence": "daily",
            "next_run_at": "2020-01-01T00:00:00Z",
        },
    ).json()
    due = client.post("/api/tracking/run-due")
    assert due.status_code == 200
    assert [item["plan_id"] for item in due.json()["executions"]] == [due_plan["id"]]


def test_engines_list_marks_stub(client):
    resp = client.get("/api/engines")
    assert resp.status_code == 200
    engines = {e["id"]: e for e in resp.json()}
    assert "deepseek" in engines
    # 无 key 时应为 stub
    assert engines["kimi"]["is_stub"] is True


def test_tracking_plan_isolates_engine_failures(client, monkeypatch, _qualified_citation_provider):
    from keeplix.agents import CitationAgent

    original_run = CitationAgent.run

    async def flaky_run(self, input_data):
        if input_data.engine_id == "qwen":
            raise RuntimeError("simulated provider failure")
        return await original_run(self, input_data)

    monkeypatch.setattr(CitationAgent, "run", flaky_run)
    project = client.post(
        "/api/projects", json={"name": "失败隔离", "primary_domain": "keeplix.com"}
    ).json()
    prompt_set = client.post(
        f"/api/projects/{project['id']}/prompt-sets",
        json={"name": "隔离问题", "prompts": ["GEO 工具"]},
    ).json()
    plan = client.post(
        f"/api/projects/{project['id']}/tracking-plans",
        json={
            "prompt_set_id": prompt_set["id"],
            "engine_ids": ["qwen", "kimi"],
            "samples": 1,
            "cadence": "weekly",
        },
    ).json()
    execution = client.post(f"/api/projects/{project['id']}/tracking-plans/{plan['id']}/run")
    assert execution.status_code == 200
    assert execution.json()["status"] == "partial"
    assert execution.json()["errors"] == {"qwen": "RuntimeError"}
    assert [result["engine_id"] for result in execution.json()["results"]] == ["kimi"]
