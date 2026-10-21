# NeoForge「不跑 JVM」安装的可行性与取证（B 线）

> 日期：2026-09-28 ｜ 性质：**证据存档 / 决策记录**，**不复述现状**（能力现状见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 22 条；phone 端登记见 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §E）。
> 问题：对我们这种 **ArkTS 启动器 + 随包 JRE**、且**安装期不能起 Java 进程**的场景（`bin/java` 落 el2 禁执行；**phone** 无独立进程宿主，见 [`安装期JVM载体-调研.md`](../../90-archive/安装期JVM载体-调研.md) §10），**有没有一条不跑 JVM 也能装成 NeoForge 的路**？
> 证据：真 installer 三件（**工作区根** `stuffs/research/neoforge/extracted/`）、生成器（`ref/NeoForge/buildSrc/src/main/java/net/neoforged/neodev/installer/`）、官方 installer（`ref/LegacyInstaller`）、工具契约（`ref/InstallerTools`）。
> **NeoForge maven 目录树为 2026-09-28 会话内实时联网抓取**（未留快照 ⇒ 目录内容可能随时间变化）。
> 原始报告：**工作区根** `stuffs/research/hmcl-neoforge/B-jvm-free.md`（本文件为其入库版，正文照搬、仅改抬头与路径口径）。
> 分档：**① 可纯 ArkTS/native 重实现 ｜ ② 可用「下载」替代 ｜ ③ 现阶段必须 JVM**。
> 姊妹篇：[`NeoForge安装链-逐行取证.md`](NeoForge安装链-逐行取证.md)（同轮 A 线：HMCL 怎么装、JVM 落在哪一步）。

## 1. 一句话结论

- **26.x（26.1.2.109）：可以不跑 JVM 装成。** client 侧只有 **1** 个 processor，且它**不做任何字节码重命名/映射**（profile 未传 `--input-mappings` / `--neoform-data`），只做「解 bundle + 施加 LZMA/GDIFF 补丁 + 写确定性 zip」。
- **1.20.2–1.21.x（21.1.250）：现阶段不能。** client 侧 **6** 个 processor 中 **ART 2.0.3（整 jar 字节码重映射）无 native 等价物** ⇒ 差 1 个「必须 JVM」。
- **1.20.1（forge 47.1.106）：现阶段不能。** 同构，卡在 **FART 0.1.22** ⇒ 差 1 个「必须 JVM」。
- **「下载代替构建」对三形态均不成立**（已联网核实）：processor 产物 `neoforge-*-client.jar` / `minecraft-client-patched` / `mappings-merged@txt` / `slim` / `extra` / `srg` **全部未在官方 maven 发布**，它们只是 `libraries/` 下的**本地输出路径**。

> ⚠️ **适用范围**：本判定只回答「**能不能不起 Java 进程**」。2in1 上我方现行「headless `:installer` 进程 + `JLI_Launch`」路线仍成立（可行性见 [`NeoForge支持-调研.md`](NeoForge支持-调研.md) §7；实机状态见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 22 条）⇒ **它绑到 phone 才有意义**（phone 拿不到独立进程宿主）。

## 2. processor 逐个表（仅 **client 侧**）

真 profile 里 `sides` 缺省 = client+server 都跑，故 `[server]` 者已剔除。**计数修正**：1.20.1 与 21.1 的 client 侧实测**均为 6**（[`NeoForge支持-调研.md`](NeoForge支持-调研.md) §5 表记 21.1 为 5，见 §5.1）。

| 形态 | processor | 作用 | 输入 → 输出 | 可否不跑 JVM | 证据（文件:行） |
|---|---|---|---|---|---|
| 1.20.1 | installertools 1.3.0 `MCP_DATA` | 从 mcp_config zip 按 `config.json` 的 `data.<key>` 路径抽一个文件 | `[de.oceanlabs.mcp:mcp_config:1.20.1-20230612.114412@zip]` → `{MAPPINGS}`（`mcp_config:...:mappings@txt`） | **①**（unzip+json+copy，极简） | profile:207-217；McpData.java:71-104,114-141；data:9-12 |
| 1.20.1 | 1.3.0 `DOWNLOAD_MOJMAPS` | GET launchermeta 清单 → version json → `downloads.client_mappings.url` → 下载 | 无线上入 → `{MOJMAPS}`（`net.minecraft:client:...:mappings@txt`） | **②**（纯 HTTP 下载；HMCL 即如此） | profile:239-249；DownloadMojmaps.java:39,66-82；data:13-16 |
| 1.20.1 | 1.3.0 `MERGE_MAPPING` | 载入两侧 TSRG，右侧 reverse 后 merge，写 TSRG2 | `{MAPPINGS}`+`{MOJMAPS}`（`--classes --reverse-right`）→ `{MERGED_MAPPINGS}` | **① 但中高工作量**（须复刻 srgutils 的 merge/reverse 语义） | profile:271-283；MergeMappings.java:34-37,68-80；data:17-20 |
| 1.20.1 | jarsplitter 1.1.4 | 按 srg 类白名单把 MC jar 拆 slim/extra（非 class 归 extra） | `{MINECRAFT_JAR}`+`{MERGED_MAPPINGS}` → `{MC_SLIM}`+`{MC_EXTRA}`（含 outputs sha1 幂等） | **①**（zip 复制 + 读 TSRG 类名，简单） | profile:288-307(303-306)；jarsplitter ConsoleTool.java:68-130；data:29-44 |
| 1.20.1 | **FART 0.1.22:all** | 用合并映射**重命名整个 jar**（含 ann/ids/src/record fix） | `{MC_SLIM}`+`{MERGED_MAPPINGS}` → `{MC_SRG}` | **③ 必须 JVM**（整 jar 字节码 remapper，需 ASM 等价物） | profile:333-353；data:45-48 |
| 1.20.1 | binarypatcher 1.1.1 | LZMA 解包 → `NFPATCHBUNDLE001` 逐条 CREATE/MODIFY/REMOVE，MODIFY = xdelta GDIFF（Adler32 校验） | `{MC_SRG}`+`{BINPATCH}`（`/data/client.lzma`）→ `{PATCHED}`（`net.neoforged:forge:1.20.1-47.1.106:client`） | **① 中等**（自定义容器+LZMA+GDIFF+Adler32；**无需 ASM**） | profile:356-378；PatchBundleReader.java:44-66,117-172；PatchBundleConstants.java:11-24；PatchBase.java:9-11；Patch.java:163,239-243；data:49-52 |
| 1.21.x | installertools 2.1.2 `MCP_DATA` | 同 1.20.1，源改为 neoform zip | `[net.neoforged:neoform:1.21.1-20240808.144430@zip]` → `{MAPPINGS}`（`neoform:...:mappings@txt`） | **①** | profile:207-217；McpData.java:71-141；data:13-16 |
| 1.21.x | 2.1.2 `DOWNLOAD_MOJMAPS` | 同 1.20.1 | → `{MOJMAPS}` | **②** | profile:241-250；data:17-20 |
| 1.21.x | 2.1.2 `MERGE_MAPPING` | 同上（多 `--fields --methods`） | → `{MERGED_MAPPINGS}`（`neoform:...:mappings-merged@txt`） | **① 但中高工作量** | profile:275-288；data:21-24 |
| 1.21.x | jarsplitter 2.1.2 | **同 1.20.1 算法**（但 profile 无 `outputs` 字段，改用内部 `.cache/.sha`） | `{MINECRAFT_JAR}`+`{MERGED_MAPPINGS}` → `{MC_SLIM}`+`{MC_EXTRA}` | **①** | profile:290-311；ConsoleTool.java:57-58,154-192；data:33-40 |
| 1.21.x | **ART 2.0.3:all** | 同 FART（整 jar 重命名） | `{MC_SLIM}`+`{MERGED_MAPPINGS}` → `{MC_SRG}` | **③ 必须 JVM** | profile:334-351；data:41-44 |
| 1.21.x | binarypatcher 2.1.2:fatjar | 同 1.20.1 思路（2.1.2 CLI 为旧式 `--clean/--apply`，与 HEAD 的 `--diff/--patch` **不兼容**） | `{MC_SRG}`+`{BINPATCH}` → `{PATCHED}`（`net.neoforged:neoforge:21.1.250:client`） | **① 中等** | profile:352-365；PatchBundleReader.java:44-66；data:45-48 |
| 26.x | **installertools 4.0.12:fatjar `PROCESS_MINECRAFT_JAR`** | ① 若输入是 vanilla **bundle** zip 则抽出主 jar 并把内嵌库写到 `libraries/`；② 施加 LZMA 补丁 bundle（同 NFPATCHBUNDLE/GDIFF/Adler32）；③ 写**确定性 zip**（固定时间戳）。`--no-mod-manifest` ⇒ 不写 `neoforge.mods.toml` | `{MINECRAFT_JAR}`+`{BINPATCH}`（`/data/client.lzma`）→ `{PATCHED}`（`net.neoforged:minecraft-client-patched:26.1.2.109`）+ `{ROOT}/libraries/` | **① 关键**：因 `--input-mappings` 缺省（**不做重命名**）、且 `data` 无 mappings（**不需要联网下 Mojang 映射**）⇒ 纯 native 可实现 | profile:66-84(73-82)；ProcessMinecraftJar.java:113-121,160,217-224,338-405,421-449,523-542；CreateInstallerProfile.java:112-114,129-142；data:12-24 |

> 工具/算法要点（源码已核）：`NFPATCHBUNDLE001` 签名 + `int entryCount` + 1 字节分发位域（CLIENT=1/SERVER=2/JOINED=4）；每条 = flags（类型 0x00/0x08/0x10）+ 路径（u16+ASCII）+ [base Adler32] + u32 长度 + data；MODIFY 的 data 为 xdelta（`GDiffPatcher`）。见 `PatchBundleReader.java:44-66,117-172`、`PatchBundleConstants.java:11-24`、`Patch.java:239-243`、`Patcher.java:220`。
> 官方执行方式（参考）：`PostProcessors` 用 `URLClassLoader` + `Class.forName` + `main.invoke`，**进程内反射**（`PostProcessors.java:237-267`），并做 outputs sha1 预检/校验（`:141-183,269-295`）—— 证明 processor 与我们是同构调用，但**仍要有 JVM 载体**。

## 3. 「下载代替构建」核查结果

结论：**不成立**。三形态的 processor **产物**都不是 maven 制品，而是 `libraries/` 下的落盘路径：

| 期望产物（坐标/路径） | maven 实况（2026-09-28 抓取） | 判定 |
|---|---|---|
| `net.neoforged:forge:1.20.1-47.1.106:client` | `.../net/neoforged/forge/1.20.1-47.1.106/` 仅有 changelog/installer/pom/sources/**universal**/userdev，**无 `-client.jar`** | ❌ 未发布 |
| `net.neoforged:neoforge:21.1.250:client` | `.../net/neoforged/neoforge/21.1.250/` 仅有 changelog/installer/moddev-config/module/pom/sources/universal/userdev，**无 `-client.jar`** | ❌ 未发布 |
| `net.neoforged:minecraft-client-patched:26.1.2.109` | `.../net/neoforged/` 目录**无 `minecraft-client-patched/`**；直取 `.../minecraft-client-patched-26.1.2.109.jar` = 404 | ❌ 未发布 |
| `net.minecraft:client:<v>:slim/extra/srg/unpacked`（1.20.1/1.21.x） | `.../net/minecraft/...` = 404（该命名空间不在 neoforged maven；是 **NeoForm 本地伪坐标**） | ❌ 非下载物 |
| `de.oceanlabs.mcp:mcp_config:1.20.1-...:mappings` / `:mappings-merged` | `.../de/oceanlabs/mcp/mcp_config/1.20.1-20230612.114412/` 仅 `.pom`/`.zip`，**无 classifier 文件** | ❌ 未发布 |
| `net.neoforged:neoform:1.21.1-20240808.144430:mappings` / `:mappings-merged` | `.../neoform/1.21.1-20240808.144430/` 仅 `.module`/`.pom`/`.zip` | ❌ 未发布 |
| 可下载的**输入**（对照） | `mcp_config-*.zip`、`neoform-*.zip`、`installertools`/`jarsplitter`/`ART`/`binarypatcher` 工具 jar、`neoforge-*-universal.jar`、Mojang `client.jar`/`client_mappings` | ✅ 有 |

**推断**（标注为**推断**）：坐标命名规则来自生成器 —— HEAD 版 `CreateInstallerProfile.java:112-115` 把 `PATCHED` 生成为 `net.neoforged:minecraft-client-patched:<neoforgeVersion>` / `:minecraft-server-patched:<...>`，只是**输出路径占位**；旧形态（1.20.1/1.21.x）的 `PATCHED = [net.neoforged:{forge,neoforge}:<ver>:client]` 亦为输出路径（这些 json 生成逻辑不在 HEAD，只有实测真 profile 为权威）。
**未联网核实**项：第三方镜像（如 BMCLAPI）是否二次分发"已安装产物" —— BMCLAPI 只镜像 maven 前缀，未逐一核实。

## 4. 三形态判定 + 最省事路径

| 形态 | 完全不跑 JVM 能装到什么程度 | 必须 JVM 的 processor 数 | 最省事路径 |
|---|---|---|---|
| **26.x** | **可以装成**：只需 native 重实现 1 个 processor 的 3 个原语（bundle 解包 / LZMA+NFPATCHBUNDLE+GDIFF+Adler32 / 确定性 zip）。无映射下载、无重命名 | **0** | **推荐**：native 重实现 `PROCESS_MINECRAFT_JAR`（等价功能）。工作量粗判 1–2 周；LZMA 可借 liblzma，GDIFF 为简单 VCDIFF 变体 |
| **1.20.2–1.21.x** | **装不成**（差 ART）：其余 5 个（MCP_DATA①/下行②/MERGE_MAPPING①/jarsplitter①/binarypatcher①）均可 native；仅 **ART 2.0.3** 无等价物（需 native 字节码 remapper，成本极高） | **1（ART）** | 维持既有「`:installer` 进程 + JVM」路线；或**离线预构建**（见下）；不建议写 native remapper |
| **1.20.1** | **装不成**（差 FART）：同上 5 个可 native，仅 **FART 0.1.22** 卡住 | **1（FART）** | 同 1.20.2–1.21.x |

「下载代替构建」不可行（§3）后，若坚持零 JVM 又要覆盖 1.20.1/1.21.x，唯一低成本出路 = **离线预构建**（**推断**，非官方制品）：在开发机跑一次官方安装，把 `PATCHED` 等产物按 maven 布局放进我们**自建**的分发位（需注意 NeoForge/LGPL 许可与体积），运行期照 `libraries/` 放文件即可，安装期仍零 JVM。缺点是**每新增一个目标版本都要预构建一次**，无法覆盖任意版本。

## 5. 未确认项

1. **计数修正**：既有 [`NeoForge支持-调研.md`](NeoForge支持-调研.md) §5 表记「1.20.2–1.21.x client 侧 5 个」，真 profile 实测为 **6**（MCP_DATA / DOWNLOAD_MOJMAPS / MERGE_MAPPING / jarsplitter / ART / binarypatcher）。本报告按实物 6 计。
2. **binarypatcher / jarsplitter / McpData / ExtractFiles / BundlerExtract 的 `①` 判定是"可重实现"的静态推断**，未做逐字节比对验证；尤其 **MERGE_MAPPING 的 srgutils merge/reverse 语义**需完全一致，风险最高（中高）。
3. **26.x `PROCESS_MINECRAFT_JAR` 输出 jar 的"命名语义"**（是否 srg/官方名）未查明；但"无重命名步骤"的判定依据是 `ProcessMinecraftJar.java:217-224`（`inputMappingsFile != null` 才 deobfuscate）。若 26.x 补丁内含重命名结果则结论更强。
4. **1.20.1/26.x 的 `PATCHED` 产物在 `version.json` 中未见引用**（grep `47.1.106`/`patched` 均只命中 id 与 game 参数）—— 它在启动期如何进入 classpath（FML 依 `-DlibraryDirectory` 自寻 vs 被拷成主 jar）未确认；不影响本报告（它必须存在，故不可省 patch 步骤）。
5. 与 [`NeoForge支持-调研.md`](NeoForge支持-调研.md) §7 的张力：该文判「headless `:installer` 进程 + `JLI_Launch`」**可行**（实机状态见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 22 条）。若成立，则"零 JVM"并非 2in1 的必需项；本报告的适用面是**拿不到独立进程宿主的 phone**。
6. **网络核实**为 2026-09-28 一次性抓取（未留快照）；maven 目录内容可能随时间变化。

## 相关

- 姊妹篇（同轮 A 线）：[`NeoForge安装链-逐行取证.md`](NeoForge安装链-逐行取证.md)
- 既有三链调研 + 我方 JVM 可行性论证：[`NeoForge支持-调研.md`](NeoForge支持-调研.md) §5/§7/§8
- 安装期 JVM 载体的候选与 phone 侧结论：[`安装期JVM载体-调研.md`](../../90-archive/安装期JVM载体-调研.md) §10
- 落地方案：[`NeoForge支持-改动方案.md`](../../90-archive/NeoForge支持-改动方案.md)
- 原始报告：**工作区根** `stuffs/research/hmcl-neoforge/B-jvm-free.md`
