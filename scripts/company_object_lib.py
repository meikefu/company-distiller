#!/usr/bin/env python3
"""Company Distiller 共用的数据契约与语义校验。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = PROJECT_ROOT / "schemas"

COLLECTIONS = {
    "entities": ("object/entities.jsonl", "entity.schema.json"),
    "sources": ("sources/sources.jsonl", "source.schema.json"),
    "records": ("records/records.jsonl", "record.schema.json"),
    "events": ("events/events.jsonl", "event.schema.json"),
    "evidence": ("evidence/index.jsonl", "evidence.schema.json"),
    "claims": ("claims/claims.jsonl", "claim.schema.json"),
    "relations": ("relations/relations.jsonl", "relation.schema.json"),
    "runs": ("runs/runs.jsonl", "run.schema.json"),
    "snapshots": ("snapshots/index.jsonl", "snapshot.schema.json"),
    "changes": ("changes/index.jsonl", "change.schema.json"),
}

BUNDLE_COLLECTIONS = {
    key: (Path(relpath).name if key != "evidence" else "evidence.jsonl", schema)
    for key, (relpath, schema) in COLLECTIONS.items()
    if key not in {"runs", "snapshots", "changes"}
}

RECORD_REQUIREMENTS = {
    "public_fact": {"fact_name", "value"},
    "crm_account": {"upstream_account_id", "owner_team", "lifecycle_state"},
    "crm_contact": {"upstream_contact_id", "role", "account_id"},
    "crm_opportunity": {"stage", "account_id", "close_date", "buying_context"},
    "crm_activity": {"activity_type", "participant_ids", "outcome"},
    "interview_segment": {
        "interview_id",
        "speaker_entity_id",
        "speaker_role",
        "topic",
        "transcript_locator",
        "consent_scope",
    },
    "contract_term": {
        "signing_entity_ids",
        "contract_id",
        "version",
        "effective_from",
        "effective_to",
        "product_id",
        "term",
    },
    "support_ticket": {
        "product_id",
        "product_version",
        "severity",
        "state",
        "opened_at",
        "closed_at",
    },
    "product_usage": {
        "metric_id",
        "metric_definition",
        "window_start",
        "window_end",
        "dimensions",
        "value",
        "unit",
        "data_quality",
    },
}

CLASSIFICATION_ORDER = ["public", "internal", "confidential", "restricted"]


class ValidationFailure(Exception):
    """Raised when a bundle or workspace violates a contract."""


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationFailure(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
        if not isinstance(row, dict):
            raise ValidationFailure(f"{path}:{line_number}: expected an object")
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(canonical_json(row) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(canonical_json(row) + "\n")


def parse_datetime(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timezone is required")
    return parsed


def _matches_type(value, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def validate_schema(instance, schema: dict, location: str = "$") -> list[str]:
    """Validate the JSON Schema subset used by this project."""
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_matches_type(instance, item) for item in expected_types):
            return [f"{location}: expected type {expected_type}, got {type(instance).__name__}"]

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{location}: must equal {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{location}: {instance!r} is not in {schema['enum']!r}")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{location}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{location}: unexpected property {key!r}")
        additional = schema.get("additionalProperties")
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate_schema(value, properties[key], f"{location}.{key}"))
            elif isinstance(additional, dict):
                errors.extend(validate_schema(value, additional, f"{location}.{key}"))
        if len(instance) < schema.get("minProperties", 0):
            errors.append(f"{location}: has fewer than {schema['minProperties']} properties")

    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{location}: has fewer than {schema['minItems']} items")
        if schema.get("uniqueItems"):
            serialized = [canonical_json(item) for item in instance]
            if len(serialized) != len(set(serialized)):
                errors.append(f"{location}: items must be unique")
        item_schema = schema.get("items")
        if item_schema:
            for index, value in enumerate(instance):
                errors.extend(validate_schema(value, item_schema, f"{location}[{index}]"))

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append(f"{location}: string is too short")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, instance) is None:
            errors.append(f"{location}: {instance!r} does not match {pattern!r}")
        if schema.get("format") == "date-time":
            try:
                parse_datetime(instance)
            except (TypeError, ValueError) as exc:
                errors.append(f"{location}: invalid date-time: {exc}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{location}: must be >= {schema['minimum']}")
    return errors


def schema_for(filename: str) -> dict:
    return read_json(SCHEMA_DIR / filename)


def validate_rows(rows: list[dict], schema_filename: str, label: str) -> list[str]:
    schema = schema_for(schema_filename)
    errors = []
    for index, row in enumerate(rows, 1):
        errors.extend(validate_schema(row, schema, f"{label}[{index}]"))
    return errors


def load_workspace(root: Path) -> dict[str, list[dict]]:
    state = {}
    for key, (relative_path, _) in COLLECTIONS.items():
        state[key] = read_jsonl(root / relative_path)
    state["policies"] = read_json(root / "governance/policies.json")
    state["manifest"] = read_json(root / "manifest.json")
    return state


def load_bundle(root: Path) -> tuple[dict, dict[str, list[dict]]]:
    run = read_json(root / "run.json")
    rows = {}
    for key, (filename, _) in BUNDLE_COLLECTIONS.items():
        rows[key] = read_jsonl(root / filename)
    return run, rows


def bundle_digest(root: Path) -> str:
    run = read_json(root / "run.json")
    run = dict(run)
    run["input_digest"] = ""
    payload = {"run": run, "collections": {}}
    for key, (filename, _) in sorted(BUNDLE_COLLECTIONS.items()):
        payload["collections"][key] = read_jsonl(root / filename)
    return sha256_value(payload)


def _ids(rows: list[dict]) -> set[str]:
    return {row["id"] for row in rows if isinstance(row.get("id"), str)}


def _index(rows: list[dict]) -> dict[str, dict]:
    return {row["id"]: row for row in rows if isinstance(row.get("id"), str)}


def _policy_index(policy_document: dict) -> dict[str, dict]:
    return {policy["id"]: policy for policy in policy_document.get("policies", [])}


def _policy_is_at_least(child: dict, parent: dict) -> bool:
    child_rank = CLASSIFICATION_ORDER.index(child["classification"])
    parent_rank = CLASSIFICATION_ORDER.index(parent["classification"])
    return (
        child_rank >= parent_rank
        and set(child["allowed_audiences"]) <= set(parent["allowed_audiences"])
        and set(child["allowed_purposes"]) <= set(parent["allowed_purposes"])
    )


def _validate_time_order(row: dict, start_key: str, end_key: str, label: str) -> list[str]:
    if not row.get(start_key) or not row.get(end_key):
        return []
    try:
        if parse_datetime(row[start_key]) > parse_datetime(row[end_key]):
            return [f"{label}: {start_key} is after {end_key}"]
    except (TypeError, ValueError):
        return []
    return []


def _validate_acyclic(index: dict[str, dict], edge_field: str, label: str) -> list[str]:
    errors = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str, path: list[str]) -> None:
        if node_id in visiting:
            errors.append(f"{label}: cycle detected: {' -> '.join(path + [node_id])}")
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        for target_id in index[node_id].get(edge_field, []):
            if target_id in index:
                visit(target_id, path + [node_id])
        visiting.remove(node_id)
        visited.add(node_id)

    for item_id in index:
        visit(item_id, [])
    return errors


def validate_state(state: dict, require_nonempty: bool = True) -> list[str]:
    errors: list[str] = []
    for key, (_, schema_filename) in COLLECTIONS.items():
        errors.extend(validate_rows(state.get(key, []), schema_filename, key))
    errors.extend(validate_schema(state.get("policies"), schema_for("policy.schema.json"), "policies"))

    if require_nonempty:
        for key in ("entities", "sources", "records", "evidence", "claims", "runs", "snapshots"):
            if not state.get(key):
                errors.append(f"{key}: must not be empty")

    all_ids: dict[str, str] = {}
    for key in COLLECTIONS:
        for row in state.get(key, []):
            item_id = row.get("id")
            if not isinstance(item_id, str):
                continue
            if item_id in all_ids:
                errors.append(f"duplicate id {item_id!r} in {all_ids[item_id]} and {key}")
            all_ids[item_id] = key

    policies = _policy_index(state.get("policies", {}))
    if len(policies) != len(state.get("policies", {}).get("policies", [])):
        errors.append("policies: duplicate policy id")
    if state.get("policies", {}).get("classification_order") != CLASSIFICATION_ORDER:
        errors.append("policies: unsupported classification order")

    indexes = {key: _index(state.get(key, [])) for key in COLLECTIONS}
    entity_ids = set(indexes["entities"])
    source_ids = set(indexes["sources"])
    record_ids = set(indexes["records"])
    event_ids = set(indexes["events"])
    evidence_ids = set(indexes["evidence"])
    claim_ids = set(indexes["claims"])
    relation_ids = set(indexes["relations"])
    run_ids = set(indexes["runs"])
    snapshot_ids = set(indexes["snapshots"])

    def require_ingested_after_observation(row: dict, label: str) -> None:
        run = indexes["runs"].get(row.get("created_by_run"))
        observed_at = row.get("observed_at")
        if not run or not observed_at:
            return
        try:
            if parse_datetime(observed_at) > parse_datetime(run["completed_at"]):
                errors.append(f"{label}: observed_at is after creating run completed_at")
        except (TypeError, ValueError):
            return

    def require_ref(ref: str, allowed: set[str], label: str) -> None:
        if ref not in allowed:
            errors.append(f"{label}: unresolved reference {ref!r}")

    def require_policy(row: dict, label: str) -> dict | None:
        policy_id = row.get("policy_id")
        if policy_id not in policies:
            errors.append(f"{label}: unresolved policy {policy_id!r}")
            return None
        return policies[policy_id]

    def require_inheritance(row: dict, dependencies: list[dict], label: str) -> None:
        child = require_policy(row, label)
        if child is None:
            return
        for dependency in dependencies:
            parent = policies.get(dependency.get("policy_id"))
            if parent and not _policy_is_at_least(child, parent):
                errors.append(
                    f"{label}: policy {child['id']!r} is less restrictive than dependency policy {parent['id']!r}"
                )

    for row in state.get("entities", []):
        label = f"entity {row.get('id')}"
        parent = None
        if row.get("parent_id"):
            require_ref(row["parent_id"], entity_ids, label)
            parent = indexes["entities"].get(row["parent_id"])
        if parent:
            require_inheritance(row, [parent], label)
        else:
            require_policy(row, label)
        require_ref(row.get("created_by_run"), run_ids, label)

    for row in state.get("sources", []):
        label = f"source {row.get('id')}"
        require_policy(row, label)
        require_ref(row.get("created_by_run"), run_ids, label)
        require_ingested_after_observation(row, label)
        errors.extend(_validate_time_order(row, "source_date", "observed_at", label))

    for row in state.get("records", []):
        label = f"record {row.get('id')}"
        source = indexes["sources"].get(row.get("source_id"))
        dependencies = []
        require_ref(row.get("source_id"), source_ids, label)
        for entity_id in row.get("subject_ids", []):
            require_ref(entity_id, entity_ids, label)
            if entity_id in indexes["entities"]:
                dependencies.append(indexes["entities"][entity_id])
        require_ref(row.get("created_by_run"), run_ids, label)
        require_ingested_after_observation(row, label)
        if source:
            dependencies.append(source)
        if dependencies:
            require_inheritance(row, dependencies, label)
        else:
            require_policy(row, label)
        missing = RECORD_REQUIREMENTS.get(row.get("record_type"), set()) - set(row.get("data", {}))
        if missing:
            errors.append(f"{label}: data missing semantic fields {sorted(missing)}")
        errors.extend(_validate_time_order(row, "valid_from", "valid_to", label))

    for row in state.get("events", []):
        label = f"event {row.get('id')}"
        dependencies = []
        for entity_id in row.get("subject_ids", []):
            require_ref(entity_id, entity_ids, label)
            if entity_id in indexes["entities"]:
                dependencies.append(indexes["entities"][entity_id])
        for source_id in row.get("source_ids", []):
            require_ref(source_id, source_ids, label)
            if source_id in indexes["sources"]:
                dependencies.append(indexes["sources"][source_id])
        for record_id in row.get("record_ids", []):
            require_ref(record_id, record_ids, label)
            if record_id in indexes["records"]:
                dependencies.append(indexes["records"][record_id])
        require_ref(row.get("created_by_run"), run_ids, label)
        require_ingested_after_observation(row, label)
        require_inheritance(row, dependencies, label)
        errors.extend(_validate_time_order(row, "occurred_at", "observed_at", label))

    for row in state.get("evidence", []):
        label = f"evidence {row.get('id')}"
        dependencies = []
        for source_id in row.get("source_ids", []):
            require_ref(source_id, source_ids, label)
            if source_id in indexes["sources"]:
                dependencies.append(indexes["sources"][source_id])
        for record_id in row.get("record_ids", []):
            require_ref(record_id, record_ids, label)
            if record_id in indexes["records"]:
                dependencies.append(indexes["records"][record_id])
        for event_id in row.get("event_ids", []):
            require_ref(event_id, event_ids, label)
            if event_id in indexes["events"]:
                dependencies.append(indexes["events"][event_id])
        for parent_id in row.get("derived_from", []):
            require_ref(parent_id, evidence_ids, label)
            if parent_id in indexes["evidence"]:
                dependencies.append(indexes["evidence"][parent_id])
        require_ref(row.get("created_by_run"), run_ids, label)
        require_ingested_after_observation(row, label)
        require_inheritance(row, dependencies, label)
    errors.extend(_validate_acyclic(indexes["evidence"], "derived_from", "evidence derivation"))

    for row in state.get("claims", []):
        label = f"claim {row.get('id')}"
        require_ref(row.get("subject_id"), entity_ids, label)
        dependencies = []
        if row.get("subject_id") in indexes["entities"]:
            dependencies.append(indexes["entities"][row["subject_id"]])
        for evidence_id in row.get("evidence_ids", []):
            require_ref(evidence_id, evidence_ids, label)
            if evidence_id in indexes["evidence"]:
                dependencies.append(indexes["evidence"][evidence_id])
        for prior_id in row.get("supersedes", []):
            require_ref(prior_id, claim_ids, label)
            if prior_id in indexes["claims"]:
                dependencies.append(indexes["claims"][prior_id])
        for prior_id in row.get("contradicts", []):
            require_ref(prior_id, claim_ids, label)
            if prior_id in indexes["claims"]:
                dependencies.append(indexes["claims"][prior_id])
        if row.get("decision") == "retracted" and not row.get("supersedes"):
            errors.append(f"{label}: a retraction must supersede at least one claim")
        require_ref(row.get("created_by_run"), run_ids, label)
        require_ingested_after_observation(row, label)
        require_inheritance(row, dependencies, label)
        errors.extend(_validate_time_order(row, "valid_from", "valid_to", label))
    errors.extend(_validate_acyclic(indexes["claims"], "supersedes", "claim supersession"))

    for row in state.get("relations", []):
        label = f"relation {row.get('id')}"
        require_ref(row.get("subject_id"), entity_ids, label)
        require_ref(row.get("object_id"), entity_ids, label)
        dependencies = []
        if row.get("subject_id") in indexes["entities"]:
            dependencies.append(indexes["entities"][row["subject_id"]])
        if row.get("object_id") in indexes["entities"]:
            dependencies.append(indexes["entities"][row["object_id"]])
        for evidence_id in row.get("evidence_ids", []):
            require_ref(evidence_id, evidence_ids, label)
            if evidence_id in indexes["evidence"]:
                dependencies.append(indexes["evidence"][evidence_id])
        require_ref(row.get("created_by_run"), run_ids, label)
        require_ingested_after_observation(row, label)
        require_inheritance(row, dependencies, label)
        errors.extend(_validate_time_order(row, "valid_from", "valid_to", label))

    for row in state.get("runs", []):
        label = f"run {row.get('id')}"
        require_ref(row.get("company_id"), entity_ids, label)
        if row.get("base_snapshot_id"):
            require_ref(row["base_snapshot_id"], snapshot_ids, label)
        require_ref(row.get("result_snapshot_id"), snapshot_ids, label)
        errors.extend(_validate_time_order(row, "started_at", "completed_at", label))

    for row in state.get("snapshots", []):
        label = f"snapshot {row.get('id')}"
        require_ref(row.get("company_id"), entity_ids, label)
        require_ref(row.get("created_by_run"), run_ids, label)
        if row.get("parent_snapshot_id"):
            require_ref(row["parent_snapshot_id"], snapshot_ids, label)
        active_ids = set(row.get("active_claim_ids", []))
        conflict_ids = set(row.get("conflict_claim_ids", []))
        retraction_ids = set(row.get("retraction_claim_ids", []))
        if active_ids & conflict_ids or active_ids & retraction_ids or conflict_ids & retraction_ids:
            errors.append(f"{label}: active, conflict, and retraction Claim sets must be disjoint")
        for claim_id in active_ids | conflict_ids | retraction_ids:
            require_ref(claim_id, claim_ids, label)
        for claim_id in active_ids | conflict_ids:
            if claim_id in indexes["claims"] and indexes["claims"][claim_id].get("decision") != "accepted":
                errors.append(f"{label}: current/conflict Claim {claim_id!r} must be accepted")
        for claim_id in retraction_ids:
            if claim_id in indexes["claims"] and indexes["claims"][claim_id].get("decision") != "retracted":
                errors.append(f"{label}: retraction Claim {claim_id!r} must be retracted")
        for relation_id in row.get("active_relation_ids", []):
            require_ref(relation_id, relation_ids, label)
        expected_hash = compute_snapshot_hash(row, indexes["claims"], indexes["relations"])
        if row.get("content_hash") != expected_hash:
            errors.append(f"{label}: content_hash mismatch")

    for row in state.get("changes", []):
        label = f"change {row.get('id')}"
        require_ref(row.get("run_id"), run_ids, label)
        require_ref(row.get("claim_id"), claim_ids, label)
        for claim_id in row.get("related_claim_ids", []):
            require_ref(claim_id, claim_ids, label)

    manifest = state.get("manifest", {})
    require_ref(manifest.get("company_id"), entity_ids, "manifest")
    current_snapshot_id = manifest.get("current_snapshot_id")
    if current_snapshot_id:
        require_ref(current_snapshot_id, snapshot_ids, "manifest")
        if state.get("snapshots") and state["snapshots"][-1].get("id") != current_snapshot_id:
            errors.append("manifest: current_snapshot_id is not the latest snapshot")
    if state.get("runs") and state.get("snapshots"):
        if state["runs"][-1].get("result_snapshot_id") != state["snapshots"][-1].get("id"):
            errors.append("latest run result does not match latest snapshot")
    return errors


def compute_snapshot_hash(snapshot: dict, claims: dict[str, dict], relations: dict[str, dict]) -> str:
    payload = {
        "company_id": snapshot["company_id"],
        "parent_snapshot_id": snapshot.get("parent_snapshot_id"),
        "active_claims": [claims[item_id] for item_id in sorted(snapshot.get("active_claim_ids", [])) if item_id in claims],
        "conflict_claims": [claims[item_id] for item_id in sorted(snapshot.get("conflict_claim_ids", [])) if item_id in claims],
        "retraction_claims": [claims[item_id] for item_id in sorted(snapshot.get("retraction_claim_ids", [])) if item_id in claims],
        "active_relations": [relations[item_id] for item_id in sorted(snapshot.get("active_relation_ids", [])) if item_id in relations],
    }
    return sha256_value(payload)


def semantic_signature(claim: dict) -> str:
    return canonical_json(
        {
            "subject_id": claim["subject_id"],
            "predicate": claim["predicate"],
            "value": claim["value"],
            "claim_type": claim["claim_type"],
            "scope": claim["scope"],
            "valid_from": claim["valid_from"],
            "valid_to": claim.get("valid_to"),
        }
    )


def policy_allows(policy: dict, audience: str, purpose: str) -> bool:
    return audience in policy["allowed_audiences"] and purpose in policy["allowed_purposes"]
