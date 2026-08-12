#!/usr/bin/env python3
"""Audit a complete K-12 research-project delivery folder against its manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from audit_common import PLACEHOLDER_RE, cli_failed
from validate_project_manifest import validate as validate_manifest

READY_STATUSES = {"ready", "submitted", "archived"}
PASS_QA = {"passed", "not-applicable"}
SUSPICIOUS_NAME_RE = re.compile(r"最终版\d|最新版|修改版\d|副本|复件|copy|\(\d+\)|（\d+）", re.I)
TEMP_NAMES = {".DS_Store", "Thumbs.db"}
SUPPORTED_SUFFIXES = {".doc", ".docx", ".xlsx", ".pdf"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_read_zip_text(archive: zipfile.ZipFile, names: list[str]) -> str:
    parts: list[str] = []
    for name in names:
        if name not in archive.namelist():
            continue
        try:
            value = archive.read(name).decode("utf-8", errors="ignore")
        except Exception:
            continue
        parts.append(re.sub(r"<[^>]+>", " ", value))
    return "\n".join(parts)


def inspect_docx(path: Path, privacy_class: str, final: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                errors.append(f"DOCX压缩包损坏：{bad}")
            names = archive.namelist()
            story_names = [
                name
                for name in names
                if name == "word/document.xml" or re.fullmatch(r"word/(?:header|footer)\d+\.xml", name)
            ]
            xml_text = "\n".join(archive.read(name).decode("utf-8", errors="ignore") for name in story_names)
            plain_text = safe_read_zip_text(archive, story_names + ["word/footnotes.xml", "word/endnotes.xml"])
            placeholders = len(PLACEHOLDER_RE.findall(plain_text))
            if placeholders:
                (errors if final else warnings).append(f"DOCX发现待处理占位内容{placeholders}处")
            if "word/comments.xml" in names:
                (errors if final else warnings).append("DOCX仍含批注comments.xml")
            if re.search(r"<w:(?:ins|del)\b", xml_text):
                (errors if final else warnings).append("DOCX仍含未接受/拒绝的修订")
            if re.search(r"<w:vanish\b", xml_text):
                (errors if final else warnings).append("DOCX仍含隐藏文字")

            external_images = 0
            external_links = 0
            for rel_name in [name for name in names if name.endswith(".rels")]:
                try:
                    root = ET.fromstring(archive.read(rel_name))
                except ET.ParseError:
                    continue
                for rel in root:
                    if rel.attrib.get("TargetMode") != "External":
                        continue
                    rel_type = rel.attrib.get("Type", "")
                    if rel_type.endswith("/image"):
                        external_images += 1
                    else:
                        external_links += 1
            if external_images:
                errors.append(f"DOCX含外链图片{external_images}处，离线报送可能丢图")
            if external_links:
                warnings.append(f"DOCX含外部链接{external_links}处，请逐项核对有效性和必要性")

            if privacy_class in {"anonymous", "public"} and "docProps/core.xml" in names:
                core = archive.read("docProps/core.xml").decode("utf-8", errors="ignore")
                if re.search(r"<(?:dc:creator|cp:lastModifiedBy)>\s*[^<\s]", core):
                    errors.append("匿名/公开DOCX仍含作者或最后修改者元数据")
            if privacy_class in {"anonymous", "public"} and "docProps/custom.xml" in names:
                warnings.append("匿名/公开DOCX仍含自定义属性，请核对并清理身份/软件信息")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"DOCX无法打开：{exc}")
    return errors, warnings


def inspect_xlsx(path: Path, allowed_hidden: set[str], final: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                errors.append(f"XLSX压缩包损坏：{bad}")
            names = archive.namelist()
            if any(name.startswith("xl/externalLinks/") for name in names) or "xl/connections.xml" in names:
                (errors if final else warnings).append("XLSX含外部工作簿链接或数据连接")
            if "xl/workbook.xml" in names:
                root = ET.fromstring(archive.read("xl/workbook.xml"))
                hidden: list[str] = []
                for element in root.iter():
                    if element.tag.endswith("sheet") and element.attrib.get("state", "visible") != "visible":
                        hidden.append(element.attrib.get("name", "未命名"))
                unapproved = [name for name in hidden if name not in allowed_hidden]
                if unapproved:
                    (errors if final else warnings).append(f"XLSX含未登记隐藏工作表：{unapproved}")
            text_names = [
                name
                for name in names
                if name in {"xl/sharedStrings.xml", "xl/workbook.xml"}
                or (name.startswith("xl/worksheets/") and name.endswith(".xml"))
            ]
            text = safe_read_zip_text(archive, text_names)
            placeholders = len(PLACEHOLDER_RE.findall(text))
            if placeholders:
                (errors if final else warnings).append(f"XLSX发现待处理占位内容{placeholders}处")
    except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        errors.append(f"XLSX无法打开：{exc}")
    return errors, warnings


def inspect_pdf(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        if path.read_bytes()[:5] != b"%PDF-":
            errors.append("PDF文件头无效")
            return errors, warnings
        try:
            from pypdf import PdfReader

            reader = PdfReader(path)
            if reader.is_encrypted:
                errors.append("PDF已加密，可能无法由管理部门打开")
            if not reader.pages:
                errors.append("PDF没有页面")
            else:
                sample_pages = reader.pages[: min(5, len(reader.pages))]
                extracted = "".join(page.extract_text() or "" for page in sample_pages)
                if not extracted.strip():
                    warnings.append("PDF抽查页面不可检索；如为扫描原件，请确认清晰度并按要求OCR")
        except ImportError:
            warnings.append("运行环境缺少pypdf，仅完成PDF文件头检查")
        except Exception as exc:
            errors.append(f"PDF解析失败：{exc}")
    except OSError as exc:
        errors.append(f"PDF无法读取：{exc}")
    return errors, warnings


def resolve_material_path(root: Path, value: str) -> tuple[Path, bool]:
    raw = Path(value)
    actual = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    inside = actual == root or root in actual.parents
    return actual, inside


def audit(manifest_path: Path, root: Path, final: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_errors, manifest_warnings = validate_manifest(data)
    errors.extend(f"manifest：{item}" for item in manifest_errors)
    warnings.extend(f"manifest：{item}" for item in manifest_warnings)

    root = root.resolve()
    if not root.is_dir():
        return [f"交付根目录不存在：{root}"], warnings

    materials = [item for item in data.get("materials", []) if isinstance(item, dict)]
    material_by_id = {str(item.get("id")): item for item in materials if item.get("id")}
    actual_paths: dict[str, Path] = {}
    hash_to_ids: dict[str, list[str]] = defaultdict(list)

    requirements = data.get("submission_requirements", {})
    if final:
        if not isinstance(requirements, dict) or requirements.get("status") != "verified":
            errors.append("当年申报/结题通知与模板尚未形成verified要求快照")
        else:
            if not requirements.get("verified_at"):
                errors.append("当年要求快照缺少verified_at")
            sources = {
                str(item.get("id")): item
                for item in data.get("sources", [])
                if isinstance(item, dict) and item.get("id")
            }
            notice_ids = requirements.get("notice_source_ids", [])
            template_ids = requirements.get("template_source_ids", [])
            if not isinstance(notice_ids, list):
                notice_ids = []
            if not isinstance(template_ids, list):
                template_ids = []
            for source_id in set(notice_ids + template_ids):
                if sources.get(str(source_id), {}).get("verification_status") != "verified":
                    errors.append(f"当年要求快照引用的来源{source_id}尚未核验")
            required_ids = requirements.get("required_material_ids", [])
            if not isinstance(required_ids, list):
                required_ids = []
            for material_id in required_ids:
                material = material_by_id.get(str(material_id), {})
                if material.get("status") not in READY_STATUSES:
                    errors.append(f"当年必交材料{material_id}尚未就绪：{material.get('status', '不存在')}")

    for item in materials:
        material_id = str(item.get("id", "未编号"))
        status = item.get("status")
        required = bool(item.get("required_for_submission"))
        if final and required and status not in READY_STATUSES:
            errors.append(f"必交材料{material_id}状态不是ready/submitted/archived：{status}")

        file_path = item.get("file_path")
        if not file_path:
            if status in READY_STATUSES:
                errors.append(f"已就绪材料{material_id}缺少file_path")
            continue
        actual, inside = resolve_material_path(root, str(file_path))
        actual_paths[material_id] = actual
        if final and not inside:
            errors.append(f"材料{material_id}不在交付根目录内：{actual}")
        if not actual.is_file():
            errors.append(f"材料{material_id}文件不存在：{actual}")
            continue
        if actual.stat().st_size == 0:
            errors.append(f"材料{material_id}为空文件")
            continue
        if SUSPICIOUS_NAME_RE.search(actual.name):
            warnings.append(f"材料{material_id}文件名疑似不可追溯版本：{actual.name}")

        output_format = str(item.get("output_format", "")).lower()
        expected_suffixes = {"doc": {".doc"}, "docx": {".docx"}, "xlsx": {".xlsx"}, "pdf": {".pdf"}}.get(output_format, set())
        if actual.suffix.lower() not in expected_suffixes:
            errors.append(f"材料{material_id}扩展名{actual.suffix}与output_format={output_format}不一致")

        digest = sha256(actual)
        if status in READY_STATUSES:
            hash_to_ids[digest].append(material_id)
        if item.get("sha256") and str(item.get("sha256", "")).lower() != digest:
            errors.append(f"材料{material_id}实际SHA-256与manifest不一致")
        if status not in READY_STATUSES:
            continue
        max_size = item.get("max_size_mb")
        if isinstance(max_size, (int, float)) and actual.stat().st_size > max_size * 1024 * 1024:
            errors.append(f"材料{material_id}超过登记的{max_size}MB大小限制")

        qa = item.get("qa", {})
        incomplete_qa = [key for key, value in qa.items() if value not in PASS_QA]
        if incomplete_qa:
            errors.append(f"材料{material_id}仍有未通过QA：{incomplete_qa}")

        suffix = actual.suffix.lower()
        if suffix == ".docx":
            sub_errors, sub_warnings = inspect_docx(actual, str(item.get("privacy_class", "internal")), final)
        elif suffix == ".xlsx":
            sub_errors, sub_warnings = inspect_xlsx(actual, set(item.get("allowed_hidden_sheets", [])), final)
        elif suffix == ".pdf":
            sub_errors, sub_warnings = inspect_pdf(actual)
        elif suffix == ".doc":
            sub_errors, sub_warnings = [], ["旧DOC仅完成存在性/哈希检查；应保留原件并另制可审计工作副本"]
        else:
            sub_errors, sub_warnings = ["不支持的文件格式"], []
        errors.extend(f"材料{material_id}：{value}" for value in sub_errors)
        warnings.extend(f"材料{material_id}：{value}" for value in sub_warnings)

        for dependency in item.get("depends_on", []):
            dependency_item = material_by_id.get(str(dependency), {})
            if dependency_item.get("status") not in READY_STATUSES:
                errors.append(f"材料{material_id}已就绪，但依赖{dependency}尚未就绪")

    for digest, ids in hash_to_ids.items():
        if len(ids) > 1:
            warnings.append(f"材料{ids}文件内容完全相同（SHA-256={digest[:12]}…），请核对是否重复交付")

    generation = data.get("generation_contract", {})
    closing_audit = final and isinstance(generation, dict) and (
        generation.get("package_scope") == "closing-kit"
        or generation.get("delivery_state") == "closing-ready"
        or generation.get("truth_state") in {"closing", "completed"}
    )
    for item in data.get("commitments", []):
        if not isinstance(item, dict):
            continue
        commitment_id = item.get("id", "未编号")
        status = item.get("status")
        if closing_audit and status not in {"fulfilled", "changed-approved"}:
            errors.append(f"承诺成果{commitment_id}尚未兑现或批准变更：{status}")
        if status == "fulfilled":
            for material_id in item.get("material_ids", []):
                if material_by_id.get(str(material_id), {}).get("status") not in READY_STATUSES:
                    errors.append(f"承诺成果{commitment_id}引用的材料{material_id}尚未就绪")

    evidence_paths: set[Path] = set()
    for item in data.get("evidence", []):
        if not isinstance(item, dict) or item.get("status") not in {"collected", "verified", "completed"}:
            continue
        evidence_id = item.get("id", "未编号")
        delivery_included = item.get("delivery_included")
        source_file = item.get("source_file")
        if delivery_included is True and source_file:
            actual, inside = resolve_material_path(root, str(Path(str(source_file)).expanduser()))
            evidence_paths.add(actual)
            if final and not inside:
                errors.append(f"证据{evidence_id}声明随包交付，但source_file不在交付根目录内：{actual}")
            if not actual.exists():
                errors.append(f"证据{evidence_id}登记的source_file不存在：{actual}")
            elif actual.is_file():
                digest_key = "original_sha256" if item.get("type") == "photo" else "source_sha256"
                if str(item.get(digest_key, "")).lower() != sha256(actual):
                    errors.append(f"证据{evidence_id}的{digest_key}与实际文件不一致")
        elif delivery_included is True:
            errors.append(f"证据{evidence_id}声明随包交付，但缺少source_file")
        elif delivery_included is False:
            custody = item.get("custody_record", {})
            if not isinstance(custody, dict) or any(not custody.get(key) for key in ("owner", "locator", "verified_at")):
                errors.append(f"证据{evidence_id}不随包交付，但缺少完整custody_record（owner/locator/verified_at）")
        if item.get("type") == "photo":
            derivative_file = item.get("derivative_file")
            if not derivative_file:
                errors.append(f"照片证据{evidence_id}缺少交付派生副本derivative_file")
            else:
                derivative, inside = resolve_material_path(root, str(Path(str(derivative_file)).expanduser()))
                evidence_paths.add(derivative)
                if final and not inside:
                    errors.append(f"照片证据{evidence_id}的派生副本不在交付根目录内：{derivative}")
                if not derivative.is_file():
                    errors.append(f"照片证据{evidence_id}登记的派生副本不存在：{derivative}")
                elif str(item.get("derivative_sha256", "")).lower() != sha256(derivative):
                    errors.append(f"照片证据{evidence_id}派生副本SHA-256与登记值不一致")

    registered = {path.resolve() for path in actual_paths.values() if path.exists()} | {
        path.resolve() for path in evidence_paths if path.exists()
    }
    try:
        manifest_resolved = manifest_path.resolve()
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.name.startswith("~$") or path.name in TEMP_NAMES:
                errors.append(f"交付目录含临时/系统文件：{path.relative_to(root)}")
            if path.resolve() == manifest_resolved or path.resolve() in registered:
                continue
            if path.suffix.lower() in SUPPORTED_SUFFIXES:
                warnings.append(f"交付目录含未登记材料：{path.relative_to(root)}")
    except OSError as exc:
        warnings.append(f"遍历交付目录时出现问题：{exc}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        errors, warnings = audit(args.manifest, args.root, args.final)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读取或审计失败：{exc}", file=sys.stderr)
        return 2
    for item in warnings:
        print(f"警告：{item}")
    for item in errors:
        print(f"错误：{item}")
    if cli_failed(errors, warnings, args.final):
        print(f"整套材料审计未通过：{len(errors)}个错误，{len(warnings)}个警告")
        return 1
    print(f"整套材料审计通过：0个错误，{len(warnings)}个警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
