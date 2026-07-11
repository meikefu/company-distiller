#!/usr/bin/env python3
"""严格校验规范公司对象工作区。"""

from __future__ import annotations

import argparse
from pathlib import Path

from company_object_lib import ValidationFailure, load_workspace, validate_state


def validate_company_object(root: Path) -> list[str]:
    try:
        state = load_workspace(root)
    except (FileNotFoundError, ValueError, ValidationFailure) as exc:
        return [str(exc)]
    return validate_state(state, require_nonempty=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="校验规范公司对象工作区。")
    parser.add_argument("workspace", help="规范公司对象工作区")
    args = parser.parse_args()
    root = Path(args.workspace).resolve()
    errors = validate_company_object(root)
    if errors:
        print("公司对象校验失败：")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    state = load_workspace(root)
    print("公司对象校验通过。")
    print(f"运行数：{len(state['runs'])}")
    print(f"快照数：{len(state['snapshots'])}")
    print(f"主张数：{len(state['claims'])}")
    print(f"当前快照：{state['manifest']['current_snapshot_id']}")


if __name__ == "__main__":
    main()
