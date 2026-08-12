#!/usr/bin/env python3
"""Validate basic identity, phase dates, and mappings in a project manifest JSON."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REQUIRED_PROJECT = ("title", "leader", "school", "subject", "stage")
FORMAT_PROFILES = {
    "official-exact",
    "research-form",
    "analysis-report",
    "lesson-table",
    "lesson-long",
    "casebook",
    "evidence-sheet",
    "attention-items",
    "spreadsheet-workbook",
}
PROJECT_STATUSES = {"planning", "application", "approved", "ongoing", "extended", "completed", "suspended", "terminated"}
MATERIAL_STAGES = {"application", "opening", "instrument", "data", "analysis", "intervention", "midterm", "final", "closing", "supporting"}
PRIVACY_CLASSES = {"confidential", "internal", "submission", "anonymous", "public"}
EVIDENCE_STATUSES = {"planned", "collected", "verified", "completed"}
EVIDENCE_TYPES = {"raw-data", "interview", "observation", "assessment", "student-work", "photo", "video", "document", "artifact", "approval", "dissemination"}
SOURCE_STATUSES = {"pending", "verified", "rejected"}
REQUIREMENT_STATUSES = {"pending", "verified", "expired"}
SUBMISSION_MODES = {"pending", "online", "offline", "mixed"}
CONSENT_STATUSES = {"planned", "pending", "obtained", "not-required", "restricted", "withdrawn"}
PUBLICATION_SCOPES = {"internal", "submission", "anonymous", "public"}
FACE_HANDLING = {"not-applicable", "no-identifiable-person", "back-view", "cropped", "blurred", "consented-identifiable", "restricted-original"}
MATERIAL_STATUSES = {"planned", "draft", "pending-data", "pending-photo", "pending-signature", "verified", "ready", "submitted", "archived"}
QA_STATUSES = {"pending", "passed", "failed", "not-applicable"}
QA_KEYS = {"content", "format", "render", "privacy", "data", "photo"}
CASE_STATUSES = {"designed", "piloted", "implemented", "validated"}
INTERVENTION_STATUSES = {"planned", "piloted", "implemented", "completed"}
COMMITMENT_STATUSES = {"planned", "in-progress", "fulfilled", "changed-approved", "not-fulfilled"}
INSTRUMENT_STATUSES = {"draft", "piloted", "ready", "collected", "analyzed", "completed"}
CLAIM_STATUSES = {"planned", "supported", "verified", "rejected", "completed"}
MATERIAL_ROLES = {
    "official-form", "application", "anonymous-form", "opening", "blank-instrument",
    "consent-form", "interview-guide", "observation-form", "assessment-tool", "codebook",
    "completed-record", "transcription", "raw-data", "data-workbook", "analysis-report",
    "intervention-plan", "lesson-plan", "task-sheet", "rubric", "case", "casebook",
    "fidelity-log", "meeting-record", "progress-report", "change-form", "photo-register",
    "final-report", "closing-application", "achievement-catalog", "expert-appraisal",
    "evidence-book", "proof", "index", "attention-items",
}
PACKAGE_SCOPES = {"application-kit", "implementation-kit", "full-lifecycle-kit", "closing-kit", "custom"}
TRUTH_STATES = {"planning", "implementing", "closing", "completed"}
DELIVERY_STATES = {"application-ready", "implementation-ready", "full-lifecycle-scaffold", "closing-ready"}
BATCH_MODES = {"single-snapshot", "incremental"}
UNKNOWN_HANDLING = {"structured-pending", "block-generation"}
TARGET_VERSIONS = {"working", "submission", "anonymous", "public"}
DATE_KEYS = (
    "application",
    "approval",
    "opening",
    "instrument_design",
    "pilot",
    "data_collection_start",
    "data_collection_end",
    "analysis",
    "intervention_start",
    "midterm",
    "intervention_end",
    "completion",
)


def parse_day(value: str, label: str, errors: list[str]) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{label} 必须使用 YYYY-MM-DD：{value!r}")
        return None


def validate(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    project = data.get("project")
    if not isinstance(project, dict):
        return ["缺少 project 对象"], warnings

    for key in REQUIRED_PROJECT:
        if not str(project.get(key, "")).strip():
            errors.append(f"project.{key} 不能为空")
    related_subjects = project.get("related_subjects", [])
    if not isinstance(related_subjects, list) or any(not str(value).strip() for value in related_subjects):
        errors.append("project.related_subjects如填写必须是非空字符串数组")
    elif str(project.get("subject", "")) in {str(value) for value in related_subjects}:
        warnings.append("project.related_subjects重复包含主学科，请去重")

    governance = data.get("governance", {})
    if not isinstance(governance, dict):
        errors.append("governance 必须是对象")
        governance = {}
    project_status = str(governance.get("project_status", "")).strip()
    if project_status not in PROJECT_STATUSES:
        errors.append(f"governance.project_status 缺少有效状态：{project_status!r}")
    current_day = parse_day(str(governance.get("current_date", date.today().isoformat())), "governance.current_date", errors)

    generation = data.get("generation_contract")
    if not isinstance(generation, dict):
        errors.append("缺少 generation_contract 对象；必须声明成套范围和真实性阶段")
        generation = {}
    if generation.get("package_scope") not in PACKAGE_SCOPES:
        errors.append("generation_contract.package_scope 缺少有效值")
    if generation.get("truth_state") not in TRUTH_STATES:
        errors.append("generation_contract.truth_state 缺少有效值")
    if generation.get("delivery_state") not in DELIVERY_STATES:
        errors.append("generation_contract.delivery_state 缺少有效值")
    if generation.get("batch_mode") not in BATCH_MODES:
        errors.append("generation_contract.batch_mode 缺少有效值")
    if generation.get("unknown_handling") not in UNKNOWN_HANDLING:
        errors.append("generation_contract.unknown_handling 缺少有效值")
    target_versions = generation.get("target_versions")
    if not isinstance(target_versions, list) or not target_versions:
        errors.append("generation_contract.target_versions 必须是非空数组")
    elif any(value not in TARGET_VERSIONS for value in target_versions):
        errors.append("generation_contract.target_versions 含无效版本")
    exemptions = generation.get("coverage_exemptions")
    if not isinstance(exemptions, list):
        errors.append("generation_contract.coverage_exemptions 必须是数组")
    else:
        for index, exemption in enumerate(exemptions, 1):
            if not isinstance(exemption, dict) or not exemption.get("group") or not exemption.get("reason"):
                errors.append(f"generation_contract.coverage_exemptions[{index}] 必须包含group和reason")
    delivery_state = generation.get("delivery_state")
    truth_state = generation.get("truth_state")
    package_scope = generation.get("package_scope")
    state_rules = {
        "application-ready": {"planning"},
        "implementation-ready": {"implementing"},
        "full-lifecycle-scaffold": {"planning", "implementing"},
        "closing-ready": {"closing", "completed"},
    }
    if delivery_state in state_rules and truth_state not in state_rules[delivery_state]:
        errors.append(f"delivery_state为{delivery_state}时，truth_state必须属于{sorted(state_rules[delivery_state])}")
    scope_rules = {
        "application-ready": {"application-kit", "custom"},
        "implementation-ready": {"implementation-kit", "full-lifecycle-kit", "custom"},
        "full-lifecycle-scaffold": {"full-lifecycle-kit", "custom"},
        "closing-ready": {"closing-kit", "full-lifecycle-kit", "custom"},
    }
    if delivery_state in scope_rules and package_scope not in scope_rules[delivery_state]:
        errors.append(f"delivery_state为{delivery_state}时，package_scope不应为{package_scope!r}")

    contributors = data.get("contributors", [])
    if not isinstance(contributors, list) or not contributors:
        errors.append("contributors 至少包含负责人")
        contributors = []
    contributor_ids: set[str] = set()
    for index, item in enumerate(contributors, 1):
        if not isinstance(item, dict):
            errors.append(f"contributors[{index}] 必须是对象")
            continue
        contributor_id = str(item.get("id", "")).strip()
        if not contributor_id:
            errors.append(f"contributors[{index}].id 不能为空")
        elif contributor_id in contributor_ids:
            errors.append(f"contributors 存在重复 id：{contributor_id}")
        contributor_ids.add(contributor_id)
        for key in ("name", "role", "affiliation"):
            if not str(item.get(key, "")).strip():
                errors.append(f"contributors[{index}].{key} 不能为空")
        if not isinstance(item.get("is_approved_member"), bool):
            errors.append(f"contributors[{index}].is_approved_member 必须是布尔值")

    timeline = data.get("timeline", {})
    if not isinstance(timeline, dict):
        errors.append("timeline 必须是对象")
        timeline = {}
    parsed = {key: parse_day(str(timeline.get(key, "")), f"timeline.{key}", errors) for key in DATE_KEYS}
    present = [(key, parsed[key]) for key in DATE_KEYS if parsed[key] is not None]
    for (left_key, left), (right_key, right) in zip(present, present[1:]):
        if left > right:
            errors.append(f"时间倒序：{left_key}({left}) 晚于 {right_key}({right})")

    completion = parsed.get("completion")
    if current_day and completion and current_day > completion and project_status not in {"completed", "extended", "terminated"}:
        errors.append(f"计划完成日{completion}已过，但项目状态仍为{project_status or '未填写'}；请登记结题、获批延期或终止")
    extension_day = None
    if governance.get("extension_approved_until"):
        extension_day = parse_day(str(governance.get("extension_approved_until")), "governance.extension_approved_until", errors)
    if project_status == "extended":
        if extension_day is None:
            errors.append("项目状态为extended时必须填写governance.extension_approved_until")
        elif completion and extension_day <= completion:
            errors.append("获批延期日期必须晚于原计划完成日期")
        elif current_day and extension_day < current_day:
            warnings.append("获批延期日期也已过去，请更新项目状态或补充新的批准记录")

    preliminary = timeline.get("preliminary_research")
    if preliminary:
        preliminary_day = parse_day(str(preliminary), "timeline.preliminary_research", errors)
        approval = parsed.get("approval")
        if preliminary_day and approval and preliminary_day < approval and not timeline.get("preliminary_label"):
            warnings.append("立项前已有研究活动，请填写 timeline.preliminary_label，明确为前期研究/预调查")

    questions = data.get("research_questions", [])
    mappings = data.get("logic_mappings", [])
    if not isinstance(questions, list) or not questions:
        errors.append("research_questions 至少包含一项")
        questions = []
    if not isinstance(mappings, list):
        errors.append("logic_mappings 必须是数组")
        mappings = []
    mapped = {str(item.get("question_id")) for item in mappings if isinstance(item, dict)}
    question_ids: set[str] = set()
    for item in questions:
        qid = str(item.get("id", "")) if isinstance(item, dict) else ""
        if not qid:
            errors.append("每个 research_questions 项必须有 id")
        elif qid in question_ids:
            errors.append(f"research_questions 存在重复 id：{qid}")
        elif qid not in mapped:
            errors.append(f"研究问题 {qid} 缺少 logic_mappings")
        question_ids.add(qid)

    needed = ("goal", "content", "method", "activity", "output", "evidence")
    for index, item in enumerate(mappings, 1):
        if not isinstance(item, dict):
            errors.append(f"logic_mappings[{index}] 必须是对象")
            continue
        question_id = str(item.get("question_id", ""))
        if not question_id:
            errors.append(f"logic_mappings[{index}].question_id 不能为空")
        elif question_id not in question_ids:
            errors.append(f"logic_mappings[{index}] 引用了不存在的研究问题：{question_id}")
        for key in needed:
            if not item.get(key):
                errors.append(f"logic_mappings[{index}].{key} 不能为空")

    samples = data.get("samples", [])
    if samples and not isinstance(samples, list):
        errors.append("samples 必须是数组")
    for index, sample in enumerate(samples if isinstance(samples, list) else [], 1):
        if not isinstance(sample, dict):
            errors.append(f"samples[{index}] 必须是对象")
            continue
        planned = sample.get("planned_n")
        actual = sample.get("actual_n")
        if planned is not None and (not isinstance(planned, int) or planned < 0):
            errors.append(f"samples[{index}].planned_n 必须是非负整数")
        if actual is not None and (not isinstance(actual, int) or actual < 0):
            errors.append(f"samples[{index}].actual_n 必须是非负整数")
        if actual is not None and not sample.get("data_source"):
            warnings.append(f"samples[{index}] 已填写实际样本量，但未填写 data_source")

    instruments = data.get("instruments", [])
    if instruments and not isinstance(instruments, list):
        errors.append("instruments 必须是数组")
        instruments = []
    instrument_ids: set[str] = set()
    for index, item in enumerate(instruments, 1):
        if not isinstance(item, dict):
            errors.append(f"instruments[{index}] 必须是对象")
            continue
        iid = str(item.get("id", "")).strip()
        if not iid:
            errors.append(f"instruments[{index}].id 不能为空")
        elif iid in instrument_ids:
            errors.append(f"instruments 存在重复 id：{iid}")
        instrument_ids.add(iid)
        if item.get("status") not in INSTRUMENT_STATUSES:
            errors.append(f"工具 {iid or index} 缺少有效 status")
        if item.get("status") in {"collected", "analyzed", "completed"} and not item.get("raw_evidence"):
            errors.append(f"工具 {iid or index} 已标记为 {item.get('status')}，但缺少 raw_evidence")
        if item.get("status") in {"analyzed", "completed"} and not item.get("analysis_output"):
            errors.append(f"工具 {iid or index} 已完成分析，但缺少 analysis_output")

    evidence = data.get("evidence", [])
    if evidence and not isinstance(evidence, list):
        errors.append("evidence 必须是数组")
        evidence = []
    evidence_ids: set[str] = set()
    photo_ids: set[str] = set()
    evidence_items: dict[str, dict] = {}
    for index, item in enumerate(evidence, 1):
        if not isinstance(item, dict):
            errors.append(f"evidence[{index}] 必须是对象")
            continue
        eid = str(item.get("id", "")).strip()
        if not eid:
            errors.append(f"evidence[{index}].id 不能为空")
        elif eid in evidence_ids:
            errors.append(f"evidence 存在重复 id：{eid}")
        evidence_ids.add(eid)
        if eid:
            evidence_items[eid] = item
        if item.get("type") not in EVIDENCE_TYPES:
            errors.append(f"证据 {eid or index} 缺少有效 type")
        if item.get("status") not in EVIDENCE_STATUSES:
            errors.append(f"证据 {eid or index} 缺少有效 status")
        if item.get("privacy_class") not in PRIVACY_CLASSES:
            errors.append(f"证据 {eid or index} 缺少有效 privacy_class")
        if item.get("status") in {"collected", "verified", "completed"}:
            delivery_included = item.get("delivery_included")
            if not isinstance(delivery_included, bool):
                errors.append(f"证据 {eid or index} 已采集/核验，delivery_included必须是布尔值")
            elif delivery_included and not item.get("source_file"):
                errors.append(f"证据 {eid or index} 声明随包交付，但缺少 source_file")
            elif delivery_included is False:
                custody = item.get("custody_record")
                if not isinstance(custody, dict):
                    errors.append(f"证据 {eid or index} 不随包交付，但缺少 custody_record 对象")
                else:
                    for key in ("owner", "locator", "verified_at"):
                        if not str(custody.get(key, "")).strip():
                            errors.append(f"证据 {eid or index}.custody_record.{key} 不能为空")
                    if custody.get("verified_at"):
                        parse_day(str(custody.get("verified_at")), f"evidence[{index}].custody_record.verified_at", errors)
            if not item.get("collected_date"):
                errors.append(f"证据 {eid or index} 已采集/核验，但缺少 collected_date")
            else:
                parse_day(str(item.get("collected_date")), f"evidence[{index}].collected_date", errors)
        consent_status = item.get("consent_status")
        if consent_status is not None and consent_status not in CONSENT_STATUSES:
            errors.append(f"证据 {eid or index} 缺少有效 consent_status")
        if item.get("type") == "photo":
            photo_ids.add(eid)
            if not eid.startswith("PHO-"):
                warnings.append(f"照片证据 {eid or index} 建议使用PHO-年份-序号格式")
            if consent_status not in CONSENT_STATUSES:
                errors.append(f"照片 {eid or index} 必须登记 consent_status")
            if item.get("publication_scope") not in PUBLICATION_SCOPES:
                errors.append(f"照片 {eid or index} 缺少有效 publication_scope")
            if item.get("face_handling") not in FACE_HANDLING:
                errors.append(f"照片 {eid or index} 缺少有效 face_handling")
            if item.get("status") in {"collected", "verified", "completed"}:
                for key in ("location", "activity", "photographer_source", "derivative_file", "original_sha256", "derivative_sha256", "caption", "alt_text", "material_ids"):
                    if not item.get(key):
                        errors.append(f"照片 {eid or index} 已采集/核验，但缺少 {key}")
                if "transformation_log" not in item or not isinstance(item.get("transformation_log"), list):
                    errors.append(f"照片 {eid or index} 必须包含数组 transformation_log；未处理时使用空数组")
                for digest_key in ("original_sha256", "derivative_sha256"):
                    digest = str(item.get(digest_key, ""))
                    if digest and (len(digest) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in digest)):
                        errors.append(f"照片 {eid or index}.{digest_key} 必须是64位SHA-256十六进制值")
            if item.get("publication_scope") in {"anonymous", "public"} and item.get("status") in {"collected", "verified", "completed"}:
                if consent_status not in {"obtained", "not-required"}:
                    errors.append(f"照片 {eid or index} 用于匿名/公开版本，但授权状态不是obtained或not-required")
                if item.get("face_handling") not in {"not-applicable", "no-identifiable-person", "back-view", "cropped", "blurred", "consented-identifiable"}:
                    errors.append(f"照片 {eid or index} 用于匿名/公开版本，但人物处理状态不合格")

    interventions = data.get("interventions", [])
    if interventions and not isinstance(interventions, list):
        errors.append("interventions 必须是数组")
        interventions = []
    intervention_ids: set[str] = set()
    for index, item in enumerate(interventions, 1):
        if not isinstance(item, dict):
            errors.append(f"interventions[{index}] 必须是对象")
            continue
        intervention_id = str(item.get("id", "")).strip()
        if not intervention_id:
            errors.append(f"interventions[{index}].id 不能为空")
        elif intervention_id in intervention_ids:
            errors.append(f"interventions 存在重复 id：{intervention_id}")
        intervention_ids.add(intervention_id)
        if item.get("status") not in INTERVENTION_STATUSES:
            errors.append(f"干预 {intervention_id or index} 缺少有效 status")
        if not item.get("core_components") or not item.get("planned_dosage"):
            errors.append(f"干预 {intervention_id or index} 缺少核心成分或计划剂量")
        if item.get("status") in {"implemented", "completed"}:
            for key in ("actual_dosage", "coverage", "evidence_ids"):
                if not item.get(key):
                    errors.append(f"干预 {intervention_id or index} 已实施，但缺少 {key}")
        for evidence_id in item.get("evidence_ids", []):
            if evidence_id not in evidence_ids:
                errors.append(f"干预 {intervention_id or index} 引用了不存在的证据：{evidence_id}")

    cases = data.get("cases", [])
    if cases and not isinstance(cases, list):
        errors.append("cases 必须是数组")
        cases = []
    case_ids: set[str] = set()
    for index, item in enumerate(cases, 1):
        if not isinstance(item, dict):
            errors.append(f"cases[{index}] 必须是对象")
            continue
        case_id = str(item.get("id", "")).strip()
        if not case_id:
            errors.append(f"cases[{index}].id 不能为空")
        elif case_id in case_ids:
            errors.append(f"cases 存在重复 id：{case_id}")
        case_ids.add(case_id)
        if item.get("status") not in CASE_STATUSES:
            errors.append(f"案例 {case_id or index} 缺少有效 status")
        for author_id in item.get("author_ids", []):
            if author_id not in contributor_ids:
                errors.append(f"案例 {case_id or index} 引用了未登记作者/协作者：{author_id}")
        for evidence_id in item.get("evidence_ids", []):
            if evidence_id not in evidence_ids:
                errors.append(f"案例 {case_id or index} 引用了不存在的证据：{evidence_id}")
        if item.get("status") in {"implemented", "validated"}:
            implementation = item.get("implementation")
            if not isinstance(implementation, dict):
                errors.append(f"案例 {case_id or index} 标记为已实施/验证，但缺少 implementation")
            else:
                for key in ("date", "school", "grade_class", "teacher_ids", "participant_n", "actual_periods", "material_version", "deviations", "data_cutoff"):
                    if implementation.get(key) in (None, "", []):
                        errors.append(f"案例 {case_id or index}.implementation 缺少 {key}")
                if implementation.get("date"):
                    parse_day(str(implementation.get("date")), f"案例{case_id}.implementation.date", errors)
                for teacher_id in implementation.get("teacher_ids", []):
                    if teacher_id not in contributor_ids:
                        errors.append(f"案例 {case_id or index} 的实施教师未登记：{teacher_id}")
            if not item.get("evidence_ids"):
                errors.append(f"案例 {case_id or index} 标记为已实施/验证，但没有 evidence_ids")

    sources = data.get("sources", [])
    if sources and not isinstance(sources, list):
        errors.append("sources 必须是数组")
        sources = []
    source_ids: set[str] = set()
    source_items: dict[str, dict] = {}
    for index, item in enumerate(sources, 1):
        if not isinstance(item, dict):
            errors.append(f"sources[{index}] 必须是对象")
            continue
        sid = str(item.get("id", "")).strip()
        if not sid:
            errors.append(f"sources[{index}].id 不能为空")
        elif sid in source_ids:
            errors.append(f"sources 存在重复 id：{sid}")
        source_ids.add(sid)
        if sid:
            source_items[sid] = item
        if item.get("verification_status") not in SOURCE_STATUSES:
            errors.append(f"来源 {sid or index} 缺少有效 verification_status")
        if item.get("verification_status") == "verified":
            if not item.get("locator"):
                errors.append(f"来源 {sid or index} 已核验，但缺少 locator")
            if not item.get("verified_at"):
                errors.append(f"来源 {sid or index} 已核验，但缺少 verified_at")
            else:
                parse_day(str(item.get("verified_at")), f"来源{sid}.verified_at", errors)
        valid_for_year = item.get("valid_for_year")
        if valid_for_year is not None and (not isinstance(valid_for_year, int) or valid_for_year < 2000):
            errors.append(f"来源 {sid or index}.valid_for_year 必须是合理年份整数")

    materials = data.get("materials", [])
    if materials and not isinstance(materials, list):
        errors.append("materials 必须是数组")
        materials = []
    material_items = [item for item in materials if isinstance(item, dict) and item.get("id")]
    material_ids = {str(item.get("id")) for item in material_items}
    if len(material_ids) != len(material_items):
        errors.append("materials 存在重复 id")

    requirements = data.get("submission_requirements")
    if not isinstance(requirements, dict):
        errors.append("缺少 submission_requirements 对象；必须登记当年通知、模板和报送要求核验快照")
        requirements = {}
    requirement_status = str(requirements.get("status", "")).strip()
    if requirement_status not in REQUIREMENT_STATUSES:
        errors.append(f"submission_requirements.status 缺少有效状态：{requirement_status!r}")
    if not str(requirements.get("authority", "")).strip():
        errors.append("submission_requirements.authority 不能为空")
    requirement_year = requirements.get("year")
    if not isinstance(requirement_year, int) or requirement_year < 2000:
        errors.append("submission_requirements.year 必须是合理年份整数")
    elif isinstance(project.get("year"), int) and requirement_year != project.get("year"):
        warnings.append("submission_requirements.year 与 project.year 不一致，请确认是否套用了其他年度要求")
    if requirements.get("submission_mode") not in SUBMISSION_MODES:
        errors.append("submission_requirements.submission_mode 必须是pending/online/offline/mixed")

    notice_source_ids = requirements.get("notice_source_ids", [])
    template_source_ids = requirements.get("template_source_ids", [])
    required_material_ids = requirements.get("required_material_ids", [])
    for key, values, known in (
        ("notice_source_ids", notice_source_ids, source_ids),
        ("template_source_ids", template_source_ids, source_ids),
        ("required_material_ids", required_material_ids, material_ids),
    ):
        if not isinstance(values, list):
            errors.append(f"submission_requirements.{key} 必须是数组")
            continue
        for value in values:
            if str(value) not in known:
                errors.append(f"submission_requirements.{key} 引用了不存在的ID：{value}")

    if requirement_status == "verified":
        if not requirements.get("verified_at"):
            errors.append("submission_requirements 已核验，但缺少 verified_at")
        else:
            parse_day(str(requirements.get("verified_at")), "submission_requirements.verified_at", errors)
        if requirements.get("deadline"):
            parse_day(str(requirements.get("deadline")), "submission_requirements.deadline", errors)
        if not notice_source_ids:
            errors.append("submission_requirements 已核验，但 notice_source_ids 为空")
        if not template_source_ids:
            errors.append("submission_requirements 已核验，但 template_source_ids 为空")
        for source_id in set(notice_source_ids + template_source_ids):
            source = source_items.get(str(source_id), {})
            if source.get("verification_status") != "verified":
                errors.append(f"submission_requirements 已核验，但来源{source_id}尚未标记verified")
            if requirement_year and source.get("valid_for_year") not in {None, requirement_year}:
                errors.append(f"来源{source_id}适用年度与submission_requirements.year不一致")
    elif requirement_status == "expired":
        warnings.append("当年报送要求快照已过期；不得据此制作可直接提交版本")
    for index, item in enumerate(materials, 1):
        if not isinstance(item, dict):
            errors.append(f"materials[{index}] 必须是对象")
            continue
        if not item.get("id") or not item.get("name"):
            errors.append(f"materials[{index}] 必须包含 id 和 name")
        if item.get("material_role") not in MATERIAL_ROLES:
            errors.append(f"材料 {item.get('id', index)} 缺少有效 material_role")
        if item.get("status") not in MATERIAL_STATUSES:
            errors.append(f"材料 {item.get('id', index)} 缺少有效 status")
        output_format = str(item.get("output_format", "")).lower()
        if output_format not in {"doc", "docx", "xlsx", "pdf"}:
            errors.append(f"材料 {item.get('id', index)} 缺少有效 output_format")
        format_profile = item.get("format_profile")
        if format_profile not in FORMAT_PROFILES:
            errors.append(f"材料 {item.get('id', index)} 缺少有效 format_profile")
        if format_profile == "official-exact" and not item.get("reference_template"):
            warnings.append(f"材料 {item.get('id', index)} 使用official-exact，但尚未登记reference_template")
        if output_format == "xlsx" and format_profile != "spreadsheet-workbook":
            errors.append(f"XLSX材料 {item.get('id', index)} 应使用spreadsheet-workbook格式")
        required_sheets = item.get("required_sheets", [])
        if output_format == "xlsx":
            if not isinstance(required_sheets, list) or not required_sheets or not all(str(value).strip() for value in required_sheets):
                errors.append(f"XLSX材料 {item.get('id', index)}.required_sheets 必须是非空名称数组")
            elif len(set(required_sheets)) != len(required_sheets):
                errors.append(f"XLSX材料 {item.get('id', index)}.required_sheets 存在重复名称")
            allowed_hidden = item.get("allowed_hidden_sheets", [])
            if not isinstance(allowed_hidden, list) or not all(str(value).strip() for value in allowed_hidden):
                errors.append(f"XLSX材料 {item.get('id', index)}.allowed_hidden_sheets 必须是名称数组；无隐藏表时使用空数组")
            elif len(set(allowed_hidden)) != len(allowed_hidden):
                errors.append(f"XLSX材料 {item.get('id', index)}.allowed_hidden_sheets 存在重复名称")
        if item.get("stage") not in MATERIAL_STAGES:
            errors.append(f"材料 {item.get('id', index)} 缺少有效 stage")
        if item.get("privacy_class") not in PRIVACY_CLASSES:
            errors.append(f"材料 {item.get('id', index)} 缺少有效 privacy_class")
        if not str(item.get("version", "")).strip():
            errors.append(f"材料 {item.get('id', index)} 缺少 version")
        if not isinstance(item.get("required_for_submission"), bool):
            errors.append(f"材料 {item.get('id', index)}.required_for_submission 必须是布尔值")
        if item.get("id") in required_material_ids and item.get("required_for_submission") is not True:
            errors.append(f"材料 {item.get('id', index)} 已列入当年必交清单，但required_for_submission不是true")
        if item.get("required_for_submission") is True and item.get("id") not in required_material_ids:
            warnings.append(f"材料 {item.get('id', index)} 标记为必交，但未列入submission_requirements.required_material_ids")
        qa = item.get("qa")
        if not isinstance(qa, dict):
            errors.append(f"材料 {item.get('id', index)} 缺少 qa 对象")
            qa = {}
        for qa_key in QA_KEYS:
            if qa.get(qa_key) not in QA_STATUSES:
                errors.append(f"材料 {item.get('id', index)}.qa.{qa_key} 缺少有效状态")
        if item.get("status") in {"ready", "submitted", "archived"}:
            if not item.get("file_path") or not item.get("sha256"):
                errors.append(f"材料 {item.get('id', index)} 已就绪/提交，但缺少 file_path 或 sha256")
            digest = str(item.get("sha256", ""))
            if digest and (len(digest) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in digest)):
                errors.append(f"材料 {item.get('id', index)}.sha256 必须是64位SHA-256")
            failed_qa = [key for key, value in qa.items() if value not in {"passed", "not-applicable"}]
            if failed_qa:
                errors.append(f"材料 {item.get('id', index)} 已就绪/提交，但QA未全部通过：{failed_qa}")
            qa_records = item.get("qa_records")
            if not isinstance(qa_records, dict):
                errors.append(f"材料 {item.get('id', index)} 已就绪/提交，但缺少 qa_records 审计凭据")
                qa_records = {}
            for qa_key, qa_status in qa.items():
                if qa_status != "passed":
                    continue
                record = qa_records.get(qa_key)
                if not isinstance(record, dict):
                    errors.append(f"材料 {item.get('id', index)}.qa.{qa_key}=passed，但缺少对应qa_records记录")
                    continue
                if not str(record.get("method", "")).strip():
                    errors.append(f"材料 {item.get('id', index)}.qa_records.{qa_key}.method 不能为空")
                if not record.get("checked_at"):
                    errors.append(f"材料 {item.get('id', index)}.qa_records.{qa_key}.checked_at 不能为空")
                else:
                    parse_day(
                        str(record.get("checked_at")),
                        f"材料{item.get('id', index)}.qa_records.{qa_key}.checked_at",
                        errors,
                    )
        source_id = item.get("reference_source_id")
        if source_id and source_id not in source_ids:
            errors.append(f"材料 {item.get('id', index)} 引用了不存在的来源：{source_id}")
        for dependency in item.get("depends_on", []):
            if dependency not in material_ids:
                errors.append(f"材料 {item.get('id', index)} 引用了不存在的依赖：{dependency}")
        for photo_id in item.get("photo_evidence_ids", []):
            if photo_id not in photo_ids:
                errors.append(f"材料 {item.get('id', index)} 引用了不存在的照片证据：{photo_id}")

    for photo_id in photo_ids:
        for material_id in evidence_items[photo_id].get("material_ids", []):
            if material_id not in material_ids:
                errors.append(f"照片 {photo_id} 引用了不存在的材料：{material_id}")

    commitments = data.get("commitments", [])
    if commitments and not isinstance(commitments, list):
        errors.append("commitments 必须是数组")
        commitments = []
    commitment_ids: set[str] = set()
    for index, item in enumerate(commitments, 1):
        if not isinstance(item, dict):
            errors.append(f"commitments[{index}] 必须是对象")
            continue
        commitment_id = str(item.get("id", "")).strip()
        if not commitment_id:
            errors.append(f"commitments[{index}].id 不能为空")
        elif commitment_id in commitment_ids:
            errors.append(f"commitments 存在重复 id：{commitment_id}")
        commitment_ids.add(commitment_id)
        if item.get("status") not in COMMITMENT_STATUSES:
            errors.append(f"承诺成果 {commitment_id or index} 缺少有效 status")
        if not item.get("name") or item.get("promised_in") not in material_ids:
            errors.append(f"承诺成果 {commitment_id or index} 缺少名称或promised_in材料不存在")
        if item.get("due_date"):
            parse_day(str(item.get("due_date")), f"承诺成果{commitment_id}.due_date", errors)
        for material_id in item.get("material_ids", []):
            if material_id not in material_ids:
                errors.append(f"承诺成果 {commitment_id or index} 引用了不存在的材料：{material_id}")
        if item.get("status") == "fulfilled" and not item.get("material_ids"):
            errors.append(f"承诺成果 {commitment_id or index} 标记fulfilled但没有实际材料")
        if item.get("status") == "changed-approved" and not item.get("change_approval_id"):
            errors.append(f"承诺成果 {commitment_id or index} 标记changed-approved但没有变更批准编号/证据")

    claims = data.get("claims", [])
    if claims and not isinstance(claims, list):
        errors.append("claims 必须是数组")
        claims = []
    claim_ids: set[str] = set()
    for index, claim in enumerate(claims, 1):
        if not isinstance(claim, dict):
            errors.append(f"claims[{index}] 必须是对象")
            continue
        claim_id = str(claim.get("id", "")).strip()
        if not claim_id:
            errors.append(f"claims[{index}].id 不能为空")
        elif claim_id in claim_ids:
            errors.append(f"claims 存在重复 id：{claim_id}")
        claim_ids.add(claim_id)
        if claim.get("status") not in CLAIM_STATUSES:
            errors.append(f"claims[{index}] 缺少有效 status")
        claim_evidence = claim.get("evidence_ids", [])
        if not isinstance(claim_evidence, list):
            errors.append(f"claims[{index}].evidence_ids 必须是数组")
            claim_evidence = []
        if claim.get("status") in {"verified", "completed"} and not claim_evidence:
            errors.append(f"claims[{index}] 已标记为已证实，但没有 evidence_ids")
        for evidence_id in claim_evidence:
            if evidence_id not in evidence_ids:
                errors.append(f"claims[{index}] 引用了不存在的证据：{evidence_id}")

    weights = data.get("evaluation_weights", {})
    if weights:
        if not isinstance(weights, dict) or not all(
            isinstance(value, (int, float)) and value >= 0 for value in weights.values()
        ):
            errors.append("evaluation_weights 必须是非负数值对象")
        elif abs(sum(weights.values()) - 100) > 1e-6:
            errors.append(f"evaluation_weights 合计必须为100，当前为 {sum(weights.values())}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读取失败：{exc}", file=sys.stderr)
        return 2
    errors, warnings = validate(data)
    for warning in warnings:
        print(f"警告：{warning}")
    for error in errors:
        print(f"错误：{error}")
    if errors:
        print(f"校验未通过：{len(errors)} 个错误，{len(warnings)} 个警告")
        return 1
    print(f"基础校验通过：0 个错误，{len(warnings)} 个警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
