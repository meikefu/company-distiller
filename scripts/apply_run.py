#!/usr/bin/env python3
"""完成全部预校验后，追加应用不可变的蒸馏运行包。"""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

from company_object_lib import (
    BUNDLE_COLLECTIONS,
    COLLECTIONS,
    ValidationFailure,
    append_jsonl,
    bundle_digest,
    canonical_json,
    compute_snapshot_hash,
    load_bundle,
    load_workspace,
    semantic_signature,
    validate_rows,
    validate_schema,
    validate_state,
    schema_for,
    write_json,
)


def materialize_snapshot(state: dict, run: dict, new_claims: list[dict], new_relations: list[dict]):
    previous = state["snapshots"][-1] if state["snapshots"] else None
    active = set(previous["active_claim_ids"] if previous else [])
    conflicts = set(previous["conflict_claim_ids"] if previous else [])
    retractions = set(previous["retraction_claim_ids"] if previous else [])
    active_relations = set(previous["active_relation_ids"] if previous else [])
    all_claims = {row["id"]: row for row in state["claims"]}
    prior_active_by_signature = {}
    for claim_id in active:
        prior_active_by_signature.setdefault(semantic_signature(all_claims[claim_id]), []).append(claim_id)

    changes = []
    for claim in new_claims:
        claim_id = claim["id"]
        related = []
        if claim["decision"] in {"proposed", "rejected"}:
            change_type = "unchanged"
        elif claim["decision"] == "retracted":
            related = list(claim["supersedes"])
            active.difference_update(related)
            conflicts.difference_update(related)
            retractions.add(claim_id)
            change_type = "retracted"
        elif claim["contradicts"]:
            related = list(claim["contradicts"])
            active.difference_update(related)
            conflicts.update(related)
            conflicts.add(claim_id)
            change_type = "conflicted"
        elif claim["supersedes"]:
            related = list(claim["supersedes"])
            active.difference_update(related)
            conflicts.difference_update(related)
            active.add(claim_id)
            change_type = (
                "reinforced"
                if related and all(
                    prior_id in all_claims
                    and semantic_signature(all_claims[prior_id]) == semantic_signature(claim)
                    for prior_id in related
                )
                else "superseded"
            )
        else:
            matches = prior_active_by_signature.get(semantic_signature(claim), [])
            if matches:
                raise ValidationFailure(
                    f"claim {claim_id}: semantic duplicate of {matches}; reinforcement requires explicit supersedes"
                )
            active.add(claim_id)
            change_type = "new"
        changes.append(
            {
                "id": f"change:{run['id']}:{claim_id}",
                "run_id": run["id"],
                "claim_id": claim_id,
                "change_type": change_type,
                "related_claim_ids": sorted(related),
            }
        )

    active_relations.update(row["id"] for row in new_relations)
    snapshot = {
        "id": run["result_snapshot_id"],
        "company_id": run["company_id"],
        "created_at": run["completed_at"],
        "created_by_run": run["id"],
        "parent_snapshot_id": run["base_snapshot_id"],
        "active_claim_ids": sorted(active),
        "conflict_claim_ids": sorted(conflicts),
        "retraction_claim_ids": sorted(retractions),
        "active_relation_ids": sorted(active_relations),
        "content_hash": "",
    }
    candidate_claims = {row["id"]: row for row in state["claims"] + new_claims}
    candidate_relations = {row["id"]: row for row in state["relations"] + new_relations}
    snapshot["content_hash"] = compute_snapshot_hash(snapshot, candidate_claims, candidate_relations)
    return snapshot, changes


def validate_bundle(run: dict, rows: dict[str, list[dict]], bundle_root: Path) -> list[str]:
    errors = validate_schema(run, schema_for("run.schema.json"), "run")
    for key, (_, schema_filename) in BUNDLE_COLLECTIONS.items():
        errors.extend(validate_rows(rows[key], schema_filename, f"bundle.{key}"))
    expected_digest = bundle_digest(bundle_root)
    if run.get("input_digest") != expected_digest:
        errors.append(f"run.input_digest mismatch: expected {expected_digest}")
    for key, collection_rows in rows.items():
        for row in collection_rows:
            if row.get("created_by_run") != run.get("id"):
                errors.append(f"bundle.{key} {row.get('id')}: created_by_run must equal {run.get('id')!r}")
    return errors


def apply_run(workspace: Path, bundle_root: Path) -> dict:
    state = load_workspace(workspace)
    run, rows = load_bundle(bundle_root)
    errors = validate_bundle(run, rows, bundle_root)
    if run.get("company_id") != state["manifest"].get("company_id"):
        errors.append("run.company_id does not match workspace manifest")
    if run.get("base_snapshot_id") != state["manifest"].get("current_snapshot_id"):
        errors.append(
            f"stale base_snapshot_id: expected {state['manifest'].get('current_snapshot_id')!r}, got {run.get('base_snapshot_id')!r}"
        )
    if run.get("id") in {item["id"] for item in state["runs"]}:
        errors.append(f"duplicate run id {run.get('id')!r}")
    existing_ids = {
        row["id"]
        for key in COLLECTIONS
        for row in state.get(key, [])
        if isinstance(row.get("id"), str)
    }
    for key, collection_rows in rows.items():
        for row in collection_rows:
            if row.get("id") in existing_ids:
                errors.append(f"bundle.{key}: id already exists: {row.get('id')!r}")
            existing_ids.add(row.get("id"))
    if errors:
        raise ValidationFailure("\n".join(errors))

    snapshot, changes = materialize_snapshot(state, run, rows["claims"], rows["relations"])
    candidate = copy.deepcopy(state)
    for key, collection_rows in rows.items():
        candidate[key].extend(collection_rows)
    candidate["runs"].append(run)
    candidate["snapshots"].append(snapshot)
    candidate["changes"].extend(changes)
    candidate["manifest"]["current_snapshot_id"] = snapshot["id"]
    semantic_errors = validate_state(candidate, require_nonempty=True)
    if semantic_errors:
        raise ValidationFailure("\n".join(semantic_errors))

    # 所有校验通过后才修改文件系统。
    for key, collection_rows in rows.items():
        relative_path, _ = COLLECTIONS[key]
        append_jsonl(workspace / relative_path, collection_rows)
    append_jsonl(workspace / COLLECTIONS["runs"][0], [run])
    append_jsonl(workspace / COLLECTIONS["snapshots"][0], [snapshot])
    append_jsonl(workspace / COLLECTIONS["changes"][0], changes)
    write_json(workspace / "manifest.json", candidate["manifest"])
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="应用已通过校验的蒸馏运行包。")
    parser.add_argument("workspace", help="规范公司对象工作区")
    parser.add_argument("bundle", help="运行包目录")
    args = parser.parse_args()
    try:
        snapshot = apply_run(Path(args.workspace).resolve(), Path(args.bundle).resolve())
    except (ValidationFailure, FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"运行被拒绝：\n{exc}") from exc
    print(f"运行已应用；当前快照：{snapshot['id']}")
    print(f"内容哈希：{snapshot['content_hash']}")


if __name__ == "__main__":
    main()
