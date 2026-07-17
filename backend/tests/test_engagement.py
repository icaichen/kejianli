"""服务交付工作流：一次 engagement 产出完整报告 + Deliverable。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session

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


def test_engagement_persists_deliverable(
    client, _mock_fetch, engine, _qualified_citation_provider
):
    # 带 project_id 时应把 Deliverable 落库
    proj = client.post(
        "/api/projects",
        json={
            "name": "客户A",
            "brand_name": "keeplix",
            "primary_domain": "keeplix.com",
            "market": "中国大陆",
            "category": "GEO 市场研究软件",
            "competitors": ["竞品 GEO"],
            "research_objective": "验证实施内容是否改善真实 AI 答案中的品牌引用。",
        },
    )
    project_id = proj.json()["id"]

    resp = client.post(
        "/api/engagements/run",
        json={
            "url": "https://keeplix.com",
            "brand_name": "keeplix",
            "engine_ids": ["qwen"],
            "prompts": ["最好的中文 GEO 工具"],
            "brand_domains": ["keeplix.com"],
            "competitors": ["竞品 GEO"],
            "samples": 2,
            "project_id": project_id,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["report"]["visibility"][0]["sample_size"] == 2
    dashboard = client.get(f"/api/projects/{project_id}").json()
    assert dashboard["cycles"][0]["stage"] == "improve"
    assert dashboard["work_items"]
    assert dashboard["work_items"][0]["evidence_snapshot"]["baseline_score"] >= 0
    assert {activity["kind"] for activity in dashboard["activities"]} >= {
        "audit",
        "visibility",
    }

    work_item = dashboard["work_items"][0]
    for deferred_item in dashboard["work_items"][1:]:
        dismissed = client.patch(
            f"/api/projects/{project_id}/work-items/{deferred_item['id']}",
            json={"status": "dismissed"},
        )
        assert dismissed.status_code == 200
    premature_done = client.patch(
        f"/api/projects/{project_id}/work-items/{work_item['id']}",
        json={"status": "done"},
    )
    assert premature_done.status_code == 400
    detail = client.get(f"/api/projects/{project_id}/work-items/{work_item['id']}")
    assert detail.status_code == 200
    assert detail.json()["artifacts"]
    original_artifact = detail.json()["artifacts"][0]
    revision = client.post(
        f"/api/projects/{project_id}/work-items/{work_item['id']}/artifacts",
        json={
            "kind": original_artifact["kind"],
            "title": original_artifact["title"],
            "content": f"{original_artifact['content']}\n用户修订。",
            "structured_content": original_artifact["structured_content"],
            "source_artifact_id": original_artifact["id"],
        },
    )
    assert revision.status_code == 200
    assert revision.json()["version"] == original_artifact["version"] + 1
    assert revision.json()["source_snapshot"]["revised_from_artifact_id"] == (
        original_artifact["id"]
    )
    approved = client.patch(
        f"/api/projects/{project_id}/artifacts/{revision.json()['id']}",
        json={"status": "approved"},
    )
    assert approved.status_code == 200
    exported = client.post(f"/api/projects/{project_id}/artifacts/{revision.json()['id']}/export")
    assert exported.status_code == 200
    assert exported.json()["content"].endswith("用户修订。")
    assert exported.json()["delivery"]["status"] == "exported"
    implemented = client.post(
        f"/api/projects/{project_id}/artifacts/{revision.json()['id']}/deliveries",
        json={
            "method": "manual",
            "status": "published",
            "target_url": "https://keeplix.com/updated-page",
            "notes": "已替换首页内容",
            "retest_after_days": 3,
        },
    )
    assert implemented.status_code == 200
    assert implemented.json()["published_at"]
    implemented_detail = client.get(
        f"/api/projects/{project_id}/work-items/{work_item['id']}"
    ).json()
    retest_plan = implemented_detail["retest_plan"]
    assert retest_plan["status"] == "scheduled"
    scheduled_for = datetime.fromisoformat(retest_plan["scheduled_for"])
    published_at = datetime.fromisoformat(implemented.json()["published_at"])
    assert timedelta(days=2, hours=23) < scheduled_for - published_at < timedelta(
        days=3, minutes=1
    )

    updated = client.patch(
        f"/api/projects/{project_id}/work-items/{work_item['id']}",
        json={"status": "in_progress", "execution_mode": "self"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"
    assert updated.json()["execution_mode"] == "self"

    cycle = dashboard["cycles"][0]
    assert cycle["measurement_config"]["questions"] == ["最好的中文 GEO 工具"]
    from keeplix.models import CycleRetestPlan

    with Session(engine) as session:
        stored_retest = session.get(CycleRetestPlan, retest_plan["id"])
        assert stored_retest is not None
        stored_retest.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
        session.add(stored_retest)
        session.commit()
    due = client.post("/api/retests/run-due")
    assert due.status_code == 200
    assert due.json() == {
        "processed": 1,
        "completed": 1,
        "failed": 0,
        "plan_ids": [retest_plan["id"]],
        "errors": {},
    }
    verified_detail = client.get(
        f"/api/projects/{project_id}/work-items/{work_item['id']}"
    ).json()
    assert verified_detail["retest_plan"]["status"] == "complete"
    verification_summary = client.get(f"/api/projects/{project_id}").json()["cycles"][0][
        "verification_summary"
    ]
    comparison = verification_summary["engines"][0]
    assert comparison["entity_delta"] == 0
    assert comparison["citation_delta"] == 0
    assert comparison["entity_assessment"] == "unchanged"
    assert verification_summary["changes"][0]["target_url"] == (
        "https://keeplix.com/updated-page"
    )

    verified_dashboard = client.get(f"/api/projects/{project_id}").json()
    assert verified_dashboard["cycles"][0]["stage"] == "complete"
    visibility_activities = [
        activity
        for activity in verified_dashboard["activities"]
        if activity["kind"] == "visibility"
    ]
    assert len(visibility_activities) == 2
    assert all(
        activity["input_snapshot"]["questions"] == ["最好的中文 GEO 工具"]
        for activity in visibility_activities
    )


def test_agent_requires_policy_budget_approval_and_human_publish(
    client, _mock_fetch, monkeypatch, _qualified_citation_provider
):
    from keeplix.providers.base import EngineResponse

    project = client.post(
        "/api/projects",
        json={
            "name": "Agent 客户",
            "brand_name": "keeplix",
            "primary_domain": "keeplix.com",
            "market": "中国大陆",
            "category": "GEO 市场研究软件",
            "competitors": ["竞品 GEO"],
            "research_objective": "根据真实答案证据建立可审批的 GEO 优化循环。",
        },
    ).json()
    client.post(
        "/api/engagements/run",
        json={
            "url": "https://keeplix.com",
            "brand_name": "keeplix",
            "engine_ids": ["qwen"],
            "prompts": ["GEO 工具"],
            "brand_domains": ["keeplix.com"],
            "samples": 1,
            "project_id": project["id"],
        },
    )
    dashboard = client.get(f"/api/projects/{project['id']}").json()
    cycle_id = dashboard["cycles"][0]["id"]
    blocked = client.post(
        f"/api/projects/{project['id']}/agent-runs",
        json={"cycle_id": cycle_id, "goal": "准备草稿"},
    )
    assert blocked.status_code == 400

    client.put(
        f"/api/projects/{project['id']}/agent-policy",
        json={
            "enabled": True,
            "generation_engine": "deepseek",
            "max_actions_per_run": 3,
            "per_run_budget": 0.0,
            "monthly_budget": 5.0,
        },
    )
    missing_facts = client.post(
        f"/api/projects/{project['id']}/agent-runs",
        json={"cycle_id": cycle_id, "goal": "准备草稿"},
    )
    assert missing_facts.status_code == 400
    assert "已验证品牌事实" in missing_facts.json()["detail"]
    fact = client.post(
        f"/api/projects/{project['id']}/brand-facts",
        json={
            "fact_type": "policy",
            "claim": "所有 Agent 草稿都必须经过人工审批才能发布。",
            "source_url": "https://keeplix.com/governance",
        },
    ).json()
    over_budget = client.post(
        f"/api/projects/{project['id']}/agent-runs",
        json={"cycle_id": cycle_id, "goal": "准备草稿"},
    )
    assert over_budget.status_code == 400
    assert "单次预算" in over_budget.json()["detail"]

    policy = client.put(
        f"/api/projects/{project['id']}/agent-policy",
        json={
            "enabled": True,
            "generation_engine": "deepseek",
            "max_actions_per_run": 2,
            "per_run_budget": 0.25,
            "monthly_budget": 5.0,
            "approval_required": False,
        },
    ).json()
    assert policy["approval_required"] is True
    assert policy["allow_direct_publish"] is False
    planned = client.post(
        f"/api/projects/{project['id']}/agent-runs",
        json={"cycle_id": cycle_id, "goal": "准备草稿"},
    ).json()
    assert planned["status"] == "awaiting_approval"
    assert planned["actions"]
    assert planned["plan"]["brand_fact_ids"] == [fact["id"]]
    before_approval = client.post(
        f"/api/projects/{project['id']}/agent-runs/{planned['id']}/execute"
    )
    assert before_approval.status_code == 400
    approved = client.patch(
        f"/api/projects/{project['id']}/agent-runs/{planned['id']}",
        json={"decision": "approve"},
    )
    assert approved.status_code == 200

    captured: dict[str, str] = {}

    class FakeGenerationProvider:
        acquisition = "api"

        async def query(self, prompt):
            captured["prompt"] = prompt
            return EngineResponse(answer_text="Agent 修订草稿，等待人工审批。")

    monkeypatch.setattr(
        "keeplix.services.agent_service.get_provider",
        lambda engine_id: FakeGenerationProvider(),
    )
    executed = client.post(f"/api/projects/{project['id']}/agent-runs/{planned['id']}/execute")
    assert executed.status_code == 200
    assert executed.json()["status"] == "done"
    output_id = executed.json()["actions"][0]["output_artifact_id"]
    detail = client.get(
        f"/api/projects/{project['id']}/work-items/{executed.json()['actions'][0]['work_item_id']}"
    ).json()
    output = next(artifact for artifact in detail["artifacts"] if artifact["id"] == output_id)
    assert output["created_by"] == "agent"
    assert output["status"] == "draft"
    assert output["source_snapshot"]["brand_fact_ids"] == [fact["id"]]
    assert fact["claim"] in captured["prompt"]
    assert fact["source_url"] in captured["prompt"]
    direct_publish = client.post(
        f"/api/projects/{project['id']}/artifacts/{output_id}/deliveries",
        json={
            "method": "manual",
            "status": "published",
            "target_url": "https://keeplix.com",
            "notes": "尝试绕过审批",
        },
    )
    assert direct_publish.status_code == 400

    next_run = client.post(
        f"/api/projects/{project['id']}/agent-runs",
        json={"cycle_id": cycle_id, "goal": "准备下一份草稿"},
    ).json()
    taken_over = client.patch(
        f"/api/projects/{project['id']}/agent-runs/{next_run['id']}",
        json={"decision": "takeover"},
    )
    assert taken_over.status_code == 200
    assert taken_over.json()["status"] == "taken_over"
    assert all(action["status"] == "rejected" for action in taken_over.json()["actions"])
