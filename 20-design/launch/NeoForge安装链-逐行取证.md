# HMCL NeoForge/Forge 安装链逐行取证（A 线）

> 日期：2026-09-28 ｜ 性质：**证据存档 / 决策记录**，**不复述现状**（能力现状见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 22 条）。
> 来源：只读 `ref/HMCL/` 源码（`HMCLCore/src/main/java/org/jackhuang/hmcl/download/{neoforge,forge}/`、`java/JavaRuntime.java`、`util/platform/SystemUtils.java`）。
> 原始报告：**工作区根** `stuffs/research/hmcl-neoforge/A-hmcl-install-chain.md`（本文件为其入库版，正文照搬、仅改抬头与路径口径）。
> 全部结论以代码为准；行号对应当次（2026-09-28）Read 的快照。未读到的标「未确认」。
> 姊妹篇：[`NeoForge无JVM安装-可行性与取证.md`](NeoForge无JVM安装-可行性与取证.md)（同一轮 B 线：逐个 processor 能否不跑 JVM）。
> 既有 HMCL 三链调研见 [`NeoForge支持-调研.md`](NeoForge支持-调研.md) §1–§4（本文修正其一处计数错误，见 §8.1）。

## 1. 一句话结论

HMCL **从不执行 `java -jar installer.jar`**：它把 installer 当**只读 zip 容器**，读 `install_profile.json` + 内嵌版本 json，**自己解析并逐个 processor 起外部 `java` 子进程**（`java -cp <classpath+processor.jar> <MANIFEST Main-Class> <args>`），退出码非 0 即失败（`NeoForgeInstallTask.install:117-160`、`ForgeNewInstallTask.java:124-153`）。

装一次 NeoForge 的 **java 进程数**：宿主启动器自带 1 个 JVM（不算），外加 **N 个外部进程 = profile 中「client 侧且非 DOWNLOAD_MOJMAPS」的 processor 条数**，**顺序执行、逐个新起进程**（`ForgeNewInstallTask.java:434-437` 的 `Task.runSequentially`）。N 是**数据驱动**的：1.20.1 = 6、1.20.2–1.21.x = 6、26.x = 1（见 §3）。

## 2. 完整步骤链（NeoForge，从「用户点安装」到「patch 产出」）

| # | 步骤 | 做什么 | 需 JVM? | 证据 |
|---|---|---|---|---|
| 0 | 选版本 | 官方列表 = 两个 Maven API（`/net/neoforged/forge` 与 `/neoforged/neoforge`），`Task.allOf` 并行 HTTP+JSON，裸版本号「破解」出 MC 版本；BMCLAPI 按 mc 版本单查 | 否（纯 HTTP/JSON） | `NeoForgeOfficialVersionList.java:56-130`、`NeoForgeBMCLVersionList.java:62-80` |
| 1 | 建任务 | `getInstallTask` 返回 `NeoForgeInstallTask` | 否 | `NeoForgeRemoteVersion.java:35-38` |
| 2 | 下 installer | 建临时文件 + `FileDownloadTask`（带 ZIP 结构校验），写入 temp `.jar` | 否（HTTP + ZIP 校验） | `NeoForgeInstallTask.java:66-76` |
| 3 | 开 zip 分流 | 只读打开 installer zip，读 `install_profile.json`，按 `profile` 字段 + `META-INF/NEOFORGE.RSA`/含 `neoforge` 文本分流 | 否（进程内 zip/JSON） | `NeoForgeInstallTask.java:122-158` |
| 4a | 1.20.1 支 | `profile=="forge"` 且含 neo 标记 → 先 `GameDownloadTask`（下原版 client jar），再 `ForgeNewInstallTask` | 否 | `NeoForgeInstallTask.java:125-135` |
| 4b | 1.20.2+ 支 | `profile=="neoforge"/"NeoForge"` → `GameDownloadTask` + `NeoForgeOldInstallTask`（**名 Old 实为现行形态**） | 否 | `NeoForgeInstallTask.java:145-155` |
| 5 | 版本号改写 | 1.20.1 支：patch id `forge`→`neoforge`、裁版本前缀 | 否 | `NeoForgeInstallTask.java:136-144,162-168` |
| 6 | (ForgeNew) 读 profile | 读 `install_profile.json` + **内嵌版本 json**（`profile.getJson()`）；把 installer 内 `maven/` 里的库与主 jar 复制进仓库 layout | 否（zip 复制） | `ForgeNewInstallTask.java:304-324`（NeoForge 同构：`NeoForgeOldInstallTask.java:288-308`） |
| 7 | (ForgeNew) 下库 | `dependents` 加 `GameLibrariesTask(profile.getLibraries())`，即 profile 声明的库（含 processor jar 及其依赖） | 否（HTTP） | `ForgeNewInstallTask.java:329`、`NeoForgeOldInstallTask.java:313` |
| 8 | 隔离原版 jar | 把原版 client jar 拷到独立 temp，作 `{MINECRAFT_JAR}`（禁外部 processor 拿共享缓存路径） | 否（文件复制） | `ForgeNewInstallTask.java:401-404`、`NeoForgeOldInstallTask.java:385-388` |
| 9 | 解 `data` | 把 profile `data` 逐条解析为 vars（`[maven]`→路径、`'lit'`→字面量、installer 内路径→解包到 temp）；补内建变量 | 否（zip 解包） | `ForgeNewInstallTask.java:406-430`、`NeoForgeOldInstallTask.java:390-414` |
| 10 | 跑 processors | `Task.runSequentially` 逐个 processor：**每个起一个外部 java 进程** | **是（外部 java 子进程）** | `ForgeNewInstallTask.java:434-437,151`、`NeoForgeOldInstallTask.java:418-421,151` |
| 11 | 校验组件 | `checkComponentCompletionAsync(内嵌版本 manifest, true)`（补 loader 库、校验） | 否（HTTP/校验） | `ForgeNewInstallTask.java:439-441`、`NeoForgeOldInstallTask.java:423-425` |
| 12 | 产出 patch | `setResult(GameInstancePatch.fromManifest(内嵌版本 json, id, selfVersion, PRIORITY_LOADER))` | 否 | `ForgeNewInstallTask.java:443-447`、`NeoForgeOldInstallTask.java:427-431` |
| 13 | 清临时 | 删 `tempDir` / installer 临时文件 | 否 | `ForgeNewInstallTask.java:456-457`、`NeoForgeInstallTask.java:84-87` |
| 14 | 落盘为实例 | 把 patch 合并/写成 `versions/<id>/<id>.json` + `<id>.jar` | — | **未在本轮范围内**（写盘任务不在给定文件列表），见 §8 |

流程顺序依据：`dependents`（如 `GameLibrariesTask`）在 `execute()` 前完成 —— 因 `execute()` 找不到 processor jar 会抛异常（`ForgeNewInstallTask.java:112-114`）；`dependencies`（processors→checkComponentCompletion）在 `execute()` 后（`ForgeNewInstallTask.java:439-448`）。

## 3. JVM 边界小结

**不需要 JVM**（HMCL 自身 JVM 内的纯 Java/网络操作即可）

- 版本列表刷新、installer 下载、原版 client 下载、profile `libraries` 下载（HTTP + Gson）：`NeoForgeOfficialVersionList.java:56-130`、`NeoForgeInstallTask.java:69-76`、`ForgeNewInstallTask.java:329`
- 打开/读取 installer zip、复制 `maven/` 内容、解 `data`（`java.nio` FileSystem / ZipFile）：`ForgeNewInstallTask.java:305-324,408-420`
- 占位符解析、sha1 计算（`DigestUtils`）、ZIP 结构校验：`ForgeNewInstallTask.java:77-110,273-282`
- `DOWNLOAD_MOJMAPS` 被特判为**直接下载** `client_mappings`，**不起 JVM**：`ForgeNewInstallTask.java:356-384`、`NeoForgeOldInstallTask.java:340-368`

**必须外部 `java` 子进程**

- 每个非 mojmap 的 client processor：`SystemUtils.callExternalProcess(command)`（`ForgeNewInstallTask.java:151`、`NeoForgeOldInstallTask.java:151`）
- 该 API 内部就是 `new ProcessBuilder(command)` 起新进程并 `waitFor`（`SystemUtils.java:68-77`）

**结论**：安装链的 JVM 需求**全部落在「processor 执行」这一步**；其余步骤均为纯下载 / 纯 zip+JSON / 纯哈希。

## 4. 「那个 java」从哪来

- `JavaRuntime.getDefault()` 直接返回**启动器自身所在 JVM**：`return CURRENT_JAVA;`（`JavaRuntime.java:135-137`）
- `CURRENT_JAVA` 由 `System.getProperty("java.home")` + `bin/<java>` 得到，`isManaged=false`（`JavaRuntime.java:139-154`）
- ⇒ processor 用的是**HMCL 进程自己的 java**，**不是**它下载/托管的游戏 JRE；前提是 HMCL 本身就是一个正在跑的 Java 程序（用户不必"单独装 Java"，但必须能运行 HMCL）（`JavaRuntime.java:140-154`）
- 命令首元素：`command.add(JavaRuntime.getDefault().getBinary().toString())`（`ForgeNewInstallTask.java:125`、`NeoForgeOldInstallTask.java:125`）

## 5. processor 执行细节

- **classpath 拼法**：先按 `processor.getClasspath()` 顺序取各 artifact 文件路径，**最后追加 processor jar 自身**，用 `File.pathSeparator` join（`ForgeNewInstallTask.java:128-136`、`NeoForgeOldInstallTask.java:128-136`）
- **Main-Class**：从 processor jar 的 `JarFile` manifest 读 `Attributes.Name.MAIN_CLASS`，空则报错（`ForgeNewInstallTask.java:116-122`）
- **命令形态**：`java -cp <cp> <Main-Class> <args...>`，`LOG.info` 打印命令行（`ForgeNewInstallTask.java:124-150`）
- **args 占位符解析**：`parseLiteral` 三分支（`ForgeNewInstallTask.java:273-282`、`NeoForgeOldInstallTask.java:257-266`）：
  - 整体 `{VAR}` → `var.get(...)`（缺失 → null → 调用方抛 `ArtifactMalformedException`）
  - 整体 `'literal'` → 去引号
  - 整体 `[group:name:ver[:classifier][@ext]]` → maven artifact 文件路径
  - 其它 → `replaceTokens` 逐字符替换内嵌 `{VAR}`/`'literal'`，**缺 key 抛 `IllegalArgumentException`**（`ForgeNewInstallTask.java:229-271`）
- **内建变量**：`SIDE=client`、`MINECRAFT_JAR`、`MINECRAFT_VERSION`、`ROOT`、`INSTALLER`、`LIBRARY_DIR`（`ForgeNewInstallTask.java:425-430`、`NeoForgeOldInstallTask.java:409-414`）
- **outputs 幂等预检**：先算 key/value 字面量，逐 outputs 比对 sha1；文件存在但 sha1 不符 → 删并置 `miss`；全部命中且 outputs 非空 → **整条跳过**（`ForgeNewInstallTask.java:77-110`）
- **事后校验**：执行后逐 outputs 算 sha1，不符 → 删文件 → 抛 `ChecksumMismatchException`（`ForgeNewInstallTask.java:155-185`）
- **zlib 降级（仅 ForgeNew 支）**：`!ZlibUtils.IS_ZLIB_COMPATIBLE` 且输出是 `.jar` 时，改判 ZIP 结构合法即放过（`ForgeNewInstallTask.java:166-179`）；**`NeoForgeOldInstallTask` 无此降级，直接抛**（`NeoForgeOldInstallTask.java:165-168`）—— 两形态的差异点
- **退出码**：`exitCode != 0` → `IOException("Game processor exited abnormally with code ...")`（`ForgeNewInstallTask.java:151-153`）
- **顺序/并发**：processors 用 `Task.runSequentially` **严格串行**（`ForgeNewInstallTask.java:434-437`、`NeoForgeOldInstallTask.java:418-421`）
- **仅 client 侧**：`getProcessors()` 过滤 `sides.contains("client")`（`ForgeNewInstallProfile.java:103-106`）

## 6. 有没有「纯下载（不跑 processor）」分支

- **有，但 NeoForge 走不到**：`ForgeInstallTask.detectForgeInstallerType` 按 `install_profile.json` 判型 —— 含 `spec` → `ForgeNewInstallTask`（processor 式）；含 `install`+`versionInfo` → `ForgeOldInstallTask`（**纯解包、无 processor、无 JVM**）（`ForgeInstallTask.java:137-155`）
- `ForgeOldInstallTask` 只做：读 `install_profile.json`、把内嵌 universal jar 解到库路径、构造 patch、`checkComponentCompletion`（`ForgeOldInstallTask.java:69-93`，**零外部进程**）
- **NeoForge 两分支都不是纯下载**：1.20.1 走 `ForgeNewInstallTask`（有 processor）；1.20.2+ 走 `NeoForgeOldInstallTask` —— **名字虽 Old，实为 processor 式**，仍起 JVM（`NeoForgeOldInstallTask.java:61-171,418-425`）
- **局部纯下载**：`DOWNLOAD_MOJMAPS` 的 processor 被替换为纯下载任务，不占 JVM（`ForgeNewInstallTask.java:356-384`）
- ⇒ 就 **NeoForge 而言不存在「完全无 JVM」的安装路径**（但「哪些 processor 真的必须 JVM」是另一问题，见姊妹篇）

## 7. 产物形态

- **返回的只是 patch**：`GameInstancePatch.fromManifest(内嵌版本 json, NEO_FORGE/FORGE id, selfVersion, PRIORITY_LOADER=30000)`（`ForgeNewInstallTask.java:443-447`、`NeoForgeOldInstallTask.java:427-431`）
- **版本 json 来源**：installer 内 `profile.getJson()` 指向的内嵌 json（如 `version.json`），被读成 `GameInstanceManifest`（`ForgeNewInstallTask.java:308`、`NeoForgeOldInstallTask.java:292`）；**是否薄 `inheritsFrom` 形态取决于该内嵌 json**（旧形态为 HMCL 扁平式、26.x 为薄 `inheritsFrom`）—— 本轮未逐份开箱核验，标**未确认**
- **libraries 落哪**：installer 内 `maven/` 中的库复制到仓库 layout 库路径（`ForgeNewInstallTask.java:310-316`）；其余由 `GameLibrariesTask` 下到共享 `libraries/`（`ForgeNewInstallTask.java:329`）
- **主 jar**：`profile.getPath()` 存在的制品复制到 artifact 路径（`ForgeNewInstallTask.java:318-324`，**有复制件**）
- **不留 installer / install_profile**：installer 是系统 temp、用完即删（`NeoForgeInstallTask.java:85`、`ForgeNewInstallTask.java:456-457`）；`install_profile.json` 只在内存解析、**不回写目标盘**（本轮文件未见写回）
- **`versions/<id>/<id>.json` + `<id>.jar` 的实际写盘、`patches`/`inheritsFrom` 顶层形态**：由**未在给定列表内的安装编排/写盘任务**完成，本轮**未确认**（[`NeoForge支持-调研.md`](NeoForge支持-调研.md) §2/§4 有描述，可作为假设）

## 8. 未确认项

1. **计数修正**：[`NeoForge支持-调研.md`](NeoForge支持-调研.md) §5 表记「21.1.250 client 侧 5 个」，真 profile 实测为 **6**（MCP_DATA / DOWNLOAD_MOJMAPS / MERGE_MAPPING / jarsplitter / ART / binarypatcher）。
2. 最终 `versions/<id>/<id>.json` + `<id>.jar` 的写盘任务与顶层扁平/`patches` 形态（不在本轮给定文件内）—— **未确认**。
3. 内嵌版本 json 是 HMCL 扁平式还是薄 `inheritsFrom`（按 NeoForge 代际而异，未逐份开箱核验）—— **未确认**。
4. 1.20.1 是否走 `NeoForgeInstallTask.install:125` 的「`profile==forge` + neo 标记」分支（取决于真 installer 内容，本轮未开箱）—— **未确认**。
5. `ZlibUtils.IS_ZLIB_COMPATIBLE` 的判定实现（在本轮范围外）—— **未确认**。

## 相关

- 姊妹篇（同轮 B 线）：[`NeoForge无JVM安装-可行性与取证.md`](NeoForge无JVM安装-可行性与取证.md)
- 既有三链调研：[`NeoForge支持-调研.md`](NeoForge支持-调研.md) §1–§4（本文修正其计数）
- 我方安装期 JVM 载体：[`安装期JVM载体-调研.md`](../../90-archive/安装期JVM载体-调研.md)
- 落地方案：[`NeoForge支持-改动方案.md`](../../90-archive/NeoForge支持-改动方案.md)
- 原始报告：**工作区根** `stuffs/research/hmcl-neoforge/A-hmcl-install-chain.md`
