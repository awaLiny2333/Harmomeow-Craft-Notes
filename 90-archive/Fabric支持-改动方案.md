# Fabric（mod loader）支持改动方案 —— 双形态（inheritsFrom + patches）落地设计

> 已归档（2026-10-01；因为其仍有效的结论已并入现役档（启动链-总览 / 决策与不变量）；现役口径见 [`启动链-总览.md`](../20-design/launch/启动链-总览.md)）。

> 日期：2026-09-13 ｜ **状态：已实施**（见 [`Fabric安装-方案.md`](Fabric安装-方案.md)；本文是改动方案/落地记录；能力现状以 [`../00-current/现状基线.md`](../00-current/现状基线.md) 为准）
> 前置：[`Fabric支持-调研.md`](../20-design/launch/Fabric支持-调研.md)（HMCL 机制 + 与 vanilla 差异 + 两形态）。
> 决策：**两形态都支持**（前提 = 判定方法明确；见 §1，已坐实）。
> 依据：自家代码（`Harmomeow-Craft-Launcher/entry/src/main/ets/**`、`tools/meow-launcher/src/meow/launcher/**`）逐文件抽读 + `ref/HMCL` @ `0e3455434` 源码。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 17 条](../00-current/现状基线.md)。

---

## 0. 结论速览

1. **两形态天然互斥、可判定**（§1）：有 `inheritsFrom` → 继承式；否则有含 `id:"game"` 的 `patches[]` → 补丁式；否则原版。
2. 启动职责**横跨两端**：ArkTS 管渲染后端/LWJGL 世代/classpath 平铺/`-D`；**Java `meow.launcher` 管真实 mainClass/参数/库解析并反射启动**（ArkTS 恒传 `meowcraftLaunch=true`，ArkTS 里的 `json.mainClass` 分支是死代码）。
3. 反转：Java `VersionLoader` **已实现 `inheritsFrom` 合并**（`VersionLoader.java:21-70`）→ 形态①的 `mainClass`（`KnotClient`）已能生效；**真正硬缺口是"父/基座客户端 jar 未进 classpath"**（`LibraryResolver.java:49-50`）。
4. 难点不在字段合并，而在 **`-Djava.system.class.loader=MeowClassLoader` 与 Fabric `KnotClassLoader` 的兼容性**（我方独有约束，未知/高风险）。

---

## 1. 判定方法（先行，零风险）

对版本 json 根对象：

```
isNonEmptyStr(x) = typeof x === 'string' && x.trim().length > 0
hasInheritsFrom  = isNonEmptyStr(json.inheritsFrom)
hasPatchesGame   = Array.isArray(json.patches) && json.patches.length > 0
                   && json.patches.some(p => p && p.id === 'game')
rootTrue         = json.root === true

form = hasInheritsFrom          ? INHERITS   // ① 官方安装器 / 外部导入
     : hasPatchesGame           ? PATCHES    // ② HMCL 自装（rootTrue 通常为 true）
     :                            VANILLA     // ③ 原版 / 普通独立清单
```

- HMCL 对应实现：`isModifiable()` = `inheritsFrom==null && patches!=null && hasPatch("game")`（`GameInstanceManifest.java:313-315`）。
- **两形态互斥**：官方安装器写 `inheritsFrom`；HMCL 先建 `root=true` 根清单再 `addPatch(game).addPatch(fabric)` → 写 `patches`（`GameInstallTask.java:89-96`）。
- 加载器识别：patch `id=="fabric"`（准）或库 `net.fabricmc:fabric-loader`（兜底）；出现 `net.legacyfabric` 组则判 `LEGACY_FABRIC`。

---

## 2. 现状：启动职责切分

| 层 | 负责 | 关键文件 |
|---|---|---|
| **ArkTS（entry）** | 扫版本、身份/隔离、**渲染后端/GL profile**、**LWJGL 世代**、把库**平铺**成 `-cp <cacheDir>/mc-cp/<id>/*`、注入全部 `-D`、调 native `startJvm` | `VersionScanner` / `GameLauncher` / `RendererPolicy` / `ClasspathStager` / `MinecraftLauncher` |
| **Java（launcher.jar）** | 读版本 json、**合并 `inheritsFrom`**、算库 classpath、生成 game 参数、反射 `mainClass.main(String[])` | `tools/meow-launcher/src/meow/launcher/*` |
| **契约** | ArkTS 输出以 `meow.launcher.MeowLauncher <player> <id>` 结尾；`-Djava.system.class.loader=meow.launcher.MeowClassLoader` | `LaunchContract.ets:14-15`、`MinecraftLauncher.ets:363-366`、`:242` |

**（设计时）当前无任何 `inheritsFrom`/`patches` 的 ArkTS 处理**；Java 有 `inheritsFrom` 但无 `patches`。→ **2026-09-13 已实现**：见 §9 与 `common/data/VersionResolver.ets`。

---

## 3. 改动方案

### A. ArkTS：新增「版本解析器」（两形态统一入口）— 核心新增

新文件 **`entry/src/main/ets/common/data/VersionResolver.ets`**（data 层，纯逻辑、不碰 UI/`$r`）：

- `resolveVersion(gameRoot: string, jsonPath: string): ResolvedVersion | null`
  - 读叶子 json → §1 判定 → ① 递归 `inheritsFrom` / ② 按 `priority` 折叠 `patches`，**归一成同一"有效清单"**；
  - 合并规则对齐 HMCL（见 [`Fabric支持-调研.md`](../20-design/launch/Fabric支持-调研.md) §2.2）：标量"子覆盖父"；`libraries` 子前父后；`arguments.game`/`arguments.jvm` 父前子后；`downloads`/`logging` 整对象择一；
  - 输出 `ResolvedVersion`：`{ mcVersion, loader, libraries, assets, assetIndexId, mainClass }`
    - **`mcVersion`**：① = 继承链**根**（无 `inheritsFrom` 的那层）的 `id`；② = `game` patch 的 `version`。
- 全量 schema 见 §4；**唯一 schema 归属**，消除 `VersionScanner.GameVersionJson` 与 `MinecraftLauncher.VersionJson` 的重复。

### B. ArkTS：消费面改造

| # | 落点 | 现状问题 | 改法 |
|---|---|---|---|
| B1 | `MinecraftLauncher.readVersionId`(`:384-387`) → 唯一调用 `GameLauncher.ets:71` | 读叶子 `id`；Fabric=`fabric-loader-…` → `RendererPolicy.isLegacyVersion` 正则 `^(\d+)\.(\d+)` 失配 → ≤1.16 判错后端 | 返回**解析后 `mcVersion`** |
| B2 | `MinecraftLauncher.lwjglGeneration`(`:520-547`) / `isLegacyLwjgl`(`:567-585`) | 只读叶子 `libraries`；Fabric 叶子无 `org.lwjgl` → 落地板 3.4.3 | 基于**解析后 libraries** 判定 |
| B3 | `MinecraftLauncher.collectFromJson`(`:460-490`)/`collectJarSources`(`:554-560`) → `ClasspathStager` | 只认 `downloads.artifact.path`；不合并父/补丁库 | 用解析后 libraries；补 **name→maven 回退**（对齐 Java `LibraryResolver.artifactPath:63-76`） |
| B4 | `VersionScanner`(`:71-93`) `GameVersion` | 无 loader/mcVersion 字段 | 扩展 `inheritsFrom?`/`loader`/`mcVersion`（构造点 `VersionScanner.ets:82`、`Index.ets:101` 同步） |
| B5 | `GameVersionsView.ets:498` 副行 | Fabric 无标识、`JRE 8` 误导 | 展示 `type · JRE x · Fabric`；`inheritsFrom` 入编辑面板 |

> B2 是**必须**（LWJGL 由 ArkTS 提供、Java 显式跳过 `org.lwjgl`）；B3 对 Fabric 库**可选**（Java `LibraryResolver` 会从 `<gameRoot>/libraries` 按 maven 补齐）。

### C. Java：`meow.launcher` 侧

| # | 落点 | 改动 |
|---|---|---|
| C1 | `VersionJson.java` | 加 `Patches[] patches`（`id/version/priority/mainClass/libraries/arguments/inheritsFrom`）、`AssetIndex assetIndex`（`id`）、可选 `String jar` |
| C2 | `VersionLoader.java` | ①已实现（`:48-70`）；补**记录基座版本 id**（现 `parent.inheritsFrom=parentId`，可直接复用）；②新增 `applyPatches()`：按 priority 折叠 patches（mainClass 覆盖、库合并、args 合并） |
| C3 | **★ `LibraryResolver.java:49-50`** | 现在只追加 `versions/<version.id>/<version.id>.jar`；Fabric 的 `version.id` 是 loader 实例名 → **vanilla 客户端 jar 永不入 cp**。改为按基座 id（或 `jar` 字段）追加 `versions/<baseId>/<baseId>.jar` |
| C4 | `ArgBuilder.java` | `assets_index_name` 空则取 `assetIndex.id`；`rules` 对象现被丢弃（`:66-70`），按需补 OS/features 求值；老 loader 按需补 `--tweakClass` |

> 形态②（HMCL）**顶层字段已被 HMCL 扁平化**（`mainClass`=KnotClient、`libraries`=合并集），且 HMCL **为实例复制了 `<id>.jar`** → Java 现状**可能已能起**，主要差 ArkTS 的 `mcVersion`/`lwjgl` 判定与验证。

### D. 契约 / 构建

- `EXTRAS_VERSION`（`LaunchDefaults.ets:54`）**改 Java 必升**（否则 staging 复用旧 `launcher.jar`；见 `ClasspathStager.ets:47-61`）。
- Java 由**用户**跑 `tools/meow-launcher/build_meow_launcher.sh`（agent 无 JVM）→ `finalize_for_meowcraft.sh`（agent 可跑）→ 部署先 HSP 后 entry。

---

## 4. 附录：两形态字段 schema（依据 HMCL 源码钉死）

### 4.1 `inheritsFrom` 形态（官方 Fabric profile）

```json
{
  "id": "fabric-loader-0.15.11-1.20.1",
  "inheritsFrom": "1.20.1",
  "mainClass": "net.fabricmc.loader.impl.launch.knot.KnotClient",
  "arguments": { "game": [], "jvm": [ "-DFabricMcEmu= net.minecraft.client.main.Main " ] },
  "libraries": [ {"name":"org.ow2.asm:asm:9.6","url":"https://maven.fabricmc.net/"} ]
}
```
- 只列增量字段；vanilla 的库/`assets`/参数去父实例取。
- 库条目常**只有 `name`+`url`**（无 `downloads.artifact`）→ 需 name→maven 回退。

### 4.2 `patches[]` 形态（HMCL 自装）

```json
{
  "id": "fabric-1.20.1", "root": true, "jar": "fabric-1.20.1",
  "patches": [
    { "id": "game",   "priority": 0,     "version": "1.20.1",
      "mainClass": "net.minecraft.client.main.Main", "libraries": [ /* vanilla 全量 */ ] },
    { "id": "fabric", "priority": 30000, "version": "0.15.11",
      "mainClass": "net.fabricmc.loader.impl.launch.knot.KnotClient",
      "arguments": {}, "libraries": [ {"name":"net.fabricmc:fabric-loader:0.15.11","url":"https://maven.fabricmc.net/"} ] }
  ]
}
```
- HMCL 写盘时顶层字段已扁平化（`reconstructByPatches()`，`GameInstanceManifest.java:671-689`），`patches` 保留；`inheritsFrom` 为空。
- 基座 MC 版本 = `game` patch 的 `version`。
- `GameInstancePatch` 键：`id/version/priority/minecraftArguments/arguments/mainClass/inheritsFrom/jar/assetIndex/assets/complianceLevel/javaVersion/libraries/compatibilityRules/downloads/logging/type/time/releaseTime/minimumLauncherVersion/hidden`（`GameInstancePatch.java:616-867`）。

### 4.3 合并规则（`GameInstanceManifest.merge`，`GameInstanceManifest.java:66-91`）

| 字段 | 规则 |
|---|---|
| `mainClass` / `minecraftArguments` / `jar` / `assetIndex` / `assets` / `javaVersion` / `type` / `time` / `releaseTime` | 子非空覆盖，否则父 |
| `arguments.game` / `arguments.jvm` | 父在前、子追加在后 |
| `libraries` | 子在前、父在后（**与 arguments 相反**） |
| `downloads` / `logging` | 整对象择一，不深合并 |
| `minimumLauncherVersion` | 取 max |

库去重（启动前）：key = `groupId:artifactId`（不含 version）；rules 相同 → 高版本赢、位置保持首次出现（`LaunchManifestNormalizer.java:277-330`）。

---

## 5. 难度估摸（分层）+ 决定难度的未知点

| 层 | 内容 | 风险 | 估时 |
|---|---|---|---|
| **T0 判定+骨架** | `VersionResolver`（判定+归一）、`GameVersion` 字段、UI badge | 低 | ~0.5 日 |
| **T1 形态① 打通** | B1/B2 + C3 父 jar + C4 assetIndex | 低-中 | ~0.5–1 日 |
| **T2 形态② 打通** | `VersionResolver` 的 patches 折叠 + B4/B5；Java 多半已够 | 中 | ~0.5–1 日 |
| **T3 类加载器打通（决定成败）** | `-Djava.system.class.loader=MeowClassLoader` 与 Fabric `KnotClassLoader` 冲突 | **高 / 未知** | 未知 |
| **T4 边角** | rules 求值、`-DFabricMcEmu`、老 loader `--tweakClass`、`version_name`、staging basename 冲突 | 中 | ~0.5 日 |

**决定整体难度的未知点（先验证，勿盲铺）：**
1. **★ `MeowClassLoader`（parent-first，被设为 system CL）与 Fabric Knot 自身 classloader/重启机制是否兼容**（我方独有约束）。
2. 官方 Fabric 实例是否**真的不产出 `<id>.jar`**（决定 C3 是否必改）。
3. Fabric Loader 是否要求自身为 system class loader（影响 1 的解法）。
4. 用户机器上两形态**实际各占多少**（决定 T1/T2 优先级）。

---

## 6. 实施顺序（清单）

1. **[T0]** 新建 `VersionResolver.ets`（判定 + `inheritsFrom`/`patches` 归一 + `mcVersion`/`loader`）。
2. **[T1-arkts]** B1 `readVersionId`、B2 `lwjglGeneration`/`isLegacyLwjgl` 改走解析清单；B3 `collectFromJson` maven 回退。
3. **[T1-java]** C1/C2/C3/C4（父 jar 为要害）。
4. **[T2]** B4/B5（`GameVersion` 字段 + UI 标识）+ patches 折叠验证。
5. **[T4]** rules 求值 / `--tweakClass` / 边角。
6. **[T3 探针]** 先用真实 Fabric 实例验类加载器（见 §7）。

## 7. 验证计划

- 静态：`check_ets_files`（ArkTS）、`check_cpp_files`（如动 native）；改 Java 后由用户 `build_meow_launcher.sh`。
- 构建：`devecocli build`（视改动带 `--modules`）；部署先 HSP 后 entry。
- 实机（UI 交互归用户）：
  - **T3 探针**：装一个真实 Fabric 实例，首次启动看是否因 `KnotClassLoader`/`MeowClassLoader` 失败；
  - 形态①（官方 `inheritsFrom`，如 1.20.1）能否进游戏；
  - 形态②（HMCL `patches`）能否进游戏；
  - 回归：≤1.16 Fabric 应走 gl4es、≥1.22 应选 LWJGL 3.4.3。
- 结论落 notes（`.logs/` 非凭据）。

---

## 8. 证据索引

| 结论 | 位置 |
|---|---|
| 判定键 / schema / 合并规则 | `ref/HMCL/HMCLCore/.../game/{GameInstanceManifest,GameInstancePatch,Arguments,Argument,Library,GameComponentType}.java` |
| ArkTS 现状消费面 | `entry/src/main/ets/common/data/{VersionScanner,MinecraftLauncher,GameLauncher,RendererPolicy,ClasspathStager}.ets` |
| Java 现状 | `tools/meow-launcher/src/meow/launcher/{MeowLauncher,VersionLoader,VersionJson,LibraryResolver,ArgBuilder,MeowClassLoader}.java` |
| HMCL 机制调研全文 | [`Fabric支持-调研.md`](../20-design/launch/Fabric支持-调研.md) |

---

## 9. 实施进度（2026-09-13）

- ✅ **ArkTS 新增** `common/data/VersionResolver.ets`：三形态判定 + `inheritsFrom`/`patches` 归一，产出 `mcVersion`（真 MC 版本）/`loader`；静态检查通过。
- ✅ **ArkTS 消费面**：`readVersionId` → 解析后 `mcVersion`；`lwjglGeneration`/`isLegacyLwjgl`/`collectJarSources`/`buildLaunchArgv` 走解析清单；`collectFromJson` 补 **name→maven 回退**（Fabric 库仅 `name`+`url`）；`GameVersion` 加 `loader`/`mcVersion`（副行 `JRE x` 改用解析后值 —— Fabric 继承 vanilla 的 javaVersion，不再误显示 8）。
- ✅ **Java**：`VersionJson` 加 `jar`/`assetIndex`；`VersionLoader.inherit` 继承二者；**`LibraryResolver` 按 `jar`/`inheritsFrom`/id 解析"基座客户端 jar"（形态①要害）**；`ArgBuilder` assetIndex 回退。`EXTRAS_VERSION` → `20260913-fabric2`（改 jar 后升，2026-09-13）。
- ⏸ **Java `applyPatches` 暂不做**：HMCL 写盘已把 `patches` 扁平化到顶层字段、且为实例复制了 `<id>.jar`，形态②经 Java 现有"顶层读取 + 实例 jar"即可启动；实机状态见 [`现状基线.md`](../00-current/现状基线.md) §5 第 17 条（形态②已验、形态①搁置），若日后证伪再补（即 C2 降级为条件项）。
- ✅ **版本卡片「编辑」区新增「版本类型」行**（原版 / Fabric / Legacy Fabric / 未知）——`GameVersion.form` 由解析器提供；「未知」= 有继承/补丁形态但识别不出加载器（Forge/NeoForge/Quilt/整合包等，暂不点名）。原计划的"卡片 Fabric 徽标"以此替代。
- ✅ **已验证（2026-09-13，见 §9.1/§9.2）**：`devecocli build` 通过；`launcher.jar` 已重打（Java 由用户 `javac`）；**形态② `patches[]` 实机进游戏**；T3 类加载器问题已定位并修复（Fabric 实例不设 `-Djava.system.class.loader`）。
  ⏸ **仍未验**：**形态①（官方安装器 `inheritsFrom`）**——无实例可测，2026-09-13 起搁置（见 §9.2）。

### 9.1 T3 实测与修法（2026-09-13，形态② HMCL `patches[]`）

- 🔎 **实测**：版本解析 / LWJGL 世代（`gen=3.4.3`）/ 渲染后端 / mainClass 覆盖（`KnotClient`）**全通**，Fabric `Knot.launch` 已进入；崩溃于
  `IllegalStateException: trying to load net.fabricmc.loader.impl.FabricLoaderImpl from target class loader`（`LoaderUtil.verifyNotInTargetCl`），
  伴 `MixinExtras`（loader `knot`）与 `IMixinConfigPlugin`（loader `app`）**跨加载器 `ClassCastException`**。
- 🔎 **根因**：我方 `-Djava.system.class.loader=meow.launcher.MeowClassLoader`（HMCL 标准路径无此项）使 Fabric 的
  "**loader 类由父加载器持 / game 类由 `KnotClassLoader` 持**"契约被破坏——Fabric 用 `KnotClassLoader.class.getClassLoader()` 定父加载器，
  loader 类被 target 加载即触发校验失败。
- 🔧 **修法（已实现）**：① Fabric 实例**不设** `-Djava.system.class.loader`（改由默认 app classloader 持 loader 类）；② 把**基座客户端 jar** 补进平铺
  classpath（`ResolvedVersion.clientJarId`，叶子目录常无 `<id>.jar`）；③ `MeowLauncher` 兼容"系统 CL 非 `MeowClassLoader`"（不追加 classpath、直接用系统 CL 加载主类）。
  vanilla 路径不变（保留自研 system CL 的运行期追加）。

### 9.2 实机结果（2026-09-13，用户实测定案）

- ✅ **形态②（HMCL `patches[]`）Fabric 实例 `26.2-Fabric` 实机进游戏、正常退出**（用户实测；该 json 顶层已由 HMCL 扁平化且含 `patches`、`id`=目录名、未见 `inheritsFrom`）。
  证据链（用户导出 hilog，非持久凭据）：`stage … gen=3.4.3` 正确选代；**CMD 中已无 `-Djava.system.class.loader`**（修复生效）；
  `MeowLauncher → KnotClient → Knot.launch`；LWJGL 3.4.3 各 native 加载；`created desktop OpenGL 4.2 (core) context`；
  OHAudio `probe … latency=25 ms`；末行 `JLI_Launch returned 0`（正常退出、无 crash report）。
- ⏸ **形态①（官方安装器 `inheritsFrom`）尚未实机验证** —— **2026-09-13 起搁置**：用户无官方 profile 实例可测；逻辑路径已具备（Java `VersionLoader` 合并父链 + ArkTS `clientJarId` 取链根），待日后有实例再验。
- 非阻断观察（与 Fabric 无关，既有现象）：Zink `SSBO is readonly in vertex stage!` 刷屏 + "incorrect rendering" 告警（见 [`已知限制与待解.md`](../00-current/已知限制与待解.md) B3）；
  系统 `igraphics_config_cust.xml` 缺失致 "GT Disable by not support / Disable hook"（A4 一类）；
  OpenAL `OpenAL10 / AL_SOFT_callback_buffer / AL_SOFT_events` "entry point is missing"（LWJGL 能力探测噪声，声音正常）。

### 9.3 独立 code review（2026-09-13，5 路并行）

结论：**vanilla 零回归、隔离改动干净、Java 主路径等价**；修掉了若干健壮性/边界缺陷。

- 已修（本轮）：① `VersionResolver` 加**类型守卫**（`inheritsFrom: null` / `patches` 非数组 / 元素为 null 不再抛）＋ `resolveVersion` 整体 try/catch；
  ② `priority` 缺省由 `0` 改为 `Number.MIN_SAFE_INTEGER`（对齐 HMCL 对 null 返回 `Integer.MIN_VALUE` → 缺省者排最前）；
  ③ 补丁式**有效清单 `id` 复位为实例 id**、继承态**叠加自身 patches**（混合形态，对齐 HMCL `resolve`）；
  ④ `detectLoader`：`net.fabricmc:fabric-loader` **精确匹配**、识别 patch id `legacyfabric`；
  ⑤ `MinecraftLauncher` 自研 system CL 的**设置条件收紧为"仅原版"（`form===VERSION_FORM_VANILLA`）**——非 Fabric 的加载器实例也不再误设。
- 已知/暂不动（低风险，记录在案）：Java `VersionLoader` 只展开**一层** `inheritsFrom`（多级叠加不支持）；`resolveJarId` 对显式 `jar` 字段优先（Mojang 语义正确，可能改变"jar≠id"历史版本的 classpath）；Fabric 分支下 `LibraryResolver.build` 仍被白算（仅噪声）；ArkTS 与 Java 的 maven 回退实现细节略有差异（`@ext`/classifier）。
- 核查面：VersionResolver / ArkTS vanilla 回归 / Java / 隔离+安装 / 集成+规范+清理（5 路互斥）。
