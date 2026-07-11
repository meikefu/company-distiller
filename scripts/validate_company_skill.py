#!/usr/bin/env python3
"""严格校验生成的受治理公司 Skill。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from company_object_lib import (
    ValidationFailure,
    policy_allows,
    read_json,
    read_jsonl,
    schema_for,
    sha256_value,
    validate_rows,
    validate_schema,
)


REQUIRED_FILES = [
    "SKILL.md",
    "projection.json",
    "object/profile.md",
    "object/entities.jsonl",
    "facts/company.md",
    "facts/commercial-relationship.md",
    "facts/product-use-service.md",
    "facts/timeline.md",
    "facts/conflicts.md",
    "facts/retractions.md",
    "sources/index.jsonl",
    "provenance/records.jsonl",
    "provenance/events.jsonl",
    "provenance/runs.jsonl",
    "evidence/index.jsonl",
    "claims/index.jsonl",
    "claims/history.jsonl",
    "relations/relations.jsonl",
    "governance/policies.json",
    "evals/test-prompts.json",
]

PLACEHOLDERS = (
    "(fill)",
    "Template placeholder",
    "（待填写）",
    "模板占位符",
    "__COMPANY",
    "__SLUG__",
    "TEMPLATE-000",
)


def validate_frontmatter(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return ["SKILL.md 缺少 YAML frontmatter"]
    frontmatter = match.group(1)
    fields = {}
    for line in frontmatter.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip('"')
    errors = []
    if set(fields) != {"name", "description"}:
        errors.append("SKILL.md frontmatter 只能包含 name 和 description")
    name = fields.get("name", "")
    if not re.fullmatch(r"[a-z0-9-]{1,64}", name):
        errors.append("SKILL.md 的 name 必须使用小写连字符格式，且不超过 64 个字符")
    if not fields.get("description"):
        errors.append("SKILL.md 的 description 不能为空")
    return errors


def validate_markdown_tables(path: Path) -> list[str]:
    errors = []
    expected_columns = None
    in_table = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("|"):
            in_table = False
            expected_columns = None
            continue
        columns = len(re.findall(r"(?<!\\)\|", line)) - 1
        if columns < 1:
            continue
        if not in_table:
            expected_columns = columns
            in_table = True
        elif columns != expected_columns:
            errors.append(f"{path.name}:{number}：Markdown 表格有 {columns} 列，预期 {expected_columns} 列")
    return errors


def validate_prompts(path: Path) -> list[str]:
    errors = []
    try:
        prompts = read_json(path)
    except (json.JSONDecodeError, ValueError) as exc:
        return [f"测试提示词无效：{exc}"]
    if not isinstance(prompts, list) or len(prompts) < 5:
        return ["evals/test-prompts.json 至少要包含 5 条提示词"]
    ids = set()
    for index, prompt in enumerate(prompts, 1):
        if not isinstance(prompt, dict):
            errors.append(f"第 {index} 条测试提示词不是对象")
            continue
        if set(prompt) != {"id", "prompt", "expected_behaviors"}:
            errors.append(f"第 {index} 条测试提示词必须包含 id、prompt 和 expected_behaviors")
            continue
        if prompt["id"] in ids:
            errors.append(f"测试提示词 ID 重复：{prompt['id']!r}")
        ids.add(prompt["id"])
        if not prompt["prompt"] or not isinstance(prompt["expected_behaviors"], list) or not prompt["expected_behaviors"]:
            errors.append(f"第 {index} 条测试提示词缺少行为要求")
    return errors


def validate_skill(package: Path) -> list[str]:
    errors = []
    for relative_path in REQUIRED_FILES:
        if not (package / relative_path).is_file():
            errors.append(f"缺少必需文件：{relative_path}")
    if errors:
        return errors
    if (package / "records").exists() or (package / "events").exists():
        errors.append("派生 Skill 不得包含规范层的 records/ 或 events/ 目录")

    errors.extend(validate_frontmatter(package / "SKILL.md"))
    projection = read_json(package / "projection.json")
    errors.extend(validate_schema(projection, schema_for("projection.schema.json"), "projection"))
    policies_document = read_json(package / "governance/policies.json")
    errors.extend(validate_schema(policies_document, schema_for("policy.schema.json"), "policies"))
    entities = read_jsonl(package / "object/entities.jsonl")
    sources = read_jsonl(package / "sources/index.jsonl")
    records = read_jsonl(package / "provenance/records.jsonl")
    events = read_jsonl(package / "provenance/events.jsonl")
    runs = read_jsonl(package / "provenance/runs.jsonl")
    evidence = read_jsonl(package / "evidence/index.jsonl")
    claims = read_jsonl(package / "claims/index.jsonl")
    history_claims = read_jsonl(package / "claims/history.jsonl")
    relations = read_jsonl(package / "relations/relations.jsonl")
    errors.extend(validate_rows(entities, "entity.schema.json", "entities"))
    errors.extend(validate_rows(sources, "source.schema.json", "sources"))
    errors.extend(validate_rows(records, "provenance-record.schema.json", "records"))
    errors.extend(validate_rows(events, "provenance-event.schema.json", "events"))
    errors.extend(validate_rows(runs, "run-summary.schema.json", "runs"))
    errors.extend(validate_rows(evidence, "evidence.schema.json", "evidence"))
    errors.extend(validate_rows(claims, "claim.schema.json", "claims"))
    errors.extend(validate_rows(history_claims, "claim.schema.json", "history_claims"))
    errors.extend(validate_rows(relations, "relation.schema.json", "relations"))

    collections = {
        "entities": entities,
        "sources": sources,
        "records": records,
        "events": events,
        "runs": runs,
        "evidence": evidence,
        "claims": claims,
        "history_claims": history_claims,
        "relations": relations,
    }
    for name, rows in collections.items():
        ids = [row.get("id") for row in rows]
        if len(ids) != len(set(ids)):
            errors.append(f"{name}：存在重复 ID")
    entity_ids = {row["id"] for row in entities}
    source_ids = {row["id"] for row in sources}
    record_ids = {row["id"] for row in records}
    event_ids = {row["id"] for row in events}
    run_ids = {row["id"] for row in runs}
    evidence_index = {row["id"]: row for row in evidence}
    evidence_ids = set(evidence_index)
    claim_ids = {row["id"] for row in claims}
    history_claim_ids = {row["id"] for row in history_claims}
    if claim_ids & history_claim_ids:
        errors.append("当前 Claim 与历史 Claim 的 ID 集合必须互斥")
    all_claim_ids = claim_ids | history_claim_ids
    relation_ids = {row["id"] for row in relations}
    policy_index = {row["id"]: row for row in policies_document["policies"]}

    expected_projection_hash = sha256_value(
        {
            "company_id": projection["company_id"],
            "snapshot_id": projection["snapshot_id"],
            "audience": projection["audience"],
            "purpose": projection["purpose"],
            "claim_ids": projection["claim_ids"],
            "history_claim_ids": projection["history_claim_ids"],
            "conflict_claim_ids": projection["conflict_claim_ids"],
            "retraction_claim_ids": projection["retraction_claim_ids"],
            "redacted_conflict_count": projection["redacted_conflict_count"],
            "evidence_ids": projection["evidence_ids"],
            "record_ids": projection["record_ids"],
            "event_ids": projection["event_ids"],
            "run_ids": projection["run_ids"],
            "relation_ids": projection["relation_ids"],
        }
    )
    if projection.get("content_hash") != expected_projection_hash:
        errors.append("projection 的 content_hash 不匹配")
    if set(projection.get("claim_ids", [])) != claim_ids:
        errors.append("projection.claim_ids 与 claims/index.jsonl 不完全一致")
    if set(projection.get("history_claim_ids", [])) != history_claim_ids:
        errors.append("projection.history_claim_ids 与 claims/history.jsonl 不完全一致")
    if not set(projection.get("conflict_claim_ids", [])) <= claim_ids:
        errors.append("projection.conflict_claim_ids 必须是当前 Claim 的子集")
    if not set(projection.get("retraction_claim_ids", [])) <= history_claim_ids:
        errors.append("projection.retraction_claim_ids 必须是历史 Claim 的子集")
    if set(projection.get("evidence_ids", [])) != evidence_ids:
        errors.append("projection.evidence_ids 与 evidence/index.jsonl 不完全一致")
    if set(projection.get("record_ids", [])) != record_ids:
        errors.append("projection.record_ids 与 provenance/records.jsonl 不完全一致")
    if set(projection.get("event_ids", [])) != event_ids:
        errors.append("projection.event_ids 与 provenance/events.jsonl 不完全一致")
    if set(projection.get("run_ids", [])) != run_ids:
        errors.append("projection.run_ids 与 provenance/runs.jsonl 不完全一致")
    if set(projection.get("relation_ids", [])) != relation_ids:
        errors.append("projection.relation_ids 与 relations/relations.jsonl 不完全一致")
    if projection.get("company_id") not in entity_ids:
        errors.append("projection.company_id 对应的实体不存在")

    def check_policy(row: dict, label: str) -> None:
        policy = policy_index.get(row.get("policy_id"))
        if not policy:
            errors.append(f"{label}：找不到策略 {row.get('policy_id')!r}")
        elif not policy_allows(policy, projection["audience"], projection["purpose"]):
            errors.append(f"{label}：策略不允许该投影的受众和用途")

    for row in entities + sources + records + events + evidence + claims + history_claims + relations:
        check_policy(row, row.get("id", "未知"))
    for row in records:
        if "data" in row or "subject_ids" in row:
            errors.append(f"记录来源链 {row['id']}：泄露了原始 data 或 subject_ids")
        if row["source_id"] not in source_ids:
            errors.append(f"记录来源链 {row['id']}：缺少数据源")
    for row in events:
        if "data" in row or "subject_ids" in row:
            errors.append(f"事件来源链 {row['id']}：泄露了原始 data 或 subject_ids")
        for source_id in row["source_ids"]:
            if source_id not in source_ids:
                errors.append(f"事件来源链 {row['id']}：缺少数据源 {source_id!r}")
        for record_id in row["record_ids"]:
            if record_id not in record_ids:
                errors.append(f"事件来源链 {row['id']}：缺少记录 {record_id!r}")
    for row in evidence:
        for source_id in row.get("source_ids", []):
            if source_id not in source_ids:
                errors.append(f"证据 {row['id']}：缺少数据源 {source_id!r}")
        for record_id in row.get("record_ids", []):
            if record_id not in record_ids:
                errors.append(f"证据 {row['id']}：缺少记录来源链 {record_id!r}")
        for event_id in row.get("event_ids", []):
            if event_id not in event_ids:
                errors.append(f"证据 {row['id']}：缺少事件来源链 {event_id!r}")
        for parent_id in row.get("derived_from", []):
            if parent_id not in evidence_ids:
                errors.append(f"证据 {row['id']}：缺少父证据 {parent_id!r}")
    for row in claims + history_claims:
        if row["subject_id"] not in entity_ids:
            errors.append(f"Claim {row['id']}：缺少主题实体")
        if row in claims and row["decision"] != "accepted":
            errors.append(f"Claim {row['id']}：只有 accepted Claim 才能进入投影")
        for evidence_id in row["evidence_ids"]:
            if evidence_id not in evidence_ids:
                errors.append(f"Claim {row['id']}：缺少证据 {evidence_id!r}")
        for related_id in row.get("supersedes", []) + row.get("contradicts", []):
            if related_id not in all_claim_ids:
                errors.append(f"Claim {row['id']}：缺少生命周期 Claim {related_id!r}")
    history_index = {row["id"]: row for row in history_claims}
    for item_id in projection.get("retraction_claim_ids", []):
        if history_index[item_id]["decision"] != "retracted":
            errors.append(f"撤回 Claim {item_id}：decision 必须是 retracted")
    for row in relations:
        if row["subject_id"] not in entity_ids or row["object_id"] not in entity_ids:
            errors.append(f"关系 {row['id']}：缺少端点实体")
        for evidence_id in row["evidence_ids"]:
            if evidence_id not in evidence_ids:
                errors.append(f"关系 {row['id']}：缺少证据 {evidence_id!r}")
    for row in entities + sources + records + events + evidence + claims + history_claims + relations:
        if row.get("created_by_run") not in run_ids:
            errors.append(f"{row.get('id')}：缺少运行来源链 {row.get('created_by_run')!r}")

    errors.extend(validate_prompts(package / "evals/test-prompts.json"))
    skill_text = (package / "SKILL.md").read_text(encoding="utf-8")
    for phrase in ("证据日期", "过期", "fact", "inference", "时间线"):
        if phrase.lower() not in skill_text.lower():
            errors.append(f"SKILL.md 缺少运行时行为术语 {phrase!r}")
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".json", ".jsonl"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for placeholder in PLACEHOLDERS:
            if placeholder in text:
                errors.append(f"{path.relative_to(package)} 包含占位符 {placeholder!r}")
        if path.suffix == ".md":
            errors.extend(validate_markdown_tables(path))
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="校验生成的受治理公司 Skill。")
    parser.add_argument("package", help="待校验的公司 Skill 目录。")
    args = parser.parse_args()
    package = Path(args.package).resolve()
    try:
        errors = validate_skill(package)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, ValidationFailure) as exc:
        errors = [str(exc)]
    if errors:
        print("公司 Skill 校验失败：")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    projection = read_json(package / "projection.json")
    print("公司 Skill 校验通过。")
    print(f"受众：{projection['audience']}")
    print(f"当前 Claim：{len(projection['claim_ids'])}")
    print(f"历史 Claim：{len(projection['history_claim_ids'])}")
    print(f"证据单元：{len(projection['evidence_ids'])}")


if __name__ == "__main__":
    main()
