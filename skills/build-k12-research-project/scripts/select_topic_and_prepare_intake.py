#!/usr/bin/env python3
"""Freeze a selected topic and create an initializer-ready intake or a precise gap report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_AFTER_SELECTION = (
    ("application", "current_date"), ("application", "year"), ("application", "level"),
    ("application", "authority"), ("application", "package_scope"), ("application", "truth_state"),
    ("application", "project_status"), ("timeline", "application"), ("timeline", "completion"),
)


def nested(data: dict, *path: str):
    value = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def prepare(profile: dict, topics: dict, topic_id: str, title_override: str | None = None) -> dict:
    matches = [item for item in topics.get("candidates", []) if item.get("id") == topic_id]
    if len(matches) != 1:
        raise ValueError(f"未找到唯一候选题目：{topic_id}")
    selected = matches[0]
    selected_title = str(title_override or selected["title"]).strip()
    if not 8 <= len(selected_title) <= 80 or "\n" in selected_title or any(token in selected_title for token in ("【", "】", "待定")):
        raise ValueError("确认题目应为8—80个字符的单行规范题目，不能含占位符")
    missing = [".".join(path) for path in REQUIRED_AFTER_SELECTION if nested(profile, *path) in (None, "", [])]
    teaching = profile.get("teaching", {})
    teacher = profile.get("teacher", {})
    school = profile.get("school", {})
    related_subjects = [str(value) for value in teaching.get("related_subjects", [])]
    if selected.get("route", "").startswith("跨学科"):
        selected_subjects = [item["subject"] for item in selected.get("subject_coverage", [])]
        expected = [str(teaching.get("subject", "")), *related_subjects]
        if selected_subjects != expected:
            missing.append("候选题目的subject_coverage与教师信息不一致")
    result = {
        "schema_version": "1.0",
        "selected_topic_id": topic_id,
        "selected_title": selected_title,
        "base_candidate_title": selected["title"],
        "title_modified": selected_title != selected["title"],
        "ready_for_initialization": not missing,
        "missing_after_selection": missing,
        "next_action": "补齐缺失字段后重新运行本脚本" if missing else "运行initialize_project_package.py建立材料包",
    }
    if missing:
        result["confirmed_logic_summary"] = {
            "research_object_and_boundary": selected["research_object_and_boundary"],
            "core_problem": selected["core_problem"],
            "core_strategy": selected["core_strategy"],
            "expected_outputs": selected["expected_outputs"],
        }
        return result

    application = profile["application"]
    timeline = dict(profile["timeline"])
    timeline.setdefault("preliminary_research", None)
    timeline.setdefault("preliminary_label", None)
    subject_coverage = []
    for item in selected["subject_coverage"]:
        subject_coverage.append(
            {
                **item,
                "standards_reference": f"{item['subject']}现行课程标准及教材相应内容，正式材料须登记版本、条目或页码",
                "reviewer": teacher["name"],
                "review_status": "pending",
            }
        )
    questions = [{"id": f"Q{index}", "text": text} for index, text in enumerate(selected["research_questions"], 1)]
    mappings = []
    for question in questions:
        mappings.append(
            {
                "question_id": question["id"],
                "goal": "形成可观察、可实施、可反思的改进行动",
                "content": selected["core_strategy"],
                "method": "作品分析、课堂观察、访谈与适合本学科的测评或量规评价",
                "activity": "基线诊断、策略实施、过程反馈和迭代改进",
                "output": "、".join(selected["expected_outputs"]),
                "evidence": "、".join(selected["evidence_plan"]),
            }
        )
    intake = {
        "project": {
            "title": selected_title, "leader": teacher["name"], "school": school["name"],
            "subject": teaching["subject"], "related_subjects": related_subjects if len(subject_coverage) > 1 else [],
            "stage": teaching["stage"], "level": application["level"], "year": application["year"],
        },
        "governance": {
            "current_date": application["current_date"], "project_status": application["project_status"],
            "extension_approved_until": None, "consent_status": "planned", "data_cutoff": None,
        },
        "generation_contract": {
            "package_scope": application["package_scope"], "truth_state": application["truth_state"],
            "batch_mode": "single-snapshot", "unknown_handling": "structured-pending",
            "target_versions": profile.get("delivery", {}).get("target_versions", ["working", "submission"]),
            "coverage_exemptions": [],
        },
        "submission_requirements": {
            "status": "verified" if application.get("official_requirements_verified") else "pending",
            "authority": application["authority"], "year": application["year"],
            "verified_at": application.get("requirements_verified_at"), "deadline": application.get("deadline"),
            "notice_source_ids": application.get("notice_source_ids", []),
            "template_source_ids": application.get("template_source_ids", []),
            "required_material_ids": application.get("required_material_ids", []),
            "anonymous_required": application.get("anonymous_required"),
            "submission_mode": application.get("submission_mode", "pending"),
            "file_rules": application.get("file_rules", {"max_size_mb": None, "naming_rule": None, "copies": None}),
        },
        "contributors": [{
            "id": "P01", "name": teacher["name"], "role": "负责人", "is_approved_member": True,
            "affiliation": school["name"], "confirmed": True,
        }],
        "subject_coverage": subject_coverage,
        "timeline": timeline,
        "research_questions": questions,
        "logic_mappings": mappings,
        "samples": [{
            "name": "主要研究班级", "planned_n": teaching.get("student_count"), "actual_n": None, "data_source": None,
        }],
        "instruments": [{
            "id": "INS-01", "name": "学科表现诊断与过程评价工具", "status": "draft",
            "raw_evidence": None, "analysis_output": None,
        }],
        "evidence": [{
            "id": "E-BASELINE-01", "type": "raw-data", "status": "planned", "privacy_class": "confidential",
            "collected_date": None, "delivery_included": False, "source_file": None, "source_sha256": None,
            "custody_record": None, "consent_status": "planned",
        }, {
            "id": "PHO-PLAN-01", "type": "photo", "status": "planned", "privacy_class": "confidential",
            "collected_date": None, "location": None, "activity": "代表性课堂或实践活动",
            "photographer_source": None, "delivery_included": False, "source_file": None, "custody_record": None,
            "derivative_file": None, "original_sha256": None, "derivative_sha256": None,
            "consent_status": "planned", "publication_scope": "internal", "face_handling": "restricted-original",
            "caption": None, "alt_text": None, "material_ids": ["M20"], "claim_ids": [], "transformation_log": [],
        }],
        "interventions": [{
            "id": "INTV-01", "name": selected["core_strategy"], "status": "planned",
            "core_components": [selected["core_strategy"], "形成性反馈", "迭代改进"],
            "planned_dosage": profile.get("research_preferences", {}).get("planned_dosage", "待开题后按校历细化"),
            "actual_dosage": None, "coverage": None, "deviations": [], "evidence_ids": [],
        }],
        "cases": [{
            "id": "CASE-01", "title": f"{selected['core_strategy']}代表性实践案例", "status": "designed",
            "author_ids": ["P01"], "implementation": None, "evidence_ids": [],
        }],
        "sources": [],
        "commitments": [{
            "id": "OUT-01", "name": "最终研究报告", "promised_in": "M01", "due_date": timeline["completion"],
            "status": "planned", "material_ids": ["M21"], "change_approval_id": None,
        }],
        "claims": [{
            "id": "CLM-01", "text": "具体学习困难、变化及局限将在真实证据收集后确定",
            "status": "planned", "evidence_ids": [],
        }],
        "evaluation_weights": profile.get("research_preferences", {}).get("evaluation_weights", {}),
    }
    result["project_intake"] = intake
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--topics", type=Path, required=True)
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--title", help="在保留候选方向和逻辑的前提下确认修改后的最终题目")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--intake-out", type=Path)
    args = parser.parse_args()
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        topics = json.loads(args.topics.read_text(encoding="utf-8"))
        result = prepare(profile, topics, args.topic_id, args.title)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if result["ready_for_initialization"] and args.intake_out:
            args.intake_out.parent.mkdir(parents=True, exist_ok=True)
            args.intake_out.write_text(json.dumps(result["project_intake"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"选题确认失败：{exc}", file=sys.stderr)
        return 1
    print(args.out.resolve())
    if result["ready_for_initialization"] and args.intake_out:
        print(args.intake_out.resolve())
    return 0 if result["ready_for_initialization"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
