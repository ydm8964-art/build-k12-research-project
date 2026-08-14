#!/usr/bin/env python3
"""Record a project-specific live official-policy search as a verified requirements snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from manual_acceptance import invalidate_manual_acceptance, pending_acceptance
from validate_project_manifest import validate

REQUIRED_INPUT = (
    "search_run_id", "searched_at", "authority", "year", "official_portals_checked", "search_queries",
    "deadline", "submission_mode", "required_material_ids", "anonymous_required", "file_rules", "sources",
    "notice_source_ids", "template_source_ids",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_inside(root: Path, value: str) -> Path:
    raw = Path(value).expanduser()
    actual = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    if actual != root and root not in actual.parents:
        raise ValueError(f"官方附件必须保存在材料包根目录内：{actual}")
    return actual


def verify_input(data: dict) -> None:
    missing = [key for key in REQUIRED_INPUT if key not in data]
    if missing:
        raise ValueError("政策核验输入缺少字段：" + "、".join(missing))
    for key in ("official_portals_checked", "search_queries", "sources", "notice_source_ids", "template_source_ids"):
        if not isinstance(data[key], list) or not data[key]:
            raise ValueError(f"{key}必须是非空数组；每个课题都要实际联网检索官方入口")
    source_ids = {str(item.get("id")) for item in data["sources"] if isinstance(item, dict) and item.get("id")}
    if any(str(value) not in source_ids for value in data["notice_source_ids"] + data["template_source_ids"]):
        raise ValueError("notice_source_ids/template_source_ids必须引用本次sources中的来源")
    for source in data["sources"]:
        if not isinstance(source, dict) or any(not source.get(key) for key in ("id", "title", "locator")):
            raise ValueError("每个政策来源必须包含id、title和locator")
        if source.get("verification_status") != "verified":
            raise ValueError(f"来源{source.get('id')}尚未标记verified")
        if source.get("valid_for_year") not in {None, data["year"]}:
            raise ValueError(f"来源{source.get('id')}适用年度与本项目不一致")


def record(manifest_path: Path, root: Path, input_path: Path) -> Path:
    manifest_path = manifest_path.resolve()
    root = root.resolve()
    if manifest_path.parent != root:
        raise ValueError("project-manifest.json必须位于材料包根目录")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    policy = json.loads(input_path.read_text(encoding="utf-8"))
    verify_input(policy)
    if policy["year"] != manifest.get("project", {}).get("year"):
        raise ValueError("政策核验年度与project.year不一致")

    source_by_id = {str(item["id"]): item for item in policy["sources"] if isinstance(item, dict) and item.get("id")}
    for source_id in policy["template_source_ids"]:
        source = source_by_id[str(source_id)]
        if source.get("source_type") != "official-template":
            raise ValueError(f"模板来源{source_id}.source_type必须为official-template")
        local_file = str(source.get("local_file", "")).strip()
        if not local_file:
            raise ValueError(f"模板来源{source_id}缺少local_file；必须下载当年官方附件原件")
        actual = resolve_inside(root, local_file)
        if not actual.is_file():
            raise ValueError(f"模板来源{source_id}本地附件不存在：{actual}")
        if actual.suffix.lower() not in {".doc", ".docx", ".xls", ".xlsx", ".pdf", ".zip"}:
            raise ValueError(f"模板来源{source_id}附件格式异常：{actual.suffix}")
        if not str(source.get("retrieved_at", "")).strip():
            raise ValueError(f"模板来源{source_id}缺少retrieved_at")
        actual_hash = digest(actual)
        if str(source.get("source_sha256", "")).lower() != actual_hash:
            raise ValueError(f"模板来源{source_id}.source_sha256与本地附件不一致")
        source["local_file"] = str(actual.relative_to(root))

    safe_run_id = re.sub(r"[^A-Za-z0-9._-]+", "-", str(policy["search_run_id"])).strip("-.")
    if not safe_run_id:
        raise ValueError("search_run_id不能转换为安全文件名")
    target = root / "01政策与立项" / f"当年要求核验快照_{policy['year']}_{policy['searched_at']}_{safe_run_id}.json"
    if target.exists():
        raise FileExistsError(f"拒绝覆盖既有政策快照：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "schema_version": "1.0",
        "project_title": manifest.get("project", {}).get("title"),
        **policy,
    }
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)

    requirements = manifest.setdefault("submission_requirements", {})
    for key in REQUIRED_INPUT:
        if key != "sources":
            requirements[key] = policy[key]
    requirements.update(
        status="verified",
        verified_at=policy["searched_at"],
        policy_snapshot_file=str(target.relative_to(root.resolve())),
        policy_snapshot_sha256=digest(target),
    )
    required_ids = {str(value) for value in policy["required_material_ids"]}
    for material in manifest.get("materials", []):
        if isinstance(material, dict) and material.get("id"):
            material["required_for_submission"] = str(material["id"]) in required_ids
    material_by_id = {
        str(item.get("id")): item
        for item in manifest.get("materials", [])
        if isinstance(item, dict) and item.get("id")
    }
    for source_id in policy["template_source_ids"]:
        source = source_by_id[str(source_id)]
        for material_id in source.get("used_in", []):
            material = material_by_id.get(str(material_id))
            if material is None:
                raise ValueError(f"模板来源{source_id}.used_in引用不存在的材料：{material_id}")
            if material.get("format_profile") != "official-exact":
                raise ValueError(f"模板来源{source_id}不能绑定非official-exact材料{material_id}")
            template_suffix = Path(str(source["local_file"])).suffix.lower().lstrip(".")
            if template_suffix != str(material.get("output_format", "")).lower():
                raise ValueError(
                    f"模板来源{source_id}文件类型.{template_suffix}与材料{material_id}的"
                    f"output_format={material.get('output_format')}不一致；不能作为原位填写模板"
                )
            material["reference_source_id"] = str(source_id)
            material["reference_template"] = source["local_file"]
    existing = {
        str(item.get("id")): item
        for item in manifest.get("sources", [])
        if isinstance(item, dict) and item.get("id")
    }
    for item in policy["sources"]:
        normalized = dict(item)
        normalized.setdefault("verified_at", policy["searched_at"])
        normalized.setdefault("valid_for_year", policy["year"])
        existing[str(item["id"])] = normalized
    manifest["sources"] = list(existing.values())
    manifest["schema_version"] = "1.6"
    if "manual_acceptance" not in manifest:
        manifest["manual_acceptance"] = pending_acceptance()
    else:
        invalidate_manual_acceptance(manifest, "当年政策或官方模板快照已更新")
    errors, _ = validate(manifest)
    if errors:
        target.unlink(missing_ok=True)
        raise ValueError("登记后的主清单未通过校验：\n- " + "\n- ".join(errors))
    manifest_temp = manifest_path.with_suffix(".tmp")
    manifest_temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(manifest_temp, manifest_path)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True, help="本次联网检索并人工核验后的结构化JSON")
    args = parser.parse_args()
    try:
        target = record(args.manifest.resolve(), args.root.resolve(), args.input.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"政策快照登记失败：{exc}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
