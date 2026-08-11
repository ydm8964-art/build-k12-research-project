from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET

import yaml

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "build-k12-research-project"
SCRIPTS = SKILL / "scripts"
EXAMPLE = SKILL / "references" / "project-manifest.example.json"
sys.path.insert(0, str(SCRIPTS))

import audit_lifecycle_coverage  # noqa: E402
import audit_project_package  # noqa: E402
import run_project_preflight  # noqa: E402
import validate_project_manifest  # noqa: E402


class SkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_frontmatter_and_agent_metadata(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        self.assertIsNotNone(match)
        metadata = yaml.safe_load(match.group(1))
        self.assertEqual(metadata["name"], "build-k12-research-project")
        self.assertIn("贵州省", metadata["description"])
        interface = yaml.safe_load((SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8"))["interface"]
        self.assertGreaterEqual(len(interface["short_description"]), 25)
        self.assertLessEqual(len(interface["short_description"]), 64)
        self.assertIn("$build-k12-research-project", interface["default_prompt"])

    def test_all_local_markdown_links_exist(self) -> None:
        broken: list[tuple[str, str]] = []
        pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        for source in SKILL.rglob("*.md"):
            for target in pattern.findall(source.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                relative = target.split("#", 1)[0]
                if relative and not (source.parent / relative).exists():
                    broken.append((str(source.relative_to(SKILL)), target))
        self.assertEqual(broken, [])

    def test_no_machine_paths_or_private_values(self) -> None:
        forbidden_text = ("/Users/", "file://", "vscode://")
        phone = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
        identity = re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")
        findings: list[str] = []
        for source in SKILL.rglob("*"):
            if not source.is_file() or "__pycache__" in source.parts:
                continue
            chunks: list[str] = []
            if source.suffix.lower() in {".md", ".py", ".mjs", ".yaml", ".json"}:
                chunks.append(source.read_text(encoding="utf-8", errors="ignore"))
            elif source.suffix.lower() in {".docx", ".xlsx"}:
                with zipfile.ZipFile(source) as archive:
                    for name in archive.namelist():
                        if name.endswith(("document.xml", "sharedStrings.xml", "core.xml", "custom.xml")):
                            chunks.append(archive.read(name).decode("utf-8", errors="ignore"))
            combined = "\n".join(chunks)
            if any(value in combined for value in forbidden_text) or phone.search(combined) or identity.search(combined):
                findings.append(str(source.relative_to(SKILL)))
        self.assertEqual(findings, [])

    def test_example_manifest_and_status_enums(self) -> None:
        errors, warnings = validate_project_manifest.validate(self.example)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

        bad_instrument = copy.deepcopy(self.example)
        bad_instrument["instruments"][0]["status"] = "unknown"
        errors, _ = validate_project_manifest.validate(bad_instrument)
        self.assertTrue(any("工具" in value and "status" in value for value in errors))

        bad_claim = copy.deepcopy(self.example)
        bad_claim["claims"][0]["status"] = "unknown"
        errors, _ = validate_project_manifest.validate(bad_claim)
        self.assertTrue(any("claims[1]" in value and "status" in value for value in errors))

    def test_custom_packages_still_require_attention_file(self) -> None:
        data = copy.deepcopy(self.example)
        data["materials"] = [item for item in data["materials"] if item["material_role"] != "attention-items"]
        errors, warnings = audit_lifecycle_coverage.audit(data, final=False)
        self.assertEqual(errors, [])
        self.assertTrue(any("attention-file" in value for value in warnings))

    def test_commitments_are_enforced_only_at_closing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "project-manifest.json"
            manifest.write_text(json.dumps(self.example, ensure_ascii=False), encoding="utf-8")
            errors, _ = audit_project_package.audit(manifest, root, final=True)
            self.assertFalse(any("承诺成果" in value and "尚未兑现" in value for value in errors))

            closing = copy.deepcopy(self.example)
            closing["generation_contract"].update(
                {"package_scope": "closing-kit", "truth_state": "closing", "delivery_state": "closing-ready"}
            )
            manifest.write_text(json.dumps(closing, ensure_ascii=False), encoding="utf-8")
            errors, _ = audit_project_package.audit(manifest, root, final=True)
            self.assertTrue(any("承诺成果" in value and "尚未兑现" in value for value in errors))

    def test_relative_evidence_paths_resolve_from_package_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_dir = root / "evidence"
            evidence_dir.mkdir()
            (evidence_dir / "raw.json").write_text("{}", encoding="utf-8")
            data = copy.deepcopy(self.example)
            data["evidence"][0].update(
                {"status": "collected", "source_file": "evidence/raw.json", "collected_date": "2026-08-12"}
            )
            manifest = root / "project-manifest.json"
            manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            errors, _ = audit_project_package.audit(manifest, root, final=True)
            self.assertFalse(any("source_file不存在" in value for value in errors))

            data["evidence"][0]["source_file"] = "evidence/missing.json"
            manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            errors, _ = audit_project_package.audit(manifest, root, final=True)
            self.assertTrue(any("source_file不存在" in value for value in errors))

    def test_final_preflight_treats_warnings_as_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "project-manifest.json"
            manifest.write_text(json.dumps(self.example, ensure_ascii=False), encoding="utf-8")
            with (
                mock.patch.object(run_project_preflight, "audit_package", return_value=([], ["test warning"])),
                mock.patch.object(run_project_preflight, "audit_lifecycle", return_value=([], [])),
            ):
                working = run_project_preflight.run(manifest, root, final=False)
                final = run_project_preflight.run(manifest, root, final=True)
            self.assertEqual(working["status"], "passed")
            self.assertEqual(final["status"], "failed")
            self.assertEqual(final["schema_version"], "1.1")

    def test_docx_templates_are_valid_and_structurally_audited(self) -> None:
        profiles = {
            "research-form.docx": "research-form",
            "analysis-report.docx": "analysis-report",
            "lesson-table.docx": "lesson-table",
            "lesson-long.docx": "lesson-long",
            "casebook.docx": "casebook",
            "evidence-sheet.docx": "evidence-sheet",
            "attention-items.docx": "attention-items",
        }
        templates = SKILL / "assets" / "templates"
        for filename, profile in profiles.items():
            source = templates / filename
            with zipfile.ZipFile(source) as archive:
                self.assertIsNone(archive.testzip(), filename)
                core = archive.read("docProps/core.xml").decode("utf-8", errors="ignore")
                self.assertNotRegex(core, r"<(?:dc:creator|cp:lastModifiedBy)>\s*[^<\s]")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "audit_docx_format.py"), str(source), "--profile", profile, "--final"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_xlsx_template_has_required_sheets_and_clean_formulas(self) -> None:
        source = SKILL / "assets" / "templates" / "project-data-workbook.xlsx"
        required = {"项目说明", "变量编码", "原始数据", "清理编码", "统计分析", "图表结果", "证据索引", "照片登记", "材料进度"}
        with zipfile.ZipFile(source) as archive:
            self.assertIsNone(archive.testzip())
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            names = {element.attrib["name"] for element in workbook.iter() if element.tag.endswith("sheet")}
            formulas = "\n".join(
                archive.read(name).decode("utf-8", errors="ignore")
                for name in archive.namelist()
                if name.startswith("xl/worksheets/") and name.endswith(".xml")
            )
        self.assertEqual(names, required)
        for token in ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "AVERIF"):
            self.assertNotIn(token, formulas)

    def test_scripts_compile_and_are_executable(self) -> None:
        scripts = [source for source in SCRIPTS.iterdir() if source.suffix in {".py", ".mjs"}]
        self.assertTrue(scripts)
        for source in scripts:
            self.assertTrue(os.access(source, os.X_OK), source.name)


if __name__ == "__main__":
    unittest.main()
