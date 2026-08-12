#!/usr/bin/env python3
"""Shared sentinels and CLI rules for final-delivery audits."""

from __future__ import annotations

import re

# Do not flag every Chinese book-title bracket: official forms legitimately use
# brackets in headings. Only flag the controlled sentinel vocabulary used by the
# supplied working templates and common drafting placeholders.
PLACEHOLDER_RE = re.compile(
    r"(?:"
    r"待填写|待补充|待确认|待插入真实照片|待照片|待核验|待签章|"
    r"XXX+|\{\{[^{}]+\}\}|_{4,}|"
    r"[【\[]\s*(?:"
    r"填写|待[^】\]]*|根据[^】\]]*(?:生成|填写)|从[^】\]]*(?:生成|填写)|"
    r"基于[^】\]]*(?:生成|填写)|课题规范题目|课题简称|课题|姓名|学校全称|"
    r"版本和日期|批次日期|编码|年级班级|实际[^】\]]*|项目\d+|公式结果|"
    r"分母(?:/多选)?说明|工作簿名|工作表|区域|照片(?:/作品/观察/评价)?ID|"
    r"材料(?:/案例)?ID|案例ID|阶段|级别|类别|状态|日期|活动|隐私级别|"
    r"负责人|责任单位|教材版本[^】\]]*|证据ID|来源ID|CASE[^】\]]*|"
    r"PHO[^】\]]*|yyyy[^】\]]*|N\s*=\s*[^】\]]*"
    r")\s*[】\]]"
    r")",
    re.I,
)


def cli_failed(errors: list[str], warnings: list[str], final: bool) -> bool:
    """Final-mode warnings block a standalone audit, matching preflight."""

    return bool(errors or (final and warnings))
