# Harmomeow Craft Notes

> **Harmomeow Craft Launcher** 的工程笔记：在鸿蒙 PC（2in1）上**原生运行 Minecraft Java 版**的启动器。
> 这里记录设计、取证、约束与踩坑。**不含源码** —— 启动器代码在另一个仓库 `Harmomeow-Craft-Launcher`。
>
> 第一次来请先读 [`PUBLIC-READING.md`](PUBLIC-READING.md)：哪些目录不随本仓发布、术语怎么读。

## 5 分钟上手

按顺序读这 5 篇，就能知道"这个项目在干嘛、为什么难、现在到哪一步"：

1. [`00-current/项目总览与新人上手.md`](00-current/项目总览与新人上手.md) —— 定义、三个难点、端到端链路（App → `:game` → JVM → 桥 → 画面）、术语表。
2. [`00-current/现状基线.md`](00-current/现状基线.md) —— 模块、native 产物、命名、关键定论。**唯一事实源**，与它冲突时以它为准。
3. [`00-current/版本支持边界.md`](00-current/版本支持边界.md) —— MC 1.6.x–26.3 的三条切轴（LWJGL 1.13 / GL 1.17 / 窗口层 26.3）。
4. [`20-design/render/渲染链-结论.md`](20-design/render/渲染链-结论.md) —— GL 与 Vulkan 两条渲染链。
5. [`00-current/已知限制与待解.md`](00-current/已知限制与待解.md) —— 平台无解、已定案不做、未测量。

> 要动手排查崩溃：先看 [`10-research/原生崩溃排查-方法论与复盘.md`](10-research/原生崩溃排查-方法论与复盘.md)（速查 + 良性噪声清单 + A/B 纪律）。

## 当前状态（一屏）

- **支持窗口**：MC **1.6.x–26.3** —— legacy LWJGL2 + gl4es / ≤1.16 gl4es / 1.17–26.2 单代 LWJGL3 3.4.3 / ≥26.3 SDL3。
- **运行时**：官方 OpenJDK 26 + legacy Java 8，自持、零黑箱。
- **已实现**：原版 / Fabric / Forge（1.7–1.20.1）/ NeoForge（1.20.2+）应用内安装；桌面 GL / gl4es / Vulkan / SDL3 四种渲染后端；离线与微软账户；版本隔离、显示缩放、全屏、触屏与虚拟按键。
- **限制与未决**：见 [`已知限制与待解.md`](00-current/已知限制与待解.md)。

> 详细状态与逐条验收只在 [`现状基线.md`](00-current/现状基线.md) §5；本页不复述。

## 目录

```
notes/
├── README.md                 ← 本文件
├── PUBLIC-READING.md         ← 公开版说明（哪些不发布、术语对照）
├── 00-current/               ← ★ 当前结论（唯一事实源 + 工程规范 + 限制 + 两根清单）
├── 10-research/              ← 其它启动器 / 崩溃排查方法论（只读参考）
├── 20-design/                ← 设计层
│   ├── launch/               ← 启动链 / 安装链 / 环境与载体 / 决策与不变量 / 账户 / 设置
│   ├── render/               ← GLFW / SDL3 / Vulkan / gl4es / 渲染链
│   ├── lwjgl/                ← LWJGL2/3 自编与世代管理
│   ├── perf/                 ← 平台加速 / QoS 绑核 / glthread
│   └── input/                ← 鼠标 / 触屏 / 键盘
├── 30-supply-chain/          ← 依赖溯源 / SBOM
├── 40-adaptation/            ← 鸿蒙环境适配
├── notes-tools/              ← 文档检查与重构脚本（MIT）
└── 90-archive/               ← 历史与证据（结论可能已被推翻）
```

## 按目标查

### 结论层（`00-current/`）

| 我要…… | 读 |
|---|---|
| 模块 / native 产物 / 命名 / 关键定论 | [`现状基线.md`](00-current/现状基线.md) |
| 工程身份、ets 目录、部署铁律、文档与编码规范 | [`工程与规范.md`](00-current/工程与规范.md) |
| 已知限制 / 待解 | [`已知限制与待解.md`](00-current/已知限制与待解.md) |
| 项目全貌 / 端到端链路 / 术语 | [`项目总览与新人上手.md`](00-current/项目总览与新人上手.md) |
| MC 版本支持边界 + 报错速查 | [`版本支持边界.md`](00-current/版本支持边界.md) |
| 运行时环境变量 / 调优开关（`MEOW_*` 等） | [`运行时环境变量.md`](00-current/运行时环境变量.md) |

### 启动 / 安装 / 环境（`20-design/launch/`）

| 我要…… | 读 |
|---|---|
| 某版本 + 加载器走哪条路、判据在哪个函数 | [`启动链-总览.md`](20-design/launch/启动链-总览.md) |
| 四类应用内安装（入口 / 判型 / 产物 / 幂等 / 失败诊断） | [`安装链-总览.md`](20-design/launch/安装链-总览.md) |
| JRE 供给 / 工具 JVM 载体 / 平台伪装 / ASM | [`环境与载体.md`](20-design/launch/环境与载体.md) |
| 定案、不变量、被否决的方案 | [`决策与不变量.md`](20-design/launch/决策与不变量.md) |
| 设置存哪（逐版本 `.hmmcraft` + 应用沙箱） | [`实例设置存储-方案.md`](20-design/launch/实例设置存储-方案.md) |
| 离线账户 + 微软登录 | [`账户系统-设计与进度.md`](20-design/launch/账户系统-设计与进度.md) |
| 下载器可靠性 / 安装进度聚合 | [`下载器-可靠性方案.md`](20-design/launch/下载器-可靠性方案.md)、[`安装进度-聚合方案.md`](20-design/launch/安装进度-聚合方案.md) |
| 加载器机制证据（HMCL 对照 / 真件解剖 / 逐行取证） | [`20-design/launch/`](20-design/launch/README.md) 下的 `*-调研.md` / `*-取证.md` |

### 渲染（`20-design/render/`）

| 我要…… | 读 |
|---|---|
| GL / Vulkan 两条链、SurfaceHolder 结论、OpenGTX 结案 | [`渲染链-结论.md`](20-design/render/渲染链-结论.md) |
| GLFW 净室桥（stub + `libmeowcraftbridge.so`） | [`GLFW净室桥-设计.md`](20-design/render/GLFW净室桥-设计.md) |
| SDL3 桥接（解锁 MC 26.3+） | [`SDL3桥接-设计.md`](20-design/render/SDL3桥接-设计.md)、[`SDL3适配-复盘.md`](20-design/render/SDL3适配-复盘.md) |
| Vulkan 后端：原理 / 取证 | [`Vulkan后端-实现与原理.md`](20-design/render/Vulkan后端-实现与原理.md)、[`Vulkan后端-取证存档.md`](20-design/render/Vulkan后端-取证存档.md) |
| ≤1.16 / legacy 的 gl4es 落地 | [`legacy渲染-gl4es-落地方案.md`](20-design/render/legacy渲染-gl4es-落地方案.md) |
| GL 3.2/3.3 core → GLES 3.2（手机路径） | [`GL33到GLES32-后端-方案.md`](20-design/render/GL33到GLES32-后端-方案.md) |
| 1.21.1 + Create/Flywheel 崩溃 | [`1.21.1-崩溃-两条链与随包规避.md`](20-design/render/1.21.1-崩溃-两条链与随包规避.md) |

### LWJGL / 性能 / 输入

| 我要…… | 读 |
|---|---|
| LWJGL 单代 3.4.3 + 5 个兼容 shim | [`LWJGL3世代管理-方案.md`](20-design/lwjgl/LWJGL3世代管理-方案.md) |
| LWJGL2 自编（1.6.x–1.12.2） | [`LWJGL2自编-方案.md`](20-design/lwjgl/LWJGL2自编-方案.md)、[`LWJGL2-legacy适配-复盘.md`](20-design/lwjgl/LWJGL2-legacy适配-复盘.md) |
| 平台加速能力（QoS / 超帧 / ABR / XEngine） | [`平台加速能力-调研.md`](20-design/perf/平台加速能力-调研.md) |
| glthread 崩溃与 GL guard | [`glthread崩溃-Bug报告.md`](20-design/perf/glthread崩溃-Bug报告.md)、[`glthread-GL-guard-方案.md`](20-design/perf/glthread-GL-guard-方案.md) |
| Vulkan 性能瓶颈 | [`Vulkan后端-性能瓶颈清单与实验计划.md`](20-design/perf/Vulkan后端-性能瓶颈清单与实验计划.md) |
| 鼠标 / 触屏 / 键盘总览 | [`输入-总览.md`](20-design/input/输入-总览.md) |

### 外部调研 / 供应链 / 适配 / 归档

| 我要…… | 读 |
|---|---|
| 跑 MC 崩了，要一套排查套路 | [`原生崩溃排查-方法论与复盘.md`](10-research/原生崩溃排查-方法论与复盘.md) |
| 具体仪器 / 探针怎么开、在哪读 | [`原生崩溃排查-仪器手册.md`](10-research/原生崩溃排查-仪器手册.md) |
| 各启动器怎么维护 `.minecraft` / 版本隔离 | [`启动器目录模型与版本隔离.md`](10-research/启动器目录模型与版本隔离.md) |
| HMCL / Amethyst / HomoLauncher / Pojav 研究 | [`10-research/`](10-research/README.md) |
| 每个 `.so` / `.jar` 从哪来、是否可控 | [`30-supply-chain/`](30-supply-chain/README.md) |
| 鸿蒙环境适配（改了什么、为什么、怎么复现） | [`40-adaptation/`](40-adaptation/README.md) |
| 历史与实验证据 | [`90-archive/`](90-archive/README.md) |

## 约定

1. **结论变了** → 先改 [`00-current/现状基线.md`](00-current/现状基线.md)，再回写对应文档。
2. **当前文档只写现行事实与契约**：不写"改了几轮"这类过程；同一机制只留一处权威表述，别处用指针；历史与过程进 `90-archive/`。
3. **三道检查全绿**（从仓库根跑）：
   `python3 notes-tools/check_links.py .` +
   `python3 notes-tools/notes_stalepaths.py` +
   `python3 notes-tools/notes_statusdup.py`。
   批量改名 / 移动后用 `notes_relink.py` + `notes_relabel.py` + `notes_repair_links.py`；
   另有提示性的 `notes_linerefs.py`（不强制清零）。
4. **写作规范**（活状态单一事实源 / 引用完整性 / 路径书写）见 [`00-current/工程与规范.md`](00-current/工程与规范.md)。

## 许可

- 文档：**CC BY 4.0** —— 见 [`LICENSE`](LICENSE)
- `notes-tools/`：**MIT** —— 见 [`LICENSE-MIT`](LICENSE-MIT)
