# NeoForge 支持调研 —— HMCL 三链 + 真 installer 解剖 + 我方现状（证据存档）

> 日期：2026-09-15 ｜ 定位：**证据存档 / 调研结论**，**不复述现状**（能力现状见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)）。
> 方法：**七路子 agent 并行**（HMCL 下载链 / 安装链 / 启动链 / 数据模型；真 installer 解剖；我方代码测绘；安装期 JVM 可行性），主会话汇总。
> 实物取证：**工作区根** `stuffs/research/neoforge/`（三个真 installer jar + 解出的 `install_profile.json`/`version.json` + processor jar）。
> 落地方案见 [`NeoForge支持-改动方案.md`](../../90-archive/NeoForge支持-改动方案.md)。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 22 条](../../00-current/现状基线.md)。

---

## 0. 结论速览（含三条对既有认知的修正）

1. **修正①**：真 installer 的 `arguments.jvm` **没有 `-DlegacyClassPath`**（三样本全文 grep 0 命中）。游戏 classpath 来自 **vanilla 父版本 json 自带的 `-cp ${classpath}`**（已 grep `1.16.5/1.19.4/1.21.10/26.1.2/26.2` 均有）。
2. **修正②**：**26.x 形态突变** —— 不再有 `-p`/`--add-modules`/`-DignoreList`，`mainClass` 改为 `net.neoforged.fml.startup.Client`，客户端安装**只剩 1 个 processor**（旧版 6 个）。
3. **修正③**：处理器 happy path **无 `System.exit`**（逐 jar 字节码扫描；exit 只在参数错误分支）→ 「同 JVM 内反射执行 processor」可行，但**必须放在独立进程**。
4. **安装期必须真跑 JVM**（installertools / FART·ART / binarypatcher / jarsplitter 无 ArkTS 等价物）。
5. **HMCL 元数据的特殊性**：官方列表只有**裸 loader 版本号**，MC 版本靠**破解版本号**；1.20.1 走 `net.neoforged:forge` 制品，1.20.2+ 才走 `net.neoforged:neoforge`。
6. **（第二轮新证据）`ref/LegacyInstaller` 就是现役 installer 源码**（`git describe` = `3.0-48` = 真 jar 的 `3.0.48`），且**支持 headless CLI 直跑**（`--installClient <dir>`、`--skip-hash-check`、`--mirror`…），其**处理器执行方式本身就是「进程内 URLClassLoader 反射」**（§8.2/§8.3）。
7. **（第二轮新证据）官方 installer 直跑路线成立性**：我们的随包 JRE **含 `java.desktop`**（43 模块，2026-09-15 核实）⇒ 无 AWT 缺模块之虞；硬前置 = 目标目录须含 `launcher_profiles.json` 之类的 profile 文件（我们自造 stub）。产物 = 官方**薄 `inheritsFrom` 形态**（形态①）+ 标准 maven libraries ⇒ HMCL 可读。
8. **（战役结论，2026-09-16）端到端打通**：**1.20.2 / 1.21.1 / 26.x 三条形态实机可玩**（用户 2026-09-16 确认，三条都进主菜单）；安装与启动两侧的踩坑见 §9。
9. **（路线结论，2026-09-15 用户拍板）不走官方 installer 直跑**：为**与 HMCL 对齐**并减少不确定项，installer jar **只当数据容器**（`install_profile.json` / `/version.json` / `data/*.lzma`），运行时**不加载它的类**；安装编排自研（ArkTS），processor 工具按 profile 坐标调用。本文 §8 的 CLI 契约等证据因此**降级为参考实现**（用于理解语义、交叉验证），不进运行时。落地方案见 [`NeoForge支持-改动方案.md`](../../90-archive/NeoForge支持-改动方案.md)（修订 3）。

---

## 1. HMCL 下载链（`HMCLCore/.../download/neoforge/`，下称 core）

- **没有 meta 服务，只有两个 Maven API**：
  - 1.20.1：`https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/forge`
  - 1.20.2+：`.../net/neoforged/neoforge`
  - 返回 `{isSnapshot: bool, versions: [String]}`，**只有裸版本号**（无 url/sha1/size/日期）。两者用 `Task.allOf` 并行，**任一失败即整表失败**。
- **MC 版本「破解」规则**（`NeoForgeOfficialVersionList.refreshAsync:75-125`）：`0.*` → 取第 1、2 段之间（快照）；主版本 ≥26 → 取前三段（第三段为 0 则取两段，`+` 后缀特殊处理）；其余 → `第二段==0 ? 截到第一段 : 截到第二段`，前缀补 `1.`。例：`21.1.250`→`1.21.1`、`20.4.237`→`1.20.4`。
- **1.20.1 特判**：制品 group = `net.neoforged:forge`，版本形如 `1.20.1-47.x`；`NeoForgeRemoteVersion.normalize:44-54` 剥 `1.20.1-` / `1.20.1-forge-` 前缀。
- **BMCLAPI 源**：`{apiRoot}/neoforge/list/{mc}`（**直接给 `mcversion`**，DTO 只认 `rawVersion/version/mcversion`）；installer = `{apiRoot}/neoforge/version/{v}/download/installer.jar`（忽略返回体的 `installerPath`）。其无参 `refreshAsync()` **故意抛 `UnsupportedOperationException`** —— 必须按 mc 版本查。
- **镜像规则**：**只重写** `https://maven.neoforged.net/releases/` → `{apiRoot}/maven/`（前缀替换）；`/api/maven/versions/...` **不镜像**。
- **边界与坑**：
  - `FetchTask` 对 **4xx 立即放弃且不重试**（不解析 body）—— 这修正了我们此前「400 + 空数组」的判读方式；
  - **真陷阱是 HTTP 200 + 空数组**：HMCL 视为成功、**不降级**到下一源 → UI 显示「无可用版本」；
  - installer 官方**无 sha1**，只能做 ZIP 完整性校验；libraries 用 profile 内 sha1。

## 2. HMCL 安装链（`download/neoforge/` + `download/forge/`）

- **两段式**：下 installer 到系统 temp → zip 打开读 `install_profile.json` → 按 `profile` 字段 + `META-INF/NEOFORGE.RSA`/含 `neoforge` 文本分流：
  - `profile=="forge"` 且有 neo 标记 → `ForgeNewInstallTask`（= NeoForge 1.20.1），完成后把 patch id 从 `forge` 改成 `neoforge` 并裁版本前缀（`NeoForgeInstallTask:125-144`）；
  - `profile=="neoforge"/"NeoForge"` → `NeoForgeOldInstallTask`（**名字叫 Old，实为 1.20.2+ 现行形态**）。
- **HMCL 不跑 `java -jar installer.jar`**：自己解析 profile 并**逐个 processor 起 JVM**：`java -cp <processor.classpath + processor.jar> <MANIFEST 的 Main-Class> <args>`（`ForgeNewInstallTask.java:124-148,151`），退出码非 0 → `IOException`。
- **profile 模型**（`ForgeNewInstallProfile`）：`spec/minecraft/json/version/path/libraries/processors/data`；`Processor{sides,jar,classpath,args,outputs:Map<path,sha1>}`；`Datum` **只取 `client`**。
- **占位符**（`parseLiteral:273-282`）：`{VAR}` 变量、`'literal'` 字面量、`[group:name:version[:classifier][@ext]]` → maven 路径；内建 `SIDE=client`、`MINECRAFT_JAR`、`MINECRAFT_VERSION`、`ROOT`、`INSTALLER`、`LIBRARY_DIR`。
- **幂等**：outputs 的 sha1 预检命中则**整条跳过**（`:90-110`）；执行后逐个校验，不符**先删再抛**。
- **原版 jar 必须隔离**：先拷到独立 temp 再作 `{MINECRAFT_JAR}`（`:401-404` 注释：外部 processor 严禁拿到共享缓存路径）。
- `DOWNLOAD_MOJMAPS` 在 HMCL 被**特判为直接下载** `client_mappings`（`:356-384`，不起 JVM）。BINPATCH 无专门代码，只是 `data` 里指向 zip 内路径的条目。
- **ZlibUtils**：探测「JVM `Deflater` 是否与参考 zlib 字节一致」；不一致时**仅 Forge 路径**把 `.jar` 输出的 sha1 校验降级为 ZIP 结构校验（`ForgeNewInstallTask.java:166-179`）。
- **产物**：返回 `GameInstancePatch(id=loader, version, priority=30000)`；builder 写 `versions/<id>/<id>.json`（**顶层扁平 + 保留 `patches`**）+ 原版 jar 拷成 `<id>.jar`；**不留 `install_profile.json`、不留 installer**；processor 产出落共享 `libraries/`，失败不回滚（靠幂等续跑）。

## 3. HMCL 启动链（`launch/DefaultLauncher.java` + `game/`）

- **启动层完全不合成 module path**：`-p/--module-path`、`--add-modules`、`--add-opens`、`-DignoreList`、`-DlibraryDirectory` **全部来自 installer 写进版本 json 的 `arguments.jvm`**，HMCL 只做 `${...}` 展开（`:313-344`）。mainClass 取 manifest（NeoForge 为 `cpw.mods.bootstraplauncher.BootstrapLauncher` 或 26.x 的 `net.neoforged.fml.startup.Client`）。
- **回退**：`arguments.jvm == null` 时才用 `DEFAULT_JVM_ARGUMENTS`（含 `-cp ${classpath}`、`-Djava.library.path=${natives_directory}`）。
- **必须提供的占位符**（`getConfigurations:622-651`）：`${classpath}`、`${classpath_separator}`、`${file_separator}`、`${library_directory}`/`${libraries_directory}`、`${primary_jar}`/`${primary_jar_name}`、`${version_name}`、`${natives_directory}`、`${assets_root}`、`${assets_index_name}`、`${auth_*}`。`${classpath}` = 库（按序去重、过滤规则不符与 native、且文件存在）+ 主 jar。
- **ignoreList 两级修复**：安装规范化期（bootstrap ≥0.1.17 时补 `${primary_jar_name}`，`LaunchManifestNormalizer:193-222`）+ 启动期（<0.1.17 时把子串改写成**精确绝对路径**，`DefaultLauncher:551-620`，**依赖真实 maven 目录布局**）。
- natives：先清目录再幂等解压到 `<instanceRoot>/natives-<platform>`；`-Djava.library.path` 由清单占位符提供。
- Java 选择：按 `manifest.javaVersion.majorVersion`；**NeoForge 不触发 `MODDED_JAVA_*`**（`GameComponentType.FORGE.matchLibrary` 在存在 NEO_FORGE 时返回 false）。
- 日志：HMCL **忽略 manifest 的 `logging.client.file`**，自管 `log4j2.xml` + `-Dlog4j.configurationFile`。

## 4. HMCL 数据模型 / 互操作（`game/`）

- **盘上**：`versions/<id>/<id>.json` + `<id>.jar`（**有 jar 复制件**）；`hint=="local"` 的库落实例内 `versions/<id>/libraries/`；共享 `libraries/`+`assets/`；**目录名 = 身份**（`manifest.id` 不符只在内存 `withId(目录名)`，不回写）。
- **`inheritsFrom` 合并**（`GameInstanceManifest.merge:66-91`）：标量「子非空则子」；`arguments`/`libraries` = **子 ++ 父**；`compatibilityRules` = **父 ++ 子**；`minimumLauncherVersion` 取 max；`root=true`；`inheritsFrom=null`；**`complianceLevel` 只取子（特例，父被丢弃）**。
- **`patches[]` 合并**（`Builder.merge:904-931`）：按 `priority` **升序**应用（`PRIORITY_MC=0`、`PRIORITY_LOADER=30000`）；标量覆盖；`arguments`/`libraries`/`compatibilityRules` 追加；**`jar`/`inheritsFrom`/`hidden` 被忽略**。
- **写盘 = 顶层扁平 + 保留 `patches`（两者都给）**：写 `resolved.withPatches(manifest.patches())`；读取时若 `root:true` 且 `patches` 非空则**丢弃顶层、从空 manifest 重放 patches** ⇒ **`patches` 必须自洽完整**。`fromManifest` 折叠时**必须保留 `complianceLevel`/`compatibilityRules`/`logging`**（否则丢 log4j 配置）。
- 库去重（`uniqueLibraries`）**只在启动规范化期**做；安装期不去重。
- 版本比较：MC 用 `GameVersionNumber`（**数值段比较** ⇒ `1.7.10 < 1.10.2`；枚举序 `SNAPSHOT < PRE_RELEASE < RC < GA`），loader/库用 Maven 式 `VersionNumber`，区间用 `VersionRange`。

## 5. 真 installer 解剖（2026-09-15 实测三样本）

实物：**工作区根** `stuffs/research/neoforge/`。installer 自身入口统一是 `net.minecraftforge.installer.SimpleInstaller`（带 GUI），**我们不必跑它**，只当 zip 容器。

| | `forge-1.20.1-47.1.106` | `neoforge-21.1.250` | `neoforge-26.1.2.109` |
|---|---|---|---|
| 大小 | 7.85 MB | 6.97 MB | 11.32 MB |
| `profile` | `forge` | `NeoForge` | `NeoForge` |
| `minecraft` | 1.20.1 | 1.21.1 | 26.1.2 |
| `data` 条数 | 13 | 10 | **3** |
| `processors` | 10（client 侧 6 需 JVM） | 10（client 侧 5 需 JVM） | **2（client 侧 1）** |
| `libraries` | 40（13.8 MB） | 70（25.4 MB） | 30（13.3 MB） |
| `mainClass` | `cpw.mods.bootstraplauncher.BootstrapLauncher` | 同左 | **`net.neoforged.fml.startup.Client`** |
| `arguments.jvm` | 18 条（含 `-p`/`--add-modules`/`-DignoreList` 长串/`-DmergeModules`/`-Dfml.*LayerLibraries`） | 15 条（含 `-p`/`--add-modules`/`-DignoreList=client-extra,${version_name}.jar`） | **6 条（无 `-p`/无 `--add-modules`/无 `-DignoreList`）** |
| 工具 | installertools 1.3.0（非 fatjar，17 伴随 jar） | installertools 2.1.2（非 fatjar，19 伴随） | installertools **4.0.12:fatjar**（classpath 仅自身） |
| 重命名 / LZMA | FART 0.1.22 / binarypatcher 1.1.1 | ART 2.0.3 / binarypatcher 2.1.2:fatjar | 并入 installertools |
| installer 内嵌 universal | 有（2.14 MB） | **无** | 有（7.58 MB） |

**`arguments.jvm` 原文要点**（全文见实物 `stuffs/research/neoforge/extracted/`）：
- 1.20.1 `-p` 值形如 `${library_directory}/cpw/mods/bootstraplauncher/1.1.2/bootstraplauncher-1.1.2.jar${classpath_separator}…`（8 个模块 jar），后接 `--add-modules ALL-MODULE-PATH` 与 4 组 `--add-opens`/`--add-exports`；
- 21.1.250 同形（bootstraplauncher 2.0.2 + securejarhandler 3.0.8 + asm 9.10.1 + JarJarFileSystems 0.4.1）；
- 26.1.2.109 只剩 `-Djava.net.preferIPv6Addresses=system`、`-DlibraryDirectory=${library_directory}`、两组 `--add-opens`/`--add-exports`。

**processor 表（`Main-Class` + 作用）**：`installertools.ConsoleTool`（`--task MCP_DATA`/`DOWNLOAD_MOJMAPS`/`MERGE_MAPPING`/`EXTRACT_FILES`/`BUNDLER_EXTRACT`/26.x 的 `PROCESS_MINECRAFT_JAR`）、`jarsplitter.ConsoleTool`（拆 slim/extra）、`fart.Main`/`art.Main`（重命名整个 MC）、`binarypatcher.ConsoleTool`（施加 LZMA 补丁）。

**`data` 值三分类**：`'literal'`（含 3 个 `*_SHA`）、`[maven 坐标]`、installer 内路径（`/data/client.lzma`）。**26.x 的 `data` 无 MAPPINGS/MOJMAPS ⇒ 安装期不需要联网下 Mojang mappings**（1.20.1/21.1.x 需要）。

**上游佐证**（`ref/NeoForge` HEAD）：installer/version.json 生成逻辑在 `buildSrc/src/main/java/net/neoforged/neodev/installer/`（`CreateLauncherProfile.java:106-131`、`CreateInstallerProfile.java:110-142`），**逐字对得上 26.1.2.109**；HEAD 的 `InstallerProcessor` 只有 `INSTALLERTOOLS`。1.20.1/21.1.x 那套 10-processor + FART + `-p` 的生成逻辑**不在 HEAD**（在 git 历史里），故旧形态的权威证据只有**实测的真 installer json**。

## 6. 我方现状测绘（主仓，2026-09-15 复核）

三层职责：**ArkTS**（安装编排、识别、**拼 JVM argv**、classpath 平铺）→ **native**（`LaunchJvm` 只设 env + 预 dlopen 渲染器 + `JLI_Launch`，**不改 argv**）→ **JVM/launcher.jar**（读 json、拼 game argv、反射调主类）。

确凿证据（关键切分）：
- **`patches[]` 只在 ArkTS 侧合并**：`VersionResolver.mergePatch`/`sortedPatches`；Java `VersionJson.java` **无 `patches` 字段**。
- **JVM argv 由 ArkTS 拼**：`MinecraftLauncher.buildLaunchArgv`（`meowcraftLaunch===true` 分支只追加 `MeowLauncher → player → id`）；**game argv 由 Java 拼**（`ArgBuilder.build`）。
- Fabric 安装：`installFabricVersion` → 三批下载 → `composeFabricManifest`（**顶层扁平 + `patches[game,fabric]`**）→ 写 `versions/<name>/<name>.json` + `<name>.jar`；库按 maven 树落 `libraries/`。
- 启动：`GameLauncher.launchGame` → `ClasspathStager` 平铺到 `cacheDir/mc-cp/<key>-<id>/` → `-cp "<dir>/*"` → `startJvm`。
- **已具备**：`makeMacros`/`expand` 占位符机制、`VersionResolver` 的继承/补丁合并（但为**固定字段投影**，会丢 `logging`/`downloads` 等）、`InstanceSettings`（逐实例）。

## 7. 安装期执行 JVM 的可行性论证（本仓，2026-09-15）

| 候选 | 结论 | 依据 |
|---|---|---|
| ① 独立 `:installer` 进程 + `JLI_Launch` | ✅ **可行（首选外壳）** | `LaunchJvm` 全程**不碰 surface**；env/`OHOS_JAVA_HOME`/`OHOS_DL_DIR`/pipe 日志/`_exit` 全套现成；唯一硬改 = 桥支持**无渲染器（headless）**（现 `rendererSo/rendererEnv` 为空即 abort，且无条件预 dlopen） |
| ② 直接 exec JRE 的 `bin/java` | ❌ **不可行** | `bin/java` 确实在 JRE 数据里，但落在 **el2**（`filesDir`，禁执行且 `Untar` 不 chmod）；el1 侧只有 29 个 `.so`，无 `bin/java` |
| ③ 从 JVM 内 `Runtime.exec`/`ProcessBuilder` | ❌ **判不可行** | 需要可执行 `java` + `jspawnhelper`（都在 el2）；el2 禁执行（见 [`决策与不变量.md`](决策与不变量.md) §8）；无 el1 可执行 `java` |
| ④ 同 JVM 内 `URLClassLoader` 反射跑 processor 的 `main` | ✅ **可行（置于独立进程内）** | 逐 jar 字节码扫描：installertools 1.3.0/2.1.2、jarsplitter、binarypatcher **无 `System.exit`**；ART/FART/26.x installertools **有**，但**仅在参数错误分支**（源码已核）⇒ happy path 安全，错误路径只杀 `:installer` 进程 |
| ⑤ 同进程二次 `JLI_Launch` | ❌ **不可行** | HotSpot 一进程一 JVM（`JNI_EEXIST`）；且 `JvmLauncher` 已有「进程内只能起一次」单例守卫 |

**推荐 = ① + ④**：新增 `:installer` 进程 → 起**一个** JVM → 由净室 Java 驱动类在该 JVM 内**每 processor 一个 `URLClassLoader`** 顺序反射执行 `main`。备选 = ① 外壳 + **每 processor 一次 JVM**（零 Java 侧新代码，代价 = N（≤6）次冷启）。

**前置问题（无论选哪条路）**：A 桥 headless 化；B 可写且**真实 maven 布局**的 `libraries/` 树；C 占位符解析（`{VAR}`/`'lit'`/`[坐标]` + 内建变量）；D `{MINECRAFT_JAR}` 必须隔离到独立 temp；E `DOWNLOAD_MOJMAPS` 直下不起 JVM；F outputs sha1 幂等 + 校验（含 zlib 降级）；G NeoForge maven 源与镜像；H 安装 JVM 的 `HOME`/tmp 指向可写 el2（el2 无 `/tmp`）。

**待实机验证（2026-09-15 登记）**：el1 文件能否 `execve`；无窗口 `:installer` 进程生存期；进程内 ART `withJvmClasspath()` 是否成立；产物 sha1 确定性；`ProcessMinecraftJar` 的线程数/OOM。

## 8. 补充取证：LegacyInstaller / InstallerTools / 真 jar 静态分析（2026-09-15 第二轮）

> 触发：用户新 clone 了 `ref/LegacyInstaller` 与 `ref/InstallerTools`，并注意到 `InstallerTools` README 写「由 LegacyInstaller 运行，**或有时被第三方 MC 启动器直接调用**」。

### 8.1 `ref/LegacyInstaller` = **现役 installer 源码**（名字里的 "Legacy" 不代表过时）

- `build.gradle:58` `MAIN_CLASS = 'net.minecraftforge.installer.SimpleInstaller'`，与我们三个真 installer jar 的 `Main-Class` 一致。
- `git describe --tags` = `3.0-48-gb8e9393`；`build.gradle` 用 `gradleutils.version`（tag + 提交数）→ 与真 jar 的 `Implementation-Version: 3.0.48`（21.1.250 / 26.1.2.109）**精确吻合**（1.20.1 的旧样本是 3.0.24）。
- 分发形态：installer jar = **本仓的 installer 类** + NeoForge 侧注入的 `install_profile.json` / `version.json` / `data/`（`build.gradle` 的 `productionTestJar` 合并、`exclude '/**/*.class'`）。即 **NeoForge 版本号不改变 installer 代码**（21.1.250 与 26.1.2.109 都是 3.0.48，类清单仅差 1 个内部类）。
- 命名由来无官方说明（仓内无 README）；推断为「从 Forge 继承的老架构保留兼容」——**待与上游确认**。

### 8.2 官方 CLI 契约（headless 可跑）

| 开关 | 参数 | 语义 |
|---|---|---|
| `--installClient` / `--install-client` | `[dir]`（默认 `~/.minecraft`） | 客户端安装 |
| `--installServer` / `--install-server` | `[dir]`（默认 `.`） | 服务端安装 |
| `--server-starter` / `--server.jar` / `--server-jar` | — | 额外下 server starter |
| `--offline` | — | 禁网络（只认内嵌 `/maven/`、`~/.m2`、目标 `.minecraft/libraries`）**⇒ 官方非 fat jar 内嵌物太少，基本不可用** |
| `--debug` | — | 保留中间文件 |
| `--skip-hash-check` | — | 跳过 processor 产物 sha1 校验（**沙箱内 zlib 差异的兜底**） |
| `--mirror` | `<url>` | 指定镜像 |
| `-h` / `--help` | — | 帮助 |

- **无 `--installDir`、无 `--headless`**；无 action 且 headless 时**自动转服务端**（3.0.48 新增，1.20.1 的 3.0.24 无此分支）。
- **GUI 影响面**：AWT/Swing 只在 `ui/` 包与 `SimpleInstaller.error`/`Action.error` 的日志分支；显式给 `--installClient` 时 `action != null`，`GraphicsEnvironment.isHeadless()` 不会执行、Swing 不加载。**我们的随包 JRE 含 `java.desktop`（43 模块，2026-09-15 核实 `release` 的 MODULES）** ⇒ 无 `NoClassDefFoundError` 之虞。
- **退出码**：成功 = 0（3.0.48 已移除成功路径的 `System.exit(0)`）；失败 = `System.exit(1)`（**必须进程隔离**）。
- **进度通道 = 纯 stdout/stderr 文本**：sysprop `net.neoforged.progressmanager.enabled=true` + ANSI 行 `\033[决策与不变量.md](决策与不变量.md) §21） |
| 3 | **`jna-5.10.0.jar` 缺失 ⇒ 同一个 `/META-INF/versions` 异常** | 1.20.x 世代的 `-DmergeModules=<文件名列表>` 让 BN **按文件名**在 classpath 里查 jar；而这些 jar **不在任何清单里**（vanilla 1.20.2 只声明 jna **5.13.0**） | 从 jvm 参数解析 `mergeModules` → 文件名拆 artifact/version、**group 取「同 artifact 的已声明库」** → 安装期补下（`maven.neoforged.net/releases` 有全量 Central 代理）、启动期补进 classpath（**主仓** `NeoForgeInstaller.resolveMergeModuleEntries` 双侧使用） |
| 4 | `--width ${resolution_width}` → **joptsimple NumberFormatException**（启动即退） | MC json 里 `--width/--demo/--quickPlay*` 是 **`features` 门控**的，而我们的规则过滤只看 `os` ⇒ 把**未展开的宏参数**发了出去 | `ruleAllows` 对**非空 `features`** 一律判不匹配（与安装侧口径统一）（`MinecraftLauncher`） |

**附带发现（非致命、已治）**：`-Dfml.earlyprogresswindow=false` 是 **Forge 时代**的旗标，**NeoForge 21.x 不读它**（早窗口开关在 `config/fml.toml` 的 `earlyWindowControl`）——我们选择**让早窗口正常工作**（修 `meowMakeCurrent(NULL)` 的 release 语义），而不是禁掉它。

## 10. 证据台账


- 真 installer 三件 + 解出物 + processor jar：**工作区根** `stuffs/research/neoforge/`。
- HMCL 源码：`ref/HMCL/HMCLCore/src/main/java/org/jackhuang/hmcl/{download/neoforge,download/forge,launch,game}/`；文档（`ref/HMCL/docs/`）未涉 NeoForge 安装细节。
- NeoForge loader 源码（非 installer 生成器）：`ref/NeoForge/`（`projects/`、`src/`、`buildSrc/`）。
- 我方代码测绘与落点地图：见 [`NeoForge支持-改动方案.md`](../../90-archive/NeoForge支持-改动方案.md) §3/§4。
**第三轮（2026-09-28，JVM 边界专查）**：HMCL 安装链逐行取证 → [`NeoForge安装链-逐行取证.md`](NeoForge安装链-逐行取证.md)；「不跑 JVM 能否装成」的逐 processor 判定 + maven 联核实况 → [`NeoForge无JVM安装-可行性与取证.md`](NeoForge无JVM安装-可行性与取证.md)；原始报告两份在 工作区根 `stuffs/research/hmcl-neoforge/A-hmcl-install-chain.md` 与 `stuffs/research/hmcl-neoforge/B-jvm-free.md`。

## 11. 第三轮取证：覆盖 §0.4 的 JVM 结论 + 一处计数 + 一条否定结论

- **修正 §0.4「安装期必须真跑 JVM」**：该判据对 **1.20.1 / 1.20.2–1.21.x 成立**（各卡 1 个整-jar 字节码 remapper：FART 0.1.22 / ART 2.0.3），但**对 26.x 不成立** —— 26.x client 侧只有 1 个 processor（installertools 4.0.12 fatjar 的 `PROCESS_MINECRAFT_JAR`），其 args **无 `--input-mappings`** ⇒ 不做任何重命名/映射（`ProcessMinecraftJar.java:217-224` 的 deobfuscate 整段被 `inputMappingsFile != null` 门住），只剩「解 bundle + 施加 LZMA/GDIFF 补丁 + 抽出内嵌库 + 写确定性 zip」⇒ **纯 native 可重实现**（真 profile 证据：工作区根 `stuffs/research/neoforge/extracted/26.1.2.109.install_profile.json:66-84`）。
- **修正 §5 表计数**：`1.20.2–1.21.x` 的 **client 侧 processor 实为 6 个**（原记 5）。
- **新增否定结论**：**「下载 processor 产物代替构建」不成立**（2026-09-28 联网核实 NeoForge maven 目录树）—— `net.neoforged:neoforge*:client`、`net.neoforged:minecraft-client-patched`、`…:mappings-merged@txt` 等**均未发布**；profile 里的 `PATCHED`/`slim`/`extra`/`srg` 都是 `libraries/` 下的**本地输出占位路径**（唯一可行替代 = 我们自建分发位做离线预构建，且每版本需预构建一次）。
- **适用面**：本修正**不推翻** §7「headless `:installer` 进程 + `JLI_Launch`」对 **2in1** 的可行性（实机状态见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 22 条）；其价值在 **phone**（拿不到独立进程宿主）—— 26.x 因此出现一条"零 JVM"的新可能路径，登记见 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §E。

相关：[`Fabric支持-调研.md`](Fabric支持-调研.md)、[`Fabric支持-改动方案.md`](../../90-archive/Fabric支持-改动方案.md)、[`../README.md`](../README.md)、记忆 `hmcl_neoforge_three_chains`。
