#!/usr/bin/env python3
"""Regenerate package attention/index DOCX files from the current manifest snapshot."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from apply_docx_format_contract import apply_in_place
from generate_attention_items import build_document as build_attention_document
from initialize_project_package import build_index, sha256, sync_index_row
from manual_acceptance import invalidate_manual_acceptance
from validate_project_manifest import validate


def reset_qa(material: dict) -> None:
    qa = material.setdefault("qa", {})
    for key, value in list(qa.items()):
        if value != "not-applicable":
            qa[key] = "pending"
    material.pop("qa_records", None)


def refresh(manifest_path: Path) -> dict:
    manifest_path = manifest_path.resolve()
    root = manifest_path.parent
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    materials = {str(item.get("id")): item for item in data.get("materials", []) if isinstance(item, dict)}
    if "M00" not in materials or "M25" not in materials:
        raise ValueError("主清单必须包含M00注意事项和M25交付索引")
    attention = materials["M00"]
    index = materials["M25"]
    attention_path = root / str(attention.get("file_path") or attention.get("planned_file_path"))
    index_path = root / str(index.get("file_path") or index.get("planned_file_path"))
    attention_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    for item, target in ((attention, attention_path), (index, index_path)):
        item.update(status="draft", file_path=str(target.relative_to(root)), sha256=None)
        reset_qa(item)
    as_of = date.fromisoformat(str(data["governance"]["current_date"]))
    build_attention_document(data, attention_path, as_of)
    apply_in_place(attention_path, "M00")
    attention["sha256"] = sha256(attention_path)
    build_index(data, index_path)
    sync_index_row(data, index_path)
    apply_in_place(index_path, "M25")
    index["sha256"] = sha256(index_path)
    invalidate_manual_acceptance(data, "注意事项或交付索引已重新生成")
    errors, warnings = validate(data)
    if errors:
        raise ValueError("刷新后主清单无效：\n- " + "\n- ".join(errors))
    data.setdefault("revision_history", []).append({
        "changed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "action": "refresh-package-controls", "material_ids": ["M00", "M25"], "warnings": warnings,
    })
    temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, manifest_path)
    return {"attention": str(attention_path), "index": str(index_path), "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        result = refresh(args.manifest)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"控制文件刷新失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
