#!/usr/bin/env python3
"""Audit XLSX sheet structure, formulas, visibility, filters, and freeze panes."""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from audit_common import cli_failed

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
FORMULA_ERROR_RE = re.compile(r"#(?:REF!|DIV/0!|VALUE!|NAME\?|N/A|NUM!|NULL!)", re.I)
CELL_RANGE_RE = re.compile(r"[A-Z]+(\d+)(?::[A-Z]+(\d+))?")
DATA_SHEET_TOKENS = ("原始数据", "清理", "编码", "证据索引", "照片登记", "材料进度")


def worksheet_target(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    while target.startswith("../"):
        target = target[3:]
    return f"xl/{target}"


def approximate_rows(root: ET.Element) -> int:
    dimension = root.find(f"{{{MAIN_NS}}}dimension")
    ref = dimension.get("ref", "") if dimension is not None else ""
    match = CELL_RANGE_RE.fullmatch(ref)
    if not match:
        return 0
    return int(match.group(2) or match.group(1))


def audit(path: Path, required_sheets: list[str], allowed_hidden_sheets: list[str], final: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if path.suffix.lower() != ".xlsx":
        return ["工作簿结构审计仅支持XLSX"], warnings
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                return [f"XLSX压缩包损坏：{bad}"], warnings
            names = set(archive.namelist())
            if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
                return ["XLSX缺少workbook.xml或工作簿关系文件"], warnings
            if any(name.startswith("xl/externalLinks/") for name in names) or "xl/connections.xml" in names:
                (errors if final else warnings).append("工作簿含外部链接或数据连接")

            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            rels = {
                rel.get("Id", ""): worksheet_target(rel.get("Target", ""))
                for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")
            }
            sheets: list[tuple[str, str, str]] = []
            for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
                name = sheet.get("name", "")
                state = sheet.get("state", "visible")
                rel_id = sheet.get(f"{{{REL_NS}}}id", "")
                sheets.append((name, state, rels.get(rel_id, "")))

            sheet_names = [name for name, _, _ in sheets]
            if not sheets:
                errors.append("工作簿没有工作表")
            if sheets and not any(state == "visible" for _, state, _ in sheets):
                errors.append("工作簿没有可见工作表")
            if len(set(sheet_names)) != len(sheet_names):
                errors.append("工作表名称重复")
            missing = [name for name in required_sheets if name not in sheet_names]
            if missing:
                (errors if final else warnings).append(f"缺少manifest要求的工作表：{missing}")

            calc = workbook.find(f"{{{MAIN_NS}}}calcPr")
            if calc is not None and calc.get("calcMode") == "manual":
                warnings.append("工作簿计算模式为manual，打开后可能不自动更新公式")

            for sheet_name, state, target in sheets:
                if not target or target not in names:
                    errors.append(f"工作表{sheet_name}缺少有效XML关系：{target or '未登记'}")
                    continue
                root = ET.fromstring(archive.read(target))
                formula_count = 0
                external_formula_count = 0
                invalid_formula_count = 0
                cached_error_count = 0
                for cell in root.findall(f".//{{{MAIN_NS}}}c"):
                    formula = cell.find(f"{{{MAIN_NS}}}f")
                    if formula is not None:
                        formula_count += 1
                        value = formula.text or ""
                        if FORMULA_ERROR_RE.search(value):
                            invalid_formula_count += 1
                        if "[" in value and "]" in value:
                            external_formula_count += 1
                    if cell.get("t") == "e":
                        cached_error_count += 1
                if invalid_formula_count:
                    errors.append(f"工作表{sheet_name}含{invalid_formula_count}个损坏引用/错误公式")
                if cached_error_count:
                    errors.append(f"工作表{sheet_name}含{cached_error_count}个已缓存公式错误值")
                if external_formula_count:
                    (errors if final else warnings).append(f"工作表{sheet_name}含{external_formula_count}个外部工作簿公式")

                rows = approximate_rows(root)
                is_data_sheet = any(token in sheet_name for token in DATA_SHEET_TOKENS)
                has_table = root.find(f"{{{MAIN_NS}}}tableParts") is not None
                has_entry_area = rows > 20 or has_table
                if is_data_sheet and has_entry_area:
                    if root.find(f".//{{{MAIN_NS}}}pane") is None:
                        warnings.append(f"数据型工作表{sheet_name}超过20行但未冻结窗格")
                    if root.find(f"{{{MAIN_NS}}}autoFilter") is None and not has_table:
                        warnings.append(f"数据型工作表{sheet_name}超过20行但未设置筛选")
                    if root.find(f"{{{MAIN_NS}}}dataValidations") is None:
                        warnings.append(f"数据型工作表{sheet_name}未设置数据验证；核对日期、类别和状态列的输入约束")
                if is_data_sheet and root.find(f"{{{MAIN_NS}}}mergeCells") is not None:
                    warnings.append(f"数据型工作表{sheet_name}含合并单元格，可能影响筛选、排序和数据分析")
                if state != "visible" and sheet_name not in allowed_hidden_sheets:
                    (errors if final else warnings).append(f"工作表{sheet_name}状态为{state}，但未登记在allowed_hidden_sheets")
                if "统计分析" in sheet_name and rows > 3 and formula_count == 0:
                    warnings.append(f"统计分析工作表{sheet_name}未发现公式；核对是否把派生结果硬编码")
    except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        errors.append(f"XLSX无法读取或解析：{exc}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--require-sheet", action="append", default=[])
    parser.add_argument("--allow-hidden-sheet", action="append", default=[])
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    errors, warnings = audit(args.xlsx, args.require_sheet, args.allow_hidden_sheet, args.final)
    for item in warnings:
        print(f"警告：{item}")
    for item in errors:
        print(f"错误：{item}")
    if cli_failed(errors, warnings, args.final):
        print(f"工作簿结构审计未通过：{len(errors)}个错误，{len(warnings)}个警告")
        return 1
    print(f"工作簿结构审计通过：0个错误，{len(warnings)}个警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
