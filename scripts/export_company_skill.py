#!/usr/bin/env python3
"""从公司对象快照导出受众权限受控的 Skill。"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from company_object_lib import (
    ValidationFailure,
    canonical_json,
    load_workspace,
    policy_allows,
    sha256_value,
    validate_schema,
    validate_state,
    schema_for,
    write_json,
    write_jsonl,
)


AUDIENCE_PURPOSE = {
    "public": "research",
    "sales": "account-planning",
    "customer-success": "customer-success",
    "executive": "executive-review",
}

FACT_FILES = {
    "company": "facts/company.md",
    "commercial_relationship": "facts/commercial-relationship.md",
    "product_use_service": "facts/product-use-service.md",
}

FACT_TITLES = {
    "company": "公司本体",
    "commercial_relationship": "商业关系",
    "product_use_service": "产品使用与服务",
}


def markdown_value(value) -> str:
    if isinstance(value, (dict, list)):
        return f"`{canonical_json(value)}`"
    if value is None:
        return "未知"
    return str(value).replace("|", "\\|").replace("\n", " ")


def export_skill(
    workspace: Path,
    output: Path,
    audience: str,
    purpose: str | None = None,
    snapshot_id: str | None = None,
    force: bool = False,
) -> dict:
    state = load_workspace(workspace)
    errors = validate_state(state, require_nonempty=True)
    if errors:
        raise ValidationFailure("规范工作区无效：\n" + "\n".join(errors))
    purpose = purpose or AUDIENCE_PURPOSE[audience]
    snapshot_id = snapshot_id or state["manifest"]["current_snapshot_id"]
    snapshots = {row["id"]: row for row in state["snapshots"]}
    if snapshot_id not in snapshots:
        raise ValidationFailure(f"未知快照 {snapshot_id!r}")
    snapshot = snapshots[snapshot_id]
    policies = {row["id"]: row for row in state["policies"]["policies"]}
    claims = {row["id"]: row for row in state["claims"]}
    evidence = {row["id"]: row for row in state["evidence"]}
    sources = {row["id"]: row for row in state["sources"]}
    records = {row["id"]: row for row in state["records"]}
    events = {row["id"]: row for row in state["events"]}
    runs = {row["id"]: row for row in state["runs"]}
    relations = {row["id"]: row for row in state["relations"]}
    entities = {row["id"]: row for row in state["entities"]}

    def allowed(row: dict) -> bool:
        return policy_allows(policies[row["policy_id"]], audience, purpose)

    selected_claims = []
    for claim_id in snapshot["active_claim_ids"] + snapshot["conflict_claim_ids"]:
        claim = claims[claim_id]
        subject = entities[claim["subject_id"]]
        if claim["decision"] == "accepted" and allowed(claim) and allowed(subject):
            selected_claims.append(claim)
    selected_claim_ids = {row["id"] for row in selected_claims}
    selected_retraction_ids = {
        item_id
        for item_id in snapshot["retraction_claim_ids"]
        if allowed(claims[item_id]) and allowed(entities[claims[item_id]["subject_id"]])
    }
    canonical_conflict_ids = set(snapshot["conflict_claim_ids"])
    selected_conflict_ids = selected_claim_ids & canonical_conflict_ids
    conflict_adjacency = {item_id: set() for item_id in canonical_conflict_ids}
    for item_id in canonical_conflict_ids:
        for other_id in claims[item_id].get("contradicts", []):
            if other_id in canonical_conflict_ids:
                conflict_adjacency[item_id].add(other_id)
                conflict_adjacency[other_id].add(item_id)
    hidden_conflict_ids = {
        other_id
        for item_id in selected_conflict_ids
        for other_id in conflict_adjacency[item_id]
        if other_id not in selected_claim_ids
    }
    history_claim_ids = set(selected_retraction_ids)
    pending_claim_ids = [
        item_id
        for row in selected_claims + [claims[item_id] for item_id in selected_retraction_ids]
        for item_id in row.get("supersedes", []) + row.get("contradicts", [])
    ]
    while pending_claim_ids:
        item_id = pending_claim_ids.pop()
        if item_id in selected_claim_ids or item_id in history_claim_ids:
            continue
        historical = claims[item_id]
        subject = entities[historical["subject_id"]]
        if not (allowed(historical) and allowed(subject)):
            continue
        history_claim_ids.add(item_id)
        pending_claim_ids.extend(historical.get("supersedes", []) + historical.get("contradicts", []))
    selected_history_claims = [claims[item_id] for item_id in sorted(history_claim_ids)]
    selected_relations = [
        relations[item_id]
        for item_id in snapshot["active_relation_ids"]
        if allowed(relations[item_id])
        and allowed(entities[relations[item_id]["subject_id"]])
        and allowed(entities[relations[item_id]["object_id"]])
    ]

    evidence_ids = {
        item_id
        for claim in selected_claims + selected_history_claims
        for item_id in claim["evidence_ids"]
    }
    evidence_ids.update(item_id for relation in selected_relations for item_id in relation["evidence_ids"])
    pending = list(evidence_ids)
    while pending:
        item_id = pending.pop()
        for parent_id in evidence[item_id].get("derived_from", []):
            if parent_id not in evidence_ids:
                evidence_ids.add(parent_id)
                pending.append(parent_id)
    selected_evidence = [evidence[item_id] for item_id in sorted(evidence_ids)]
    for item in selected_evidence:
        if not allowed(item):
            raise ValidationFailure(f"导出证据 {item['id']} 时策略继承失败")
    record_ids = {item_id for item in selected_evidence for item_id in item["record_ids"]}
    event_ids = {item_id for item in selected_evidence for item_id in item["event_ids"]}
    selected_records = [records[item_id] for item_id in sorted(record_ids)]
    selected_events = [events[item_id] for item_id in sorted(event_ids)]
    for item in selected_records + selected_events:
        if not allowed(item):
            raise ValidationFailure(f"导出来源链 {item['id']} 时策略继承失败")
    source_ids = {item_id for item in selected_evidence for item_id in item["source_ids"]}
    selected_sources = [sources[item_id] for item_id in sorted(source_ids)]
    entity_ids = {snapshot["company_id"]}
    entity_ids.update(claim["subject_id"] for claim in selected_claims + selected_history_claims)
    entity_ids.update(relation["subject_id"] for relation in selected_relations)
    entity_ids.update(relation["object_id"] for relation in selected_relations)
    selected_entities = [entities[item_id] for item_id in sorted(entity_ids) if item_id in entities and allowed(entities[item_id])]

    projected_evidence = [dict(item) for item in selected_evidence]
    projected_records = [
        {
            "id": item["id"],
            "record_type": item["record_type"],
            "source_id": item["source_id"],
            "observed_at": item["observed_at"],
            "valid_from": item.get("valid_from"),
            "valid_to": item.get("valid_to"),
            "policy_id": item["policy_id"],
            "created_by_run": item["created_by_run"],
        }
        for item in selected_records
    ]
    projected_events = [
        {
            "id": item["id"],
            "event_type": item["event_type"],
            "occurred_at": item["occurred_at"],
            "observed_at": item["observed_at"],
            "source_ids": item["source_ids"],
            "record_ids": item["record_ids"],
            "policy_id": item["policy_id"],
            "created_by_run": item["created_by_run"],
        }
        for item in selected_events
    ]
    run_ids = {
        item["created_by_run"]
        for item in selected_entities
        + selected_sources
        + selected_records
        + selected_events
        + selected_evidence
        + selected_claims
        + selected_history_claims
        + selected_relations
    }
    projected_runs = [
        {
            "id": runs[item_id]["id"],
            "completed_at": runs[item_id]["completed_at"],
            "mode": runs[item_id]["mode"],
            "model": runs[item_id]["model"],
            "prompt_version": runs[item_id]["prompt_version"],
            "input_digest": runs[item_id]["input_digest"],
            "result_snapshot_id": runs[item_id]["result_snapshot_id"],
        }
        for item_id in sorted(run_ids)
    ]
    projected_sources = []
    for item in selected_sources:
        projected = dict(item)
        if not policies[item["policy_id"]]["export_locator"]:
            projected["locator"] = "按策略隐藏"
        projected_sources.append(projected)

    projection_core = {
        "company_id": snapshot["company_id"],
        "snapshot_id": snapshot_id,
        "audience": audience,
        "purpose": purpose,
        "claim_ids": sorted(row["id"] for row in selected_claims),
        "history_claim_ids": sorted(row["id"] for row in selected_history_claims),
        "conflict_claim_ids": sorted(selected_conflict_ids),
        "retraction_claim_ids": sorted(selected_retraction_ids),
        "redacted_conflict_count": len(hidden_conflict_ids),
        "evidence_ids": sorted(evidence_ids),
        "record_ids": sorted(record_ids),
        "event_ids": sorted(event_ids),
        "run_ids": sorted(run_ids),
        "relation_ids": sorted(row["id"] for row in selected_relations),
    }
    projection = {
        "id": f"projection:{state['manifest']['slug']}:{snapshot_id.split(':')[-1]}:{audience}",
        **projection_core,
        "created_at": snapshot["created_at"],
        "content_hash": sha256_value(projection_core),
    }
    projection_errors = validate_schema(projection, schema_for("projection.schema.json"), "projection")
    if projection_errors:
        raise ValidationFailure("\n".join(projection_errors))

    if output.exists():
        if not force:
            raise ValidationFailure(f"输出目录已存在：{output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    write_json(output / "projection.json", projection)
    write_jsonl(output / "object/entities.jsonl", selected_entities)
    write_jsonl(output / "sources/index.jsonl", projected_sources)
    write_jsonl(output / "provenance/records.jsonl", projected_records)
    write_jsonl(output / "provenance/events.jsonl", projected_events)
    write_jsonl(output / "provenance/runs.jsonl", projected_runs)
    write_jsonl(output / "evidence/index.jsonl", projected_evidence)
    write_jsonl(output / "claims/index.jsonl", sorted(selected_claims, key=lambda row: row["id"]))
    write_jsonl(output / "claims/history.jsonl", selected_history_claims)
    write_jsonl(output / "relations/relations.jsonl", sorted(selected_relations, key=lambda row: row["id"]))
    used_policy_ids = sorted(
        {
            row["policy_id"]
            for row in selected_entities
            + selected_sources
            + selected_records
            + selected_events
            + selected_evidence
            + selected_claims
            + selected_history_claims
            + selected_relations
        }
    )
    write_json(
        output / "governance/policies.json",
        {
            "version": state["policies"]["version"],
            "classification_order": state["policies"]["classification_order"],
            "audiences": state["policies"]["audiences"],
            "policies": [policies[item_id] for item_id in used_policy_ids],
        },
    )
    (output / "evals").mkdir(parents=True, exist_ok=True)
    shutil.copy2(workspace / "evals/test-prompts.json", output / "evals/test-prompts.json")

    company_name = state["manifest"]["company_name"]
    skill_name = f"{state['manifest']['slug']}-{audience}-company-skill"
    latest_observed = max((row["observed_at"] for row in selected_evidence), default=snapshot["created_at"])
    skill_text = f'''---
name: {skill_name}
description: "面向 {audience} 受众、用途为 {purpose} 的 {company_name} 受治理公司对象 Skill。用于回答有证据支持的公司问题，开展商业关系、产品使用、风险和客户规划分析，并识别过期数据。"
---

# {company_name} 公司 Skill

这是快照 `{snapshot_id}` 面向 `{audience}` 受众、服务于 `{purpose}` 用途的只读投影。
规范层的原始记录和事件不包含在本交付包中。

## 证据日期

- 快照创建时间：`{snapshot['created_at']}`
- 最新纳入的观察时间：`{latest_observed}`
- 受众：`{audience}`
- 用途：`{purpose}`

如果“最新”或“当前”问题晚于已纳入的观察时间，应刷新规范公司对象，或明确说明该投影已经过期（`stale`）。

## 回答协议

1. 只加载 `facts/` 中与问题相关的文件，再把重要表述解析到 `claims/index.jsonl` 和 `evidence/index.jsonl`。
2. 按 `claim_type` 和 `decision` 将输出标记为事实（`fact`）、观察（`observation`）、有证据支持的推断（`inference`）、假设或未解决冲突。
3. 对财务、合同、产品用量（usage）、客服、法律、市场和当前状态主张给出有效日期与观察日期。
4. 将 CRM 阶段视为卖方观察，将访谈内容视为有归属的陈述，将合同视为义务，将工单视为边界明确的事件，将用量指标视为限定时间窗内的观察。
5. 不得从单一记录类型推断采购意向、产品采纳、满意度或公司级弱点。
6. 对 `facts/conflicts.md` 中的主张展示冲突双方。
7. 不得尝试访问本投影排除的数据。

## 交付包目录

- `projection.json`：快照、受众、用途和纳入的 ID。
- `object/entities.jsonl`：获授权的实体身份。
- `facts/company.md`：公司本体领域 Claim。
- `facts/commercial-relationship.md`：获授权的 CRM、访谈和合同 Claim。
- `facts/product-use-service.md`：获授权的产品用量与客服 Claim。
- `facts/timeline.md`：业务有效时间与观察时间线。
- `facts/conflicts.md`：未解决的备选说法。
- `facts/retractions.md`：获授权的历史 Claim 撤回记录。
- `claims/index.jsonl`：投影中的当前规范 Claim。
- `claims/history.jsonl`：获授权的生命周期前序 Claim，不属于当前事实。
- `evidence/index.jsonl`：包含安全来源链的投影证据。
- `provenance/records.jsonl`：不含原始 `data` 或主体的记录元数据。
- `provenance/events.jsonl`：不含原始 `data` 或主体的事件元数据。
- `provenance/runs.jsonl`：模型、提示词、摘要与快照审计概要。
- `sources/index.jsonl`：带治理定位符的数据源版本。
- `relations/relations.jsonl`：投影中的有类型关系。
'''
    (output / "SKILL.md").write_text(skill_text, encoding="utf-8")

    company_entity = entities[snapshot["company_id"]]
    profile = f'''# {company_name} 投影概况

| 字段 | 值 |
|---|---|
| 对象 ID | `{snapshot['company_id']}` |
| 实体类型 | `{company_entity['entity_type']}` |
| 快照 | `{snapshot_id}` |
| 受众 | `{audience}` |
| 用途 | `{purpose}` |
| 当前投影 Claim 数 | {len(selected_claims)} |
| 投影证据单元数 | {len(selected_evidence)} |

本页描述的是投影边界，不代表规范公司对象中保存的全部知识。
'''
    (output / "object/profile.md").write_text(profile, encoding="utf-8")

    for scope, relative_path in FACT_FILES.items():
        rows = [row for row in selected_claims if row["scope"] == scope]
        title = FACT_TITLES[scope]
        lines = [f"# {title}\n", "| Claim | 状态 | 类型 | 值 | 有效起始时间 | 观察时间 | 证据 |", "|---|---|---|---|---|---|---|"]
        for row in rows:
            status = "冲突（conflicted）" if row["id"] in selected_conflict_ids else "当前（current）"
            lines.append(
                f"| `{row['id']}` | {status} | {row['claim_type']} | {markdown_value(row['value'])} | {row['valid_from']} | {row['observed_at']} | {' '.join(f'`{item}`' for item in row['evidence_ids'])} |"
            )
        if not rows:
            lines.append("| 本投影没有获授权的 Claim | 当前（current） | 未知 | 无 | 不适用 | 不适用 | 无 |")
        (output / relative_path).parent.mkdir(parents=True, exist_ok=True)
        (output / relative_path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    timeline_lines = ["# 时间线\n", "| 有效起始时间 | 观察时间 | 主体 | 谓词 | Claim |", "|---|---|---|---|---|"]
    for row in sorted(selected_claims, key=lambda item: (item["valid_from"], item["observed_at"], item["id"])):
        timeline_lines.append(
            f"| {row['valid_from']} | {row['observed_at']} | `{row['subject_id']}` | `{row['predicate']}` | `{row['id']}` |"
        )
    (output / "facts/timeline.md").write_text("\n".join(timeline_lines) + "\n", encoding="utf-8")

    conflict_lines = ["# 未解决冲突\n"]
    conflicts = [row for row in selected_claims if row["id"] in selected_conflict_ids]
    if conflicts:
        for row in conflicts:
            visible_alternatives = sorted(conflict_adjacency[row["id"]] & selected_claim_ids)
            conflict_lines.extend(
                [
                    f"## {row['id']}",
                    "",
                    f"- 值：{markdown_value(row['value'])}",
                    f"- 可见的备选 Claim：{', '.join(visible_alternatives) or '无获授权项'}",
                    f"- 证据：{', '.join(row['evidence_ids'])}",
                    "",
                ]
            )
    else:
        conflict_lines.append("本投影中没有获授权的未解决冲突。\n")
    if hidden_conflict_ids:
        conflict_lines.append(
            f"另有 {len(hidden_conflict_ids)} 个冲突备选项因策略限制而被隐藏。\n"
        )
    (output / "facts/conflicts.md").write_text("\n".join(conflict_lines), encoding="utf-8")

    retraction_lines = ["# 撤回记录\n"]
    selected_history_index = {row["id"]: row for row in selected_history_claims}
    if selected_retraction_ids:
        for item_id in sorted(selected_retraction_ids):
            row = selected_history_index[item_id]
            retraction_lines.extend(
                [
                    f"## {item_id}",
                    "",
                    f"- 撤回说明：{markdown_value(row['value'])}",
                    f"- 替代对象：{', '.join(row['supersedes'])}",
                    f"- 观察时间：{row['observed_at']}",
                    f"- 证据：{', '.join(row['evidence_ids'])}",
                    "",
                ]
            )
    else:
        retraction_lines.append("本投影中没有获授权的撤回记录。\n")
    (output / "facts/retractions.md").write_text("\n".join(retraction_lines), encoding="utf-8")
    return projection


def main() -> None:
    parser = argparse.ArgumentParser(description="导出受治理的公司 Skill。")
    parser.add_argument("workspace", help="规范公司对象工作区。")
    parser.add_argument("--output", required=True, help="投影 Skill 的输出目录。")
    parser.add_argument("--audience", required=True, choices=sorted(AUDIENCE_PURPOSE), help="目标受众。")
    parser.add_argument("--purpose", help="用途；省略时使用受众的默认用途。")
    parser.add_argument("--snapshot", help="要导出的快照 ID；省略时使用当前快照。")
    parser.add_argument("--force", action="store_true", help="输出目录已存在时覆盖。")
    args = parser.parse_args()
    try:
        projection = export_skill(
            Path(args.workspace).resolve(),
            Path(args.output).resolve(),
            args.audience,
            args.purpose,
            args.snapshot,
            args.force,
        )
    except (ValidationFailure, FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"导出失败：\n{exc}") from exc
    print(f"已导出 {projection['audience']} Skill：{Path(args.output).resolve()}")
    print(
        f"当前 Claim：{len(projection['claim_ids'])}；历史 Claim：{len(projection['history_claim_ids'])}；"
        f"证据：{len(projection['evidence_ids'])}"
    )


if __name__ == "__main__":
    main()
