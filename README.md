# build-k12-research-project

面向贵州省及黔东南州中小学教师教育科研课题的 Codex Skill。它把选题、申报、开题、研究工具、Word 表格、XLSX 数据、真实照片证据、中期、研究报告和结题材料组织为同一套可追溯项目，而不是彼此矛盾的独立文稿。

## 能做什么

- 根据学校、学段、学科、年级/班级和真实教学问题推荐 5—8 个方向并规范拟题；
- 题目确认后建立唯一项目主清单，按申请—开题—实施—数据—案例—结题的依赖顺序生成；
- 兼顾语文、数学、英语、物理、化学、生物、科学、道德与法治、历史、地理、音乐、美术、体育与健康、信息科技、劳动、综合实践、心理健康、幼小衔接及学校管理等场景；
- 提供 7 个通用 DOCX 结构母版、1 个含 9 张工作表的 XLSX 数据母版、26项生命周期初始化器及整套审计脚本；
- 主学科与每个关联学科分别登记研究功能、课标/教材范围、专项证据和复核人，支持真正的跨学科材料链；
- 强制区分计划、实施和完成状态，不伪造调查数据、访谈原话、照片、签章、专家意见或成果；
- 每个材料包生成 `00_课题材料包注意事项_真实性与待办清单.docx`，专门列明真实照片、原始材料、时间冲突、签章和增强建议。

## 安装

在 Codex 中直接说：

> 使用 `$skill-installer` 安装 `https://github.com/ydm8964-art/build-k12-research-project/tree/main/skills/build-k12-research-project`

也可以使用 Skill Installer 脚本：

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo ydm8964-art/build-k12-research-project \
  --path skills/build-k12-research-project
```

安装后重新启动 Codex，使新 Skill 生效。

## 使用

可以从一句话开始：

> 使用 `$build-k12-research-project`。学校为……，学段/学科为……，任教年级和班级为……，我最想解决的教学问题是……。先给我课题方向，题目确认后再生成完整材料包。

如果已有当年通知、官方 Word/Excel/PDF 附件或历史材料包，请一并提供。Skill 会优先使用当年官方附件；仓库内母版仅在没有官方格式时作为通用结构，不能冒充官方表格。

题目确认后可先复制`references/project-intake.example.json`填写一次采集信息，再运行`initialize_project_package.py`。它会建立标准文件夹、26项生命周期材料登记、注意事项、交付索引和工作簿草稿；真实数据、照片、签章和官方意见仍按阶段补入，不能由初始化器伪造。

## 运行环境

先运行：

```bash
python skills/build-k12-research-project/scripts/check_environment.py
```

Python 端需要 `python-docx`；照片元数据和 PDF 深度审计建议安装 `Pillow`、`pypdf`。预生成的 XLSX 母版可直接使用。重建母版时先加载 Codex 工作区依赖，把生成脚本和冻结窗格兼容脚本复制到同一可写目录，建立指向其`node_modules`的符号链接，再用其Node运行；主脚本只从公开包入口导入`@oai/artifact-tool`。

## 质量与真实性边界

机器审计通过不等于官方受理。年度通知、报送系统、签章、限额、学科事实、照片授权、真实数据和逐页效果仍须由负责人核验。任何真实证据缺失时，材料只能保持相应待办状态，不能标记为“整套可直接提交”。

## 仓库结构

```text
skills/build-k12-research-project/
├── SKILL.md
├── agents/openai.yaml
├── assets/templates/        # DOCX 与 XLSX 通用母版
├── references/              # 流程、格式、学科、证据和地方适配规则
└── scripts/                 # 生成、环境检查与一键预检
tests/                       # 可移植性、隐私、格式与逻辑回归测试
```

## 许可

[MIT](LICENSE)
