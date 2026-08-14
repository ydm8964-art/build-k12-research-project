#!/usr/bin/env python3
"""Normalize frozen panes and the portable default font after artifact-tool XLSX export."""

from __future__ import annotations

import argparse
import os
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("x", MAIN_NS)


def normalize(path: Path, freeze_rows: int, default_font: str | None = None) -> None:
    if freeze_rows < 1:
        raise ValueError("freeze_rows必须大于0")
    with zipfile.ZipFile(path) as source:
        bad = source.testzip()
        if bad:
            raise ValueError(f"XLSX压缩包损坏：{bad}")
        entries = [(info, source.read(info.filename)) for info in source.infolist()]

    changed = 0
    output_entries: list[tuple[zipfile.ZipInfo, bytes]] = []
    for info, content in entries:
        if info.filename == "xl/styles.xml" and default_font:
            root = ET.fromstring(content)
            fonts = root.find(f"{{{MAIN_NS}}}fonts")
            first_font = fonts.find(f"{{{MAIN_NS}}}font") if fonts is not None else None
            if first_font is None:
                raise ValueError("styles.xml缺少默认字体记录")
            name = first_font.find(f"{{{MAIN_NS}}}name")
            if name is None:
                name = ET.SubElement(first_font, f"{{{MAIN_NS}}}name")
            name.set("val", default_font)
            content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        if info.filename.startswith("xl/worksheets/") and info.filename.endswith(".xml"):
            root = ET.fromstring(content)
            sheet_views = root.find(f"{{{MAIN_NS}}}sheetViews")
            if sheet_views is not None:
                sheet_view = sheet_views.find(f"{{{MAIN_NS}}}sheetView")
                if sheet_view is not None:
                    for node in list(sheet_view):
                        if node.tag in {f"{{{MAIN_NS}}}pane", f"{{{MAIN_NS}}}selection"}:
                            sheet_view.remove(node)
                    top_left = f"A{freeze_rows + 1}"
                    ET.SubElement(
                        sheet_view,
                        f"{{{MAIN_NS}}}pane",
                        {
                            "ySplit": str(freeze_rows),
                            "topLeftCell": top_left,
                            "activePane": "bottomLeft",
                            "state": "frozen",
                        },
                    )
                    ET.SubElement(
                        sheet_view,
                        f"{{{MAIN_NS}}}selection",
                        {"pane": "bottomLeft", "activeCell": top_left, "sqref": top_left},
                    )
                    content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                    changed += 1
        output_entries.append((info, content))

    if not changed:
        raise ValueError("未找到可处理的工作表视图")
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w") as target:
            for info, content in output_entries:
                target.writestr(info, content)
        with zipfile.ZipFile(temp_path) as check:
            bad = check.testzip()
            if bad:
                raise ValueError(f"规范化后的XLSX损坏：{bad}")
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--freeze-rows", type=int, default=3)
    parser.add_argument("--default-font")
    args = parser.parse_args()
    normalize(args.xlsx, args.freeze_rows, args.default_font)
    font_text = f"，默认字体{args.default_font}" if args.default_font else ""
    print(f"已为工作表设置冻结前{args.freeze_rows}行{font_text}：{args.xlsx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
