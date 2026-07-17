"""端到端 API：health / analyses / citations / projects / engines。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select


def _complete_research_project(name: str, **overrides) -> dict:
    return {
        "name": name,
        "brand_name": name,
        "primary_domain": "keeplix.com",
        "market": "中国大陆",
        "category": "GEO 市场研究软件",
        "competitors": ["GEO"],
        "research_objective": "研究品牌在 AI 答案中的发现率、推荐理由与引用来源。",
        **overrides,
    }


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
    engines = {engine["id"]: engine for engine in client.get("/api/engines").json()}
    assert engines["deepseek"]["runtime_status"] == "not_connected"
    assert engines["deepseek"]["last_observed_at"] is None
    assert engines["kimi"]["runtime_status"] == "not_connected"
    assert engines["kimi"]["last_observed_at"] is None


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
        "/api/projects",
        json=_complete_research_project("部分成功", brand_name="keeplix"),
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


def test_projects_crud(client, engine, _qualified_citation_provider):
    create = client.post(
        "/api/projects",
        json={
            "name": "中国洗护品类 AI 市场研究",
            "client_name": "联合利华",
            "brand_name": "多芬",
            "primary_domain": "dove.com.cn",
            "market": "中国大陆",
            "category": "个人护理",
            "competitors": ["海飞丝", "潘婷"],
            "research_objective": "了解消费者问题中各品牌的 AI 推荐份额与来源结构。",
        },
    )
    assert create.status_code == 200
    assert create.json()["name"] == "中国洗护品类 AI 市场研究"
    assert create.json()["client_name"] == "联合利华"
    assert create.json()["brand_name"] == "多芬"
    assert create.json()["competitors"] == ["海飞丝", "潘婷"]
    assert create.json()["category"] == "个人护理"
    assert create.json()["research_objective"].startswith("了解消费者问题")
    from keeplix.models import BrandEntity

    with Session(engine) as session:
        brand = session.exec(
            select(BrandEntity).where(BrandEntity.project_id == create.json()["id"])
        ).one()
        assert brand.brand_name == "多芬"
        assert brand.domains == ["dove.com.cn"]
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
            "brand_name": "多芬",
            "brand_domains": ["dove.com.cn"],
            "competitors": ["海飞丝", "潘婷"],
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


def test_research_report_waits_for_formal_baseline(client):
    project = client.post(
        "/api/projects",
        json={
            "name": "等待基线的研究",
            "client_name": "测试咨询公司",
            "brand_name": "测试品牌",
            "category": "测试品类",
        },
    ).json()

    response = client.get(f"/api/projects/{project['id']}/research-report")

    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "waiting_for_baseline"
    assert report["client_name"] == "测试咨询公司"
    assert report["brief_version"] == 1
    assert report["question_count"] == 0
    assert report["measurement_quality"]["status"] == "limited"
    assert report["sample_count"] == 0
    assert report["engine_results"] == []
    assert report["warnings"]


def test_question_framework_uses_enterprise_research_brief(client):
    project = client.post(
        "/api/projects",
        json={
            "name": "中国洗护 AI 市场研究",
            "client_name": "联合利华",
            "brand_name": "多芬",
            "market": "中国大陆",
            "category": "洗护产品",
            "competitors": ["海飞丝", "潘婷"],
            "research_objective": "了解消费者问题中的品牌推荐位置。",
        },
    ).json()

    response = client.get(f"/api/projects/{project['id']}/question-framework")

    assert response.status_code == 200
    framework = response.json()
    assert framework["project_id"] == project["id"]
    assert framework["recommended_samples"] == 2
    assert len(framework["items"]) == 16
    assert sum(item["selected"] for item in framework["items"]) == 12
    assert framework["measurement_quality"]["status"] == "comprehensive"
    assert framework["measurement_quality"]["coverage"] == {
        "branded": 3,
        "category": 3,
        "problem": 3,
        "comparison": 3,
    }
    assert {item["intent"] for item in framework["items"]} == {
        "branded",
        "category",
        "problem",
        "comparison",
    }
    assert any("多芬与海飞丝相比" in item["text"] for item in framework["items"])
    assert all("洗护产品产品" not in item["text"] for item in framework["items"])
    assert "研究目标" in framework["summary"]


def test_incomplete_brief_cannot_become_formal_research(client, _qualified_citation_provider):
    project = client.post(
        "/api/projects",
        json={"name": "范围待定", "brand_name": "示例品牌", "market": "中国大陆"},
    ).json()

    assert project["brief_ready"] is False
    assert set(project["brief_missing_fields"]) == {
        "category",
        "competitors",
        "research_objective",
    }
    framework = client.get(f"/api/projects/{project['id']}/question-framework")
    assert framework.status_code == 409
    prompt_set = client.post(
        f"/api/projects/{project['id']}/prompt-sets",
        json={"name": "含糊问题", "prompts": ["手机收纳软件推荐"]},
    )
    assert prompt_set.status_code == 400

    sample = client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["qwen"],
            "prompts": ["手机收纳软件推荐"],
            "brand_name": "示例品牌",
            "samples": 1,
        },
    )
    assert sample.status_code == 200
    assert sample.json()["results"][0]["report_eligible"] is False
    dashboard = client.get(f"/api/projects/{project['id']}").json()
    assert dashboard["visibility"] == []
    assert dashboard["activities"][0]["input_snapshot"]["formal_scope_ready"] is False


def test_sampling_cannot_silently_change_confirmed_brief(client):
    project = client.post(
        "/api/projects",
        json=_complete_research_project("口径保护", brand_name="示例品牌"),
    ).json()

    response = client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["qwen"],
            "prompts": ["整理规划应用有哪些？"],
            "brand_name": "另一个品牌",
            "competitors": ["GEO"],
            "samples": 1,
        },
    )

    assert response.status_code == 400
    assert "与项目 Brief 不一致" in response.json()["detail"]
    unchanged = client.get(f"/api/projects/{project['id']}").json()
    assert unchanged["brand_name"] == "示例品牌"
    assert unchanged["brief_version"] == 1


def test_project_brief_update_refreshes_question_framework(client):
    project = client.post(
        "/api/projects",
        json={"name": "待完善项目", "brand_name": "示例品牌"},
    ).json()

    response = client.patch(
        f"/api/projects/{project['id']}",
        json={
            "brand_name": "示例品牌",
            "primary_domain": "example.cn",
            "market": "中国大陆",
            "category": "企业协作软件",
            "competitors": ["竞品甲", "竞品乙", "竞品甲"],
            "research_objective": "了解企业采购者寻找协作平台时的自然发现率。",
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["category"] == "企业协作软件"
    assert updated["competitors"] == ["竞品甲", "竞品乙"]
    framework = client.get(f"/api/projects/{project['id']}/question-framework").json()
    assert "企业协作软件" in framework["title"]
    assert any("示例品牌与竞品甲相比" in item["text"] for item in framework["items"])
    assert "自然发现率" in framework["summary"]


def test_project_brief_change_invalidates_old_tracking_scope(
    client, _qualified_citation_provider
):
    project = client.post(
        "/api/projects",
        json={
            "name": "范围版本测试",
            "brand_name": "测试品牌",
            "category": "旧品类",
            "research_objective": "旧目标",
            "competitors": ["旧竞品"],
        },
    ).json()
    prompt_set = client.post(
        f"/api/projects/{project['id']}/prompt-sets",
        json={"name": "旧问题", "prompts": ["旧品类有哪些品牌"]},
    ).json()
    plan = client.post(
        f"/api/projects/{project['id']}/tracking-plans",
        json={
            "prompt_set_id": prompt_set["id"],
            "engine_ids": ["qwen"],
            "samples": 1,
            "cadence": "weekly",
        },
    ).json()
    baseline = client.post(
        f"/api/projects/{project['id']}/tracking-plans/{plan['id']}/run"
    )
    assert baseline.status_code == 200
    assert client.get(f"/api/projects/{project['id']}/research-report").json()["status"] == "ready"

    updated = client.patch(
        f"/api/projects/{project['id']}",
        json={"category": "新品类", "research_objective": "新目标"},
    ).json()
    dashboard = client.get(f"/api/projects/{project['id']}").json()

    assert updated["brief_version"] == 2
    assert dashboard["visibility"][0]["brief_version"] == 1
    assert dashboard["visibility"][0]["scope_current"] is False
    assert dashboard["evidence"][0]["scope_current"] is False
    assert dashboard["diagnosis"]["qualified_sample_count"] == 0
    refreshed_report = client.get(
        f"/api/projects/{project['id']}/research-report"
    ).json()
    assert refreshed_report["status"] == "waiting_for_baseline"
    assert dashboard["prompt_sets"][0]["scope_current"] is False
    stale_plan = next(item for item in dashboard["tracking_plans"] if item["id"] == plan["id"])
    assert stale_plan["scope_current"] is False
    assert stale_plan["status"] == "paused"
    assert "Brief 已更新" in stale_plan["last_error"]
    assert (
        client.post(
            f"/api/projects/{project['id']}/tracking-plans",
            json={
                "prompt_set_id": prompt_set["id"],
                "engine_ids": ["qwen"],
                "samples": 1,
            },
        ).status_code
        == 400
    )
    current_set = client.post(
        f"/api/projects/{project['id']}/prompt-sets",
        json={"name": "新问题", "prompts": ["新品类有哪些品牌"]},
    ).json()
    assert current_set["brief_version"] == 2
    assert current_set["scope_current"] is True


def test_research_report_uses_latest_qualified_run_per_engine(
    client, _qualified_citation_provider
):
    project = client.post(
        "/api/projects",
        json={
            "name": "企业 AI 市场报告",
            "client_name": "联合利华",
            "brand_name": "keeplix",
            "primary_domain": "keeplix.com",
            "market": "中国大陆",
            "category": "市场研究软件",
            "competitors": ["GEO"],
            "research_objective": "判断品牌在采购问题中的 AI 推荐位置。",
        },
    ).json()
    first = client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["qwen"],
            "prompts": ["旧的 GEO 工具问题"],
            "brand_name": "keeplix",
            "brand_domains": ["keeplix.com"],
            "competitors": ["GEO"],
            "samples": 1,
        },
    )
    assert first.status_code == 200
    latest = client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["qwen", "kimi"],
            "prompts": ["GEO 工具采购比较", "如何选择市场研究软件"],
            "brand_name": "keeplix",
            "brand_domains": ["keeplix.com"],
            "competitors": ["GEO"],
            "samples": 1,
        },
    )
    assert latest.status_code == 200

    response = client.get(f"/api/projects/{project['id']}/research-report")

    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "ready"
    assert report["client_name"] == "联合利华"
    assert report["brand_name"] == "keeplix"
    assert report["qualified_run_count"] == 2
    assert report["sample_count"] == 4
    assert report["engine_count"] == 2
    assert report["brief_version"] == 1
    assert report["question_count"] == 2
    assert report["measurement_quality"]["question_count"] == 2
    assert report["entity_sov"] == 1.0
    assert report["citation_sov"] == 1.0
    assert report["discovery_sov"] == 1.0
    assert {item["intent"] for item in report["intent_results"]} == {
        "branded", "category", "problem", "comparison"
    }
    assert {item["engine_id"] for item in report["engine_results"]} == {"qwen", "kimi"}
    assert report["competitor_results"][0]["name"] == "GEO"
    assert report["competitor_results"][0]["mention_count"] == 2
    assert report["source_results"][0] == {
        "domain": "keeplix.com",
        "citation_count": 4,
        "citation_share": 1.0,
        "owned": True,
    }
    assert report["findings"]
    assert "4 个最新样本" in report["executive_summary"]


def test_research_report_separates_discovery_from_branded_prompts(
    client, monkeypatch, _qualified_citation_provider
):
    from keeplix.providers.base import EngineResponse

    class IntentAwareProvider:
        acquisition = "api"
        measurement_scope = "citation"

        async def query(self, prompt: str) -> EngineResponse:
            answer = "keeplix 是一个研究平台" if "keeplix" in prompt else "可以考虑其他平台"
            return EngineResponse(
                answer_text=answer,
                cited_sources=[],
                raw={"provider": "intent-test", "request_id": prompt},
            )

    monkeypatch.setattr(
        "keeplix.agents.citation_agent.get_provider",
        lambda engine_id, **kwargs: IntentAwareProvider(),
    )
    monkeypatch.setattr(
        "keeplix.services.citation_service.get_provider",
        lambda engine_id, **kwargs: IntentAwareProvider(),
    )
    project = client.post(
        "/api/projects",
        json=_complete_research_project(
            "分层报告", brand_name="keeplix", category="GEO 平台"
        ),
    ).json()
    response = client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["qwen"],
            "prompts": ["keeplix 有哪些能力？", "GEO 平台有哪些值得考虑的品牌？"],
            "brand_name": "keeplix",
            "samples": 1,
        },
    )
    assert response.status_code == 200

    report = client.get(f"/api/projects/{project['id']}/research-report").json()

    assert report["entity_sov"] == 0.5
    assert report["discovery_sov"] == 0.0
    assert report["intent_results"][0]["entity_sov"] == 1.0
    assert report["intent_results"][1]["entity_sov"] == 0.0
    assert "非品牌问题中自然出现" in report["findings"][0]["title"]


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
    assert qwen["validation_status"] == "pending"
    assert qwen["report_eligible"] is False
    assert qwen["is_stub"] is True


def test_provider_validation_records_stub_failure(client):
    response = client.post("/api/engines/qwen/validations")
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "failed"
    assert run["review_status"] == "pending"
    assert run["checks"]["provider_connected"] is False
    assert run["evidence"] == []
    assert "stub" in run["error_summary"]

    review = client.post(
        f"/api/engines/qwen/validations/{run['id']}/review",
        json={"decision": "accepted", "notes": "不能接受 stub 证据"},
    )
    assert review.status_code == 409
    history = client.get("/api/engines/qwen/validations").json()
    assert [item["id"] for item in history] == [run["id"]]


def test_provider_validation_requires_human_acceptance(
    client, _qualified_citation_provider
):
    response = client.post("/api/engines/qwen/validations")
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "passed"
    assert run["review_status"] == "pending"
    assert all(run["checks"].values())
    assert len(run["evidence"]) == 2
    assert run["evidence"][0]["provider_metadata"]["request_id"] == "qwen-1"

    pending = next(engine for engine in client.get("/api/engines").json() if engine["id"] == "qwen")
    assert pending["validation_status"] == "pending"
    assert pending["report_eligible"] is False

    review = client.post(
        f"/api/engines/qwen/validations/{run['id']}/review",
        json={"decision": "accepted", "notes": "已人工对照答案、引用与请求标识。"},
    )
    assert review.status_code == 200
    assert review.json()["review_status"] == "accepted"
    accepted = next(
        engine for engine in client.get("/api/engines").json() if engine["id"] == "qwen"
    )
    assert accepted["validation_status"] == "accepted"
    assert accepted["report_eligible"] is True

    repeated = client.post(
        f"/api/engines/qwen/validations/{run['id']}/review",
        json={"decision": "rejected", "notes": "不允许覆盖已有审核结论。"},
    )
    assert repeated.status_code == 409


def test_provider_validation_rejects_overlapping_run(client, engine):
    from keeplix.models import EngineValidationRun

    with Session(engine) as session:
        session.add(EngineValidationRun(engine_id="qwen", status="running"))
        session.commit()

    response = client.post("/api/engines/qwen/validations")

    assert response.status_code == 400
    assert "正在运行" in response.json()["detail"]


def test_new_provider_validation_supersedes_pending_evidence(
    client, _qualified_citation_provider
):
    first = client.post("/api/engines/qwen/validations").json()
    second = client.post("/api/engines/qwen/validations").json()

    history = client.get("/api/engines/qwen/validations").json()
    old = next(item for item in history if item["id"] == first["id"])
    latest = next(item for item in history if item["id"] == second["id"])
    assert old["review_status"] == "rejected"
    assert "替代" in old["review_notes"]
    assert latest["review_status"] == "pending"


def test_competitor_benchmark_is_returned_and_persisted(client, _qualified_citation_provider):
    project = client.post(
        "/api/projects",
        json=_complete_research_project("竞品基准", brand_name="keeplix"),
    ).json()
    response = client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["qwen"],
            "prompts": ["GEO 工具"],
            "brand_name": "keeplix",
            "competitors": ["GEO"],
            "samples": 1,
        },
    )
    result = response.json()["results"][0]
    assert result["competitor_sov"] == {"GEO": 1.0}
    assert result["relative_sov"] == 0.5

    dashboard = client.get(f"/api/projects/{project['id']}").json()
    assert dashboard["visibility"][0]["competitor_sov"] == {"GEO": 1.0}
    assert dashboard["evidence"][0]["competitor_mentions"] == ["GEO"]
    assert dashboard["evidence"][0]["request_id"] == "qwen-1"
    assert dashboard["evidence"][0]["provider_metadata"]["model"] == "qualified-test-model"

    prompt_set = client.post(
        f"/api/projects/{project['id']}/prompt-sets",
        json={"name": "竞品追踪", "prompts": ["GEO 工具"]},
    ).json()
    plan = client.post(
        f"/api/projects/{project['id']}/tracking-plans",
        json={
            "prompt_set_id": prompt_set["id"],
            "engine_ids": ["qwen"],
            "samples": 1,
            "cadence": "manual",
        },
    ).json()
    tracked = client.post(f"/api/projects/{project['id']}/tracking-plans/{plan['id']}/run").json()
    assert tracked["results"][0]["competitor_sov"] == {"GEO": 1.0}


def test_project_diagnosis_uses_only_qualified_answer_evidence(
    client, _qualified_citation_provider
):
    project = client.post(
        "/api/projects", json=_complete_research_project("诊断证据")
    ).json()
    # A real/qualified answer-surface sample. The fixture mentions the brand
    # but has no own-domain source, yielding a citation gap.
    client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["qwen"],
            "prompts": ["GEO 工具有哪些"],
            "brand_name": "诊断证据",
            "competitors": ["GEO"],
            "samples": 1,
        },
    )
    # Stub evidence is retained by the product, but cannot influence diagnosis.
    client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["deepseek"],
            "prompts": ["另一个问题"],
            "brand_name": "诊断证据",
            "samples": 1,
        },
    )
    dashboard = client.get(f"/api/projects/{project['id']}").json()
    diagnosis = dashboard["diagnosis"]
    assert diagnosis["qualified_sample_count"] == 1
    assert diagnosis["qualified_run_count"] == 1
    assert diagnosis["insights"][0]["kind"] == "citation_gap"
    assert diagnosis["insights"][0]["engine_id"] == "qwen"
    assert diagnosis["insights"][0]["competitor_mentions"] == {"GEO": 1}


def test_qualified_diagnosis_can_create_idempotent_traceable_work_item(
    client, engine, _qualified_citation_provider
):
    project = client.post(
        "/api/projects", json=_complete_research_project("诊断转工作")
    ).json()
    client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["qwen"],
            "prompts": ["GEO 工具有哪些"],
            "brand_name": "诊断转工作",
            "competitors": ["GEO"],
            "samples": 1,
        },
    )
    dashboard = client.get(f"/api/projects/{project['id']}").json()
    insight = dashboard["diagnosis"]["insights"][0]
    response = client.post(
        f"/api/projects/{project['id']}/diagnosis/{insight['id']}/work-items"
    )
    assert response.status_code == 200
    item = response.json()
    assert item["evidence_snapshot"]["diagnosis_id"] == insight["id"]
    assert item["evidence_snapshot"]["citation_run_ids"] == insight["evidence_run_ids"]
    premature_verification = client.post(
        f"/api/projects/{project['id']}/cycles/{item['cycle_id']}/verify"
    )
    assert premature_verification.status_code == 400
    assert "必须先完成" in premature_verification.json()["detail"]

    same = client.post(
        f"/api/projects/{project['id']}/diagnosis/{insight['id']}/work-items"
    )
    assert same.status_code == 200
    assert same.json()["id"] == item["id"]

    updated = client.get(f"/api/projects/{project['id']}").json()
    assert len(updated["cycles"]) == 1
    assert updated["cycles"][0]["measurement_config"]["questions"] == ["GEO 工具有哪些"]
    assert updated["cycles"][0]["measurement_config"]["engine_ids"] == ["qwen"]

    artifact = client.post(
        f"/api/projects/{project['id']}/work-items/{item['id']}/artifacts",
        json={
            "kind": "instructions",
            "title": "证据执行说明",
            "content": "仅使用可验证事实；实施后按原问题复测。",
            "structured_content": {},
        },
    )
    assert artifact.status_code == 200
    fact = client.post(
        f"/api/projects/{project['id']}/brand-facts",
        json={
            "fact_type": "policy",
            "claim": "所有优化草稿在发布前需要人工审批。",
            "source_url": "https://neutral-product.example/governance",
        },
    )
    assert fact.status_code == 200
    policy = client.put(
        f"/api/projects/{project['id']}/agent-policy",
        json={
            "enabled": True,
            "generation_engine": "deepseek",
            "max_actions_per_run": 1,
            "per_run_budget": 0.25,
            "monthly_budget": 5.0,
        },
    )
    assert policy.status_code == 200
    # Compatibility check: a diagnostic cycle written before the explicit
    # report_eligible field still has immutable qualified CitationRun evidence.
    from keeplix.models import GeoCycle

    with Session(engine) as session:
        cycle = session.get(GeoCycle, item["cycle_id"])
        assert cycle is not None
        cycle.baseline_summary["engines"][0].pop("report_eligible", None)
        session.add(cycle)
        session.commit()
    agent_plan = client.post(
        f"/api/projects/{project['id']}/agent-runs",
        json={"cycle_id": item["cycle_id"], "goal": "为证据诊断准备草稿"},
    )
    assert agent_plan.status_code == 200
    assert agent_plan.json()["status"] == "awaiting_approval"
    assert agent_plan.json()["actions"][0]["source_artifact_id"] == artifact.json()["id"]
    rejected = client.patch(
        f"/api/projects/{project['id']}/agent-runs/{agent_plan.json()['id']}",
        json={"decision": "reject"},
    )
    assert rejected.status_code == 200
    approved = client.patch(
        f"/api/projects/{project['id']}/artifacts/{artifact.json()['id']}",
        json={"status": "approved"},
    )
    assert approved.status_code == 200
    delivery = client.post(
        f"/api/projects/{project['id']}/artifacts/{artifact.json()['id']}/deliveries",
        json={
            "method": "manual",
            "status": "published",
            "target_url": "https://keeplix.com/evidence-update",
            "notes": "已按批准草稿实施",
        },
    )
    assert delivery.status_code == 200
    verification = client.post(
        f"/api/projects/{project['id']}/cycles/{item['cycle_id']}/verify"
    )
    assert verification.status_code == 200
    assert verification.json()["status"] == "complete"
    assert verification.json()["verification_summary"]["questions"] == ["GEO 工具有哪些"]
    assert verification.json()["verification_summary"]["changes"][0]["target_url"] == (
        "https://keeplix.com/evidence-update"
    )


def test_prompt_set_versions_preserve_existing_tracking_scope(client, _qualified_citation_provider):
    project = client.post(
        "/api/projects", json=_complete_research_project("版本化问题集")
    ).json()
    first = client.post(
        f"/api/projects/{project['id']}/prompt-sets",
        json={"name": "核心意图", "prompts": ["GEO 工具有哪些"]},
    ).json()
    plan = client.post(
        f"/api/projects/{project['id']}/tracking-plans",
        json={
            "prompt_set_id": first["id"],
            "engine_ids": ["qwen"],
            "samples": 1,
            "cadence": "manual",
        },
    ).json()
    second = client.post(
        f"/api/projects/{project['id']}/prompt-sets/{first['id']}/versions",
        json={"prompts": ["GEO 工具有哪些", "如何提高 AI 引用率"]},
    )
    assert second.status_code == 200
    assert second.json()["version"] == 2
    assert second.json()["source_prompt_set_id"] == first["id"]

    prompt_sets = client.get(f"/api/projects/{project['id']}/prompt-sets").json()
    old = next(item for item in prompt_sets if item["id"] == first["id"])
    assert old["active"] is False
    assert old["prompts"] == ["GEO 工具有哪些"]
    assert (
        client.post(
            f"/api/projects/{project['id']}/tracking-plans",
            json={
                "prompt_set_id": first["id"],
                "engine_ids": ["qwen"],
                "samples": 1,
                "cadence": "manual",
            },
        ).status_code
        == 400
    )

    execution = client.post(f"/api/projects/{project['id']}/tracking-plans/{plan['id']}/run").json()
    assert execution["results"][0]["measurement_quality"]["question_count"] == 1


def test_tracking_plan_is_returned_on_project_dashboard(client, _qualified_citation_provider):
    project = client.post(
        "/api/projects",
        json=_complete_research_project("追踪项目"),
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
    assert plan.json()["measurement_quality"]["status"] == "limited"
    assert {item["intent"] for item in plan.json()["prompt_items"]} == {
        "category",
        "problem",
    }
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
    assert {snapshot["comparison_status"] for snapshot in snapshots} == {"baseline"}
    scheduled_activities = [
        activity
        for activity in tracked["activities"]
        if activity["input_snapshot"].get("tracking_plan_id") == plan.json()["id"]
    ]
    assert len(scheduled_activities) == 2

    repeated = client.post(
        f"/api/projects/{project['id']}/tracking-plans/{plan.json()['id']}/run"
    )
    assert repeated.status_code == 200
    repeated_dashboard = client.get(f"/api/projects/{project['id']}").json()
    latest_by_engine = {}
    for snapshot in repeated_dashboard["visibility"]:
        if snapshot["tracking_plan_id"] == plan.json()["id"]:
            latest_by_engine.setdefault(snapshot["engine_id"], snapshot)
    assert set(latest_by_engine) == {"qwen", "kimi"}
    assert {
        snapshot["comparison_status"] for snapshot in latest_by_engine.values()
    } == {"comparable"}
    assert {snapshot["entity_delta"] for snapshot in latest_by_engine.values()} == {0.0}
    assert {snapshot["citation_delta"] for snapshot in latest_by_engine.values()} == {0.0}

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


def test_visibility_comparison_resets_when_answer_scope_changes():
    from keeplix.models import VisibilityScore
    from keeplix.services.project_service import _visibility_comparisons

    baseline = VisibilityScore(
        id="baseline",
        project_id="project",
        engine_id="qwen",
        tracking_plan_id="plan",
        surface_name="千问联网检索",
        provider_acquisition="api",
        measurement_scope="citation",
        period=datetime(2026, 7, 1, tzinfo=UTC),
        entity_sov=0.2,
        citation_sov=0.1,
    )
    changed = VisibilityScore(
        id="changed",
        project_id="project",
        engine_id="qwen",
        tracking_plan_id="plan",
        surface_name="千问普通聊天",
        provider_acquisition="api",
        measurement_scope="brand_awareness",
        period=datetime(2026, 7, 8, tzinfo=UTC),
        entity_sov=0.8,
        citation_sov=0.0,
    )

    comparisons = _visibility_comparisons([changed, baseline])

    assert comparisons["baseline"]["comparison_status"] == "baseline"
    assert comparisons["changed"]["comparison_status"] == "scope_changed"
    assert "entity_delta" not in comparisons["changed"]


def test_tracking_plan_lease_prevents_duplicate_execution(
    client, engine, _qualified_citation_provider
):
    from keeplix.models import TrackingPlan

    project = client.post(
        "/api/projects", json=_complete_research_project("租约测试")
    ).json()
    prompt_set = client.post(
        f"/api/projects/{project['id']}/prompt-sets",
        json={"name": "租约问题", "prompts": ["GEO 工具"]},
    ).json()
    plan = client.post(
        f"/api/projects/{project['id']}/tracking-plans",
        json={
            "prompt_set_id": prompt_set["id"],
            "engine_ids": ["qwen"],
            "samples": 1,
            "cadence": "daily",
            "next_run_at": "2020-01-01T00:00:00Z",
        },
    ).json()

    with Session(engine) as session:
        stored = session.get(TrackingPlan, plan["id"])
        assert stored is not None
        stored.lease_token = "other-worker"
        stored.lease_expires_at = datetime.now(UTC) + timedelta(minutes=10)
        session.add(stored)
        session.commit()

    assert client.post("/api/tracking/run-due").json()["executions"] == []
    manual = client.post(f"/api/projects/{project['id']}/tracking-plans/{plan['id']}/run")
    assert manual.status_code == 400
    assert manual.json()["detail"] == "追踪计划正在执行，请稍后重试"

    with Session(engine) as session:
        stored = session.get(TrackingPlan, plan["id"])
        assert stored is not None
        stored.lease_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.add(stored)
        session.commit()

    recovered = client.post("/api/tracking/run-due").json()["executions"]
    assert [item["plan_id"] for item in recovered] == [plan["id"]]
    with Session(engine) as session:
        stored = session.get(TrackingPlan, plan["id"])
        assert stored is not None
        assert stored.lease_token is None
        assert stored.lease_expires_at is None


def test_due_tracking_isolates_invalid_plans(client, engine, _qualified_citation_provider):
    from keeplix.models import Prompt, TrackingPlan

    project = client.post(
        "/api/projects", json=_complete_research_project("批量追踪")
    ).json()
    invalid_prompt_set = client.post(
        f"/api/projects/{project['id']}/prompt-sets",
        json={"name": "失效问题", "prompts": ["旧问题"]},
    ).json()
    valid_prompt_set = client.post(
        f"/api/projects/{project['id']}/prompt-sets",
        json={"name": "有效问题", "prompts": ["GEO 工具"]},
    ).json()

    def create_due_plan(prompt_set_id: str) -> dict:
        return client.post(
            f"/api/projects/{project['id']}/tracking-plans",
            json={
                "prompt_set_id": prompt_set_id,
                "engine_ids": ["qwen"],
                "samples": 1,
                "cadence": "daily",
                "next_run_at": "2020-01-01T00:00:00Z",
            },
        ).json()

    invalid_plan = create_due_plan(invalid_prompt_set["id"])
    valid_plan = create_due_plan(valid_prompt_set["id"])
    with Session(engine) as session:
        prompts = session.exec(
            select(Prompt).where(Prompt.prompt_set_id == invalid_prompt_set["id"])
        ).all()
        for prompt in prompts:
            prompt.active = False
            session.add(prompt)
        session.commit()

    executions = client.post("/api/tracking/run-due").json()["executions"]
    by_plan = {item["plan_id"]: item for item in executions}
    assert by_plan[invalid_plan["id"]]["status"] == "failed"
    assert by_plan[invalid_plan["id"]]["errors"] == {"plan": "追踪计划没有可用问题"}
    assert by_plan[valid_plan["id"]]["status"] == "done"

    with Session(engine) as session:
        failed = session.get(TrackingPlan, invalid_plan["id"])
        assert failed is not None
        assert failed.consecutive_failures == 1
        assert failed.lease_token is None
        assert failed.next_run_at is not None
        assert failed.next_run_at <= datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=6)


def test_engines_list_marks_stub(client):
    resp = client.get("/api/engines")
    assert resp.status_code == 200
    engines = {e["id"]: e for e in resp.json()}
    assert "deepseek" in engines
    # 无 key 时应为 stub
    assert engines["kimi"]["is_stub"] is True
    assert engines["qwen"]["region_language"] == "zh-CN"
    assert engines["qwen"]["auth_mode"] == "api_key"
    assert engines["qwen"]["cost_note"]
    assert engines["kimi"]["runtime_status"] == "not_connected"
    assert engines["kimi"]["last_observed_at"] is None


def test_tracking_plan_isolates_engine_failures(client, monkeypatch, _qualified_citation_provider):
    from keeplix.agents import CitationAgent

    original_run = CitationAgent.run

    async def flaky_run(self, input_data):
        if input_data.engine_id == "qwen":
            raise RuntimeError("simulated provider failure")
        return await original_run(self, input_data)

    monkeypatch.setattr(CitationAgent, "run", flaky_run)
    project = client.post(
        "/api/projects", json=_complete_research_project("失败隔离")
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

    engines = {engine["id"]: engine for engine in client.get("/api/engines").json()}
    assert engines["qwen"]["runtime_status"] == "degraded"
    assert engines["qwen"]["last_error"] == "RuntimeError"
    assert engines["qwen"]["last_failure_at"] is not None
    assert engines["kimi"]["runtime_status"] == "ready"
    assert engines["kimi"]["last_success_at"] is not None
    assert engines["kimi"]["last_error"] == ""


def test_cycle_verification_blocks_false_attribution_when_surface_changes(
    client, engine, monkeypatch
):
    from keeplix.models import GeoCycle
    from keeplix.schemas import CitationRunResponse, SoVEngineResult
    from keeplix.services import project_service

    project = client.post(
        "/api/projects", json=_complete_research_project("复测范围漂移")
    ).json()
    with Session(engine) as session:
        cycle = GeoCycle(
            project_id=project["id"],
            name="范围漂移验证",
            stage="verify",
            measurement_config={
                "brief_version": project["brief_version"],
                "questions": ["GEO 工具有哪些"],
                "engine_ids": ["qwen"],
                "samples": 1,
                "brand_name": project["brand_name"],
            },
            baseline_summary={
                "engines": [
                    {
                        "engine_id": "qwen",
                        "surface_name": "千问联网检索 Agent v1",
                        "acquisition": "api",
                        "measurement_scope": "citation",
                        "report_eligible": True,
                        "entity_sov": 0.2,
                        "citation_sov": 0.1,
                        "sample_size": 1,
                    }
                ]
            },
        )
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        cycle_id = cycle.id

    async def changed_surface(*args, **kwargs):
        return CitationRunResponse(
            results=[
                SoVEngineResult(
                    engine_id="qwen",
                    surface_name="千问联网检索 Agent v2",
                    acquisition="api",
                    measurement_scope="citation",
                    report_eligible=True,
                    entity_sov=0.8,
                    citation_sov=0.7,
                    avg_rank=None,
                    sample_size=1,
                    entity_ci_low=0.5,
                    entity_ci_high=1.0,
                    citation_ci_low=0.4,
                    citation_ci_high=1.0,
                )
            ]
        )

    monkeypatch.setattr(project_service, "run_citations", changed_surface)
    response = client.post(f"/api/projects/{project['id']}/cycles/{cycle_id}/verify")
    assert response.status_code == 200
    summary = response.json()["verification_summary"]
    assert summary["comparison_status"] == "scope_changed"
    assert "不能归因" in summary["comparison_note"]
    comparison = summary["engines"][0]
    assert comparison["comparison_status"] == "scope_changed"
    assert comparison["entity_delta"] is None
    assert comparison["citation_delta"] is None
    assert comparison["entity_assessment"] == "not_comparable"
    assert "答案面已从" in comparison["comparison_reasons"][0]


def test_cycle_verification_rejects_old_brief_scope(client, engine, monkeypatch):
    from keeplix.models import GeoCycle
    from keeplix.services import project_service

    project = client.post(
        "/api/projects", json=_complete_research_project("旧 Brief 复测")
    ).json()
    with Session(engine) as session:
        cycle = GeoCycle(
            project_id=project["id"],
            name="旧口径周期",
            stage="verify",
            measurement_config={
                "brief_version": project["brief_version"],
                "questions": ["GEO 工具有哪些"],
                "engine_ids": ["qwen"],
            },
            baseline_summary={"engines": []},
        )
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        cycle_id = cycle.id

    updated = client.patch(
        f"/api/projects/{project['id']}",
        json={"category": "更新后的 GEO 软件品类"},
    )
    assert updated.status_code == 200
    assert updated.json()["brief_version"] == project["brief_version"] + 1

    async def should_not_run(*args, **kwargs):
        raise AssertionError("旧 Brief 不应触发付费复测")

    monkeypatch.setattr(project_service, "run_citations", should_not_run)
    response = client.post(f"/api/projects/{project['id']}/cycles/{cycle_id}/verify")
    assert response.status_code == 400
    assert "建立新基线" in response.json()["detail"]
