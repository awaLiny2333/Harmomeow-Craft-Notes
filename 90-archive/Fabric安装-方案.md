# Fabric 安装方案（下载面板选 loader → 装单实例）

> 已归档（2026-10-01；因为 Fabric 安装结论已并入现役档（安装链-总览 §2）；现役口径见 [`安装链-总览.md`](../20-design/launch/安装链-总览.md)）。

> 日期：2026-09-13 ｜ 状态：**已提交（`e9234c3` feat + 文档 `c4b5e7d`，均为 HEAD `8c62c0d` 祖先）并实机验证（用户 2026-09-15 确认）** ｜ 形态：**B. HMCL 补丁式（单实例）**
> ⚠️ **该"状态"为当时记录，非现状**；仅存档，勿引用。
> 依据：HMCL 源码（`download/fabric/*`、`download/{BMCLAPIDownloadProvider,DefaultGameBuilder,DefaultDependencyManager}.java`）+ 自家安装代码调研 + Fabric 官方 meta 实测。
> 相关：[`Fabric支持-调研.md`](../20-design/launch/Fabric支持-调研.md)（启动机制）、[`Fabric支持-改动方案.md`](Fabric支持-改动方案.md)（启动改动）。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 17 条](../00-current/现状基线.md)。

---

## 0. 结论速览

- **单实例**：`versions/<名>/<名>.json` = **顶层扁平化** + `root:true` + `jar:"<名>"` + `patches:[game, fabric]`。
- **客户端 jar** 落 `versions/<名>/<名>.jar`（HMCL 同款；Java 端 form② 靠顶层 `jar` 找它）；库落**共享 `libraries/`**（maven 布局）；assets 共享。
- **源**：Fabric 的 meta/maven 走 **该 loader 自己的下载源**（**独立于版本源**，2026-09-13 用户拍板，见 §2）——镜像(BMCLAPI) 走 `/fabric-meta`、`/maven`，官方直连；UI 放进该 loader 的子面板。

## 1. Fabric 端点（2026-09-13 实测）

| 用途 | URL | 返回 |
|---|---|---|
| loader 列表（按游戏） | `https://meta.fabricmc.net/v2/versions/loader/<game>` | 数组：`{ loader:{version,stable,maven,separator,build}, intermediary:{maven,version,stable}, launcherMeta:{ mainClass:{client,server}, libraries:{client[],common[],server[],development[]} } }` |
| 单点安装元数据 | `…/v2/versions/loader/<game>/<loader>` | 单条（同上结构） |

- 取 `launcherMeta.mainClass.client`（= `net.fabricmc.loader.impl.launch.knot.KnotClient`）。
- 取 `launcherMeta.libraries.common`（+`server`，常空）；**忽略 `client`/`development`**（HMCL 同款：硬编码只取 common+server）。
- 追加两条坐标（`url=https://maven.fabricmc.net/`）：`intermediary.maven`、`loader.maven`。
- 注：26.x 的 `intermediary` 版本可能是 `0.0.0`（按端点原样用）。

## 2. 源路由（**每个 mod loader 独立源** —— 2026-09-13 用户拍板）

- 镜像适配（HMCL 同款，`BMCLAPIDownloadProvider.java:90-91`）：`meta.fabricmc.net` → `<BMCLAPI_ROOT>/fabric-meta`；`maven.fabricmc.net` → `<BMCLAPI_ROOT>/maven`。
- **决策：mod loader 的下载源与"版本下载源"分开** —— **每个 mod loader 有自己独立的源选择**（起初仅 Fabric：`镜像(BMCLAPI) / 官方`；后按同一原则扩到 Forge `forgeSource` / NeoForge `neoForgeSource`，决策见 [`实例设置存储-方案.md`](../20-design/launch/实例设置存储-方案.md) §2.1），持久化为独立项 `fabricSource`（2026-09-15 起存**应用级全局设置** `app-settings.json` 的 `global.network.fabricSource`），**不复用版本源 `downloadSource`**；UI 放进该 loader 的子面板（loader 版本选择旁）。
- 含义：Fabric 的 loader 列表、单点安装元数据、fabric 库（maven）下载，**全部按 loader 源**取候选 → 即传给 §3 的 `fetchFabricLoaders`/`installFabricVersion` 的 `source` = **loader 源**，而非版本源。

## 3. 改动清单

1. **`DownloadContract.ets`**：`FABRIC_META_ROOT` / `FABRIC_MAVEN`；`BMCLAPI_REWRITES` 加上述两条；`fabricLoaderListCandidates(game, source)`、`fabricLaunchMetaCandidates(game, loader, source)`。
2. **`VersionInstaller.ets`**（复用其私有 `mavenPath`/`libraryItem`/`runDownloads`/`writeText`）：
   - `export interface FabricLoaderVersion { version: string; stable: boolean; }`
   - `fetchFabricLoaders(gameVersion, source)` → 列表映射 `{version,stable}`（新版在前）。
   - `installFabricVersion(gameRoot, gameRemote, loaderVersion, instanceName, source, callbacks)`：
     1. 取 vanilla json（`gameRemote.url` 原文+解析）→ client jar / 库 / assets；
     2. 取单点 meta → `mainClass`/`libraries.common+server`/`intermediary`/`loader`；
     3. 下载：client jar → `versions/<名>/<名>.jar`；vanilla 库 + fabric 库（`lib.url` 回退）→ `libraries/`；assets（索引+对象）；
     4. 组装并写 `<名>.json`：**顶层扁平化**（`mainClass`、`libraries`=vanilla+fabric、`arguments` 合并、`assets/assetIndex/type/time/releaseTime/javaVersion/downloads` 取 vanilla）+ `root:true` + `jar:"<名>"` + `patches:[game, fabric]`。
3. **`InstallerState.ets`**：`loaderKind`/`fabricLoaders`/`fabricLoadersLoading`/`fabricLoadersLoaded`/`fabricLoader`；`refreshFabricLoaders(game)`；`installFabric(...)`（复用 `installingId` 占用与错误码）。
4. **`GameVersionsView.ets`**：「设置实例名」面板 `TextInput` 右侧加「加载器」`Select`（原版/Fabric）；选 Fabric 时下方新增 **loader 子面板**＝**该 loader 的下载源** `Select`（镜像/官方，独立项 `fabricSource`）+ **loader 版本选择**（loading/失败/空/成功 四态 + 单选，默认最新）；确认时分流：原版→`installRemote`，Fabric→`installFabric`。
   - 新增持久化项 `fabricSource`（2026-09-15 起存应用级全局设置 `global.network.fabricSource`，见 [`实例设置存储-方案.md`](../20-design/launch/实例设置存储-方案.md) §3.2）+ `SettingsTools` 读写（与 `downloadSource` 同款式，但**互不影响**）。
5. **`string.json`**：加载器/原版/Fabric/loader 版本/拉取失败等文案。

## 4. 分阶段与难度

| 阶段 | 内容 | 难度 | 风险 |
|---|---|---|---|
| T1 | 常量 + 拉 loader 列表 | 低 | — |
| T2 | **json 组装（game+fabric patch + 顶层扁平化）** | 中 | 扁平化字段须与 Java `VersionJson`「读顶层」一致，否则启动失败 |
| T3 | 下载（client jar→`<名>.jar`、fabric 库、assets 复用） | 中低 | 复用现成原语 |
| T4 | State + UI（下拉/版本子面板/确认分流） | 中 | — |

## 5. 未知 / 待验（不确定则派 agent 查 HMCL 或实测）

- 顶层扁平化的**精确字段集**（须对齐 Java `VersionJson`：`id/inheritsFrom/jar/mainClass/assets/assetIndex/type/releaseTime/javaVersion/minecraftArguments/arguments/libraries`）。
- Fabric profile 是否带 `assetIndex`（一般不带 → 从 vanilla 继承）。
- 无镜像时 `meta.fabricmc.net`/`maven.fabricmc.net` 直连通达性（本机此前可直连）。

## 6. 进度（2026-09-13）

- ✅ **T1**：`DownloadContract.ets` — Fabric 常量 + 镜像路由（`/fabric-meta`、`/maven`）+ `fabricLoaderListCandidates`/`fabricLaunchMetaCandidates`。
- ✅ **T2+T3**：`VersionInstaller.ets` — `fetchFabricLoaders(game, loaderSource)` + `installFabricVersion(gameRoot, gameRemote, loaderVersion, instanceName, loaderSource, callbacks)`：
  - **整条链按 `loaderSource`**（Fabric 自己的源）：vanilla 文件（client jar → `versions/<名>/<名>.jar`、原版库、资源索引 + 对象）与 **Fabric 库**（`libraries.common+server` + `intermediary` + `loader`，url=`maven.fabricmc.net/`）同源；原「vanilla 件走版本源」的拆分已删除（2026-09-29 对齐 HMCL，决策见 [`实例设置存储-方案.md`](../20-design/launch/实例设置存储-方案.md) §2.1）；
  - 写 `<名>.json` = **顶层扁平化**（`id/jar=<名>`、`root:true`、`mainClass=KnotClient`、`libraries`=vanilla+fabric、其余随原 vanilla 字段保留）+ **`patches:[game,fabric]`**；`gamePatch.version=gameVersion`（供 ArkTS 取真 MC 版本）。
  - `check_ets_files` 绿 + `devecocli build` 成功。
- ✅ **T4**：`Constants.ets` 加 `KEY_FABRIC_SOURCE`；`SettingsTools` `fabricSource/setFabricSource`；`InstallerState` 加 `loaderKind`/`fabricSource`/`fabricLoaders*`/`fabricLoader` + `refreshFabricLoaders`/`setFabricSource`/`installFabric`（错误码 `INSTALL_ERR_LOADER`）；`GameVersionsView`「设置实例名」面板：实例名右侧加**加载器下拉**（原版/Fabric），选 Fabric 时下方出 **loader 子面板**（Fabric 下载源 Select + loader 版本 List/四态），确认分流 vanilla/fabric。`check_ets_files` 绿 + build 成功 + 已部署。
- ✅ **已实机验证（用户 2026-09-15 确认）**：装出 Fabric 实例并可启动。

### 6.1 实机问题与修法（2026-09-13）

- 🐞 **启动即崩**：装好的 Fabric 实例（1.21.10）启动报
  `IllegalStateException: duplicate ASM classes found on classpath: …/mc-cp/<id>/asm-9.6.jar 与 …/asm-9.10.1.jar`（Fabric `LoaderUtil.verifyClasspath`）。
- 🔎 **根因**：vanilla 自带 `org.ow2.asm:asm:9.6`，Fabric meta 的 `libraries.common` 带 `asm:9.10.1` → 合并后 classpath 上 ASM **两份**；Fabric Knot 要求**恰好一份**。
- 🔧 **修法**：`VersionResolver` 增**库去重**（同 `group:artifact` 留**最高版本**、位置保持首次出现、分类器变体保留）＝对齐 HMCL `uniqueLibraries`；在 `resolveVersion` 对有效清单执行 → 平铺 `-cp` 只剩 `asm-9.10.1.jar`（`ClasspathStager` 的残留清理会删掉旧 `asm-9.6.jar`）。vanilla 无重复 → 零改动。
- ✅ 修后 build 通过、已部署；**已实机验证（用户 2026-09-15 确认）**。

### 6.2 手机 Fabric 首次 remap 崩（用户存储 FUSE 拒 chmod，2026-09-27）

- 🐞 **现象**：手机（HUAWEI Mate XT）上装好的 Fabric 实例**首次启动崩**（未进主菜单）。
- 🔎 **根因**：Fabric 的 `tiny-remapper` 经 `jdk.zipfs` 往 `<gameDir>/.fabric/remappedJars/*.jar` 写盘；`ZipFileSystem.sync()` 会**无条件** `Files.setPosixFilePermissions`（chmod），而手机游戏目录在**用户存储**（FUSE/hmdfs，**拒绝 chmod**）⇒ `Operation not permitted` ⇒ Fabric 崩。
- 🔧 **修法**：把那次 chmod 改成 **best-effort**（失败即忽略，**被写 jar 字节不变**），用 JDK 官方 **`--patch-module jdk.zipfs=<jreHome>/lib/patch/jdk.zipfs`** 投放（**只覆盖 `jdk.zipfs` 一个模块的类；不动 `lib/modules`(jimage) / `jmods` / 模块哈希；不 patch `java.base`**）。属**平台坑**（用户存储拒 chmod），不在 MC/模组侧。补丁本体/构建 = 主仓 `tools/jre26/{patches/zipfs_chmod_best_effort.py,linux_build_zipfs_patch.sh}`；随包数据变 ⇒ **令牌升 `-r2`**。
- ✅ **已实机验证（用户 2026-09-27 确认）**：手机 Fabric **能直接进游戏 + 后续装 mod 也没问题**。
- 详见 [`现状基线.md`](../00-current/现状基线.md) §5 第 27 条、[`已知限制与待解.md`](../00-current/已知限制与待解.md) §F、主仓 `tools/jre26/README.md` §6。

### 6.3 代码评审与修补（2026-09-13）

- 🔎 **评审**：对未提交的 Fabric 安装改动集派 5 个 agent 分头评审（`VersionInstaller` / `VersionResolver` / `InstallerState`+`DownloadContract` / `GameVersionsView` UI / `FileAccess`）。
  结论：**原版链路零回归**；Fabric 链路发现 6 处缺陷，逐条核实（读代码 + 官方文档 + Fabric 官方 meta 实测）后修补。
- 🐞 **①** `VersionResolver.dedupLibraries` 只按 `group:artifact` 去重、**忽略 `rules`** → 规则不同的平台变体被错误合并。
  🔧 加 `sameRules()` 判等：规则不同则不合并。
- 🐞 **②** loader 列表拉取**竞态**：`fabricLoadersLoading` 早退会**丢弃**请求；且切源 / 换游戏版本 / 重开安装面板后，**在途旧响应会覆盖**新状态。
  🔧 加请求序号 `fabricLoaderSeq`（非观察态）：响应仅在仍是最新序号时写入；新增 `resetFabricLoaders()`（自增序号 + 清列表），由 `setFabricSource` 与 `openInstallPanel` 调用。
- 🐞 **③** `installFabric` 只校验 loader 版本非空，**未校验该列表对应本次要装的游戏版本**（陈旧列表可能被用）→ 硬门 `fabricLoadersGame === remote.id`，不符报 `INSTALL_ERR_LOADER`。
- 🐞 **④** 「打开文件夹」用 `fileUri.getUriFromPath(物理路径)` → 得到**应用沙箱 URI**（`file://<bundleName>/...`），文件管理器是**另一个应用**，解析不了 → 打不开。
  🔧 目标 URI 改由「**已授权目录 URI + 相对子路径**」拼出（新增 `Paths.versionDirUri`）＝公共目录 URI 形式（`file://docs/storage/...`）。
  📚 依据：官方 FAQ「如何跳转到系统文件管理App界面」（`faqs-ability-116`）+「应用沙箱路径及访问URI的大小写分段规则」（`faqs-local-file-manager-49`：`/storage/Users/<user>/Documents` ↔ `file://docs/storage/Users/<user>/Documents`）+ fileuri 文档构造示例（`getUriFromPath` 产出 `file://<packageName>/...`）。
- 🐞 **⑤** Fabric 库缺 `url` 时 `libraryItem` 回退到 `DEFAULT_LIBRARY_URL`（**Mojang 库仓**）→ Fabric 产物取错仓库。
  🔧 新增 `withFabricUrl()`：缺 `url` 的 Fabric 库一律补 `FABRIC_MAVEN`（实测 Fabric meta 的库本就都带 `url=https://maven.fabricmc.net/`，此为防御）。
- 🐞 **⑥** `fetchFabricLoaders` 未防 meta 数组里的 `null` 项 → `entry.loader` 抛异常。
  🔧 按 `(FabricMeta | null)[]` 解析，逐项判空跳过。
- ✅ 修后 `check_ets_files` 绿（`FileAccess` 仅剩 Picker 的既有 `28057` 警告、非本次改动）+ `devecocli build` 成功 + 已部署。
- ✅ **已实机验证（用户 2026-09-15 确认）**：④「打开文件夹」正常；②③⑤⑥ 属边界，未单独记录复测（② 竞态可「快速切源 / 换版本 / 重开面板」观察）。
- ✅ 用户已确认：④「打开文件夹」正常。

### 6.4 独立复核（第 2 轮，2026-09-13）——4 个只读子 agent

分头独立复核：①HMCL 安装对齐 + 实例互操作 ②原版零回归 ③启动侧 json 契约 ④Fabric meta / 源契约。

**对齐结论**：库集合（`common`+`server`，忽略 `client`/`development`）、`intermediary`/`loader` 追加与 url、`mainClass` 取 client、补丁 priority（`0` / `30000`）、补丁 id（`game` / `fabric`）、`versions/<id>/<id>.json` 布局——均与 HMCL 一致。
**互操作**：HMCL 写盘同样是「**顶层扁平化 + 保留 `patches[]`**」（`DefaultGameBuilder.withPatches` + `GameInstanceManifest` 重建）→ **双向可读**；镜像路由 `/fabric-meta`、`/maven` 与 HMCL 一致（curl 实证：302 跳转后字节数一致）；26.x `intermediary=0.0.0` 确有制品（实测 200 / 572B）。
**已核实非问题**：③ 的 F4「顶层缺 `arguments`」不成立——`composeFabricManifest` 就地复用 vanilla，顶层 `arguments`/`minecraftArguments`/`logging` 等未声明字段随 `JSON.stringify` 原样保留。
**用户改动不回退**：② 的 B2（`download_install` 值改为图标字形）是用户自己的改动（鸿蒙内置字体），不动。

**🐞 BLOCKER（实测：我们在第 1 轮确实破坏了原版）——第 1 轮 ① 的去重把「同名 natives 条目」当重复合并掉了。**
- 根因：Mojang 1.12–1.18 清单里同一 `group:artifact:version` 有**两条同名条目**——普通 jar + 只多 `natives`/`downloads.classifiers` 的原生包；去重键只看 `group:artifact` + `rules`，二者被判重复 → 原生包被丢。
- 实测（真实 piston-meta，脚本比对）：1.13.2 丢 **7** 条 natives（含 `org.lwjgl:lwjgl:3.1.6` 的 linux/osx/windows）、1.12.2 丢 `text2speech`(linux/windows)、1.14.4 / 1.16.5 / 1.18.2 各丢 7–8 条（macOS 变体）；样本合计 **31** 条丢弃。→ 本机（linux/aarch64）**1.13.2 会缺 `natives-linux` 而启动失败**。
- 修法（最小、保 ASM 语义不变）：`VersionLibrary` 补 `natives` / `downloads.classifiers` 建模；新增 `sameNative()`；互斥条件由「`rules` 相同」扩展为「`rules` 相同 **且** 原生载荷相同」（对齐 HMCL `Library.equals` 计入 `isNative()`）。
- **复验（同一脚本）**：全部样本 **natives lost = 0**；1.21.4 vanilla asm 原样不动；vanilla(asm 9.6) + Fabric(asm 9.7.1) 合并后 classpath 上 ASM **恰好 1 条**（9.7.1）且 fabric 库完整 → 原 ASM 修复未被破坏。

**🐞 新代码竞态（已修）**：`resetFabricLoaders()` 未清 `fabricLoadersLoading`；在途请求被作废后 `finally` 因序号不匹配不再清标志 → 该标志可能永久为 `true`。修：reset 里一并置 `false`。

**待定（已记录、未改）**：

| 项 | 级别 | 说明 |
|---|---|---|
| game patch 缺 `logging` / `complianceLevel` / `compatibilityRules` | MINOR | 只影响「**HMCL 读我们装的实例**」时丢 log4j 配置；我们自己的启动端读顶层，不受影响 |
| Fabric 不支持的游戏版本：端点返回 `400 []`，而 `fetchText` 仅认 2xx → 显示「拉取失败 + 重试」而非「无可用版本」 | MINOR | 与 HMCL（交叉相乘 → 无匹配 → 空）行为不同 |
| 版本比较 `localeCompare` / `.` 分段 | NIT | `9.10.1 > 9.6` 正确；`+build`、`RC2 vs RC10` 不严谨 |
| 安装器既有缺口（**非本次引入**）：已存在文件不重校验、natives 描述符探测窄于 HMCL、缺 client jar 兜底 URL | MINOR | 与本改动集无关，属原版安装器历史状态 |
| Java 启动端不建模 `patches` | 观察 | 我们写盘顶层已扁平化（Java 读顶层）且实测可启动；HMCL 自写实例亦顶层扁平化 → 实测兼容；仅「纯 patches-only 外部文件」Java 侧不认（须先经 ArkTS 归一） |

### 6.5 第 2 轮复核的处置（2026-09-13，用户选定后实施）

用户选定：修下列 3 项；**已提交（`e9234c3` + 文档 `c4b5e7d`）并实机验证（用户 2026-09-15 确认）**。

1. **game patch 补 `complianceLevel` / `compatibilityRules` / `logging`**（已修）：`VersionInstaller` 的 `VersionJson` / `PatchJson` 建模这三项（`LoggingEntryJson` 原样透传），`composeFabricManifest` 从 vanilla 顶层复制进 `game` patch。
   依据：HMCL `GameInstancePatch.fromManifest` 取 `manifest.complianceLevel()/compatibilityRules()/logging()`；`GameInstanceManifest` 的 JSON 键名即 `complianceLevel` / `compatibilityRules` / `logging`。→ HMCL 读我们装的实例不再丢 log4j 配置。
2. **Fabric 不适用的游戏版本 → 按「无可用版本」处理**（已修）：`DownloadContract` 加 `HTTP_STATUS_BAD_REQUEST` / `HTTP_STATUS_NOT_FOUND`；`Downloader.fetchText(candidates, alsoAccept?)` 新增**可选**参数（不传＝只认 2xx，原行为不变）；`fetchFabricLoaders` 传 `[400, 404]`。→ 不再把 `400 []` 误报为「拉取失败 + 无效重试」。
3. **版本比较改为确定性**（已修）：`compareArtifactVersions` 重写——先剥 `+build` 元数据（Maven/semver 的 build metadata 不参与优先级），再把版本切成「数字 / 非数字」交替片段逐段比较（数字按数值、其它按码点），**去掉 `localeCompare`**（locale 无关）；`allDigits` 保留复用。
   - 单测（脚本）：`9.10.1 > 9.6` ✓、`1.0.0-RC10 > 1.0.0-RC2` ✓、`9.7.1+build == 9.7.1` ✓、`0.13.3+mixin.0.8.5 < 0.15.11` ✓。
   - 回归复验：9 个版本 **natives lost = 0**；3 组 vanilla + Fabric 合并 **ASM 恰好 1 条** → 前两个修复未被破坏。
- ✅ `check_ets_files` 绿（先遇一次跨文件陈旧缓存 → `deveco-mcp_restart` arkts 后复检绿）+ `devecocli build` 成功 + 已部署。
- ✅ **已提交**（`e9234c3` + 文档 `c4b5e7d`，均为 HEAD `8c62c0d` 祖先）**并实机验证（用户 2026-09-15 确认）**：装 Fabric 实例可启动。建议的 legacy 回归（如 1.13.2，其原生库路径正是本轮 BLOCKER 的受害面）**未单独记录复测**。
