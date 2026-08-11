#!/usr/bin/env python3
"""Structural DOCX format audit for K-12 research-project materials."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0
TOLERANCE_MM = 1.0
TABLE_PROFILES = {"lesson-table", "casebook", "attention-items"}
REPEAT_HEADER_PROFILES = {"research-form", "analysis-report", "casebook", "attention-items"}
VALID_PROFILES = {
    "official-exact",
    "research-form",
    "analysis-report",
    "lesson-table",
    "lesson-long",
    "casebook",
    "evidence-sheet",
    "attention-items",
}


def close(left: float, right: float, tolerance: float = TOLERANCE_MM) -> bool:
    return abs(left - right) <= tolerance


def section_signature(section) -> tuple[float, ...]:
    return tuple(
        round(value.mm, 1)
        for value in (
            section.page_width,
            section.page_height,
            section.top_margin,
            section.bottom_margin,
            section.left_margin,
            section.right_margin,
            section.header_distance,
            section.footer_distance,
        )
    ) + (int(section.orientation),)


def table_width_dxa(table) -> int | None:
    node = table._tbl.tblPr.find(qn("w:tblW"))
    if node is None or node.get(qn("w:type")) != "dxa":
        return None
    try:
        return int(node.get(qn("w:w")))
    except (TypeError, ValueError):
        return None


def has_repeat_header(table) -> bool:
    if not table.rows:
        return False
    props = table.rows[0]._tr.trPr
    return props is not None and props.find(qn("w:tblHeader")) is not None


def has_cell_margins(table) -> bool:
    return table._tbl.tblPr.find(qn("w:tblCellMar")) is not None


def exact_height_rows(table) -> list[int]:
    found: list[int] = []
    for index, row in enumerate(table.rows, 1):
        props = row._tr.trPr
        if props is None:
            continue
        for height in props.findall(qn("w:trHeight")):
            if height.get(qn("w:hRule")) == "exact":
                found.append(index)
                break
    return found


def all_text(document: Document) -> str:
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def audit(path: Path, profile: str, reference: Path | None, final: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if profile not in VALID_PROFILES:
        return [f"未知profile：{profile}"], warnings
    if path.suffix.lower() != ".docx":
        return ["结构审计仅支持DOCX；DOC请先保留原件并制作工作副本"], warnings

    document = Document(path)
    if not document.sections:
        errors.append("文档没有分节信息")

    if profile == "official-exact":
        if reference is None:
            errors.append("official-exact必须提供--reference")
        else:
            source = Document(reference)
            if len(document.sections) != len(source.sections):
                errors.append(f"分节数量与官方模板不一致：{len(document.sections)} != {len(source.sections)}")
            for index, (actual, expected) in enumerate(zip(document.sections, source.sections), 1):
                if section_signature(actual) != section_signature(expected):
                    errors.append(f"第{index}节纸张/页边距/页眉页脚与官方模板不一致")
            if len(document.tables) != len(source.tables):
                errors.append(f"表格数量与官方模板不一致：{len(document.tables)} != {len(source.tables)}")
            for index, (actual, expected) in enumerate(zip(document.tables, source.tables), 1):
                actual_shape = (len(actual.rows), len(actual.columns))
                expected_shape = (len(expected.rows), len(expected.columns))
                if actual_shape != expected_shape:
                    errors.append(f"第{index}个表格形状与模板不一致：{actual_shape} != {expected_shape}")
    else:
        for index, section in enumerate(document.sections, 1):
            width, height = section.page_width.mm, section.page_height.mm
            portrait_a4 = close(width, A4_WIDTH_MM) and close(height, A4_HEIGHT_MM)
            landscape_a4 = close(width, A4_HEIGHT_MM) and close(height, A4_WIDTH_MM)
            if not (portrait_a4 or landscape_a4):
                errors.append(f"第{index}节不是A4：{width:.1f}×{height:.1f}mm")
            if landscape_a4 and profile not in {"analysis-report", "evidence-sheet", "attention-items"}:
                warnings.append(f"第{index}节为横向A4，请确认该材料确需横向")
            if min(section.top_margin.mm, section.bottom_margin.mm, section.left_margin.mm, section.right_margin.mm) < 15:
                warnings.append(f"第{index}节页边距小于15mm，可能不适合装订或打印")

    if profile in TABLE_PROFILES and not document.tables:
        errors.append(f"{profile}应至少包含一个表格")

    for index, table in enumerate(document.tables, 1):
        section = document.sections[0]
        usable_mm = section.page_width.mm - section.left_margin.mm - section.right_margin.mm
        width = table_width_dxa(table)
        if width is None or width == 0:
            warnings.append(f"第{index}个表格未设置明确DXA总宽")
        else:
            width_mm = width / 1440 * 25.4
            if width_mm > usable_mm + 1.0:
                errors.append(f"第{index}个表格宽{width_mm:.1f}mm，超过版心{usable_mm:.1f}mm")
        grid = table._tbl.tblGrid.findall(qn("w:gridCol"))
        if not grid or any(not col.get(qn("w:w")) for col in grid):
            warnings.append(f"第{index}个表格缺少完整列宽网格")
        if len(table.rows) > 2 and profile in REPEAT_HEADER_PROFILES and not has_repeat_header(table):
            warnings.append(f"第{index}个多行表格未设置重复表头")
        if not has_cell_margins(table):
            warnings.append(f"第{index}个表格未设置表级单元格内边距")
        exact_rows = exact_height_rows(table)
        if exact_rows:
            warnings.append(f"第{index}个表格存在固定行高，可能截字：{exact_rows[:8]}")

    text = all_text(document)
    if profile == "casebook" and "目录" not in text:
        errors.append("案例集缺少目录")
    if final:
        for pattern, label in (
            (r"待填写|待补充|待确认|XXX+", "待处理占位词"),
            (r"_{4,}", "连续下划线占位"),
        ):
            count = len(re.findall(pattern, text, flags=re.IGNORECASE))
            if count:
                warnings.append(f"发现{label}{count}处；核对是否属于保留签章/填写区")

    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            if run.text.strip() and run.font.size and run.font.size.pt < 9:
                warnings.append("正文存在小于9磅文字，请检查可读性")
                return errors, warnings
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--profile", required=True, choices=sorted(VALID_PROFILES))
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        errors, warnings = audit(args.docx, args.profile, args.reference, args.final)
    except Exception as exc:  # keep CLI failure legible for production use
        print(f"读取或审计失败：{exc}", file=sys.stderr)
        return 2
    for item in warnings:
        print(f"警告：{item}")
    for item in errors:
        print(f"错误：{item}")
    if errors:
        print(f"格式结构审计未通过：{len(errors)}个错误，{len(warnings)}个警告")
        return 1
    print(f"格式结构审计通过：0个错误，{len(warnings)}个警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
