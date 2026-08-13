#!/usr/bin/env python3
"""Build topological, truth-aware generation jobs for every included project material."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from validate_project_manifest import validate

ROLE_CONTRACTS = {
    "attention-items": ("汇总真实性状态、阻断项、照片任务、原始材料、时间冲突、签章和增强建议", ("project_context", "problem_context", "governance", "timeline", "evidence", "subject_coverage", "materials")),
    "application": ("写清依据、问题证据、研究目标、内容、方法、创新、团队基础、计划和承诺成果", ("project", "project_context", "problem_context", "research_questions", "logic_mappings", "timeline", "commitments")),
    "anonymous-form": ("从申请书提炼匿名评审内容并清除身份线索，不改变研究承诺", ("project", "project_context", "problem_context", "research_questions", "logic_mappings", "commitments")),
    "opening": ("把申请承诺操作化为指标、任务、样本、工具、时间、分工、风险和质量控制", ("project_context", "problem_context", "logic_mappings", "samples", "instruments", "timeline", "interventions")),
    "consent-form": ("形成适龄告知、数据使用、照片授权、退出机制和联系方式留空区", ("project", "evidence", "governance")),
    "blank-instrument": ("设计与研究问题和学科表现对应的调查或诊断工具，并提供使用说明", ("project_context", "problem_context", "research_questions", "subject_coverage", "instruments")),
    "interview-guide": ("设计对象明确、从事实到解释递进且避免诱导的访谈提纲", ("research_questions", "samples", "instruments")),
    "observation-form": ("设计可观察行为、频次或等级、情境备注和观察者一致性字段", ("research_questions", "subject_coverage", "instruments")),
    "assessment-tool": ("形成前后测、迁移任务或作品评价工具及评分细则，保持同构而非照抄", ("research_questions", "subject_coverage", "evaluation_weights")),
    "data-workbook": ("从主清单填充项目说明、变量编码、证据、照片和材料进度，保留真实数据空区", ("project", "project_context", "problem_context", "samples", "instruments", "evidence", "materials")),
    "raw-data": ("建立原始记录、版本、保管位置、授权、哈希和匿名化索引", ("instruments", "evidence", "governance")),
    "analysis-report": ("只依据已收集数据说明样本、清理、统计或编码、三角互证、反例和局限", ("samples", "instruments", "evidence", "claims")),
    "intervention-plan": ("把诊断问题映射到核心策略、实施课次、载体、评价、证据和偏离记录", ("project_context", "problem_context", "logic_mappings", "interventions", "subject_coverage", "timeline")),
    "lesson-plan": ("按学科目标—任务—成果—评价设计可实施课例并登记版本和安全要求", ("project_context", "problem_context", "interventions", "subject_coverage", "evaluation_weights")),
    "task-sheet": ("提供与课例目标一致、学生可直接使用、留有真实作答空间的任务单或支架", ("interventions", "subject_coverage")),
    "rubric": ("设计可观察、互斥、分级清晰的成果量规并与工作簿变量一致", ("evaluation_weights", "subject_coverage", "research_questions")),
    "casebook": ("区分设计、试教、实施、验证状态；记录背景、行动、证据、偏离、反思和改进", ("cases", "interventions", "evidence", "contributors")),
    "fidelity-log": ("记录核心成分、计划与实际课次、覆盖、执行质量、偏离及证据ID", ("interventions", "timeline", "evidence")),
    "meeting-record": ("建立教研活动的真实日期、人员、议题、决定、任务和附件索引", ("contributors", "timeline", "evidence")),
    "progress-report": ("对照申请和开题说明真实进展、阶段证据、问题、调整和下一步", ("commitments", "interventions", "claims", "timeline")),
    "evidence-book": ("按照片/作品ID编排真实证据、图题、日期、授权、材料引用和证据边界", ("evidence", "claims", "cases")),
    "final-report": ("逐项回答研究问题，呈现方法、真实数据、结果、讨论、结论、局限和成果核销", ("research_questions", "logic_mappings", "evidence", "claims", "commitments")),
    "closing-application": ("按官方结题模板提炼成果、过程、鉴定事项和真人签章区", ("project", "timeline", "commitments", "claims")),
    "achievement-catalog": ("逐项对照申请承诺登记成果名称、作者、文件、完成日、证据和变更", ("commitments", "contributors", "cases")),
    "proof": ("索引发表、获奖、应用、推广、专家评议等真实证明，不代写意见或签字", ("commitments", "evidence", "contributors")),
    "index": ("从主清单刷新全部材料的名称、状态、路径、哈希、版本、依赖和待办", ("materials", "generation_contract")),
}

TRUTH_REQUIREMENTS = {
    "pending-data": ["真实原始数据或实施记录"],
    "pending-photo": ["真实照片/作品原件、授权和登记"],
    "pending-signature": ["真人意见、签名或单位盖章"],
}

REFERENCE_ROUTING = {
    "application": ["material-specifications.md", "guizhou-qiandongnan.md", "format-and-tables.md"],
    "anonymous-form": ["material-specifications.md", "research-integrity-and-delivery.md", "format-and-tables.md"],
    "opening": ["material-specifications.md", "methods-and-evidence.md", "timeline-and-quality.md", "format-and-tables.md"],
    "data-workbook": ["spreadsheet-standards.md", "methods-and-evidence.md"],
    "analysis-report": ["material-specifications.md", "methods-and-evidence.md", "spreadsheet-standards.md"],
    "lesson-plan": ["material-specifications.md", "subject-specific-evidence.md", "format-and-tables.md"],
    "casebook": ["material-specifications.md", "subject-authorship-and-implementation.md", "photo-evidence-and-placement.md"],
    "evidence-book": ["photo-evidence-and-placement.md", "research-integrity-and-delivery.md", "format-and-tables.md"],
    "final-report": ["material-specifications.md", "methods-and-evidence.md", "package-finalization.md"],
    "closing-application": ["material-specifications.md", "guizhou-qiandongnan.md", "package-finalization.md"],
    "attention-items": ["attention-items-file.md", "subject-specific-evidence.md"],
}

DEFAULT_REFERENCES = ["material-specifications.md", "subject-specific-evidence.md", "format-and-tables.md"]


def topological_waves(materials: list[dict]) -> list[list[str]]:
    ids = {item["id"] for item in materials}
    remaining = {item["id"]: {dep for dep in item.get("depends_on", []) if dep in ids} for item in materials}
    waves: list[list[str]] = []
    completed: set[str] = set()
    while remaining:
        wave = sorted(item_id for item_id, deps in remaining.items() if deps <= completed)
        if not wave:
            raise ValueError("材料依赖存在循环或无法解析")
        waves.append(wave)
        completed.update(wave)
        for item_id in wave:
            remaining.pop(item_id)
    return waves


def truth_inputs_ready(manifest: dict, status: str) -> bool:
    """Return whether a pending skeleton has newly registered real inputs to process."""
    collected = [
        item for item in manifest.get("evidence", [])
        if item.get("status") in {"collected", "verified", "completed"}
    ]
    if status == "pending-photo":
        return any(item.get("type") == "photo" for item in collected)
    if status == "pending-data":
        samples = manifest.get("samples", [])
        sample_counts_ready = bool(samples) and all(item.get("actual_n") is not None for item in samples)
        non_photo_evidence_ready = any(item.get("type") not in {"photo", "approval"} for item in collected)
        return sample_counts_ready and non_photo_evidence_ready
    return False


def build(manifest: dict) -> dict:
    errors, warnings = validate(manifest)
    if errors:
        raise ValueError("主清单未通过校验：" + "；".join(errors))
    materials = [item for item in manifest["materials"] if item.get("included_in_batch")]
    waves = topological_waves(materials)
    wave_by_id = {item_id: index for index, wave in enumerate(waves, 1) for item_id in wave}
    jobs = []
    for item in materials:
        role = item["material_role"]
        contract, source_fields = ROLE_CONTRACTS.get(role, ("按材料名称和主清单形成结构完整、可追溯的工作稿", ("project", "timeline")))
        blockers = list(TRUTH_REQUIREMENTS.get(item["status"], []))
        if item["format_profile"] == "official-exact" and not item.get("reference_template"):
            blockers.append("当年官方模板或用户指定同类模板")
        target_path = item.get("file_path") or item.get("planned_file_path")
        jobs.append({
            "job_id": f"JOB-{item['id']}", "material_id": item["id"], "name": item["name"],
            "wave": wave_by_id[item["id"]], "stage": item["stage"], "depends_on": item.get("depends_on", []),
            "current_status": item["status"], "target_path": target_path,
            "output_format": item["output_format"], "format_profile": item["format_profile"],
            "reference_template": item.get("reference_template"), "source_manifest_fields": list(source_fields),
            "required_skill_references": REFERENCE_ROUTING.get(role, DEFAULT_REFERENCES),
            "content_contract": contract,
            "truth_blockers_for_finalization": blockers,
            "execution_state": "waiting-dependency",
            "allowed_now": "生成结构和基于已登记事实的工作稿；缺失未来事实使用结构化待办，禁止编造",
            "work_action": "revise-and-qa" if item.get("file_path") else "create-and-qa",
            "completion_gate": ["内容QA", "格式QA", "逐页或逐表渲染QA", "隐私QA", "登记文件路径和SHA-256"],
        })
    by_id = {item["id"]: item for item in materials}
    terminal = {"ready", "submitted", "archived"}
    dependency_available = {"draft", "pending-data", "pending-photo", "pending-signature", *terminal}
    next_jobs = []
    blocked_jobs = []
    waiting_jobs = []
    for job in jobs:
        material = by_id[job["material_id"]]
        if material["status"] in terminal:
            job["execution_state"] = "complete"
            continue
        dependencies = [by_id[dep] for dep in job["depends_on"] if dep in by_id]
        if all(dep["status"] in dependency_available and dep.get("file_path") for dep in dependencies):
            if job["execution_state"] == "blocked-template":
                blocked_jobs.append(job["job_id"])
            elif any("当年官方模板或用户指定同类模板" == value for value in job["truth_blockers_for_finalization"]):
                job["execution_state"] = "blocked-template"
                blocked_jobs.append(job["job_id"])
            elif material["status"] in TRUTH_REQUIREMENTS and material.get("file_path") and not truth_inputs_ready(manifest, material["status"]):
                job["execution_state"] = "waiting-truth-input"
                job["waiting_for_truth_inputs"] = TRUTH_REQUIREMENTS[material["status"]]
                blocked_jobs.append(job["job_id"])
            else:
                job["execution_state"] = "executable"
                next_jobs.append(job["job_id"])
        else:
            missing_dependencies = [
                dep["id"] for dep in dependencies
                if dep["status"] not in dependency_available or not dep.get("file_path")
            ]
            job["waiting_for_material_ids"] = missing_dependencies
            waiting_jobs.append(job["job_id"])
    unfinished_jobs = [job["job_id"] for job in jobs if by_id[job["material_id"]]["status"] not in terminal]
    return {
        "schema_version": "1.1", "snapshot_id": manifest["generation_contract"].get("snapshot_id"),
        "package_scope": manifest["generation_contract"]["package_scope"],
        "truth_state": manifest["generation_contract"]["truth_state"],
        "warnings": warnings, "wave_count": len(waves), "waves": waves,
        "material_job_count": len(jobs), "unfinished_jobs": unfinished_jobs,
        "next_jobs": next_jobs, "blocked_jobs": blocked_jobs, "waiting_jobs": waiting_jobs, "jobs": jobs,
        "agent_loop": [
            "只处理依赖已满足的next_jobs", "从source_manifest_fields读取唯一事实，不在单份文档内另造事实",
            "用reference_template或对应通用母版制作文件", "完成内容、格式、渲染、隐私及适用的数据/照片QA",
            "用register_material_file.py登记文件和状态；待真实输入的骨架不得反复生成",
            "真实数据或照片登记进主清单后重新生成本计划，继续下一批，直到所有可完成任务处理完毕",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = build(manifest)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"任务计划生成失败：{exc}", file=sys.stderr)
        return 1
    print(args.out.resolve())
    print(f"材料任务：{result['material_job_count']}；依赖波次：{result['wave_count']}；当前可处理：{len(result['next_jobs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
