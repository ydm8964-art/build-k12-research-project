---
name: build-k12-research-project
description: 为贵州省及黔东南州中小学教师规划、申报、实施和结题教育科研课题。用于根据教师、学校、学科、学段、班级和教学问题推荐方向、规范选题，并按当年官方模板生成相互一致的申请书、开题报告、研究工具、Word表格、数据XLSX、真实照片证据、教学案例、研究报告和结题材料；也用于审核格式、表格、时间、数据、隐私、署名、学科事实、证据闭环与整套文件夹。
---

# 中小学课题全流程生成

把一个课题视为同一研究项目的证据系统，不把材料当作互不关联的文章。始终维护唯一的“项目主清单”，再由它生成和校验每份材料。

## 入口判断

按用户当前阶段进入流程：

1. 只有教师基本信息：执行“信息采集与选题”。
2. 已有方向、尚未定题：评估并提供候选题目。
3. 已确认题目：建立项目主清单和完整材料目录，经确认后生成。
4. 已有部分材料：先提取事实和承诺，建立主清单，再补齐或修订。
5. 要求审核：执行全套一致性检查，不擅自重写未授权材料。

## 必读路由

- 信息采集、方向推荐、题目规范：读 [intake-and-topic.md](references/intake-and-topic.md)。
- 只有基本情况，需要稳定生成候选题目并衔接全套材料：以[teacher-profile.example.json](references/teacher-profile.example.json)建立输入，运行`project_workflow.py`；候选题由`generate_topic_candidates.py`校验数量、学科证据和跨学科覆盖。
- 确定整套材料范围、阶段和依赖关系：读 [dossier-map.md](references/dossier-map.md)。
- 撰写具体材料：读 [material-specifications.md](references/material-specifications.md)。
- 设计问卷、访谈、观察、数据分析和效果证据：读 [methods-and-evidence.md](references/methods-and-evidence.md)。
- 排期或终审：读 [timeline-and-quality.md](references/timeline-and-quality.md)。
- 涉及贵州省、黔东南州申报或结题：读 [guizhou-qiandongnan.md](references/guizhou-qiandongnan.md)。
- 用户要求沿用本地参考材料的方法、栏目或成套形态：读 [source-derived-blueprints.md](references/source-derived-blueprints.md)。该文件只提供结构母版，不允许复制其中的项目事实、人员、日期或数据。
- 用户要求“一次性生成全套”或只提供一次基本信息后批量生成：读 [one-shot-generation-protocol.md](references/one-shot-generation-protocol.md)，先确定成套范围和真实性阶段，再整批生成。
- 需要判断用户提供的本地历史材料包中哪类材料可作格式母版、结构参考或仅作内容示例：读 [reference-material-catalog.md](references/reference-material-catalog.md)，不得把有缺陷的旧文件误设为官方精确模板。
- 生成或审核Word、Word表格、封面、目录、成果汇编：读 [format-and-tables.md](references/format-and-tables.md)和[26项材料固定版式合同](references/material-format-contracts.md)；机器执行源为`references/material-format-contracts.json`。
- 生成问卷数据、访谈编码、课堂观察、统计分析、证据索引或材料进度电子表格：读 [spreadsheet-standards.md](references/spreadsheet-standards.md)。
- 涉及匿名评审、个人信息、学生数据、知情同意、研究工具质量、效果结论、案例安全、引用核验、版本管理或最终交付：读 [research-integrity-and-delivery.md](references/research-integrity-and-delivery.md)。
- 涉及真实课堂照片、活动照片、学生作品照片、教研现场、照片证据册或Word插图位置：读 [photo-evidence-and-placement.md](references/photo-evidence-and-placement.md)。照片只能来自用户/学校真实提供，不得生成或借用图片冒充研究过程。
- 涉及时政、地图、实验原理、跨学科知识、乡土文化、课例作者、外部协作者、案例实施状态或策略效果：读 [subject-authorship-and-implementation.md](references/subject-authorship-and-implementation.md)。
- 生成任何学科的选题、工具、课例、证据或注意事项文件：读 [subject-specific-evidence.md](references/subject-specific-evidence.md)，采用“通用底座＋学科专项清单”；跨学科课题同时核验主学科和实际关联学科。
- 组装正式报送/结题文件夹、核销承诺成果或宣布“整套可直接提交”：读 [package-finalization.md](references/package-finalization.md)。
- 生成材料包中的真实照片、原始材料、时间逻辑和建议补充事项总表：读 [attention-items-file.md](references/attention-items-file.md)。每个成套包都必须生成该控制文件。

## 阶段一：信息采集与选题

一次性收集必要信息；用户未知的项目允许标注“待定”，不得用虚构事实补齐。至少获取：

- 教师姓名、学校、地区、学段、学科、年级/班级、职务职称；
- 日常教学中最想解决的真实问题、已有实践和可获得资源；
- 拟申报年份、课题级别/管理单位、计划周期、团队情况；
- 偏好的研究对象、成果形式，以及是否有当年通知和官方模板。

推荐 5—8 个有明显差异的方向。每个方向给出“拟题、核心问题、研究对象、创新点、主要成果、实施难度、数据可得性”，并说明优先级。题目确认前不批量生成全套材料。

不要每次从空白提示词临时拼选题。先把已知基本情况写入独立JSON，再运行：

```bash
python scripts/project_workflow.py start --profile teacher-profile.json --root topic-workspace --count 6
```

把`topic-candidates.md`中的5—8项候选直接展示给用户；允许用户回复候选ID或提出修改。脚本输出是确定性底稿，Agent仍须检查题目是否自然、是否贴合用户原话、是否使用当年政策/课标的准确名称；不得为提高分数虚构政策依据。

选题评分只能依据已登记的基线证据、已有做法、可用资源、班级和学科条件动态计算。没有乡土/社区/地方资源依据时不得默认生成“乡土资源融入”题目；选题后若教师、学校、学科、班级或真实问题发生变化，重新生成候选题，禁止沿用旧候选逻辑。

题目应同时包含研究对象或情境、核心变量或策略、研究内容/目标，避免空泛口号、范围过大、因果承诺过强和多个研究中心并列。

## 阶段二：建立唯一项目主清单

题目确认后，建立结构化主清单，至少包括：

- 项目标识：规范题目、负责人、学校、主学科、实际关联学科、学段、申报层级和年份；
- 问题链：现实问题、证据、原因假设、核心研究问题和子问题；
- 目标链：总目标、分目标、研究内容、方法、活动和预期成果；
- 对象与样本：年级、班级、教师/学生人数、选取方式；
- 时间轴：前期基础、申报、立项、开题、各研究阶段、结题；
- 成果清单：阶段成果、最终成果、作者/责任人、完成时间；
- 证据清单：工具、原始数据、过程记录、学生作品、评价、照片和反思；
- 术语表：核心概念、固定简称、关键数据和统一措辞；
- 材料状态：待写、草稿、已核验、待真实数据、已完成。
- 治理信息：项目当前状态、是否延期/变更、数据截止日期、知情同意和隐私版本；
- 来源登记：政策、课程标准、文献和官方模板的来源编号、核验状态和引用位置；
- 版本登记：工作版、报送版、匿名版、公开版的文件名、版本号、隐私等级和责任人。
- 当年要求快照：管理单位、适用年度、核验日期、截止日期、通知/模板来源ID、必交材料ID、匿名要求、报送方式、命名/大小/份数规则；未核验不得进入“可提交”状态。
- 成套生成合同：`package_scope`、当前真实性阶段、单批次/增量模式、未知字段处理、目标版本和覆盖豁免；“全生命周期包”必须通过材料角色覆盖审计。
- 照片登记：照片ID、原件哈希、真实日期、活动、地点、拍摄/来源、授权范围、人物处理、对应材料/案例/结论、图题和替代文本；另明确`delivery_included`。敏感原件不随包时登记`custody_record`（保管责任人、受控定位、核验日期），不得为通过审计而复制进普通交付包。
- 贡献登记：成果ID、原作者、课题角色、实际贡献、是否立项成员、改编/授权来源和最终署名；
- 成果核销：申请书承诺名称、计划日期、实际文件、状态、证明和获批变更；
- 实施保真度：策略核心成分、计划/实际课次与时长、覆盖对象、执行质量、偏离原因和证据。
- 注意事项快照：当前阻断项、阶段必须补充、真实照片任务、其他真实原件、学科专项证据与风险、时间冲突、签章事项和建议增强材料；每项登记责任人、最迟时间、目标材料及完成标准。
- 学科覆盖表：主学科和每个实际关联学科分别登记研究功能、课程标准/教材范围、专项工具与证据、复核人和复核状态；`subject_coverage`必须与`subject + related_subjects`一一对应，不允许只在题目中写“跨学科”。

同时建立三张控制表：

- “承诺表”：申请书中的目标、内容、方法、阶段和预期成果；
- “证据表”：每个结论对应的工具、原始记录、数据、作品和评价；
- “材料依赖表”：每份材料依赖哪些前置事实和材料，修改上游时标出全部受影响文件。

先向用户展示“课题逻辑摘要＋材料目录＋时间轴”。只有题目已确认且必要事实足够时，才开始正式生成。

用户选择候选ID后运行：

```bash
python scripts/project_workflow.py select --root topic-workspace --topic-id TOPIC-02
```

用户对候选题目作了小幅修改时，追加`--title "最终确认题目"`；保留该候选的方向、证据和方法逻辑，同时把修改后的题目冻结为唯一正式题目。

若返回`awaiting-project-details`，只追问清单中的阻断字段；不要重复询问已经记录的信息，也不要臆造管理单位、年度模板、申报日或完成日。返回`ready-to-initialize`后运行`project_workflow.py initialize`，把已选题目、问题、策略、学科覆盖和时间统一冻结到主清单。

冻结时把地区/校情、职称职务、教材版本、年级班级、人数、问题表现、已有证据、已有做法、可用资源和选题依据写入`project_context/problem_context`；把用户偏好的每项成果分别转成`commitments`，不得只保留最终研究报告。

用户要求一次性生成时，只设置一个题目确认节点。确认后冻结同一主清单快照，按`application-kit/implementation-kit/full-lifecycle-kit/closing-kit`整批生成；已登记的信息不重复询问。未来事实缺失时仍可生成实施工具和结果材料骨架，但对应文件必须保持`pending-data/pending-photo/pending-signature`，并把整套状态标为`full-lifecycle-scaffold`，不能伪称结题终稿。

题目确认且一次采集信息完整后，优先以[project-intake.example.json](references/project-intake.example.json)为字段样例创建独立输入JSON，再运行初始化器。初始化器固定创建26项生命周期角色、标准文件夹、项目主清单、根目录注意事项、交付索引和数据工作簿草稿，不覆盖已有控制文件：

```bash
python scripts/initialize_project_package.py --intake project-intake.json --root delivery-folder
```

初始化产物是可继续制作的`scaffold`；DOCX/XLSX在完成真实内容填充、渲染和QA前保持`draft`。生成或更新单份文件后，使用`register_material_file.py`登记相对路径、SHA-256和状态；提升为`ready`必须提供真实QA报告，禁止只改JSON状态。

初始化后必须在材料包外的`workflow-control/`生成`material-generation-plan.json`，不得停在空目录或把26个角色清单当作已生成材料。该计划把每份材料转换为包含依赖、主清单事实来源、内容合同、格式母版、真实性阻断和QA门槛的任务；工作流控制JSON默认不混入正式交付包。

## 阶段三：按依赖顺序生成

按以下闭环持续执行，直到当前真实性阶段内所有可完成材料已经制作，不能生成终稿的材料也已有结构完整的工作稿和明确待办：

1. 运行`python scripts/project_workflow.py plan --root topic-workspace`刷新任务队列；
2. 只处理`material-generation-plan.json`中的`next_jobs`；`blocked_jobs`先补官方模板或真实输入；`waiting_jobs`读取各任务的`waiting_for_material_ids`，不得把等待依赖误报为无任务；
3. 从每个任务的`source_manifest_fields`读取唯一事实，按`content_contract`写正文；
4. 使用登记的官方模板或对应通用母版，按材料ID应用固定版式合同，完成内容、字体字号与段落、结构格式、渲染、隐私及适用的数据/照片QA；
5. 用`register_material_file.py`登记文件、哈希和真实状态；结果骨架可以登记`pending-data/pending-photo/pending-signature`，只有完整QA通过后才登记`ready`；
6. 上游事实变化时先更新主清单快照并运行`plan_incremental_refresh.py`，不要在下游文件中零散修改；
7. 每一批文件登记后运行`refresh_package_controls.py`重生注意事项和交付索引，再刷新工作簿；完成QA并重新登记两个控制文件后运行一键预检。

单个Agent执行整套生成时，要在同一任务中主动重复以上闭环，不要每写一份材料都重新向用户确认。只有遇到会改变研究事实、官方格式或真实性状态的阻断项时才暂停。

遵循以下顺序，前一层是后一层的约束：

1. 申报通知与官方表格核验；
2. 申请书/申报书；
3. 开题报告与实施方案；
4. 调查、访谈、观察、测评等研究工具；
5. 原始记录模板和数据台账；
6. 真实数据分析报告；
7. 教学或管理干预框架；
8. 教学设计、活动方案、案例和评价量规；
9. 阶段总结、中期报告、变更说明；
10. 研究报告、成果汇编、结题申请和鉴定材料。
11. 根据同一主清单生成`00_课题材料包注意事项_真实性与待办清单.docx`，再执行整套预检。

阶段材料必须递进：申请书负责“承诺”，开题报告负责“操作化”，中期材料负责“进展与调整”，结题材料负责“回答、证据和局限”。不得把申请书大段复制为开题报告，也不得用教案案例汇编代替最终研究报告。

缺少真实实施数据时，生成“可填写模板、编码表、分析方案和待补字段”，不得生成虚假回收数量、百分比、访谈原话、效果数据、专家意见、签字、盖章或照片。

缺少真实照片时，只在工作稿预定位置加入结构化备注`【待插入真实照片 PHO-…｜活动｜所缺日期/地点/授权】`，并同步进入待人工事项。不得用网络图片、AI生成图或其他项目照片代替。终稿仍缺照片时，删除相应证据性表述或标记`待照片`，不能标记“可直接使用”。

每一批输出完成后执行一次局部校验，不等到结题才发现矛盾：申请书后检查“承诺表”，开题后检查时间和分工，工具后检查题项—指标映射，分析后检查数据—结论映射，案例后检查活动—作品—评价证据链。

教学设计和案例生成后另做学科事实审查。时政、行政区划、地图、统计数据、实验原理、食品健康和安全内容使用权威来源；关联学科知识说明核验人/来源。非课题成员的课例不得直接包装为课题组原创成果，必须登记贡献、授权和最终署名。

## 阶段四：文档制作

优先使用当年官方 Word/Excel/PDF 附件作为版式母版，保留栏目、顺序、页数限制和签章位置。没有官方格式时，采用规范中文教育科研文档格式，但明确标注为通用稿。

在写正文前为每份材料确定`format_profile`、唯一`format_contract_id`、权威模板和版式合同。M00—M25的绑定、每级字体字号、首行缩进、行距、段前段后、页面和表格硬值见`references/material-format-contracts.json`，不得由Agent临时发挥。格式优先级为：当年官方附件 > 用户指定的同类模板 > 本Skill格式合同 > 通用格式。官方模板使用工作副本原位填写，不从空白文档重建，不用美化版式覆盖官方结构。

没有官方或用户指定模板的非官方材料，从`assets/templates/`中对应的通用结构母版复制工作件：`research-form.docx`、`analysis-report.docx`、`lesson-table.docx`、`lesson-long.docx`、`casebook.docx`、`evidence-sheet.docx`或`attention-items.docx`。这些母版只提供已验证的纸张、表格几何、分页和题注结构；年度字体、栏目名称、真实内容和签章要求仍须按版式合同覆盖。`official-exact`材料严禁改用这些通用母版。

每次生成材料包时，运行`scripts/generate_attention_items.py`从项目主清单生成注意事项文件。把它放在材料包根目录并以`00_`开头；内容至少包含状态快照、阻断/必须/阶段事项、真实照片清单、其他真实原件清单、学科专项真实性与安全核验、时间逻辑检查、增强建议和教师操作顺序。该文件默认仅供负责人内部使用，不冒充官方附件，也不因列出缺件而把缺件写成已经取得。

制作非官方DOCX时调用文档制作能力；若参考文件控制版式，先提炼模板结构再从参考副本生成。正文完成后必须依次运行`resolve_material_format.py`、`apply_docx_format_contract.py`、`audit_docx_style_contract.py`和`audit_docx_format.py`，然后渲染逐页检查：封面、目录、标题层级、字体字号、首行缩进、行距、段前段后、表格宽度、跨页表头、页眉页脚、页码、图片、空白页和签章区。任何一项失败都不得标记`ready`。更新目录域或明确提醒用户在 Word 中更新目录。输出文件名应包含序号、材料名称和版本/日期。

`official-exact`材料禁止运行通用套版脚本；必须以实际官方原件作为`--reference`，同时执行结构审计和字体段落合同审计。若没有当年模板，保持`blocked-template`，不得用通用字号猜测。

每份DOCX还要执行内容完整性审计。匿名/公开版出现身份证号、手机号或邮箱属于阻断错误；最终版的错字、编号跳号、长段重复、空占位、无证据的强结论和“声称有照片但文档无图”必须处理。官方模板或项目确需保留的身份字段，只能放在`submission`版本。

插入真实照片时，先登记原件和授权，再制作派生副本并插入。优先内嵌图片，保持长宽比；每张证据照片必须有连续图号、规范图题、照片ID、真实日期/活动、正文交叉引用和有意义的替代文本。匿名/公开版还要打码或裁切可识别人物并清理图片/DOCX元数据。图片修改或增删后重新编号、更新交叉引用并渲染逐页检查。

制作 XLSX 时调用电子表格能力，按“项目说明—变量编码—原始数据—清理/编码—统计分析—图表结果—证据索引—照片登记—材料进度”分层。无官方电子表格时，直接复制`assets/templates/project-data-workbook.xlsx`作为固定格式母版；如需重建，先加载Codex工作区依赖，把`build_generic_xlsx_template.mjs`和`normalize_xlsx_views.py`复制到同一可写工作目录，并建立指向加载器所返回`node_modules`的符号链接，再用返回的Node运行生成脚本，不得猜测或导入运行时内部路径。兼容脚本补足标准冻结窗格和默认中文字体。它不是官方报送表，不得替代当年附件。原始数据与分析分开，派生值使用公式，设置数据验证、筛选、冻结窗格和正确数据类型。导出前运行`audit_xlsx_structure.py`和`audit_xlsx_style_contract.py`，检查关键区域、公式错误并渲染查看全部9张工作表。

初始化后不要把空白工作簿直接交付。把`populate_project_workbook.mjs`与`normalize_xlsx_views.py`复制到同一可写运行目录，使用工作区依赖提供的Node和`node_modules`，从同一主清单写入项目说明、证据、照片和26项材料进度，并用`--qa-dir`渲染全部9张工作表；输出仍是草稿，真实数据区不自动伪填。

Word与Excel必须使用同一项目主清单、变量编码和统计口径。Word中的频数、比例、样本量、表图编号应能追溯到XLSX具体工作表和区域。

制作PDF时从已通过渲染的最终DOCX导出，检查页数、方向、字体、图片、表格、签章和可检索性。可编辑源文件、PDF定稿和数据工作簿使用同一版本号与数据截止日期。

## 阶段五：全套终审

逐项检查：

- 题目、姓名、学校、编号、学段、学科是否全套一致；
- 研究问题—目标—内容—方法—活动—成果—证据是否一一对应；
- 时间轴是否按真实事件排序，前期研究是否明确标注；
- 样本量、题号、表号、数据、百分比和多选题口径是否一致；
- 结论强度是否与证据匹配，开发案例与实际实施案例是否区分；
- 引用、参考文献、政策名称、文号和课程标准是否可核验；
- 官方格式、篇幅限制、附件命名、签字盖章处是否符合通知；
- 是否清除占位符、错别字、旧项目残留、过期年份和目录错页。
- 问卷、访谈、观察是否形成“工具—原始记录—统计/编码—分析报告”四件套；
- 案例集目录页码是否已更新，目录宣称的案例是否都在正文中；
- 学生层面、教师层面和课堂层面的效果结论是否分别有对应证据。
- 每份材料是否已确定并通过相应`format_profile`，官方表格是否与原模板结构一致；
- 每份材料是否绑定正确`format_contract_id`，标题层级、正文、列表、图表题和表格文字是否逐项通过固定字体字号、缩进、行距和段前段后审计；
- Word表格是否明确列宽、重复表头、合理内边距且无固定行高截字；
- XLSX是否分离原始数据与分析、公式无错误、字段类型正确并完成全工作表视觉检查。
- 申请—开题—中期—结题是否形成递进，而非段落机械重复；最终成果是否逐项兑现申请承诺；
- 是否区分现状工具、过程工具和效果工具，效果结论是否有前后测/多时点/作品量规等相称证据；
- 抽样、质性编码、观察记录、反例和研究局限是否如实交代，是否存在由小样本向全体不当外推；
- 工作版、报送版、匿名版、公开版是否正确分流，学生和教师个人信息、照片及文件属性是否妥善处理；
- 案例是否标明开发、试教、实施或验证状态，照片/作品/反馈陈述是否能追溯到证据编号；
- 校外、实验、制作和模型活动是否具备审批、同意、防护、应急和科学边界说明；
- 计划完成日已过时，是否如实登记结题、延期、终止或变更状态，而非继续沿用过期计划。
- 所有真实照片是否经过“原件登记—哈希—日期活动核对—授权—人物处理—图题—正文引用—证据台账—渲染”闭环；
- 是否存在无图题照片、图片与说明日期不符、相同照片对应不同活动、缺失替代文本、浮动图片漂移、人物未授权或待插图备注残留；
- 照片是否仅证明相应过程，避免用单张活动照片证明能力显著提升或研究因果效果。
- 时政、地图、统计、实验和跨学科知识是否由权威来源或相应学科复核，模型局限、单位和安全结论是否正确；
- 每个`implemented/validated`案例是否具备日期、学校、班级、教师、人数、实际课时、材料版本、偏离事项和证据ID；
- 策略是否按计划真正实施，课次、时长、参与流失和偏离是否记录，效果解释是否考虑实施不足；
- 所有课例、案例和成果作者是否与课题成员/贡献登记一致，外部课例、比赛稿和改编资源是否有授权与来源；
- 申请书承诺成果是否逐项核销，未兑现或变更是否如实说明并附批准依据；
- 最终文件夹是否无缺件、重复旧版本、临时文件、批注修订、隐藏内容、外部链接、模拟数据和无法打开的文件。
- 根目录注意事项文件是否为当前批次自动重建，是否完整列出真实照片、原始数据/记录、官方附件、证明、签章、时间冲突和建议增强项；已解决事项是否清除，是否存在笼统的“补材料”而没有责任人、截止时间和完成标准。

可将项目主清单保存为 JSON，并运行：

```bash
python scripts/validate_project_manifest.py project-manifest.json
```

脚本通过只代表基础字段和时间一致，不替代人工内容、格式和证据审查。

对DOCX执行结构格式审计：

```bash
python scripts/audit_docx_format.py material.docx --profile analysis-report --final
python scripts/audit_docx_format.py filled-official.docx --profile official-exact --reference official-template.docx --final
```

对非官方DOCX先应用并审计固定字体字号、段落和表格合同：

```bash
python scripts/resolve_material_format.py --material-id M21 --validate-catalog --out M21-format.json
python scripts/apply_docx_format_contract.py draft.docx --material-id M21 --out formatted.docx
python scripts/audit_docx_style_contract.py formatted.docx --material-id M21
python scripts/audit_docx_style_contract.py filled-official.docx --material-id M01 --reference official-template.docx
```

审计脚本通过仍不替代逐页渲染检查。

对DOCX/TXT/Markdown执行内容、隐私和证据用语审计：

```bash
python scripts/audit_content_integrity.py material.docx --mode submission --final
python scripts/audit_content_integrity.py anonymous-review.docx --mode anonymous --final
python scripts/audit_content_integrity.py casebook.docx --mode public --final --project-title "当前课题规范题目"
```

内容审计提示仍需人工判断上下文；它用于拦截敏感信息、编号跳号、重复段落、常见漏字、非便携字体、占位符和无证据强结论。

对含真实照片的DOCX执行照片证据专项审计：

```bash
python scripts/audit_photo_evidence.py photo-evidence.docx --manifest project-manifest.json --mode submission --final
python scripts/audit_photo_evidence.py public-casebook.docx --manifest project-manifest.json --mode public --scope registered-only --final
```

同时运行文档能力中的图片、无障碍和隐私审计，再渲染查看全部页面。专项脚本不能自动判断人脸是否已获得授权，授权与打码状态仍需人工确认。

对案例集执行状态、实施元数据和证据ID审计：

```bash
python scripts/audit_casebook_integrity.py casebook.docx --manifest project-manifest.json --final
```

整套交付前执行文件夹级终审：

```bash
python scripts/audit_project_package.py project-manifest.json --root delivery-folder --final
```

文件夹审计通过仍不替代学科专家、真实数据、逐页渲染、签章和当年报送系统检查。

正式交付优先运行一键预检，让主清单、文件夹、每份DOCX内容与格式、XLSX工作表与公式结构、案例状态和照片证据在同一次运行中接受实际检查，并保存机器报告：

```bash
python scripts/run_project_preflight.py project-manifest.json --root delivery-folder --final --report-json preflight-report.json
```

单项脚本用于定位和修复具体问题；一键预检是宣布“机器审计通过”的统一入口。`qa.*=passed`必须有`qa_records`记录核验日期、方法和报告/审阅人，不能只靠人工改状态。预检报告中的`manual_gates`仍须逐项完成。

任何上游事实变化时，把新主清单设为`batch_mode=incremental`，填写新`snapshot_id`和旧`parent_snapshot_id`，再运行`plan_incremental_refresh.py old.json new.json --out refresh-plan.json`；按报告重新生成所有受影响材料并重做QA，不得仅手改某一个Word标题或Excel单元格。

一键预检同时运行生命周期覆盖审计。`full-lifecycle-kit`至少包含注意事项文件、申报、开题、伦理、工具、编码、原始证据、数据工作簿、诊断分析、干预、实践载体、评价、过程管理、照片台账、证据册、最终报告、结题申请、成果目录、证明/鉴定和交付索引等角色；确实不适用的组必须在`coverage_exemptions`写明理由，不能靠删材料通过。

## 输出与沟通规则

- 首次使用或换到新的Agent/运行环境时，先运行`python scripts/check_environment.py`；缺少必需依赖时先修复环境，缺少可选依赖时在交付说明中列出受限审计项。

- 每次先说明当前阶段、已知事实、待补事实和本次输出。
- 内容较多时分批交付，并持续使用同一主清单；不要让用户反复提供已有信息。
- 明确区分“计划开展”“正在开展”“已经完成”和“取得成效”。
- 对政策、年度通知、官方模板和现行课程标准进行实时核验并提供来源。
- 保留用户原文件；修订件另存，未经允许不覆盖。
- 最终交付同时提供材料目录、一致性检查报告和仍需签字/盖章/填入真实数据的事项清单。
- 每个生成材料包根目录必须包含`00_课题材料包注意事项_真实性与待办清单.docx`；无论当前缺件多少都生成，缺件清零时也保留“已核验/无阻断项”记录和非阻断建议。
- 待人工事项同时列出缺少的真实照片、照片日期/活动信息、拍摄来源、授权、打码要求和应插入的材料位置。
- 正式交付默认保留内部工作版，并按用途另存报送版、匿名版或公开版；不得把含完整个人信息和学生映射表的工作版直接公开。
- 只有必交材料、承诺成果、证据、格式、隐私和文件夹审计全部通过时，才使用“整套可直接提交”；否则明确标注最接近的待办状态。
- “整套可直接提交”还要求当年要求快照为`verified`、一键预检零错误、所有机器与人工QA有可追溯记录；警告必须逐项判定为已解决或有书面接受理由。
- 整套状态使用`application-scaffold/application-ready`、`implementation-scaffold/implementation-ready`、`full-lifecycle-scaffold`、`closing-scaffold/closing-ready`。`scaffold`表示结构已建立但尚有内容/格式/证据/签章门槛；只有真实结果和结题证据齐全时才可使用`closing-ready`。
