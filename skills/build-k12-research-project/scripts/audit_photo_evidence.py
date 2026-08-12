#!/usr/bin/env python3
"""Audit real-photo evidence placement, captions, IDs, privacy, and manifest links in DOCX."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from audit_common import cli_failed
from docx import Document

try:
    from PIL import ExifTags, Image
except ImportError:  # optional: structural checks still work
    Image = None
    ExifTags = None


MODES = {"working", "submission", "anonymous", "public"}
CAPTION_RE = re.compile(r"^\s*图\s*[0-9一二三四五六七八九十]+(?:\s*[-－.]\s*[0-9一二三四五六七八九十]+)?\s*[：:]?")
PHOTO_ID_RE = re.compile(r"\bPHO-[0-9]{4}-[A-Z0-9-]+\b", re.I)
DATE_RE = re.compile(r"(?:20\d{2}[年./-]\d{1,2}(?:[月./-]\d{1,2}日?)?)")
GENERIC_ALT_RE = re.compile(r"^(?:(?:图片|图像|照片|image|picture|photo)\s*\d*|[0-9a-f]{24,}|[^\s]+\.(?:jpe?g|png|gif|webp))$", re.I)
SAFE_PUBLIC_FACE = {"not-applicable", "no-identifiable-person", "back-view", "cropped", "blurred", "consented-identifiable"}


def paragraph_text(paragraph) -> str:
    return "".join(node.text or "" for node in paragraph.xpath(".//w:t")).strip()


def next_nonempty_text(paragraphs, start: int) -> str:
    for paragraph in paragraphs[start + 1 :]:
        value = paragraph_text(paragraph)
        if value:
            return value
    return ""


def image_info(drawing, document: Document) -> dict:
    rel_ids = drawing.xpath(".//*[local-name()='blip']/@*[local-name()='embed']")
    if not rel_ids:
        rel_ids = drawing.xpath(".//*[local-name()='imagedata']/@*[local-name()='id']")
    rel_id = rel_ids[0] if rel_ids else None
    blob = None
    target = None
    if rel_id and rel_id in document.part.related_parts:
        part = document.part.related_parts[rel_id]
        blob = part.blob
        target = str(part.partname)
    digest = hashlib.sha256(blob).hexdigest() if blob else None

    props = drawing.xpath(".//*[local-name()='docPr']")
    alt = ""
    if props:
        alt = (props[0].get("descr") or props[0].get("title") or "").strip()

    width_px = height_px = None
    dpi = None
    distorted = False
    cropped = False
    gps_present = False
    if blob and Image is not None:
        try:
            with Image.open(io.BytesIO(blob)) as image:
                width_px, height_px = image.size
                extents = drawing.xpath(".//*[local-name()='extent']")
                if extents:
                    cx = int(extents[0].get("cx", "0"))
                    cy = int(extents[0].get("cy", "0"))
                    if cx > 0 and cy > 0:
                        width_in = cx / 914400
                        height_in = cy / 914400
                        dpi = min(width_px / width_in, height_px / height_in)
                        effective_width = float(width_px)
                        effective_height = float(height_px)
                        crop_nodes = drawing.xpath(".//*[local-name()='srcRect']")
                        if crop_nodes:
                            crop_node = crop_nodes[0]
                            left = int(crop_node.get("l", "0"))
                            top = int(crop_node.get("t", "0"))
                            right = int(crop_node.get("r", "0"))
                            bottom = int(crop_node.get("b", "0"))
                            cropped = any(value != 0 for value in (left, top, right, bottom))
                            effective_width *= max(0.01, 1 - (left + right) / 100000)
                            effective_height *= max(0.01, 1 - (top + bottom) / 100000)
                        source_ratio = effective_width / effective_height
                        placed_ratio = width_in / height_in
                        distorted = abs(source_ratio - placed_ratio) / source_ratio > 0.05
                exif = image.getexif()
                if exif and ExifTags is not None:
                    gps_tag = next((key for key, value in ExifTags.TAGS.items() if value == "GPSInfo"), None)
                    gps_present = bool(gps_tag and gps_tag in exif)
        except Exception:
            pass
    return {
        "rel_id": rel_id,
        "target": target,
        "digest": digest,
        "alt": alt,
        "width_px": width_px,
        "height_px": height_px,
        "dpi": dpi,
        "distorted": distorted,
        "cropped": cropped,
        "gps_present": gps_present,
    }


def load_manifest(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(item.get("id")): item
        for item in data.get("evidence", [])
        if isinstance(item, dict) and item.get("type") == "photo" and item.get("id")
    }


def add_manifest_checks(
    photo_id: str,
    item: dict,
    mode: str,
    manifest_root: Path,
    final: bool,
    errors: list[str],
    warnings: list[str],
) -> None:
    for key in ("collected_date", "location", "activity", "photographer_source", "derivative_file", "original_sha256", "derivative_sha256", "consent_status", "publication_scope", "face_handling", "caption", "alt_text", "material_ids"):
        if not item.get(key):
            errors.append(f"照片登记{photo_id}缺少{key}")
    delivery_included = item.get("delivery_included")
    if not isinstance(delivery_included, bool):
        errors.append(f"照片登记{photo_id}缺少布尔值delivery_included")
    elif delivery_included and not item.get("source_file"):
        errors.append(f"照片登记{photo_id}声明原件随包交付，但缺少source_file")
    elif delivery_included is False:
        custody = item.get("custody_record")
        if not isinstance(custody, dict) or any(not custody.get(key) for key in ("owner", "locator", "verified_at")):
            errors.append(f"照片登记{photo_id}原件不随包交付，但缺少完整custody_record")
    for digest_key in ("original_sha256", "derivative_sha256"):
        digest = str(item.get(digest_key, ""))
        if digest and (len(digest) != 64 or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
            errors.append(f"照片登记{photo_id}的{digest_key}不是64位SHA-256")
    if "transformation_log" not in item or not isinstance(item.get("transformation_log"), list):
        errors.append(f"照片登记{photo_id}缺少数组transformation_log")

    scope = item.get("publication_scope")
    if mode == "public" and scope != "public":
        errors.append(f"照片{photo_id}用于公开版，但登记的publication_scope不是public")
    if mode == "anonymous" and scope not in {"anonymous", "public"}:
        errors.append(f"照片{photo_id}用于匿名版，但登记的publication_scope不允许匿名/公开使用")
    if mode == "submission" and scope not in {"submission", "public"}:
        errors.append(f"照片{photo_id}用于报送版，但登记的publication_scope不允许报送/公开使用")
    if mode in {"anonymous", "public"}:
        if item.get("consent_status") not in {"obtained", "not-required"}:
            errors.append(f"照片{photo_id}用于匿名/公开版，但授权状态不合格")
        if item.get("face_handling") not in SAFE_PUBLIC_FACE:
            errors.append(f"照片{photo_id}用于匿名/公开版，但人物处理状态不合格")

    path_fields = [("derivative_file", "派生副本")]
    if delivery_included is True:
        path_fields.append(("source_file", "原件"))
    for key, label in path_fields:
        value = item.get(key)
        if not value:
            continue
        raw = Path(str(value)).expanduser()
        actual = raw.resolve() if raw.is_absolute() else (manifest_root / raw).resolve()
        inside = actual == manifest_root or manifest_root in actual.parents
        if final and not inside:
            errors.append(f"照片{photo_id}登记的{label}不在交付根目录内：{actual}")
        if not actual.is_file():
            message = f"照片{photo_id}登记的{label}路径不存在：{actual}"
            (errors if final else warnings).append(message)


def audit(path: Path, manifest_path: Path | None, mode: str, final: bool, scope: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if path.suffix.lower() != ".docx":
        return ["照片证据专项审计仅支持DOCX"], warnings

    document = Document(path)
    paragraphs = document.element.body.xpath(".//w:p")
    anchors = document.element.body.xpath(".//*[local-name()='anchor']")
    if anchors:
        warnings.append(f"发现浮动/锚定图片{len(anchors)}处；真实照片优先改为内嵌并逐页检查跨软件漂移")

    records: list[dict] = []
    for index, paragraph in enumerate(paragraphs):
        drawings = paragraph.xpath(".//w:drawing|.//w:pict")
        if not drawings:
            continue
        caption = next_nonempty_text(paragraphs, index)
        caption_ids = [value.upper() for value in PHOTO_ID_RE.findall(caption)]
        caption_is_valid = bool(CAPTION_RE.match(caption))
        for drawing_index, drawing in enumerate(drawings, 1):
            info = image_info(drawing, document)
            info.update(
                {
                    "paragraph_index": index + 1,
                    "drawing_index": drawing_index,
                    "caption": caption,
                    "caption_is_valid": caption_is_valid,
                    "caption_ids": caption_ids,
                }
            )
            records.append(info)

    if not records:
        errors.append("DOCX中未发现照片/图片；需要真实照片证据时不能交付空证据册")
        return errors, warnings

    if scope == "registered-only":
        unclassified = [item for item in records if not item["caption_ids"]]
        records = [item for item in records if item["caption_ids"]]
        if unclassified:
            warnings.append(f"另有{len(unclassified)}张未使用PHO证据ID的插图，按普通图表/资料图另行核对来源、题注和授权")
        if not records:
            errors.append("未发现带PHO证据ID的真实照片；如文档应含照片，请先在图题和manifest登记")
            return errors, warnings

    missing_caption = [item for item in records if not item["caption_is_valid"]]
    if missing_caption:
        message = f"有{len(missing_caption)}张图片后未紧跟规范‘图…’题注"
        (errors if final else warnings).append(message)

    missing_ids = [item for item in records if not item["caption_ids"]]
    if missing_ids:
        message = f"有{len(missing_ids)}张图片的相邻图题缺少PHO-年份-序号证据ID"
        (errors if final else warnings).append(message)

    missing_dates = [item for item in records if item["caption_is_valid"] and not DATE_RE.search(item["caption"])]
    if missing_dates:
        message = f"有{len(missing_dates)}张图片的图题缺少可核对的拍摄/活动日期"
        (errors if final else warnings).append(message)

    missing_alt = [item for item in records if not item["alt"]]
    generic_alt = [item for item in records if item["alt"] and GENERIC_ALT_RE.fullmatch(item["alt"])]
    if missing_alt:
        message = f"有{len(missing_alt)}张图片缺少替代文本"
        (errors if final else warnings).append(message)
    if generic_alt:
        warnings.append(f"有{len(generic_alt)}张图片的替代文本过于笼统，应描述真实活动和证据用途")

    low_dpi = [item for item in records if item["dpi"] is not None and item["dpi"] < 150]
    if low_dpi:
        warnings.append(f"有{len(low_dpi)}张图片按当前插入尺寸低于150dpi，打印可能模糊")
    distorted = [item for item in records if item["distorted"]]
    if distorted:
        errors.append(f"有{len(distorted)}张图片的插入长宽比与原图相差超过5%，疑似拉伸变形")

    gps = [item for item in records if item["gps_present"]]
    if gps and mode in {"anonymous", "public"}:
        errors.append(f"匿名/公开版有{len(gps)}张内嵌图片仍含GPS EXIF，请对派生副本清理定位元数据")

    digest_to_ids: dict[str, set[str]] = defaultdict(set)
    digest_counts: dict[str, int] = defaultdict(int)
    for item in records:
        if item["digest"]:
            digest_counts[item["digest"]] += 1
            digest_to_ids[item["digest"]].update(item["caption_ids"])
    conflicting = [digest for digest, ids in digest_to_ids.items() if len(ids) > 1]
    if conflicting:
        errors.append(f"发现{len(conflicting)}组相同图片对应不同照片ID，可能被写成不同活动/日期")
    repeated = [digest for digest, count in digest_counts.items() if count > 1]
    if repeated:
        warnings.append(f"发现{len(repeated)}组图片在文档中重复出现；如属必要复用，应保持同一照片ID和说明")

    manifest_items = load_manifest(manifest_path)
    doc_ids = {photo_id for item in records for photo_id in item["caption_ids"]}
    if manifest_path is None:
        warnings.append("未提供项目manifest，无法核对照片原件哈希、日期、授权、人物处理和材料对应关系")
    else:
        for photo_id in sorted(doc_ids):
            if photo_id not in manifest_items:
                errors.append(f"图题中的照片ID未在manifest登记：{photo_id}")
            else:
                manifest_root = manifest_path.resolve().parent
                add_manifest_checks(photo_id, manifest_items[photo_id], mode, manifest_root, final, errors, warnings)
        for record in records:
            for photo_id in record["caption_ids"]:
                item = manifest_items.get(photo_id)
                if not item:
                    continue
                expected_digest = str(item.get("derivative_sha256") or item.get("original_sha256") or "").lower()
                if expected_digest and record["digest"] and record["digest"].lower() != expected_digest:
                    errors.append(f"文档内照片{photo_id}的文件哈希与登记的派生照片不一致")
                expected_alt = str(item.get("alt_text") or "").strip()
                if expected_alt and record["alt"].strip() != expected_alt:
                    errors.append(f"文档内照片{photo_id}的替代文本与manifest登记不一致")
                expected_caption = str(item.get("caption") or "").strip()
                if expected_caption and expected_caption not in record["caption"]:
                    errors.append(f"文档内照片{photo_id}的图题内容与manifest登记不一致")

    props = document.core_properties
    if mode in {"anonymous", "public"} and any(str(value or "").strip() for value in (props.author, props.last_modified_by, props.comments)):
        errors.append("匿名/公开版DOCX仍含作者、最后修改者或备注元数据")
    if mode in {"anonymous", "public"}:
        warnings.append("自动审计不能识别人脸、姓名牌、校服校徽和黑板信息；必须逐图人工确认授权、裁切或打码")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--mode", choices=sorted(MODES), default="working")
    parser.add_argument("--scope", choices=("all-images", "registered-only"), default="all-images", help="照片证据册用all-images；含地图/图表的混合文档用registered-only")
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        errors, warnings = audit(args.docx, args.manifest, args.mode, args.final, args.scope)
    except Exception as exc:
        print(f"读取或审计失败：{exc}", file=sys.stderr)
        return 2
    for item in warnings:
        print(f"警告：{item}")
    for item in errors:
        print(f"错误：{item}")
    if cli_failed(errors, warnings, args.final):
        print(f"照片证据审计未通过：{len(errors)}个错误，{len(warnings)}个警告")
        return 1
    print(f"照片证据审计通过：0个错误，{len(warnings)}个警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
