#!/usr/bin/env python3
"""Create an empty, correctly named Company Distiller run bundle."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from company_object_lib import BUNDLE_COLLECTIONS, write_json, write_jsonl


def default_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def scaffold_bundle(
    output: Path,
    run_id: str,
    company_id: str,
    result_snapshot_id: str,
    mode: str,
    base_snapshot_id: str | None,
    started_at: str,
    completed_at: str,
    model: str,
    prompt_version: str,
    force: bool = False,
) -> None:
    if output.exists():
        if not force:
            raise SystemExit(f"输出目录已存在：{output}。使用 --force 重新创建。")
        for path in sorted(output.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    output.mkdir(parents=True, exist_ok=True)
    for _, (filename, _) in BUNDLE_COLLECTIONS.items():
        write_jsonl(output / filename, [])
    write_json(
        output / "run.json",
        {
            "id": run_id,
            "company_id": company_id,
            "base_snapshot_id": base_snapshot_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "mode": mode,
            "model": model,
            "prompt_version": prompt_version,
            "input_digest": "",
            "connector_cursors": {},
            "status": "completed",
            "result_snapshot_id": result_snapshot_id,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="创建空的 Company Distiller 运行包骨架。")
    parser.add_argument("--output", required=True, help="运行包目录")
    parser.add_argument("--run-id", required=True, help="本次运行 ID，例如 run:example-tech:001")
    parser.add_argument("--company-id", required=True, help="公司实体 ID，例如 company:example-tech")
    parser.add_argument("--result-snapshot-id", required=True, help="成功后生成的快照 ID")
    parser.add_argument("--mode", choices=["initial", "incremental", "rebuild"], required=True)
    parser.add_argument("--base-snapshot-id", help="增量运行的当前快照 ID；初始运行留空")
    parser.add_argument("--started-at", default=default_timestamp(), help="带时区的 ISO 8601 时间")
    parser.add_argument("--completed-at", default=default_timestamp(), help="带时区的 ISO 8601 时间")
    parser.add_argument("--model", default="manual-curation", help="抽取/审核模型或流程标识")
    parser.add_argument("--prompt-version", default="company-distiller-v2")
    parser.add_argument("--force", action="store_true", help="输出目录存在时重建")
    args = parser.parse_args()
    if args.mode == "initial" and args.base_snapshot_id:
        raise SystemExit("initial 运行不应设置 --base-snapshot-id")
    if args.mode == "incremental" and not args.base_snapshot_id:
        raise SystemExit("incremental 运行必须设置 --base-snapshot-id")
    scaffold_bundle(
        Path(args.output).expanduser().resolve(),
        args.run_id,
        args.company_id,
        args.result_snapshot_id,
        args.mode,
        args.base_snapshot_id,
        args.started_at,
        args.completed_at,
        args.model,
        args.prompt_version,
        args.force,
    )
    print(f"已创建运行包骨架：{Path(args.output).expanduser().resolve()}")
    print("下一步：填写 entities.jsonl、sources.jsonl、records.jsonl、events.jsonl、evidence.jsonl、claims.jsonl 和 relations.jsonl。")
    print("填写完成后再运行 scripts/update_bundle_digest.py。")


if __name__ == "__main__":
    main()
