#!/usr/bin/env python3
"""Build reproducible public-source run bundles for BYD Company Limited."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from company_object_lib import BUNDLE_COLLECTIONS, write_json, write_jsonl


PUBLIC = "policy:public"
COMPANY = "company:byd"
LEGAL = "legal:byd-company-limited"
RUN_001 = "run:byd:001"
RUN_002 = "run:byd:002"


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def confidence(corroboration: str = "single", strength: str = "direct", overall: str = "high") -> dict:
    return {
        "source_reliability": "high",
        "corroboration": corroboration,
        "inference_strength": strength,
        "overall": overall,
    }


def entity(item_id: str, entity_type: str, name: str, run_id: str, parent_id: str | None = None) -> dict:
    return {
        "id": item_id,
        "entity_type": entity_type,
        "name": name,
        "aliases": [],
        "parent_id": parent_id,
        "scope": "company",
        "external_ids": {},
        "policy_id": PUBLIC,
        "created_by_run": run_id,
    }


def public_record(
    item_id: str,
    source_id: str,
    subject_ids: list[str],
    observed_at: str,
    valid_from: str,
    valid_to: str | None,
    fact_name: str,
    value,
    run_id: str,
) -> dict:
    return {
        "id": item_id,
        "record_type": "public_fact",
        "source_id": source_id,
        "subject_ids": subject_ids,
        "observed_at": observed_at,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "data": {"fact_name": fact_name, "value": value},
        "policy_id": PUBLIC,
        "created_by_run": run_id,
    }


def evidence(
    item_id: str,
    source_ids: list[str],
    record_ids: list[str],
    event_ids: list[str],
    locator: str,
    excerpt: str,
    observed_at: str,
    run_id: str,
) -> dict:
    return {
        "id": item_id,
        "evidence_type": "document_excerpt",
        "source_ids": source_ids,
        "record_ids": record_ids,
        "event_ids": event_ids,
        "locator": locator,
        "excerpt": excerpt,
        "observed_at": observed_at,
        "policy_id": PUBLIC,
        "derived_from": [],
        "created_by_run": run_id,
    }


def claim(
    item_id: str,
    subject_id: str,
    predicate: str,
    value,
    claim_type: str,
    valid_from: str,
    valid_to: str | None,
    observed_at: str,
    evidence_ids: list[str],
    run_id: str,
    corroboration: str = "single",
) -> dict:
    return {
        "id": item_id,
        "subject_id": subject_id,
        "predicate": predicate,
        "value": value,
        "claim_type": claim_type,
        "scope": "company",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "observed_at": observed_at,
        "evidence_ids": evidence_ids,
        "decision": "accepted",
        "confidence": confidence(corroboration=corroboration),
        "supersedes": [],
        "contradicts": [],
        "policy_id": PUBLIC,
        "created_by_run": run_id,
    }


def relation(
    item_id: str,
    subject_id: str,
    predicate: str,
    object_id: str,
    context: str,
    valid_from: str,
    observed_at: str,
    evidence_ids: list[str],
    run_id: str,
) -> dict:
    return {
        "id": item_id,
        "subject_id": subject_id,
        "predicate": predicate,
        "object_id": object_id,
        "context": context,
        "valid_from": valid_from,
        "valid_to": None,
        "observed_at": observed_at,
        "evidence_ids": evidence_ids,
        "confidence": "high",
        "policy_id": PUBLIC,
        "created_by_run": run_id,
    }


def empty_bundle(bundle: Path) -> None:
    bundle.mkdir(parents=True, exist_ok=True)
    for _, (filename, _) in BUNDLE_COLLECTIONS.items():
        write_jsonl(bundle / filename, [])


def build_foundation(bundle: Path, raw: Path) -> None:
    annual_report = raw / "byd-2025-annual-report.pdf"
    about_page = raw / "byd-about-2026-08-16.html"
    for path in (annual_report, about_page):
        if not path.is_file():
            raise FileNotFoundError(path)

    observed = "2026-08-16T09:00:00+08:00"
    fiscal_start = "2025-01-01T00:00:00+08:00"
    fiscal_end = "2025-12-31T23:59:59+08:00"
    report_state_date = "2025-12-31T23:59:59+08:00"
    report_source = "source:byd-2025-annual-report"
    web_source = "source:byd-about-20260816"
    report_event = "event:byd-2025-annual-report-published"

    empty_bundle(bundle)
    entities = [
        entity(COMPANY, "company", "比亚迪", RUN_001),
        {
            **entity(LEGAL, "legal_entity", "比亚迪股份有限公司", RUN_001, COMPANY),
            "aliases": ["BYD Company Limited", "比亞迪股份有限公司"],
            "external_ids": {"HKEX_HKD": "01211", "HKEX_RMB": "81211", "SZSE": "002594"},
        },
        entity("unit:byd-auto-battery", "business_unit", "汽车及电池业务", RUN_001, COMPANY),
        entity("unit:byd-handset-assembly", "business_unit", "手机部件及组装业务", RUN_001, COMPANY),
        entity("unit:byd-rail-transit", "business_unit", "城市轨道交通业务", RUN_001, COMPANY),
        entity("product:byd-blade-battery", "product", "刀片电池", RUN_001, "unit:byd-auto-battery"),
        entity("market:global-nev", "market", "全球新能源汽车市场", RUN_001),
    ]
    sources = [
        {
            "id": report_source,
            "source_type": "annual_report",
            "title": "BYD Company Limited 2025 Annual Report",
            "source_date": "2026-03-27T21:40:00+08:00",
            "observed_at": observed,
            "content_hash": file_hash(annual_report),
            "connector": "https-download",
            "external_id": "HKEX:2026032703008",
            "version": "2025-annual-report-released-2026-03-27",
            "locator": "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0327/2026032703008.pdf",
            "policy_id": PUBLIC,
            "created_by_run": RUN_001,
        },
        {
            "id": web_source,
            "source_type": "official_website",
            "title": "About BYD | BYD AUTO",
            "source_date": observed,
            "observed_at": observed,
            "content_hash": file_hash(about_page),
            "connector": "https-download",
            "external_id": "BYD-WEB:about-byd",
            "version": "snapshot-2026-08-16",
            "locator": "https://www.byd.com/sc/about-byd",
            "policy_id": PUBLIC,
            "created_by_run": RUN_001,
        },
    ]
    records = [
        public_record(
            "record:byd-2025-company-profile", report_source,
            [COMPANY, LEGAL, "unit:byd-auto-battery", "unit:byd-handset-assembly", "unit:byd-rail-transit"],
            observed, report_state_date, None, "principal_activities",
            ["new_energy_vehicles", "handset_components_and_assembly", "rechargeable_batteries_and_photovoltaics", "urban_rail_transportation"], RUN_001,
        ),
        public_record(
            "record:byd-2025-financial-highlights", report_source, [COMPANY, LEGAL], observed,
            fiscal_start, fiscal_end, "financial_highlights",
            {"revenue_rmb": 803964958000, "profit_attributable_rmb": 32619022000, "total_assets_rmb": 883729883000, "rd_expense_rmb": 57978105000, "audit_status": "audited"}, RUN_001,
        ),
        public_record(
            "record:byd-2025-segment-revenue", report_source,
            [COMPANY, "unit:byd-auto-battery", "unit:byd-handset-assembly"], observed,
            fiscal_start, fiscal_end, "external_revenue_by_segment",
            {"automobiles_and_related_products_rmb": 648645636000, "handset_components_assembly_and_other_rmb": 155236528000, "audit_status": "audited"}, RUN_001,
        ),
        public_record(
            "record:byd-2025-geographic-revenue", report_source, [COMPANY], observed,
            fiscal_start, fiscal_end, "external_revenue_by_geography",
            {"prc_including_hk_macao_taiwan_rmb": 493223970000, "overseas_rmb": 310740988000, "audit_status": "audited"}, RUN_001,
        ),
        public_record(
            "record:byd-web-technology-profile", web_source,
            [COMPANY, "unit:byd-auto-battery", "product:byd-blade-battery"], observed,
            observed, None, "technology_profile",
            {"technologies": ["Blade Battery", "dual-mode hybrid power technology"]}, RUN_001,
        ),
    ]
    events = [
        {
            "id": report_event,
            "event_type": "company_update",
            "subject_ids": [COMPANY, LEGAL],
            "occurred_at": "2026-03-27T21:40:00+08:00",
            "observed_at": observed,
            "source_ids": [report_source],
            "record_ids": [
                "record:byd-2025-company-profile",
                "record:byd-2025-financial-highlights",
                "record:byd-2025-segment-revenue",
                "record:byd-2025-geographic-revenue",
            ],
            "data": {"event": "2025_annual_report_published", "exchange": "HKEX"},
            "policy_id": PUBLIC,
            "created_by_run": RUN_001,
        }
    ]
    evidence_rows = [
        evidence(
            "evidence:byd-2025-ar-profile-p2", [report_source], ["record:byd-2025-company-profile"], [report_event],
            "PDF page 2, company overview", "年报将集团主要业务界定为新能源汽车、手机部件及组装、充电电池与光伏，并说明集团拓展城市轨道交通。", observed, RUN_001,
        ),
        evidence(
            "evidence:byd-2025-ar-financials-p5", [report_source], ["record:byd-2025-financial-highlights"], [report_event],
            "PDF page 5, Financial Highlights", "2025 年营业额为人民币 803,964,958 千元，母公司拥有人应占溢利为 32,619,022 千元，总资产为 883,729,883 千元。", observed, RUN_001,
        ),
        evidence(
            "evidence:byd-2025-ar-rd-p368", [report_source], ["record:byd-2025-financial-highlights"], [report_event],
            "PDF page 368, Five Year Financial Summary", "2025 年财务报表列示研发费用为人民币 57,978,105 千元。", observed, RUN_001,
        ),
        evidence(
            "evidence:byd-2025-ar-segments-p347", [report_source], ["record:byd-2025-segment-revenue"], [report_event],
            "PDF page 347, segment reporting", "2025 年汽车及相关产品对外收入为人民币 648,645,636 千元，手机部件、组装及其他产品为 155,236,528 千元。", observed, RUN_001,
        ),
        evidence(
            "evidence:byd-2025-ar-geography-p349", [report_source], ["record:byd-2025-geographic-revenue"], [report_event],
            "PDF page 349, geographical information", "2025 年中国地区对外收入为人民币 493,223,970 千元，境外对外收入为 310,740,988 千元。", observed, RUN_001,
        ),
        evidence(
            "evidence:byd-web-about-listing", [web_source, report_source], ["record:byd-web-technology-profile", "record:byd-2025-company-profile"], [report_event],
            "Official About BYD page and annual report page 2", "官网与年报共同表明比亚迪在香港和深圳证券交易所上市；年报列示 H 股及 A 股代码。", observed, RUN_001,
        ),
        evidence(
            "evidence:byd-web-blade-battery", [web_source], ["record:byd-web-technology-profile"], [],
            "Official About BYD page, Auto / Blade Battery section", "比亚迪官网将刀片电池与双模混动技术列为其汽车领域技术。", observed, RUN_001,
        ),
    ]
    claims = [
        claim(
            "claim:byd-legal-identity-2025", LEGAL, "legalIdentity",
            {"name": "比亚迪股份有限公司", "jurisdiction": "PRC", "legal_form": "joint_stock_company_with_limited_liability"},
            "fact", report_state_date, None, observed, ["evidence:byd-2025-ar-profile-p2"], RUN_001,
        ),
        claim(
            "claim:byd-listings-2025", LEGAL, "exchangeListings",
            [{"exchange": "HKEX", "codes": ["01211", "81211"]}, {"exchange": "SZSE", "code": "002594"}],
            "fact", report_state_date, None, observed, ["evidence:byd-web-about-listing"], RUN_001, "multiple",
        ),
        claim(
            "claim:byd-principal-activities-2025", COMPANY, "principalActivities",
            ["new_energy_vehicles", "handset_components_and_assembly", "rechargeable_batteries_and_photovoltaics", "urban_rail_transportation"],
            "fact", report_state_date, None, observed, ["evidence:byd-2025-ar-profile-p2"], RUN_001,
        ),
        claim(
            "claim:byd-revenue-fy2025", COMPANY, "revenue",
            {"amount": 803964958000, "currency": "CNY", "period": "FY2025", "basis": "consolidated_audited"},
            "metric", fiscal_start, fiscal_end, observed, ["evidence:byd-2025-ar-financials-p5"], RUN_001,
        ),
        claim(
            "claim:byd-profit-attributable-fy2025", COMPANY, "profitAttributableToOwners",
            {"amount": 32619022000, "currency": "CNY", "period": "FY2025", "basis": "consolidated_audited"},
            "metric", fiscal_start, fiscal_end, observed, ["evidence:byd-2025-ar-financials-p5"], RUN_001,
        ),
        claim(
            "claim:byd-total-assets-2025", COMPANY, "totalAssets",
            {"amount": 883729883000, "currency": "CNY", "as_of": "2025-12-31", "basis": "consolidated_audited"},
            "metric", report_state_date, report_state_date, observed, ["evidence:byd-2025-ar-financials-p5"], RUN_001,
        ),
        claim(
            "claim:byd-rd-expense-fy2025", COMPANY, "researchAndDevelopmentExpense",
            {"amount": 57978105000, "currency": "CNY", "period": "FY2025", "basis": "financial_statement_expense"},
            "metric", fiscal_start, fiscal_end, observed, ["evidence:byd-2025-ar-rd-p368"], RUN_001,
        ),
        claim(
            "claim:byd-auto-segment-revenue-fy2025", "unit:byd-auto-battery", "externalRevenue",
            {"amount": 648645636000, "currency": "CNY", "period": "FY2025", "basis": "segment_external_trading"},
            "metric", fiscal_start, fiscal_end, observed, ["evidence:byd-2025-ar-segments-p347"], RUN_001,
        ),
        claim(
            "claim:byd-handset-segment-revenue-fy2025", "unit:byd-handset-assembly", "externalRevenue",
            {"amount": 155236528000, "currency": "CNY", "period": "FY2025", "basis": "segment_external_trading"},
            "metric", fiscal_start, fiscal_end, observed, ["evidence:byd-2025-ar-segments-p347"], RUN_001,
        ),
        claim(
            "claim:byd-overseas-revenue-fy2025", COMPANY, "overseasExternalRevenue",
            {"amount": 310740988000, "currency": "CNY", "period": "FY2025", "basis": "customer_location"},
            "metric", fiscal_start, fiscal_end, observed, ["evidence:byd-2025-ar-geography-p349"], RUN_001,
        ),
        claim(
            "claim:byd-prc-revenue-fy2025", COMPANY, "prcExternalRevenue",
            {"amount": 493223970000, "currency": "CNY", "period": "FY2025", "basis": "customer_location_including_hk_macao_taiwan"},
            "metric", fiscal_start, fiscal_end, observed, ["evidence:byd-2025-ar-geography-p349"], RUN_001,
        ),
        claim(
            "claim:byd-blade-battery-offering-2026", "product:byd-blade-battery", "technologyCategory",
            "lithium_iron_phosphate_power_battery", "fact", observed, None, observed,
            ["evidence:byd-web-blade-battery"], RUN_001,
        ),
    ]
    relations = [
        relation("relation:byd-contains-legal", COMPANY, "contains", LEGAL, "Consolidated company boundary", report_state_date, observed, ["evidence:byd-2025-ar-profile-p2"], RUN_001),
        relation("relation:byd-contains-auto-battery", COMPANY, "contains", "unit:byd-auto-battery", "Principal business boundary", report_state_date, observed, ["evidence:byd-2025-ar-profile-p2"], RUN_001),
        relation("relation:byd-contains-handset", COMPANY, "contains", "unit:byd-handset-assembly", "Principal business boundary", report_state_date, observed, ["evidence:byd-2025-ar-profile-p2"], RUN_001),
        relation("relation:byd-contains-rail", COMPANY, "contains", "unit:byd-rail-transit", "Developing business segment", report_state_date, observed, ["evidence:byd-2025-ar-profile-p2"], RUN_001),
        relation("relation:byd-auto-offers-blade", "unit:byd-auto-battery", "offers", "product:byd-blade-battery", "Automotive battery technology", observed, observed, ["evidence:byd-web-blade-battery"], RUN_001),
        relation("relation:byd-targets-global-nev", COMPANY, "targets_market", "market:global-nev", "Company positioning in the global NEV market", report_state_date, observed, ["evidence:byd-2025-ar-profile-p2"], RUN_001),
    ]
    for filename, rows in {
        "entities.jsonl": entities,
        "sources.jsonl": sources,
        "records.jsonl": records,
        "events.jsonl": events,
        "evidence.jsonl": evidence_rows,
        "claims.jsonl": claims,
        "relations.jsonl": relations,
    }.items():
        write_jsonl(bundle / filename, rows)
    write_json(
        bundle / "run.json",
        {
            "id": RUN_001,
            "company_id": COMPANY,
            "base_snapshot_id": None,
            "started_at": "2026-08-16T09:00:00+08:00",
            "completed_at": "2026-08-16T09:05:00+08:00",
            "mode": "initial",
            "model": "openai-codex-agent",
            "prompt_version": "company-distiller-v2",
            "input_digest": "",
            "connector_cursors": {"hkex": "2026032703008", "byd-web": "snapshot-2026-08-16"},
            "status": "completed",
            "result_snapshot_id": "snapshot:byd:001",
        },
    )


def build_july_update(bundle: Path, raw: Path) -> None:
    sales_report = raw / "byd-july-2026-production-sales.pdf"
    if not sales_report.is_file():
        raise FileNotFoundError(sales_report)

    observed = "2026-08-16T09:10:00+08:00"
    period_start = "2026-01-01T00:00:00+08:00"
    period_end = "2026-07-31T23:59:59+08:00"
    july_start = "2026-07-01T00:00:00+08:00"
    july_end = period_end
    source_id = "source:byd-2026-07-production-sales"
    record_id = "record:byd-2026-07-production-sales"
    event_id = "event:byd-2026-07-sales-update"

    empty_bundle(bundle)
    sources = [
        {
            "id": source_id,
            "source_type": "regulatory",
            "title": "BYD Production and Sales Volume for July 2026",
            "source_date": "2026-08-02T00:00:00+08:00",
            "observed_at": observed,
            "content_hash": file_hash(sales_report),
            "connector": "https-download",
            "external_id": "HKEX:2026080200027",
            "version": "published-2026-08-02",
            "locator": "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0802/2026080200027.pdf",
            "policy_id": PUBLIC,
            "created_by_run": RUN_002,
        }
    ]
    records = [
        public_record(
            record_id, source_id, [COMPANY, "unit:byd-auto-battery"], observed, period_start, period_end,
            "production_and_sales_volume",
            {
                "period": "2026-01-01/2026-07-31",
                "new_energy_vehicle": {
                    "july_sales_units": 419211,
                    "ytd_sales_units": 2227722,
                    "ytd_sales_yoy_percent": -10.54,
                    "ytd_bev_sales_units": 1100584,
                    "ytd_phev_sales_units": 1087863,
                    "july_export_units": 180538,
                },
                "audit_status": "unaudited_subject_to_adjustment",
            }, RUN_002,
        )
    ]
    events = [
        {
            "id": event_id,
            "event_type": "company_update",
            "subject_ids": [COMPANY, "unit:byd-auto-battery"],
            "occurred_at": "2026-08-02T00:00:00+08:00",
            "observed_at": observed,
            "source_ids": [source_id],
            "record_ids": [record_id],
            "data": {"event": "july_2026_production_sales_announced", "audit_status": "unaudited"},
            "policy_id": PUBLIC,
            "created_by_run": RUN_002,
        }
    ]
    evidence_rows = [
        evidence(
            "evidence:byd-2026-07-sales-table-p1", [source_id], [record_id], [event_id],
            "PDF page 1, production and sales table", "公告列示 2026 年 7 月新能源汽车销量 419,211 辆，1-7 月累计销量 2,227,722 辆，同比下降 10.54%。", observed, RUN_002,
        ),
        evidence(
            "evidence:byd-2026-07-powertrain-table-p1", [source_id], [record_id], [event_id],
            "PDF page 1, BEV and PHEV rows", "公告列示 2026 年 1-7 月纯电动乘用车销量 1,100,584 辆，插电式混合动力乘用车销量 1,087,863 辆。", observed, RUN_002,
        ),
        evidence(
            "evidence:byd-2026-07-export-note-p2", [source_id], [record_id], [event_id],
            "PDF page 2, note", "公告附注列示 2026 年 7 月新能源汽车出口量为 180,538 辆，并注明全部产销数据未经审计、可能调整。", observed, RUN_002,
        ),
    ]
    claims = [
        claim(
            "claim:byd-nev-sales-july-2026", "unit:byd-auto-battery", "newEnergyVehicleSales",
            {"amount": 419211, "unit": "vehicles", "period": "2026-07", "audit_status": "unaudited_subject_to_adjustment"},
            "metric", july_start, july_end, observed, ["evidence:byd-2026-07-sales-table-p1"], RUN_002,
        ),
        claim(
            "claim:byd-nev-sales-ytd-july-2026", "unit:byd-auto-battery", "newEnergyVehicleSales",
            {"amount": 2227722, "unit": "vehicles", "period": "2026-01-01/2026-07-31", "audit_status": "unaudited_subject_to_adjustment"},
            "metric", period_start, period_end, observed, ["evidence:byd-2026-07-sales-table-p1"], RUN_002,
        ),
        claim(
            "claim:byd-nev-sales-yoy-ytd-july-2026", "unit:byd-auto-battery", "newEnergyVehicleSalesYoY",
            {"amount": -10.54, "unit": "percent", "period": "2026-01-01/2026-07-31", "audit_status": "unaudited_subject_to_adjustment"},
            "metric", period_start, period_end, observed, ["evidence:byd-2026-07-sales-table-p1"], RUN_002,
        ),
        claim(
            "claim:byd-bev-sales-ytd-july-2026", "unit:byd-auto-battery", "batteryElectricPassengerVehicleSales",
            {"amount": 1100584, "unit": "vehicles", "period": "2026-01-01/2026-07-31", "audit_status": "unaudited_subject_to_adjustment"},
            "metric", period_start, period_end, observed, ["evidence:byd-2026-07-powertrain-table-p1"], RUN_002,
        ),
        claim(
            "claim:byd-phev-sales-ytd-july-2026", "unit:byd-auto-battery", "plugInHybridPassengerVehicleSales",
            {"amount": 1087863, "unit": "vehicles", "period": "2026-01-01/2026-07-31", "audit_status": "unaudited_subject_to_adjustment"},
            "metric", period_start, period_end, observed, ["evidence:byd-2026-07-powertrain-table-p1"], RUN_002,
        ),
        claim(
            "claim:byd-nev-exports-july-2026", "unit:byd-auto-battery", "newEnergyVehicleExports",
            {"amount": 180538, "unit": "vehicles", "period": "2026-07", "audit_status": "unaudited_subject_to_adjustment"},
            "metric", july_start, july_end, observed, ["evidence:byd-2026-07-export-note-p2"], RUN_002,
        ),
    ]
    for filename, rows in {
        "entities.jsonl": [],
        "sources.jsonl": sources,
        "records.jsonl": records,
        "events.jsonl": events,
        "evidence.jsonl": evidence_rows,
        "claims.jsonl": claims,
        "relations.jsonl": [],
    }.items():
        write_jsonl(bundle / filename, rows)
    write_json(
        bundle / "run.json",
        {
            "id": RUN_002,
            "company_id": COMPANY,
            "base_snapshot_id": "snapshot:byd:001",
            "started_at": "2026-08-16T09:10:00+08:00",
            "completed_at": "2026-08-16T09:15:00+08:00",
            "mode": "incremental",
            "model": "openai-codex-agent",
            "prompt_version": "company-distiller-v2",
            "input_digest": "",
            "connector_cursors": {"hkex": "2026080200027"},
            "status": "completed",
            "result_snapshot_id": "snapshot:byd:002",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build BYD public-source run bundles.")
    parser.add_argument("--raw", default="./byd-research/raw", help="Directory containing immutable source snapshots.")
    parser.add_argument("--output", default="./byd-bundles", help="Output directory for run bundles.")
    args = parser.parse_args()
    raw = Path(args.raw).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    build_foundation(output / "run-001-public-foundation", raw)
    build_july_update(output / "run-002-july-2026-sales", raw)
    print(f"Built BYD bundles under: {output}")
    print("Next: run update_bundle_digest.py for each bundle before apply_run.py.")


if __name__ == "__main__":
    main()
