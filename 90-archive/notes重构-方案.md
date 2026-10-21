# notes 重构方案（临时方案档）

> 已归档（2026-10-02；方案已执行完毕 —— 批 A/B/C 全部落地、现役档已收敛；本文仅作重构决策存档）。

> **日期**：2026-10-01
> **依据**：本次对 notes 非 archive 全量探查（79 个 .md 档 / 15,819 行；其中内容档 69 篇 / 15,467 行）+ 全部目录 README 索引 + 现役事实逐条核对（方案 A：MeowLauncher/MeowClassLoader/launcher.jar 退役；Forge 支持面 1.7–1.20.1；extras = lwjgl-3.4.3.jar + asm9/*×5；legacy 走 ordered、Forge≥1.13/NeoForge 走 real-tree、vanilla/Fabric 走 flat 等）。
> **目标**：让"非 archive 部分"与实际完全一致 —— 把**过时/已被取代**的文档整体下沉到 90-archive，把仍然有效的**结论 / 不变量 / 踩坑**抽取进少数几篇**有条理的新档**，并把现役档收敛到"每档一个现实事实"。
> **约束（本轮）**：只调研、只出本方案；**不改动/移动/删除任何其它文件、不 commit**。
> **写作约定**：本文所有文件路径按**纯文本**书写（不写 markdown 链接字面量、不加反引号），以免被 check_links.py / notes_stalepaths.py 误判为断链或死路径。
> **重要前置事实**：写本方案时，notes 工作区**已存在 18 个未提交改动**（`git status` 显示 `M`，均在 00-current/、20-design/launch/、30-supply-chain/；内容 = 2026-10-01 方案 A 的多处口径更正）。**这不是本方案造成的**；执行本方案前应先由用户提交或确认这批改动（见 §5.4）。

---

## 0. 一句话背景

现役"真相"已经基本准确（00-current/ 九篇大多带内联更正），**但 20-design/ 里堆着大量"方案草案 / 已落地方案 / 复盘 / 取证"**：
- 一部分描述的是**方案 A 之前**的世界（自研 system class loader、`MeowLauncher`、`launcher.jar` 桩件、把"启动器族"摘出平铺）—— 现已**整体作废**；
- 一部分是**已落地的分期计划**（T0–T8、F0–F3、期 1–4 …）—— 计划本身已无意义，但其中的"结论 / 不变量 / 踩坑"仍有效；
- 少数是**已整体退役**的机制（`launcher净室-设计`、`自研收编-总览与交接` 的 launcher.jar 战役、`40-adaptation/launcher-rebuild`）。

本次重构 = **把上面三类分别"整体归档"或"抽取后归档"**，并把现役结论重写成少数几篇**边界清楚、单一职责**的档。

---

## 1. 处置总表（逐档）

**判定图例**：`保留现役` 留在原处（可能微修）｜`归并入新档` 内容抽进新的合并档、原档归档｜`需重写` 保留文件名但剥离历史章节、抽取现行部分｜`归档` 整体移入 90-archive｜`外移` 移到更合适的现役目录。
**入站引用数** = 全库（含 archive）指向该档的 markdown 链接条数（用于估链接修复面；数字越大，移动成本越高）。

### 1.1 00-current/（9 档 + README）

| 路径 | 一句话职责 | 判定 | 判定依据（哪条现役事实冲突） | 入站 |
|---|---|---|---|---|
| 00-current/现状基线.md | 唯一事实源：模块 / 命名 / 关键定论 | 保留现役 | 它就是现役事实源本身 | 186 |
| 00-current/工程与规范.md | 工程配置 + 编码规范 + 兼容铁律 | 保留现役 | 规范/工程身份，与实现同步（已随方案 A 更正） | 33 |
| 00-current/已知限制与待解.md | 已知限制 / 待解登记册（§A–§J） | 保留现役 | 限制登记，本身即"未决"区 | 110 |
| 00-current/项目总览与新人上手.md | 新人导览 + 端到端链路 + 术语表 | 保留现役 | 导览/投影（活状态 4 家之一） | 13 |
| 00-current/架构决策与踩坑.md | 已实现功能的决策 + 踩坑（项目 log） | 需重写 | 混合现行决策（§20/§21/§24）与**已被取代**的章节（§6 Step0、§7 独立窗口、§8 JRE 内嵌、§8.5、§19 glthread）⇒ 现行部分抽入新《决策与不变量》，历史章节归档 | 42 |
| 00-current/渲染链与迁移结论.md | 渲染链测绘（GL/Vulkan 两条）+ SurfaceHolder 迁移结论 | 外移（建议 → 20-design/render） | 内容是"设计/测绘结论"，不是"现状/规范/限制"；任务要求 00-current 只留四家 | 38 |
| 00-current/版本支持边界.md | MC 支持面 1.6.x–26.3 + 三轴 + 判据速查 | 外移（争议；见 §7） | 属"支持面/判据"，可并入启动链总览或旧第 5 家；**高入站，移动代价大** | 35 |
| 00-current/输入方案.md | 鼠标 + 触屏输入总览 | 外移（建议 → 20-design/input/） | 内容是"输入域结论"，非四家范畴；触屏结论本已在 90-archive/触屏输入 | 20 |
| 00-current/运行时环境变量.md | 运行时 env / 调优开关唯一清单 | 保留现役 | 性质 = "规范类唯一清单"（与现状基线并列），保留 | 34 |
| 00-current/README.md | 结论层目录索引 | 保留现役 | 索引 | 0 |

### 1.2 10-research/（9 档 + README）

| 路径 | 一句话职责 | 判定 | 判定依据 | 入站 |
|---|---|---|---|---|
| 10-research/原生崩溃排查-方法论与复盘.md | 本工程崩溃排查方法论（canonical） | 保留现役 | 与"不改 MC + Zink/Mesa + 自持 JRE"现役栈一致 | 7 |
| 10-research/原生崩溃排查-仪器手册.md | 探针 / 调试手段工具手册 | 保留现役 | 工具手册，现役 | 2 |
| 10-research/启动器目录模型与版本隔离.md | .minecraft 目录模型 / 隔离 / 安装（外部参考） | 保留现役（微修） | 含一处 MeowLauncher 措辞（§385/§402）需按方案 A 改写 | 15 |
| 10-research/hmcl.md | HMCL 深度分析（旧类名体系） | 归并入 hmcl-存储模型 | 顶部已自述"旧类名体系、非同一套代码" ⇒ 与 hmcl-存储模型 合并 | 7 |
| 10-research/hmcl-存储模型.md | HMCL 持久化模型（源码级） | 保留现役 | 外部参考，现役 | 10 |
| 10-research/amethyst.md | Amethyst 深度分析 | 保留现役 | 外部学习参考 | 3 |
| 10-research/amethyst-源码深潜.md | Amethyst 源码级深潜（移植参照） | 保留现役 | 外部参考 | 2 |
| 10-research/homolauncher.md | HOML 唯一集中档案 | 保留现役 | 唯一 HOML 档案（血统已清除，仅学习） | 3 |
| 10-research/pojav系-启动渲染对照.md | Pojav 系启动/渲染对照 | 保留现役 | 外部参考 | 2 |
| 10-research/README.md | 目录索引 | 保留现役 | 索引 | 1 |

> 10-research/ 整体是**外部参考层**，无"过时冲突"问题，**本轮几乎不动**（唯一合并 = hmcl.md → hmcl-存储模型）。

### 1.3 20-design/（根 1 + launch 21 + lwjgl 4 + render 11 + perf 6）

**根**

| 路径 | 一句话职责 | 判定 | 判定依据 | 入站 |
|---|---|---|---|---|
| 20-design/自研收编-总览与交接.md | 收编自研路线 + 交接（含 launcher.jar 战役档案） | 归档 | 顶部★已自述：launcher.jar / gson-for-launcher 随方案 A 移除，§1/§2/§3/§5 均成历史 | 7 |
| 20-design/README.md | 分区索引 | 保留现役（重写） | 索引需按新结构改写 | 8 |

**launch/**

| 路径 | 一句话职责 | 判定 | 判定依据 | 入站 |
|---|---|---|---|---|
| launch/启动流程-四大类型逐世代总览.md | 四类型 × 逐世代启动总纲（三轴/三分流/总表/判据/误判） | 保留现役（→ 启动链-总览核心） | 已按方案 A 更正，是现役启动总纲 | 4 |
| launch/classpath形态-真树与平铺-决策情报.md | 三态 classpath（flat / real-tree / ordered）机制决策 | 归并入《决策与不变量》 | 内容是"为什么这么切"的定案与代价 ⇒ 属决策与不变量 | 9 |
| launch/Forge-1.13及以上-调研与方案.md | Forge ≥1.13 四世代机制 / 阶段1首改 / 范围收窄 | 保留现役 | 现役机制依据（含 §5.3 首改） | 19 |
| launch/Forge-1.13至1.20.1-安装实施方案.md | Forge 1.13–1.20.1 应用内安装实施（方案 B） | 保留现役（→ 安装链-总览） | 已落地（processor 链），结论有效 | 15 |
| launch/桌面标准启动链路-对照.md | 桌面正常启动基线（1.21.10 实证） | 保留现役（可并入启动链-总览） | 现役基线参照 | 8 |
| launch/多JRE共存-方案.md | 多 JRE 共存 / JRE 选择逻辑 | 归并入《环境与载体》 | "JRE 供给与分段"正是环境与载体主题 | 14 |
| launch/安装期JVM载体-调研.md | 安装期"无感"JVM 载体（无窗 UIAbility） | 归并入《环境与载体》 | "工具 JVM 载体"正是环境与载体主题 | 18 |
| launch/实例设置存储-方案.md | 设置存储（实例 / 全局 / 应用级） | 保留现役 | 与实现同步（§2.1/§3.2/§3.3 引用中） | 26 |
| launch/账户系统-设计与进度.md | 离线账户 + 微软正版登录 | 保留现役 | 已实现并实机验证 | 7 |
| launch/原版安装-方案.md | 原版安装流程 | 保留现役（→ 安装链-总览） | 已实现并实机验证 | 9 |
| launch/Forge支持-调研.md | HMCL 的 Forge 版本面 / 两形态 / 盘上格式（取证） | 保留现役（证据） | 机制依据，仍有效 | 12 |
| launch/Forge支持-改动方案.md | Forge 落地设计草案 1（三代际启动 + 两形态安装 + 分期） | 需重写/归并 | 顶部★已标：多处口径随方案 A 变；"计划 / 分期 / 经 MeowLauncher"为史 ⇒ 结论入《决策与不变量》/《安装链-总览》，草案本体归档 | 19 |
| launch/Fabric支持-改动方案.md | Fabric 双形态落地设计（含 MeowClassLoader 兼容性分析） | 归并入《启动链-总览》/《决策与不变量》 | "T3 类加载器打通（MeowClassLoader vs KnotClassLoader）"整段已随退役作废 | 12 |
| launch/Fabric支持-调研.md | Fabric 启动机制调研（KnotClient + 追加 loader 库） | 保留现役（证据） | 机制依据，仍有效 | 14 |
| launch/Fabric安装-方案.md | Fabric 安装方案（下载面板选 loader → 装单实例） | 保留现役（→ 安装链-总览） | 已实现并实机验证 | 14 |
| launch/NeoForge支持-调研.md | NeoForge 三链取证 + 真 installer 解剖 | 保留现役（证据） | 取证，仍有效（§9 启动期踩坑） | 22 |
| launch/NeoForge支持-改动方案.md | NeoForge 落地设计修订 5（含 §141 旧 MeowLauncher 口径） | 需重写/归并 | §141/§143 描述"以 MeowLauncher 为主类 + 设 system CL"，已作废 ⇒ 结论入《安装链-总览》/《决策与不变量》 | 17 |
| launch/NeoForge安装链-逐行取证.md | HMCL 装 NeoForge/Forge 的逐行取证 | 保留现役（证据） | 取证，仍有效 | 12 |
| launch/NeoForge无JVM安装-可行性与取证.md | "不跑 JVM"逐 processor 判定 | 保留现役（证据） | 与服务 §J2/§E 的现役登记一致 | 14 |
| launch/launcher净室-设计.md | 净室 meow.launcher 设计与实施 | 归档 | 顶部★：方案 A 已整体退役 `MeowLauncher`/`MeowClassLoader`/`launcher.jar`，全文仅考古 | 13 |
| launch/Forge-splash-崩溃根因与共享上下文修复.md | FML splash 共享上下文崩溃取证/修复 | 保留现役（取证） | C11 现役取证；但正文含 MeowClassLoader/ITweaker 旧段（§258-273）需标注 | 10 |

**lwjgl/**

| 路径 | 一句话职责 | 判定 | 判定依据 | 入站 |
|---|---|---|---|---|
| lwjgl/LWJGL3世代管理-方案.md | 现代单代 3.4.3 管理（含 §7 落地） | 保留现役 | 单代 3.4.3 = 现役事实 | 14 |
| lwjgl/LWJGL3单代收敛-决策依据.md | 两代→单代决策依据（成员级判据 + 5 shim） | 归并入 LWJGL3世代管理-方案 | 同主题，可合一篇 | 6 |
| lwjgl/LWJGL2自编-方案.md | legacy LWJGL2 自编方案 | 保留现役 | 1.6.x–1.12.2 现役路径 | 9 |
| lwjgl/LWJGL2-legacy适配-复盘.md | LWJGL2 OHOS 适配全过程复盘 | 保留现役 | 复盘，仍有效（含"全屏副屏未测"caveat 的被引点） | 9 |
| lwjgl/README.md | 目录索引 | 保留现役 | 索引 | 1 |

**render/**

| 路径 | 一句话职责 | 判定 | 判定依据 | 入站 |
|---|---|---|---|---|
| render/GLFW净室桥-设计.md | 净室 lwjgl GLFW stub + libmeowcraftbridge.so | 保留现役（微修） | 桥现役；正文有"launcher 无需再随包 android/util"旧句 | 11 |
| render/SDL3桥接-设计.md | 真 SDL3 fork 设计（解锁 26.3+） | 保留现役 | ≥26.3 现役路径 | 13 |
| render/SDL3适配-复盘.md | 26.3 SDL 适配复盘 + 与 GLFW 对照 | 保留现役 | 现役（§七 Vulkan vtable） | 21 |
| render/MC26.x渲染栈-差异分析.md | 26.x 渲染栈差异（glthread 崩溃放大器） | 保留现役 | 现役分析 | 8 |
| render/Vulkan后端-跟进与结案.md | 26.2+ Vulkan 取证（BLOCKED 结论） | 归档 | 顶部★：BLOCKED 结论**已被推翻**（错因 = sType 常量写错致假阴性）⇒ 结论过时；取证方法可并入绕过可行性 | 7 |
| render/Vulkan后端-实现历程与原理.md | Vulkan shim 实现原理 | 保留现役（可并入绕过可行性） | 机制，现役 | 1 |
| render/Vulkan后端-绕过可行性-调研与方案.md | 翻案 + 落地（1149 行，五机制 + 探针交接） | 保留现役 | 现役权威（§13 五机制） | 15 |
| render/legacy渲染-gl4es-落地方案.md | ≤1.16 原生 GLES + 自编 gl4es 落地 | 保留现役 | ≤1.16 现役路径 | 6 |
| render/GL33到GLES32-后端-方案.md | gl4es core 后端（1.17–1.21.x 无桌面 GL 出路） | 保留现役 | 现役（手机路径） | 9 |
| render/gl4es固定管线雾-取证与修复.md | 1.7.10+OptiFine「Fog: Fast」取证/修复 | 保留现役 | C12 现役取证 | 4 |
| render/1.21.1-崩溃-两条链与随包规避.md | 1.21.1+Flywheel 崩溃两条链 + 随包规避 | 保留现役 | §5 第 23 条现役 | 12 |
| render/README.md | 目录索引 | 保留现役 | 索引 | 1 |

**perf/**

| 路径 | 一句话职责 | 判定 | 判定依据 | 入站 |
|---|---|---|---|---|
| perf/平台加速能力-调研.md | 华为平台加速能力可用性判定 + 马良反模式 | 保留现役 | §5 第 15 条现役 | 11 |
| perf/性能实验台与glthread-结论.md | 实验台 + glthread 原负项定论 | 需重写 | §2 的"不可修"负项**已被 GL guard 推翻**（顶部有状态更新，但正文 §2 大段过时）⇒ 剥离负项、指向 glthread-GL-guard-方案 | 13 |
| perf/QoS与绑核-实验报告.md | QoS / 绑核实验（含 CPU 拓扑实测） | 保留现役 | 已证伪无收益，保留为负项记录 | 8 |
| perf/glthread崩溃-Bug报告.md | glthread×Zink×Maleoon UAF bug 报告 | 保留现役 | 可直接提交上游 | 13 |
| perf/glthread-GL-guard-方案.md | GL guard 转发层方案 | 保留现役 | §5 第 16 条现役 | 19 |
| perf/Vulkan后端-性能瓶颈清单与实验计划.md | Vulkan 档性能瓶颈清单 + 实验记录 | 保留现役 | 记录 9/16–19 现役 | 8 |
| perf/README.md | 目录索引 | 保留现役 | 索引 | 2 |

### 1.4 30-supply-chain/（3 .md + 1 .txt + README）

| 路径 | 一句话职责 | 判定 | 判定依据 | 入站 |
|---|---|---|---|---|
| 30-supply-chain/provenance-master.md | 资产溯源总表（分级/来源/收编路线） | 保留现役 | 权威，已补 §4.2（ASM 9.9.1 等） | 25 |
| 30-supply-chain/per-so-catalog.md | el1 逐 so 名录（66 so） | 保留现役 | 对齐两套 JRE + 12 组件 | 11 |
| 30-supply-chain/bisheng-hnp-trial.md | BiSheng hnp 嵌入试验（结论：不可嵌入） | 保留现役 | 结论现役（分体前提） | 6 |
| 30-supply-chain/assets-digests.txt | 校验和（SBOM 基线） | 保留现役 | 现役 | 0 |
| 30-supply-chain/README.md | 目录索引 | 保留现役 | 索引 | 0 |

### 1.5 40-adaptation/（5 档 + README）与 notes-tools/、根

| 路径 | 一句话职责 | 判定 | 判定依据 | 入站 |
|---|---|---|---|---|
| 40-adaptation/oshi-cpu-info.md | oshi CPU 型号适配（F3 `20x KirinX90`） | 保留现役 | §5 第 13 条现役 | 8 |
| 40-adaptation/openal-ohos.md | OpenAL Soft 自编（OpenSL 后端移植） | 保留现役 | 现役（ohaudio 的前置） | 5 |
| 40-adaptation/ohaudio-backend.md | OHAudio 默认后端（OpenSL→OHAudio） | 保留现役 | §5 第 12 条现役 | 9 |
| 40-adaptation/freetype-ohos.md | FreeType 自编 | 保留现役 | §5 第 14 条现役 | 3 |
| 40-adaptation/launcher-rebuild.md | launcher.jar 自编重建（Pojav 派生） | 归档 | 顶部★：已被净室取代，且 launcher.jar 已随方案 A 退役 ⇒ 双重过时 | 1 |
| 40-adaptation/README.md | 目录索引 | 保留现役（删 launcher-rebuild 行） | 索引 | 0 |
| notes-tools/（8 脚本 + README） | 本仓自用文档工具 | 保留现役 | 工具 | 4 |
| README.md（根） | notes 总导航（活状态投影家） | 保留现役（重写导航段） | 索引/入口 | 5 |

**小计（内容档 69 篇）**：保留现役 ≈ 50；归并入新档 ≈ 7；需重写 ≈ 4；归档（整体）≈ 4；外移 ≈ 3；合并 1（hmcl.md）。

---

## 2. 新结构（现役"有条理"的部分）

> 原则：**每份现役档 = 一个现实事实面**；档内只写"现状 / 规范 / 限制 / 定案（含为什么）/ 判据落点"；历史、分期、复现过程一律进 archive。

### 2.1 00-current/（结论层，收敛为"四家 + 两根 + 索引"）

建议 00-current/ 只保留 **4 家 + 2 根 + README**：

| 档 | 职责（只保留这一面） | 大纲 |
|---|---|---|
| 现状基线.md（家·现状） | 唯一事实源 | 模块/产物/命名对照/环境/§5 关键定论（编号条目）/文档权威分工。**保持现状**，仅随实现更新 |
| 工程与规范.md（家·规范） | 工程身份 + 目录结构 + 部署铁律 + 编码规范 + 兼容铁律 | 保持现状 |
| 已知限制与待解.md（家·限制） | 平台无解 / 已定案不做 / 未测量登记册 | 保持现状（§A–§J），把现役 doc 里散落的"未决"回链到此 |
| 项目总览与新人上手.md（家·索引/导览） | 第一入口：定义 / 端到端链路 / 一屏状态 / 术语 / 最短阅读路径 | 保持现状（§3 只留投影 + 指向 §5 编号） |
| 版本支持边界.md（根·支持面） | MC 1.6.x–26.3 支持面 + 三轴 + 判据速查（**决策点，见 §7**） | 现内容收拢：支持矩阵 / 三轴 / 设备 GL 画像 / 触发判断速查 / JRE 路线 |
| 运行时环境变量.md（根·唯一清单） | 运行时 env / 开关唯一清单 | 保持现状 |
| README.md | 目录索引 | 重写导航表，指向新结构 |

**外移**（离开 00-current）：
- 架构决策与踩坑.md → 现行"决策/不变量"并入 20-design/launch/决策与不变量.md；历史章节（§6/§7/§8/§8.5/§19）→ 90-archive/架构决策与踩坑-历史章节.md。
- 渲染链与迁移结论.md → 20-design/render/渲染链-结论.md（渲染链测绘 → 归 render）。
- 输入方案.md → 20-design/input/输入-总览.md（新建 input 子目录；把 90-archive/触屏输入 的现役结论也上提汇总）。

> 注：scripts 定义的"活状态 4 家"（现状基线 / 项目总览 / 已知限制 / README）与上面"4 家"**是两个概念**——前者是"可裸写活状态"的白名单，后者是"00-current 的档"。工程与规范 / 版本支持边界 / 运行时环境变量**不是**活状态家，但可以留在 00-current（它们承载不变量/规范，不是活状态）。

### 2.2 20-design/launch/（启动 / 安装 / 环境链，收敛为 ≤4 份现役档 + 证据档）

**新写/合并的 4 篇现役档**（旧档的"结论/不变量/踩坑"抽取至此，旧档归档）：

1. **启动链-总览.md** — 一页看明白"某 MC 版本 + 加载器该走哪条路、为什么、判据落在哪个函数/常量"。
   - 大纲：§0 三条切轴（LWJGL 切 1.13 / GL 切 1.17 / 窗口层切 26.3）+ 三个分流问题（classpath 三态 / 是否直启加载器主类 / JRE 档）；§1 四类型 × 逐世代**总表**；§2 逐代主类 + classpath 形态 + JRE + 关键坑（vanilla / Forge legacy·①·②·③ / NeoForge / Fabric）；§3 平台伪装（凡另起 JVM 必带）+ 强封装参数原样透传；§4 判据与落点索引（符号名表）；§5 常见误判速查（`Missing forge!` / `AssertionError: Platform not recognized` / `Unsupported class file major version 70` / `ResolutionException` …）。
   - 来源档：启动流程-四大类型逐世代总览（主体）、桌面标准启动链路-对照（基线）、Fabric支持-改动方案（现役结论）、classpath 形态判定。
2. **安装链-总览.md** — 四类型**应用内安装**现状（入口 / 判型 / 产物形态 / 幂等 / 失败诊断）。
   - 大纲：§0 四条独立安装链（vanilla / Fabric / Forge / NeoForge）；§1 vanilla（填 4 类文件 + 落 2 版本文件）；§2 Fabric（选 loader + 每 loader 独立源）；§3 Forge（判型 = client processor 数；≤1.12.2 零 JVM 链 / 1.13–1.20.1 processor 链内嵌 `maven/**`）；§4 NeoForge（installer 当数据容器 + 自研 processor 编排 + `:neoinstall` 无窗载体 + `outputs` 幂等）；§5 产物形态（顶层扁平 + `patches[]`，HMCL 兼容）；§6 失败诊断与自愈；§7 服务内登记（指向 §J）。
   - 来源档：原版安装-方案、Fabric安装-方案、Forge-1.13至1.20.1-安装实施方案、Forge支持-改动方案（安装部分）、NeoForge支持-改动方案（安装部分）。
3. **环境与载体.md** — JRE 供给与分段 / 工具 JVM 载体 / 平台伪装 / ASM 覆盖。
   - 大纲：§1 两套 JRE（现代 OpenJDK 26 + legacy Java 8）与 `(MC 版本 × loader) → JRE` 规则表；§2 多 JRE 布局（第二 el1 命名空间）与令牌门；§3 安装期工具 JVM 载体（无窗 `:neoinstall` UIAbility；phone 限制）；§4 平台伪装（`os.name`/`os.version`，JDK8 精确匹配）；§5 随包 ASM 9.9.1 覆盖（判据 = ModLauncher ≥10 且声明 ASM 覆盖不了 JRE class major；1.19.x）。
   - 来源档：多JRE共存-方案、安装期JVM载体-调研、启动流程总览（§0.3）、Forge-1.13及以上（环境侧）。
4. **决策与不变量.md** — 所有"为什么这么选"的定案 + 不变量 + 被否决方案一句话。
   - 大纲：§1 硬约束（不改 MC / 官方件优先 / 净室自研）；§2 定案表（含"为什么"）：直启 json.mainClass（无自研 system CL）、三态 classpath 及判据、平台伪装、ASM 覆盖、Forge 支持面截至 1.20.1（政策 vs 技术）、NeoForge 与 Forge 安装链分开（方案 B，隔离风险）；§3 不变量（如"真树按绝对路径去重，不按 artifact 名"、"任何另起 JVM 必带平台伪装"、"随包件不得声明 Multi-Release 而无 versions/**"）；§4 被否决/已作废方案一句话（自研 system CL + 启动器族摘出 → 作废；`launcher.jar` 桩件 → 退役；独立 OptiFine → 范围外；F72 环复用 → 容量墙）。
   - 来源档：架构决策与踩坑（现行部分）、classpath 形态、Forge/Fabric/NeoForge 改动方案的"被否决/定案"段。

**保留为"证据/调研"档（不进 4 篇，也不归档）**：Forge-1.13及以上-调研与方案（机制取证）、Forge支持-调研、Forge-splash-崩溃根因与共享上下文修复（C11 取证）、NeoForge支持-调研、NeoForge安装链-逐行取证、NeoForge无JVM安装-可行性与取证、Fabric支持-调研、实例设置存储-方案、账户系统-设计与进度。

**归档**：launcher净室-设计、Forge支持-改动方案（抽结论后）、Fabric支持-改动方案（抽结论后）、NeoForge支持-改动方案（抽结论后）。

### 2.3 20-design/{lwjgl,render,perf}/

- **lwjgl/**：合并 LWJGL3单代收敛 → LWJGL3世代管理-方案（一篇讲"现代单代 3.4.3 + 为什么收敛 + 5 shim"）；LWJGL2 两篇保留（自编方案 + 适配复盘）。目标 3 篇 + README。
- **render/**：
  - 保留：GLFW净室桥-设计、SDL3桥接-设计、SDL3适配-复盘、MC26.x渲染栈-差异分析、legacy渲染-gl4es-落地方案、GL33到GLES32-后端-方案、gl4es固定管线雾-取证与修复、1.21.1-崩溃-两条链与随包规避。
  - 合并：Vulkan 三档（跟进与结案 + 实现历程与原理 + 绕过可行性）→ 收敛为 **2 篇**：Vulkan后端-实现与原理.md（合并"实现历程与原理" + "绕过可行性"的机制面）+ Vulkan后端-取证存档.md（"跟进与结案"的取证方法/设备事实，顶部标注"BLOCKED 结论已被更正"）。归档旧的"跟进与结案"结论面。
  - 移入：渲染链与迁移结论（来自 00-current）。
- **perf/**：保留 5 篇（平台加速能力 / QoS绑核 / glthread崩溃Bug报告 / glthread-GL-guard方案 / Vulkan性能瓶颈）；**重写** 性能实验台与glthread-结论（剥离已被推翻的"不可修"负项，只留实验台 + 基准模型 + 指向 GL guard）。

### 2.4 10-research/、40-adaptation/、30-supply-chain/

- **10-research/**：9 篇几乎全留；只把 hmcl.md 并入 hmcl-存储模型。补一句：凡出现旧代码名（`MeowLauncher` 等）按 现状基线 §3 换算。
- **40-adaptation/**：归档 launcher-rebuild；其余 4 篇保留（README 删对应行）。
- **30-supply-chain/**：全部保留（已是"只放现状"口径）。

### 2.5 明确"抽取进新档 vs 整体归档"

| 旧档 | 抽进新档的部分 | 整体归档的部分 |
|---|---|---|
| 架构决策与踩坑.md | §20 启动器功能 / §21 脚本 / §22 杂项接口 / §24 输入不变量等**现行**决策与踩坑 | §6 Step0 / §7 独立窗口雏形 / §8 JRE 内嵌 / §8.5 / §19 glthread 等**已被取代**的章节 |
| Forge支持-改动方案.md | 定案（判据按形态不按 loader 名）、分期结论、被否决方案一句话 | T0–T6 分步计划、当时逐文件改动清单 |
| Fabric支持-改动方案.md | 双形态判定、直启结论 | T1–T6 计划、`MeowClassLoader` 兼容性分析 |
| NeoForge支持-改动方案.md | 写盘形态、module path + 真树、三形态结论 | 修订历史、逐条改造清单 |
| classpath形态-真树与平铺-决策情报.md | 三态机制 + 代价 + 为什么暂不统一 | （几乎全抽，可整体归档） |
| 多JRE共存-方案.md | JRE 规则表 + 布局结论 | 原始逐处改法清单、M0–M4 分期 |
| 安装期JVM载体-调研.md | 载体结论（无窗 UIAbility）+ phone 限制 | 原始候选穷尽过程 |
| 性能实验台与glthread-结论.md | 实验台 + 基准模型 | §2 "不可修"负项定论与逐条排除证据 |

---

## 3. 分批执行计划

> 每批结束都跑"完工仪式"（§4），全绿再进下一批；每批单独 commit（notes 为本地独立仓）。

### 批 A — 启动 / 安装链族（最大）

- **移动清单（old → new，90-archive/ 表示归档）**：
  - 20-design/自研收编-总览与交接.md → 90-archive/自研收编-总览与交接.md
  - 20-design/launch/launcher净室-设计.md → 90-archive/launcher净室-设计.md
  - 20-design/launch/Forge支持-改动方案.md → 90-archive/Forge支持-改动方案.md
  - 20-design/launch/Fabric支持-改动方案.md → 90-archive/Fabric支持-改动方案.md
  - 20-design/launch/NeoForge支持-改动方案.md → 90-archive/NeoForge支持-改动方案.md
  - 20-design/launch/classpath形态-真树与平铺-决策情报.md → 90-archive/classpath形态-真树与平铺-决策情报.md
  - 20-design/launch/多JRE共存-方案.md → 90-archive/多JRE共存-方案.md
  - 20-design/launch/安装期JVM载体-调研.md → 90-archive/安装期JVM载体-调研.md
  - 00-current/架构决策与踩坑.md → 拆分后：现行部分进 20-design/launch/决策与不变量.md；历史进 90-archive/架构决策与踩坑-历史章节.md（原档删除或整体归档）
- **要新写/合并的档**：启动链-总览、安装链-总览、环境与载体、决策与不变量（§2.2）。
- **要修的入站引用**：launcher净室-设计（13）、Forge支持-改动方案（19）、Fabric支持-改动方案（12）、NeoForge支持-改动方案（17）、自研收编（7）、classpath 形态（9）、多JRE共存（14）、安装期JVM载体（18）、架构决策与踩坑（42，其中相当部分应改指 决策与不变量）。合计约 130+ 条。
- **验证门槛**：§5 三道检查全绿 + 人工核对"每条被归档档的现役结论都已在 4 新档出现"。

### 批 B — 渲染 / 性能 / gl4es

- **移动清单**：
  - 00-current/渲染链与迁移结论.md → 20-design/render/渲染链-结论.md（外移）
  - 20-design/render/Vulkan后端-跟进与结案.md → 90-archive/Vulkan后端-跟进与结案.md（结论面过时；取证方法并入新档）
  - 20-design/render/Vulkan后端-实现历程与原理.md + Vulkan后端-绕过可行性-调研与方案.md → 合并为 Vulkan后端-实现与原理.md（+ 新建 Vulkan后端-取证存档.md）
  - perf/性能实验台与glthread-结论.md → 原地重写（不移动）
- **要新写/合并的档**：Vulkan后端-实现与原理、Vulkan后端-取证存档、渲染链-结论（外移版）。
- **要修的入站引用**：渲染链与迁移结论（38）、Vulkan后端-跟进与结案（7）、Vulkan后端-绕过可行性（15）、Vulkan后端-实现历程与原理（1）、性能实验台glthread（13）。合计约 74 条。
- **验证门槛**：三道检查全绿 + 确认"渲染链测绘"在 render/ 下、两条链（GL/Vulkan）与 §5 第 2/24 条一致。

### 批 C — 研究 / 适配 / 供应链

- **移动清单**：
  - 40-adaptation/launcher-rebuild.md → 90-archive/launcher-rebuild.md
  - 10-research/hmcl.md → 并入 10-research/hmcl-存储模型.md（原档归档或删除）
  - 00-current/输入方案.md → 20-design/input/输入-总览.md（新建 input 目录；外移）
- **要新写/合并的档**：输入-总览（外移版；把 90-archive/触屏输入 的现役结论上提汇总）、hmcl 合并稿。
- **要修的入站引用**：输入方案（20）、hmcl（7）、launcher-rebuild（1）。合计约 28 条。
- **验证门槛**：三道检查全绿 + 补跑 notes_stalepaths 的 --include-archive 与 grep 扫"指向已删物的活引用"（§4.2）。

---

## 4. 执行工艺（关键，别踩坑）

### 4.1 正确顺序（每批内）

```
cd notes
git mv <old> <new> ...                              # 1) 批量移动/改名（保留历史）
#   编辑 notes-tools/notes_relink.py 的 MOVED（old→new，相对 notes 根）
python3 notes-tools/notes_relink.py --dry-run       # 2) 先看规模
python3 notes-tools/notes_relink.py                 #    同时改"目标路径"与"被移动文件自身的出站链接"
#   编辑 notes-tools/notes_relabel.py 的 OLD2NEW（对齐链接显示文本，可选）
python3 notes-tools/notes_relabel.py                # 3) 对齐显示文本
python3 notes-tools/check_links.py .                 # 4) 必须 all OK
python3 notes-tools/notes_stalepaths.py .            # 5) 死路径=0
python3 notes-tools/notes_statusdup.py .             # 6) 活状态越位=0
```

要点：
- **notes_relink.py 一次覆盖两类改写**：① 链接**目标**是移动过的文件 → 改指新位置；② 链接**所在文件自身**移动过 → 用"旧基目录"重算所有出站链接（例如被移动文件里原本相对 00-current 的一层上级路径，要改成两层上级路径）。所以**移动后先跑它，不要手工逐个改上级路径**。
- **notes_relink.py 幂等**：目标当前目录已能解析的链接一律不动（建行 2026-09-15 的防抖）⇒ 第二遍是 no-op。**但它仍只用于"刚 git mv 过、链接还没重算"的场景**；别在别的时候跑。
- **别在一条消息里**同时跑"改文件的脚本"与"派 agent 改同一批文件"（并行互相覆盖）。
- **出事别整目录 `git checkout` 回滚**（会丢同期改动）——用 notes_repair_links.py 按内容修（或按批单独 commit 后 `git revert`）。

### 4.2 两个已知口径（务必注意）

1. **notes_stalepaths.py 显式跳过 `tools/` / `stuffs/` / `ref/` / `libs/` / `src` / `Harmomeow-Craft-Launcher` 前缀的路径**（视为"仓库外、故意不可解析"）。⇒ 它**查不到**"正文里指向**已删物**的活引用"（如 `tools/meow-launcher/`、`tools/relocate_gson.py`）。这类要**另外**用 grep 扫：
   - 用 **`grep -E`**（zsh 下 `grep "a\|b"` 是**假阴性**，`\|` 不被当 alternation —— 必须 `-E`）。
   - 本次已扫出**非 archive 的活引用**集中在：40-adaptation/launcher-rebuild.md（已定归档）、00-current/{现状基线,架构决策与踩坑,工程与规范,已知限制与待解,项目总览}（多已带"已退役"横幅/括注，属**允许的带日期历史记录**）、20-design/launch/{Fabric支持-改动方案,Forge支持-改动方案,Forge-1.13及以上-调研与方案,Forge-splash,NeoForge支持-改动方案,NeoForge支持-调研,launcher净室-设计,账户系统}、10-research/启动器目录模型与版本隔离.md（§385/§402 一处）。
   - 约定：**归档的档**里的旧引用随档进 archive（历史允许陈旧，脚本豁免）；**保留现役的档**里若仍把已删物当现役引用，须改写成"已退役"括注或删句。
2. **`90-archive/**` 被 notes_stalepaths / notes_statusdup 整体豁免**，只有 `notes_stalepaths.py --include-archive` 才纳入。⇒ **归档后，过时口径不再污染现役检索**——这正是本次重构的目标。因此"归档"是最佳处置（优于"现役档里留一堆已作废段落"）。

### 4.3 归档档顶部约定

每份移入 90-archive 的档，顶部加一行横幅：`> 已归档（<日期>；因为 <一句话>；现役口径见 <新档>）`。现役新档则留一行指针 + 一句话历史（如"旧设计见 90-archive/xxx（已退役）"）。

---

## 5. 风险与回退

### 5.1 链接面

- 入站引用最多的 10 篇（现状基线 186、已知限制 110、架构决策 42、渲染链结论 38、版本支持边界 35、运行时环境变量 34、工程与规范 33、实例设置存储 26、provenance-master 25、NeoForge支持-调研 22）中，**本轮真正移动的**是 **架构决策与踩坑（42）、渲染链与迁移结论（38）**；这两篇是全库链接的主要承重点，移动务必**整批做、一次跑 relink**。
- 被归档档的入站（launcher净室 13 + Forge改动 19 + Fabric改动 12 + NeoForge改动 17 + classpath 9 + 多JRE 14 + 安装期JVM 18 + 自研收编 7 + Vulkan跟进 7 + launcher-rebuild 1）≈ 117 条，全部由 `notes_relink.py` 一并改写（改指新档或 archive）。
- **check_links.py 是唯一能兜住"移动后断链"的门**：每批必跑，出现断链用 `notes_repair_links.py` 按内容修。

### 5.2 relink 幂等性

- 已确认 `notes_relink.py` 有幂等防抖（目标已解析则不动）⇒ 可安全重跑。**但**：如果**手工**先改了一部分链接，再跑 relink，可能因"目标已解析"而跳过⇒**统一由脚本改，别手工插队**。

### 5.3 回退

- notes 是**独立 git 仓**（`notes/.git`，与主仓无关，只本地提交、从不 push）。**每批一个 commit**（语义化前缀，如 `docs: archive superseded launch plans (batch A)`）⇒ 出问题按批 `git revert` 或 `git reset --hard <批前 commit>`。
- **别整目录 checkout**：工作区可能有同期未提交改动（见 5.4）。

### 5.4 前置：工作区已有未提交改动

- 写本方案时 `git status` 显示 **18 个 `M` 文件**（00-current/ 5 篇 + 20-design/launch/ 6 篇 + 30-supply-chain/ 4 篇…），内容 = 2026-10-01 方案 A 的口径更正。**执行重构前必须先由用户 atob submit（提交）或确认这批改动**，否则批 A 的 `git mv` / revert 会把它们搅在一起。承诺的"`git status --short` 只多一个 `??`"**在当前工作区做不到**。

---

## 6. 量化目标

| 指标 | 现在（非 archive） | 目标（估） |
|---|---|---|
| .md 文件数 | 79（内容档 69 + 索引 10） | ≈ 60（内容档 ≈ 52 + 索引 ≈ 8） |
| 行数 | 15,819（内容 15,467） | ≈ 11,500–12,500 |
| 90-archive 新增档 | — | ≈ 15 篇（整档 ≈ 8 + 抽结论后归档 ≈ 7） |
| 新写/合并现役档 | — | ≈ 8 篇（launch 4 + render 2 + 其它 2） |

**"每份现役档 ↦ 现实事实"映射**（抽要）：

| 现役档 | 对应的现实事实 |
|---|---|
| 现状基线.md | 模块/产物/命名/关键定论 = 代码现状 |
| 版本支持边界.md | 1.6.x–26.3 支持面 + 三轴切点 |
| 启动链-总览.md | 四类型 × 逐世代：形态/classpath/JRE/渲染分流 + 判据落点 |
| 安装链-总览.md | 四类型应用内安装现状（Forge 1.7–1.20.1 等） |
| 环境与载体.md | 两套 JRE + 工具 JVM 载体 + 平台伪装 + ASM 覆盖 |
| 决策与不变量.md | 所有"为什么这么选"的定案 + 被否决方案 |
| 渲染链-结论.md | GL / Vulkan 两条渲染链 + SurfaceHolder 结案 |
| 运行时环境变量.md | env / 开关唯一清单 |
| glthread-GL-guard-方案.md | glthread UAF 应用侧修复（默认开） |
| provenance-master / per-so-catalog / assets-digests | 随包件来源 = lwjgl-3.4.3.jar + asm9/*×5 等 |

---

## 7. 需你拍板的选项

1. **渲染 / perf 那批是否也一并收（批 B 是否执行）**：render 与 perf 现役档**大多准确**（只有 Vulkan"跟进与结案"结论过时、glthread 负项过时）。可只做**最小修正**（归档 1 篇 + 重写 1 篇），不做 Vulkan 合并。
2. **00-current 是否真裁到"四家 + 两根"**：版本支持边界 / 渲染链与迁移结论 / 输入方案 三篇**都是现役、高入站**，外移会改动约 90 条链接、读者习惯也会被打断。备选：**00-current 保留"现状/规范/限制/索引 + 3 篇结论参考"（共 8 篇）**，仅把"架构决策与踩坑"拆分。
3. **是否新建 20-design/input/**：输入域现无独立目录（结论散在 00-current/输入方案 + 90-archive/触屏输入）。建目录更整齐，但也增加一处结构。
4. **Vulkan 三档合并粒度**：建议合成 2 篇（实现与原理 / 取证存档）；也可保守只归档"跟进与结案"、其余两篇不动。
5. **是否重构时同步删除本方案档**：建议合并进 20-design/README 的"维护约定"，本文件随后删除。

---

## 附：本次探查的原始统计（用于复核）

- 非 archive .md：**79**（内容档 69 + README 10）；总行数 **15,819**（内容 **15,467**）。
- 分批体量：00-current 2,315 行 / 10 档；10-research 2,034 / 10；20-design 10,251 / 47（launch 4,564·21、lwjgl 635·4、render 3,423·11、perf 1,443·6、根 169·1）；30-supply-chain 812 / 4（含 assets-digests.txt）；40-adaptation 661 / 6；notes-tools 856（8 py + README）。
- 三道检查基线（执行本方案前）：check_links **all OK**；notes_stalepaths **0**；notes_statusdup **0**。
