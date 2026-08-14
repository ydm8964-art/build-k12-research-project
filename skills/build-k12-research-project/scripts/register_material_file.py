#!/usr/bin/env python3
"""Register a generated material file, its digest, status, and optional QA evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from manual_acceptance import invalidate_manual_acceptance
from validate_project_manifest import QA_KEYS, validate

READY = {"ready", "submitted", "archived"}
PENDING_TRUTH = {"pending-data", "pending-photo", "pending-signature"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register(
    manifest_path: Path,
    material_id: str,
    file_path: Path,
    status: str,
    qa_report_path: Path | None,
    data_cutoff: str | None,
) -> None:
    manifest_path = manifest_path.resolve()
    root = manifest_path.parent
    actual = file_path.resolve()
    if not actual.is_file():
        raise ValueError(f"材料文件不存在：{actual}")
    if actual != root and root not in actual.parents:
        raise ValueError(f"材料文件必须位于材料包根目录内：{root}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    materials = [item for item in data.get("materials", []) if isinstance(item, dict)]
    matches = [item for item in materials if str(item.get("id")) == material_id]
    if len(matches) != 1:
        raise ValueError(f"材料ID必须唯一存在：{material_id}")
    material = matches[0]
    suffix = actual.suffix.lower().lstrip(".")
    if suffix != str(material.get("output_format", "")).lower():
        raise ValueError(f"文件扩展名.{suffix}与output_format={material.get('output_format')}不一致")
    if status in PENDING_TRUTH:
        expected = {
            "pending-data": {"data"}, "pending-photo": {"photo"}, "pending-signature": set(),
        }[status]
        applicable = {key for key, value in material.get("qa", {}).items() if value != "not-applicable"}
        if expected and not expected <= applicable:
            raise ValueError(f"材料{material_id}不适用状态{status}；相应QA门槛未启用")

    report: dict = {}
    if qa_report_path:
        report = json.loads(qa_report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("QA报告必须是以QA项目为键的JSON对象")
        for key, value in report.items():
            if key not in QA_KEYS or not isinstance(value, dict):
                raise ValueError(f"QA报告含无效项目：{key}")
    if status in READY and not qa_report_path:
        raise ValueError("提升为ready/submitted/archived时必须提供--qa-report，不允许只改状态")

    material["file_path"] = str(actual.relative_to(root))
    material["sha256"] = sha256(actual)
    material["status"] = status
    if data_cutoff:
        material["data_cutoff"] = data_cutoff
    if qa_report_path:
        qa = material.setdefault("qa", {})
        qa_records = material.setdefault("qa_records", {})
        for key, value in report.items():
            qa[key] = value.get("status")
            if qa[key] == "passed":
                qa_records[key] = {name: value.get(name) for name in ("checked_at", "method", "report_path", "reviewer")}

    invalidate_manual_acceptance(data, f"材料{material_id}文件或状态发生变化")

    errors, warnings = validate(data)
    if errors:
        raise ValueError("登记后主清单无效：\n- " + "\n- ".join(errors))
    history = data.setdefault("revision_history", [])
    history.append(
        {
            "changed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "action": "register-material-file",
            "material_id": material_id,
            "status": status,
            "file_path": material["file_path"],
            "sha256": material["sha256"],
            "warnings": warnings,
        }
    )
    temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, manifest_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--material-id", required=True)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument(
        "--status",
        choices=("draft", "pending-data", "pending-photo", "pending-signature", "verified", "ready", "submitted", "archived"),
        default="draft",
    )
    parser.add_argument("--qa-report", type=Path)
    parser.add_argument("--data-cutoff")
    args = parser.parse_args()
    try:
        register(args.manifest, args.material_id, args.file, args.status, args.qa_report, args.data_cutoff)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"登记失败：{exc}", file=sys.stderr)
        return 1
    print(f"登记完成：{args.material_id} -> {args.file.resolve()} ({args.status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
