#!/usr/bin/env python3
"""Shared manual final-acceptance gates and invalidation helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

MANUAL_GATES = {
    "policy-and-submission": "核对当年通知、官方附件、报送系统、限额、命名、份数、装订、签章和截止时间",
    "docx-pdf-visual": "逐页检查DOCX/PDF的目录、页码、标题、表格、图片、题注、交叉引用和打印效果",
    "xlsx-reconciliation": "逐表检查XLSX、复算公式，并回查Word/PDF中的样本量、频数、比例和图表",
    "evidence-privacy-authorship": "核对照片与原始证据真实性、授权/打码、学科事实、署名和贡献登记",
    "attention-and-signature": "逐条清零注意事项中的阻断项，确认责任人、签字盖章和线下原件",
}

ACCEPTANCE_STATUSES = {"pending", "verified", "expired"}


def pending_acceptance() -> dict:
    return {
        "status": "pending",
        "reviewed_at": None,
        "reviewer": None,
        "attestation_file": None,
        "attestation_sha256": None,
        "invalidated_at": None,
        "invalidation_reason": None,
    }


def manifest_review_sha256(data: dict) -> str:
    """Hash project facts while excluding the attestation itself and append-only history."""
    review_scope = {
        key: value
        for key, value in data.items()
        if key not in {"manual_acceptance", "revision_history"}
    }
    payload = json.dumps(review_scope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def invalidate_manual_acceptance(data: dict, reason: str) -> None:
    acceptance = data.setdefault("manual_acceptance", pending_acceptance())
    if acceptance.get("status") != "verified":
        return
    acceptance["status"] = "expired"
    acceptance["invalidated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    acceptance["invalidation_reason"] = reason
