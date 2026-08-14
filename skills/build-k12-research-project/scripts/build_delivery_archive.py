#!/usr/bin/env python3
"""Preflight, checksum, and package a complete K-12 project folder as one verified ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from run_project_preflight import run as run_preflight

SKIP_NAMES = {".DS_Store", "Thumbs.db"}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_arcname(path: Path, root: Path) -> str:
    value = PurePosixPath(path.relative_to(root).as_posix())
    if value.is_absolute() or ".." in value.parts:
        raise ValueError(f"不安全的归档路径：{value}")
    return str(value)


def scrub_report_paths(value, root: Path):
    if isinstance(value, dict):
        return {key: scrub_report_paths(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_report_paths(item, root) for item in value]
    if isinstance(value, str):
        return value.replace(str(root), ".")
    return value


def collect_files(root: Path, output: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.resolve() == output.resolve():
            continue
        if path.name.startswith("~$") or path.name in SKIP_NAMES or "__pycache__" in path.parts:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def write_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def build(manifest_path: Path, root: Path, output: Path, *, final: bool = True) -> dict:
    root = root.resolve()
    manifest_path = manifest_path.resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"拒绝覆盖既有交付包：{output}")
    if root not in manifest_path.parents:
        raise ValueError("project-manifest.json必须位于交付根目录内")

    report = run_preflight(manifest_path, root, final)
    if report["status"] != "passed":
        raise ValueError(
            f"一键预检未通过，不能打包：{report['error_count']}个错误，{report['warning_count']}个警告"
        )
    files = collect_files(root, output)
    if manifest_path not in files:
        raise ValueError("交付目录缺少project-manifest.json")

    portable_report = scrub_report_paths(report, root)
    report_bytes = (json.dumps(portable_report, ensure_ascii=False, indent=2) + "\n").encode()
    source_checksums = [(safe_arcname(path, root), sha256_file(path)) for path in files]
    checksum_lines = [f"{digest}  {name}" for name, digest in source_checksums]
    checksum_lines.append(f"{sha256_bytes(report_bytes)}  交付校验/preflight-report.json")
    checksums_bytes = ("\n".join(checksum_lines) + "\n").encode()
    summary = {
        "schema_version": "1.0",
        "package_state": "ready" if final else "scaffold",
        "project_title": json.loads(manifest_path.read_text(encoding="utf-8"))["project"]["title"],
        "built_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "file_count": len(files),
        "preflight": {"status": report["status"], "error_count": 0, "warning_count": report["warning_count"]},
        "manual_acceptance": report.get("manual_acceptance", {"status": "pending"}),
        "notice": "ready表示机器预检和已登记的人工终审均通过；实际上传仍须按通知选择相应报送文件。"
        if final else "本包为scaffold，含待补真实数据/照片/签章事项，不得作为可直接提交终稿。",
    }
    summary_bytes = (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode()

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output.stem}.", suffix=".tmp.zip", dir=output.parent)
    os.close(fd)
    temporary = Path(temp_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                write_entry(archive, safe_arcname(path, root), path.read_bytes())
            write_entry(archive, "交付校验/preflight-report.json", report_bytes)
            write_entry(archive, "交付校验/SHA256SUMS.txt", checksums_bytes)
            write_entry(archive, "交付校验/package-summary.json", summary_bytes)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("生成的ZIP完整性检查失败")
            names = set(archive.namelist())
            if any(name.startswith("/") or ".." in PurePosixPath(name).parts for name in names):
                raise ValueError("ZIP含不安全路径")
            for name, expected in source_checksums:
                if sha256_bytes(archive.read(name)) != expected:
                    raise ValueError(f"ZIP内文件校验失败：{name}")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {**summary, "archive": str(output), "sha256": sha256_file(output)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scaffold", action="store_true", help="明确生成不可直接提交的工作包；默认要求最终预检")
    args = parser.parse_args()
    try:
        result = build(args.manifest, args.root, args.out, final=not args.scaffold)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"整套材料打包失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
