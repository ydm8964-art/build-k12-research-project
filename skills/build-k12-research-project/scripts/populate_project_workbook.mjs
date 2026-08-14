#!/usr/bin/env node
/** Populate the generic project workbook from one manifest snapshot and render every sheet for QA. */

import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const args = process.argv.slice(2);
function valueAfter(flag) {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : null;
}

const inputPath = path.resolve(valueAfter("--input") || "project-data-workbook.xlsx");
const outputPath = path.resolve(valueAfter("--output") || inputPath);
const manifestPath = path.resolve(valueAfter("--manifest") || "project-manifest.json");
const qaDirValue = valueAfter("--qa-dir");
const qaDir = qaDirValue ? path.resolve(qaDirValue) : null;

const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const project = manifest.project || {};
const projectContext = manifest.project_context || {};
const problemContext = manifest.problem_context || {};
const governance = manifest.governance || {};
const generation = manifest.generation_contract || {};
const requirements = manifest.submission_requirements || {};
const timeline = manifest.timeline || {};
const subjects = [project.subject, ...(Array.isArray(project.related_subjects) ? project.related_subjects : [])].filter(Boolean);

const info = workbook.worksheets.getItem("项目说明");
info.getRange("B4:B13").values = [
  [project.title || "[填写]"],
  [project.leader || "[填写]"],
  [project.school || "[填写]"],
  [`${project.stage || "[填写]"}/${subjects.join("、") || "[填写]"}｜${(projectContext.grade_classes || []).join("、") || "班级待确认"}`],
  [`${timeline.application || "[填写]"}至${timeline.completion || "[填写]"}`],
  [governance.data_cutoff || "[待真实数据形成后填写]"],
  [(manifest.samples || []).map((item) => `${item.name || "样本"}：计划${item.planned_n ?? "未定"}，实际${item.actual_n ?? "待采集"}`).join("；") || "[填写]"],
  ["匿名ID；身份映射表单独加密保存"],
  [generation.snapshot_id || "V0.1"],
  [`${requirements.authority || "待核验"}｜${requirements.status || "pending"}`],
];
info.getRange("H4:H13").values = [
  [projectContext.region || "[待确认]"],
  [projectContext.school_context || "[待确认校情]"],
  [projectContext.textbook_version || "[待核验教材版本]"],
  [problemContext.description || "[待确认真实问题]"],
  [(problemContext.observed_evidence || []).join("；") || "[待补基线证据]"],
  [(problemContext.existing_practices || []).join("；") || "[待补已有做法]"],
  [(problemContext.available_resources || []).join("；") || "[待补可用资源]"],
  [problemContext.selected_route || "[待确认选题路线]"],
  [problemContext.selected_core_strategy || "[待确认核心策略]"],
  [projectContext.teacher_title || projectContext.teacher_role || "[待确认教师信息]"],
];
info.getRange("G4:G13").values = [
  ["地区"], ["学校情境"], ["教材版本"], ["真实问题"], ["已有证据"],
  ["已有做法"], ["可用资源"], ["选题路线"], ["核心策略"], ["教师职称/职务"],
];
info.getRange("C4:C13").values = [
  ["已核验"], ["已核验"], ["已核验"], ["已核验"], ["已核验"],
  [governance.data_cutoff ? "已核验" : "待确认"], ["工作版"], ["待确认"], ["工作版"],
  [requirements.status === "verified" ? "已核验" : "待核验"],
];
info.getRange("E4:E13").values = Array.from({ length: 10 }, () => [governance.current_date || ""]);

const evidenceSheet = workbook.worksheets.getItem("证据索引");
const evidence = (manifest.evidence || []).slice(0, 30);
if (evidence.length) {
  evidenceSheet.getRangeByIndexes(3, 0, evidence.length, 15).values = evidence.map((item) => [
    item.id || "", item.type || "", item.collected_date || "", item.delivery_included === true ? "是" : "否",
    item.source_file || "", item.source_sha256 || item.original_sha256 || "",
    item.custody_record?.owner || "", item.custody_record?.locator || "", item.custody_record?.verified_at || "",
    (item.question_ids || []).join("、"), (item.material_ids || []).join("、"), (item.claim_ids || []).join("、"),
    item.privacy_class || "", item.status || "", item.owner || project.leader || "",
  ]);
}

const photoSheet = workbook.worksheets.getItem("照片登记");
const photos = (manifest.evidence || []).filter((item) => item.type === "photo").slice(0, 30);
const consentLabels = { planned: "计划", pending: "待取得", obtained: "已取得", "not-required": "无需", restricted: "限制", withdrawn: "撤回" };
const faceLabels = { "not-applicable": "不适用", "no-identifiable-person": "无人脸", "back-view": "背影", cropped: "裁切", blurred: "模糊", "consented-identifiable": "明确同意可识别", "restricted-original": "仅限原件" };
if (photos.length) {
  photoSheet.getRangeByIndexes(3, 0, photos.length, 20).values = photos.map((item) => [
    item.id || "", item.original_filename || "", item.original_sha256 || "", item.collected_date || "",
    item.location || "", item.activity || "", item.photographer_source || "", item.delivery_included === true ? "是" : "否",
    item.source_file || "", item.custody_record?.owner || "", item.custody_record?.locator || "",
    item.custody_record?.verified_at || "", consentLabels[item.consent_status] || item.consent_status || "", faceLabels[item.face_handling] || item.face_handling || "", item.caption || "",
    item.alt_text || "", [...(item.material_ids || []), ...(item.case_ids || [])].join("、"), item.derivative_file || "",
    item.derivative_sha256 || "", item.figure_location || "",
  ]);
}

const progress = workbook.worksheets.getItem("材料进度");
const materials = (manifest.materials || []).filter((item) => item.included_in_batch !== false).slice(0, 30);
const materialStatusLabels = { planned: "计划", draft: "草稿", "pending-data": "待数据", "pending-photo": "待照片", "pending-signature": "待签章", verified: "已核验", ready: "可提交", submitted: "已提交", archived: "已归档" };
const qaLabels = { pending: "待检查", passed: "通过", failed: "失败", "not-applicable": "不适用" };
if (materials.length) {
  progress.getRangeByIndexes(3, 0, materials.length, 14).values = materials.map((item) => [
    item.id || "", item.name || "", item.material_role || "", item.owner || project.leader || "",
    item.due_date || "", item.completed_date || "", materialStatusLabels[item.status] || item.status || "", (item.depends_on || []).join("、"),
    item.file_path || item.planned_file_path || "", qaLabels[item.qa?.content] || "待检查", qaLabels[item.qa?.format] || "待检查",
    qaLabels[item.qa?.render] || "待检查", qaLabels[item.qa?.privacy] || "待检查", `快照：${generation.snapshot_id || "未登记"}`,
  ]);
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const normalizer = fileURLToPath(new URL("./normalize_xlsx_views.py", import.meta.url));
const normalized = spawnSync(
  process.env.PYTHON || "python3",
  [normalizer, outputPath, "--freeze-rows", "3", "--default-font", "Microsoft YaHei"],
  { encoding: "utf8" },
);
if (normalized.status !== 0) {
  throw new Error(`XLSX冻结窗格兼容处理失败：${normalized.stderr || normalized.stdout || "未知错误"}`);
}

const inspection = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  maxChars: 4000,
});
const inspectionText = inspection.ndjson || "";
if (/\"match\"/.test(inspectionText) || /#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A/.test(inspectionText)) {
  throw new Error(`工作簿发现公式错误：${inspectionText.slice(0, 800)}`);
}

if (qaDir) {
  await fs.mkdir(qaDir, { recursive: true });
  const names = ["项目说明", "变量编码", "原始数据", "清理编码", "统计分析", "图表结果", "证据索引", "照片登记", "材料进度"];
  for (const [index, name] of names.entries()) {
    const preview = await workbook.render({ sheetName: name, autoCrop: "all", scale: 1, format: "png" });
    await fs.writeFile(path.join(qaDir, `${String(index + 1).padStart(2, "0")}_${name}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
}

console.log(`已填充：${outputPath}`);
if (qaDir) console.log(`逐表预览：${qaDir}`);
