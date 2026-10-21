# Forge 支持调研 —— HMCL 的版本面/下载源 + 两形态安装链 + 盘上格式（证据存档）

> 日期：2026-09-28 ｜ 定位：**证据存档 / 调研结论**，**不复述现状**。
> **我方对 Forge 的支持状态**见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 22 条 与 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §E（Forge 在 loader 支持表里归「未知」档）。
> 方法：**两路子 agent 并行**（A 线 = 版本面/下载源；B 线 = 安装执行/盘上格式），主会话汇总；**§11 为 T0 真件取证轮；其覆盖口径以 §11 为准**。
> 原始报告（工作区根）：`stuffs/research/hmcl-forge/A-forge-versions-download.md`、`stuffs/research/hmcl-forge/B-forge-install-format.md`（本文件为其入库版，正文搬运 + 交叉引用）；T0 取证见 **工作区根** `stuffs/research/forge-support/evidence/T0-findings.md`（11 个真 installer）。
> 只读范围：`ref/HMCL/HMCLCore/src/main/java/org/jackhuang/hmcl/{download/forge,download,game}/`；行号对应 2026-09-28 的源码。
> 姊妹篇：[`Fabric支持-调研.md`](Fabric支持-调研.md)（Fabric 的启动机制与形态）、[`NeoForge支持-调研.md`](NeoForge支持-调研.md)（NeoForge 三链 + 真 installer 解剖）、[`NeoForge安装链-逐行取证.md`](NeoForge安装链-逐行取证.md)、[`NeoForge无JVM安装-可行性与取证.md`](NeoForge无JVM安装-可行性与取证.md)。

## 0. 结论速览

1. **支持面由远端元数据决定，不写死**：HMCL 能给「远端版本表里存在 Forge 制品的任意 MC 版本」装 Forge；代码只特判 `1.7.10-pre4 ↔ 1.7.10_pre4`（`ForgeVersionList.java:48-54`）。
2. **只有一个下载物 = installer jar**：老/新形态都下 installer jar；**universal jar 不单独下载**（老形态从 installer 内本地解包，`ForgeOldInstallTask.java:76-86`）。
3. **两形态靠 `install_profile.json` 的键判定**：含 `spec` → **新形态**（processor 式，逐个起外部 `java`）；含 `install`+`versionInfo` → **老形态**（纯解包，**零 JVM**）；否则 `IOException`（`ForgeInstallTask.java:141-153`）。
4. **零 JVM 安装面比原先以为的更宽**（2026-09-28 T0 实测，见 §11）：`ForgeOldInstallTask` 那条**真老形态只覆盖 ≤1.8.9**；而 **1.12.2 已是 `spec:0` 但 0 个 processor** ⇒ 纯复制内嵌 universal + 组装 json，**同样不需要 JVM**。⇒ **"安装要不要 JVM"的真正判据是 client 侧 processor 数 > 0，不是 `spec` 有无**；对 phone 侧的参考价值同 [`NeoForge无JVM安装-可行性与取证.md`](NeoForge无JVM安装-可行性与取证.md)。
5. **盘上格式 = 顶层扁平 + 保留 `patches[]`**，`<id>.jar` 是**原版 client jar 的复制件**（不是 loader jar），库落共享 `libraries/`（仅 `hint=="local"` 才落实例内），**不留** `install_profile.json` / installer（`DefaultGameBuilder.java:173-174`、`GameInstanceManifest.java:592-657`）。

## 1. 支持面（版本段 × 制品形态）

> ⚠️ 下表第 2 行按 **T0 实测（§11）** 拆分：`install`+`versionInfo` 只到 1.8.9；1.12.2 起都已是 `spec` 形态。

| 版本段 | 是否支持 | 制品形态 / 判据 | 证据 |
|---|---|---|---|
| 1.7.10-pre4 与 1.7.10 | 是（查表名特判 `1.7.10_pre4`） | installer jar | `ForgeVersionList.java:48-54` |
| **≤1.8.9**（真老形态） | 是 | 下 installer.jar，**本地解包内嵌 universal**；`install_profile.json` 含 `install`+`versionInfo`、**无 `spec`** | `ForgeInstallTask.java:146-150`、`ForgeOldInstallTask.java:70-93`、T0 §1 |
| **1.12.2**（`spec:0`、0 processor） | 是 | installer 内 `maven/…/<id>.jar` 纯复制（无 processor ⇒ **不跑 JVM**） | T0 §1 |
| 1.13+（processor installer） | 是 | 下 installer.jar，读内嵌 version json，跑 processor（`spec:0`/`spec:1` 皆是） | `ForgeInstallTask.java:141-145`、`ForgeNewInstallTask.java:306-308`、T0 §1 |
| 1.13+ 主类约束 | 视情况 | `gameVersion>=1.13` 时主类不在 `FORGE_OPTIFINE_MAIN` 就抛 `UNSUPPORTED_LAUNCH_WRAPPER` | `ForgeInstallTask.java:110-114` |
| 快照（snapshot） | **未确认** | 代码无 release/snapshot 之分，取决于元数据 key | 见 §8 |

## 2. 版本列表来源与解析链（两个源 + 逐源降级）

**源 A｜官方（`MojangDownloadProvider` → `ForgeVersionList`）**
- 常量 `FORGE_LIST = https://hmcl.glavo.site/metadata/forge/`（**HMCL 自托管元数据，不是 Forge 官方 promotions**），GET 后反序列化为 `ForgeVersionRoot`（`ForgeVersionList.java:58-59,99`）。
- `ForgeVersionRoot` 字段：`artifact/webpath/branches/mcversion/promos/number`（`ForgeVersionRoot.java:33-41,87-97`）；`promos` 被解析但**本类未使用**（`:91-93`）。
- 遍历 `mcversion`（gameVersion→`int[]` buildId）→ 按 id 从 `number` 取 `ForgeVersion`（branch/mcversion/jobver/version/build/modified/files[][]）（`ForgeVersionList.java:67-72`、`ForgeVersion.java:31-37`）。
- 只匹配 `files` 中 `category=="installer"` 的项，按 `classifier = gameVersion-version[-branch]` 拼 URL：`webpath + classifier + "/" + artifact-classifier-installer.<fmt>`；**无 installer 项则跳过**（`ForgeVersionList.java:74-83`）。

**源 B｜BMCLAPI（`BMCLAPIDownloadProvider` → `ForgeBMCLVersionList`）**
- **整表刷新抛 `UnsupportedOperationException`**，只支持按 MC 版本刷新（`ForgeBMCLVersionList.java:56-58`）。
- GET `apiRoot + "/forge/minecraft/" + lookupVersion` → `List<ForgeVersion>`（内部类字段 `branch/build/mcversion/modified/version/files(format,category,hash)`）（`:79,137-141,201-204`）。
- 只取 `category=="installer" && format=="jar"`，生成 **3 个候选 URL**（Forge maven 两种布局 + BMCLAPI `/forge/download?mcversion=&version=&branch=&category=&format=`）（`:90,93-104`）。
- 失败语义：**200+空** ⇒ 清空后返回（不报错）；**4xx** ⇒ `GetTask` 抛异常使任务失败（`:83-84`；源 A 同理 `ForgeVersionList.java:63-64`）。

**多源顺序与降级**：各 provider 的列表按顺序组成 `MultipleSourceVersionList`（`AutoDownloadProvider.java:104-112`）；`refreshAsync(gameVersion)` 从 index 0 起、失败换下一个源、全部失败才抛（`:175-198`）。⇒ **顺序由构造方决定（未确认谁优先）**。

## 3. 两条安装链（按 `install_profile.json` 判型）

判型（开只读 zip）：含 `spec` → 新；含 `install` **且** 含 `versionInfo` → 老；否则 `IOException`（`ForgeInstallTask.java:137-155`）。构造前置：manifest 必须可改（顶层非 `inheritsFrom` + 有 `patches` + 有 GAME patch），否则抛（`ForgeInstallTask.java:59-61`、`GameInstanceManifest.java:313-315`）。

### 3.1 新形态（processor 式）—— 需外部 JVM

| # | 步骤 | 做什么 | 需 JVM? | 证据 |
|---|---|---|---|---|
| 1 | 下原版 jar | `GameDownloadTask` 取原版 client jar | 否 | `ForgeInstallTask.java:117-118` |
| 2 | 读 profile | zip 内读 `install_profile.json` + 内嵌版本 json（`profile.getJson()`）；把 `maven/` 里的库与主 jar 复制进仓库 layout | 否 | `ForgeNewInstallTask.java:304-324` |
| 3 | 下库 | `dependents += GameLibrariesTask(profile.getLibraries())`（含 processor jar 及其依赖） | 否 | `ForgeNewInstallTask.java:329` |
| 4 | 隔离原版 jar | 原版 jar 拷到独立 temp 作 `{MINECRAFT_JAR}`（外部 processor 禁拿共享缓存路径） | 否 | `ForgeNewInstallTask.java:401-404` |
| 5 | 解 `data`/内建变量 | `{VAR}`/`[maven]`/`'lit'` 解析；补 `SIDE/MINECRAFT_JAR/ROOT/INSTALLER/LIBRARY_DIR` | 否 | `ForgeNewInstallTask.java:406-430` |
| 6 | 跑 processors | `Task.runSequentially`，**每个 processor 起一个外部 `java -cp … MainClass args`** | **是** | `ForgeNewInstallTask.java:434-437,151` |
| 7 | 校验组件 | `checkComponentCompletionAsync(内嵌 manifest, true)` | 否 | `ForgeNewInstallTask.java:439-441` |
| 8 | 产 patch | `GameInstancePatch.fromManifest(forgeVersion, "forge", selfVersion, PRIORITY_LOADER)` | 否 | `ForgeNewInstallTask.java:443-447` |
| 9 | 清理 | 删 tempDir / installer 临时文件 | 否 | `ForgeNewInstallTask.java:456-457`、`ForgeInstallTask.java:92-93` |

`DOWNLOAD_MOJMAPS` 被特判为直接下载 `client_mappings`、不起 JVM（`ForgeNewInstallTask.java:356-384`）。

### 3.2 老形态（纯解包）—— **完全不起 JVM**

| # | 步骤 | 做什么 | 需 JVM? | 证据 |
|---|---|---|---|---|
| 1 | 读 profile | zip 内读 `install_profile.json` → `ForgeInstallProfile`（`install` + `versionInfo`） | 否 | `ForgeOldInstallTask.java:70-74`、`ForgeInstallProfile.java:30-31` |
| 2 | 定位 universal jar | `install.path` 构 `Library`，按 layout 求库文件路径并建父目录 | 否 | `ForgeOldInstallTask.java:77-80` |
| 3 | 解包 universal jar | 把 `install.filePath` 指向的内嵌 jar 解到库路径（`is.transferTo(os)`） | 否 | `ForgeOldInstallTask.java:82-86` |
| 4 | 产 patch | `GameInstancePatch.fromManifest(install.versionInfo, "forge", selfVersion, PRIORITY_LOADER)` | 否 | `ForgeOldInstallTask.java:88-92` |
| 5 | 补库/校验 | `checkComponentCompletionAsync(versionInfo, true)`（网络下库） | 否 | `ForgeOldInstallTask.java:93` |

⇒ **老形态零外部进程**：全程仅 `ZipFile` 解包 + `JsonUtils` 解析 +（异步）HTTP 下载（对比新形态的 `ForgeNewInstallTask.java:151`）。

## 4. 盘上格式

```
<base>/                                  # DefaultGameRepositoryLayout
├── versions/<id>/
│   ├── <id>.json                        # 顶层扁平 + 保留 patches[]
│   ├── <id>.jar                         # 原版 client jar 的复制件（非 loader jar）
│   └── libraries/...                    # 仅 hint=="local" 的库落此
├── libraries/...                        # 共享库（含 universal / processor 产物）
└── assets/{indexes,objects,log_configs}/
```

- 布局与定位（实例根 / 清单 / jar / 共享库 / assets）：`DefaultGameRepositoryLayout.java:53-55,61-63,69-71,81-83,103-105`。
- **`<id>.json` = 顶层扁平 + 保留 `patches[]`**：builder 写 `resolved.withPatches(manifest.patches())`（`DefaultGameBuilder.java:173`）；序列化先出扁平顶层字段、再出 `patches` 数组，若有 `rawJson` 则按其逐字回写（`GameInstanceManifest.java:592-657`）；**读取时 `root:true` 且 `patches` 非空 ⇒ 丢弃顶层、从空 manifest 重放 `patches`**（故 `patches` 必须自洽）（`:671-689`）。
- **`<id>.jar` 是复制件**：`draft.putPrimaryJar(instanceId, minecraftJar)`，目标 = `versions/<id>/<id>.jar`（`DefaultGameBuilder.java:174`、`DefaultGameRepositoryDraft.java:137,440-449`、`DefaultGameRepositoryLayout.java:69-71`）。
- **库落哪的判据 = `hint=="local"`**：命中 ⇒ 实例内 `versions/<owner>/libraries/`；否则共享 `libraries/`（`DefaultGameRepositoryLayout.java:87-97`）。老 Forge 的 universal（`ForgeOldInstallTask.java:79`）与新形态 `maven/` 库（`ForgeNewInstallTask.java:313`）都走 `getLibraryFile` ⇒ 默认落共享区。
- **不留 `install_profile.json` / installer**：installer 在系统 temp、用完即删（`ForgeInstallTask.java:76,93`、`ForgeNewInstallTask.java:456-457`）；`install_profile.json` 只在内存解析、不回写目标盘。
- **`mods/`**：builder 会算出 `runDirectory/mods` 并传给组件安装（供 loader 自带 mods 落位），但 **Forge 安装本身不创建 `config/` / `natives-*` / `launcher_profiles.json`**（本轮文件内未见此类写盘）（`DefaultGameBuilder.java:140-146`）。
- **老/新在盘上的差异**：① 清单来源不同（老 = `install_profile.json.versionInfo`；新 = installer 内嵌 `profile.getJson()`），但**最终顶层形态一致**（都被 builder 压成扁平 + `patches`）；② 库产物不同（老只解 1 个 universal jar；新复制整套 `maven/` 库 + processor 逐个生成 patched 产物）；③ vanilha 清单走同一 `GameDownloadTask`（`DefaultGameBuilder.java:169-172`）。

## 5. 与 NeoForge 的差异（同一「processor 式」位点：`ForgeNewInstallTask` vs `NeoForgeOldInstallTask`）

| 维度 | Forge（新形态） | NeoForge（1.20.2+ 现行形态） | 证据 |
|---|---|---|---|
| patch id | `forge` | `neoforge`（1.20.1 由 `NeoForgeInstallTask` 把 `forge`→`neoforge` 并裁前缀） | `ForgeNewInstallTask.java:445`、`GameComponentType.java:84,113`、`NeoForgeOldInstallTask.java:429`、`NeoForgeInstallTask.java:136-144` |
| priority | `PRIORITY_LOADER=30000` | 同 `30000` | `GameInstancePatch.java:67`、`ForgeNewInstallTask.java:447`、`NeoForgeOldInstallTask.java:431` |
| jar 处理 | 复制 `profile.getPath()` 主制品到 artifact 路径（有复制件） | 同构 | `ForgeNewInstallTask.java:318-324`、`NeoForgeOldInstallTask.java:302-308` |
| 是否改装 vanilla jar | 否 —— 原版 jar 作隔离副本 `{MINECRAFT_JAR}`，产物落共享 `libraries/` | 否，同构 | `ForgeNewInstallTask.java:401-404`、`NeoForgeOldInstallTask.java:385-388` |
| zlib 降级 | **有**：`.jar` 输出 sha1 不符时降级为 ZIP 结构校验 | **无**，直接抛 | `ForgeNewInstallTask.java:166-179`、`NeoForgeOldInstallTask.java:165-168` |
| 形态判定入口 | `spec` / `install`+`versionInfo` | `profile=="forge"`+neo 标记，或 `neoforge`/`NeoForge` | `ForgeInstallTask.java:141-150`、`NeoForgeInstallTask.java:125,145` |

> Forge 另有一条 **`ForgeOldInstallTask`（纯解包、零 JVM）**，NeoForge 无对应物（其 `NeoForgeOldInstallTask` 名 Old 实为 processor 式）（`ForgeOldInstallTask.java:69-93`、`NeoForgeOldInstallTask.java:61-171`）。

## 6. 镜像 / 前缀重写规则

- 下载前对候选 URL 逐个 `injectURLsWithCandidates`（`DownloadProvider.java:52-62`、`ForgeInstallTask.java:79`）。
- `BMCLAPIDownloadProvider.injectURL`：顺序遍历 replacement，命中 `baseURL.startsWith(key)` ⇒ 返回 `value + baseURL.substring(key.length())`（`BMCLAPIDownloadProvider.java:141-153`）。
- Forge 相关前缀：`https://bmclapi2.bangbang93.com`→apiRoot（`:78`）；`http://files.minecraftforge.net/maven` / `https://files.minecraftforge.net/maven` / `https://maven.minecraftforge.net` → `apiRoot + "/maven"`（`:84-86`）。
- 主表无匹配再试 `fallbackReplacement`（modrinth/curseforge CDN，`:100-106`），仍无匹配则原样返回（`:156-171`）。
- `MojangDownloadProvider.injectURL` **恒返回原 URL、不重写**（`MojangDownloadProvider.java:102-105`）。

## 7. 版本号归一化

- 源 A：`VersionNumber.normalize(mcversion key)` + `1.7.10-pre4 ↔ 1.7.10_pre4` 双向特判（`ForgeVersionList.java:68,48-54`）。
- 源 B：`getVersion` 用 `StringUtils.substringAfter(remoteVersion, "-")` 去掉 `mcver-` 前缀再比对（`ForgeBMCLVersionList.java:130-131`）。
- `ForgeInstallTask.modifyVersion`：先 `version.replace(gameVersion,"")`，再循环剥除 `-`/`_` 前后缀与 `forge-` 前缀（`ForgeInstallTask.java:217-219`）。

## 8. 失败 / 幂等语义

- **outputs sha1 预检**（仅新形态）：逐 outputs 算 key/value，文件存在且 sha1 命中才计数；**全部命中且 outputs 非空 ⇒ 整条 processor 跳过**；不符则删文件置 `miss`（`ForgeNewInstallTask.java:77-110`）。
- **事后校验**：执行后逐 outputs 算 sha1，不符 ⇒ **先删文件再抛** `ChecksumMismatchException`（`ForgeNewInstallTask.java:155-185`）。
- **退出码**：processor `exitCode != 0` ⇒ `IOException`（`ForgeNewInstallTask.java:151-153`）。
- **不回滚**：注释明确「Shared libraries, assets, and download caches may remain after failure」，靠幂等续跑（`DefaultGameBuilder.java:42-44`）；processor 产物「已存在则比对/删」，非原子（`ForgeNewInstallTask.java:91-106`）。
- **失败边界**：builder 的 build 任务 `whenComplete` 时若 draft 未提交则 `abort()`（`DefaultGameBuilder.java:180-184`）；构造阶段失败 `abortDraftAfterFailure`（`:188-191`）。
- **重装**：重跑同一 installer 时命中 sha1 的 processor 跳过、未命中重新生成 ⇒ 幂等续跑，无独立卸载/清理逻辑（`ForgeNewInstallTask.java:108-110`）。

## 9. 未确认项

1. **`<id>.json` 的 `rawJson` 回写路径**：`putManifest(manifest, true)` 的布尔语义未展开；「顶层扁平」由 `toJsonObject` + `withPatches` 推断；**内嵌/`versionInfo` 源自带 `inheritsFrom` 时最终是否保持继承**未确认（`GameInstanceManifest.java:592-596`）。
2. **`mods/` 是否真被创建**：builder 只计算并传递 `modsDirectory`（`DefaultGameBuilder.java:146,149`），Forge/NeoForge 是否写入该目录的组件实现不在本轮文件内。
3. **`launcher_profiles.json` / `config/` / `natives-*`**：本轮文件内**未见** Forge 安装创建它们（`launcher_profiles.json` 是**官方 installer** 行为，见 [`桌面标准启动链路-对照.md`](../../90-archive/桌面标准启动链路-对照.md) 与 [`NeoForge支持-调研.md`](NeoForge支持-调研.md) §8.3）—— 属"未见即否定"的弱结论。
4. **多源优先级**：`versionListProviders` 的顺序由 `AutoDownloadProvider` 的构造方决定（`AutoDownloadProvider.java:104-112`），未确认谁优先。
5. **MC 版本上下界与快照**：代码内无显式上下界、无 release/snapshot 分支，完全取决于远端元数据 key。
6. **1.20.1 专属特判**：未在允许文件内发现（可能在 `GameVersionNumber` 等未读文件）。
7. `ZlibUtils.IS_ZLIB_COMPATIBLE` 判定实现、`GameLibrariesTask` 的落盘细节在给定文件外。

## 10. 证据台账

- HMCL 源码：`ref/HMCL/HMCLCore/src/main/java/org/jackhuang/hmcl/download/forge/`（版本面 6 件 + 安装 5 件）、`download/{DownloadProvider,BMCLAPIDownloadProvider,MojangDownloadProvider,AutoDownloadProvider,DefaultGameBuilder,GameBuilder}.java`、`game/{GameInstanceManifest,GameInstancePatch,DefaultGameRepository,DefaultGameRepositoryDraft,DefaultGameRepositoryLayout,GameInstanceLibraryBuilder}.java`。
- 原始报告（工作区根）：`stuffs/research/hmcl-forge/A-forge-versions-download.md`、`stuffs/research/hmcl-forge/B-forge-install-format.md`。
- Forge 官方件形态（我方早期取证）：[`NeoForge支持-调研.md`](NeoForge支持-调研.md) §5 表（含 1.20.1 样本 `forge-1.20.1-47.1.106`）、§8.3（官方 installer 写盘行为，含 `launcher_profiles.json` 前置）。
- **T0 真件取证（2026-09-28，11 个真 installer）**：**工作区根** `stuffs/research/forge-support/evidence/`（每份样本含 `installer.jar` + 解出的 `install_profile.json` / `version.json`；归纳 **工作区根** `stuffs/research/forge-support/evidence/T0-findings.md`、逐题明细 `stuffs/research/forge-support/evidence/T0-summary.md`、选样与解析脚本 `stuffs/research/forge-support/evidence/analyze.py`、版本表 `stuffs/research/forge-support/evidence/mt.txt`、选样清单 `stuffs/research/forge-support/evidence/picked_all.txt`）。

## 11. T0 真件取证（11 个真 installer）—— 覆盖 §1/§2 与既有启动代际口径

> 方法：从 `maven.minecraftforge.net` 下 11 份 installer（HTTP 200、合法 zip）→ 解 `install_profile.json` 与内嵌 `version.json` → 逐题归纳。
> 原始报告：**工作区根** `stuffs/research/forge-support/evidence/T0-findings.md`（表 + 未确认项）；明细 **工作区根** `stuffs/research/forge-support/evidence/T0-summary.md`。
> 样本：1.7.10-10.13.4.1614-1.7.10 / 1.8.9-11.15.1.2318-1.8.9 / 1.12.2-14.23.5.2864 / 1.13.2-25.0.223 / 1.16.5-36.2.42 / 1.17.1-37.1.1 / 1.18.2-40.3.12 / 1.20.1-47.4.23 / 1.20.6-50.2.10 / 1.21.1-52.1.16 / 26.3-66.0.6。

### 11.1 安装侧：真形态是 **3 种**，"要不要 JVM"的判据是 **client processor 数**

| 样本 | `install_profile.json` 形态 | 内嵌 universal 来源 | client processors | 需 JVM |
|---|---|---|---|---|
| 1.7.10 / 1.8.9 | `install`+`versionInfo`（**无 `spec`**） | installer **根**内嵌 `…-universal.jar` | 0 | **否** |
| **1.12.2** | **`spec:0`**（无 `install`/`versionInfo`） | installer 内 `maven/…/forge-<id>.jar`（纯复制） | **0** | **否** |
| 1.13.2 / 1.16.5 | `spec:0` | — | 5 / 4 | 是 |
| 1.17.1 / 1.18.2 / 1.20.1 | `spec:1` | — | 6 / 6 / 6 | 是 |
| 1.20.6 / 1.21.1 / 26.3 | `spec:1`（多 `hideExtract`/`serverJarPath`，`path` 带 **`:shim`** classifier） | — | 4 / 3 / **1** | 是 |

⇒ **修正 §1 表与 §0 第 4 条**：`ForgeOldInstallTask` 那条真老形态只到 **≤1.8.9**；**1.12.2 已在 `spec` 家族但 0 processor** ⇒ **零 JVM 安装面 = ≤1.12.2 全段**（比原先认为的更宽），**1.13 起才真正需要 JVM**。

### 11.2 启动侧：真代际是 **4 段**，module path 只活在 **1.17.1–1.20.1**

| 样本 | mainClass | `-p` module path | `-DignoreList` / `-DmergeModules` | 传统 `minecraftArguments` |
|---|---|---|---|---|
| 1.7.10 / 1.8.9 / 1.12.2 | `net.minecraft.launchwrapper.Launch` | 无 | 无 | **有** + `--tweakClass …FMLTweaker` |
| 1.13.2 / 1.16.5 | `cpw.mods.modlauncher.Launcher` | 无 | 无 | 无（走 `arguments.game`） |
| 1.17.1 / 1.18.2 / 1.20.1 | `cpw.mods.bootstraplauncher.BootstrapLauncher` | **有** | **有** | 无 |
| 1.20.6 / 1.21.1 / 26.3 | **`net.minecraftforge.bootstrap.ForgeBootstrap`** | **无** | 无 | 无 |

⇒ **修正启动代际口径**：① module path 的**起点 = 1.17.1**（此前的"1.17+"推断成立）、**终点 = 1.20.1**（**1.20.6 已去掉 `-p` 并换主类**）⇒ 突变在 **1.20.x 内部**，**与 NeoForge 的 26.x 突变不同步**；② ≤1.16 段全部走传统启动（`LaunchWrapper` / `ModLauncher`），**无 module path**；③ 1.17–1.20.1 段才带 `-DignoreList`/`-DmergeModules`（与 NeoForge 同构，我方机制可复用）。

### 11.3 仍未确认（T0 残留）

1. 1.13–1.16 段内的形态漂移（只测两端 1.13.2 / 1.16.5）；1.14/1.15 未测。
2. **1.20.1 → 1.20.6 之间的确切切点**未定位（1.20.2–1.20.4 未测）。
3. 全部样本 `type=release`、`inheritsFrom=<MC 版本>`（**薄继承**，非 HMCL 扁平式）——与 §4 的盘上格式结论一致。
4. **启动可行性不属本报告范围**：本轮只做静态取证；随包 JRE 26 能否跑 ≤1.16 段 Forge 是另一问题（见 [`Forge支持-改动方案.md`](../../90-archive/Forge支持-改动方案.md) §10 的 R1）。

相关：[`Fabric支持-调研.md`](Fabric支持-调研.md)、[`NeoForge支持-调研.md`](NeoForge支持-调研.md)、[`NeoForge安装链-逐行取证.md`](NeoForge安装链-逐行取证.md)、[`NeoForge无JVM安装-可行性与取证.md`](NeoForge无JVM安装-可行性与取证.md)、[`Forge支持-改动方案.md`](../../90-archive/Forge支持-改动方案.md)、[`../README.md`](../README.md)。
