#!/usr/bin/env python3
"""Bind completed human final-review gates to the current project files and policy snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from manual_acceptance import MANUAL_GATES, manifest_review_sha256
from validate_project_manifest import validate


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_inside(root: Path, value: str) -> Path:
    raw = Path(value).expanduser()
    actual = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    if actual != root and root not in actual.parents:
        raise ValueError(f"文件不在材料包根目录内：{actual}")
    return actual


def verify_input(value: dict) -> tuple[datetime, str, dict]:
    reviewer = str(value.get("reviewer", "")).strip()
    reviewed_at = str(value.get("reviewed_at", "")).strip()
    gates = value.get("gates")
    if not reviewer:
        raise ValueError("人工终审输入缺少reviewer")
    try:
        reviewed_time = datetime.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise ValueError("reviewed_at必须是含时区的ISO 8601日期时间") from exc
    if reviewed_time.tzinfo is None:
        raise ValueError("reviewed_at必须包含时区")
    if not isinstance(gates, dict):
        raise ValueError("gates必须是对象")
    missing = sorted(set(MANUAL_GATES) - set(gates))
    extra = sorted(set(gates) - set(MANUAL_GATES))
    if missing or extra:
        raise ValueError(f"人工终审门槛集合不一致；缺少{missing}，多出{extra}")
    for gate_id, item in gates.items():
        if not isinstance(item, dict) or item.get("status") != "passed":
            raise ValueError(f"人工终审门槛{gate_id}必须明确标记passed")
        if not str(item.get("note", "")).strip():
            raise ValueError(f"人工终审门槛{gate_id}必须填写具体核验说明note")
    return reviewed_time, reviewer, gates


def record(manifest_path: Path, root: Path, input_path: Path) -> Path:
    manifest_path = manifest_path.resolve()
    root = root.resolve()
    if manifest_path.parent != root:
        raise ValueError("project-manifest.json必须位于材料包根目录")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reviewed_time, reviewer, gates = verify_input(json.loads(input_path.read_text(encoding="utf-8")))
    if reviewed_time.date().isoformat() > str(manifest.get("governance", {}).get("current_date", "")):
        raise ValueError("reviewed_at晚于主清单governance.current_date")
    if reviewed_time > datetime.now().astimezone():
        raise ValueError("reviewed_at晚于实际当前时间")
    requirements = manifest.get("submission_requirements", {})
    if not isinstance(requirements, dict) or requirements.get("status") != "verified":
        raise ValueError("人工终审前必须先完成当年政策与模板核验")
    policy_hash = str(requirements.get("policy_snapshot_sha256", ""))
    if not policy_hash:
        raise ValueError("人工终审前缺少政策快照SHA-256")
    if reviewed_time.date().isoformat() < str(requirements.get("searched_at", "")):
        raise ValueError("人工终审时间早于本次官方政策检索日期")
    manifest["schema_version"] = "1.6"

    material_hashes: dict[str, str] = {}
    for item in manifest.get("materials", []):
        if not isinstance(item, dict) or item.get("included_in_batch") is False or not item.get("file_path"):
            continue
        material_id = str(item.get("id", "")).strip()
        actual = resolve_inside(root, str(item["file_path"]))
        if not actual.is_file():
            raise ValueError(f"人工终审绑定的材料不存在：{material_id} -> {actual}")
        actual_hash = sha256(actual)
        if str(item.get("sha256", "")).lower() != actual_hash:
            raise ValueError(f"人工终审前材料{material_id}的实际哈希与主清单不一致")
        material_hashes[material_id] = actual_hash
    if not material_hashes:
        raise ValueError("没有可绑定的实际材料文件")

    stamp = re.sub(r"[^0-9]", "", reviewed_time.isoformat())[:14]
    target = root / "交付校验" / f"人工终审确认_{stamp}.json"
    if target.exists():
        raise FileExistsError(f"拒绝覆盖既有人工终审确认：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    attestation = {
        "schema_version": "1.0",
        "project_title": manifest.get("project", {}).get("title"),
        "snapshot_id": manifest.get("generation_contract", {}).get("snapshot_id"),
        "manifest_review_sha256": manifest_review_sha256(manifest),
        "policy_snapshot_sha256": policy_hash,
        "reviewed_at": reviewed_time.isoformat(timespec="seconds"),
        "reviewer": reviewer,
        "gates": {
            gate_id: {"description": MANUAL_GATES[gate_id], **gates[gate_id]}
            for gate_id in MANUAL_GATES
        },
        "material_hashes": material_hashes,
    }
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(attestation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)

    manifest["manual_acceptance"] = {
        "status": "verified",
        "reviewed_at": attestation["reviewed_at"],
        "reviewer": reviewer,
        "attestation_file": str(target.relative_to(root)),
        "attestation_sha256": sha256(target),
        "invalidated_at": None,
        "invalidation_reason": None,
    }
    errors, _ = validate(manifest)
    if errors:
        target.unlink(missing_ok=True)
        raise ValueError("人工终审登记后的主清单无效：\n- " + "\n- ".join(errors))
    manifest_temp = manifest_path.with_suffix(".tmp")
    manifest_temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(manifest_temp, manifest_path)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        target = record(args.manifest, args.root, args.input)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"人工终审登记失败：{exc}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
