#!/usr/bin/env python3
"""Deterministic folder and material blueprint for K-12 research-project packages."""

from __future__ import annotations

from copy import deepcopy

FOLDERS = (
    "01政策与立项",
    "02申报",
    "03开题",
    "04研究工具",
    "05原始数据",
    "06分析报告",
    "07实践方案",
    "08课例案例",
    "09过程管理",
    "10成果与结题",
    "11附录证据/照片原件（受控）",
    "11附录证据/照片派生件",
    "11附录证据/授权与审批状态",
    "11附录证据/作品与证明",
)

WORKBOOK_SHEETS = [
    "项目说明",
    "变量编码",
    "原始数据",
    "清理编码",
    "统计分析",
    "图表结果",
    "证据索引",
    "照片登记",
    "材料进度",
]


def _qa(*, data: str = "not-applicable", photo: str = "not-applicable") -> dict[str, str]:
    return {
        "content": "pending",
        "format": "pending",
        "render": "pending",
        "privacy": "pending",
        "data": data,
        "photo": photo,
    }


def _material(
    material_id: str,
    name: str,
    role: str,
    stage: str,
    folder: str,
    profile: str,
    *,
    status: str = "planned",
    output_format: str = "docx",
    privacy: str = "internal",
    depends_on: tuple[str, ...] = (),
    scopes: tuple[str, ...] = ("full-lifecycle-kit",),
    data_qa: str = "not-applicable",
    photo_qa: str = "not-applicable",
) -> dict:
    suffix = output_format
    filename = f"{material_id}_{name}_v0.1.{suffix}"
    item = {
        "id": material_id,
        "name": name,
        "material_role": role,
        "status": status,
        "output_format": output_format,
        "format_profile": profile,
        "reference_template": None,
        "reference_source_id": None,
        "stage": stage,
        "privacy_class": privacy,
        "version": "0.1",
        "data_cutoff": None,
        "required_for_submission": False,
        "planned_file_path": f"{folder}/{filename}" if folder else filename,
        "file_path": None,
        "sha256": None,
        "qa": _qa(data=data_qa, photo=photo_qa),
        "depends_on": list(depends_on),
        "_scopes": list(scopes),
    }
    if output_format == "xlsx":
        item["required_sheets"] = list(WORKBOOK_SHEETS)
        item["allowed_hidden_sheets"] = []
    return item


ALL = ("application-kit", "implementation-kit", "full-lifecycle-kit", "closing-kit")
IMPLEMENT = ("implementation-kit", "full-lifecycle-kit")
CLOSING = ("closing-kit", "full-lifecycle-kit")

MATERIAL_BLUEPRINTS = (
    _material("M00", "课题材料包注意事项_真实性与待办清单", "attention-items", "supporting", "", "attention-items", scopes=ALL),
    _material("M01", "课题申请书", "application", "application", "02申报", "official-exact", privacy="submission", scopes=("application-kit", "full-lifecycle-kit")),
    _material("M02", "匿名评审活页", "anonymous-form", "application", "02申报", "official-exact", privacy="anonymous", scopes=("application-kit", "full-lifecycle-kit")),
    _material("M03", "开题报告", "opening", "opening", "03开题", "official-exact", privacy="submission", depends_on=("M01",), scopes=IMPLEMENT),
    _material("M04", "告知同意与照片授权", "consent-form", "instrument", "04研究工具", "research-form", depends_on=("M03",), scopes=IMPLEMENT),
    _material("M05", "学生问卷或学情调查工具", "blank-instrument", "instrument", "04研究工具", "research-form", depends_on=("M03",), scopes=IMPLEMENT),
    _material("M06", "访谈提纲", "interview-guide", "instrument", "04研究工具", "research-form", depends_on=("M03",), scopes=IMPLEMENT),
    _material("M07", "课堂观察表", "observation-form", "instrument", "04研究工具", "research-form", depends_on=("M03",), scopes=IMPLEMENT),
    _material("M08", "前后测或作品评价工具", "assessment-tool", "instrument", "04研究工具", "research-form", depends_on=("M03",), scopes=IMPLEMENT),
    _material("M09", "课题研究数据工作簿", "data-workbook", "data", "05原始数据", "spreadsheet-workbook", output_format="xlsx", privacy="confidential", depends_on=("M04", "M05", "M06", "M07", "M08"), scopes=("implementation-kit", "full-lifecycle-kit", "closing-kit"), data_qa="pending", photo_qa="pending"),
    _material("M10", "原始记录与受控保管索引", "raw-data", "data", "05原始数据", "evidence-sheet", privacy="confidential", depends_on=("M04", "M05", "M06", "M07", "M08"), scopes=("full-lifecycle-kit", "closing-kit"), data_qa="pending"),
    _material("M11", "现状诊断与综合分析报告", "analysis-report", "analysis", "06分析报告", "analysis-report", status="pending-data", depends_on=("M09", "M10"), scopes=("implementation-kit", "full-lifecycle-kit", "closing-kit"), data_qa="pending"),
    _material("M12", "课题干预与实施方案", "intervention-plan", "intervention", "07实践方案", "research-form", depends_on=("M11",), scopes=IMPLEMENT),
    _material("M13", "代表性教学设计或活动方案", "lesson-plan", "intervention", "08课例案例", "lesson-long", depends_on=("M12",), scopes=IMPLEMENT),
    _material("M14", "学生任务单或学习支架", "task-sheet", "intervention", "08课例案例", "research-form", depends_on=("M13",), scopes=IMPLEMENT),
    _material("M15", "学习成果评价量规", "rubric", "intervention", "08课例案例", "research-form", depends_on=("M12",), scopes=IMPLEMENT),
    _material("M16", "教学案例集", "casebook", "intervention", "08课例案例", "casebook", status="pending-data", depends_on=("M13", "M14", "M15"), scopes=IMPLEMENT, data_qa="pending", photo_qa="pending"),
    _material("M17", "实施保真度与课堂过程记录", "fidelity-log", "midterm", "09过程管理", "research-form", depends_on=("M12",), scopes=IMPLEMENT, data_qa="pending"),
    _material("M18", "教研活动与会议记录", "meeting-record", "midterm", "09过程管理", "research-form", depends_on=("M03",), scopes=IMPLEMENT),
    _material("M19", "中期或阶段研究报告", "progress-report", "midterm", "09过程管理", "research-form", status="pending-data", depends_on=("M11", "M12", "M17", "M18"), scopes=IMPLEMENT, data_qa="pending", photo_qa="pending"),
    _material("M20", "研究过程照片与作品证据册", "evidence-book", "supporting", "11附录证据", "evidence-sheet", status="pending-photo", privacy="submission", depends_on=("M17", "M18"), scopes=CLOSING, photo_qa="pending"),
    _material("M21", "最终研究报告", "final-report", "final", "10成果与结题", "analysis-report", status="pending-data", privacy="submission", depends_on=("M09", "M11", "M16", "M17", "M19", "M20"), scopes=CLOSING, data_qa="pending", photo_qa="pending"),
    _material("M22", "结题申请或鉴定书", "closing-application", "closing", "10成果与结题", "official-exact", status="pending-signature", privacy="submission", depends_on=("M21",), scopes=CLOSING),
    _material("M23", "成果目录与承诺成果核销表", "achievement-catalog", "closing", "10成果与结题", "research-form", status="pending-data", privacy="submission", depends_on=("M16", "M21"), scopes=CLOSING, data_qa="pending"),
    _material("M24", "成果证明与专家评议索引", "proof", "closing", "10成果与结题", "evidence-sheet", status="pending-data", privacy="submission", depends_on=("M23",), scopes=CLOSING, data_qa="pending"),
    _material("M25", "整套材料目录与交付索引", "index", "supporting", "", "evidence-sheet", depends_on=("M22", "M23", "M24"), scopes=ALL),
)


def materials_for_scope(scope: str) -> list[dict]:
    selected = [deepcopy(item) for item in MATERIAL_BLUEPRINTS]
    for item in selected:
        item["included_in_batch"] = scope in item["_scopes"]
        item.pop("_scopes", None)
    included_ids = [item["id"] for item in selected if item["included_in_batch"] and item["id"] != "M25"]
    for item in selected:
        if item["id"] == "M25":
            item["depends_on"] = included_ids
        elif item["id"] == "M00":
            item["planned_file_path"] = "00_课题材料包注意事项_真实性与待办清单_v0.1.docx"
    return selected
