# Forge 1.13–1.20.1 应用内安装实施方案（方案 B：Forge 与 NeoForge 安装办法分开）

> 已归档（2026-10-01；因为 Forge 1.13–1.20.1 安装结论已并入现役档（安装链-总览 §3）；现役口径见 [`安装链-总览.md`](../20-design/launch/安装链-总览.md)）。

> **本文 = 带日期的实施方案（2026-09-30）**，属 20-design，只写 **带日期的记录 + 指针**，**不写活状态**。
> **决策变更（2026-09-30，用户裁决）**：安装办法由「方案 A（把 NeoForge 链泛化）」**改为方案 B（Forge 与 NeoForge 彻底分开、不泛化）**（理由 = 隔离风险、安全，见 §1）；**本轮不做设备门**（phone 上有意接受失败，见 §2.11），设备门被**有意推迟**。
> 支持面现状以 [`../../00-current/版本支持边界.md`](../00-current/版本支持边界.md) 与
> [`../../00-current/现状基线.md`](../00-current/现状基线.md) §5 第 28 条为准；未决项登记见
> [`../../00-current/已知限制与待解.md`](../00-current/已知限制与待解.md)。
> 上游与前置：[`Forge-1.13及以上-调研与方案.md`](../20-design/launch/Forge-1.13及以上-调研与方案.md)（§1 四世代 / §2 安装侧 / §5 分期）·
> [`Forge支持-改动方案.md`](Forge支持-改动方案.md) · [`Forge支持-调研.md`](../20-design/launch/Forge支持-调研.md) ·
> [`NeoForge支持-改动方案.md`](NeoForge支持-改动方案.md) · [`NeoForge安装链-逐行取证.md`](../20-design/launch/NeoForge安装链-逐行取证.md) ·
> [`安装期JVM载体-调研.md`](安装期JVM载体-调研.md) · [`多JRE共存-方案.md`](多JRE共存-方案.md) ·
> [`classpath形态-真树与平铺-决策情报.md`](classpath形态-真树与平铺-决策情报.md)。
> 读核基准（2026-09-30）：主仓 HEAD = `ef9d9a4`。**本文引用代码一律用「文件 + 函数/常量名」（不写行号）。**

## 0. 范围与判型

### 0.1 范围（用户裁决，2026-09-30）

- **本方案只做 Forge for MC 1.13–1.20.1 的「应用内安装」。** 启动侧已通（1.16.5 / 1.20.1 真机跑起来；机制与首改见 [`Forge-1.13及以上-调研与方案.md`](../20-design/launch/Forge-1.13及以上-调研与方案.md) §3/§5.3），**不在本方案内**。
- **≤1.12.2 不在本方案内**：零 JVM 链已实现（老形态 `install`+`versionInfo`、`spec:0`+空 processors）。
- **≥1.20.2 不在本方案内**：Forge 支持面截至 1.20.1，更高交 NeoForge。
- **≥1.20.3（③ 代 `ForgeBootstrap`）不在本方案内**。
- **1.20.2–1.20.4 已补样（2026-09-30）：③ 代 = 1.20.4（及 1.20.3），②→③ 切点 = 1.20.2 → 1.20.3。** 1.20.2 仍是 ② 的**安装形态**（`spec:1`、`serverJarPath` 普通、`path` 无、内嵌 `maven/` 0），但**主类已改名**为 `net.minecraftforge.bootstrap.BootstrapLauncher`（仍在 `arguments.jvm` 带 `-p`）⇒ **按世代封顶时 1.20.2 的安装形态可顺带，1.20.3 / 1.20.4 不顺带**。注意 **1.20.2 的主类不在我方启动侧 `REAL_CLASSPATH_MAIN_CLASSES` 清单里**（故外部 1.20.2 实例不会走真树）——这正是**「按 1.20.1 封口」边界干净**的原因。**1.20.2–1.20.4 仍不写入支持面**（免费搭车不承诺）。
- **更正（2026-09-30 用户设备实测）：③ 代"范围外"现为政策选择、而非技术必然。** 该代原先被记下的"模块化 classpath 撞包"（[`Forge-1.13及以上-调研与方案.md`](../20-design/launch/Forge-1.13及以上-调研与方案.md) §5.2 C）在当前实现下**不再出现**：把 Forge ≥1.13 改为**直接以加载器主类启动**后，随包 `launcher.jar` 桩件不进 classpath ⇒ `com.mojang.text2speech` 只剩真实库一个提供者；实测 **Forge 1.21.1 已进游戏界面并干净退出**（`ResolutionException` 计数 = 0）。**但 ③ 代的应用内安装仍未支持**（本方案的安装链按 ①② 代建模）：③ 代另有 `hideExtract` / `serverJarPath` / `path` 带 `:shim` 三项形态差异需额外适配，不在本方案内。活状态以 [`../../00-current/现状基线.md`](../00-current/现状基线.md) §5 第 28 条与 [`../../00-current/已知限制与待解.md`](../00-current/已知限制与待解.md) §E 为准。

### 0.2 世代与安装判型（11 份真件实证）

| 世代 | MC 段 | 启动 mainClass（形态） | install `spec` | client processor | `arguments.jvm` 的 `-p` | 内嵌 `maven/` | installertools |
|---|---|---|---|---|---|---|---|
| ① | **1.13–1.16.5** | `cpw.mods.modlauncher.Launcher` | `0`（但 processors **非空**） | 4–5 | **无** | **恒 7 条**（5 目录项 + 主制品 + `:universal`，均内嵌；**已证实**） | 1.0.3 / 1.3.0 |
| ② | **1.17.1–1.20.1** | `cpw.mods.bootstraplauncher.BootstrapLauncher` | `1`、`path:null`、有 `serverJarPath` | 有 | **有**（7–8 jar：bootstraplauncher + securejarhandler + asm×5 + JarJarFileSystem） | 0（1.20.1 为 24 条） | 1.2.7 / 1.4.1 |
| ③ | ≥1.20.3 | `net.minecraftforge.bootstrap.ForgeBootstrap` | — | — | — | — | 范围外 |

> **②→③ 过渡（1.20.2，已补样）**：安装形态仍是 ②（`spec:1`、`serverJarPath` 普通、`path` 无、内嵌 `maven/` 0），**主类已改名**为 `net.minecraftforge.bootstrap.BootstrapLauncher`（仍带 `-p`）⇒ 该主类不在我方 `REAL_CLASSPATH_MAIN_CLASSES` 内，**外部 1.20.2 实例不会走真树**（这正是「按 1.20.1 封口」边界干净的原因，详见 §0.1）。

**判型判据 = client 侧 processor 数（不是 `spec` 有无）：**

- `spec:0` **且** `processors: []`（**1.12.2**）才是零 JVM；
- **1.13.2 / 1.16.5 是 `spec:0` 但有 processor** ⇒ 需 JVM；
- `spec` 值与该世代主制品形态无关；MC 版本号**完全不参与**判型（`install_profile.json` 无 `minecraft` 判型字段）。

**判据落点**：`VersionInstaller.ets` 的 `classifyForgeProfile` + `forgeClientProcessorCount`（缺省 `sides` = 双端）。

## 1. 决策：方案 B（Forge 与 NeoForge 安装办法分开，不泛化）

**用户裁决（2026-09-30）**：Forge 与 NeoForge 的安装办法**彻底分开、不泛化**。理由 = **隔离风险、安全**——NeoForge 以后肯定还会更新、**可能改变行为**，把 Forge 挂在 NeoForge 的 processor 链上会把 NeoForge 的将来变动**传染**给 Forge；分开后一侧改动不牵动另一侧。

（原「方案 A（把 NeoForge 的 processor 链泛化成共享链）」**作废**：其理由「真件字段逐字同构 / HMCL 已漂移 / 三缺口只修一遍」在**技术上**仍成立，但被上述**风险隔离**权衡**否决**——用户**接受**重复的代价换取隔离。）

**方案 B 的具体形态：**

- **新增 Forge 自己的一套**：**独立文件**（建议 `common/data/ForgeNewInstaller.ets`，与 `common/data/NeoForgeInstaller.ets` 平行）；**编排入口** = `common/data/VersionInstaller.ets` 里与 `installNeoForgeVersion` **平行的新函数**（暂名 `installForgeNewVersion`）。
- **不得调用 NeoForge 侧的函数**：`buildNeoForgeProcessorPlans` / `resolveMergeModuleEntries` / `runNeoForgeProcessors` / `composeNeoForgeManifest` 等**一律不调**；需要的能力在 Forge 侧**独立实现**（**可参照其逻辑，但代码独立**）。
- **明确记录代价**：处理器**编排内核**会在两侧各存一份——**退出码权威**、**结果文件新鲜度基线**（`ProcessorResultBaseline`）、**软超时**（`PROCESSOR_SOFT_TIMEOUT_MS` = 120 s）、**`STARTUP_HIDE` 独立进程载体**、**`16000068` 退避重试**；将来修一处要修两处（**HMCL 的 zlib 漂移**——`ForgeNewInstallTask` 有降级、`NeoForgeOldInstallTask` 无——就是这种代价的**实证**）。用户**接受**该代价以换取**风险隔离**。
- **★更新（2026-10-01，用户裁决）：上面那条"编排内核两侧各存一份"收窄了 —— 只针对「安装办法 / 数据层」，不再包含「载体机理」。** 落地后定案的**精确边界**：
  - **共享（已抽成一段）**：与 loader 无关的**载体机理** —— 起无窗 `:neoinstall` 进程（`processMode`/`startupVisibility` 成对）、job 文件协议、**结果文件字节偏移式新鲜度基线**、**退出码权威**、软/硬超时、`16000068` 退避重试、进程探针。落点 = `common/data/VersionInstaller.ets` 顶部「安装期工具 JVM 载体」的 `runToolJvmOnce`（两条链共用）。**理由 = 那几条是"已验证修复"，各存一份会让将来只修一处**（HMCL 的 zlib 漂移正是这种代价的教训）。
  - **各存一份（不变）**：profile 解析、processor 计划构造（classpath / args / 占位符展开）、`outputs` 幂等（含 Forge 侧 `.jar` 结构降级，见 §2.8）、内嵌 `maven/**` 解包、清单组装、ASM 替换排除 —— 即"**安装办法分开**"的裁决**依然成立**（`common/data/NeoForgeInstaller.ets` 与 `common/data/ForgeNewInstaller.ets` **平行、互不调用**）。
- **允许复用的既有件**（**不属于**「泛化 NeoForge」）：`Downloader` / `runDownloads` / `libraryItem` / `writeText` / `extractArchive` / `copyFromUnzip` / `forgeLibraryRelPath` / `mergeLibsByCoordinate` / `composeForgeManifest`（**本来就是 Forge 侧或通用件**），以及**平台设施** `entryability/NeoInstallAbility.ets` + job 文件协议（它是 **JVM 宿主**、不是安装逻辑；本轮**不重命名**）。

## 2. 逐条改造清单（按依赖排序）

> 每条给「做什么 / 落点（文件+函数/常量名）/ 新增或改造 / 风险 / 验收」。

### 2.1 F0 — Forge 侧独立 processor 编排内核（新文件 `ForgeNewInstaller.ets`）

- **做什么**：在**新文件** `common/data/ForgeNewInstaller.ets` 里**独立实现** Forge 自己的 **processor 计划构造**（读 `install_profile.json` 的 `processors`/`data`、展开占位符、逐条 plan、读工具 `Main-Class`、`outputs` 幂等判定）；**运行**则调 `VersionInstaller.ets` 的**共享载体** `runToolJvmOnce`（**★2026-10-01：载体机理已抽成共享段** —— 逐条起无窗 ability / 结果文件轮询 / 新鲜度基线 / 软超时 / 退避都在那里）。
- **落点**：`entry/src/main/ets/common/data/ForgeNewInstaller.ets`（**新**）；与 `common/data/NeoForgeInstaller.ets` **平行、互不调用**。载体仍走 `entryability/NeoInstallAbility.ets` + job 文件协议（**平台设施**，本轮不重命名）。
- **新增或改造**：**新增**。**不得调用** NeoForge 侧函数（`runNeoForgeProcessors` / `buildNeoForgeProcessorPlans` / `waitProcessorExit` / `resolveMergeModuleEntries` / `composeNeoForgeManifest` 等）；**可参照其逻辑，代码独立**。
- **~~必须独立实现并保留的机制~~（★2026-10-01 已改）**：**退出码权威**、结果文件**新鲜度基线**、**软超时**（`PROCESSOR_SOFT_TIMEOUT_MS` = 120 s）、**`STARTUP_HIDE` 独立进程载体**、**`16000068` 退避重试** —— 这几条属**载体机理**，现由 `VersionInstaller.ets` 的共享段 `runToolJvmOnce` 承担（**不再各存一份**，见 §1 的 2026-10-01 更新）；Forge 侧**独立实现并各存一份**的只剩**计划构造**（profile 解析 / classpath / args / 占位符展开 / `outputs` 幂等）。
- **代价（记录）**：**（★2026-10-01 已收窄）** ~~上述内核两份，将来修一处要修两处~~ —— 收窄为「**数据层 / 安装办法两份**」（载体机理已共享，见 §1）；数据层的重复仍属实（**HMCL 的 zlib 漂移 = 实证**），用户接受以换**风险隔离**（§1）。
- **风险**：与 NeoForge 侧**行为分叉**（fresh-baseline / 退避参数可能不一致）；`label` 与进度文案需自定；job 类型若复用须与 `NeoInstallAbility.ets` 期望的 job 协议一致。
- **验收**：Forge 1.13.2 / 1.16.5 的 processor 链能起 JVM、退出码权威生效（期 2）。

### 2.2 F0b — Forge 侧「新格式安装」骨架（`installForgeNewVersion`）

- **做什么**：在 `VersionInstaller.ets` 新增与 `installNeoForgeVersion` **平行**的 `installForgeNewVersion`，**Forge 自持**步骤 1)–6)（拉 vanilla 清单 → installer 获取/自愈/解包 → vanilla 文件下载 → processor 链（调 `ForgeNewInstaller`）→ 写清单），**并在此骨架上加** G1 / G2 / G3。**不抽公共骨架、不调 NeoForge 骨架**。
- **落点**：`VersionInstaller.ets`（新函数 `installForgeNewVersion`；Forge 自持 `forge-installer/<源>/<版本>` workDir）；类型与计划在 `ForgeNewInstaller.ets`。
- **新增或改造**：**新增**。**入参含** `ctx / gameRootUri / jreId / loaderSource / cacheDir / workDir`；**workDir = Forge 目录**（`FORGE_INSTALLER_DIR`，≠ `neoWorkDir`）。
- **风险**：与 NeoForge 侧骨架**重复实现**（可读性/维护面上升）——这正是方案 B 的**已接受代价**；差异点（老/新形态分流、`maven/` 必需、`mergeModules`、`outputs`）反而因「Forge 自持」而**边界更干净**。
- **验收**：Forge 1.13.2 / 1.16.5 装上（期 2）；NeoForge 侧**不被触碰**（方案 B 隔离 ⇒ 无需回归）。

### 2.3 F1 — 判型新增「可由 processor 链支持」形态

- **做什么**：`classifyForgeProfile` 新增「`spec` + client processor > 0 ⇒ 可由 processor 链支持」的返回值（新常量，暂名 `FORGE_FORM_SPEC_PROCESSOR`），**不再**直接归 `FORGE_FORM_UNSUPPORTED`；`FORGE_FORM_UNSUPPORTED` 语义**收窄为「两键皆无」**。
- **落点**：`VersionInstaller.ets` 的 `classifyForgeProfile` / `forgeClientProcessorCount` / `FORGE_FORM_*` 常量；`installForgeVersion` 的「早拒」分支改写为「分派」（processor 形态 ⇒ 转 `installForgeNewVersion`，见 §2.2）。
- **新增或改造**：新增分支 + 常量。
- **风险（硬约束）**：**拒绝必须仍在写清单之前**（见 §3 不变量 1）；「两键皆无」不能落进 processor 分支，否则计划为空、链路抛 `profile has no client-side processors`，须保持为**明确的形式错误**。
- **验收**：静态判型（真件 1.13.2 / 1.16.5 / 1.17.1 / 1.20.1 → processor 形态；1.12.2 → `spec-no-processor`；坏 profile → 拒绝）。

### 2.4 F2 — Forge 侧 `ForgeInstallProfileJson` 补 processor / data 字段（**自持，不复用 NeoForge 类型**）

- **做什么**：Forge **自持**的 `ForgeProcessorJson` 补 `jar / classpath / args / outputs`；`ForgeInstallProfileJson` 补 `data`（**不复用** `NeoForgeProcessorJson` / `NeoForgeInstallProfileJson`）。
- **落点**：`common/data/ForgeNewInstaller.ets`（Forge 侧类型与计划）。
- **新增或改造**：改造（类型扩展）。**Forge 与 NeoForge 的类型各存一份**（方案 B 代价，§1）。
- **风险**：`data` 不补则 Forge 侧占位符表为空、展开抛 `unresolved placeholder`。Forge 与 NeoForge 的 `data` 键**同义**（真件逐字同构）⇒ **语义可照搬，但声明与展开代码独立**。
- **验收**：占位符展开静态测试（§6）：`'literal'` / `[坐标]` / `/包内路径` / `{KEY}` 四形态。

### 2.5 F3 — `extractArchive` 复用校验扩到「内嵌 `version.json`」

- **做什么**：Forge 自愈解包（`extractArchive`）现只在 `spec-no-processor` 形态下读内嵌启动清单；**新 processor 形态也要读 `profile.json` 指向的内嵌清单**（否则「有 `install_profile.json` 但内嵌清单缺失」的坏缓存能通过自愈、在下游 processor 阶段失败）。校验面可参照 NeoForge 的 `NeoForgeArchive`（**代码独立**，不调用其函数）。
- **落点**：`installForgeVersion` / `installForgeNewVersion` 的 `extractArchive`（把 `FORGE_FORM_SPEC_NO_PROCESSOR` 判定扩为「所有 `spec` 形态」）。
- **新增或改造**：改造。
- **风险**：老形态（`install`+`versionInfo`）清单在 profile 内、无独立文件 ⇒ 该分支**不**读文件（保持现状）。
- **验收**：构造「有 `install_profile.json`、缺内嵌 `version.json`」的坏缓存 ⇒ 判坏并重下。

### 2.6 G1 — 内嵌 `maven/**` 解包（1.13–1.16.5 的**必需项**）

- **做什么**：对 `profile.libraries` 逐条用 `forgeLibraryRelPath` / `mavenPath` 求 rel，命中 `<unzipDir>/maven/<rel>` 即 `copyFromUnzip` 到 `<gameRoot>/libraries/<rel>`。**必须在库下载之前**。
- **为何必需**：1.13–1.16.5 主制品 `net.minecraftforge:forge:<ver>` 与 `:universal` 的 `url` 为空 ⇒ `libraryItem` 会穿透到 `DEFAULT_LIBRARY_URL`（`DownloadContract.ets` = `libraries.minecraft.net`）生成 404；靠「目标已存在即跳过」的语义接住这一步落位。
- **① 代内嵌 `maven/` 组成（2026-09-30 已证实，非推断）**：1.13–1.16.5 恒 **7 条** = 5 目录项 + 主制品 `forge-<ver>.jar` + `forge-<ver>-universal.jar`；**1.16.5 三方 sha1 对照相等**（主制品 `caca08d2…`、`:universal` `fd07fe6c…`）⇒ 主制品与 `:universal` **都来自内嵌 `maven/`**；`-client.jar` = `data.PATCHED_SHA.client`（`427f13ce…`）⇒ 是 **binarypatcher 产物**（不在内嵌 `maven/`）。证据：`stuffs/research/forge-support/install-1.13-1.20.1/A-sample-requirements.md`。
- **落点**：`installForgeVersion` / `installForgeNewVersion`（该逻辑已存在于 `FORGE_FORM_SPEC_NO_PROCESSOR` 分支：`forgeLibraryRelPath` / `copyFromUnzip`；**Forge 侧新骨架（§2.2）里把它变为「所有 `spec` 形态通用」的一步**）。
- **新增或改造**：改造（从 1.12.2 分支提升为通用步）。**仅 Forge 侧**（方案 B：不动 NeoForge）。
- **风险**：rel 必须与 `libraryItem` 落点一致（`forgeLibraryRelPath` 优先 `downloads.artifact.path`，否则 `mavenPath(name)`）。
- **验收**：1.13.2 / 1.16.5 装后 `<gameRoot>/libraries/net/minecraftforge/forge/<ver>/` 有主制品与 `-universal`。

### 2.7 G2 — `mergeModules` 接入 Forge（**Forge 侧自解析，不调 NeoForge**）

- **做什么**：安装期解析 `arguments.jvm` 的 `-DmergeModules=` 文件名清单，`declaredNames` = **vanilla + profile + launch 三处库名**，把缺件补到 maven 树（`files.push(newItem(...))`）。
- **不许复用**：**不得调用** NeoForge 的 `resolveMergeModuleEntries`（及 `libraryNames` / `stringArgs`）——Forge 侧**独立实现**该解析（**可参照其逻辑，代码独立**）。
- **基址问题（必看）**：现补库 URL 硬编码 `NEOFORGE_RELEASES`（`DownloadContract.ets` = `maven.neoforged.net/releases/`），**对 Forge 语义错**（例：`jna` 的 group = `net.java.dev.jna`，物理件在 `libraries.minecraft.net`，**既不在 NeoForged、也不在 Forge maven**）⇒ **Forge 侧须换基址**（按声明库的仓库，或对 `jna` 用 `MOJANG_LIBRARIES`）**或按需跳过**。另注意 1.17.1 真件点名 `jna-platform-58.0.jar`（疑似 `5.8.0` 的拼写 typo）会切成 version `58.0` ⇒ 路径错。
- **落点**：`common/data/ForgeNewInstaller.ets`（Forge 侧解析器）+ `VersionInstaller.ets` 的 `installForgeNewVersion`（merge 段）。
- **新增或改造**：**新增**（Forge 侧独立解析器 + 基址参数化）。
- **风险 / 缓释**：**不要当阻塞**——启动侧对 `-DmergeModules` 点名缺件已按 warn 处理，1.20.1 实测可启动（反证：`stuffs/test-higher-forge/libraries` 里无 `jna-5.10.0.jar` 仍进过世界）；基址错会下 404（无害但噪声）。
- **验收**：1.17.1 / 1.20.1 装后 `libraries/` 出现点名 jar（基址修好后）；否则至少日志 warn、不阻塞。

### 2.8 G3 — `outputs` 幂等

- **做什么**：`outputs` 形态是**对象**（`{路径: sha1}`，**不是数组**）。实现：① 展开 key/value 字面量；② 逐项比 sha1；③ **全命中且非空 ⇒ 整条 processor 跳过**；④ 执行后不符 ⇒ **先删产物再抛**。
- **落点**：`common/data/ForgeNewInstaller.ets`（Forge 侧 plan 增加展开后的 outputs）+ `VersionInstaller.ets` 的 `installForgeNewVersion` / Forge 侧运行内核（跳过/校验）。**仅 Forge 侧**（方案 B：不为 NeoForge 顺带实现）。
- **新增或改造**：新增（此前只有 `PATCHED` **存在性**断言）。
- **决策**：**不做 zlib 降级**——HMCL 的降级只在一侧（ForgeNew 有、NeoForgeOld 无）、其 `IS_ZLIB_COMPATIBLE` 判据不可移植、且会掩盖真实错误。
  > **更正（2026-10-01，用户裁决）：改按 HMCL 对齐，做 `.jar` 的 ZIP 结构降级。** 判据 = sha1 为主，**仅 `.jar`** 不符时退化为「ZIP 结构可读 + 条目完整」（不伪造 sha1，打稳定英文 warn；非 `.jar` 仍硬失败、先删再抛），落点 `ForgeNewInstaller.ets` 的 `forgeOutputsAllMatch` / `forgeVerifyOutputsOrThrow`。理由：processor **动态生成**的 jar（`jarsplitter` 的 `MC_SLIM`/`MC_EXTRA`、`binarypatcher` 的 `PATCHED`）在 deflate 实现与官方参考 zlib 不同的沙箱里 sha1 **必然**不符 ⇒ 不做降级安装**必然失败**；HMCL Forge 侧正是这么处理（`ForgeNewInstallTask.ProcessorTask.execute()` 的 `!ZlibUtils.IS_ZLIB_COMPATIBLE && ext=="jar"` → `ZIP_INTEGRITY_CHECK_HANDLER.checkIntegrity`），**NeoForge 侧没有**该降级 ⇒ 这正是"两链分开实现"的好处之一。原"不做降级"的决策**保留为记录**（其顾虑——判据不可移植、可能掩盖真实错误——由"仅 `.jar` + 全量解压校验"收窄）。
- **风险**：若实机发现沙箱 deflate 导致 `PATCHED_SHA` **必然**不符，再单独决策（见 §4 P2、§7 未决）。
- **验收**：重入幂等测试（第二次安装命中 outputs ⇒ 跳过；改坏产物 ⇒ 重跑）。

### 2.9 S1–S3 — 签名扩参（对齐 NeoForge）

- **做什么**：`installForgeVersion` / `InstallerState.installForge` / `GameVersionsView.installForgeRemote` 都补 `ctx / gameRootUri / jreId`（与 `installNeoForgeVersion` / `installNeoForge` / `installNeoForgeRemote` 对齐）。
- **落点**：`entry/src/main/ets/common/data/VersionInstaller.ets`、`entry/src/main/ets/common/state/InstallerState.ets`、`entry/src/main/ets/components/GameVersionsView.ets`。
- **新增或改造**：改造。
- **风险**：三处调用点必须同步（编译期暴露）；`≤1.12.2` 零 JVM 分支要能收下这组参数（可为空/忽略）。
- **验收**：编译通过 + 零 JVM 分支行为不变。

### 2.10 S4 — UI 前置：JRE 就绪门扩到 Forge ≥1.13

- **做什么**：`confirmInstall` 的 JRE 就绪门从「仅 NeoForge」扩到「Forge **且 MC ≥1.13**」；**≤1.12.2 零 JVM 分支保持无前置**。
- **判据**：用**版本比较**（不写死字符串）；JRE 解析仍走 `JavaPolicy.resolveJavaRuntime`（**工具 JVM 与启动 JVM 同源**这条不变量不许破）。
- **落点**：`GameVersionsView.ets` 的 `confirmInstall`（现仅 `kind === LOADER_KIND_NEO_FORGE` 分支）；`JavaPolicy.ets` 的 `requirementFor`（Forge 分段已实现：≤1.12.2 上限 8 / 1.13–1.16.999 偏好 8 上限 17 / 1.17–1.20.4 min16 偏好 17）。
- **新增或改造**：改造。
- **风险**：判据写死会与 `FORGE_MAX_MC` 分家 ⇒ 统一到一处比较函数；1.13–1.16 段「偏好 8」在只有现代套的设备上会兜底到现代套（§4 P1）。
- **验收**：Forge 1.16.5 未装 Java 8 时弹「启动同款」对话框并保留面板；Forge 1.12.2 不弹。

### 2.11 U1 — UI 门控（**本轮不做设备门**）

- **做什么**：① `FORGE_MAX_MC` 放到 `1.20.1`；② **本轮不加设备门**——设备门被**有意推迟**（2026-09-30 用户裁决：**先聚焦 2in1，phone 装不了不管他**）。
- **落点**：`GameVersionsView.ets` 的 `FORGE_MIN_MC` / `FORGE_MAX_MC` / `forgeSupported` / `setLoaderKind`。
- **新增或改造**：改造（只放开上界，**不新增设备门分支**）。
- **已知且有意接受**：phone 上 1.13+ 会失败（无独立进程载体——静态 `process:":neoinstall"` 在 phone 被忽略 ⇒ 工具 JVM 返回后 `_exit` 带走 App），**本轮不处理**；载体机制见 [`安装期JVM载体-调研.md`](安装期JVM载体-调研.md) §10。
- **验收**：2in1 上 1.13–1.20.1 可选并装成；phone 行为**不承诺**（已知会失败/可能退出 App）。

### 2.12 U2 — 文案资源化

- **做什么**：`loader_forge_unsupported` 现值含「1.13 及以上需要 JVM」（对「新范围」**已过期**）⇒ 改写为「超上界（≥1.20.2）」语义即可；**不再需要「设备不支持（phone）」文案**（本轮不做设备门，§2.11）。
- **落点**：`entry/src/main/resources/base/element/string.json`（`loader_forge_unsupported`；若有其它语言资源一并改）。
- **新增或改造**：改造（**简化**，不再分「设备不支持」档）。
- **验收**：两种状态（<1.7 超下界 / ≥1.20.2 超上界）各有独立、可操作的文案。

### 2.13 U3 — Forge 版本列表后端

- **做什么**：**无需改**。`fetchForgeVersions` 已按 `mcVersion` 查、与 loader 版本无关（`forgeVersionsOfMavenMetadata` / `hasForgeInstaller`）。
- **落点**：`VersionInstaller.ets` 的 `fetchForgeVersions`。
- **验收**：1.13–1.20.1 各拉一次列表成功（真件驱动即可）。

### 2.14 X1 — 额外（HMCL 有而我们缺）

- **(a) 安装时校验 `install_profile.minecraft == 目标 MC`**：HMCL 抛 `VersionMismatchException`；我们 `ForgeInstallSectionJson.minecraft` 已声明但未用。评估：加一致性校验（低风险、可诊断）。
- **(b) HMCL 的 `net.minecraftforge:forge` → 强制 classifier `universal`**：评估我们是否需要。**初步结论**：我们靠 `maven/` 解包 + 清单路径，**大概率不需要**强指 classifier；但需真件核对 `profile.libraries` 里主制品的 classifier 写法后再定案（见 §7 未决）。

## 3. 必须保住的不变量（逐条 + 落点）

| 不变量 | 落点（文件 + 函数/常量名） |
|---|---|
| **写清单前拒绝**（不留「能列出但起不来」的残缺实例） | `VersionInstaller.ets` `classifyForgeProfile` / `installForgeVersion`（拒绝分支在 `writeText` 之前） |
| 安装期只写 `versions/**` + `libraries/**`（不把我们的状态写进游戏目录） | `installForgeVersion` / `composeForgeManifest` / `writeText` |
| 每 loader 独立下载源（`forgeSource` / `neoForgeSource`） | `InstallerState.ets` `forgeSource` / `neoForgeSource`；`VersionInstaller.ets` 传 `loaderSource` |
| installer 缓存**自愈**（复用前先解） | `installForgeVersion` 的 `extractArchive` + `downloadInstaller`（走 `downloadFile` 原语以保官方兜底） |
| `{MINECRAFT_JAR}` 用**独立 temp 副本**（工具会就地改写） | `installNeoForgeVersion` / `installForgeNewVersion` 的 `mcJarForTools`（`workDir/mc.jar`） |
| workDir 按「源 / 版本」隔离且 **Forge ≠ NeoForge 目录** | `neoWorkDir` / `installForgeNewVersion` 的 workDir 构造（`FORGE_INSTALLER_DIR`） |
| **产物断言优先于退出码**（工具 fail-open） | Forge 侧运行内核调用方（`ForgeNewInstaller.ets`）；`patchedPath` 存在性 + G3 `outputs` sha1 |
| 失败只清「半装实例」 | `InstallerState.ets` `installForge` / `removeIncompleteInstance` |
| **HMCL 双向兼容**：顶层扁平 + `patches[]` priority `0`/`30000`、`<id>.jar` = vanilla 复制件、同坐标**高优先胜出**、不写 `launcher_profiles.json` | `composeForgeManifest` / `mergeLibsByCoordinate` / `libraryMergeKey` |
| **工具 JVM 与启动 JVM 同源**（同一处 `JavaPolicy` 解析） | `GameVersionsView.ets` `confirmInstall` → `JavaPolicy.resolveJavaRuntime` → job `jreId` → `NeoInstallAbility` |
| `composeForgeManifest` **不把 forge 模板的 `javaVersion` 写进 patch** | `composeForgeManifest` 的 `forgePatch`（只取 `mainClass`/`arguments`/`libraries` 等；`javaVersion` 留在 vanilla 顶层与 `gamePatch`） |

## 4. 风险与缓解（按优先级；附「能否静态定案」）

| 级别 | 风险 | 缓解 | 能否静态定案 |
|---|---|---|---|
| **P0** | **phone 无独立进程载体** ⇒ 工具 JVM 返回后 `_exit` 带走 App | **本轮有意接受**（2026-09-30 用户裁决：**先聚焦 2in1，phone 装不了不管他**）；设备门**有意推迟**（U1 不再做门） | **可**（源码 + 平台契约） |
| **P0** | `DOWNLOAD_MOJMAPS` 硬编码 `launchermeta.mojang.com`、**不可镜像**、只命中 1.17.1–1.20.1 | 仿 HMCL 特判为「**可镜像纯下载、不起 JVM**」（走 provider 候选 URL）；并把工具 **stdout 落盘** / `label` 带 task 名，否则 `processor failed (installertools) exit=N` 分不清 3 个子任务 | 部分：硬编码**可**静态定案；设备网络可用性需上机 |
| **P1** | **① 代工具能否在 Java 8 legacy 套上跑通**（工具字节码 Java 8 级，但可能踩 `Pack200` / `SecurityManager` 被删） | 上机实测（工具链上从未测过）；失败则改走现代套或记录边界 | 否（需上机） |
| **P1** | **② 代工具在 26 上**（1.17.1 / 1.18.2 的老 `securejarhandler` 未试） | 上机实测 1.17.1 / 1.18.2 / 1.20.1（1.20.1 走 `bootstraplauncher 1.1.2` 已有正证据） | 否（需上机） |
| **P1** | **G1 是 1.13–1.16.5 必需项**（缺则主制品/`:universal` 必 404） | 期 2 必须落地并上机验收落位 | 否（需上机） |
| **P1** | **G2 补库基址**（现硬编码 `NEOFORGE_RELEASES`） | Forge 侧**自解析** mergeModules 并换基址（`jna` group 在 `libraries.minecraft.net`）；不阻塞（启动侧已 warn） | **可**（源码） |
| **P2** | **方案 B 的代价**：processor 编排内核**两份**（Forge `ForgeNewInstaller.ets` / NeoForge `NeoForgeInstaller.ets`），将来修一处要修两处 | 用户**接受**以换**风险隔离**（§1）；两侧注释/文档标注「平行实现、勿互调」 | **可**（结构事实） |
| **P2** | `outputs` 幂等缺失 ⇒ **陈旧产物被复用** | G3（对象形态展开 + sha1 比对 + 先删再抛） | 部分（判据可静态写；沙箱 deflate 行为需上机） |
| **P2** | 与 HMCL 共存时「存在即跳过」+ 多数件不复验 sha1 ⇒ **坏库被永久复用** | 采纳 HMCL 的「异常退出留标记 ⇒ 下次补坏件」思路（可选增强，非本方案阻塞） | 部分 |
| **P2** | `copyFromUnzip` 落库路径**未消毒**（低危） | 校验 rel 不含 `..` / 绝对路径 | **可** |
| **P2** | installer jar **无强校验**（只有结构可解 + 自愈） | 现状保留（官方元数据无 sha1）；镜像源 BMCL `files[].hash` 可增 sha1（更强，另排期） | 部分 |
| **P3** | 安装期退后台被**冻结**（多 processor 长跑） | 保活/冻结兜底见 [`安装期JVM载体-调研.md`](安装期JVM载体-调研.md) §5 | 否 |
| **P3** | 工具 JVM **无 `-Xmx`**（remapper OOM 可能） | 评估给 `job.argv` 注入内存上限 | 部分 |
| **P3** | `CacheCleaner` 不覆盖共享 `libraries/` 的中间件（如 `PATCHED`） | 与 G3 一起考虑；登记为增强 | 部分 |

### 4.1 已踩坑与故障诊断：工具 JVM 缺平台伪装（2026-09-30 定案）

- **症状**：应用内装 Forge 1.16.5，**第一个** client processor 起工具 JVM 后约 **500 ms 退 1**；工具 stderr = `Error: A JNI error has occurred…` 且 `java.lang.AssertionError: Platform not recognized`（栈顶 `sun.nio.fs.DefaultFileSystemProvider.create` → `java.io.FilePermission.<clinit>` → … → `sun.launcher.LauncherHelper.checkAndLoadMain`）。
- **根因**：**工具 JVM 的 argv 漏了平台伪装**。JDK 8 的 `DefaultFileSystemProvider.create()` 按 `os.name` **精确匹配**（`Linux` / `SunOS` / `Darwin` / …），而本机真 `os.name` 不是 `Linux` ⇒ 在**类初始化期**硬 `AssertionError` ⇒ `LauncherHelper.checkAndLoadMain` 连主类都加载不到 ⇒ 退 1。**游戏路径本来就带**这两条 `-D`（`MinecraftLauncher.buildLaunchArgv` 用 `LaunchDefaults` 的 `SPOOF_OS_NAME` / `SPOOF_OS_VERSION`）；**工具 JVM 的 argv 两个 loader 都漏了**（Forge / NeoForge 各一份）。
- **判别要点**（为什么"游戏能跑、NeoForge 工具能跑、偏偏 Forge ① 代工具炸"）：三条互不干扰的轴 ——
  - **进程 / 载体**：游戏走 `:game`、安装工具走 `:neoinstall`，二者都能起（说明载体与进程本身没问题）⇒ 故障只可能落在**这一次的 argv / 这一套 JRE**；
  - **JRE 套**：Forge ① 代（1.13–1.16.5）工具落在 **Java 8 legacy 套**（§2.10 / §4 P1），legacy 对未知 `os.name` **零容忍**；现代套（26）对未知 `os.name` **宽容回退**到 `UnixFileSystemProvider` ⇒ 同一条链在 26 上此前从未暴露；
  - **主类加载**：异常发生在 class init（`FilePermission.<clinit>`，由 `AppClassLoader.getPermissions` 触发）⇒ **连 `main` 都没进** ⇒ 表现为"工具没跑任何逻辑就退 1"，而非工具自身抛错。
- **修法**：**两处 loader 的工具 job argv 都补** `-Dos.name` / `-Dos.version`，**复用** `LaunchDefaults.ets` 的常量并收敛为前缀数组 `TOOL_JVM_PLATFORM_SPOOF_ARGS`（紧随 `java`、排在其余 `-D` 之前；Forge = `runForgeProcessors`，NeoForge = `runNeoForgeProcessors`）。**Forge 1.16.5 实机通过（2026-09-30）**：应用内安装 + 启动均正常（用户确认）。
- **可复用排查结论**：本仓**任何"另起 JVM"的路径**（安装期工具 JVM / 各子进程 / 将来的其它载体）**都必须带上与游戏同源的平台伪装** —— 只要链路上可能落到 legacy（Java 8）套，缺它就必炸；在 26 上不炸只是"宽容回退"的运气，**不可依赖**。

## 5. 分期路线（每期含「做完什么就算完成」判据 + 上机验证项）

### 期 1 — Forge 侧独立编排内核（F0）

- **完成判据**：`ForgeNewInstaller.ets` 落地（计划构造 + 运行内核，**独立实现、不调 NeoForge 侧**）；机制齐备（退出码权威 / 新鲜度基线 / 软超时 120 s / `STARTUP_HIDE` 载体 / `16000068` 退避）。**（★2026-10-01：后四项已是共享载体 `runToolJvmOnce` 的既有能力，不再是 Forge 侧单独交付项；Forge 侧真正要独立交付的是计划构造 + `outputs` 幂等。）**
- **验证项**：NeoForge 侧**不被触碰**（方案 B 隔离 ⇒ 无需回归）；Forge 侧内核用真件做静态演练（§6）。

### 期 2 — Forge 侧骨架（F0b）+ G1 + G3 + F1/F2/F3（先让 1.13–1.16.5 装上、能启动）

- **完成判据**：`installForgeNewVersion` 骨架落地（**Forge 自持，不抽公共骨架**）；F1 判型放行 processor 形态；F2 Forge 侧类型补全；F3 自愈面扩到内嵌清单；G1 主制品/`:universal` 落位；G3 `outputs` 幂等。
- **上机验证项**：Forge **1.13.2 / 1.16.5** 装上（库落位正确）并能启动（① 代真树 classpath + Java 8）。

### 期 3 — ② 代（1.17.1 / 1.18.2 / 1.20.1）+ `DOWNLOAD_MOJMAPS` 特判 + G2

- **完成判据**：② 代装上；`DOWNLOAD_MOJMAPS` 走可镜像纯下载；`mergeModules` 补库基址修正。
- **上机验证项**：Forge **1.17.1 / 1.18.2 / 1.20.1** 装上并启动（真树 cp + `-p` + `-DmergeModules`）。

### 期 4 — UI（U1 放开上界 + U2 文案 + S4 前置）与收尾（校验、清理、诊断）

- **完成判据**：`FORGE_MAX_MC` = 1.20.1（**不加设备门**）；文案分档（下界/上界两种）；JRE 就绪门覆盖 Forge ≥1.13；X1 一致性校验；诊断（工具 stdout 落盘 / label 带 task 名）。
- **上机验证项**：2in1 上 1.13–1.20.1 可选并装成；phone **不承诺**（已知会失败/可能退出 App，**有意接受**）。

## 6. 测试计划

**静态（真件驱动离线演练）**：判型（`classifyForgeProfile` 逐份真件）/ 占位符展开（**Forge 侧展开函数**，四形态）/ `outputs` 判据（对象展开 + sha1）/ 清单产物断言（`composeForgeManifest` 顶层扁平 + `patches[]` + 同坐标合并）。

**上机**：
- **版本矩阵**：① 代 1.13.2 / 1.16.5；② 代 1.17.1 / 1.18.2 / 1.20.1（各含「装上」与「能启动」两个读数）。
- **看哪些日志与文件**：`processor <label> handshake returned code=N`（退出码权威）/ 软超时诊断行 / `<gameRoot>/libraries/net/minecraftforge/forge/<ver>/`（主制品 + `-universal` + `:client` 产物）/ 实例 `<id>.json`（`patches[]` 与 priority）。
- **重入幂等**：同一 (mc, loader) 连装两次（第二次应命中 `outputs`/`PATCHED` 跳过）；改坏一个产物后再装（应重跑并修正）。

## 7. 未决清单（如实写，非结论）

> 原第 1 / 2 条（`1.14` / `1.15` 与 `1.20.2–1.20.4` 取样、`1.13–1.16.5` 内嵌 `maven/` 条目名）已由 **2026-09-30 取证收口**：世代边界见 §0.1 / §0.2；内嵌 `maven/` 组成见 §2.6。

1. **`jna-5.10.0` 是否真需要补**（`mergeModules` 点名，但运行期是否真用未证）。
2. **`zlib.decompressFile` 是否拦路径穿越**（G1 的 rel 与 installer 内条目名都进过它）。
3. **1.20.1 的 `:client` 产物在启动期由谁消费**。
4. **工具在随包 JRE 上的可跑性**（① 代的 Java 8 legacy 套与 ② 代的 26，两档都未实测）。
5. **X1(b)**：主制品是否需强制 classifier `universal`（待真件核对 `profile.libraries` 写法）。

## 8. 指针

- 上游机制与分期：[`Forge-1.13及以上-调研与方案.md`](../20-design/launch/Forge-1.13及以上-调研与方案.md)（§1 四世代 / §2 安装侧三缺口 / §5 分期）。
- classpath 形态决策：[`classpath形态-真树与平铺-决策情报.md`](classpath形态-真树与平铺-决策情报.md)。
- HMCL 安装链逐行取证：[`NeoForge安装链-逐行取证.md`](../20-design/launch/NeoForge安装链-逐行取证.md)。
- 安装期载体：[`安装期JVM载体-调研.md`](安装期JVM载体-调研.md)（§8.3 / §10）。
- 多 JRE：[`多JRE共存-方案.md`](多JRE共存-方案.md)。
- 未决/受限登记：[`../../00-current/已知限制与待解.md`](../00-current/已知限制与待解.md)（C13 / C14）。
- **取证来源审计（下载 URL / 下载日期 / 官方 sha1 / 实测 sha256 / 落盘 / 是否随包）**：[`../../30-supply-chain/provenance-master.md`](../30-supply-chain/provenance-master.md) §4.2（覆盖随包 ASM 9.9.1 ×5、重建的 `meowcraft_extras.tar.gz`、以及本方案取证的 6 份 Forge installer）。
- **平行调研（2026-09-30 四份均已落盘）**：工作区根 `stuffs/research/forge-support/install-1.13-1.20.1/` 下四件（逐件指名）：
  - 需求取样（逐版本真件 + 世代切点 + ① 代内嵌 `maven/` 已证实）：`stuffs/research/forge-support/install-1.13-1.20.1/A-sample-requirements.md`
  - 我方代码缺口：`stuffs/research/forge-support/install-1.13-1.20.1/B-our-code-gaps.md`
  - HMCL 对照：`stuffs/research/forge-support/install-1.13-1.20.1/C-hmcl-reference.md`
  - 风险与环境：`stuffs/research/forge-support/install-1.13-1.20.1/D-risks-and-env.md`
