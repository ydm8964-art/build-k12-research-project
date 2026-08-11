#!/usr/bin/env node
/** Build the generic, non-official K-12 research data workbook. */

import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";


async function loadArtifactTool() {
  try {
    return await import("@oai/artifact-tool");
  } catch (firstError) {
    const bundled = path.resolve(
      path.dirname(process.execPath),
      "..",
      "node_modules",
      "@oai",
      "artifact-tool",
      "dist",
      "artifact_tool.mjs",
    );
    try {
      await fs.access(bundled);
      return await import(pathToFileURL(bundled).href);
    } catch {
      throw new Error(
        "缺少@oai/artifact-tool。请使用Codex工作区依赖中的Node运行本脚本，或在当前Node环境安装该包。",
        { cause: firstError },
      );
    }
  }
}


const { SpreadsheetFile, Workbook } = await loadArtifactTool();


const args = process.argv.slice(2);
const outputPath = path.resolve(args.find((value) => !value.startsWith("--")) || "project-data-workbook.xlsx");
const qaIndex = args.indexOf("--qa-dir");
const qaDir = qaIndex >= 0 && args[qaIndex + 1] ? path.resolve(args[qaIndex + 1]) : null;

const workbook = Workbook.create();
const COLORS = {
  navy: "#1F4E78",
  blue: "#D9EAF7",
  input: "#FFF2CC",
  formula: "#E2F0D9",
  note: "#F2F2F2",
  border: "#B7C9D6",
  white: "#FFFFFF",
};

function createSheet(name, title, description, headers, widths) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A2").values = [[description]];
  sheet.getRangeByIndexes(0, 0, 1, headers.length).format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white, size: 14 },
  };
  sheet.getRangeByIndexes(1, 0, 1, headers.length).format = {
    fill: COLORS.blue,
    font: { color: "#1F1F1F", size: 10 },
    wrapText: true,
  };
  sheet.getRangeByIndexes(2, 0, 1, headers.length).values = [headers];
  sheet.getRangeByIndexes(2, 0, 1, headers.length).format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: COLORS.border },
  };
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 40, 1).format.columnWidth = width;
  });
  sheet.getRangeByIndexes(3, 0, 30, headers.length).format = {
    fill: COLORS.input,
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: COLORS.border },
  };
  sheet.freezePanes.freezeRows(3);
  return sheet;
}

function addTable(sheet, name, lastColumn, lastRow = 33) {
  sheet.tables.add(`A3:${lastColumn}${lastRow}`, true, name);
}

const info = createSheet(
  "项目说明",
  "课题研究数据工作簿（通用结构母版）",
  "本文件不是官方申报附件。黄色为人工录入，绿色为公式/引用；真实数据、政策信息和署名必须核验后填写。",
  ["项目字段", "内容", "核验状态", "来源/责任人", "最后更新", "说明"],
  [24, 42, 16, 22, 16, 42],
);
info.getRange("A4:F14").values = [
  ["课题名称", "[填写]", "未核验", "负责人", "", "与申请书、开题、结题材料完全一致"],
  ["负责人", "[填写]", "未核验", "本人", "", "按报送版填写"],
  ["学校", "[填写]", "未核验", "学校", "", "使用规范全称"],
  ["学段/学科", "[填写]", "未核验", "负责人", "", "跨学科同时登记实际关联学科"],
  ["研究周期", "[填写]", "未核验", "立项通知", "", "yyyy-mm-dd至yyyy-mm-dd"],
  ["数据截止日", "[填写]", "未核验", "数据管理员", "", "Word、PDF、XLSX使用同一截止日"],
  ["样本口径", "[填写]", "未核验", "研究工具", "", "说明计划数、回收数、有效数与排除规则"],
  ["匿名规则", "匿名ID；身份映射表单独加密保存", "待确认", "负责人", "", "不得在分析工作簿保留学生姓名"],
  ["工作簿版本", "V0.1", "工作版", "数据管理员", "", "每次修改留存版本号"],
  ["当年通知/模板", "[填写来源ID]", "待核验", "负责人", "", "年度变化后重新核验"],
  ["使用边界", "仅作通用研究数据底稿", "已说明", "", "", "不得冒充官方电子表格"],
];
info.getRange("C4:C14").dataValidation = { rule: { type: "list", values: ["未核验", "待确认", "待核验", "工作版", "已说明", "已核验"] } };
info.getRange("E4:E14").format.numberFormat = "yyyy-mm-dd";
addTable(info, "ProjectInfo", "F", 14);

const codebook = createSheet(
  "变量编码",
  "变量编码表",
  "每个变量一行；先定义编码、缺失值和计分方向，再收集数据。",
  ["变量名", "题号/来源", "维度", "题型", "取值/选项代码", "缺失值", "计分方向", "用途", "版本"],
  [18, 18, 20, 16, 34, 14, 16, 26, 14],
);
codebook.getRange("A4:I8").values = [
  ["anonymous_id", "系统生成", "身份", "文本", "S001…", "空", "不计分", "匿名关联", "V0.1"],
  ["measure_date", "记录日期", "时间", "日期", "yyyy-mm-dd", "空", "不计分", "时间逻辑", "V0.1"],
  ["group_code", "对象组别", "分组", "单选", "A=实施组；B=参照组", "空", "不计分", "分组比较", "V0.1"],
  ["pre_score", "前测", "核心指标", "数值", "0—100", "空", "正向", "基线", "V0.1"],
  ["post_score", "后测", "核心指标", "数值", "0—100", "空", "正向", "效果评价", "V0.1"],
];
codebook.getRange("D4:D33").dataValidation = { rule: { type: "list", values: ["文本", "日期", "单选", "多选0/1", "量表", "数值", "长文本"] } };
codebook.getRange("G4:G33").dataValidation = { rule: { type: "list", values: ["正向", "反向", "不计分"] } };
addTable(codebook, "VariableCodebook", "I");

const raw = createSheet(
  "原始数据",
  "原始数据录入",
  "一行一条记录；只使用匿名ID。原始值不做覆盖式清洗，修正原因写入备注。",
  ["匿名ID", "测量日期", "组别", "前测分", "后测分", "是否有效", "录入人", "备注"],
  [16, 16, 14, 14, 14, 14, 16, 36],
);
raw.getRange("A4:H4").values = [["[填写]", "", "", "", "", "待复核", "[填写]", "示例行仅提示录入方式，正式录入时替换"]];
raw.getRange("B4:B33").format.numberFormat = "yyyy-mm-dd";
raw.getRange("C4:C33").dataValidation = { rule: { type: "list", values: ["A", "B", "其他"] } };
raw.getRange("D4:E33").dataValidation = { rule: { type: "decimal", operator: "between", formula1: 0, formula2: 100 } };
raw.getRange("F4:F33").dataValidation = { rule: { type: "list", values: ["是", "否", "待复核"] } };
addTable(raw, "RawData", "H");

const clean = createSheet(
  "清理编码",
  "清理与派生变量",
  "通过公式引用原始数据，不覆盖原始值；人工填写排除理由时保留审计痕迹。",
  ["匿名ID", "组别", "前测原值", "后测原值", "是否有效", "增量", "纳入分析", "问题标记", "排除理由"],
  [16, 14, 14, 14, 14, 14, 16, 24, 36],
);
clean.getRange("A4:E4").formulas = [[
  "=IF('原始数据'!A4=\"\",\"\",'原始数据'!A4)",
  "=IF('原始数据'!C4=\"\",\"\",'原始数据'!C4)",
  "=IF('原始数据'!D4=\"\",\"\",'原始数据'!D4)",
  "=IF('原始数据'!E4=\"\",\"\",'原始数据'!E4)",
  "=IF('原始数据'!F4=\"\",\"\",'原始数据'!F4)",
]];
clean.getRange("A4:E33").fillDown();
clean.getRange("F4").formulas = [["=IF(OR(C4=\"\",D4=\"\"),\"\",D4-C4)"]];
clean.getRange("F4:F33").fillDown();
clean.getRange("G4").formulas = [["=IF(A4=\"\",\"\",IF(E4=\"是\",\"纳入\",IF(E4=\"否\",\"排除\",\"待复核\")))"]];
clean.getRange("G4:G33").fillDown();
clean.getRange("A4:G33").format.fill = COLORS.formula;
clean.getRange("H4:I33").format.fill = COLORS.input;
clean.getRange("G4:G33").dataValidation = { rule: { type: "list", values: ["纳入", "排除", "待复核"] } };
addTable(clean, "CleanData", "I");

const stats = createSheet(
  "统计分析",
  "统计分析",
  "结果由公式引用数据区；正式研究应按工具性质、样本设计和统计前提补充适当分析。",
  ["指标", "结果", "单位/口径", "Excel来源", "复核状态", "复核人", "复核日期"],
  [24, 18, 28, 34, 16, 16, 16],
);
stats.getRange("A4:A8").values = [["有效记录数"], ["前测均值"], ["后测均值"], ["平均增量"], ["完整配对数"]];
stats.getRange("B4:B8").formulas = [
  ["=COUNTIF('原始数据'!F4:F33,\"是\")"],
  ["=IFERROR(AVERAGEIF('原始数据'!F4:F33,\"是\",'原始数据'!D4:D33),\"\")"],
  ["=IFERROR(AVERAGEIF('原始数据'!F4:F33,\"是\",'原始数据'!E4:E33),\"\")"],
  ["=IFERROR(AVERAGEIF('清理编码'!G4:G33,\"纳入\",'清理编码'!F4:F33),\"\")"],
  ["=COUNTIFS('清理编码'!G4:G33,\"纳入\",'清理编码'!C4:C33,\"<>\",'清理编码'!D4:D33,\"<>\")"],
];
stats.getRange("C4:C8").values = [["条；F列=是"], ["0—100；有效记录"], ["0—100；有效记录"], ["后测－前测；纳入记录"], ["前后测均非空且纳入"]];
stats.getRange("D4:D8").values = [["原始数据!F4:F33"], ["原始数据!D4:D33"], ["原始数据!E4:E33"], ["清理编码!F4:F33"], ["清理编码!C4:D33"]];
stats.getRange("E4:E8").values = [["待复核"], ["待复核"], ["待复核"], ["待复核"], ["待复核"]];
stats.getRange("B4:B8").format.fill = COLORS.formula;
stats.getRange("B5:B7").format.numberFormat = "0.00";
stats.getRange("E4:E33").dataValidation = { rule: { type: "list", values: ["待复核", "已复核", "不适用"] } };
stats.getRange("G4:G33").format.numberFormat = "yyyy-mm-dd";
addTable(stats, "Statistics", "G");

const charts = createSheet(
  "图表结果",
  "Word/PDF表图登记",
  "只登记已经复核的结果；每个表图必须能追溯到工作表和单元格范围。",
  ["表/图号", "标题", "结果值", "单位", "来源工作表", "来源区域", "统计口径", "生成日期", "复核人", "状态"],
  [14, 32, 16, 14, 18, 22, 32, 16, 16, 14],
);
charts.getRange("A4:J7").values = [
  ["表1", "有效记录数", "", "条", "统计分析", "B4", "F列=是", "", "", "待复核"],
  ["表2", "前测均值", "", "分", "统计分析", "B5", "有效记录", "", "", "待复核"],
  ["表3", "后测均值", "", "分", "统计分析", "B6", "有效记录", "", "", "待复核"],
  ["表4", "平均增量", "", "分", "统计分析", "B7", "纳入记录", "", "", "待复核"],
];
charts.getRange("C4:C7").formulas = [["='统计分析'!B4"], ["='统计分析'!B5"], ["='统计分析'!B6"], ["='统计分析'!B7"]];
charts.getRange("C4:C33").format.fill = COLORS.formula;
charts.getRange("H4:H33").format.numberFormat = "yyyy-mm-dd";
charts.getRange("J4:J33").dataValidation = { rule: { type: "list", values: ["待复核", "已复核", "已写入Word", "已更新PDF"] } };
addTable(charts, "FigureRegister", "J");

const evidence = createSheet(
  "证据索引",
  "证据索引",
  "每条结论链接到真实原件；文件路径优先使用材料包内相对路径。",
  ["证据ID", "类型", "真实日期", "相对文件路径", "SHA-256", "对应问题", "对应材料", "对应结论", "隐私等级", "授权/核验状态", "责任人"],
  [18, 18, 16, 36, 68, 22, 22, 30, 16, 20, 16],
);
evidence.getRange("B4:B33").dataValidation = { rule: { type: "list", values: ["原始数据", "访谈", "观察", "测评", "学生作品", "照片", "文件", "审批", "传播证明"] } };
evidence.getRange("C4:C33").format.numberFormat = "yyyy-mm-dd";
evidence.getRange("I4:I33").dataValidation = { rule: { type: "list", values: ["机密", "内部", "报送", "匿名", "公开"] } };
evidence.getRange("J4:J33").dataValidation = { rule: { type: "list", values: ["计划", "待授权", "已采集", "已核验", "限制使用"] } };
addTable(evidence, "EvidenceIndex", "K");

const photos = createSheet(
  "照片登记",
  "真实照片证据登记",
  "只登记教师/学校真实提供的照片；不得用AI或网络图片冒充研究过程。原件与派生件分别留存。",
  ["照片ID", "原文件名", "原件SHA-256", "真实日期", "地点", "活动", "拍摄/来源", "授权状态", "人物处理", "图题", "替代文本", "对应材料/案例", "派生文件", "派生SHA-256", "图号/位置"],
  [20, 30, 68, 16, 22, 28, 22, 18, 20, 38, 38, 28, 34, 68, 22],
);
photos.getRange("D4:D33").format.numberFormat = "yyyy-mm-dd";
photos.getRange("H4:H33").dataValidation = { rule: { type: "list", values: ["计划", "待取得", "已取得", "无需", "限制", "撤回"] } };
photos.getRange("I4:I33").dataValidation = { rule: { type: "list", values: ["不适用", "无人脸", "背影", "裁切", "模糊", "明确同意可识别", "仅限原件"] } };
addTable(photos, "PhotoRegister", "O");

const progress = createSheet(
  "材料进度",
  "材料生成与核验进度",
  "材料状态只反映真实完成度；含缺件的材料不得标记为可提交。",
  ["材料ID", "材料名称", "角色", "负责人", "计划日期", "实际日期", "状态", "依赖材料", "相对文件路径", "内容QA", "格式QA", "渲染QA", "隐私QA", "备注"],
  [16, 32, 22, 16, 16, 16, 18, 24, 38, 14, 14, 14, 14, 36],
);
progress.getRange("E4:F33").format.numberFormat = "yyyy-mm-dd";
progress.getRange("G4:G33").dataValidation = { rule: { type: "list", values: ["计划", "草稿", "待数据", "待照片", "待签章", "已核验", "可提交", "已提交", "已归档"] } };
for (const col of ["J", "K", "L", "M"]) {
  progress.getRange(`${col}4:${col}33`).dataValidation = { rule: { type: "list", values: ["待检查", "通过", "失败", "不适用"] } };
}
addTable(progress, "MaterialProgress", "N");

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
await fs.rm(`${outputPath}.inspect.ndjson`, { force: true });

if (qaDir) {
  await fs.mkdir(qaDir, { recursive: true });
  const names = ["项目说明", "变量编码", "原始数据", "清理编码", "统计分析", "图表结果", "证据索引", "照片登记", "材料进度"];
  for (const [index, name] of names.entries()) {
    const preview = await workbook.render({ sheetName: name, autoCrop: "all", scale: 1, format: "png" });
    const filename = `${String(index + 1).padStart(2, "0")}_${name}.png`;
    await fs.writeFile(path.join(qaDir, filename), new Uint8Array(await preview.arrayBuffer()));
  }
}

console.log(`已生成：${outputPath}`);
if (qaDir) console.log(`逐表预览：${qaDir}`);
