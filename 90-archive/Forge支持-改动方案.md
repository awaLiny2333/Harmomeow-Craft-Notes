# Forge 支持改动方案（草案 1）—— 复用 NeoForge 通道 + 两形态安装 + 三代际启动

> 已归档（2026-10-01；因为其仍有效的结论已并入现役档（启动链-总览 / 安装链-总览 / 决策与不变量）；现役口径见 [`启动链-总览.md`](../20-design/launch/启动链-总览.md)）。

> 日期：2026-09-28 ｜ **修订 1 = 初稿；本轮只出方案、不动代码**。
> 前置：[`Forge支持-调研.md`](../20-design/launch/Forge支持-调研.md)（HMCL 的 Forge 版本面 / 两形态 / 盘上格式）+ 本轮三份测绘报告（**工作区根** `stuffs/research/forge-support/A-our-install-side.md`、`stuffs/research/forge-support/B-our-launch-side.md`、`stuffs/research/forge-support/C-forge-requirements.md`）。
> 本文为**决策记录 / 方案存档**，**不复述现状**；Forge 的支持状态见 [`../../00-current/现状基线.md`](../00-current/现状基线.md) §5 第 28 条 与 [`../../00-current/已知限制与待解.md`](../00-current/已知限制与待解.md) §C11、§E。
> 范围（对齐 HMCL 的口径）：**能给任意"远端元数据里有 Forge 制品"的 MC 版本装 Forge 并启动** —— 覆盖**两形态安装**（老 `install`+`versionInfo` 纯解包 / 新 `spec`+processors）与**三代启动**（≤1.12.2 LaunchWrapper / 1.13–1.16.x ModLauncher / 1.17+ BootstrapLauncher）。
> **范围收窄（2026-09-30，用户裁决）**：Forge **支持面截至 MC 1.20.1**（≥1.20.2 交给 NeoForge）⇒ 本文中 **≥1.20.2（③ 代 `ForgeBootstrap`）相关段落 = 范围外**（保留作知识）；**1.13+ 的应用内安装 = 后话（该文撰写时口径，仍只覆盖 ≤1.12.2）**——**2026-10-01 已落地，见下★**。现状以 [`../../00-current/现状基线.md`](../00-current/现状基线.md) §5 第 28 条为准；机制 / 阶段 1 首改 / 范围见 [`Forge-1.13及以上-调研与方案.md`](../20-design/launch/Forge-1.13及以上-调研与方案.md) §5.3。
>
> **★状态更新（2026-10-01，方案 A「`MeowLauncher` 退役」）—— 本文多处旧口径已变：**
> ① **不再有** `MeowLauncher` / 自研 system class loader（`-Djava.system.class.loader` **恒不设**）；所有形态**一律直启 `json.mainClass`**；
> ② legacy（≤1.12.2 Forge）的 classpath 由"平铺 + 门控"改为 **`ordered`（显式有序绝对路径列表）**，「启动器族」（launchwrapper / FML 本体 / OptiFine）**就在 classpath 上、不再摘出**；
> ③ **1.13–1.20.1 的应用内安装已落地**（processor 链，见 [`Forge-1.13至1.20.1-安装实施方案.md`](Forge-1.13至1.20.1-安装实施方案.md)）⇒ 与 ≤1.12.2 零 JVM 链合起来 = **应用内安装 Forge 覆盖 1.7–1.20.1**。
> 本文其余"计划 / 后话 / 经 `MeowLauncher`"表述均为**该文撰写时（2026-09-28）**的记录。

## 0. 结论速览

1. **可复用度高**：现有 loader 安装骨架（下载器 / maven 树落盘 / `composeXxxManifest` / 无窗 UIAbility 安装期 JVM）与 loader 名**解耦**，Forge 可整段复用，新增面主要是"Forge 列表 + profile 执行器入口"（A 报告判复用度 ≈70–80%）。
2. **"零 JVM 安装"面 = ≤1.12.2 全段**（**2026-09-28 T0 实测修正**）：真老形态（`install`+`versionInfo`）只到 ≤1.8.9；**1.12.2 已是 `spec:0` 但 client processor = 0** ⇒ 纯复制 + 组装 json，同样不跑 JVM。⇒ **判据是 client processor 数 > 0，不是 `spec` 有无**；1.13 起才需要 JVM。对 phone 侧的价值同 [`NeoForge无JVM安装-可行性与取证.md`](../20-design/launch/NeoForge无JVM安装-可行性与取证.md)。
3. **启动链已为现代加载器打开通道**，但**判据是按 loader 名写死的**（`loader === 'neoforge'` ⇒ 真 maven 树 + 不用 `MeowLauncher`〔当时表述；2026-10-01 起 = 直启加载器主类，`MeowLauncher` 已退役〕）⇒ 新增 Forge 时**必须把判据从"loader 名"改成"形态"**，否则老 Forge 会被误判。
4. **最大先决风险不在代码而在 Java 版本**：HMCL 对 Forge 的硬约束是 ≤1.16.999 需 **Java 7/8**、1.17 需 16、1.18–1.20.4 需 17、≥1.20.5 需 21；我们随包的是 **JRE 26** ⇒ **老 Forge 能否启动必须先实测**（见 §10 R1）。
5. **"完美支持"= 补齐 HMCL 的 4 处启动侧特判**：① LaunchWrapper 的 `--tweakClass` 重排；② ModLauncher 的 OptiFine transformer 注入；③ BootstrapLauncher 的 `ignoreList` 双形态修复 + `${primary_jar_name}`；④ 无条件的 `-Dfml.ignoreInvalidMinecraftCertificates/-Dfml.ignorePatchDiscrepancies`（C 报告 §7）。
6. **启动侧真代际 = 4 段**（T0 实测）：`≤1.12.2` LaunchWrapper / `1.13–1.16.x` ModLauncher / **`1.17.1–1.20.1` BootstrapLauncher + `-p`** / **`1.20.6+` `net.minecraftforge.bootstrap.ForgeBootstrap` 且无 `-p`** ⇒ module path **不能按"≥1.17"一刀切**（会误伤 1.20.6+）。

## 1. 目标与验收判据

**目标**：在**不改 MC、不引入新平台依赖**的前提下，把 Forge 纳入与 Fabric/NeoForge 同级的 loader 支持面。

**验收判据（分档）**

| 档 | 判据 |
|---|---|
| **A 档（必须）** | 1.13+ 形态：能装（复用 processor 链）+ 能启动；至少一个 1.17–1.20.1（带 `-p`）版本实机进主菜单（**原"与一个 1.20.6+（无 `-p`）版本"部分 2026-09-30 范围外**，见文首范围收窄） |
| **B 档（必须）** | ≤1.12.2：能装（**零 JVM**）+ 能启动（LaunchWrapper + legacy 链 + `--tweakClass`） |
| **C 档（加分）** | 与 HMCL 互操作（HMCL 装 → 我们启动 / 我们装 → HMCL 可读）；phone 上 B 档可用 |
| **不做** | 快照/极端老版本（<1.7.10）、OptiFine 集成包（仅保留"不崩"的最低限度）、Forge 自带 installer GUI |

## 2. 需求侧事实（只给指针，细则见前文）

- 安装侧 **3 种真形态**（`install`+`versionInfo` ≤1.8.9 / `spec:0`（1.12.2 = 0 processor，1.13.2+ 有）/ `spec:1`）与启动侧 **4 代际**：见 [`Forge支持-调研.md`](../20-design/launch/Forge支持-调研.md) **§11（T0 实测，含对 §1/§2 口径的修正）**。
- 真件 `1.20.1-47.1.106/47.4.23`（带 `-p`）与 `1.21.1-52.1.16`/`26.3-66.0.6`（无 `-p`）的 `arguments.jvm` 归类：**工作区根** `stuffs/research/forge-support/evidence/T0-findings.md` §2。
- 盘上格式（顶层扁平 + `patches[]`、`<id>.jar` 复制件、库落位判据 `hint=="local"`、不留 installer/`install_profile.json`）：[`Forge支持-调研.md`](../20-design/launch/Forge支持-调研.md) §4；T0 另证全部样本 `type=release` + **薄 `inheritsFrom`**。

## 3. 我方现状（可复用面）

- **安装侧**：可复用件清单、安装期 JVM 载体（`:neoinstall` 无窗 UIAbility + job 文件 + 结果文件回传）、processor 编排与 `PATCHED` 断言、**扩展点地图（文件级）**：A 报告 §3–§7。
- **启动侧**：argv 组装职责（ArkTS 拼 JVM argv / Java 只拼 vanilla 的 game 参数）、classpath 形态判据、`arguments.jvm` 原样展开、rules/去重/natives、legacy 分流、**启动侧特判清单**：B 报告 §2–§7。

## 4. 架构决策

### 4.1 安装：**按形态分流，而不是按 MC 版本号**

判据直接取 HMCL 的口径（`install_profile.json` 的键），因为版本号切点不可靠（1.20.1 的 Forge 就已带 `spec`）：

| 形态 | 判据 | 我方走法 |
|---|---|---|
| **老（纯解包）** | 含 `install` 且含 `versionInfo` | **新增一条轻路径**：解包 universal → 组装 manifest → 写盘。**不碰 JVM**，不复用 processor 链 |
| **新（processor）** | 含 `spec` | **复用 NeoForge 的 processor 链**（占位符/变量表/工具主类/产物断言全同构），差异仅在 profile 字段与 `path` |
| 其它 | 两键皆无 | 报错（对齐 HMCL 抛 `IOException`） |

理由：老形态"零 JVM"是**平台侧的稀缺能力**（phone），不该被强行塞进新形态的 JVM 通道；而新形态与 NeoForge 同构，重复实现没有收益。

### 4.2 启动：**classpath 形态判据从"loader 名"改为"形态"**

现状判据 `resolved.loader === LOADER_NEO_FORGE`（B 报告 §3）⇒ 真 maven 树 + 跳过 `MeowLauncher`。问题：老 Forge 是 `inheritsFrom` 形态、`loader` 认不出 ⇒ 会落到"平铺 + MeowLauncher"，而**现代 Forge 又需要真树**。⇒ 建议改为**形态判据**：

```
needRealTree = json.arguments.jvm 含 "-p" 或 "--module-path"     // 或 mainClass ∈ BN/ModLauncher 家族
```

理由：① 真树的前置不变量是"有 module path / 依赖真实布局"（B 报告 §3 已证 NeoForge 的动因）；② 不依赖 loader 识别是否正确，抗将来突变（对照 NeoForge 26.x 去掉 module path 的突变）；③ 老 Forge（LaunchWrapper 形态）自然走平铺 + `MeowLauncher`，与现有 legacy 链一致。

> **落地状态（2026-09-29 核对实现；2026-09-30 更新）**：本节原为**建议** —— `MinecraftLauncher.ets` 曾以 `resolved.loader === LOADER_NEO_FORGE` 决定"真 maven 树 + 跳过 `MeowLauncher`"。**2026-09-30 阶段 1 首改已按本节思路把 classpath 判据收敛到"启动形态主类"**（函数 `assembleNeoForgeClasspath` **2026-09-30 改名**为 `assembleRealTreeClasspath`；判据常量 `REAL_CLASSPATH_MAIN_CLASSES`）；主类分叉的"Forge 一律直启"（L3）**未落地**（当时 Forge 仍经 `MeowLauncher`）**——★2026-10-01 已落地：全形态一律直启、`MeowLauncher` 退役**。机制 / 首改 / 范围收窄见 [`Forge-1.13及以上-调研与方案.md`](../20-design/launch/Forge-1.13及以上-调研与方案.md) §5.3。

### 4.3 启动：**主类分叉沿用"NeoForge 例外"那条路**

**计划意图**：Forge 各代**不走 `MeowLauncher`**（主类 = json `mainClass`，game 参数由 ArkTS 组）——与 NeoForge 同路（B 报告 §2）。理由：Forge 各代的 mainClass（Launch/ModLauncher/BN）都有各自的参数契约，经 `MeowLauncher` 反射只会多一层不确定性；而现成通道已在 NeoForge 上实机验证。

**当前代码（与上段计划不符，2026-09-29 核对实现）**：主类分叉的判据是 `if (opts.meowcraftLaunch === true && !neoForge)`（`MinecraftLauncher.ets:404`）⇒ **只有 NeoForge 绕过 `MeowLauncher`；Forge（以及 vanilla/Fabric）今天仍走它**（`loader === 'forge'` 未参与该判据）。⇒ 上段"Forge 一律不走 `MeowLauncher`"是**计划**、**未落地**；落地时按 L3 扩为 `loaderMainDirect ∈ {neoForge, forge}`。（**★2026-10-01：已按"全形态直启、`MeowLauncher` 退役"落地** —— 主类分叉整个取消。）

### 4.4 loader 识别：**patch id 优先于库匹配**

Forge 47 的库表里含 `net.neoforged.fancymodloader:{core,loader}`（C 报告 §8-4）⇒ 按"命中 NEO_FORGE 库"匹配会误判。⇒ `detectLoader` 新增 Forge 分支时，**先看 `patches[]` 的 id（`forge`）**，再看库（`net.minecraftforge` × `forge`/`fmlloader`），并让 `forge` 优先于 `neoforge`（对齐 HMCL 的互斥语义：`matchLibrary` 命中 NEO_FORGE 则 FORGE 返回否，但 HMCL 是先按 patch id 定 id）。

### 4.5 不需要 `launcher_profiles.json`

那是**官方 installer 的前置**（[`NeoForge支持-调研.md`](../20-design/launch/NeoForge支持-调研.md) §8.3），HMCL 式自研安装不需要 ⇒ 我们不引入该前置（少一个平台侧写盘约束）。

## 5. 安装链改动面

| # | 改动 | 落点（现有符号为参照） |
|---|---|---|
| I1 | **Forge 端点与镜像行**：列表源 + installer URL 候选；`BMCLAPI_REWRITES` 加 Forge maven 前缀 | `constants/DownloadContract.ets`（仿 `fabricLoaderListCandidates` / `BMCLAPI_REWRITES`）|
| I2 | **`fetchForgeVersions`**：两源（官方自托管元数据 / BMCLAPI `forge/minecraft/<mcver>`）+ 逐源降级 + "200 空数组"语义 | 仿 `VersionInstaller.ets:fetchFabricLoaders`(:800) |
| I3 | **`installForgeVersion`（老形态）**：下 installer → 读 `install_profile.json` → 解包 `install.filePath` 的 universal 到 `install.path` 库路径 → `composeForgeManifest(versionInfo)` → 写盘 | 仿 `installFabricVersion`(:827) + `ForgeOldInstallTask.java:69-93` 的语义 |
| I4 | **`installForgeVersion`（新形态）**：复用 NeoForge 的 processor 编排（占位符/变量表/工具主类/`PATCHED` 断言）；profile 字段差异（`path` 可为 null）需容忍 | 复用 `NeoForgeInstaller.ets:buildNeoForgeProcessorPlans/expandValue/readToolMainClassAsync` 与 `VersionInstaller.ets:runNeoForgeProcessors`(:1178) |
| I5 | **`composeForgeManifest`**：顶层扁平 + `patches[game,forge]`；`jar=<实例名>.jar`；version 来源老=`versionInfo`、新=内嵌 `version.json` | 仿 `composeNeoForgeManifest`(:969) / `composeFabricManifest`(:758) |
| I6 | **`mergeModules` 补库**（新形态，真件声明 `jna-5.10.0.jar` 却不在清单）：安装侧补下 + 启动侧按名补 cp，**两侧必须一致** | 复用 `NeoForgeInstaller.ets:resolveMergeModuleEntries`(:348) + `VersionInstaller.ets:1099-1121` |
| I7 | loader 类型枚举与 UI 分流 | `state/InstallerState.ets`（`LOADER_KIND_*`:12-15 / `loaderKind`:69 / `installForge`）+ `components/GameVersionsView.ets` 分流点（:788-794 等）|
| I8 | **独立 Forge / NeoForge 下载源字段（已采纳，2026-09-30）** | `GlobalSettings.ets` 的 `network` 组：`forgeSource` / `neoForgeSource`（**不再复用 `downloadSource`**）—— 决策与 HMCL 对照见 [`实例设置存储-方案.md`](../20-design/launch/实例设置存储-方案.md) §2.1 |

**安装期载体**：新形态沿用 `NeoInstallAbility`（`:neoinstall`）与 job/结果文件协议；老形态**不需要载体**（纯解包在 ArkTS 内完成）。

> **零 JVM 两形态（≤1.8.9 / 1.12.2）的施工细案**（判别事实 / HMCL 做法 / 映射到现有代码 / 许可边界 / 未决点）**见 §13**。本次安装范围以 §13 开头为准（＝ **Forge，MC 1.7–1.12.2**）；本表 **I4（1.13+ 新形态）＝ 后话**（**★2026-10-01：I4 已落地**，见 [`Forge-1.13至1.20.1-安装实施方案.md`](Forge-1.13至1.20.1-安装实施方案.md)）。

## 6. 启动链改动面（工作量最大）

> ≥1.13 的专项调研与方案见 [`Forge-1.13及以上-调研与方案.md`](../20-design/launch/Forge-1.13及以上-调研与方案.md)。

| # | 改动 | 依据 |
|---|---|---|
| L1 | **`detectLoader` 加 Forge**（patch id 优先，见 §4.4）—— **已落地**（Forge 识别先于 NeoForge） | `VersionResolver.ets:483-537` |
| L2 | **classpath 形态判据改形态**（见 §4.2），并把 `mergeModules`/oshi 补件从"NeoForge 分支"释放为"真树分支" | `MinecraftLauncher.ets:163,178-183,569-611` |
| L3 | **主类分叉**：`neoForge` 改为 `loaderMainDirect ∈ {neoForge, forge}`（Forge 一律直启 json.mainClass） | `MinecraftLauncher.ets:393-414` |
| L4 | **`-Dfml.*` 默认旗标**（仅 Forge）：`-Dfml.ignoreInvalidMinecraftCertificates=true`、`-Dfml.ignorePatchDiscrepancies=true` | HMCL `DefaultLauncher.java:258-259` |
| L5 | **LaunchWrapper 代（≤1.12.2）**：`--tweakClass` 体系识别/保留/重排（FML / OptiFine / LiteLoader 的确定性顺序）；主类 `net.minecraft.launchwrapper.Launch` | HMCL `LaunchManifestNormalizer.java:89-153`、`GameComponentAnalyzer.java:182-191` |
| L6 | **ModLauncher 代（1.13–1.16.x）**：按 mainClass 特判（无 module path）；Forge+OptiFine 时注入 `transformer-discovery-service` 与 `-Dhmcl.transformer.candidates=` 的等价物 | HMCL `LaunchManifestNormalizer.java:64-66,156-185` |
| L7 | **BootstrapLauncher 代（1.17+）**：`ignoreList` 双形态修复 —— ① 安装规范化期补 `${primary_jar_name}`；② 启动期（旧 bootstraplauncher）把子串改写为**精确绝对路径** | HMCL `LaunchManifestNormalizer.java:193-223`、`DefaultLauncher.java:551-620` |
| L8 | **Java 版本约束**：Forge 各段的 Java 版本 + `MODLAUNCHER_8`（1.16.3–1.17.1）特例 ⇒ 决定我们**哪些版本可说"支持"**（R1 先决） | HMCL `JavaVersionConstraint.java:68-223` |
| L9 | legacy 链适配：老 Forge 走 legacy（LWJGL2 + gl4es + 自补 `-cp`）时的**类加载路径**核对（`-Djava.system.class.loader` 在 `INHERITS` 形态下不设，B 报告 §5 已标风险） | `MinecraftLauncher.ets:250-257,730-748`、`MeowLauncher.java:103-119` |

## 7. UI / 设置改动面

- 下载面板：loader 下拉加 `Forge`、版本列表（两源）、"装成单实例"（与 Fabric/NeoForge 同一套面板节奏）。落点见 A 报告 §5 的 `GameVersionsView` 分流点清单。
- 竞态：列表请求序号（`InstallerState` 的 `fabricLoaderSeq/neoLoaderSeq` 模式）需为 Forge 加一条。
- 新增设置项：各自 loader 的下载源（`forgeSource` / `neoForgeSource`，见 I8 与 [`实例设置存储-方案.md`](../20-design/launch/实例设置存储-方案.md) §2.1）。

## 8. 形态 × 代际 走法矩阵（按 **T0 实测** 更新）

| MC 段 | 安装形态（真件实测） | 启动代际（真件实测） | 走法（我们要做的） | phone |
|---|---|---|---|---|
| **≤1.8.9** | `install`+`versionInfo`（内嵌 universal） | LaunchWrapper | **纯解包**安装 + legacy 链 + L5（`--tweakClass`）+ L8 | **可装**（零 JVM）；启动受 R1 |
| **1.12.2** | `spec:0`、**0 processor**（`maven/` 内嵌 universal 纯复制） | LaunchWrapper | **纯复制**安装（仍零 JVM）+ 同上 | **可装**；启动受 R1 |
| **1.13–1.16.x** | `spec:0` + processors | `cpw.mods.modlauncher.Launcher`（**无 `-p`**） | processor 链安装 + L6 + L8（Java 16/17） | 装受 JVM 限制 |
| **1.17–1.20.1** | `spec:1` | `cpw.mods.bootstraplauncher.BootstrapLauncher`（**有 `-p`**） | processor 链安装 + **真树 cp** + L7 + L8（Java 17） | 同上 |
| **1.20.6+（范围外）** | `spec:1`（`hideExtract`/`serverJarPath`，`path` 带 `:shim`） | **`net.minecraftforge.bootstrap.ForgeBootstrap`（无 `-p`）** | processor 链安装 + **“平铺即可”＝待验证假设（无真件/HMCL 证据，未取证）** + L8（Java 21）；**整行 2026-09-30 范围外**（≥1.20.2 交 NeoForge） | 同上 |
| 快照/更老 | — | — | 不做（C 档外） | — |

> 要点：① **`-p` 不能按"≥1.17"一刀切**（1.20.6 已去掉）；② **零 JVM 安装面是 ≤1.12.2 全段**；③ 1.20.6+ 真件只证 `arguments.jvm` 无 `-p`，**不代表"平铺即可"** —— `ForgeBootstrap` 须自行发现库并做 classpath 分区（平铺只给一个通配串），该断言**未取证、标为待验证假设**（见 [`Forge-1.13及以上-调研与方案.md`](../20-design/launch/Forge-1.13及以上-调研与方案.md) §3.3）。

## 9. 分阶段实施

| 阶段 | 内容 | 出口判据 |
|---|---|---|
| **T0 取证补齐** ✅（2026-09-28 完成） | 下 11 份真 installer（≤1.8.9 / 1.12.2 / 1.13.2 / 1.16.5 / 1.17.1 / 1.18.2 / 1.20.1 / 1.20.6 / 1.21.1 / 26.3）→ 解 `install_profile.json` + `version.json` | ✅ 已产出：**修正 §8 矩阵**、消解原 R2 的 3 处主要未确认（残 4 条见 §10 R2）；报告 **工作区根** `stuffs/research/forge-support/evidence/T0-findings.md` |
| **T1 零 JVM 安装**（≤1.12.2） | I1/I2/I3/I5（+ I7 最小）——纯 ArkTS，两种形态（内嵌 universal 解包 / `maven/` 纯复制）；**细案见 §13** | 装出的实例与 HMCL 装的一致（逐文件比对） |
| **T2 processor 安装**（1.13+，**后话** = 超出本次范围，见 §13；**安装上界收到 ≤1.20.1，2026-09-30**；**★2026-10-01 已落地**，见 [`Forge-1.13至1.20.1-安装实施方案.md`](Forge-1.13至1.20.1-安装实施方案.md)） | I4/I6 + I7 完整（③ 代 `ForgeBootstrap` 范围外） | 1.20.1（带 `-p`）装成，`PATCHED` 断言通过（**1.21.1 无 `-p` 部分 2026-09-30 范围外**） |
| **T3 启动通道** | L1/L2/L3/L4 | 1.17–1.20.1 各一版进主菜单（**1.20.6+ 2026-09-30 范围外**） |
| **T4 代际特判** | L5/L6/L7 | 1.7.10（或 1.8.9）/ 1.12.2 / 1.16.5 / 1.20.1 各一版进主菜单 |
| **T5 Java 版本收口** | L8 + 实测（R1） | 明确"可支持版本段"清单；不可支持段写进已知限制 |
| **T6 UI 与互操作** | §7 + 与 HMCL 双向验收 | HMCL 装 ↔ 我们启动 双向通 |

## 10. 风险与未知点

| # | 风险 | 影响 | 处置 |
|---|---|---|---|
| **R1** | **JRE 26 vs Forge 的 Java 版本要求** | **已实测定案（2026-09-28，用户三次实机）**：**≤1.12.2 在随包 JRE 26 上不可启动**。三阶段取证：① `ClassCastException`（launchwrapper 假设 JDK 8 的 `AppClassLoader extends URLClassLoader`）⇒ 换系统 CL + 把"启动器族"摘出平铺目录后过掉；② `NoClassDefFoundError: ITweaker`（同第二次修掉）；③ **终局卡点 = `UnsupportedOperationException: Setting a Security Manager is not supported`**（`FMLTweaker.<init>`；**JEP 486 / JDK 24+ 永久禁用 SecurityManager、任何 flag 无效**，且 FML 只 catch `SecurityException`）。⇒ **不是我们传参/类加载的问题，是上游件与 JDK 26 的结构性冲突**。<br>**第二轮（2026-09-28，已闭环）**：把这 3 字节那次调用摘掉（探针，证据在工作区根 `stuffs/research/forge-support/r1-probe/SM-PATCH.md`）后堆栈推进到 coremod 注入阶段，新卡点 = **`java.lang.NoClassDefFoundError: java/util/jar/Pack200`**（`ClassPatchManager.setup`；**JEP 367 / JDK 14 删除**，且它读的 `binpatches.pack.lzma` 就在 universal jar 里，躲不开）。⇒ **能跑原样 1.12.2 客户端的 JDK 上限 = 13**（23/21/17/14 均出局；`java.util.jar.Pack200` 是 JDK 类、无法从 classpath 提供） | 出路二选一定案为 **C = 给 legacy 段配 Java 8**（HMCL `MODDED_JAVA_8` 口径，且 1.13–1.16 段亦要求 8）：收编工序已落地在工作区根 `Harmomeow-Craft-Launcher/tools/jre8/`。**D = 支持面收窄到 1.13+** 仍作为备选（若 Java 8 在 OHOS 上走不通，把 ≤1.12.2 登记进 [`../../00-current/已知限制与待解.md`](../00-current/已知限制与待解.md)）。**A′（逐个魔改上游件）已弃**：每道墙都要自造轮子且 Pack200 那道无小补丁替代 |
| **R2** | 需求侧残留未确认（**T0 后**）：① 1.13–1.16 段内的形态漂移（只测两端）；② **1.20.1→1.20.6 之间的确切切点**（1.20.2–1.20.4 未测）；③ 1.14/1.15 未测；④ JRE 26 可行性 | 细节可能返工 | 补测即可；主结论（4 代 + 零 JVM 面）已由 11 份真件支撑 |
| **R3** | Forge 47（1.20.1）的库表含 `net.neoforged.fancymodloader` | loader 误判（当 NeoForge） | §4.4：patch id 优先 |
| **R4** | phone 上 1.13+ 的安装仍需 JVM 宿主（与 NeoForge 同受限） | phone 只能覆盖 ≤1.12.2 | 与 [`安装期JVM载体-调研.md`](安装期JVM载体-调研.md) §10 的结论并列登记 |
| **R5** | 老 Forge 在 `inheritsFrom` 形态下不设 `-Djava.system.class.loader` ⇒ `MeowLauncher` 的运行期追加 classpath 失效 | 可能缺类 | T1/T3 实测；必要时把"平铺 `-cp` 自足"作为硬前提核验。**（★2026-10-01：已消解** —— `MeowLauncher` 退役、全形态直启；legacy 走 `ordered` 显式列表，不再依赖"运行期追加 classpath"） |
| **R6** | 真树 cp 判据若仍按 loader 名，会与 ≤1.16 段冲突 | 启动崩 | §4.2 已改为形态判据（T0 §11.2 支持该判据：`-p` 只在 1.17–1.20.1） |
| **R7** | Forge 的 `-DmergeModules`/`-DignoreList` 依赖**按文件名**补库（T0 实测 1.17.1 起出现） | 启动崩（同类已有实机教训） | 复用现有两侧一致的 mergeModules 机制并补 ignoreList 的 `${primary_jar_name}` |

## 11. 验收矩阵（跑起来要覆盖的格子）

| 维度 | 取值 |
|---|---|
| 安装形态 | 老（纯解包）/ 新（processor） |
| 启动代际 | LaunchWrapper / ModLauncher / Bootstraplauncher |
| 设备 | 2in1（全量）/ phone（老形态安装 + 其启动，视 R1） |
| 渲染后端 | 推荐（桌面 GL）/ GL4ES（legacy 段必测）/ Vulkan（≥26.2，与 Forge 无关但需确认不互斥） |
| 互操作 | HMCL 装 → 我们启动；我们装 → HMCL 读 |

## 12. 参考 / 台账

- 需求侧：[`Forge支持-调研.md`](../20-design/launch/Forge支持-调研.md)（HMCL 的 Forge 支持面 / 两形态 / 盘上格式）、**工作区根** `stuffs/research/forge-support/C-forge-requirements.md`
- 我方现状：**工作区根** `stuffs/research/forge-support/A-our-install-side.md`（安装侧可复用面 + 扩展点地图）、`stuffs/research/forge-support/B-our-launch-side.md`（启动侧特判清单 + 已知坑）
- 同族方案：[`NeoForge支持-改动方案.md`](NeoForge支持-改动方案.md)（processor 链 / 真树 cp / 无窗载体 的既有决策）、[`Fabric安装-方案.md`](Fabric安装-方案.md)、[`安装期JVM载体-调研.md`](安装期JVM载体-调研.md)、[`NeoForge无JVM安装-可行性与取证.md`](../20-design/launch/NeoForge无JVM安装-可行性与取证.md)
- 真件物证：**工作区根** `stuffs/research/neoforge/extracted/1.20.1-47.1.106.{install_profile,version}.json`（T0 需补更老/更新样本）

## 13. 零 JVM 安装（≤1.12.2）实现细案（2026-09-29；**本次范围已定 = 用户裁决**）

> **范围（2026-09-29 用户裁决，本次范围已定）**：本次 = **Forge 安装，MC 1.7 – 1.12.2 全段**（零 JVM 面，见 13.1；**1.9–1.12.1 的六份真 installer 已于 2026-09-29 逐版静态核验：全为 `legacy` 形态、client processor = 0**，见 §13.6 第 2 条）。
> **范围外**：**OptiFine 组合 = 不管**（其安装路径与启动侧 OF 特判本就不同，本细案不覆盖，见 §6 L5/L6）；**1.13+ 的安装 = 后话**（见 §13.6 第 3 条；**★2026-10-01 已落地**）。
> 本节把 §5 的 I1–I5/I7 与 §9 的 T1 展开为可施工的细案；**只出方案、不动代码**，**不复述现状**（口径以 §5/§9 与主页为准）。
> 依据：T0 真件（**工作区根** `stuffs/research/forge-support/evidence/**`）、HMCL 只读源码（`ref/HMCL/HMCLCore/src/main/java/org/jackhuang/hmcl/download/forge/`）、我方现有安装骨架（**主仓** `entry/src/main/ets/common/**`）。

### 13.1 判别事实：安装是否需要 JVM（已研究，不复述推导）

唯一判据 = **client 侧 processor 数 > 0**（**不是** `spec` 的有无）；对 phone 侧的价值同 [`NeoForge无JVM安装-可行性与取证.md`](../20-design/launch/NeoForge无JVM安装-可行性与取证.md)。两个**零 JVM 子形态**：

| 子形态 | `install_profile.json` 形态 | 零 JVM 的原因 | 真件 |
|---|---|---|---|
| **≤1.8.9** | `install`+`versionInfo`（**无 `spec`**） | 纯解包：把 installer 根内嵌的 `install.filePath`（`…-universal.jar`）写到 `libraries/<install.path 的 Maven 路径>` | `…/evidence/{1.7.10-…,1.8.9-…}/install_profile.json` |
| **1.12.2** | **`"spec": 0` 且 `"processors": []`** | 走"新形态"编排但 **processor 循环跑 0 个任务** ⇒ 纯复制：installer 内 `maven/…` 命中项 + 主制品（`path`）落共享库区 | `…/evidence/1.12.2-14.23.5.2864/install_profile.json` |
| **1.13+** | `spec:0/1` + 非空 `processors` | —（**需要 JVM**） | 同目录 1.13.2 起各样本 |

> 归纳见 **工作区根** `stuffs/research/forge-support/evidence/T0-findings.md` §1（1.12.2 内可见 `"processors": []`、`"path": "net.minecraftforge:forge:1.12.2-14.23.5.2864"`、`"json": "/version.json"`）。

### 13.2 HMCL 的做法（只取 approach；行号对应 `ref/HMCL/.../download/forge/`）

- **类型判定**：开只读 zip 读 `install_profile.json` —— 含 `spec` ⇒ 新（`ForgeNewInstallTask`）；含 `install`+`versionInfo` ⇒ 老（`ForgeOldInstallTask`）；否则抛 `IOException`（`ForgeInstallTask.java:137-155`）。
- **只下 installer jar**：`FileDownloadTask` 下候选 URL（BMCL 源的每项给 **3 条**：`files.minecraftforge.net/maven` 的两种布局 + BMCLAPI `/forge/download`，`ForgeBMCLVersionList.java:96-104`；官方源则由 `webpath` 拼一条，`ForgeVersionList.java:74-83`），**完整性 = ZIP 结构校验**（`ForgeInstallTask.java:78-84` 挂 `ZIP_INTEGRITY_CHECK_HANDLER`）—— 元数据里的 `hash` 字段（`ForgeBMCLVersionList.java:201-227`）**未用于 installer**。
- **installer 的获取与校验（HMCL 通用下载器形态）**：每次**新建临时文件**下载（`download/forge/ForgeInstallTask.java:76`；NeoForge 同形 `download/neoforge/NeoForgeInstallTask.java:67`）、在临时文件上跑 **ZIP 结构完整性校验**（`task/FileDownloadTask.java:303-310` 的 `ZIP_INTEGRITY_CHECK_HANDLER`；挂载见 `ForgeInstallTask.java:78-84`）后才 `Files.move(temp, file, REPLACE_EXISTING)` 落位（`FileDownloadTask.java:258`）；失败 / 未过校验**一律删临时文件**（`FileDownloadTask.java:276-278`；任务用完即删见 `ForgeInstallTask.java:93`、`NeoForgeInstallTask.java:85`），**只有通过后才开只读 zip 读 `install_profile.json`**（`ForgeInstallTask.java:137-155`、`NeoForgeInstallTask.java:122-124`）；下载叠加**逐 URL 重试 ×5**（`task/FetchTask.java:47`）与 **Range 断点续传**（`:140-141`、`:326-327`）⇒ 坏文件从不进持久位置。
- **已存在的库 / 资源的自愈**：`integrityCheck==true` 时按 sha1 / ZIP 复验、不符即重下（`download/game/GameLibrariesTask.java:89-120`；安装链里 Forge / NeoForge 的 profile 库正以 `true` 调用，`download/forge/ForgeNewInstallTask.java:329`、`download/neoforge/NeoForgeOldInstallTask.java:313`）；真实触发 = 上次异常退出在实力例根留下的 `.abnormal` 标记（`ref/HMCL/HMCL` 模块 `.../game/LauncherHelper.java:161` 读、`.../game/HMCLGameInstance.java:490-493` 写）⇒ 崩溃一次的实例下次启动自动补坏件。
- **老形态（零 JVM）5 步**：读 `install_profile.json`（`ForgeOldInstallTask.java:70-74`）→ 由 `install.path` 定位库文件并建父目录（`:77-80`）→ 把 `install.filePath` 的内嵌 jar 解到该库路径（`:82-86`）→ 由 `versionInfo` 产 Forge 补丁（`:88-92`）→ 补库/校验（`:93`）。**全程无外部进程**。
- **`spec` 形态（1.12.2 亦走此路）**：`preExecute` 把 `maven/` 内命中的库逐条拷进仓库 layout（`ForgeNewInstallTask.java:310-316`）、把主制品 `profile.getPath()` 拷到 artifact 路径（`:318-324`）；内嵌启动清单 = `fs.getPath(profile.getJson())`（`:308`）；`execute()` 的 `Task.runSequentially(processors…map(…))`（`:434-437`）在 `processors=[]` 时是**空序列 ⇒ 不建 JVM**；库清单下载 = `GameLibrariesTask(profile.getLibraries())`（`:329`）。
- **版本 json 的产出**：老 = 用 `versionInfo` 产补丁（`ForgeOldInstallTask.java:88-92`）、新（含 1.12.2）= 用内嵌 `version.json` 产补丁（`ForgeNewInstallTask.java:443-447`）；builder 最终压成**顶层扁平 + `patches[]`**、并把原版 client jar 复制到 `versions/<id>/<id>.jar`（`DefaultGameBuilder.java:169-174`；盘上格式细则见 [`Forge支持-调研.md`](../20-design/launch/Forge支持-调研.md) §4）。
- **无启动器侧占位符替换**（两个零 JVM 形态）：`versionInfo` / 内嵌 `version.json` 的 `minecraftArguments` 里 `${auth_player_name}` / `${version_name}` / `${game_directory}` … 是 **Mojang 启动期占位符**，安装时**原样携带**；只有 `spec` 形态的 processor `data` 才有 `[maven]`/`{var}`/`'literal'` 语法（`ForgeNewInstallTask.java:406-430`），而那属于**需 JVM**的形态。真件 `minecraftArguments` 见证据目录的 `version.json`。

### 13.3 我方实现拆解（映射到现有代码；零 JVM = 现有机制去掉 processor 链）

**已有（可直接复用）**：

- 安装骨架三件套：**主仓** `entry/src/main/ets/common/data/VersionInstaller.ets` 的 `installVersion`(:635)/`installFabricVersion`(:827)/`installNeoForgeVersion`(:1029)，收尾都是 `writeText(versionJsonPath(gameRoot, instanceName), …)`（:694/:907/:1171）。
- 下载契约：**主仓** `entry/src/main/ets/common/constants/DownloadContract.ets` 的端点模板 + `BMCLAPI_REWRITES`(:126-135) —— **当前无 Forge maven 前缀**（`https://maven.minecraftforge.net/`、`https://files.minecraftforge.net/maven` 未入表 ⇒ 按 I1 补）。
- 库 / Maven 机制：`libraryItem`(:331) 已支持 `downloads.artifact.{path,url,sha1,size}` **与**"无 downloads 时按 `lib.url`/缺省仓库 + `mavenPath(name)` 拼"（:383-390）⇒ **老形态 `versionInfo.libraries`（name+url）与新形态 `downloads.artifact` 都能落 `libraries/**`**。
- 解包：`zlib.decompressFile(jarPath, unzipDir)`（:1062；installer jar → 工作目录）。
- 沙箱 staging（`cacheDir/…`，`ClasspathStager.ets`）；**安装期 JVM 载体** `:neoinstall` 无窗 UIAbility（**仅 1.13+ 形态需要**，见 §5 末与 [`安装期JVM载体-调研.md`](安装期JVM载体-调研.md)）；启动侧 legacy 支持见 §5 L1/L2/L3。

**缺（按 I1–I7 新增）**：

- **Forge 版本列表源 + installer URL 候选**（I1/I2）：仿 `fetchFabricLoaders`(:800) 的"两源 + 逐源降级 + 200 空数组 = 无"语义。
- **两个零 JVM 安装函数**（I3）：① **老形态** = 下 installer → `zlib.decompressFile` → 读 `install_profile.json` → 把 `install.filePath` 指向的内嵌 jar 写到 `libraries/<install.path>` → `composeForgeManifest(versionInfo)`；② **`spec:0` 形态（1.12.2）** = 同上但读 `json` 指的内嵌 `version.json`、把 `maven/` 命中项与主制品（`path`）落库（**不跑 processor**）。
- **清单组装**（I5）：仿 `composeFabricManifest`(:758)/`composeNeoForgeManifest`(:969) ⇒ 顶层扁平 + `patches[game,forge]`。
- **loader 枚举 + UI 分流**（I7）：**主仓** `entry/src/main/ets/common/state/InstallerState.ets:12-15` 的 `LOADER_KIND_*` 现只有 vanilla/fabric/neoforge。

> **口径**：zero-JVM 安装 = **现有机制去掉 processor 链**，不是新引擎（下载 / 落库 / 写清单全复用）。

### 13.4 许可边界

`ref/HMCL` 是 **GPLv3**（各文件头即 GPLv3）⇒ **学做法、不搬代码**。划清两类：

- **格式强定的既成事实（按格式实现即可）**：`install_profile.json` 的键语义（`spec` / `install.{path,filePath,minecraft}` / `versionInfo` / `processors` / `data` / `json`）、`maven/` 目录布局、库的 `downloads.artifact.{path,url,sha1,size}`、processor `data` 值的 `[artifact]`/`{var}`/`'literal'` 语法。
- **HMCL 专有构造（只当参照，不照搬）**：`patches[]` 扁平清单、库落位的 `hint=="local"` 判定、自托管元数据端点 `https://hmcl.glavo.site/metadata/forge/`。

⇒ 我们产盘仍写 `patches[]`（它是**互操作契约**，见 §4/§5 与 [`Forge支持-调研.md`](../20-design/launch/Forge支持-调研.md) §4），但**代码自研**。

### 13.5 与兼容铁律（§二.3 推论①）的关系

本细案全部落在**安装路径**上 ⇒ 按 [`../../00-current/工程与规范.md`](../00-current/工程与规范.md) §二.3 **推论①（2026-09-29 用户裁决：铁律在安装时豁免）**，**可写** `versions/<id>/{<id>.json,<id>.jar}` 与共享 `libraries/**`（含写进用户已有游戏目录）；但**不得**把**我们自己的配置 / 状态**写进用户游戏目录（先例 = 已废弃的 `config/splash.properties` 策略）。

### 13.6 未决点

1. **installer jar 无强校验 ⇒ 定为「结构可解 + 复用期自愈」**（2026-09-30 定案；`691777b`）：**不做哈希校验**（**官方**源 `maven-metadata.xml` 只有目录名、无 installer 的 sha1；**镜像**源 BMCL 列表的 `files[].hash` 实测 = 该 sha1〔见下备选〕，但本轮未接入；见 §13.2），改由**结构可解性 + 复用前自愈**兜坏缓存 —— `installForgeVersion`（**主仓** `entry/src/main/ets/common/data/VersionInstaller.ets`）复用 `forge-installer/<源>/<loader 版本>/installer.jar` 时**先解一次**（`extractArchive`）：解不出所需文件即判坏（`install_profile.json`；`spec` 形态还需 `profile.json` 指向的**内嵌启动清单**，校验面与 NeoForge `NeoForgeArchive` 同款）→ 打稳定英文告警（`cached forge installer unusable, re-downloading: …`）→ 删文件 → 重下（**当次安装内自愈**，坏缓存不会永久复用）；为此 installer 走**下载原语 `downloadFile`（非 `runDownloads`）**（`installForgeVersion` 的 `downloadInstaller`，:1945-1950）以保官方兜底不丢。**所照 HMCL 形态** = 临时文件 + ZIP 结构校验 + 用完即删（见 §13.2「installer 的获取与校验」条）。**备选（更强、本轮未做）**：BMCL 列表 `files[].hash`（`category=="installer" && format=="jar"`）实测 = installer 的 sha1（三样本对上官方 maven 件）⇒ 可做比 HMCL 更严的 sha1 校验，但需跨层接线 + 一次额外往返。
2. **样本覆盖面（= 覆盖前提）—— 已核验（2026-09-29）**：T0 只取 ≤1.8.9 / 1.12.2 两端真件，当时 1.9–1.12.1 是否同构**尚无物证**；**该逐版核验义务已在实现期履行** —— 又取 **6 份真 installer**（`1.9 = 12.16.1.1938-1.9.0`、`1.9.4`、`1.10.2`、`1.11.2`、`1.12`、`1.12.1`），逐份静态核实其 `install_profile.json` **全部归入 13.1 的 `legacy`（`install`+`versionInfo`）子形态、client processor = 0** ⇒ 零 JVM 面 **1.7–1.12.2 全段**由物证支撑（另有 `1.7.10` / `1.8.9` / `1.12.2` 来自 T0）。**失败安全（保留）**：不在物证列内的细分版本**不靠推断声称覆盖**，而由 `VersionInstaller.ets::classifyForgeProfile` 兜底 —— 形态不落两子形态之一（带 client processor / 键不认识）即判 `unsupported` 并**明确拒绝、不留残缺实例**（`:1721-1729`）。
3. **1.13+（需 JVM）＝ 范围外（后话，2026-09-29 用户裁决）**：不在本次内；后一阶段可**复用** `:neoinstall` 载体 + 现有 `runNeoForgeProcessors`（`VersionInstaller.ets:1184`，I4 已规划复用），**参考 HMCL 的做法**，留待 T2。（**2026-09-30 追加**：安装上界收到 **MC 1.20.1**；Forge 支持面截至 1.20.1、≥1.20.2 交 NeoForge —— 见 [`Forge-1.13及以上-调研与方案.md`](../20-design/launch/Forge-1.13及以上-调研与方案.md) §5.3。）（**★2026-10-01 追加**：**已落地** —— 1.13–1.20.1 的应用内安装走 processor 链 + `common/data/ForgeNewInstaller.ets`，见 [`Forge-1.13至1.20.1-安装实施方案.md`](Forge-1.13至1.20.1-安装实施方案.md)。原文的"复用 `runNeoForgeProcessors`"未被采用 —— 改用**方案 B**，两链的**编排内核**各存一份，但**载体机理**共用，见该文 §1 的 2026-10-01 更新。）

> **1.13–1.20.1 的应用内安装细案见** [`Forge-1.13至1.20.1-安装实施方案.md`](Forge-1.13至1.20.1-安装实施方案.md)（**方案 B：Forge 与 NeoForge 安装办法分开、不做设备门（有意推迟）**，含逐条改造清单与分期）。
