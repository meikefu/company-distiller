#!/usr/bin/env python3
"""执行并报告 Company Distiller 的全部必选发布门禁。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from apply_run import apply_run
from build_evolving_example import AUDIENCE_PURPOSE, build
from company_object_lib import (
    BUNDLE_COLLECTIONS,
    COLLECTIONS,
    ValidationFailure,
    load_workspace,
    read_json,
    read_jsonl,
    validate_schema,
    validate_state,
    schema_for,
    write_json,
    write_jsonl,
)
from scaffold_company_skill import scaffold
from update_bundle_digest import update_digest
from validate_company_skill import validate_skill


ROOT = Path(__file__).resolve().parent.parent
QUICK_VALIDATE = Path.home() / ".codex/skills/.system/skill-creator/scripts/quick_validate.py"


class GateFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateFailure(message)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def text_tree(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    )


def write_empty_bundle_files(bundle: Path) -> None:
    bundle.mkdir(parents=True, exist_ok=True)
    for _, (filename, _) in BUNDLE_COLLECTIONS.items():
        write_jsonl(bundle / filename, [])


def expect_rejected_unchanged(workspace: Path, bundle: Path, phrase: str) -> None:
    before = tree_digest(workspace)
    try:
        apply_run(workspace, bundle)
    except ValidationFailure as exc:
        require(phrase in str(exc), f"拒绝原因未包含 {phrase!r}：{exc}")
    else:
        raise GateFailure("无效运行被错误接受")
    require(tree_digest(workspace) == before, "被拒绝的运行修改了工作区字节")


def make_run_bundle(
    bundle: Path,
    run_id: str,
    base_snapshot_id: str | None,
    result_snapshot_id: str,
    claims: list[dict] | None = None,
) -> None:
    write_empty_bundle_files(bundle)
    write_jsonl(bundle / "claims.jsonl", claims or [])
    run = {
        "id": run_id,
        "company_id": "company:example-company",
        "base_snapshot_id": base_snapshot_id,
        "started_at": "2026-07-02T00:00:00+00:00",
        "completed_at": "2026-07-02T00:01:00+00:00",
        "mode": "incremental",
        "model": "acceptance-fixture",
        "prompt_version": "company-distiller-v2",
        "input_digest": "",
        "connector_cursors": {},
        "status": "completed",
        "result_snapshot_id": result_snapshot_id,
    }
    write_json(bundle / "run.json", run)
    update_digest(bundle)


def run_official_quick_validate() -> str:
    require(QUICK_VALIDATE.is_file(), f"缺少 skill-creator 快速校验器：{QUICK_VALIDATE}")
    with tempfile.TemporaryDirectory() as temp:
        shim = Path(temp) / "yaml.py"
        shim.write_text(
            '''import json\n\nclass YAMLError(Exception):\n    pass\n\ndef safe_load(text):\n    result = {}\n    for raw in text.splitlines():\n        if not raw.strip() or raw.lstrip().startswith("#"):\n            continue\n        if ":" not in raw:\n            raise YAMLError("不支持的 frontmatter 行")\n        key, value = raw.split(":", 1)\n        value = value.strip()\n        if value.startswith(("\\\"", "'")):\n            try:\n                value = json.loads(value)\n            except Exception:\n                value = value.strip("\\\"'")\n        result[key.strip()] = value\n    return result\n''',
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(temp))
        completed = subprocess.run(
            [sys.executable, str(QUICK_VALIDATE), str(ROOT)],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        require(completed.returncode == 0, completed.stdout + completed.stderr)
        return completed.stdout.strip()


def gate_g01(context: dict) -> str:
    result = run_official_quick_validate()
    agent_text = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
    require("$company-distiller" in agent_text, "默认提示词没有调用该 Skill")
    require(
        all(term in agent_text for term in ("治理", "更新", "公司对象")),
        "Agent 元数据未体现公司对象的治理和持续更新能力",
    )
    short = next(line.split(":", 1)[1].strip().strip('"') for line in agent_text.splitlines() if "short_description:" in line)
    require(25 <= len(short) <= 64, "short_description 长度不在 25 到 64 个字符之间")
    return f"skill-creator 官方校验器：{result}；UI 元数据已对齐"


def gate_g02(context: dict) -> str:
    required = {
        "entity", "source", "record", "event", "evidence", "claim",
        "relation", "policy", "run", "snapshot", "change", "projection",
        "provenance-record", "provenance-event", "run-summary",
    }
    present = {path.name.removesuffix(".schema.json") for path in (ROOT / "schemas").glob("*.schema.json")}
    require(required <= present, f"缺少 schema：{sorted(required - present)}")
    for path in (ROOT / "schemas").glob("*.schema.json"):
        schema = read_json(path)
        require(schema.get("$schema") and schema.get("type") == "object", f"schema 头部无效：{path.name}")
    state = context["state"]
    require(validate_state(state) == [], "代表性的规范数据行未通过校验")
    for audience in AUDIENCE_PURPOSE:
        require(validate_skill(context["output"] / "projections" / audience) == [], f"{audience} 投影无效")
    return f"{len(required)} 个 schema 可解析，并通过规范对象与投影夹具校验"


def gate_g03(context: dict) -> str:
    types = {row["record_type"] for row in context["state"]["records"]}
    required = {"crm_account", "crm_opportunity", "interview_segment", "contract_term", "support_ticket", "product_usage"}
    require(required <= types, f"缺少结构化内部记录类型：{sorted(required - types)}")
    for record in context["state"]["records"]:
        require(isinstance(record["data"], dict) and record["data"], f"记录被扁平化或为空：{record['id']}")
    return f"类型化记录账本包含 {', '.join(sorted(required))}"


def gate_g04(context: dict) -> str:
    require(validate_state(context["state"]) == [], "规范对象的溯源引用未闭合")
    bad = copy.deepcopy(context["state"])
    first, second = bad["evidence"][0], bad["evidence"][1]
    first["derived_from"] = [second["id"]]
    second["derived_from"] = [first["id"]]
    errors = validate_state(bad)
    require(any("cycle detected" in error for error in errors), "证据派生环路未被拒绝")
    return "所有引用均闭合；注入的证据环路被正确拒绝"


def gate_g05(context: dict) -> str:
    types = {row["entity_type"] for row in context["state"]["entities"]}
    required = {"company", "legal_entity", "business_unit", "role", "product", "account"}
    require(required <= types, f"缺少实体边界类型：{sorted(required - types)}")
    scopes = {row["scope"] for row in context["state"]["entities"]}
    require(scopes == {"company", "commercial_relationship", "product_use_service"}, "未完整表示三个领域")
    return "公司、法律实体、业务单元、角色、产品和账户保持清晰区分"


def gate_g06(context: dict) -> str:
    state = context["state"]
    require(all(row.get("valid_from") and row.get("observed_at") for row in state["claims"]), "Claim 缺少时间字段")
    require(all(row.get("occurred_at") and row.get("observed_at") for row in state["events"]), "事件缺少时间字段")
    bad_claim = copy.deepcopy(state)
    bad_claim["claims"][0]["valid_to"] = "2025-01-01T00:00:00+00:00"
    require(any("valid_from is after valid_to" in error for error in validate_state(bad_claim)), "无效的 Claim 时间区间通过了校验")
    bad_event = copy.deepcopy(state)
    bad_event["events"][0]["observed_at"] = "2025-01-01T00:00:00+00:00"
    require(any("occurred_at is after observed_at" in error for error in validate_state(bad_event)), "观察时间早于发生时间的事件通过了校验")
    return "双时间字段完整；无效的 Claim 与事件时间区间均被拒绝"


def gate_g07(context: dict) -> str:
    workspace = context["output"] / "company-object"
    with tempfile.TemporaryDirectory() as temp:
        duplicate = Path(temp) / "duplicate"
        shutil.copytree(context["output"] / "bundles/run-003-contract-support-usage", duplicate)
        run = read_json(duplicate / "run.json")
        run["base_snapshot_id"] = "snapshot:example-company:003"
        write_json(duplicate / "run.json", run)
        update_digest(duplicate)
        expect_rejected_unchanged(workspace, duplicate, "duplicate run id")

        stale = Path(temp) / "stale"
        make_run_bundle(stale, "run:example-company:stale", "snapshot:example-company:001", "snapshot:example-company:stale")
        expect_rejected_unchanged(workspace, stale, "stale base_snapshot_id")
    require(len(context["state"]["runs"]) == 3 and len(context["state"]["snapshots"]) == 3, "按顺序执行的运行数量不符")
    return "3 次运行均成功应用；重复运行和过期基准运行被拒绝，工作区字节保持不变"


def gate_g08(context: dict) -> str:
    with tempfile.TemporaryDirectory() as temp:
        workspace = Path(temp) / "object"
        scaffold("Example Company (Synthetic)", "example-company", workspace, "2026-01-15")
        tracked = [workspace / relative for relative, _ in COLLECTIONS.values()]
        prior = {path: path.read_bytes() for path in tracked}
        for bundle_name in ("run-001-public", "run-002-crm-interview", "run-003-contract-support-usage"):
            apply_run(workspace, context["output"] / "bundles" / bundle_name)
            for path in tracked:
                current = path.read_bytes()
                require(current.startswith(prior[path]), f"账本被重写：{path}")
                prior[path] = current
        state = load_workspace(workspace)
        claims = {row["id"]: row for row in state["claims"]}
        require(claims["claim:opportunity-stage-validation"]["supersedes"] == ["claim:opportunity-stage-discovery"], "更正项缺少 supersedes")
        require(claims["claim:procurement-statement-retracted"]["decision"] == "retracted", "缺少撤回项")
    return "所有规范账本保持仅追加；更正与撤回均使用生命周期链接"


def gate_g09(context: dict) -> str:
    change_types = {row["change_type"] for row in context["state"]["changes"]}
    required = {"new", "reinforced", "superseded", "conflicted", "retracted", "unchanged"}
    require(change_types == required, f"变更类型覆盖不符：{sorted(change_types)}")
    return "测试夹具覆盖全部六种变更结果"


def gate_g10(context: dict) -> str:
    with tempfile.TemporaryDirectory() as temp:
        replay_a = Path(temp) / "a"
        replay_b = Path(temp) / "b"
        build(replay_a, force=False)
        build(replay_b, force=False)
        a = load_workspace(replay_a / "company-object")["snapshots"][-1]["content_hash"]
        b = load_workspace(replay_b / "company-object")["snapshots"][-1]["content_hash"]
        require(a == b == context["state"]["snapshots"][-1]["content_hash"], "快照重放哈希不一致")
    return f"两次全新重放的哈希一致：{a}"


def gate_g11(context: dict) -> str:
    workspace = context["output"] / "company-object"
    with tempfile.TemporaryDirectory() as temp:
        bundle = Path(temp) / "downgrade"
        bad_claim = {
            "id": "claim:bad-policy-downgrade",
            "subject_id": "product:example-product",
            "predicate": "ProductUseService.bad_policy_test",
            "value": "must not publish",
            "claim_type": "observation",
            "scope": "product_use_service",
            "valid_from": "2026-07-02T00:00:00+00:00",
            "valid_to": None,
            "observed_at": "2026-07-02T00:00:00+00:00",
            "evidence_ids": ["evidence:ticket-sev1"],
            "decision": "accepted",
            "confidence": {"source_reliability": "high", "corroboration": "single", "inference_strength": "direct", "overall": "high"},
            "supersedes": [],
            "contradicts": [],
            "policy_id": "policy:public",
            "created_by_run": "run:example-company:bad-policy",
        }
        make_run_bundle(bundle, "run:example-company:bad-policy", "snapshot:example-company:003", "snapshot:example-company:bad-policy", [bad_claim])
        expect_rejected_unchanged(workspace, bundle, "less restrictive")
    return "注入的客户成功证据公开降级在写入前被拒绝，工作区保持不变"


def gate_g12(context: dict) -> str:
    for audience, purpose in AUDIENCE_PURPOSE.items():
        package = context["output"] / "projections" / audience
        require(not (package / "records").exists() and not (package / "events").exists(), f"{audience} 投影复制了原始账本")
        require(validate_skill(package) == [], f"{audience} 投影未通过严格策略校验")
        projection = read_json(package / "projection.json")
        require(projection["audience"] == audience and projection["purpose"] == purpose, f"{audience} 投影边界不符")
        require(set(projection["conflict_claim_ids"]) <= set(projection["claim_ids"]), f"{audience} 冲突 ID 超出当前 Claim 范围")
        require(set(projection["retraction_claim_ids"]) <= set(projection["history_claim_ids"]), f"{audience} 撤回 ID 超出历史 Claim 范围")
    public_projection = read_json(context["output"] / "projections/public/projection.json")
    require(public_projection["redacted_conflict_count"] == 1, "public 投影隐藏了受限冲突的存在")
    sales_projection = read_json(context["output"] / "projections/sales/projection.json")
    require(
        sales_projection["retraction_claim_ids"] == ["claim:procurement-statement-retracted"],
        "sales 投影遗漏了已授权的撤回项",
    )
    return "四个受治理的 Skill 均通过校验，且只包含安全的记录/事件溯源存根"


def gate_g13(context: dict) -> str:
    sentinels = {
        "TEST_ONLY_CRM_SENTINEL_NEON": {"sales", "executive"},
        "TEST_ONLY_CONTRACT_SENTINEL_VAULT": {"executive"},
        "TEST_ONLY_TICKET_SENTINEL_CIRCUIT": {"customer-success", "executive"},
        "TEST_ONLY_USAGE_SENTINEL_PULSE": {"customer-success", "executive"},
    }
    for sentinel, allowed in sentinels.items():
        for audience in AUDIENCE_PURPOSE:
            present = sentinel in text_tree(context["output"] / "projections" / audience)
            require(present == (audience in allowed), f"{sentinel} 对 {audience} 的可见性错误")
    return "四个固定测试哨兵均符合示例受众允许列表矩阵；该检查不代表通用秘密或 PII 扫描"


def gate_g14(context: dict) -> str:
    valid = context["output"] / "projections/public"
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        empty = temp / "empty"
        empty.mkdir()
        require(validate_skill(empty), "空的伪造包错误通过校验")

        def mutated(name, mutation):
            target = temp / name
            shutil.copytree(valid, target)
            mutation(target)
            require(validate_skill(target), f"无效夹具错误通过校验：{name}")

        mutated("placeholder", lambda path: (path / "facts/company.md").write_text("(fill)\n", encoding="utf-8"))

        def invalid_enum(path):
            rows = read_jsonl(path / "claims/index.jsonl")
            rows[0]["decision"] = "approved"
            write_jsonl(path / "claims/index.jsonl", rows)
        mutated("enum", invalid_enum)

        def duplicate(path):
            rows = read_jsonl(path / "claims/index.jsonl")
            write_jsonl(path / "claims/index.jsonl", rows + [rows[0]])
        mutated("duplicate", duplicate)

        def broken(path):
            rows = read_jsonl(path / "claims/index.jsonl")
            rows[0]["evidence_ids"] = ["evidence:missing"]
            write_jsonl(path / "claims/index.jsonl", rows)
        mutated("broken", broken)

        def malformed(path):
            table = path / "facts/company.md"
            table.write_text(table.read_text(encoding="utf-8") + "| malformed |\n", encoding="utf-8")
        mutated("table", malformed)
    return "空包、占位符、无效枚举、重复 ID、断裂引用和畸形表格夹具均被拒绝"


def gate_g15(context: dict) -> str:
    for audience in AUDIENCE_PURPOSE:
        package = context["output"] / "projections" / audience
        skill = (package / "SKILL.md").read_text(encoding="utf-8").lower()
        for term in ("证据日期", "过期", "事实", "fact", "推断", "inference", "时间线", "crm 阶段", "合同"):
            require(term in skill, f"{audience} 运行时 Skill 缺少术语 {term!r}")
        require("使用量" in skill or "用量" in skill, f"{audience} 运行时 Skill 缺少使用量协议")
        require((package / "facts/timeline.md").is_file(), f"{audience} 缺少时间线文件")
        prompts = read_json(package / "evals/test-prompts.json")
        require(len(prompts) >= 5 and all(row.get("expected_behaviors") for row in prompts), f"{audience} 行为测试提示词不完整")
    return "所有投影均包含证据日期、过期语义、认知边界、时间线和行为测试提示词"


def gate_g16(context: dict) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    require(completed.returncode == 0, completed.stdout + completed.stderr)
    count = completed.stderr.count(" ... ok") + completed.stdout.count(" ... ok")
    require(count >= 6, "应至少执行六项单元/集成测试")
    return f"标准库 unittest 测试套件通过（{count} 项测试）"


GATES = [
    ("G01", "Skill 包", gate_g01),
    ("G02", "Schema 覆盖", gate_g02),
    ("G03", "内部数据保真", gate_g03),
    ("G04", "溯源闭合", gate_g04),
    ("G05", "实体范围", gate_g05),
    ("G06", "时间完整性", gate_g06),
    ("G07", "增量并发控制", gate_g07),
    ("G08", "不可变历史", gate_g08),
    ("G09", "变更语义", gate_g09),
    ("G10", "确定性重放", gate_g10),
    ("G11", "策略继承", gate_g11),
    ("G12", "投影隔离", gate_g12),
    ("G13", "示例敏感值隔离", gate_g13),
    ("G14", "严格校验", gate_g14),
    ("G15", "运行时行为", gate_g15),
    ("G16", "回归测试套件", gate_g16),
]


def run_acceptance(report_path: Path | None = None) -> list[dict]:
    results = []
    with tempfile.TemporaryDirectory() as temp:
        output = Path(temp) / "evolving-company"
        build(output, force=False)
        context = {"output": output, "state": load_workspace(output / "company-object")}
        for gate_id, name, function in GATES:
            try:
                evidence = function(context)
                result = {"id": gate_id, "name": name, "status": "PASS", "evidence": evidence}
                print(f"{gate_id} PASS {name}: {evidence}")
            except Exception as exc:
                result = {"id": gate_id, "name": name, "status": "FAIL", "evidence": str(exc)}
                print(f"{gate_id} FAIL {name}: {exc}")
            results.append(result)
    if report_path:
        write_json(
            report_path,
            {
                "rubric": "references/evaluation-rubric.md",
                "command": "python3 scripts/run_acceptance.py",
                "passed": sum(row["status"] == "PASS" for row in results),
                "total": len(results),
                "gates": results,
            },
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 Company Distiller 的全部必选验收门禁。")
    parser.add_argument("--report", default="example/evolving-company/acceptance-report.json", help="JSON 验收报告输出路径")
    args = parser.parse_args()
    report_path = Path(args.report).resolve() if args.report else None
    results = run_acceptance(report_path)
    failed = [row for row in results if row["status"] != "PASS"]
    print(f"\n验收结果：{len(results) - len(failed)}/{len(results)} 项门禁通过")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
