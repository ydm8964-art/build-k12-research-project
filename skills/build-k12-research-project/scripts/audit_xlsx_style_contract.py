#!/usr/bin/env python3
"""Audit M09 workbook fonts, row heights, columns, panes, gridlines, and reserved-cell styles."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from format_contracts import DEFAULT_CONTRACT_PATH, material_contract

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def tag(name: str) -> str:
    return f"{{{MAIN_NS}}}{name}"


def worksheet_target(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    while target.startswith("../"):
        target = target[3:]
    return f"xl/{target}"


def sheet_map(archive: zipfile.ZipFile) -> tuple[list[str], dict[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rels = {
        node.get("Id", ""): worksheet_target(node.get("Target", ""))
        for node in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    names: list[str] = []
    result: dict[str, str] = {}
    for sheet in workbook.findall(f".//{tag('sheet')}"):
        name = sheet.get("name", "")
        names.append(name)
        result[name] = rels.get(sheet.get(f"{{{REL_NS}}}id", ""), "")
    return names, result


def xml_signature(root: ET.Element, child_name: str) -> bytes | None:
    child = root.find(tag(child_name))
    return ET.tostring(child, encoding="utf-8") if child is not None else None


def row_signature(root: ET.Element, last_row: int) -> dict[int, tuple[str | None, tuple[tuple[str, str], ...]]]:
    result: dict[int, tuple[str | None, tuple[tuple[str, str], ...]]] = {}
    for row in root.findall(f".//{tag('row')}"):
        index = int(row.get("r", "0"))
        if index > last_row:
            continue
        cells = tuple((cell.get("r", ""), cell.get("s", "0")) for cell in row.findall(tag("c")))
        result[index] = (row.get("ht"), cells)
    return result


def font_values(styles: ET.Element) -> list[tuple[str | None, float | None, bool]]:
    fonts = styles.find(tag("fonts"))
    result: list[tuple[str | None, float | None, bool]] = []
    for font in list(fonts) if fonts is not None else []:
        name = font.find(tag("name"))
        size = font.find(tag("sz"))
        result.append(
            (
                name.get("val") if name is not None else None,
                float(size.get("val")) if size is not None and size.get("val") else None,
                font.find(tag("b")) is not None,
            )
        )
    return result


def audit(
    path: Path,
    material_id: str = "M09",
    reference: Path | None = None,
    contracts_path: Path = DEFAULT_CONTRACT_PATH,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    contract = material_contract(material_id, contracts_path)
    if contract.get("output_format") != "xlsx":
        return [f"{material_id}不是XLSX版式合同"], warnings
    if path.suffix.lower() != ".xlsx":
        return ["电子表格版式合同审计仅支持XLSX"], warnings
    if reference is None:
        reference = Path(__file__).resolve().parents[1] / str(contract["reference_template"])
    if not reference.is_file():
        return [f"固定XLSX母版不存在：{reference}"], warnings

    try:
        with zipfile.ZipFile(path) as actual_zip, zipfile.ZipFile(reference) as reference_zip:
            for archive, label in ((actual_zip, "待审工作簿"), (reference_zip, "固定母版")):
                bad = archive.testzip()
                if bad:
                    return [f"{label}压缩包损坏：{bad}"], warnings
            actual_names, actual_sheets = sheet_map(actual_zip)
            reference_names, reference_sheets = sheet_map(reference_zip)
            if actual_names != contract["required_sheets"]:
                errors.append(f"工作表名称或顺序必须为{contract['required_sheets']}，实际为{actual_names}")
            if actual_names != reference_names:
                errors.append("工作表名称或顺序与固定母版不一致")

            actual_styles_bytes = actual_zip.read("xl/styles.xml")
            reference_styles_bytes = reference_zip.read("xl/styles.xml")
            if actual_styles_bytes != reference_styles_bytes:
                errors.append("styles.xml与固定母版不一致；字体、字号、颜色、边框或数字格式发生漂移")
            actual_styles = ET.fromstring(actual_styles_bytes)
            required_font = contract["roles"]["input"]["font"]
            fonts = font_values(actual_styles)
            if not fonts or any(name != required_font for name, _, _ in fonts):
                errors.append(f"全簿字体必须为{required_font}，实际字体记录为{fonts}")
            required_font_roles = {
                (float(contract["roles"]["title"]["size_pt"]), True),
                (float(contract["roles"]["description"]["size_pt"]), False),
                (float(contract["roles"]["header"]["size_pt"]), True),
                (float(contract["roles"]["input"]["size_pt"]), False),
            }
            actual_font_roles = {(size, bold) for _, size, bold in fonts}
            if not required_font_roles <= actual_font_roles:
                errors.append(f"工作簿字体层级缺失：应含{sorted(required_font_roles)}，实际{sorted(actual_font_roles)}")

            for sheet_name in reference_names:
                actual_target = actual_sheets.get(sheet_name)
                reference_target = reference_sheets.get(sheet_name)
                if not actual_target or actual_target not in actual_zip.namelist():
                    errors.append(f"工作表{sheet_name}缺少有效XML")
                    continue
                actual_root = ET.fromstring(actual_zip.read(actual_target))
                reference_root = ET.fromstring(reference_zip.read(reference_target))
                actual_view = actual_root.find(f".//{tag('sheetView')}")
                if actual_view is None or actual_view.get("showGridLines", "1") != "0":
                    errors.append(f"工作表{sheet_name}必须关闭网格线")
                pane = actual_root.find(f".//{tag('pane')}")
                freeze = contract["freeze"]
                if (
                    pane is None
                    or pane.get("state") != "frozen"
                    or pane.get("ySplit") != str(freeze["rows"])
                    or pane.get("topLeftCell") != freeze["top_left_cell"]
                ):
                    errors.append(f"工作表{sheet_name}必须冻结前{freeze['rows']}行并定位{freeze['top_left_cell']}")
                if xml_signature(actual_root, "cols") != xml_signature(reference_root, "cols"):
                    errors.append(f"工作表{sheet_name}列宽与固定母版不一致")
                if actual_root.find(tag("mergeCells")) is not None:
                    errors.append(f"工作表{sheet_name}数据区不得含合并单元格")
                validations = actual_root.find(tag("dataValidations"))
                if validations is None or int(validations.get("count", "0")) < 1:
                    errors.append(f"工作表{sheet_name}必须保留数据验证")
                last_row = int(contract["data_region"]["last_reserved_row"])
                if row_signature(actual_root, last_row) != row_signature(reference_root, last_row):
                    errors.append(f"工作表{sheet_name}第1—{last_row}行的行高或单元格样式与固定母版不一致")
    except (OSError, zipfile.BadZipFile, KeyError, ValueError, ET.ParseError) as exc:
        errors.append(f"XLSX版式合同审计失败：{exc}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--material-id", default="M09")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACT_PATH)
    args = parser.parse_args()
    errors, warnings = audit(args.xlsx, args.material_id, args.reference, args.contracts)
    for warning in warnings:
        print(f"警告：{warning}")
    for error in errors:
        print(f"错误：{error}")
    if errors:
        print(f"XLSX固定版式合同审计未通过：{len(errors)}个错误")
        return 1
    print("XLSX固定版式合同审计通过：0个错误")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
