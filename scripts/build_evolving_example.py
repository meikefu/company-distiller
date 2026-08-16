#!/usr/bin/env python3
"""构建包含三次运行的确定性内部数据示例。"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from apply_run import apply_run
from company_object_lib import BUNDLE_COLLECTIONS, sha256_value, write_json, write_jsonl
from export_company_skill import AUDIENCE_PURPOSE, export_skill
from scaffold_company_skill import scaffold
from update_bundle_digest import update_digest


PUBLIC = "policy:public"
SALES = "policy:confidential-sales"
CS = "policy:confidential-cs"
EXEC = "policy:restricted-executive"
COMPANY = "company:example-company"


def confidence(reliability="high", corroboration="single", strength="direct", overall="high"):
    return {
        "source_reliability": reliability,
        "corroboration": corroboration,
        "inference_strength": strength,
        "overall": overall,
    }


def source(item_id, source_type, title, date, policy, run_id, external_id, version, locator):
    return {
        "id": item_id,
        "source_type": source_type,
        "title": title,
        "source_date": date,
        "observed_at": date,
        "content_hash": sha256_value({"id": item_id, "version": version, "title": title}),
        "connector": "fixture",
        "external_id": external_id,
        "version": version,
        "locator": locator,
        "policy_id": policy,
        "created_by_run": run_id,
    }


def entity(item_id, entity_type, name, scope, policy, run_id, parent=None):
    return {
        "id": item_id,
        "entity_type": entity_type,
        "name": name,
        "aliases": [],
        "parent_id": parent,
        "scope": scope,
        "external_ids": {},
        "policy_id": policy,
        "created_by_run": run_id,
    }


def evidence(item_id, evidence_type, source_ids, record_ids, event_ids, locator, excerpt, observed, policy, run_id):
    return {
        "id": item_id,
        "evidence_type": evidence_type,
        "source_ids": source_ids,
        "record_ids": record_ids,
        "event_ids": event_ids,
        "locator": locator,
        "excerpt": excerpt,
        "observed_at": observed,
        "policy_id": policy,
        "derived_from": [],
        "created_by_run": run_id,
    }


def claim(
    item_id,
    subject_id,
    predicate,
    value,
    claim_type,
    scope,
    valid_from,
    observed_at,
    evidence_ids,
    policy,
    run_id,
    decision="accepted",
    supersedes=None,
    contradicts=None,
    conf=None,
):
    return {
        "id": item_id,
        "subject_id": subject_id,
        "predicate": predicate,
        "value": value,
        "claim_type": claim_type,
        "scope": scope,
        "valid_from": valid_from,
        "valid_to": None,
        "observed_at": observed_at,
        "evidence_ids": evidence_ids,
        "decision": decision,
        "confidence": conf or confidence(),
        "supersedes": supersedes or [],
        "contradicts": contradicts or [],
        "policy_id": policy,
        "created_by_run": run_id,
    }


def relation(item_id, subject_id, predicate, object_id, date, evidence_ids, policy, run_id, context=None):
    return {
        "id": item_id,
        "subject_id": subject_id,
        "predicate": predicate,
        "object_id": object_id,
        "context": context,
        "valid_from": date,
        "valid_to": None,
        "observed_at": date,
        "evidence_ids": evidence_ids,
        "confidence": "high",
        "policy_id": policy,
        "created_by_run": run_id,
    }


def empty_bundle_rows():
    return {key: [] for key in BUNDLE_COLLECTIONS}


def write_bundle(root: Path, run: dict, rows: dict[str, list[dict]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "run.json", run)
    for key, (filename, _) in BUNDLE_COLLECTIONS.items():
        write_jsonl(root / filename, rows[key])
    update_digest(root)


def run_one(root: Path):
    run_id = "run:example-company:001"
    at = "2026-01-15T09:00:00+00:00"
    rows = empty_bundle_rows()
    rows["entities"] = [
        entity(COMPANY, "company", "Example Company (Synthetic)", "company", PUBLIC, run_id),
        entity("legal_entity:example-company-holdings", "legal_entity", "Example Company Holdings (Synthetic)", "company", PUBLIC, run_id, COMPANY),
        entity("business_unit:example-company-software", "business_unit", "Example Company Software Unit", "company", PUBLIC, run_id, COMPANY),
        entity("product:example-product", "product", "Example Product", "company", PUBLIC, run_id, COMPANY),
        entity("market:industrial-operations", "market", "工业运营团队", "company", PUBLIC, run_id),
    ]
    rows["sources"] = [
        source("source:example-company-site-v1", "official_website", "Example Company fixture profile", at, PUBLIC, run_id, "example-company-site", "v1", "https://example.invalid/example-company/about#products")
    ]
    rows["records"] = [
        {
            "id": "record:public-profile-v1",
            "record_type": "public_fact",
            "source_id": "source:example-company-site-v1",
            "subject_ids": [COMPANY, "product:example-product"],
            "observed_at": at,
            "valid_from": "2026-01-01T00:00:00+00:00",
            "valid_to": None,
            "data": {"fact_name": "company_profile", "value": "合成公司夹具与 Example Product"},
            "policy_id": PUBLIC,
            "created_by_run": run_id,
        }
    ]
    rows["events"] = [
        {
            "id": "event:public-profile-observed",
            "event_type": "company_update",
            "subject_ids": [COMPANY],
            "occurred_at": at,
            "observed_at": at,
            "source_ids": ["source:example-company-site-v1"],
            "record_ids": ["record:public-profile-v1"],
            "data": {"update": "首次建立公开资料"},
            "policy_id": PUBLIC,
            "created_by_run": run_id,
        }
    ]
    rows["evidence"] = [
        evidence("evidence:public-category", "document_excerpt", ["source:example-company-site-v1"], ["record:public-profile-v1"], ["event:public-profile-observed"], "about#company", "Example Company 是用于测试公司对象演进的合成夹具。", at, PUBLIC, run_id),
        evidence("evidence:public-product", "document_excerpt", ["source:example-company-site-v1"], ["record:public-profile-v1"], ["event:public-profile-observed"], "products#example-product", "Example Product 定位为 7x24 小时高韧性运营平台。", at, PUBLIC, run_id),
    ]
    rows["claims"] = [
        claim("claim:company-category-v1", COMPANY, "BusinessModel.category", "工业运营软件", "fact", "company", "2026-01-01T00:00:00+00:00", at, ["evidence:public-category"], PUBLIC, run_id),
        claim("claim:example-product-positioning-v1", "product:example-product", "Products.positioning", "7x24 小时高韧性运营平台", "statement", "company", "2026-01-01T00:00:00+00:00", at, ["evidence:public-product"], PUBLIC, run_id, conf=confidence("medium", "single", "direct", "medium")),
    ]
    rows["relations"] = [relation("relation:example-company-offers-example-product", COMPANY, "offers", "product:example-product", "2026-01-01T00:00:00+00:00", ["evidence:public-product"], PUBLIC, run_id)]
    run = {
        "id": run_id,
        "company_id": COMPANY,
        "base_snapshot_id": None,
        "started_at": "2026-01-15T08:59:00+00:00",
        "completed_at": at,
        "mode": "initial",
        "model": "fixture-distiller-v1",
        "prompt_version": "company-distiller-v2",
        "input_digest": "",
        "connector_cursors": {"public": "2026-01-15"},
        "status": "completed",
        "result_snapshot_id": "snapshot:example-company:001",
    }
    write_bundle(root, run, rows)


def run_two(root: Path):
    run_id = "run:example-company:002"
    at = "2026-03-10T12:00:00+00:00"
    rows = empty_bundle_rows()
    rows["entities"] = [
        entity("account:example-company-crm", "account", "Example Company CRM Account", "commercial_relationship", SALES, run_id),
        entity("opportunity:example-security", "opportunity", "Example Product Security Opportunity", "commercial_relationship", SALES, run_id, "account:example-company-crm"),
        entity("role:security-sponsor", "role", "安全项目发起人", "commercial_relationship", SALES, run_id),
    ]
    rows["sources"] = [
        source("source:example-company-site-v2", "official_website", "Example Company fixture profile revision", at, PUBLIC, run_id, "example-company-site", "v2", "https://example.invalid/example-company/about#category"),
        source("source:crm-export-001", "crm", "CRM 客户与商机导出", at, SALES, run_id, "crm-account-991", "2026-03-10", "crm://accounts/991"),
        source("source:interview-001", "interview", "安全项目发起人访谈", "2026-03-09T16:00:00+00:00", SALES, run_id, "interview-001", "v1", "interview://001#segment-07"),
    ]
    rows["records"] = [
        {
            "id": "record:public-profile-v2",
            "record_type": "public_fact",
            "source_id": "source:example-company-site-v2",
            "subject_ids": [COMPANY],
            "observed_at": at,
            "valid_from": "2026-01-01T00:00:00+00:00",
            "valid_to": None,
            "data": {"fact_name": "company_category", "value": "工业运营软件"},
            "policy_id": PUBLIC,
            "created_by_run": run_id,
        },
        {
            "id": "record:crm-account-001",
            "record_type": "crm_account",
            "source_id": "source:crm-export-001",
            "subject_ids": ["account:example-company-crm", COMPANY],
            "observed_at": at,
            "valid_from": at,
            "valid_to": None,
            "data": {"upstream_account_id": "991", "owner_team": "战略客户团队", "lifecycle_state": "prospect"},
            "policy_id": SALES,
            "created_by_run": run_id,
        },
        {
            "id": "record:crm-opportunity-001",
            "record_type": "crm_opportunity",
            "source_id": "source:crm-export-001",
            "subject_ids": ["opportunity:example-security", "account:example-company-crm"],
            "observed_at": at,
            "valid_from": at,
            "valid_to": None,
            "data": {"stage": "discovery", "account_id": "account:example-company-crm", "close_date": "2026-09-30", "buying_context": "TEST_ONLY_CRM_SENTINEL_NEON 安全体系现代化"},
            "policy_id": SALES,
            "created_by_run": run_id,
        },
        {
            "id": "record:interview-segment-001",
            "record_type": "interview_segment",
            "source_id": "source:interview-001",
            "subject_ids": [COMPANY, "role:security-sponsor"],
            "observed_at": at,
            "valid_from": "2026-03-09T16:00:00+00:00",
            "valid_to": None,
            "data": {"interview_id": "interview-001", "speaker_entity_id": "role:security-sponsor", "speaker_role": "安全项目发起人", "topic": "采购", "transcript_locator": "segment-07", "consent_scope": "internal account planning"},
            "policy_id": SALES,
            "created_by_run": run_id,
        },
    ]
    rows["events"] = [
        {
            "id": "event:opportunity-discovery",
            "event_type": "opportunity_stage_changed",
            "subject_ids": ["opportunity:example-security"],
            "occurred_at": at,
            "observed_at": at,
            "source_ids": ["source:crm-export-001"],
            "record_ids": ["record:crm-opportunity-001"],
            "data": {"from": "unknown", "to": "discovery"},
            "policy_id": SALES,
            "created_by_run": run_id,
        },
        {
            "id": "event:interview-001",
            "event_type": "interview_conducted",
            "subject_ids": [COMPANY, "role:security-sponsor"],
            "occurred_at": "2026-03-09T16:00:00+00:00",
            "observed_at": at,
            "source_ids": ["source:interview-001"],
            "record_ids": ["record:interview-segment-001"],
            "data": {"topic": "采购"},
            "policy_id": SALES,
            "created_by_run": run_id,
        },
    ]
    rows["evidence"] = [
        evidence("evidence:public-category-v2", "document_excerpt", ["source:example-company-site-v2"], ["record:public-profile-v2"], [], "about#category", "Example Company 是用于测试公司对象演进的合成夹具。", at, PUBLIC, run_id),
        evidence("evidence:crm-opportunity", "structured_observation", ["source:crm-export-001"], ["record:crm-opportunity-001"], ["event:opportunity-discovery"], "opportunity.stage", "商机阶段为 discovery；客户备注标记为 TEST_ONLY_CRM_SENTINEL_NEON。", at, SALES, run_id),
        evidence("evidence:interview-procurement", "interview_statement", ["source:interview-001"], ["record:interview-segment-001"], ["event:interview-001"], "segment-07", "项目发起人表示，安全采购由总部统一管理。", at, SALES, run_id),
    ]
    rows["claims"] = [
        claim("claim:company-category-v2", COMPANY, "BusinessModel.category", "工业运营软件", "fact", "company", "2026-01-01T00:00:00+00:00", at, ["evidence:public-category-v2"], PUBLIC, run_id, supersedes=["claim:company-category-v1"], conf=confidence("high", "multiple", "direct", "high")),
        claim("claim:opportunity-stage-discovery", "opportunity:example-security", "CommercialRelationship.opportunity_stage", "探索阶段（discovery）/ TEST_ONLY_CRM_SENTINEL_NEON", "observation", "commercial_relationship", at, at, ["evidence:crm-opportunity"], SALES, run_id),
        claim("claim:procurement-centralized", COMPANY, "CommercialRelationship.procurement_model", "安全采购由总部统一管理", "statement", "commercial_relationship", "2026-03-09T16:00:00+00:00", at, ["evidence:interview-procurement"], SALES, run_id, conf=confidence("medium", "single", "direct", "medium")),
    ]
    rows["relations"] = [
        relation("relation:account-has-opportunity", "account:example-company-crm", "contains", "opportunity:example-security", at, ["evidence:crm-opportunity"], SALES, run_id)
    ]
    run = {
        "id": run_id,
        "company_id": COMPANY,
        "base_snapshot_id": "snapshot:example-company:001",
        "started_at": "2026-03-10T11:58:00+00:00",
        "completed_at": at,
        "mode": "incremental",
        "model": "fixture-distiller-v1",
        "prompt_version": "company-distiller-v2",
        "input_digest": "",
        "connector_cursors": {"public": "2026-03-10", "crm": "cursor-001", "interview": "interview-001"},
        "status": "completed",
        "result_snapshot_id": "snapshot:example-company:002",
    }
    write_bundle(root, run, rows)


def run_three(root: Path):
    run_id = "run:example-company:003"
    at = "2026-07-01T01:00:00+00:00"
    rows = empty_bundle_rows()
    rows["entities"] = [
        entity("contract:example-enterprise-001", "contract", "Example Product Enterprise Agreement", "commercial_relationship", EXEC, run_id),
        entity("subscription:example-product-test", "subscription", "Example Product Test Subscription", "product_use_service", CS, run_id),
        entity("ticket:sev1-042", "ticket", "Example Product SEV-1 Test Ticket 042", "product_use_service", CS, run_id),
        entity("metric:weekly-active-sites", "metric", "每周活跃站点", "product_use_service", CS, run_id),
    ]
    rows["sources"] = [
        source("source:crm-export-002", "crm", "CRM 商机更新", at, SALES, run_id, "crm-account-991", "2026-06-30", "crm://accounts/991/opportunities/7"),
        source("source:interview-correction", "interview", "安全项目发起人访谈更正", "2026-06-15T10:00:00+00:00", SALES, run_id, "interview-001-correction", "v1", "interview://001/correction"),
        source("source:contract-001", "contract", "Example Product Enterprise Agreement", "2026-06-20T12:00:00+00:00", EXEC, run_id, "contract-001", "signed-v1", "contract://001#pricing"),
        source("source:support-042", "support", "SEV-1 支持工单", "2026-06-25T15:00:00+00:00", CS, run_id, "ticket-042", "closed-v1", "support://tickets/042"),
        source("source:usage-june", "product_analytics", "六月使用量汇总", at, CS, run_id, "usage-example-company-june", "v1", "warehouse://usage/example-company/2026-06"),
    ]
    rows["records"] = [
        {
            "id": "record:crm-opportunity-002",
            "record_type": "crm_opportunity",
            "source_id": "source:crm-export-002",
            "subject_ids": ["opportunity:example-security", "account:example-company-crm"],
            "observed_at": at,
            "valid_from": "2026-06-30T12:00:00+00:00",
            "valid_to": None,
            "data": {"stage": "validation", "account_id": "account:example-company-crm", "close_date": "2026-09-30", "buying_context": "安全试点验证"},
            "policy_id": SALES,
            "created_by_run": run_id,
        },
        {
            "id": "record:interview-correction",
            "record_type": "interview_segment",
            "source_id": "source:interview-correction",
            "subject_ids": [COMPANY, "role:security-sponsor"],
            "observed_at": at,
            "valid_from": "2026-06-15T10:00:00+00:00",
            "valid_to": None,
            "data": {"interview_id": "interview-001-correction", "speaker_entity_id": "role:security-sponsor", "speaker_role": "安全项目发起人", "topic": "采购访谈更正", "transcript_locator": "correction", "consent_scope": "internal account planning"},
            "policy_id": SALES,
            "created_by_run": run_id,
        },
        {
            "id": "record:contract-term-001",
            "record_type": "contract_term",
            "source_id": "source:contract-001",
            "subject_ids": [COMPANY, "contract:example-enterprise-001", "product:example-product"],
            "observed_at": at,
            "valid_from": "2026-07-01T00:00:00+00:00",
            "valid_to": "2027-06-30T23:59:59+00:00",
            "data": {"signing_entity_ids": ["legal_entity:example-company-holdings"], "contract_id": "contract-001", "version": "signed-v1", "effective_from": "2026-07-01", "effective_to": "2027-06-30", "product_id": "product:example-product", "term": "高管级定价代码 TEST_ONLY_CONTRACT_SENTINEL_VAULT", "amount": 840000, "currency": "USD"},
            "policy_id": EXEC,
            "created_by_run": run_id,
        },
        {
            "id": "record:support-ticket-042",
            "record_type": "support_ticket",
            "source_id": "source:support-042",
            "subject_ids": [COMPANY, "ticket:sev1-042", "product:example-product"],
            "observed_at": at,
            "valid_from": "2026-06-25T09:00:00+00:00",
            "valid_to": "2026-06-25T15:00:00+00:00",
            "data": {"product_id": "product:example-product", "product_version": "4.8.1", "severity": "SEV-1", "state": "resolved", "opened_at": "2026-06-25T09:00:00Z", "closed_at": "2026-06-25T15:00:00Z", "root_cause": "故障转移回路 TEST_ONLY_TICKET_SENTINEL_CIRCUIT"},
            "policy_id": CS,
            "created_by_run": run_id,
        },
        {
            "id": "record:usage-june",
            "record_type": "product_usage",
            "source_id": "source:usage-june",
            "subject_ids": [COMPANY, "subscription:example-product-test", "metric:weekly-active-sites"],
            "observed_at": at,
            "valid_from": "2026-06-01T00:00:00+00:00",
            "valid_to": "2026-06-30T23:59:59+00:00",
            "data": {"metric_id": "metric:weekly-active-sites", "metric_definition": "七天内至少运行一次生产工作流的去重站点数", "window_start": "2026-06-01", "window_end": "2026-06-30", "dimensions": {"environment": "production"}, "value": 37, "unit": "sites", "data_quality": "数据完整；质量标记 TEST_ONLY_USAGE_SENTINEL_PULSE"},
            "policy_id": CS,
            "created_by_run": run_id,
        },
    ]
    rows["events"] = [
        {
            "id": "event:opportunity-validation",
            "event_type": "opportunity_stage_changed",
            "subject_ids": ["opportunity:example-security"],
            "occurred_at": "2026-06-30T12:00:00+00:00",
            "observed_at": at,
            "source_ids": ["source:crm-export-002"],
            "record_ids": ["record:crm-opportunity-002"],
            "data": {"from": "discovery", "to": "validation"},
            "policy_id": SALES,
            "created_by_run": run_id,
        },
        {
            "id": "event:contract-signed",
            "event_type": "contract_signed",
            "subject_ids": [COMPANY, "contract:example-enterprise-001"],
            "occurred_at": "2026-06-20T12:00:00+00:00",
            "observed_at": at,
            "source_ids": ["source:contract-001"],
            "record_ids": ["record:contract-term-001"],
            "data": {"effective_from": "2026-07-01"},
            "policy_id": EXEC,
            "created_by_run": run_id,
        },
        {
            "id": "event:ticket-resolved-042",
            "event_type": "ticket_resolved",
            "subject_ids": ["ticket:sev1-042", "product:example-product"],
            "occurred_at": "2026-06-25T15:00:00+00:00",
            "observed_at": at,
            "source_ids": ["source:support-042"],
            "record_ids": ["record:support-ticket-042"],
            "data": {"severity": "SEV-1", "state": "resolved"},
            "policy_id": CS,
            "created_by_run": run_id,
        },
        {
            "id": "event:usage-june",
            "event_type": "usage_observed",
            "subject_ids": ["subscription:example-product-test", "metric:weekly-active-sites"],
            "occurred_at": "2026-06-30T23:59:59+00:00",
            "observed_at": at,
            "source_ids": ["source:usage-june"],
            "record_ids": ["record:usage-june"],
            "data": {"window": "2026-06", "value": 37},
            "policy_id": CS,
            "created_by_run": run_id,
        },
    ]
    rows["evidence"] = [
        evidence("evidence:crm-validation", "structured_observation", ["source:crm-export-002"], ["record:crm-opportunity-002"], ["event:opportunity-validation"], "opportunity.stage", "CRM 商机阶段从 discovery 变更为 validation。", at, SALES, run_id),
        evidence("evidence:interview-correction", "interview_statement", ["source:interview-correction"], ["record:interview-correction"], [], "correction", "项目发起人撤回了此前关于集中采购的陈述。", at, SALES, run_id),
        evidence("evidence:contract-pricing", "contract_term", ["source:contract-001"], ["record:contract-term-001"], ["event:contract-signed"], "pricing", "已签署的年度付款义务包含定价标记 TEST_ONLY_CONTRACT_SENTINEL_VAULT。", at, EXEC, run_id),
        evidence("evidence:ticket-sev1", "ticket_observation", ["source:support-042"], ["record:support-ticket-042"], ["event:ticket-resolved-042"], "root_cause", "一次已解决的 SEV-1 故障转移事故包含标记 TEST_ONLY_TICKET_SENTINEL_CIRCUIT。", at, CS, run_id),
        evidence("evidence:usage-active-sites", "usage_aggregate", ["source:usage-june"], ["record:usage-june"], ["event:usage-june"], "metric:weekly-active-sites", "生产环境每周活跃站点为 37 个；质量标记为 TEST_ONLY_USAGE_SENTINEL_PULSE。", at, CS, run_id),
    ]
    rows["claims"] = [
        claim("claim:opportunity-stage-validation", "opportunity:example-security", "CommercialRelationship.opportunity_stage", "验证阶段（validation）", "observation", "commercial_relationship", "2026-06-30T12:00:00+00:00", at, ["evidence:crm-validation"], SALES, run_id, supersedes=["claim:opportunity-stage-discovery"]),
        claim("claim:procurement-statement-retracted", COMPANY, "CommercialRelationship.procurement_model", "已撤回此前关于集中采购的陈述", "statement", "commercial_relationship", "2026-06-15T10:00:00+00:00", at, ["evidence:interview-correction"], SALES, run_id, decision="retracted", supersedes=["claim:procurement-centralized"], conf=confidence("high", "single", "direct", "high")),
        claim("claim:contract-obligation", "contract:example-enterprise-001", "CommercialRelationship.annual_obligation", "USD 840000 / TEST_ONLY_CONTRACT_SENTINEL_VAULT", "obligation", "commercial_relationship", "2026-07-01T00:00:00+00:00", at, ["evidence:contract-pricing"], EXEC, run_id),
        claim("claim:sev1-observed", "product:example-product", "ProductUseService.continuity_incident", "已解决的 SEV-1 / TEST_ONLY_TICKET_SENTINEL_CIRCUIT", "observation", "product_use_service", "2026-06-25T09:00:00+00:00", at, ["evidence:ticket-sev1"], CS, run_id, contradicts=["claim:example-product-positioning-v1"], conf=confidence("high", "single", "direct", "high")),
        claim("claim:usage-active-sites", "subscription:example-product-test", "ProductUseService.weekly_active_sites", {"value": 37, "unit": "sites", "quality": "TEST_ONLY_USAGE_SENTINEL_PULSE"}, "metric", "product_use_service", "2026-06-01T00:00:00+00:00", at, ["evidence:usage-active-sites"], CS, run_id),
        claim("claim:usage-implies-satisfaction", COMPANY, "ProductUseService.satisfaction", "较高使用量可能意味着较高满意度", "hypothesis", "product_use_service", "2026-06-01T00:00:00+00:00", at, ["evidence:usage-active-sites"], CS, run_id, decision="proposed", conf=confidence("medium", "single", "speculative", "low")),
    ]
    rows["relations"] = [
        relation("relation:contract-party-example-company", "contract:example-enterprise-001", "party_to", "legal_entity:example-company-holdings", "2026-07-01T00:00:00+00:00", ["evidence:contract-pricing"], EXEC, run_id),
        relation("relation:subscription-uses-example-product", "subscription:example-product-test", "uses_product", "product:example-product", "2026-06-01T00:00:00+00:00", ["evidence:usage-active-sites"], CS, run_id),
    ]
    run = {
        "id": run_id,
        "company_id": COMPANY,
        "base_snapshot_id": "snapshot:example-company:002",
        "started_at": "2026-07-01T00:55:00+00:00",
        "completed_at": at,
        "mode": "incremental",
        "model": "fixture-distiller-v1",
        "prompt_version": "company-distiller-v2",
        "input_digest": "",
        "connector_cursors": {"crm": "cursor-002", "interview": "correction-001", "contract": "signed-v1", "support": "ticket-042", "usage": "2026-06"},
        "status": "completed",
        "result_snapshot_id": "snapshot:example-company:003",
    }
    write_bundle(root, run, rows)


def build(output: Path, force: bool) -> None:
    if output.exists():
        if not force:
            raise SystemExit(f"输出目录已存在：{output}；请传入 --force 覆盖")
        shutil.rmtree(output)
    bundles = output / "bundles"
    run_one(bundles / "run-001-public")
    run_two(bundles / "run-002-crm-interview")
    run_three(bundles / "run-003-contract-support-usage")
    workspace = output / "company-object"
    scaffold("Example Company (Synthetic)", "example-company", workspace, "2026-01-15")
    for bundle in sorted(bundles.iterdir()):
        apply_run(workspace, bundle)
    projections = output / "projections"
    for audience, purpose in AUDIENCE_PURPOSE.items():
        export_skill(workspace, projections / audience, audience, purpose)


def main() -> None:
    parser = argparse.ArgumentParser(description="构建可持续更新的公司对象示例。")
    parser.add_argument("--output", default="example/evolving-company", help="示例输出目录")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的输出目录")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    build(output, args.force)
    print(f"三次运行示例已构建：{output}")


if __name__ == "__main__":
    main()
