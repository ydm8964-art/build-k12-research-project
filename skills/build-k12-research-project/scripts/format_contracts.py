#!/usr/bin/env python3
"""Load and resolve per-material DOCX/XLSX format contracts."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "references" / "material-format-contracts.json"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_contracts(path: Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("profiles"), dict) or not isinstance(data.get("materials"), dict):
        raise ValueError("版式合同缺少profiles或materials")
    return data


def resolve_profile(profile_id: str, data: dict[str, Any]) -> dict[str, Any]:
    profiles = data["profiles"]
    stack: list[str] = []

    def resolve(current: str) -> dict[str, Any]:
        if current not in profiles:
            raise ValueError(f"未知版式合同：{current}")
        if current in stack:
            raise ValueError("版式合同继承存在循环：" + " -> ".join([*stack, current]))
        stack.append(current)
        item = profiles[current]
        parent = item.get("extends")
        result = deep_merge(resolve(str(parent)), item) if parent else deepcopy(item)
        stack.pop()
        result["contract_id"] = current
        return result

    return resolve(profile_id)


def material_contract(material_id: str, path: Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    data = load_contracts(path)
    profile_id = data["materials"].get(material_id)
    if not profile_id:
        raise ValueError(f"材料{material_id}未绑定版式合同")
    result = resolve_profile(str(profile_id), data)
    result["material_id"] = material_id
    return result


def validate_contract_catalog(path: Path = DEFAULT_CONTRACT_PATH) -> list[str]:
    data = load_contracts(path)
    errors: list[str] = []
    expected = {f"M{index:02d}" for index in range(26)}
    actual = set(data["materials"])
    if actual != expected:
        errors.append(f"材料版式合同覆盖不完整：缺少{sorted(expected - actual)}；多出{sorted(actual - expected)}")
    for material_id, profile_id in data["materials"].items():
        try:
            contract = resolve_profile(str(profile_id), data)
        except ValueError as exc:
            errors.append(f"{material_id}：{exc}")
            continue
        if contract.get("output_format") == "docx" and contract.get("mode") != "official-exact":
            roles = contract.get("roles", {})
            for role in (
                "title", "heading1", "heading2", "heading3", "body", "toc_title", "toc_level1", "toc_level2",
                "caption", "table_header", "table_body", "header_footer",
            ):
                if role not in roles:
                    errors.append(f"{material_id}/{profile_id}缺少{role}格式")
        if contract.get("output_format") == "xlsx":
            for key in ("reference_template", "required_sheets", "freeze", "rows", "roles", "number_formats"):
                if not contract.get(key):
                    errors.append(f"{material_id}/{profile_id}缺少XLSX固定格式字段{key}")
            roles = contract.get("roles", {})
            for role in ("title", "description", "header", "label", "input", "formula"):
                if role not in roles:
                    errors.append(f"{material_id}/{profile_id}缺少XLSX角色{role}")
    return errors
