#!/usr/bin/env python3
"""Run manifest, package, DOCX content/format, photo, and casebook audits in one pass."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from audit_casebook_integrity import audit as audit_casebook
from audit_content_integrity import audit as audit_content
from audit_docx_format import audit as audit_docx_format
from audit_lifecycle_coverage import audit as audit_lifecycle
from audit_photo_evidence import audit as audit_photo
from audit_project_package import READY_STATUSES
from audit_project_package import audit as audit_package
from audit_xlsx_structure import audit as audit_xlsx


def resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    raw = Path(str(value)).expanduser()
    return raw.resolve() if raw.is_absolute() else (root / raw).resolve()


def add_result(
    checks: list[dict],
    check: str,
    scope: str,
    errors: list[str],
    warnings: list[str],
    material_id: str | None = None,
) -> None:
    checks.append(
        {
            "check": check,
            "scope": scope,
            "material_id": material_id,
            "status": "failed" if errors else ("warning" if warnings else "passed"),
            "errors": errors,
            "warnings": warnings,
        }
    )


def run(manifest_path: Path, root: Path, final: bool) -> dict:
    manifest_path = manifest_path.resolve()
    root = root.resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks: list[dict] = []

    package_errors, package_warnings = audit_package(manifest_path, root, final)
    add_result(checks, "package", str(root), package_errors, package_warnings)

    lifecycle_errors, lifecycle_warnings = audit_lifecycle(data, final)
    add_result(checks, "lifecycle-coverage", str(manifest_path), lifecycle_errors, lifecycle_warnings)

    project_title = str(data.get("project", {}).get("title", "")).strip() or None
    forbidden = data.get("legacy_forbidden_terms", [])
    if not isinstance(forbidden, list):
        forbidden = []

    for item in data.get("materials", []):
        if not isinstance(item, dict) or item.get("status") not in READY_STATUSES:
            continue
        material_id = str(item.get("id", "未编号"))
        path = resolve_path(root, item.get("file_path"))
        if path is None or not path.is_file():
            continue

        if path.suffix.lower() == ".xlsx":
            required_sheets = item.get("required_sheets", [])
            if not isinstance(required_sheets, list):
                required_sheets = []
            allowed_hidden = item.get("allowed_hidden_sheets", [])
            if not isinstance(allowed_hidden, list):
                allowed_hidden = []
            try:
                errors, warnings = audit_xlsx(
                    path,
                    [str(value) for value in required_sheets],
                    [str(value) for value in allowed_hidden],
                    final,
                )
            except Exception as exc:
                errors, warnings = [f"审计执行失败：{exc}"], []
            add_result(checks, "xlsx-structure", str(path), errors, warnings, material_id)
            continue
        if path.suffix.lower() != ".docx":
            continue

        privacy = str(item.get("privacy_class", "internal"))
        mode = privacy if privacy in {"submission", "anonymous", "public"} else "working"
        try:
            errors, warnings = audit_content(path, mode, final, project_title, [str(value) for value in forbidden])
        except Exception as exc:
            errors, warnings = [f"审计执行失败：{exc}"], []
        add_result(checks, "docx-content", str(path), errors, warnings, material_id)

        profile = str(item.get("format_profile", ""))
        reference = resolve_path(root, item.get("reference_template"))
        if profile == "official-exact" and (reference is None or not reference.is_file()):
            errors, warnings = [f"official-exact参考模板不存在：{reference or '未登记'}"], []
        else:
            try:
                errors, warnings = audit_docx_format(path, profile, reference, final)
            except Exception as exc:
                errors, warnings = [f"审计执行失败：{exc}"], []
        add_result(checks, "docx-format", str(path), errors, warnings, material_id)

        if item.get("material_role") in {"case", "casebook"}:
            try:
                errors, warnings = audit_casebook(path, manifest_path, final)
            except Exception as exc:
                errors, warnings = [f"审计执行失败：{exc}"], []
            add_result(checks, "casebook-integrity", str(path), errors, warnings, material_id)

        if item.get("material_role") == "evidence-book" or item.get("photo_evidence_ids"):
            scope = "all-images" if item.get("material_role") == "evidence-book" else "registered-only"
            try:
                errors, warnings = audit_photo(path, manifest_path, mode, final, scope)
            except Exception as exc:
                errors, warnings = [f"审计执行失败：{exc}"], []
            add_result(checks, "photo-evidence", str(path), errors, warnings, material_id)

    error_count = sum(len(item["errors"]) for item in checks)
    warning_count = sum(len(item["warnings"]) for item in checks)
    strict_failure = bool(error_count or (final and warning_count))
    return {
        "schema_version": "1.1",
        "run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest": str(manifest_path),
        "root": str(root),
        "final": final,
        "status": "failed" if strict_failure else "passed",
        "error_count": error_count,
        "warning_count": warning_count,
        "checks": checks,
        "manual_gates": [
            "按当年官方通知核对报送系统、限额、命名、份数、签章和截止时间",
            "DOCX/PDF逐页渲染检查并更新目录、页码、题注和交叉引用",
            "XLSX逐工作表视觉检查、公式复算及Word/PDF数值回查",
            "照片真实性、人物授权/打码、学科事实、署名与签章人工复核",
            "打开00_课题材料包注意事项文件，逐条确认责任人、最迟时间、完成标准和已解决事项",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()
    try:
        report = run(args.manifest, args.root, args.final)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读取或预检失败：{exc}", file=sys.stderr)
        return 2

    for check in report["checks"]:
        prefix = f"{check['check']}[{check['material_id']}]" if check.get("material_id") else check["check"]
        for value in check["warnings"]:
            print(f"警告：{prefix}：{value}")
        for value in check["errors"]:
            print(f"错误：{prefix}：{value}")
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告：{args.report_json.resolve()}")
    if report["status"] == "failed":
        suffix = "；--final要求警告清零或先形成书面处置并消除对应机器警告" if args.final and report["warning_count"] else ""
        print(f"一键预检未通过：{report['error_count']}个错误，{report['warning_count']}个警告{suffix}")
        return 1
    print(f"一键预检通过：0个错误，{report['warning_count']}个警告；仍须完成人工门槛")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
