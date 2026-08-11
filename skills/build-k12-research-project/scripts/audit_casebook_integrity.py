#!/usr/bin/env python3
"""Audit casebook case states, implementation metadata, evidence, and manifest coverage."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

CASE_STATUS_RE = re.compile(r"案例状态\s*[：:]\s*(designed|piloted|implemented|validated)", re.I)
ACTUAL_CLAIM_RE = re.compile(r"学生(?:们)?普遍认为|许多学生表示|活动提高了|结果表明|总体来看，本次活动|从(?:过程|实验|附件)?照片(?:中)?(?:可以看出|可见)|已经完成|已完成")
EVIDENCE_ID_RE = re.compile(r"\b(?:PHO|OBS|INT|EVAL|STU-WORK|DATA|ART)-[A-Z0-9-]+\b", re.I)
META_PATTERNS = {
    "实施日期": re.compile(r"实施日期|实施时间|授课日期"),
    "学校": re.compile(r"实施学校|授课学校"),
    "年级班级": re.compile(r"实施班级|授课班级|年级班级"),
    "教师": re.compile(r"授课教师|指导教师|实施教师"),
    "参与人数": re.compile(r"参与人数|学生人数"),
    "实际课时": re.compile(r"实际课时|实际用时|实施课时"),
    "材料版本": re.compile(r"材料版本|教案版本|方案版本"),
    "偏离事项": re.compile(r"偏离事项|方案调整|实施偏差"),
    "数据截止": re.compile(r"数据截止"),
}


def element_text(element) -> str:
    return "".join(node.text or "" for node in element.iter() if node.tag == qn("w:t")).strip()


def paragraph_style_id(element) -> str:
    style_nodes = element.xpath("./w:pPr/w:pStyle")
    if not style_nodes:
        return ""
    return style_nodes[0].get(qn("w:val"), "")


def extract_cases(path: Path) -> tuple[list[dict], list[str]]:
    document = Document(path)
    heading1_ids = {style.style_id for style in document.styles if style.name == "Heading 1"}
    body_children = list(document.element.body.iterchildren())
    start_indexes: list[int] = []
    for index, child in enumerate(body_children):
        if child.tag != qn("w:p") or paragraph_style_id(child) not in heading1_ids:
            continue
        if "案例" in element_text(child):
            start_indexes.append(index)

    toc_titles: list[str] = []
    first_start = start_indexes[0] if start_indexes else len(body_children)
    for child in body_children[:first_start]:
        value = element_text(child)
        if re.match(r"^案例[一二三四五六七八九十百0-9]+[：:]", value):
            toc_titles.append(re.sub(r"\s+\d+\s*$", "", value))

    cases: list[dict] = []
    for position, start in enumerate(start_indexes):
        end = start_indexes[position + 1] if position + 1 < len(start_indexes) else len(body_children)
        heading = element_text(body_children[start])
        pieces = [element_text(child) for child in body_children[start:end]]
        pieces = [piece for piece in pieces if piece]
        text = "\n".join(pieces)
        title = ""
        for piece in pieces[1:8]:
            if piece.startswith(("一、", "一.")):
                break
            if len(piece) > 4 and "案例基本信息" not in piece:
                title = piece
                break
        cases.append({"heading": heading, "title": title or heading, "text": text})
    return cases, toc_titles


def audit(path: Path, manifest_path: Path | None, final: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if path.suffix.lower() != ".docx":
        return ["案例集专项审计仅支持DOCX"], warnings
    cases, toc_titles = extract_cases(path)
    if not cases:
        return ["未识别到Heading 1样式的案例起始标题；请先规范案例层级"], warnings
    if toc_titles and len(toc_titles) != len(cases):
        errors.append(f"目录列出{len(toc_titles)}个案例，但正文识别到{len(cases)}个案例")

    for index, case in enumerate(cases, 1):
        label = f"案例{index}“{case['title'][:30]}”"
        status_match = CASE_STATUS_RE.search(case["text"])
        status = status_match.group(1).lower() if status_match else None
        actual_claims = len(ACTUAL_CLAIM_RE.findall(case["text"]))
        evidence_ids = set(value.upper() for value in EVIDENCE_ID_RE.findall(case["text"]))
        if status is None:
            (errors if final else warnings).append(f"{label}未明确标注designed/piloted/implemented/validated状态")
        if actual_claims and status in {None, "designed", "piloted"}:
            errors.append(f"{label}有{actual_claims}处已实施/效果表述，但状态不是implemented/validated")
        if status in {"implemented", "validated"}:
            missing = [name for name, pattern in META_PATTERNS.items() if not pattern.search(case["text"])]
            if missing:
                errors.append(f"{label}缺少实施元数据：{missing}")
            if not evidence_ids:
                errors.append(f"{label}标记为已实施/验证，但正文没有可追溯证据ID")
        if status == "validated" and not re.search(r"实际学习成果|效果证据|结果与证据", case["text"]):
            warnings.append(f"{label}标记validated，但未识别到独立的实际成果/效果证据栏目")

    if manifest_path is not None:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_cases = [item for item in data.get("cases", []) if isinstance(item, dict)]
        if len(manifest_cases) != len(cases):
            errors.append(f"manifest登记{len(manifest_cases)}个案例，但案例集正文有{len(cases)}个")
        manifest_titles = {str(item.get("title", "")).strip() for item in manifest_cases}
        for case in cases:
            if case["title"].strip() not in manifest_titles:
                warnings.append(f"案例集题名未在manifest精确匹配：{case['title'][:50]}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        errors, warnings = audit(args.docx, args.manifest, args.final)
    except Exception as exc:
        print(f"读取或审计失败：{exc}", file=sys.stderr)
        return 2
    for item in warnings:
        print(f"警告：{item}")
    for item in errors:
        print(f"错误：{item}")
    if errors:
        print(f"案例集证据审计未通过：{len(errors)}个错误，{len(warnings)}个警告")
        return 1
    print(f"案例集证据审计通过：0个错误，{len(warnings)}个警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
