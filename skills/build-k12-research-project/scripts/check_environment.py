#!/usr/bin/env python3
"""Check portable runtime prerequisites for the K-12 research-project skill."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import sys

MIN_PYTHON = (3, 10)
REQUIRED_MODULES = {"docx": "python-docx"}
OPTIONAL_MODULES = {"PIL": "Pillow", "pypdf": "pypdf"}


def check() -> dict:
    required_missing = [package for module, package in REQUIRED_MODULES.items() if importlib.util.find_spec(module) is None]
    optional_missing = [package for module, package in OPTIONAL_MODULES.items() if importlib.util.find_spec(module) is None]
    office = shutil.which("libreoffice") or shutil.which("soffice")
    python_ok = sys.version_info >= MIN_PYTHON
    return {
        "status": "ready" if python_ok and not required_missing else "blocked",
        "python": platform.python_version(),
        "python_ok": python_ok,
        "required_missing": required_missing,
        "optional_missing": optional_missing,
        "libreoffice": office,
        "capabilities": {
            "docx_generation_and_audit": python_ok and not required_missing,
            "image_metadata_audit": "Pillow" not in optional_missing,
            "pdf_text_audit": "pypdf" not in optional_missing,
            "office_rendering": bool(office),
            "xlsx_generation": "由Agent的电子表格运行时提供；此脚本不把Node模块设为全局前提",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="输出机器可读JSON")
    args = parser.parse_args()
    report = check()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Python {report['python']}：{'通过' if report['python_ok'] else '低于3.10'}")
        print(f"必需依赖：{'通过' if not report['required_missing'] else '缺少 ' + ', '.join(report['required_missing'])}")
        print(f"可选依赖：{'通过' if not report['optional_missing'] else '缺少 ' + ', '.join(report['optional_missing'])}")
        print(f"LibreOffice：{report['libreoffice'] or '未发现；无法完成Office渲染复核'}")
        print(f"环境状态：{report['status']}")
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
