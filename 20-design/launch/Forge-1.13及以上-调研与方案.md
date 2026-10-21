# Forge 1.13 及以上（新格式安装器世代）支持 — 调研与方案

> **本文是带日期的调研记录（2026-09-30），不是活状态。** 支持面现状以
> [`../../00-current/版本支持边界.md`](../../00-current/版本支持边界.md) 与
> [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 28 条为准。
> 上游与前置：[`Forge支持-调研.md`](Forge支持-调研.md) · [`Forge支持-改动方案.md`](../../90-archive/Forge支持-改动方案.md)（§6 逐条改造清单、§8 代际矩阵）
> · [`NeoForge支持-改动方案.md`](../../90-archive/NeoForge支持-改动方案.md) · [`NeoForge安装链-逐行取证.md`](NeoForge安装链-逐行取证.md)
> · [`安装期JVM载体-调研.md`](../../90-archive/安装期JVM载体-调研.md) · [`多JRE共存-方案.md`](../../90-archive/多JRE共存-方案.md)。
> · **classpath 形态（真树 vs 平铺）的系统决策情报**见 [`classpath形态-真树与平铺-决策情报.md`](../../90-archive/classpath形态-真树与平铺-决策情报.md)（本文 §5.2/§5.3/§5.5 的零散结论在其中收拢）。
> · **四大类型（原版/Forge/NeoForge/Fabric）× 逐世代的启动总览**见 [`启动链-总览.md`](启动链-总览.md)（本文 §1 的四世代机制在该总览里与其它加载器并列成表）。
> **真件取证**：`stuffs/research/forge-support/evidence/**`（11 份 installer 开箱，T0 轮；汇总见同目录的 T0-findings.md 与 T0-summary.md）。
> 行号基准：`Harmomeow-Craft-Launcher/` HEAD = `8e46d50`。

## 0. 边界修正（两处前提先纠正）

### 0.1 真边界是 1.13，不是 1.12

Forge for MC **≤1.12.2** 的**安装与运行均已支持**（用户实机确认：1.7.10、1.12.2 可玩，含 OptiFine 组合）。
Forge 从 **1.13 起**换成"新格式安装器"（`install_profile.json` 带 `spec` + `processors`），**安装期必须跑 JVM**。
因此本主题 = **Forge for MC ≥1.13**。

现在有**两道互相独立的闸门**把 1.13+ 挡在外面：

| # | 闸门 | 位置 | 行为 |
|---|---|---|---|
| A | UI 层 | `entry/src/main/ets/components/GameVersionsView.ets:55-56`（`FORGE_MIN_MC='1.7'` / `FORGE_MAX_MC='1.12.2'`）、`:748-751` `forgeSupported()`、`:765-767` 不拉列表、`:922-924` 禁用按钮、`:1672-1676` 文案 `loader_forge_unsupported` | 1.13+ 连 Forge 版本列表都不拉 |
| B | 数据层（硬判据） | `entry/src/main/ets/common/data/VersionInstaller.ets:1721-1729` `classifyForgeProfile()` | `spec` 存在 **且 client 侧 processor 数 > 0** ⇒ 返回 `FORGE_FORM_UNSUPPORTED`；拒绝动作 `:2013-2022`（`hilog.error` + `throw new Error('forge install unsupported (needs a JVM): …')`），发生在写清单（`:2132-2135`）**之前** |

> **★更正（2026-10-01）：上表两道闸门均已拆除。** 闸门 A（UI 门控 `FORGE_MAX_MC`）已放开到 **1.20.1**；闸门 B（数据层拒绝）已按 processor 链放行 **1.13–1.20.1** —— 应用内安装 Forge 现支持 **1.7–1.20.1**（见 [`Forge-1.13至1.20.1-安装实施方案.md`](../../90-archive/Forge-1.13至1.20.1-安装实施方案.md)）。下表 / 下文凡"把 1.13+ 挡在外面"均为**该文撰写时（2026-09-30）**的记录。

**判据澄清（重要）**：区分新老形态的是**有无 `spec`**（`Forge支持-调研.md` 的口径），但决定**要不要 JVM** 的是 **client 侧 processor 数**，不是 `spec` 本身——
`spec` 只是"新形态"的形态标签。1.12.2 正是反例：它 `spec:0` 却是 **`processors: []`**，所以才是零 JVM 的那一例。
`spec` 值与该世代的主制品形态无关（1.13.2/1.16.5 是 `spec:0` 但**有 4–5 个 processor**）。MC 版本号**完全不参与**判型（`ForgeInstallProfileJson` 无 `minecraft` 字段，`VersionInstaller.ets:1519-1533`）。

### 0.2 一处流行误解：NeoForge 链并**没有**内嵌 `maven/` 解包

"NeoForge 链路已实现内嵌 `maven/` 解包"**不成立**。全仓 `/maven` 命中只有 Forge 1.12.2 分支那两处（`VersionInstaller.ets:2054-2071`，注释依据 `:2041-2042`）。
NeoForge 真件的 profile/version.json 里没有空 `url` 项（实测 0 命中），所以它**不需要**这一步；而 **1.13–1.16.5 的 Forge 需要**（见 §2.3 缺口 1）。这条误解会直接影响改造面估算。

### 0.3 与判型相邻的既有约束（改造会撞上）

- `installForgeVersion` 签名**不含** `ctx` / `gameRootUri` / `jreId`（`:1912-1917`）；`installNeoForgeVersion` **含**（`:1057-1063`）⇒ 想复用 processor 链必须扩签名。
- `InstallerState` 把"仅 1.7–1.12.2"写进了注释契约（`state/InstallerState.ets:18-21`、`:523-528`；`installForge()` 不含 `ctx/gameRootUri/jreId`，`:529-565`）。
- UI 的"工具 JVM JRE 就绪前置"**只在 NeoForge 分支**（`GameVersionsView.ets:998-1008`）⇒ Forge ≥1.13 需要同款前置。
- **资产**：`JavaPolicy.requirementFor` 已为 Forge 分段完整实现（`data/JavaPolicy.ets:112-127`）：≤1.12.2 强制 ≤8；1.13–1.16.999 `min 0 / max 17 / prefer 8`；1.17–1.20.4 `min 16 / prefer 17`；≥1.20.5 `min 21`。但这条在环境侧有陷阱，见 §4.1。

## 1. 四世代机制（11 份真件实证）

| 世代 | MC 段 | mainClass | module path `-p` | `-DignoreList` / `-DmergeModules` | `arguments.jvm` | 安装 `spec` | 内嵌 `maven/` |
|---|---|---|---|---|---|---|---|
| legacy | ≤1.12.2 | `net.minecraft.launchwrapper.Launch` | 无 | 无 | 无（走 `minecraftArguments` + `--tweakClass`） | `0` + 空 processors | 有（已实现） |
| ① | **1.13–1.16.5** | `cpw.mods.modlauncher.Launcher` | **无** | **无** | 1.13.2 **完全缺失**；1.16.5 仅 4 条（`-XX:+IgnoreUnrecognizedVMOptions` + 2×`--add-exports` + 1×`--add-opens`） | `0`（但 **processors 非空**） | **7 条（主制品必需）** |
| ② | **1.17.1–1.20.1** | `cpw.mods.bootstraplauncher.BootstrapLauncher` | **有**（7–8 jar：bootstraplauncher + securejarhandler + asm×5 + JarJarFileSystems） | **都有** | `-DignoreList=…`、`-DmergeModules=jna-…`、`-DlibraryDirectory=…`、`--add-modules ALL-MODULE-PATH`、4×`--add-opens`/`--add-exports`；1.20.1 另有两级 `-Dfml.*LayerLibraries` | `1`，`path: null` | 0 条（1.20.1 为 24 条） |
| ③ | **1.20.6 / 1.21.1 / 26.3** | `net.minecraftforge.bootstrap.ForgeBootstrap` | **无** | **无** | 极少（1.20.6/1.21.1 仅 `-Djava.net.preferIPv6Addresses=system`；26.3 另加 `-XX:+UseCompactObjectHeaders`、`-XX:StackShadowPages=32`） | `1` + `hideExtract` + `serverJarPath`，`path` 带 `:shim` | 2 条 |

世代切点：**1.13**（LWJGL2→3 与安装器格式）、**1.17**（引入 module path）、**1.20.6**（module path 责任收回加载器）。

要点：
- **全部世代都是薄 `inheritsFrom`**（`inheritsFrom = <MC 版本>`），`arguments.jvm` / `arguments.game` 由 **installer 内嵌的 `version.json`** 承载，由 `install_profile.json` 的 `"json": "/version.json"` 指明 ⇒ **启动器不需要自己拼 game 参数**（世代 ② 的 `-p` / `-DignoreList` 也都是 installer 写好的）。
- Forge 自己的 `version.json` **不含 `natives` / `classifiers` / `extract`**（全量 0 命中）⇒ natives 完全由 vanilla 父版本承担。
- 全部世代 **不需要 `--installClient`**、**不需要 `launcher_profiles.json`**（我们走 HMCL 式自研安装，installer 只作数据容器；`Forge支持-改动方案.md` §4.5 已裁定）。
- `processors` 字段名（`sides`/`jar`/`classpath`/`args`/`outputs`）与 NeoForge **逐字一致**；`installertools` 版本各代漂移（1.0.3 / 1.3.0 / 1.2.7 / 1.4.3 / 1.4.6）与我们无关——我们只做"args 原样来自 profile + 占位符替换"。
- **`outputs` 在 Forge 世代普遍存在**（1.13.2 / 1.16.5 / 1.17.1 / 1.20.6 都有）——`NeoForge支持-调研.md` §8.4 的"现代 profile 没有 `outputs`"**只对 NeoForge 1.20.2+ 成立，不可外推**。

## 2. 安装侧

### 2.1 NeoForge 链的能力清单与可复用性

链路：编排 `VersionInstaller.ets`（`installNeoForgeVersion` `:1057-1250`、`runNeoForgeProcessors` `:1262-1338`、`waitProcessorExit` `:1396-1496`）+ 数据层 `NeoForgeInstaller.ets` + 载体 `entryability/NeoInstallAbility.ets`。

| 分类 | 项 |
|---|---|
| **可直接复用于 Forge ≥1.13**（11 项） | ① installer 获取与缓存（`<cache>/neo-installer/<源>/<版本>/`，镜像优先 + 官方兜底，`VersionInstaller.ets:948-958`、`:1083-1095`；Forge 已有对偶件 `forgeInstallerCandidates` `:182-185`）② 缓存自愈（复用前先解一次，`:1112-1141`）③ processor 执行语义（只跑 client 侧、按序、串行、每 processor 独立进程 + 独立 JVM，`:1262-1338` + `NeoForgeInstaller.ets:280-311`）④ `:neoinstall` 无窗载体（job 文件 + 退出码轮询 + `16000068` 退避 + 等进程消失，`NeoInstallAbility.ets:26-79`、`VersionInstaller.ets:1285-1496`）⑤ `data` 变量表与占位符展开（`'literal'` / `[坐标]` / `/…` 路径 / 内建 `SIDE`·`MINECRAFT_JAR`·`MINECRAFT_VERSION`·`ROOT`·`INSTALLER`·`LIBRARY_DIR`，`NeoForgeInstaller.ets:146-171`、`:246-278`）⑥ 从工具 jar 读 `Main-Class`（`:177-238`）⑦ 失败清理（`InstallerState.ets:452`/`:568`、`CacheCleaner.ets:84-85`）⑧ 产物断言优先于退出码（`PATCHED` 存在 = 成功硬判据，`:1242-1244`）⑨ 实例清单组装（`composeForgeManifest` `:1825-1876` 已存在）⑩ 不跑 installer 主类、无入口参数 ⑪ `-Djava.io.tmpdir` 指向可写沙箱（`:1279-1281`） |
| **需按世代适配**（4 项） | ① profile 结构体（NeoForge 用 `NeoForgeInstaller.ets:38-48`；`ForgeInstallProfileJson` `:1519-1533` 的 `processors` **只声明了 `sides`**，缺 `jar/classpath/args/outputs`）② libraries 下载与校验（三处硬伤见 §2.3）③ `-DmergeModules` 按名补库（仅在 `installNeoForgeVersion` 内调用，`:1180-1202` + `NeoForgeInstaller.ets:318-404`；Forge 1.17+ 需要）④ `outputs` 幂等预检（此前未实现） |
| **NeoForge 特有 / 缺失**（3 项） | ① 不读 `spec`（NeoForge 无此概念）② **不做内嵌 `maven/` 解包**（见 §0.2）③ 不特判 `DOWNLOAD_MOJMAPS`（照原样当 processor 跑） |

### 2.2 HMCL 对照：它**没有**把 Forge/NeoForge 合并

HMCL 是"同一条语义、两份几乎逐字重复的实现"：`forge/ForgeNewInstallTask.java` 与 `neoforge/NeoForgeOldInstallTask.java` 的 ProcessorTask / replaceTokens / parseLiteral / patchDownloadMojangMappingsTask / preExecute / execute 逐字重复，只有类名、patch id、temp 前缀、报错文案不同。

**而重复已经产生漂移**：ForgeNew 有 **zlib 降级**（`.jar` 输出 sha1 不符时降级为 ZIP 结构校验，`ForgeNewInstallTask.java:165-184`），NeoForgeOld **没有**（直接抛 `ChecksumMismatchException`，`:165-168`）。这是"复制粘贴必然漂移"的直接实证。

其他可借鉴项：
- **判型**：`ForgeInstallTask.detectForgeInstallerType`（含 `spec` ⇒ 新；含 `install`+`versionInfo` ⇒ 老；否则 `IOException`），**并校验 installer 的 `minecraft` == 目标版本**（`:137-155`）——我们目前无此校验（`ForgeInstallProfileJson` 未声明 `minecraft`）。
- **`outputs` 幂等**：先算字面量、逐 outputs 比 sha1，全命中且非空 ⇒ **整条 processor 跳过**；执行后不符 ⇒ **先删再抛**（`:77-110`、`:155-185`）。
- **`{MINECRAFT_JAR}` 隔离**：先拷到独立 temp 再用（"外部 processor 不得拿到共享缓存路径"，`:401-404`）——我们已有等价物（`:1220-1230`）。
- **`DOWNLOAD_MOJMAPS` 特判为纯下载**（走 provider 候选 URL、可镜像、不起 JVM，`:356-384`）。
- **下载源**：一次安装**只有一个** provider（镜像 = BMCLAPI 重写 `maven.minecraftforge.net` → `apiRoot + "/maven"`；官方恒不重写）。
- **installer 获取**：每次**新建临时文件** → 下到 temp → 挂 ZIP 结构校验 → 过校验才 `Files.move` 落位 → **用完即删**（`hash` 字段不用于校验）。这正是我们"缓存 + 自愈"策略要与之对齐的对照面。
- **1.13+ 前置**：`gameVersion >= 1.13` 且 base manifest 主类不在 `FORGE_OPTIFINE_MAIN` 时抛 `UNSUPPORTED_LAUNCH_WRAPPER`（防在 LaunchWrapper 实例上叠装，`:110-114`）。

### 2.3 三个真缺口与两个短板

**缺口 1 — 空 `url` 落到缺省仓（必挂）**：1.13–1.16.5 的主制品与 `:universal` 的 `url: ""`（真件：`1.13.2/version.json`、`install_profile.json`；`1.16.5/install_profile.json` 的 `:universal` sha1 `fd07fe6c…`），`libraryItem` 在 `downloads.artifact.url === ''` 时穿透到 `lib.url ?? DEFAULT_LIBRARY_URL`（`VersionInstaller.ets:391-393`，`DownloadContract.ets:40` = `libraries.minecraft.net`）⇒ 404。
Forge 1.12.2 分支靠"**先把 `maven/**` 拷进去、下载时命中即跳**"规避（`:2054-2071`）。**新链必须照做**，这是 1.13–1.16.5 的必需项。

**缺口 2 — 1.20.6+ 的 `:client` 是 processor 产物（顺序错误）**：`net.minecraftforge:forge:<ver>:client` 在 `version.json` 里 `url: ""`（`evidence/1.20.6-50.2.10/version.json`、`1.21.1-52.1.16/version.json`、`26.3-66.0.6/version.json`），而它是 `binarypatcher` 的**输出**。我们的顺序是"先下全部库（`:1203`）→ 再跑 processor（`:1220-1244`）"⇒ 该件在下载阶段必然不存在 ⇒ 404。
**修法**：把 launch-manifest 的库校验/补齐**挪到 processor 之后**（HMCL 正是这么分层的：profile.libraries 在 processor 前，launch manifest 的库在之后由 `checkComponentCompletionAsync(forgeVersion, true)` 处理，`ForgeNewInstallTask.java:329` vs `:439-441`）。

**缺口 3 — `-DmergeModules` 按名补库未接上 Forge**：解析器在 `NeoForgeInstaller.ets:318-404`，但它**只在 `installNeoForgeVersion` 内被调用**（`:1180-1202`）；而 1.17.1/1.18.2/1.20.1 的 Forge 真件都带 `-DmergeModules`（例：1.20.1 = `jna-5.10.0.jar,jna-platform-5.10.0.jar`；1.17.1 = `jna-5.8.0.jar,jna-platform-58.0.jar,java-objc-bridge-1.0.0.jar`，注意 `-58.0` 是 Forge 自己的拼写）。

**短板 1 — `outputs` 幂等缺失**：我们只做"存在性"（`PATCHED`），重入时 processor 会重跑；工具多数"先删后写"、非原子 ⇒ 中断可能留下半成品。
**短板 2 — `DOWNLOAD_MOJMAPS` 直连 Mojang 不可镜像**：`ref/InstallerTools/.../DownloadMojmaps.java` 硬编码 `https://launchermeta.mojang.com/mc/game/version_manifest.json`，无 `--url` 覆盖；1.17.1+ 会命中该 task。HMCL 用"替换为 provider 直下"规避，我们没做 ⇒ CN 网络风险。

### 2.4 方案 A（泛化，推荐）vs 方案 B（复制）

**方案 A**：把 NeoForge 链泛化成共享"新格式安装器链路"。
1. 先做**纯搬移**：抽出与 loader 无关的 processor 编排内核（现 `runNeoForgeProcessors` + `waitProcessorExit`/`waitNeoInstallGone` + plan 构造），`installNeoForgeVersion` 改为调用它（零行为变更）。
2. 抽出"新格式安装"共用骨架 = 现 `installNeoForgeVersion` 的步骤 1)–6)，**加上**：内嵌 `maven/**` 解包（搬 Forge 分支的 `:2054-2071`；对 NeoForge 是 no-op）、launch-manifest 库的"processor 之后再校验"、`mergeModules` 补库、`outputs` 幂等。
3. Forge 侧只剩薄事：`classifyForgeProfile` 新增一个"支持（新格式）"返回值；`ForgeInstallProfileJson` 补 `jar/classpath/args/outputs`（或直接复用 `NeoForgeProcessorJson`）；`composeForgeManifest`（已有）。
4. UI/状态层：`FORGE_MAX_MC` 改为按世代判断；`confirmInstall` 的 JRE 前置扩到 Forge（仅 ≥1.13 要求）；`InstallerState.installForge` 加 `ctx/gameRootUri/jreId`。

新增文件 0；改动面 = `VersionInstaller.ets`（三处搬移 + 一处新增分支）、`NeoForgeInstaller.ets`（命名泛化，注意 `NeoForgeProcessorJob` 被 `NeoInstallAbility.ets:8` 引用）、`GameVersionsView.ets`、`InstallerState.ets`。

**方案 B**：给 Forge 另起分支、复制一份。短期最快，但 §2.3 的三个缺口要在两份里各修一遍，且 HMCL 的 zlib 漂移就是这条路的终点。

**推荐 A**，理由：① 格式同构已被两侧独立证实（真件字段名逐字相同 + HMCL 逐字复制实现）；② NeoForge 链的"不可复用面"很小且可枚举（3 项）；③ 泛化能顺带修掉 NeoForge 链自己的三个洞（缺 `maven/`、缺 `outputs` 幂等、无下载顺序分层）；④ 选 B 等于把 NeoForge 链的债抄一遍。

> **更正（2026-09-30，用户裁决）：本节推荐作废，改为方案 B。** 安装办法由「方案 A（把 NeoForge 链泛化）」**改为方案 B（Forge 与 NeoForge 彻底分开、不泛化）**，理由 = **隔离风险**——NeoForge 会持续演进、**可能改行为**，把 Forge 挂在 NeoForge 的 processor 链上会把其将来变动**传染**给 Forge，分开才能让一侧改动不牵动另一侧。**原推荐 A 的理由（真件同构、HMCL 已漂移、三缺口只修一遍）保留为记录**（技术上仍成立，被"风险隔离"权衡否决）；细案见 [`Forge-1.13至1.20.1-安装实施方案.md`](../../90-archive/Forge-1.13至1.20.1-安装实施方案.md) §1。

### 2.5 泛化时必须保住的不变量

| 不变量 | 落点 |
|---|---|
| 安装期可写 `versions/**`、`libraries/**`；**不得**把我们的状态写进用户游戏目录（`config/`、`launcher_profiles.json` 一律不写） | `../../00-current/工程与规范.md` §二.3 推论① |
| **每个 loader 独立下载源**（`forgeSource` / `neoForgeSource` 各一份） | `InstallerState.ets:91-102`、`VersionInstaller.ets:1900-1908`、`:1047-1052` |
| installer 缓存自愈（复用前先解一次） | `:1112-1141` / `:1985-2010` |
| 工具 JVM 与启动 JVM 同源 `jreId` | `GameVersionsView.ets:999-1007`、`NeoInstallAbility.ets:65-98` |
| `{MINECRAFT_JAR}` 必须是独立 temp 副本（工具会就地改写） | `:1220-1230` |
| unzip 先清后解；workDir 按"源/版本"隔离（Forge 与 NeoForge 勿合并目录） | `:1078-1082`、`:1101-1105`、`Paths.ets:61-65` |
| 产物断言优先于退出码（工具 fail-open） | `:1242-1244` |
| 失败只清"半装实例" | `InstallerState.ets:452`/`:568` |
| 平台限制：安装期 JVM 宿主仅 2in1/Tablet（phone 无独立进程载体） | `安装期JVM载体-调研.md` §10 |

## 3. 启动侧

### 3.1 现状：解析/拼参层面基本够用

| 能力 | 判定 | 证据 |
|---|---|---|
| `inheritsFrom` 展开与合并（子覆盖父、基座在前） | 支持 | `VersionResolver.ets:248-317`、`:356-374` |
| HMCL 式 `patches[]` 折叠（按 `priority`） | 支持 | `:296-313`、`:324-335`、`:379-396` |
| `arguments.jvm` / `arguments.game` 数组形态 | 支持 | `MinecraftLauncher.ets:370-378`、`:414-419`；`ArgBuilder.java:78-92` |
| `-p` / `--module-path` | 支持（**仅透传，不自造**） | 同上；宏 `library_directory` 在 `:458` |
| `--launchTarget` / `--fml.*` 透传 | 支持（唯一过滤是 `ruleAllows`，这些是字面量、无 rules ⇒ 原样通过） | `:52-79`、`:372`、`:416` |
| `-DlibraryDirectory` | 支持 | `:458` |
| rules 过滤（os/arch/features） | 支持 | `:53-79`（**非空 `features` 一律不命中**，`:64-66`） |
| natives 目录与 `java.library.path` | 支持（json 参数之后统一覆盖为可写沙箱） | `:185-194`、`:389-398` |
| LWJGL 世代 / legacy 分流 | 支持（轴切在 1.13） | `:679-706`、`:770-788`、`ClasspathStager.ets:33-36` |
| `-DlegacyClassPath` | 不适用（11 份真件 0 命中） | — |

### 3.2 缺口：一个病根的三处表现

**病根 = 判据按 loader 名（`neoForge` 布尔）而不是"启动形态"。**

| 表现 | 位置 |
|---|---|
| classpath 形态：`neoForge ? 真 maven 树 : '<dir>/*' 平铺` | `MinecraftLauncher.ets:164`、`:179-184`（平铺由 `ClasspathStager.ets:79-121` 落盘） |
| 主类分叉：`meowcraftLaunch === true && !neoForge` ⇒ 推 `MEOW_MAIN_CLASS`（Forge 会被 `MeowLauncher` 反射调用，与我们"NeoForge 直启"的既定口径不一致） | `:404`（`MeowLauncher.java:56-137`；**`MeowLauncher` 已于 2026-10-01 退役，本行 = 该文撰写时的诊断**） |
| `mergeModules` 按名补库 + oshi 覆盖只挂在 NeoForge 分支 | `:569-611`、`:577-584`（`NeoForgeInstaller.ets:372-399`） |

世代 ② 的机制要求 classpath 是**真实路径列表**：`-DmergeModules` 由加载器按**文件名**在 classpath 里查表（真机 `UnionFileSystem$NoSuchFileException` 记录见 `NeoForge支持-调研.md`），`-DignoreList` 也按 classpath 条目匹配；平铺 `<dir>/*` 时 `java.class.path` 只有一个通配串 ⇒ 两者同时失效。

**建议**：把"classpath 形态"与"主类分叉"两个判据**收敛到同一个来源**（例如 `ResolvedVersion` 上新增 `launchShape`：`launchwrapper` / `modlauncher` / `bootstraplauncher` / `forgebootstrap`），不要在两处各写一遍布尔——现在是两处，将来 1.20.6+ 会变三处。

**HMCL 对照**：它判的是 **mainClass 字符串**（`GameComponentAnalyzer.MOD_LAUNCHER_MAIN` / `BOOTSTRAP_LAUNCHER_MAIN` / `FORGE_BOOTSTRAP_MAIN`），且**对 1.20.6+ 不做任何补偿**（`repairForLaunch` 只匹配 Launch/ModLauncher/Bootstrap 三者）——靠真树 classpath 让加载器自己工作。这间接支持 §3.3 的推测。

### 3.3 需要打掉的一条假设

`Forge支持-改动方案.md` §8 与 §3.4 断言 **1.20.6+ "平铺即可（无 module path）"**——**无任何真件/HMCL 证据**，且与机制矛盾：`ForgeBootstrap` 的 profile 里 `-p`/`-DignoreList`/`-DlibraryDirectory` **全都没有**，说明库发现与 classpath 分区的责任**收回到加载器自己**，它必须能枚举 classpath 条目，而平铺只给一个通配串。⇒ 该断言应标为**待验证假设**，大概率仍需真树 classpath。

### 3.4 改造时的注意点

- **`features` 门控必须保留**（`:64-66`）：否则 `--width ${resolution_width}` 会原样发给 Forge 的 joptsimple ⇒ `NumberFormatException`（NeoForge 1.21.1 实测教训）。
- **超长 `-cp`**：真树 classpath 在手机上可能上千字符；「超长 `-cp` 在本 JLI 移植会失效」的坑（`:152-153`）**只被 NeoForge 实测豁免过**（NeoForge 也是真树，1.21.1 已实机通过；2026-09 记录）⇒ 改 Forge 走真树前应确认该豁免同样成立。
- **`-Djava.system.class.loader` 不要给 Forge 加**：现状对 Forge 不设（`:261` 只对 vanilla 或 launchwrapper 主类设）⇒ **天然正确**。注意 `stuffs/research/forge-support/B-our-launch-side.md` §5 的"老 Forge 不设"表述已过期（应为"launchwrapper 主类会设"）。
- **世代 ① 的 Java 8 张力**：`JavaPolicy` 对 1.13–1.16.999 **偏好 8**，而 1.16.5 的 Forge json 带 `--add-opens`/`--add-exports`（JDK9+ 选项）。json 首条恰是 `-XX:+IgnoreUnrecognizedVMOptions`，**是否足以让 Java 8 容忍 `--` 长选项尚未验证（2026-09-30 复核）**；这也是该代唯一可能"启动即退"的点。
- **世代 ② 的 ignoreList 形态**：现实现靠 `${version_name}.jar` 恰好等于实例 jar 名。HMCL 有两级修复（`LaunchManifestNormalizer.java:193-223` 给 bootstraplauncher ≥0.1.17 追加 `${primary_jar_name}`；`DefaultLauncher.java:551-620` 对 <0.1.17 改写为精确绝对路径）。真件样本是 1.1.2（≥0.1.17）与 0.1.17 边界 ⇒ **≥0.1.17 可省**。
- **HMCL 的两条无条件 `-Dfml.*`**：`-Dfml.ignoreInvalidMinecraftCertificates=true` / `-Dfml.ignorePatchDiscrepancies=true`（`DefaultLauncher.java:258-259`）。属"与 HMCL 一致"的加分项，**不是能否启动的必要条件**。
- **classpath 绝对路径去重（保序）**：既有不变量（`:619-632`，防 bootstraplauncher `Duplicate key`）必须保留。

## 4. 环境侧（真正的硬阻塞）

### 4.1 JRE 供给：缺 17 / 21 两档

随包只有两个（`JavaRuntime.ets:76-87`；`multi-JRE` 数据根 `filesDir/meow-jres/<id>` 已就位）：

| id | Java | 来源 | 数据令牌 |
|---|---|---|---|
| `meow_jre` | **26** | 官方 `openjdk/jdk26u` `jdk-26.0.2.1-ga`（glibc 件原地改 `.dynstr` + 自编 `libc6/libjli/libjvm`） | `26.0.2.1+1-7-r2` |
| `meow_jre_legacy` | **8** | Eclipse Adoptium Temurin `jdk8u504-b01`（data + 自编 musl `libjvm` + `libc6/libjli`） | `1.8.0_504-b01-r1` |

**可下载 = 无**（rawfile 只有这两份）。`tools/jre25/` 是历史配方（已声明勿用于当前随包）。

⇒ 解算结果：Forge ≤1.12.2 = **8**（实机）；1.13–1.16.999 = **8**（代码自标 untested）；**1.17–1.20.4 与 ≥1.20.5 只能用 26 顶**（17/21 不存在）。
风险排序：**1.17.1/1.18.2 的 `securejarhandler 0.9.54 / 1.0.8` + bootstraplauncher 老档在 JDK 26 上风险最高**（仅 NeoForge 1.20.2 的 `bootstraplauncher 1.1.2 + securejarhandler 2.1.24` 有 JRE 26 实机正证据）。JDK 24+ 永久禁用 `SecurityManager`、JDK 14+ 无 `Pack200`，而 Forge 的 bootstrap/ModLauncher 代际远老于 26。

另外：`JavaPolicy` 对 1.13–1.16 段 `satisfies` 在"只装现代套"时会全灭 ⇒ `autoChoice` 兜底现代套 + 警告（`JavaPolicy.ets:215-220`），即"不会硬失败但语义是兜底"，需要显式决策。

### 4.2 Java 8 × LWJGL3 × gl4es FPE 组合从未真机验证

这是 **1.13–1.16.5 的唯一必经组合**：LWJGL 轴在 1.13 切到 LWJGL3（单代 3.4.3），GL 后端轴在 1.17 才切到 core ⇒ 1.13–1.16 必须是 **Java 8 + LWJGL3 3.4.3 + gl4es FPE**。
三件各自都验过（Java8+Lwjgl2 实机；JRE26+Lwjgl3+FPE 实机；Java8+FPE 实机），**合起来没验过**——legacy JRE 的日志对象全是 1.6.4/1.7.10/1.12.2（LWJGL2 实例）。
代码级可行性有二处旁证：`ref/lwjgl3-3.4.3/README.md` 明写"LWJGL 3 requires Java 8 or later"，`MemoryBackend` 有 Java 8 用的 `MemoryBackendUnsafeLegacy` 后端，我们的 overlay 也是 `javac --release 8`（`tools/lwjgl/build_lwjgl_jar.sh:208`）。但**真机为零证据**。

### 4.3 natives 供给是"随包顶替"，不是"按规则解压"

- 现代只有一代 **3.4.3**：jar 含 `lwjgl`(core)/`glfw`/`opengl`/`openal`/`stb`/`vulkan`/`freetype`/`tinyfd`（3.4.x 另加 `sdl`/`vma`/`spvc`/`shaderc`）；natives 12 项（`libs/meowlwjgls/libs/natives.manifest`）。
- **没有 `liblwjgl_glfw.so` 是设计**：由自研桥 `libmeowcraftbridge.so` 提供全部 `nglfw*` 符号；命名/加载靠"世代号紧跟基名 + `MeowBundledNameMapper`"两处锁步。
- **缺口**：① 无 `lwjgl-jemalloc`（模块与 native 都没有；靠 `-Dorg.lwjgl.system.allocator=system` 规避，`MinecraftLauncher.ets:275`）——香草实测可玩 ⇒ 香草不引用，**Forge/模组是否引用未证**；② **natives 不是按 `libraries[].natives` 解压**，而是"用随包同名库顶替"（`:541-551` 跳过一切 `org/lwjgl/*`，且无解压到 `<natives_directory>` 的步骤）⇒ 任何 Forge/模组引入的、我们未随包的 native 拿不到 ⇒ `UnsatisfiedLinkError`。
- JNA native 已从随包摘除，而 Forge 1.17+ 的 json 显式 `-DmergeModules=jna-…` ⇒ 运行期是否真用 JNA **未证**。

### 4.4 GL 后端适用世代

| 后端 | 适用 | 状态 |
|---|---|---|
| gl4es **FPE** | legacy 1.6.x–1.12.2 与 **≤1.16.x** | 实机可用 |
| 系统桌面 GL（`libmeowglguard` → `libGLv4.so` = Mesa 25.0.1 Zink，GL 4.2 core/compat） | **≥1.17**（2in1/tablet） | 实机可用 |
| gl4es **core**（`MEOW_GL3`，GL 3.2/3.3 core → 原生 GLES 3.2） | **≥1.17**（无桌面 GL 的设备） | 实机可用（r9/tls2） |
| Vulkan（MC 原生 + 自研 `libmeowvulkan.so` shim） | **仅 MC ≥26.2** | 实机 70–80 FPS（26.3） |

硬约束：**MC 1.17.1–1.19.4 要 GL 3.2 core，1.21.10/1.21.11 升到 GL 3.3 core**（含 UBO/`glMapBufferRange`/fence/instancing）⇒ gl4es FPE 对 ≥1.17 **结构性不可用**；1.13–1.16 反过来只能用 FPE（GLES 无固定管线）。
⇒ Forge ≥1.13 的落点：**1.13–1.16.5 只有 FPE 一条路；≥1.17 走桌面 GL core 或 gl4es core**。
未验面：gl4es core 的 1.18.x / 1.20.x 其余 / 1.21.11（含 GL 3.3 core + UBO 世代）与性能；core 档还有"静默 no-op 陷阱"（`已知限制与待解.md` C8/C9/C10）。

### 4.5 平台限制

安装期必须有 JVM 宿主（processor 链），而 **phone 无独立进程/无窗载体** ⇒ **phone 上装不了 Forge ≥1.13**（与 NeoForge 1.20.2+ 同受限）；只有 26.x 形态有"零 JVM"潜力。

## 5. 分期路线（建议）

### 阶段 0 — 零代码改动的设备验证（先做，性价比最高）

拿**现成外部（HMCL）装好的** Forge 实例丢进游戏根目录，只走"识别 → 组 argv → 起 JVM"：
- 样本 1：**Forge 1.16.5**（走 Java 8 路 = `meowjrelegacy` el1，验 §4.2 的未验组合）；
- 样本 2：**Forge 1.20.1**（走 JRE 26 路 = 世代 ② 的真树 cp + `-p` + `mergeModules`）；
- 可选样本 3：**Forge 1.21.1**（世代 ③，验 §3.3 的"平铺 vs 真树"假设）。

两条读数判据：日志 `JRE for <实例>: <id>`（自证 JavaPolicy 解算）与 `[meowcore]` / `RendererInit` 自证行。
**理由**：§4 的三个高强阻塞**都不在安装链里**，先测能把 §4.2、§4.1 与 §3.3 的"未知"变成"已证/已证否"，避免把安装链白做。

### 阶段 1 — 启动链（按 §5.2 实测修订）

1. **真树 classpath（充要项）**：把 `-cp` 从平铺通配改为 `<gameRoot>/libraries/**` 逐条绝对路径 + 实例 jar（对齐 HMCL 的 `${classpath}`）。这是 1.16.5 `Missing forge!` 的充要修法。**首改已落地并实测（2026-09-30，见 §5.3）**。
2. **（原"1.20.6+ 必要项"，2026-09-30 改为范围外记录）**：1.20.6+ 的"重复 `com.mojang.text2speech` 提供者"是 §5.2 C 记录的机制，**触发条件 = 某加载器把 classpath 模块化（做模块解析）且我们的 `launcher.jar` 桩在 classpath 上同时导出 `com.mojang.text2speech`**。因 Forge 支持面截至 1.20.1（③ 代不在范围内），此项**不在本路线图内**，仅作机制记录（触发时见 §5.2 C 的三条候选）；① 代不做模块解析、② 代 `BootstrapLauncher` 自带 `PackageTracker` 包去重 ⇒ ①② 代都够不着该触发条件。
3. **`mergeModules` 补库**：补上（② 代真件带它；实测不阻塞，但属正确性）。
4. **主类直启**：降为重构项——与"判据收敛"合并成"判据收敛到 `launchShape`"，不阻塞功能。（首改只做了"判据收敛到同一来源"，未把 Forge 改走直启，见 §5.3。）
5. 可选：HMCL 的两条无条件 `-Dfml.*`。

### 阶段 2 — 安装链泛化（方案 A）+ 三缺口

纯搬移内核 → 共用骨架 → Forge 薄分支；补 `maven/**` 解包、launch 库"processor 之后"校验、`mergeModules` 接入。

**范围（2026-09-30）**：安装链上界收到 **≤1.20.1**（Forge 支持面封顶 1.20.1；≥1.20.2 交 NeoForge）⇒ §2.3 **缺口 2（1.20.6+ 的 `:client` 顺序错误）及其 ③ 代部分 = 范围外**；**缺口 1（内嵌 `maven/**`，1.13–1.16.5 必需）与缺口 3（`mergeModules` 接入，②代）= 在范围内**。

> **落地细案见** [`Forge-1.13至1.20.1-安装实施方案.md`](../../90-archive/Forge-1.13至1.20.1-安装实施方案.md)（**方案 B**；逐条改造清单 F0/F0b/F1–F3/G1–G3/S1–S4/U1–U3、必须保住的不变量、P0–P3 风险、期 1–4 分期与测试计划）。

### 阶段 3 — 收尾

`outputs` sha1 幂等（含"是否要像 HMCL 那样给 Forge 加 zlib 降级"的决策）、`DOWNLOAD_MOJMAPS` 特判为可镜像直下、`spec` 形态一致性校验（是否需要比 `minecraft` 字段）。

**范围（2026-09-30）**：这三项中**仅 1.20.6+（③ 代）才需要的部分标为范围外**，触及 ①② 代的部分保留 —— `outputs` 幂等（①② 代 profile 普遍有 `outputs`，见 §1）**保留**；`DOWNLOAD_MOJMAPS` 在 **1.17.1+（② 代）已会命中**（§2.3 短板 2）⇒ 也**保留**（可镜像直下，非阻塞）；`spec`/`hideExtract`/`serverJarPath` 这些仅 ③ 代出现的形态一致性校验 ⇒ **范围外**。

### 5.1 阶段 0 操作清单与读数判据（2026-09-30 制定）

**阶段 0 不改任何代码**，被测的是既有链的"识别 → 组 argv → 起 JVM"。

**准备**
1. 三个样本都让 HMCL 把库落在**应用实际使用的那个游戏根目录**下（我们的 `-cp` 与 `-DlibraryDirectory` 都指向 `<gameRoot>/libraries`）。HMCL 的实例布局即可——我们的 resolver 同时读 `inheritsFrom` 与 HMCL `patches[]`。
   - 样本 A = **Forge 1.16.5**（世代 ①；同时覆盖 §4.2 的 Java8 × LWJGL3 × gl4es FPE 组合）
   - 样本 B = **Forge 1.20.1**（世代 ②；覆盖真树 cp + `-p` + `mergeModules`）
   - 样本 C（可选）= **Forge 1.21.1**（世代 ③；验 §3.3 的"平铺 vs 真树"）
2. 用当前 HEAD 构建并部署应用（阶段 0 不加代码，但要用与本文行号基准 `8e46d50` 一致的构建）。
3. 按惯例把设备日志导出到 `Harmomeow-Craft-Launcher/.logs/`。

**读数判据（每条记原文行）**

| # | 看什么 | 期望 / 判定 |
|---|---|---|
| 1 | 版本卡片是否识别为 `forge`（而非「未知」/vanilla） | 若「未知」⇒ loader 识别这条链先断，后续不必继续 |
| 2 | 日志 `JRE for <实例>: <id>` | 样本 A 预期 `meow_jre_legacy`（Java 8：`JavaPolicy` 对 1.13–1.16.999 偏好 8）；样本 B 预期 `meow_jre`（26）。**实际值就是 §4.1 的判据** |
| 3 | 组出的 `-cp` 形态 | 平铺 = `<cacheDir>/mc-cp/<key>-<id>/*`；真树 = `<gameRoot>/libraries/**` 逐条绝对路径 |
| 4 | mainClass | 样本 A 预期 `cpw.mods.modlauncher.Launcher`；若出现 `meow.launcher.MeowLauncher` ⇒ 证实"主类分叉"（被反射顶替） |
| 5 | 世代 ② 的参数是否齐 | `-p`（module path）、`--launchTarget forgeclient`、`-DignoreList`、`-DmergeModules`、`-DlibraryDirectory` 应原样透传；缺哪条记哪条 |
| 6 | GL 后端的自证行 | `created desktop OpenGL …` / `created OpenGL ES 3.2 context for gl4es core backend` / `[meowcore] core backend init` |
| 7 | **第一条**致命 Java / 原生错误 | 见下矩阵 |

**判定矩阵**

| 症状 | 指向 | 得到什么结论 |
|---|---|---|
| `Unrecognized option: --add-opens`（样本 A） | Java 8 不吃 JDK9+ 选项 | §3.4 的"Java 8 张力"成立 ⇒ 需剥离或改写这些参数 |
| `UnsupportedOperationException: Setting a Security Manager is not supported` | JRE 26 跑老 Forge | §4.1 的 JRE 代际冲突（与 Forge ≤1.12.2 同一堵墙） |
| `UnionFileSystem` 的 `NoSuchFileException` / bootstraplauncher `Duplicate key` | 平铺 cp ⇒ `mergeModules` 失效 | §3.2 的"classpath 形态"与"`mergeModules` 挂载"两条成立 |
| 指向 `cpw.mods.*` 的 `NoClassDefFoundError` / `ClassNotFoundException` | classpath 不完整 | 需再分"形态错"还是"库缺"（比对 `libraries/` 落位） |
| `UnsatisfiedLinkError` | natives 顶替机制未覆盖 | §4.3；记录具体库名（如 jemalloc） |
| 落到主菜单 / 出现 Forge 加载进度条 | 成功 | 记录 GL 后端、FPS、以及是否出现 §7-15 的"加载器层落盘" |

**产出**：把上面 7 条的原文行 + 判定矩阵命中项贴回，即可确定 §7 里第 10–13 条哪几条转成"已证/已证否"，再决定阶段 1（启动链）与阶段 2（安装链）的先后。

### 5.2 阶段 0 实测结果（2026-09-30，A/B/C 三样本）

| 样本 | 实例 | 结果 | 直接死因 |
|---|---|---|---|
| A | Forge 1.16.5 | **失败** | `FMLCommonLaunchHandler.validatePaths` 抛 `Missing forge!` |
| B | Forge 1.20.1 | **成功**（进世界、正常退出） | — |
| C | Forge 1.21.1 | **失败** | `Bootstrap.moduleMain` 抛 `java.lang.module.ResolutionException` |

三个样本的 JRE 解算均符合预期（A = `meow_jre_legacy` / Java 8；B、C = `meow_jre` / 26），`GameLauncher CMD:` 三份都在日志里。实例根 = `stuffs/test-higher-forge`。

#### A：Forge 1.16.5 —— **平铺 classpath 是充要病因**

FML 定位自己的 universal jar 的机制（字节码定案，类在 `libraries/net/minecraftforge/forge/1.16.5-36.2.42/forge-1.16.5-36.2.42.jar`）：

```
FMLLoader.setupLaunchHandler → getForgePath → LibraryFinder.getForgeLibraryPath
   └─ LibraryFinder.findLibsPath()
        └─ findJarPathFor("org/objectweb/asm/Opcodes.class")
             = ClassLoader.getResource(…Opcodes.class) → 该资源所在 jar 的 Path
        → 连续 getParent() × 6  ⇒ "libraries 根"
   → MavenCoordinateResolver.get(group, "forge", "universal", jar, mcVer+"-"+forgeVer)
      ⇒ <libsRoot>/net/minecraftforge/forge/1.16.5-36.2.42/forge-1.16.5-36.2.42-universal.jar
   → FMLCommonLaunchHandler.validatePaths:104 仅做 Files.exists(...)，失败即 fatal "Missing forge!"
```

- **6 级父目录**正好对应 Maven 布局 `libraries/org/objectweb/asm/asm/9.6/asm-9.6.jar`（从文件上溯 6 次 = `libraries`）。
- 我们的 `-cp` 是**平铺 staging 通配**（`<cache>/mc-cp/<key>-<id>/*`）⇒ ASM 命中 `…/cache/mc-cp/1.16.5-Forge/asm-9.6.jar`，从 `/data/storage/el2/base` 起**也正好 6 级** ⇒ 路径基被算成**应用数据根**，于是报错路径 = `/data/storage/el2/base/net/minecraftforge/forge/1.16.5-36.2.42/forge-1.16.5-36.2.42-universal.jar`（与日志逐字符吻合）。
- **jar 本身是存在的**（`<gameRoot>/libraries/…/forge-1.16.5-36.2.42-universal.jar`，2,540,080 B）——纯粹是"路径基算错"。
- ⇒ FML **不读任何 `-D` 属性**、也不扫描 `java.class.path` 找 universal jar；该代际 json 里**没有**可指向它的参数（我们没漏传任何东西）。**真树 classpath**（ASM 落在 `<gameRoot>/libraries/org/ow2/asm/asm/9.6/…`，上溯 6 级 = `<gameRoot>/libraries`）即为充要修法。
- 由此得到一条**机制性不变量**：**① 代（1.13–1.16.5）不能用平铺目录承载 classpath**，这不是配置问题而是必然——换任何深度的平铺目录都只会把"路径基"错成另一个值。
- 附带证否：`-XX:+IgnoreUnrecognizedVMOptions` + `--add-exports/--add-opens` 在 **Java 8 上没有阻塞**（`ModLauncher 8.1.3 … java version 1.8.0_504` 已正常启动）⇒ §3.4 那条"Java 8 张力"在本样本上不成立。

#### C：Forge 1.21.1 —— **我们自己的桩包与真实库重复导出同一包**

- 冲突的两个模块来源（构件定位）：`text2speech` = `libraries/com/mojang/text2speech/1.17.9/text2speech-1.17.9.jar`（真实库）；**`launcher` = 我们自己的 `launcher.jar` 桩**（来自 `entry/src/main/resources/rawfile/meowcraft_extras.tar.gz`，内含 `com/mojang/text2speech/Narrator.class` 与 `NarratorDummy.class`）。
- `ForgeBootstrap.selectRuntimeModules` 会把 `java.class.path` 上**每一条**（既非 ModFile 也非已在 bootLayer 的）当成模块候选，模块名取自文件名（`text2speech-1.17.9.jar` → `text2speech`；`launcher.jar` → `launcher`）；随后 `Bootstrap.moduleMain:166` 的 `resolveAndBind` 同时看到两个导出 `com.mojang.text2speech` 的模块 ⇒ 硬报错 `Resolver.checkExportSuppliers`。
- **与平铺无关**：真树 classpath 下这两个 jar 依然都在 classpath 上 ⇒ 照样冲突（这也回答了 §3.3 留下的"平铺 vs 真树"疑问——对 ③ 代而言平铺不是关键变量）。
- 为什么香草能跑：普通 classpath 按类加载顺序遮蔽，**不发生模块解析**；为什么 B 能跑：② 代用 `cpw.mods.bootstraplauncher.BootstrapLauncher`，其 `PackageTracker` 会把**已被前一个模块申领的包**从后续 jar 剔除（自动去重）⇒ 天然不冲突。
- 日志里那行 `Ignored non-exists file: …/forge/1.21.1-52.1.16/forge-1.21.1-52.1.16.jar` 来自 FML `validatePaths` 对 `mcPaths` 的正常扫描（该目录只有 `-client`/`-shim`/`-universal`）⇒ **非问题**。

> **更正（2026-09-30，用户设备实测）**：本节的撞包**在当前实现下不再出现** —— 把 Forge ≥1.13 改为**直接以加载器主类启动**（不再经 `meow.launcher.MeowLauncher` 反射）后，随包 `launcher.jar` 桩件**不进 classpath** ⇒ `com.mojang.text2speech` **只剩真实库一个提供者**；实测 **Forge 1.21.1 已进游戏界面并干净退出**（`ResolutionException` 计数 = 0）。⇒ §5.3 的"③ 代范围外"**现为政策选择、而非技术必然**；③ 代的应用内安装仍需额外适配（`hideExtract` / `serverJarPath` / `path` 带 `:shim` 三项形态差异），不在本方案内。活状态见 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §E 与 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 28 条。

#### B：Forge 1.20.1 —— 为什么能成功

② 代的 `-p`（module path）由 **json 提供**并经 `${library_directory}` 宏展开为**真路径** ⇒ 不受平铺 `-cp` 影响；`-DignoreList` / `-DmergeModules` / `-DlibraryDirectory` 同样由 json 自带。此外 `BootstrapLauncher` 自带包去重（见上）。
**主类分叉（经 `meow.launcher.MeowLauncher` 反射顶替）在三例中都是无关项**：B 正是通过它跑通的；A/C 的失败点都在被反射调用的目标内部。

> **事实修正（2026-09-30）**：B 当时的 classpath 是**平铺**（`-cp` 走 `<dir>/*`），它跑通进世界与之无关（靠的是 json 自带的 `-p`/`-DignoreList`/`-DmergeModules`）；**本改动把 ② 代也切到真树** ⇒ B 从"已证形态（平铺）"切到"未证形态（真树）"，**需复测**（review 的 major 即此，见 §5.3）。

#### 对分期的影响（修订 §5）

1. **真树 classpath 升为阶段 1 的充要项**：它是 A 的充要修法，也是这一族"加载器按自身 jar 位置推断路径"问题的通解。
2. **主类直启降为重构项**：三例证明它不影响功能；保留为"判据收敛"的一部分，不阻塞 ≥1.13 跑起来。
3. **新增必要项**：1.20.6+ 必须消除重复的 `com.mojang.text2speech` 提供者。（**2026-09-30 范围注**：此项**仅对 ③ 代成立**，而 ③ 代已定为范围外，见 §5.3 ⇒ 不再是必要项，改写为**触发条件式记录**：见 §5 阶段 1 第 2 条。候选（都需实机验证）：① 从我们的 `launcher.jar` 桩里剥离 `com/mojang/text2speech/*`；② 对 1.20.6+ 在 staging 阶段跳过真实 `text2speech-1.17.9.jar`（可复用 `ClasspathStager` 既有的 override/排除机制）；③ 用 `net.minecraftforge.bootstrap.api.BootstrapClasspathModifier` SPI 在分区前剔除。）
4. **`mergeModules` 补库仍然要补**（②代真件带它），但实测表明它**不阻塞**（`-p` 已给真路径）。
5. §5.1 的七条读数中，①（识别）、②（JRE）、③（平铺）、④（主类）、⑤（②代参数齐）**全部按预期命中**；⑦（首条致命错误）命中 §5.2 的两处新机制。

### 5.3 阶段 1 首改与范围收窄（2026-09-30）

> 本节 = **阶段 1（启动链）首改已落地并实测**（带日期记录）+ **用户对 Forge 支持面的范围裁决**。
> 支持面现状以 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 28 条与
> [`../../00-current/版本支持边界.md`](../../00-current/版本支持边界.md) 为准。

#### 改动内容（主仓工作区，未提交）

2 文件（`entry/src/main/ets/common/constants/LaunchContract.ets`、`entry/src/main/ets/common/data/MinecraftLauncher.ets`），把"需要真库树的版本"的 classpath 从**平铺通配**切到**真 maven 树逐条绝对路径 + 实例 jar**（对齐 HMCL 的 `${classpath}`）：

- **判据 = 启动形态主类**（`REAL_CLASSPATH_MAIN_CLASSES`）：`cpw.mods.modlauncher.Launcher`（①代）/ `cpw.mods.bootstraplauncher.BootstrapLauncher`（②代，同时覆盖 NeoForge 现状）/ `net.minecraftforge.bootstrap.ForgeBootstrap`（③代）/ `net.neoforged.fml.startup.Client`（NeoForge 新世代），另有 `loader === neoforge` 兜底。判据**不再按 loader 名**（对上 §3.2 的病根）。
- **真树组装 = `assembleRealTreeClasspath`**（原 `assembleNeoForgeClasspath` 泛化，**2026-09-30 改名**）：按清单顺序逐条绝对路径 + 实例 jar（含继承式实例的基座 client jar）+ `-DmergeModules` 按名补库。
- **平铺目录只以具名件的绝对路径**参与（**不再**是 `<dir>/*` 通配）：随包 LWJGL3 jar、oshi 补丁件（**替换**而非前置）。`org/lwjgl/*` 仍跳过（随包 clean-room 件替代）。随包 `launcher.jar` / `gson-for-launcher.jar` **已退役、不进任何 classpath**（见 [`决策与不变量.md`](决策与不变量.md) §0.4）。
- 副作用：NeoForge（**自装 / HMCL 形态**）的 classpath 形态**保持不变**（本就走真树）；**外部 `inheritsFrom` 形态**会**多一条 jar**且**未复测**（口径与决策见 §5.5）。

#### 1.16.5 实测通过（2026-09-30，用户设备）

§5.2 A 的修法（真树 classpath）被实机验证：真树后 **1.16.5 的 `Missing forge!` 消失、能跑起来**（此前失败机制见 §5.2 A）。⇒ §5.2 归纳的"① 代不能用平铺目录承载 classpath"这条**机制性不变量实机成立**。

#### 自证日志（设备复测时读数用）

| 串 | 含义 |
|---|---|
| `classpath mode=real-tree (entries=N)` / `classpath mode=flat` | 是否命中形态判据（N = 条目数）；排查"这类实例为什么起不来"先看这一行 |
| `classpath real-tree: asm=<path> (in-libraries=yes\|no)` | FML 反推用的 ASM jar 提供者，及其是否落在 `<gameRoot>/libraries/org/ow2/asm/…`；`in-libraries=no` 即预兆 `Missing forge!` |
| `classpath real-tree: asm=(none) (in-libraries=no) -> …` | classpath 里没有 ASM 核心 jar（同上，warn 级） |

（`logAsmProvider` 只打日志、不改行为；`(none)` 与 `in-libraries=no` 两条负控在 2026-09-30 构造验证过。）

#### 独立 review 结论与已修项

review 判 `request_changes`（补齐实机复测前不合并）：**无确定性代码缺陷、机制推演站得住**。两条被修：

1. **② 代从"已证平铺"切到"未证真树"无设备证据**（review 的 major）⇒ 见下方"事实修正"与"范围"。
2. **"ASM 首命中"原先没有可观测落点** ⇒ 新增 ASM 自证日志（上表第 2/3 行）；主类常量补 NeoForge 新世代（`net.neoforged.fml.startup.Client`）。

#### 范围决定（2026-09-30，用户裁决）

- **Forge 支持面截至 1.20.1**（世代 ①+②）；**≥1.20.2 交给 NeoForge**（"再往上更流行 NeoForge"）。
- 由此 **③ 代（`ForgeBootstrap`，1.20.6+）从"待做"改为"不在范围内"** ⇒ §5.2 C 的"1.20.6+ 消除重复 `com.mojang.text2speech` 提供者"**不再是必要项**，改写为**触发条件式记录**（见 §7 注记）。
- **"启动"与"应用内安装"是两条线，现均已覆盖 1.13–1.20.1**。**现状**：应用内安装 Forge 支持 **1.7–1.20.1**（≤1.12.2 = **零 JVM 链**；**1.13–1.20.1 = processor 链**）；安装链上界 = **1.20.1**（≥1.20.2 交 NeoForge）。启动链与安装链的路由见 [`启动链-总览.md`](启动链-总览.md) 与 [`安装链-总览.md`](安装链-总览.md)。
- **免费搭车（形态未取样）**：1.20.2–1.20.4 的 Forge 形态 **T0 未取样**；若按**世代**（①+②）封顶，它**大概率**也顺带可用（② 代主类 `BootstrapLauncher` 覆盖 1.17.1–1.20.1，1.20.2–1.20.4 是否仍用该主类未取样 ⇒ **不写入支持面，等采样**）。

#### §5.2 B（1.20.1）的事实修正

B **当时是在平铺 classpath 下跑通并进世界的**（§5.2 B 原文即"② 代的 `-p` 由 json 提供、不受平铺 `-cp` 影响"；其能成功与平铺与否无关，见 §5.2 B）；本改动把**② 代也切到真树** ⇒ B 从"已证形态（平铺）"切到"未证形态（真树）"，**需复测**（review 的 major 正是这条）。

### 5.4 桩包来历与"谁提供 `com.mojang.text2speech`"（2026-09-30 调研）

> 本节 = **桩包那 2 个类的来历** + **实际提供者是谁**。结论用于把 §5.2 C 的撞包从"必要项"降为"触发条件式记录"。
> **（★2026-10-01：该桩包（`launcher.jar` 里的 `com/mojang/text2speech/*`）已随 `MeowLauncher` 退役整体移除 ⇒ 本节为历史记录；`tools/meow-launcher/` 目录亦已删除。）**

**桩里那 2 个类是 Pojav 时代契约的遗留**，不是我们为鸿蒙新增的：

- **Java 侧"跳过真库"是契约**：`tools/meow-launcher/src/meow/launcher/LibraryResolver.java` 的 `SKIPPED_PREFIXES` 第一项就是 `com.mojang:text2speech`（Pojav 原注释 "Support for text2speech is not planned, so skip it for now"）。
- **必须自带 no-op 桩顶住调用点**：MC 在**字段初始化**时即调 `Narrator.getNarrator()`，真库被跳过后若没有桩就直接链接失败 ⇒ 桩兜住该调用点。
- **净室把它从 Pojav 的 6 个类裁到 2 个**（`com/mojang/text2speech/{Narrator,NarratorDummy}`，`setJNAPath` 改空实现）。设计依据见 [`launcher净室-设计.md`](../../90-archive/launcher净室-设计.md)（§5 的 classpath 跳过表 / §6 的桩类规划 / §8 的合法性风险条）；供应链登记见 [`provenance-master.md`](../../30-supply-chain/provenance-master.md) 的 `com.mojang.text2speech 接口面` 条目。

**关键事实 —— 真库才是实际提供者，桩只是"真库缺失"时的 fallback**：ArkTS 侧的库收集器（`MinecraftLauncher.ets` 的 `collectFromJson`）**并不跳过 `com.mojang.text2speech`**（它只跳 `org/lwjgl/*`）⇒ 真实 `text2speech-<v>.jar` 本来就进 classpath。日志实证：1.16.5 / 1.20.1 加载的是真库里的 `NarratorLinux`（桩里连这个类都没有）⇒ **真库才是实际提供者，桩只是 fallback**。

⇒ **顺序翻转不是问题**：真树 classpath（§5.3 首改）把"谁赢"从"依赖 classpath 顺序"变成"**真库优先**"，而这正与"真库才是提供者"的事实一致；2026-09-30 的 **1.16.5 实机（真树）跑通**即旁证。

**结论**：§5.2 C 的撞包**从计划移除**，改写为**触发条件式记录**（见 [`已知限制与待解.md`](../../00-current/已知限制与待解.md) §E 新增条目）。

### 5.5 全面评审记录（2026-09-30）

> 本节 = **四路只读对抗性评审**的结论汇总（带日期记录）。逐条明细（症状 → 触发条件 → 建议修法 → 处置 → 证据）存
> `stuffs/research/forge-support/review-2026-09-30.md`。活状态以
> [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 28 条、
> [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md)、
> [`../../00-current/版本支持边界.md`](../../00-current/版本支持边界.md) 为准。

**四路范围与判定（一句话各自）**

| 路 | 范围 | 判定 |
|---|---|---|
| ① 启动侧（classpath / argv 组装） | 形态判定与 argv 组装 | `request_changes`（快照级；代码层无可证缺陷，唯一阻塞项 = 验证面） |
| ② 安装侧（Forge ≤1.12.2 零 JVM + NeoForge processor 链） | 安装编排 | 未见 blocker |
| ③ gl4es / 渲染 / 原生 | delta / 桥 / 随包件 | 可以合并 |
| ④ JRE / 资源化 | JavaPolicy / UI 资源 / native | 可以合并 |

**已修清单（本轮）**

1. gl4es **M-1（硬门误拒）与 M-2（root 上下文生命周期）可观测化**。
2. 安装侧 **processor 结果文件新鲜度校验 + 软超时**。
3. **两处可见性 warn**：`mergeModules` 点名缺件、真树形态未传 `stagedDir`。
4. `oshiJarBaseName` **过滤 `rules`**。
5. **文案 / 资源化四处**（网络异常分类文案、编辑面板双数字、`version_edit_java_label` 变量名、Java 环境友好名）。
6. **若干文档 stale**（`版本支持边界.md` 两处、`运行时环境变量.md` 的 `OHOS_JAVA_HOME`、`meowjrebridge.cpp` 头注释/回退字面量、`tools/gl4es/README.md` tag 计数、lwjgl2 哈希、"新装"实证口径）。

**登记暂缓 / 范围外**

- **gl4es 共享对象表并发加固**：**已登记暂缓**（逐项决策与重开条件见 [`Forge-splash-崩溃根因与共享上下文修复.md`](Forge-splash-崩溃根因与共享上下文修复.md) §5.4）。**本轮新增**：gl4es **root 上下文生命周期限制（M-2）** 一并暂缓（活状态登记在 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §C）。
- **Forge ≥1.20.2（③ 代）**：**范围外**（交给 NeoForge）。
- 其它 minor 项（`logAsmProvider` 文件名启发式、`entries=N` 计数口径、`isAsmCoreJarFileName` 正则漏判、官方源列表含无 installer 构建、下载无逐候选重试、`DownloadItem.urls` 只 `[0]` 生效 等）：**范围外 / 登记**。

**决策记录**

1. **Forge 1.17–1.17.1 继续用 26**（用户裁决，2026-09-30）：`JavaPolicy` 对该段 `min 16 / prefer 17`，随包只有 26 与 8（8 太老、不满足 `min 16`）⇒ **静默落到 26**；HMCL `MODLAUNCHER_8` 要求 ≤17 ⇒ 属偏离。**不加 `max 17` 边界**；**将来解法 = 补一档 JRE 17**（不是改用 8）。活状态登记在 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §C。
2. **「NeoForge 现状不变」应读作「自装（HMCL 形态）不变」**：本改动的"基座 client jar"分支对**外部 `inheritsFrom` 形态**的 NeoForge 会**多一条 jar**（判定可接受）；**外部 `inheritsFrom` 形态未复测** ⇒ §5.3 的口径**收窄为"自装（HMCL 形态）不变"**。
3. **② 代真树切换（评审 major）关闭**：用户 **2026-09-30 确认** 1.20.1 已在**真树**下跑过（日志未导出）⇒ §5.3 的"待复测"归零；`-DignoreList` / `-DmergeModules` 首次生效的形态由该确认覆盖。

**需实机清单**

1. **13.4 KB / 15.4 KB `-cp` 长度档**（1.20.1 / 1.20.6 真树 classpath 是否仍可启动）。
2. **1.13.2 / 1.14.4 / 1.15.2 真树**（① 代中段形态）。
3. **1.17.1 在 26 上**（JRE 17 缺档决策的反证）。
4. **外部 `inheritsFrom` 形态 NeoForge**（多一条 jar 的判定）。
5. **gl4es M-1 次序**（共享上下文先于首次成功 `makeCurrent` 创建）+ **`MEOW_ALLOW_SHARED_CTX=0` 负路径**。
6. **平铺冒烟 vanilla / Fabric / legacy**（确认真树分支无回归）。

**明细档指针**：`stuffs/research/forge-support/review-2026-09-30.md`。

## 6. 史料不一致（本轮已修正清单）

| # | 位置 | 问题 | 处理 |
|---|---|---|---|
| 1 | `stuffs/research/forge-support/C-forge-requirements.md` §2 | 把"老形态"覆盖写为 ~1.8–1.12.2 | 已改为 1.12.2 = `spec:0` + 空 processors；老形态 = 无 `spec` + 有 `install`/`versionInfo` |
| 2 | 同上 §1 | 判据只写"`spec` 有无" | 已补全为"需 JVM = client processor 数" |
| 3 | 同上 §3 | 1.13–1.16"无 module path"标为推断 | 已按真件改为已证实 |
| 4 | `stuffs/research/forge-support/A-our-install-side.md` | 行号大面积漂移；§8"未确认项"已过期 | 已加日期注记 + 行号对照；已标"由 T0 轮解决" |
| 5 | `stuffs/research/forge-support/B-our-launch-side.md` §5/§6-③ | "老 Forge 不设 `-Djava.system.class.loader`" | 已按代码（`MinecraftLauncher.ets:261`）改正 |
| 6 | `Forge支持-改动方案.md` §6 的 Forge 识别那条 | 旧口径称 Forge 识别未实现 | 已按 `VersionResolver.ets:483-537` 改标已落地 |
| 7 | 同上 §8 / §3.4 | 1.20.6+ "平铺即可"无证据 | 已标为待验证假设（见本文 §3.3） |
| 8 | `NeoForge支持-调研.md` §8.4 | "现代 profile 没有 `outputs`"外推到 Forge | 已限定为 NeoForge 1.20.2+ |
| 9 | `Harmomeow-Craft-Launcher/README.md` | Vulkan / 加载器口径陈旧 | 已对齐 notes 现状 |

## 7. 未证实 / 待验证

> **范围注记（2026-09-30）**：Forge 支持面**截至 1.20.1**（≥1.20.2 → NeoForge，见 §5.3）⇒ 下列与 **③ 代（1.20.6+ / 1.21.1 / 26.x）** 相关的项**标为范围外**（**不删，保留作知识**）：第 2、7、13 条整条，以及第 10、16 条里的 1.21.1 / 26.x 部分。与 ①② 代相关的项保留在范围内。

**真件层（T0 未记录）**
1. 1.13.2 / 1.16.5 / 1.20.1 installer 内 `maven/` 的**具体条目名**（T0 只记了数量；"主制品与 `:universal` 来自内嵌 maven/"是由"空 url + 数量>0"推断，强但非逐字节）。
2. **（范围外）** 1.20.6 / 1.21.1 / 26.3 的 `maven/`（2 条）分别是什么。
3. **1.20.2–1.20.4** 的世代切点；**1.14 / 1.15** 的形态（两端已测，中间未取样）。
4. Forge `data` 是否**所有** ≥1.13 版本都含 `PATCHED`（1.13.2/1.17.1/1.20.6/1.21.1/26.3 已目视确认；1.18.2/1.20.1 仅看过键数）。

**能力层**
5. 1.13–1.16 段的 installertools（1.0.3 / 1.3.0）+ SpecialSource / binarypatcher / jarsplitter 在**随包 JRE 26** 上能否跑通（字节码是 Java 8 级，未实测）；以及"是否该改走 JRE 8"。
6. `DOWNLOAD_MOJMAPS` 直连 `launchermeta.mojang.com` 在设备网络下是否可用（**不可镜像**）。
7. **（范围外）** 1.20.6+ 的 `:client`（空 url）在**启动期**是否必须存在、由谁消费。
8. `outputs` 幂等与 zlib 降级的取舍：沙箱内 zlib 差异是否会让 `PATCHED_SHA` 校验失败。
9. 是否需要"installer 的 `minecraft` 字段 == 目标版本"的一致性校验（HMCL 有，我们无）。

**实机层**（2026-09-30 起有 A/B/C 三样本实测，见 §5.2）
10. 三代中"任何一代能否进主菜单"——**已有一半答案**：1.20.1 实测进世界并正常退出；1.16.5 与 1.21.1 各自死在 §5.2 记录的两处机制上。1.17.x / 1.18.x / 1.19.x / 1.20.4 的 Forge 仍未试。**（范围外：1.20.6 / 26.x / 1.21.1 部分；1.16.5 已在阶段 1 首改后用真树复测通过，见 §5.3；1.20.1 见 §5.3 的事实修正需复测。）**
11. Java 8 + LWJGL3 3.4.3 + gl4es FPE 的真机组合（§4.2）——**部分回答**：1.16.5 用该组合已跑到 FML 初始化（JVM、LWJGL3、jvm args 均正常），但**尚未走到 GL 初始化**，整链仍未验。
12. Forge 1.17–1.20.4 在 **JDK 26** 上能否起来（尤其 `securejarhandler 0.9.54 / 1.0.8`）——**已在 1.20.1 上证否**（`bootstraplauncher 1.1.2` + `securejarhandler 2.1.10` 在 JDK 26 上工作正常）；1.17.x / 1.18.x 的老 `securejarhandler`（0.9.54 / 1.0.8）仍未试。
13. **（范围外）** Forge ≥1.20.5 的 `ForgeBootstrap` 在 JDK 26 下能否起来——**部分回答**：JVM 与 bootstrap 都已启动（JDK 26 非阻塞），失败点是模块冲突（§5.2 C），与 JRE 代际无关。
14. Forge 1.17+ 运行期是否引用 `org.lwjgl.system.jemalloc`、是否需要 JNA native（两者我们都没有）。
15. Forge 1.17+ 加载器层运行期是否**落盘**（securejarhandler / `.forge` 标记 / natives）——与"启动路径零写入"的边界（现口径只覆盖我们自己的代码）。
16. gl4es core 档的 1.18.x / 1.20.x 其余与性能。**（范围外：1.21.11 部分。）**
