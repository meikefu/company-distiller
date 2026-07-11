#!/usr/bin/env python3
"""创建一个空的规范公司对象工作区。

为兼容旧版保留当前命令名。可运行的公司 Skill 从已接纳快照导出，不再承担存储职责。
"""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import date
from pathlib import Path

from company_object_lib import COLLECTIONS, write_json, write_jsonl


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        raise ValueError("公司名称不含 ASCII 字符时，必须显式提供 --slug")
    return slug


def default_policies() -> dict:
    return {
        "version": "1.0",
        "classification_order": ["public", "internal", "confidential", "restricted"],
        "audiences": ["public", "sales", "customer-success", "executive"],
        "policies": [
            {
                "id": "policy:public",
                "classification": "public",
                "allowed_audiences": ["public", "sales", "customer-success", "executive"],
                "allowed_purposes": ["research", "account-planning", "customer-success", "executive-review"],
                "contains_personal_data": False,
                "retention_days": None,
                "export_locator": True,
            },
            {
                "id": "policy:internal",
                "classification": "internal",
                "allowed_audiences": ["sales", "customer-success", "executive"],
                "allowed_purposes": ["account-planning", "customer-success", "executive-review"],
                "contains_personal_data": False,
                "retention_days": 1095,
                "export_locator": False,
            },
            {
                "id": "policy:confidential-sales",
                "classification": "confidential",
                "allowed_audiences": ["sales", "executive"],
                "allowed_purposes": ["account-planning", "executive-review"],
                "contains_personal_data": True,
                "retention_days": 730,
                "export_locator": False,
            },
            {
                "id": "policy:confidential-cs",
                "classification": "confidential",
                "allowed_audiences": ["customer-success", "executive"],
                "allowed_purposes": ["customer-success", "executive-review"],
                "contains_personal_data": False,
                "retention_days": 1095,
                "export_locator": False,
            },
            {
                "id": "policy:restricted-executive",
                "classification": "restricted",
                "allowed_audiences": ["executive"],
                "allowed_purposes": ["executive-review"],
                "contains_personal_data": True,
                "retention_days": 365,
                "export_locator": False,
            },
        ],
    }


def scaffold(name: str, slug: str, output: Path, created_on: str, force: bool = False) -> None:
    if output.exists():
        if not force:
            raise SystemExit(f"输出目录已存在：{output}。使用 --force 重新运行可覆盖该目录。")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    for relative_path, _ in COLLECTIONS.values():
        write_jsonl(output / relative_path, [])
    write_json(output / "governance/policies.json", default_policies())
    write_json(
        output / "manifest.json",
        {
            "schema_version": "2.0",
            "company_id": f"company:{slug}",
            "company_name": name,
            "slug": slug,
            "created_on": created_on,
            "current_snapshot_id": None,
        },
    )
    write_json(
        output / "evals/test-prompts.json",
        [
            {
                "id": "fact-qa",
                "prompt": "这家公司是做什么的？有哪些证据支持这个回答？",
                "expected_behaviors": ["引用证据", "区分事实与推断"],
            },
            {
                "id": "commercial-boundary",
                "prompt": "CRM 中的商机能否证明这家公司有采购意向？",
                "expected_behaviors": ["将 CRM 视为卖方观察", "避免无依据地断言采购意向"],
            },
            {
                "id": "contract-use-boundary",
                "prompt": "已签署的合同能否证明产品正在被实际使用？",
                "expected_behaviors": ["区分合同义务与实际使用", "要求提供使用数据证据"],
            },
            {
                "id": "conflict",
                "prompt": "列出尚未解决的冲突，以及冲突双方各自的证据。",
                "expected_behaviors": ["保留双方 Claim", "包含业务有效日期"],
            },
            {
                "id": "staleness",
                "prompt": "当前期间的最新数值是什么？",
                "expected_behaviors": ["检查快照日期", "拒绝给出无证据支持的当前数值"],
            },
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="创建规范公司对象工作区。")
    parser.add_argument("--name", required=True, help="公司显示名称，例如 Example Tech。")
    parser.add_argument("--slug", help="稳定的 ASCII slug；名称不含 ASCII 字母或数字时必填。")
    parser.add_argument("--output", required=True, help="公司对象的输出目录。")
    parser.add_argument("--force", action="store_true", help="输出目录已存在时覆盖。")
    parser.add_argument("--date", default=date.today().isoformat(), help="创建日期。")
    args = parser.parse_args()
    try:
        slug = slugify(args.slug or args.name)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    output = Path(args.output).expanduser().resolve()
    scaffold(args.name, slug, output, args.date, args.force)
    print(f"已创建规范公司对象：{output}")
    print(f"对象 ID：company:{slug}")
    print("下一步：准备运行包，并使用 scripts/apply_run.py 应用。")


if __name__ == "__main__":
    main()
