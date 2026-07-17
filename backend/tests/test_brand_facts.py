"""已核验品牌事实与证据化优化产物的端到端测试。"""

from __future__ import annotations

from keeplix.providers.base import EngineResponse


def _complete_project(name: str = "中性测试品牌") -> dict:
    return {
        "name": name,
        "brand_name": name,
        "primary_domain": "neutral-product.example",
        "market": "中国大陆",
        "category": "企业软件",
        "competitors": ["同类产品"],
        "research_objective": "评估品牌在 AI 答案中的提及和引用表现。",
    }


def _create_diagnosis_work_item(client, project: dict) -> dict:
    citation = client.post(
        "/api/citations/run",
        json={
            "project_id": project["id"],
            "engine_ids": ["qwen"],
            "prompts": ["企业软件如何选择"],
            "brand_name": project["brand_name"],
            "competitors": project["competitors"],
            "samples": 1,
        },
    )
    assert citation.status_code == 200
    dashboard = client.get(f"/api/projects/{project['id']}").json()
    insight = dashboard["diagnosis"]["insights"][0]
    response = client.post(
        f"/api/projects/{project['id']}/diagnosis/{insight['id']}/work-items"
    )
    assert response.status_code == 200
    return response.json()


def test_brand_facts_are_traceable_and_reviewable(client):
    project = client.post("/api/projects", json=_complete_project()).json()
    invalid = client.post(
        f"/api/projects/{project['id']}/brand-facts",
        json={
            "fact_type": "product",
            "claim": "支持将诊断结果转为待审核优化工作。",
            "source_url": "not-a-url",
        },
    )
    assert invalid.status_code == 400

    created = client.post(
        f"/api/projects/{project['id']}/brand-facts",
        json={
            "fact_type": "product",
            "claim": "支持将诊断结果转为待审核优化工作。",
            "source_url": "https://neutral-product.example/product",
        },
    )
    assert created.status_code == 200
    assert created.json()["status"] == "verified"
    assert created.json()["created_by"] == "user"

    duplicate = client.post(
        f"/api/projects/{project['id']}/brand-facts",
        json={
            "fact_type": "product",
            "claim": "支持将诊断结果转为待审核优化工作。",
            "source_url": "https://neutral-product.example/product",
        },
    )
    assert duplicate.json()["id"] == created.json()["id"]

    rejected = client.patch(
        f"/api/projects/{project['id']}/brand-facts/{created.json()['id']}",
        json={"status": "rejected"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    facts = client.get(f"/api/projects/{project['id']}/brand-facts").json()
    assert facts == [rejected.json()]


def test_formal_diagnosis_and_verified_facts_generate_reviewable_artifact(
    client, monkeypatch, _qualified_citation_provider
):
    project = client.post("/api/projects", json=_complete_project()).json()
    item = _create_diagnosis_work_item(client, project)

    without_facts = client.post(
        f"/api/projects/{project['id']}/work-items/{item['id']}/generate-artifact",
        json={"kind": "content", "engine_id": "deepseek"},
    )
    assert without_facts.status_code == 400
    assert "已验证品牌事实" in without_facts.json()["detail"]

    fact = client.post(
        f"/api/projects/{project['id']}/brand-facts",
        json={
            "fact_type": "proof",
            "claim": "所有 AI 生成产物在发布前都需要人工批准。",
            "source_url": "https://neutral-product.example/governance",
        },
    ).json()
    captured: dict[str, str] = {}

    class GenerationProvider:
        acquisition = "api"

        async def query(self, prompt: str) -> EngineResponse:
            captured["prompt"] = prompt
            return EngineResponse(
                answer_text=(
                    "# 建议草稿\n\n"
                    "所有 AI 生成产物在发布前都需要人工批准。\n\n"
                    "事实来源：https://neutral-product.example/governance"
                )
            )

    monkeypatch.setattr(
        "keeplix.services.artifact_generation_service.get_provider",
        lambda _engine_id: GenerationProvider(),
    )
    generated = client.post(
        f"/api/projects/{project['id']}/work-items/{item['id']}/generate-artifact",
        json={"kind": "content", "engine_id": "deepseek"},
    )
    assert generated.status_code == 200
    artifact = generated.json()
    assert artifact["created_by"] == "assistant"
    assert artifact["status"] == "draft"
    assert artifact["source_snapshot"]["brand_fact_ids"] == [fact["id"]]
    assert artifact["source_snapshot"]["generation_engine"] == "deepseek"
    assert artifact["source_snapshot"]["diagnosis_id"]
    assert fact["claim"] in captured["prompt"]
    assert fact["source_url"] in captured["prompt"]
    engines = {item["id"]: item for item in client.get("/api/engines").json()}
    assert engines["deepseek"]["runtime_status"] == "ready"

    detail = client.get(
        f"/api/projects/{project['id']}/work-items/{item['id']}"
    ).json()
    assert detail["item"]["status"] == "review"
    assert detail["artifacts"][0]["id"] == artifact["id"]
    dashboard = client.get(f"/api/projects/{project['id']}").json()
    assert any(
        activity["kind"] == "optimization"
        and activity["output_summary"]["artifact_id"] == artifact["id"]
        for activity in dashboard["activities"]
    )

    class RateLimitedProvider:
        acquisition = "api"

        async def query(self, prompt: str) -> EngineResponse:
            error = RuntimeError("provider response must not leak")
            error.response = type("Response", (), {"status_code": 429})()
            raise error

    monkeypatch.setattr(
        "keeplix.services.artifact_generation_service.get_provider",
        lambda _engine_id: RateLimitedProvider(),
    )
    rate_limited = client.post(
        f"/api/projects/{project['id']}/work-items/{item['id']}/generate-artifact",
        json={"kind": "instructions", "engine_id": "deepseek"},
    )
    assert rate_limited.status_code == 400
    assert rate_limited.json()["detail"] == (
        "生成引擎当前限频或额度不足，请稍后重试或切换引擎"
    )
    assert "provider response" not in rate_limited.text
    engines = {item["id"]: item for item in client.get("/api/engines").json()}
    assert engines["deepseek"]["runtime_status"] == "degraded"
    assert "provider response" not in engines["deepseek"]["last_error"]

    revision = client.post(
        f"/api/projects/{project['id']}/work-items/{item['id']}/artifacts",
        json={
            "kind": "content",
            "title": artifact["title"],
            "content": f"{artifact['content']}\n\n用户核对后的修订。",
            "structured_content": {},
            "source_artifact_id": artifact["id"],
        },
    )
    assert revision.status_code == 200
    revised = revision.json()
    assert revised["source_snapshot"]["brand_fact_ids"] == [fact["id"]]
    assert revised["source_snapshot"]["generation_engine"] == "deepseek"
    assert revised["source_snapshot"]["revised_from_artifact_id"] == artifact["id"]

    rejected = client.patch(
        f"/api/projects/{project['id']}/brand-facts/{fact['id']}",
        json={"status": "rejected"},
    )
    assert rejected.status_code == 200
    approval = client.patch(
        f"/api/projects/{project['id']}/artifacts/{revised['id']}",
        json={"status": "approved"},
    )
    assert approval.status_code == 400
    assert "品牌事实已停用" in approval.json()["detail"]


def test_old_brief_evidence_cannot_generate_current_artifact(
    client, monkeypatch, _qualified_citation_provider
):
    project = client.post("/api/projects", json=_complete_project()).json()
    item = _create_diagnosis_work_item(client, project)
    client.post(
        f"/api/projects/{project['id']}/brand-facts",
        json={
            "fact_type": "product",
            "claim": "可保留每次测量的证据范围。",
            "source_url": "https://neutral-product.example/evidence",
        },
    )
    updated = client.patch(
        f"/api/projects/{project['id']}",
        json={"research_objective": "改为评估引用来源质量与竞品差距。"},
    )
    assert updated.status_code == 200
    assert updated.json()["brief_version"] == project["brief_version"] + 1

    class UnusedProvider:
        acquisition = "api"

        async def query(self, prompt: str) -> EngineResponse:
            raise AssertionError("旧 Brief 工作项不应请求生成引擎")

    monkeypatch.setattr(
        "keeplix.services.artifact_generation_service.get_provider",
        lambda _engine_id: UnusedProvider(),
    )
    generated = client.post(
        f"/api/projects/{project['id']}/work-items/{item['id']}/generate-artifact",
        json={"kind": "content", "engine_id": "deepseek"},
    )
    assert generated.status_code == 400
    assert "旧研究 Brief" in generated.json()["detail"]

    manual_revision = client.post(
        f"/api/projects/{project['id']}/work-items/{item['id']}/artifacts",
        json={
            "kind": "content",
            "title": "绕过旧范围的手工草稿",
            "content": "不应保存",
            "structured_content": {},
        },
    )
    assert manual_revision.status_code == 400
    assert "旧研究 Brief" in manual_revision.json()["detail"]
