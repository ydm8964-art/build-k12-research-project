#!/usr/bin/env python3
"""Classify DOCX paragraphs into deterministic K-12 material typography roles."""

from __future__ import annotations

import re

K12_STYLE_NAMES = {
    "cover_title": "K12 Cover Title",
    "cover_metadata": "K12 Cover Metadata",
    "title": "K12 Title",
    "subtitle": "K12 Subtitle",
    "heading1": "K12 Heading 1",
    "heading2": "K12 Heading 2",
    "heading3": "K12 Heading 3",
    "heading4": "K12 Heading 4",
    "body": "K12 Body",
    "list": "K12 List",
    "toc_title": "K12 TOC Title",
    "toc_level1": "K12 TOC Level 1",
    "toc_level2": "K12 TOC Level 2",
    "caption": "K12 Caption",
    "table_header": "K12 Table Header",
    "table_body": "K12 Table Body",
    "table_note": "K12 Table Note",
    "photo_placeholder": "K12 Photo Placeholder",
    "header_footer": "K12 Header Footer",
}

HEADING_ROLES = {"heading1", "heading2", "heading3", "heading4"}
STRUCTURAL_ROLES = {"cover_title", "cover_metadata", "title", "subtitle", *HEADING_ROLES}

MAJOR_HEADINGS = {
    "摘要", "关键词", "引言", "前言", "研究背景", "问题提出", "研究缘起", "研究意义",
    "核心概念", "概念界定", "理论依据", "政策依据", "研究现状", "文献综述", "研究述评",
    "研究目标", "研究内容", "研究对象", "研究问题", "研究假设", "研究思路", "研究方法",
    "研究重点", "研究难点", "创新之处", "技术路线", "实施步骤", "实施方案", "研究过程",
    "阶段安排", "进度安排", "组织分工", "条件保障", "预期成果", "研究成果", "数据分析",
    "结果与分析", "研究结论", "主要结论", "研究成效", "研究局限", "问题与反思", "改进建议",
    "参考文献", "附录", "教学目标", "教学重点", "教学难点", "教学准备", "教学过程",
    "教学反思", "评价设计", "作业设计", "活动目标", "活动准备", "活动过程", "注意事项",
}

METADATA_RE = re.compile(
    r"^(课题名称|课题题目|课题|项目名称|课题负责人|负责人|承担单位|责任单位|所在学校|学校|"
    r"所属学科|学科|年级|班级|申报类别|课题类别|填表日期|编制日期|生成日期|日期|版本|主清单快照)\s*[：:]"
)
TERMINAL_SENTENCE_RE = re.compile(r"[。！？；!?;]$")


def normalized_text(paragraph) -> str:
    return re.sub(r"\s+", " ", paragraph.text).strip()


def explicit_role(paragraph) -> str | None:
    style_name = paragraph.style.name.strip().lower()
    for role, fixed_name in K12_STYLE_NAMES.items():
        if style_name == fixed_name.lower():
            return role
    return None


def short_heading_candidate(text: str, limit: int = 48) -> bool:
    return 0 < len(text) <= limit and not TERMINAL_SENTENCE_RE.search(text)


def semantic_role(paragraph, index: int, contract: dict, *, trust_k12_style: bool = True) -> str:
    """Return a role from explicit styles and conservative text semantics.

    ``index`` is the zero-based ordinal among non-empty body paragraphs. Setting
    ``trust_k12_style=False`` makes the result independent from styles already
    applied by this skill, which is used to detect heading/body role mistakes.
    """
    text = normalized_text(paragraph)
    style_name = paragraph.style.name.strip().lower()
    if trust_k12_style:
        role = explicit_role(paragraph)
        if role:
            return role
    if text.startswith("【待插入真实照片"):
        return "photo_placeholder"
    if text == "目录":
        return "toc_title"
    if style_name.startswith("toc 2") or "目录 2" in style_name:
        return "toc_level2"
    if style_name.startswith("toc") or "目录 1" in style_name:
        return "toc_level1"
    if re.match(r"^(图|表)\s*\d+(?:[.．-]\d+)?(?:\s|[：:])", text):
        return "caption"
    if index <= 15 and METADATA_RE.match(text):
        return "cover_metadata"
    if index <= 3 and re.fullmatch(r"【[^】]{2,60}】", text):
        return "subtitle"
    if "subtitle" in style_name or "副标题" in style_name:
        return "subtitle"
    if style_name in {"title", "标题", "document title"}:
        return "title"
    if style_name.startswith("heading 1") or style_name in {"标题 1", "标题1"}:
        return "heading1"
    if style_name.startswith("heading 2") or style_name in {"标题 2", "标题2"}:
        return "heading2"
    if style_name.startswith("heading 3") or style_name in {"标题 3", "标题3"}:
        return "heading3"
    if style_name.startswith("heading 4") or style_name in {"标题 4", "标题4"}:
        return "heading4"
    if index == 0:
        return "cover_title" if contract.get("contract_id") == "casebook-fixed" else "title"

    if short_heading_candidate(text):
        if re.match(r"^(第[一二三四五六七八九十百]+[章节部分篇]|[一二三四五六七八九十]+[、．.])", text):
            return "heading1"
        if re.match(r"^[（(][一二三四五六七八九十]+[）)]", text):
            return "heading2"
        if re.match(r"^\d+(?:\.\d+){1,2}(?:[、．.\s]|$)", text):
            return "heading3"
        if re.match(r"^[（(]\d+[）)]", text):
            return "heading4"
        bare = re.sub(r"[：:]$", "", text)
        if bare in MAJOR_HEADINGS:
            return "heading1"
        if text.endswith(("：", ":")) and len(text) <= 20:
            return "heading4"

    if re.match(r"^\d+[、．.]\s*", text):
        return contract.get("classification", {}).get("numbered_paragraph_role", "heading3")
    if re.match(r"^[•●□☐✓√-]\s*", text):
        return "list"
    return "body"


def semantic_conflict(actual_role: str, inferred_role: str, text: str) -> str | None:
    """Describe a strong semantic/style mismatch; ignore genuinely ambiguous text."""
    if actual_role in {"body", "list"} and inferred_role in STRUCTURAL_ROLES:
        return f"疑似{inferred_role}却套用了{actual_role}"
    if actual_role in HEADING_ROLES and inferred_role == "body":
        if len(text) > 55 or TERMINAL_SENTENCE_RE.search(text):
            return f"疑似正文却套用了{actual_role}"
    if actual_role in {"title", "cover_title"} and inferred_role == "body" and len(text) > 80:
        return f"疑似正文却套用了{actual_role}"
    if actual_role == "cover_metadata" and inferred_role == "body" and not METADATA_RE.match(text):
        return "封面信息样式用于非封面字段"
    return None
