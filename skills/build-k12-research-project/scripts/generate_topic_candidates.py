#!/usr/bin/env python3
"""Generate 5-8 comparable, subject-aware project topics from a teacher profile."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from topic_blueprint import focus_for_problem, profile_for_subject

REQUIRED_PATHS = (
    ("teacher", "name"), ("school", "name"), ("school", "region"),
    ("teaching", "stage"), ("teaching", "subject"), ("teaching", "grade_classes"),
    ("problem", "description"),
)


def nested(data: dict, *path: str):
    value = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def validate_profile(profile: dict) -> list[str]:
    missing = [".".join(path) for path in REQUIRED_PATHS if nested(profile, *path) in (None, "", [])]
    related = nested(profile, "teaching", "related_subjects") or []
    if not isinstance(related, list):
        missing.append("teaching.related_subjects（必须是数组，可为空）")
    return missing


def _coverage(subject: str, related: list[str], include_related: bool) -> list[dict[str, str]]:
    result = [{"subject": subject, "role": "main", "research_function": "承担核心问题、主要教学行动和主要评价"}]
    if include_related:
        result.extend(
            {"subject": item, "role": "related", "research_function": "为真实任务提供必要知识、工具或成果表达"}
            for item in related
        )
    return result


def _candidate(
    candidate_id: str,
    title: str,
    route: str,
    profile: dict,
    strategy: str,
    evidence: list[str],
    outputs: list[str],
    innovation: str,
    difficulty: str,
    score: int,
    *,
    include_related: bool = False,
) -> dict:
    teaching = profile["teaching"]
    problem = profile["problem"]
    related = [str(value) for value in teaching.get("related_subjects", [])]
    grade_classes = teaching["grade_classes"]
    boundary = "、".join(str(value) for value in grade_classes)
    base_score = 64
    remaining = score - base_score
    innovation_score = max(7, min(10, remaining - 17))
    operability_score = remaining - innovation_score
    return {
        "id": candidate_id,
        "title": title,
        "route": route,
        "core_problem": str(problem["description"]),
        "research_object_and_boundary": f"{teaching['stage']}{boundary}；以本校常态教学为边界",
        "core_strategy": strategy,
        "research_questions": [
            f"{problem['description']}的主要表现和原因是什么？",
            f"如何将“{strategy}”转化为可执行、可观察的教学行动？",
            "学生作品、课堂表现和多源记录呈现出哪些变化、差异与局限？",
        ],
        "subject_coverage": _coverage(str(teaching["subject"]), related, include_related),
        "evidence_plan": evidence,
        "expected_outputs": outputs,
        "innovation": innovation,
        "difficulty": difficulty,
        "data_availability": "以现有班级常态教学、原始学习成果和过程记录为主，可在一个课题周期内取得",
        "risks": ["须先取得真实基线，不能预设效果", profile_for_subject(str(teaching["subject"])).special_review],
        "score": score,
        "score_explanation": {
            "problem_authenticity": 19,
            "policy_and_standard_fit": 13,
            "research_value": 13,
            "operability": operability_score,
            "evidence_availability": 14,
            "innovation": innovation_score,
            "title_quality": 5,
        },
    }


def generate(profile: dict, count: int = 6) -> dict:
    missing = validate_profile(profile)
    if missing:
        raise ValueError("生成选题前缺少：" + "，".join(missing))
    if not 5 <= count <= 8:
        raise ValueError("候选数量必须在5—8之间")
    teaching = profile["teaching"]
    subject = str(teaching["subject"])
    stage = str(teaching["stage"])
    related = [str(value) for value in teaching.get("related_subjects", [])]
    subject_profile = profile_for_subject(subject)
    focus = focus_for_problem(subject_profile, str(profile["problem"]["description"]))
    subject_context = "" if subject_profile.key in {"early", "special", "management"} else subject
    s1, s2, s3 = subject_profile.strategies
    evidence = list(subject_profile.primary_evidence)
    outputs = list(subject_profile.expected_outputs)
    candidates = [
        _candidate("TOPIC-01", f"{stage}{subject_context}{focus}困难诊断与改进研究", "诊断改进型", profile, s1,
                   evidence, outputs, "把真实错因或表现证据转化为分层改进任务", "较低", 88),
        _candidate("TOPIC-02", f"基于{s2}的{stage}{subject_context}{focus}实践研究", "策略行动型", profile, s2,
                   evidence, outputs, "形成“诊断—行动—反馈—再行动”的校本迭代链", "适中", 91),
        _candidate("TOPIC-03", f"{stage}{subject_context}{focus}形成性评价的实践研究", "评价改进型", profile, s3,
                   evidence, outputs, "把成果量规、过程反馈和学生自评纳入同一证据链", "适中", 89),
        _candidate("TOPIC-04", f"真实任务导向的{stage}{subject_context}{focus}教学研究", "任务实践型", profile,
                   f"真实任务＋{s1}", evidence, outputs, "用本校真实情境承载学科任务并保留原始成果", "适中", 87),
    ]
    if related:
        related_text = "、".join(related)
        candidates.extend([
            _candidate("TOPIC-05", f"{subject}与{related_text}融合的{focus}项目化学习研究", "跨学科项目型", profile,
                       f"以{subject}为主线、{related_text}提供必要工具或表达的项目任务", evidence,
                       outputs + ["跨学科项目成果"], "明确主学科目标和关联学科真实功能，避免学科拼盘", "较高", 86,
                       include_related=True),
            _candidate("TOPIC-06", f"真实问题驱动的{stage}{subject}跨学科任务设计研究", "跨学科任务型", profile,
                       f"主学科评价＋{related_text}协同支架", evidence, outputs, "分别设置各学科成果和复核责任", "较高", 84,
                       include_related=True),
            _candidate("TOPIC-07", f"基于学习档案的{stage}{subject_context}{focus}持续改进研究", "学习档案型", profile,
                       "多时点学习档案＋教师反馈", evidence, outputs, "以版本变化和反例记录呈现学习过程", "适中", 83),
            _candidate("TOPIC-08", f"同伴互助视域下{stage}{subject_context}{focus}课堂改进研究", "协同教研型", profile,
                       "同课异构＋课堂观察反馈", evidence, outputs + ["课堂观察改进记录"],
                       "把教师协同研修与学生学习证据建立直接联系", "较高", 82),
        ])
    else:
        candidates.extend([
            _candidate("TOPIC-05", f"乡土资源融入{stage}{subject_context}{focus}的实践研究", "乡土资源型", profile,
                       f"本地真实资源＋{s2}", evidence, outputs, "把贵州或黔东南可核验资源转化为学科任务，不作装饰性贴标签", "适中", 85),
            _candidate("TOPIC-06", f"基于学习档案的{stage}{subject_context}{focus}持续改进研究", "学习档案型", profile,
                       "多时点学习档案＋教师反馈", evidence, outputs, "以版本变化和反例记录呈现学习过程", "适中", 83),
            _candidate("TOPIC-07", f"同伴互助视域下{stage}{subject_context}{focus}课堂改进研究", "协同教研型", profile,
                       "同课异构＋课堂观察反馈", evidence, outputs + ["课堂观察改进记录"],
                       "把教师协同研修与学生学习证据建立直接联系", "较高", 82),
            _candidate("TOPIC-08", f"分层支持下{stage}{subject_context}{focus}差异化教学研究", "差异化支持型", profile,
                       "基线分层＋弹性任务＋个别反馈", evidence, outputs + ["分层支持方案"],
                       "以同一目标下的不同支架回应班级差异，避免固定标签", "较高", 81),
        ])
    candidates = candidates[:count]
    ranked = sorted(candidates, key=lambda item: (-item["score"], item["id"]))
    for rank, item in enumerate(ranked, 1):
        item["priority_rank"] = rank
        item["recommended"] = rank == 1
    return {
        "schema_version": "1.0",
        "generated_on": str(nested(profile, "application", "current_date") or date.today().isoformat()),
        "profile_summary": {
            "teacher": profile["teacher"]["name"], "school": profile["school"]["name"],
            "region": profile["school"]["region"], "stage": stage, "subject": subject,
            "related_subjects": related, "grade_classes": teaching["grade_classes"],
            "problem": profile["problem"]["description"],
        },
        "selection_rule": "选择一个研究中心；跨学科选题必须保留主学科并说明每个关联学科的真实功能",
        "candidates": ranked,
    }


def to_markdown(result: dict) -> str:
    lines = ["# 课题选题候选对比表", "", f"教师：{result['profile_summary']['teacher']}｜学科：{result['profile_summary']['subject']}", ""]
    for item in result["candidates"]:
        marker = "（优先推荐）" if item["recommended"] else ""
        coverage = "、".join(value["subject"] for value in item["subject_coverage"])
        lines.extend([
            f"## {item['priority_rank']}. {item['id']} {item['title']}{marker}", "",
            f"- 方向：{item['route']}；覆盖学科：{coverage}；综合评分：{item['score']}",
            f"- 核心问题：{item['core_problem']}", f"- 核心策略：{item['core_strategy']}",
            f"- 研究边界：{item['research_object_and_boundary']}",
            f"- 证据：{'、'.join(item['evidence_plan'])}", f"- 成果：{'、'.join(item['expected_outputs'])}",
            f"- 难度：{item['difficulty']}；创新点：{item['innovation']}", f"- 风险：{'；'.join(item['risks'])}", "",
        ])
    lines.extend(["## 选择方式", "", "回复候选ID（如 `TOPIC-02`）或提出题目修改意见；题目确认后再建立唯一项目主清单。", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--count", type=int, default=6)
    args = parser.parse_args()
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        result = generate(profile, args.count)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.markdown:
            args.markdown.parent.mkdir(parents=True, exist_ok=True)
            args.markdown.write_text(to_markdown(result), encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"选题生成失败：{exc}", file=sys.stderr)
        return 1
    print(args.out.resolve())
    if args.markdown:
        print(args.markdown.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
