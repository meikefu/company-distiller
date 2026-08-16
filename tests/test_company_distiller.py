from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_evolving_example import build  # noqa: E402
from company_object_lib import (  # noqa: E402
    ValidationFailure,
    load_workspace,
    schema_for,
    validate_schema,
    validate_state,
)
from scaffold_company_skill import slugify  # noqa: E402
from validate_company_skill import validate_markdown_tables, validate_skill  # noqa: E402


class SchemaTests(unittest.TestCase):
    def test_claim_enum_is_strict(self):
        valid = {
            "id": "claim:test",
            "subject_id": "company:test",
            "predicate": "Identity.name",
            "value": "Test",
            "claim_type": "fact",
            "scope": "company",
            "valid_from": "2026-01-01T00:00:00+00:00",
            "valid_to": None,
            "observed_at": "2026-01-01T01:00:00+00:00",
            "evidence_ids": ["evidence:test"],
            "decision": "accepted",
            "confidence": {
                "source_reliability": "high",
                "corroboration": "single",
                "inference_strength": "direct",
                "overall": "high",
            },
            "supersedes": [],
            "contradicts": [],
            "policy_id": "policy:public",
            "created_by_run": "run:test",
        }
        self.assertEqual(validate_schema(valid, schema_for("claim.schema.json")), [])
        invalid = copy.deepcopy(valid)
        invalid["decision"] = "approved"
        self.assertTrue(validate_schema(invalid, schema_for("claim.schema.json")))

    def test_non_ascii_name_requires_slug(self):
        with self.assertRaises(ValueError):
            slugify("测试公司")
        self.assertEqual(slugify("test-company"), "test-company")

    def test_markdown_table_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "table.md"
            path.write_text("| A | B |\n|---|---|\n| only-one |\n", encoding="utf-8")
            self.assertTrue(validate_markdown_tables(path))


class IntegrationTests(unittest.TestCase):
    def test_repository_example_is_explicitly_synthetic(self):
        example = ROOT / "example" / "evolving-company" / "company-object"
        manifest = json.loads((example / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["company_id"], "company:example-company")
        self.assertEqual(manifest["company_name"], "Example Company (Synthetic)")

        sources = [
            json.loads(line)
            for line in (example / "sources" / "sources.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(sources)
        self.assertTrue(all(source["connector"] == "fixture" for source in sources))
        for source in sources:
            parsed = urlparse(source["locator"])
            if parsed.scheme in {"http", "https"}:
                self.assertEqual(parsed.hostname, "example.invalid")

    def test_three_run_example_and_projections_validate(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "example"
            build(output, force=False)
            state = load_workspace(output / "company-object")
            self.assertEqual(validate_state(state), [])
            self.assertEqual(len(state["runs"]), 3)
            self.assertEqual(len(state["snapshots"]), 3)
            for audience in ("public", "sales", "customer-success", "executive"):
                self.assertEqual(validate_skill(output / "projections" / audience), [])

    def test_policy_downgrade_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "example"
            build(output, force=False)
            state = load_workspace(output / "company-object")
            bad = copy.deepcopy(state)
            target = next(row for row in bad["claims"] if row["id"] == "claim:usage-active-sites")
            target["policy_id"] = "policy:public"
            errors = validate_state(bad)
            self.assertTrue(any("less restrictive" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
