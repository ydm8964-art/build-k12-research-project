#!/usr/bin/env python3
"""Resolve and print the complete inherited format contract for one material."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from format_contracts import DEFAULT_CONTRACT_PATH, material_contract, validate_contract_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--material-id", required=True)
    parser.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--validate-catalog", action="store_true")
    args = parser.parse_args()
    try:
        if args.validate_catalog:
            errors = validate_contract_catalog(args.contracts)
            if errors:
                raise ValueError("；".join(errors))
        result = material_contract(args.material_id, args.contracts)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"版式合同解析失败：{exc}", file=sys.stderr)
        return 1
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
        print(args.out.resolve())
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
