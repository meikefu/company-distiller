#!/usr/bin/env python3
"""设置运行包的确定性输入摘要。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from company_object_lib import bundle_digest, read_json, write_json


def update_digest(bundle: Path, complete_now: bool = False) -> str:
    run_path = bundle / "run.json"
    run = read_json(run_path)
    if complete_now:
        run["completed_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        write_json(run_path, run)
    digest = bundle_digest(bundle)
    run["input_digest"] = digest
    write_json(run_path, run)
    return digest


def main() -> None:
    parser = argparse.ArgumentParser(description="更新运行包的输入摘要。")
    parser.add_argument("bundle", help="运行包目录")
    parser.add_argument(
        "--complete-now",
        action="store_true",
        help="先把 run.completed_at 更新为当前 UTC 时间，再计算摘要；适合手工填完 bundle 后使用。",
    )
    args = parser.parse_args()
    digest = update_digest(Path(args.bundle).resolve(), complete_now=args.complete_now)
    print(digest)


if __name__ == "__main__":
    main()
