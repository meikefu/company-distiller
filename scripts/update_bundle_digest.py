#!/usr/bin/env python3
"""设置运行包的确定性输入摘要。"""

from __future__ import annotations

import argparse
from pathlib import Path

from company_object_lib import bundle_digest, read_json, write_json


def update_digest(bundle: Path) -> str:
    run_path = bundle / "run.json"
    run = read_json(run_path)
    digest = bundle_digest(bundle)
    run["input_digest"] = digest
    write_json(run_path, run)
    return digest


def main() -> None:
    parser = argparse.ArgumentParser(description="更新运行包的输入摘要。")
    parser.add_argument("bundle", help="运行包目录")
    args = parser.parse_args()
    digest = update_digest(Path(args.bundle).resolve())
    print(digest)


if __name__ == "__main__":
    main()
