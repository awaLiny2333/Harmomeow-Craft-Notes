# NeoForge 支持改动方案（修订 5）—— 自研编排（对齐 HMCL）+ 无窗 UIAbility 载体 + **三形态实机打通**

> 已归档（2026-10-01；因为其仍有效的结论已并入现役档（启动链-总览 / 安装链-总览 / 决策与不变量）；现役口径见 [`启动链-总览.md`](../20-design/launch/启动链-总览.md)）。

> 日期：2026-09-16（**修订 5**：⑥ **1.20.2 / 1.21.1 / 26.x 三形态实机可玩**（用户 2026-09-16 确认）；⑦ 启动期四个坑已修（见 [`NeoForge支持-调研.md`](../20-design/launch/NeoForge支持-调研.md) §9）；⑧ 随包 jar 的 `Multi-Release` 不实声明已根治、tar 重打并升 `EXTRAS_VERSION=20260916-script-rebuild`；原 **修订 4**：⑤ **安装载体定为「无窗 UIAbility」**——2026-09-15 POC 实测无窗口/无 dock 条目、零打包改动，依据见 [`安装期JVM载体-调研.md`](安装期JVM载体-调研.md) §8；原 **修订 3**：① 范围仍为 **MC 1.20.2+**；② 主线**回退为自研安装编排**，与 HMCL 对齐；③ 官方 installer **只当数据容器**（`install_profile.json` / `/version.json` / `data/*.lzma`），**不在运行时加载它的任何类**；④ 写盘确定为 **HMCL 形态**（顶层扁平 + `patches[game, neoforge]`））
> 前置：[`NeoForge支持-调研.md`](../20-design/launch/NeoForge支持-调研.md)（HMCL 三链 + 真 installer 解剖 + `LegacyInstaller`/`InstallerTools` 契约 + 我方现状）。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 22 条](../00-current/现状基线.md)。

---

## 0. 修订 5 要点

| # | 项 | 结论 |
|---|---|---|
| 1 | **安装载体（本次定案）** | **无窗 UIAbility**：静态 `process: ":neoinstall"` 的 UIAbility（**不 `loadContent`**）+ 父进程 `startAbility` 传 `StartOptions{processMode: NEW_PROCESS_ATTACH_TO_PARENT, startupVisibility: STARTUP_HIDE}`（SDK 要求二者成对；@since 12；仅 2in1/Tablet）。实测：**完全无窗口、无 dock 条目、主 UI 无干扰**；该进程内走 HSP 的 JRE 链路跑通（`JLI_RETURNED code=0`）；**零打包改动** |
| 2 | **native 子进程（A 路线）** | **不采用**：技术成立，但要求 JRE `.so` 落在**入口 HAP**（进程 loader namespace 只认自己模块 libs + 已加载 HSP + 系统）+33MB/改架构（实测见调研 §8.1/§8.2）。保留为**已评估备选** |
| 3 | **桥的沉淀（已完成）** | headless 模式（`rendererLib` 传空 ⇒ 跳过渲染器预 dlopen / 渲染 env / glthread 失效安全）+ 退出码文件通道（`<filesDir>/meow-neo-jvm-result.txt`，`JLI_BEGIN` / `JLI_RETURNED code=N`）。回归：MC 26.2 Fabric 实机无问题（用户 2026-09-15 确认） |
| 4 | **进度（2026-09-15）** | **T0 完成**；**T1 的列表/版本号破解/源降级已落地**（`common/data/NeoForgeVersionList.ets` + `DownloadContract` 的 NeoForge 段：官方 Maven API + BMCLAPI 专用接口 + `4xx 不解析 body` + `200+空数组也继续下一源`） |
| 5 | 探针清理 | 本轮所有探针（native 子进程探针 / 探针数据层 / 无窗 ability / UI 入口与文案）已删除；结论落 [`安装期JVM载体-调研.md`](安装期JVM载体-调研.md) §8 |

### 修订 2 → 修订 3（历史）

| # | 修订 2 | **修订 3** | 理由 |
|---|---|---|---|
| 1 | 主线 = 跑官方 `SimpleInstaller --installClient` | **主线 = 自研编排（我们自己解析 profile、自己跑工具）** | **与 HMCL 对齐**；不依赖 install 器的类/行为（`launcher_profiles` 前置、`System.exit`、进度通道、名称与血统的模糊性） |
| 2 | installer jar = 要执行的程序 | **installer jar = 只读的数据容器** | 卸载「疑似继承的 installer」的不确定性：我们只读它的 3 类数据，不加载它的代码 |
| 3 | 产物 = 官方薄 `inheritsFrom`（形态①） | **产物 = HMCL 形态**（顶层扁平 + `patches[game, neoforge]`） | 对齐 HMCL；**复用我们 Fabric 已有的写盘套路**；⇒ **不需要形态① 递归解析**（少一大块新逻辑） |
| 4 | 安装执行 = 官方 installer 内部反射 | **`:installer` 进程 + 每 processor 一次 JVM**（HMCL 语义：进程隔离 + 退出码权威 + 无状态泄漏）；备选 = 单 JVM 内逐 processor 隔离 `ClassLoader` | 对齐 HMCL 的「一次调用一个工具、看退出码」；规避进程内静态态污染 |
| 5 | 需要理解/实现 Forge 的换行参数 | **参数原样来自 profile，只做占位符替换** | 我们不需要「理解」`-DmergeModules`/`-Dfml.*LayerLibraries` 之类的语义；也**绕过** `InstallerTools` 2.1.2 与 4.x 的 CLI 漂移 |

> **自编范围**（用户 2026-09-15：「有必要的话可以自编一些东西」）：自研编排的产物全部落在 **ArkTS 侧**——zip/`MANIFEST` 读取、占位符展开、变量表、下载与 maven 树落盘、编排与产物校验。**无需自编 Java**（`InstallerTools` 与 processor 工具一律按 profile 给的坐标使用，与 HMCL 相同）。若日后采用「单 JVM 内多 `ClassLoader`」的加速模式，再自编一个净室 Java 驱动类。

---

## 1. 目标与验收判据

**目标**：鸿蒙侧完成 NeoForge（1.20.2+）的「选版本 → 安装 → 启动」，产物与 HMCL 双向兼容。

| # | 判据 | 说明 |
|---|---|---|
| V1 | **我们装 → HMCL 能读能起** | 写盘为 HMCL 形态（`root:true` + 自洽 `patches[]`），`game` patch 需带 `complianceLevel`/`compatibilityRules`/`logging` |
| V2 | **HMCL 装 → 我们能读能起** | 两形态均可：HMCL 自装 = 顶层扁平 + `patches[]`（我方 ArkTS 已有合并）；官方安装器形态① = 薄 `inheritsFrom`（**已有实现，2026-09-15 前未实机验证**，与 NeoForge 主线无关，可作为独立课题） |
| V3 | **端到端跑通** | 至少覆盖 `-p` 形态（1.20.2–1.21.x）与 26.x 新形态各一 |
| V4 | **可重入** | 中断后重跑成功（多数工具先删后写、非原子 ⇒ 靠重跑与产物断言） |

---

## 2. 架构决策

### 2.1 主线数据流（自研编排）

```
主进程 ArkTS（安装编排 = 本次新增主体）
 1) 列表/选版本（1.20.2+ 两条 Maven API + BMCLAPI；版本号破解 → MC 版本）
 2) 下 installer jar（官方 maven / 镜像）→ 当 zip 读：
      · install_profile.json（spec/minecraft/version/json/libraries/processors/data）
      · /version.json（= 将来 neoforge patch 的内容源）
      · data/*.lzma（如 client.lzma）解到 temp
 3) 下载 install_profile.libraries 全部（processor 工具 + 依赖）→ 落 maven 树 libraries/
 4) 准备 vanilla：原版 client jar → 独立 temp 副本（作 {MINECRAFT_JAR}）+ 作为 game patch 底座
 5) 逐 processor（按 profile 顺序；只跑 client 侧；详见 §3）：
      · ArkTS 展开 args（占位符/坐标→真路径/字面量/installer 内文件路径）
      · startAbility(:installer, argv=[java, -cp <profile classpath + processor.jar>, <jar MANIFEST 的 Main-Class>, ...args])
      · 等进程结束 → 退出码 + **断言产物存在/sha1**（工具 fail-open，不能只看退出码）
 6) 写盘（HMCL 形态）：versions/<id>/<id>.json = 顶层扁平 + patches[game, neoforge]
                           versions/<id>/<id>.jar  = 原版 client jar 复制件
 7) 刷新实例列表（识别为 NeoForge）
        │
        ▼  启动时（启动链改造，见 §4）
:game 进程：manifest 派生 JVM 参数（含 -p/--add-modules/--add-opens/-DignoreList/-DlibraryDirectory）
            + NeoForge mainClass + game 参数 → JLI_Launch
```

### 2.2 为什么这样最「少不确定」

| 不确定项（修订 2 里存在的） | 修订 3 的处置 |
|---|---|
| installer 的类/行为（`launcher_profiles.json` 前置、注入、`System.exit`、日志/进度通道、CWD） | **不加载它的类**，只读 3 类数据 ⇒ 全部消失 |
| installer 名称/血统（`LegacyInstaller` 为何叫 Legacy） | 与我们无关：我们只关心**数据格式**（`install_profile.json` 的 spec 语义），且以真 jar 实测为准 |
| 「Forge 的神奇参数」（`-DmergeModules`/`-Dfml.*LayerLibraries`/长 `ignoreList`） | **照抄 profile/`/version.json` 原文**，只替换占位符 ⇒ 不需要理解语义 |
| `InstallerTools` CLI 漂移（2.1.2 vs 4.x 的 `--base/--merge` 与 `--clean/--apply`） | **参数原样来自 profile** ⇒ 漂移与我们无关（我们是 profile 的执行者，不是 CLI 的作者） |
| 工具 fail-open（错参数也退 0） | 我们**自行断言产物**（存在性 + sha1），不依赖退出码 |
| 现代 profile **无 `outputs` 字段** | 自建完成度门控：以 `data` 里已知产物（如 `PATCHED`、`MC_SLIM`…）的存在性/尺寸为判据 |
| processor 的 `System.exit` 杀掉宿主 | 每个 processor 独立 `:installer` 进程 ⇒ 只杀它自己 |
| 平铺 classpath 与 `-p` 冲突 | 见 §4.4（NeoForge 走真 maven 树 + 按序显式 classpath） |
| `-Djava.system.class.loader` 与 NeoForge 类加载冲突 | 见 §4.5（绕过 `meow.launcher`） |

### 2.3 与 HMCL 的差异（仅一处，且是被平台逼出来的）

HMCL 在桌面可 `java -cp … Main args` 派生**子进程**；我们平台上**无法 exec**（JRE 数据在 el2、禁执行；el1 无可执行的 `java`）⇒ 我们改用 **`startAbility(:installer)` 逐处理器起 JVM**——语义等价（独立进程、退出码、无状态泄漏），代价是 N 次 JVM 冷启动（client 侧 N = 1（26.x）…6（1.21.x））。

### 2.4 共同前置

| # | 事项 | 说明 |
|---|---|---|
| P1 | **桥 headless 化** | 现桥在 `rendererSo`/`rendererEnv` 为空时 abort、无条件预 dlopen 渲染器、且自检 argv 里的 `-Dorg.lwjgl.opengl.libname`。安装 JVM 要绕开这三处（跳过渲染器预加载与 GL env 注入） |
| P2 | **载体（定案：无窗 UIAbility）** | 静态 `process: ":neoinstall"` 的 UIAbility（不 `loadContent`）+ `startAbility` 传成对的 `processMode`/`startupVisibility`。实测无窗、零打包改动（调研 §8.3）。**注意**：`module.json5` 中 UIAbility 必须声明 `startWindowIcon`/`startWindowBackground`，否则 schema 校验失败 |
| P3 | **结果回传（已完成）** | 桥在 headless 模式追加写 `<filesDir>/meow-neo-jvm-result.txt`（`Paths.NEO_JVM_RESULT`）；安装编排据此判 processor 成败 |
| P4 | **可写工作区** | job/temp/`libraries/`/`versions/` 均在 el2 可写区；`HOME`/tmpdir 显式指向（el2 无 `/tmp`） |
| P5 | **installer jar 获取** | 官方 maven（+ 镜像候选）；无 sha1 ⇒ **解包 + 读两份必需 JSON**（`install_profile.json` 与内嵌启动清单，缺任一即判坏）+ **复用期自愈**（见 §6.1）；**按需下载 + 缓存** |

---

## 3. 安装链改动面

| # | 需求 | 现有最接近 | 改动 |
|---|---|---|---|
| A1 | NeoForge 版本列表 | `VersionInstaller.fetchManifest` + `DownloadContract.manifestCandidates` | 新增 `net/neoforged/neoforge` 两条 Maven API + BMCLAPI `/neoforge/list/{mc}`；**版本号破解 → MC 版本** |
| A2 | 降级语义 | 候选逐个试 | **4xx 立即放弃不解析 body**；**200 + 空数组也判该源无结果并继续下一源** |
| A3 | installer jar | `Downloader.downloadFile` | URL `.../releases/net/neoforged/neoforge/<v>/neoforge-<v>-installer.jar`；解包 + 读两份必需 JSON（见 §6.1） |
| A4 | **读 installer 数据**（新增） | 无 | ArkTS zip 读取：`install_profile.json` + `/version.json` + 解 `data/*.lzma` 到 temp |
| A5 | **库下载**（新增细粒度） | `VersionInstaller.libraryItem`/`mavenPath` | 按 `install_profile.libraries[]` 全量下到 maven 树（含 processor 工具与依赖） |
| A6 | **占位符/变量表**（新增） | `MinecraftLauncher.makeMacros`（JVM 参数用） | 新增 installer 版展开器：`{VAR}` / `'literal'` / `[group:name:version[:classifier][@ext]]` → 真路径；内建 `SIDE=client`、`MINECRAFT_JAR`、`MINECRAFT_VERSION`、`ROOT`、`INSTALLER`、`LIBRARY_DIR`；`data` **只取 client** |
| A7 | **读 processor 的 `Main-Class`**（新增） | 无 | ArkTS 读 processor jar 的 `META-INF/MANIFEST.MF`（`-cp` 方式必须显式主类） |
| A8 | **编排与执行**（新增） | 无 | 逐 processor：`startAbility(:installer)` + 退出码 + 产物断言；`DOWNLOAD_MOJMAPS` **由我们直接下载** `client_mappings`（省一次 JVM，HMCL 同款） |
| A9 | **写盘（HMCL 形态）** | `VersionInstaller.composeFabricManifest`（Fabric 模板） | 新增 `composeNeoForgeManifest`：`game` patch（priority 0，vanilla 全字段）+ `neoforge` patch（priority 30000，来自 `/version.json` 的 mainClass/libraries/arguments）+ 顶层扁平 + `<id>.jar` 复制件 |
| A10 | 实例识别 | `VersionResolver.detectLoader` | 识别 NeoForge：patch `id==='neoforge'`；兜底看库 `net.neoforged.fancymodloader:core\|loader` 或 mainClass |
| A11 | 渲染后端/LWJGL | `RendererPolicy`（按 `mcVersion`） | 无需改；但 `mcVersion` 要从 **game patch 的 version** 取（HMCL 形态下即成） |

---

## 4. 启动链改动面（工作量依旧最大）

### 4.1 JVM 参数 = manifest 派生（必须进 `JLI_Launch` 的 argv）

`-p/--module-path`、`--add-modules ALL-MODULE-PATH`、`--add-opens`、`--add-exports`、`-DignoreList`、`-DlibraryDirectory` 全在 `neoforge` patch 的 `arguments.jvm` 里；`-cp ${classpath}` 由 vanilla 侧提供：

1. **分区显式化**：启动器固定参数在前、manifest 派生参数在后；不得覆盖 NeoForge 的 `--add-opens`/`--add-modules`；
2. `-cp` 与 `-p` **共存**；
3. `ignoreList` **原样保留**（不自己推导）。

### 4.2 占位符补全

新增 `${library_directory}`（= `gameRoot/libraries`）、`${classpath_separator}`、`${file_separator}`、`${primary_jar}` / `${primary_jar_name}`（= `<id>.jar`，`ignoreList` 要用）。

### 4.3 classpath：真 maven 树 + 按序（弃平铺）

- 现「平铺 + `-cp "<dir>/*"`」对 NeoForge 不适用（`-p` 指向真树；`*` 顺序不定且与真树双份库，ASM/log4j 易冲突）。
- **方案**：NeoForge 实例走 **真 maven 树 + 按 manifest 库顺序显式拼接**；原版/Fabric 维持平铺（两条路径并存）。

### 4.4 **绕开 `-Djava.system.class.loader`（高风险点）**

- 现状恒以 `meow.launcher.MeowLauncher` 为主类并设 `-Djava.system.class.loader=meow.launcher.MeowClassLoader`；NeoForge 有自己的模块层/类加载 ⇒ 叠加属**未知高风险**（同 Fabric `KnotClassLoader` 那类）。
- **建议**：NeoForge 实例**直接以 NeoForge 的 mainClass 作为 JVM 主类**（ArkTS 全量组 argv；`buildLaunchArgv` 里现存的 game 参数分支正好可复活），不设自定义 system class loader。
- **回退**：保留 `MeowLauncher` 反射路径（需实机验证兼容性）。

### 4.5 其它

- natives 沿用 `runDir/natives`；日志沿用顶层读取；Java 选择按 manifest `javaVersion`（1.20.2+ → 17/21，2026-09-15 登记待验证）；隔离沿用逐实例设置。

---

## 5. 分阶段实施

| 阶段 | 目标 | 关键改动 | 验收 |
|---|---|---|---|
| ~~**T0 前置冒烟**~~ **已完成（2026-09-15）** | 证明「无感起 JVM」 | 桥 headless（P1）+ 载体实测（P2：定为无窗 UIAbility）+ 结果回传（P3） | 实测：**无窗口/无 dock 条目**、`java.home` 正确、`JLI_RETURNED code=0`；游戏回归（MC 26.2 Fabric）无问题 |
| **T1 列表与下载** | 选得到、下得动 | A1–A3（1.20.2+ 的列表/破解/降级语义 + installer jar 与镜像） | 列出并可下到 installer |
| **T2 数据解析与库落盘** | 数据齐 | A4–A5 + A6/A7（profile 解析、变量表、maven 树落盘、MANIFEST 读取） | `libraries/` 与 profile 清单一致；变量表展开正确 |
| ~~**T3 编排执行**~~ **已完成（2026-09-16）** | 装得完 | A8 + `:neoinstall` 无窗进程 + 退出码文件通道 + 有 `JLI_BEGIN` 无退出码 ⇒ 不再「快速判失败」、等到 deadline 出码或超时（瞬时进程探测不可信：没列出≠没在跑） | 产物齐备（PATCHED 断言）；1.20.2（6 processor）与 26.x（1 processor）实机通过 |
| **T4 写盘与识别** | 看得见 | A9–A11：`composeNeoForgeManifest`（HMCL 形态）+ 类型识别 + 列表/文案 | V1 判据（HMCL 可读） |
| ~~**T5 启动链**~~ **已完成（2026-09-16）** | 跑得起（**最大**） | §4.1–4.4 + 按路径去重的真树 classpath + oshi 补丁件**替换** + `features` 门控 + auth 真值 | 1.21.1 实机进游戏（用户确认） |
| ~~**T6 `-p` 形态**~~ **已完成（2026-09-16）** | 覆盖 1.20.2–1.21.x | module path 与 `-cp` 共存、ART/jarsplitter/binarypatcher 产物链、`mergeModules` 按名补齐 | 1.20.2 实机进游戏（用户确认） |
| **T7 UI 与隔离** | 体验闭环 | loader 下拉（原版/Fabric/NeoForge）+ 版本过滤（1.20.2+）+ 进度 | UI 可用 |
| **T8 兼容验收 + 收尾** | 双向 + 留档 | V1/V2 双跑 + notes 回写 + 新增第三方件入 SBOM/许可 | 三道文档检查全绿 |

**顺序理由**：T0 是唯一能推翻架构的未知（无窗口 JVM + 工具在沙箱内可跑）；T3 先 26.x（1 个 processor）后 1.21.x（6 个）；T5/T6 是工作量与风险集中处。

---

## 6. 风险与未知点

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| ~~R1~~ | ~~无 surface 进程生存期~~ | — | **已消除**：无窗 UIAbility 实测可用（2026-09-15，调研 §8.3） |
| R2 | 工具在沙箱内的可运行性（读写路径、jopt 解析、`System.exit` 错误分支） | 阻塞 T0/T3 | 最简 task 先跑通；独立进程隔离退出码 |
| R3 | 工具 fail-open（错参数退 0 不产文件） | 静默失败 | **产物断言**（存在性/sha1），不信退出码 |
| R4 | 现代 profile 无 `outputs` ⇒ 幂等无元数据 | 重入体验 | 自建门控（已知产物的存在性/尺寸）；必要时复用工具内建跳过（BUNDLER_EXTRACT 的 sha256、jarsplitter 的 `.cache`） |
| R5 | `-Djava.system.class.loader` 与 NeoForge 类加载冲突 | 阻塞 T5 | §4.4 绕过（直接以 NeoForge mainClass 为主类）；保留回退 |
| R6 | 平铺 classpath 与 `-p`/ignoreList 冲突、库双份 | 启动失败 | §4.3 真 maven 树 + 按序显式 classpath |
| R7 | 1.21.x 六个 processor 的耗时/内存（N 次 JVM） | 体验 | 按阶段 T6 单独攻；必要时评估「单 JVM 多 ClassLoader」加速模式（需自编驱动） |
| R8 | 产物 sha1 因 zlib 差异不符 | 安装判定失败 | 我方校验降级为「存在性 + 尺寸 + ZIP 结构」（HMCL Forge 路径同款思路） |
| R9 | `MiNECRAFT_JAR` 被工具就地改写 | 污染共享缓存 | 独立 temp 副本（HMCL 同款硬约束） |
| R10 | 1.20.2+ 在 JDK26 下可跑性 | 该段不可玩 | 实机验证；必要时评估 |

**待验证清单（2026-09-16 更新）**：~~`:installer` 无窗口进程生存期~~ ✅ 已实测（无窗、进程隔离）；~~工具在沙箱内跑通~~ ✅；~~ArkTS game 参数分支~~ ✅；~~1.20.2+ 在 JDK26 下可跑性~~ ✅（三形态实机）。**仍未做**：与 HMCL 的双向兼容验收（V1/V2，用户 2026-09-16 决定**先搁置**）。

### 6.1 installer jar 的获取与复用自愈（2026-09-30；与 Forge 同款）

`installer.jar` 经**下载原语 `downloadFile`**（直传 `neoforgeInstallerCandidates` = 镜像优先 + 官方兜底）落到 `neo-installer/**`，安装编排按 `exists` 复用缓存、且 installer 无 sha1 ⇒ 复用到的坏文件（半截 / 上次中断）会被**永久复用**。**为何不用 `runDownloads`**（2026-09-30 登记，即 §E finding (a)）：`runDownloads` 只对 `urls[0]` 再做一次前缀展开 ⇒ `urls[0]` 已是镜像地址时展不出官方兜底（镜像取不到 installer 即无官方回退）；且它对「目标已存在」跳过下载 ⇒ 自愈删坏文件后若删除失败，日志会打 `re-downloading` 却没真重下、坏缓存退化为「每次解包都失败」。改直连 `downloadFile`（落盘前先删目标再 rename，与 Forge 链同款）两者兼治。处置 = **复用前先解一次**：`installNeoForgeVersion`（**主仓** `entry/src/main/ets/common/data/VersionInstaller.ets`）的 `extractArchive()` 要求**同时**解出 `install_profile.json` **与**内嵌启动清单（缺任一即判坏）⇒ 打稳定英文告警（`cached neoforge installer unusable, re-downloading: …`）→ 删文件 → 重下（**当次安装内自愈**）。同类：`NeoForgeInstaller.readToolMainClassAsync` 解工具 jar 主类前**先清输出目录**（上次中断留下的半截 `mainclass/<jar>/`）。**所照 HMCL 形态**（临时文件 + ZIP 结构校验 + 用完即删，坏文件从不进持久位置）见 [`Forge支持-改动方案.md`](Forge支持-改动方案.md) §13.2。

---

## 7. 兼容性验收（双向）

- **V1（我方 → HMCL）**：`root:true` + 自洽 `patches[game, neoforge]`（`game` 带 `complianceLevel`/`compatibilityRules`/`logging`）+ 标准 `libraries/` + `<id>.jar` ⇒ HMCL 应能识别并启动。
- **V2（HMCL → 我方）**：HMCL 自装（扁平 + `patches[]`）我方已支持合并；官方安装器形态①（薄 `inheritsFrom`）属独立课题（2026-09-15 前未实机验证）。
- **V3**：`-p` 形态与 26.x 形态各实机跑通。
- **V4**：中断后重跑成功。

---

## 8. 参考

- 调研与证据：[`NeoForge支持-调研.md`](../20-design/launch/NeoForge支持-调研.md)（含 §8：`LegacyInstaller`/`InstallerTools`/真 jar 取证——**证据仍有效，但按修订 3 仅作参考实现，不进运行时**）
- 同域既有实现（**本次直接复用**）：[`Fabric安装-方案.md`](Fabric安装-方案.md)（补丁式写盘 + 顶层扁平）、[`Fabric支持-改动方案.md`](Fabric支持-改动方案.md)（形态判定与分层改动面）、[`原版安装-方案.md`](原版安装-方案.md)（vanilla 下载 → game patch 底座）
- 参照实现：`ref/HMCL/`（编排语义的对照物）、`ref/InstallerTools/`（工具契约）、`ref/LegacyInstaller/`（仅作语义参考）
- 实物取证：**工作区根** `stuffs/research/neoforge/`
- 相关记忆：`hmcl_neoforge_three_chains`、`hmcl_fabric_install_mechanism`
