# Fabric（mod loader）支持调研 —— HMCL 机制 + 我们的改动面

> 日期：2026-09-13 ｜ **状态：机制调研（已完成）**；实现见 [`Fabric安装-方案.md`](../../90-archive/Fabric安装-方案.md) / [`Fabric支持-改动方案.md`](../../90-archive/Fabric支持-改动方案.md)（本文是机制依据，非现状；命名/状态以 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) 为准）
> 调研对象：`ref/HMCL` @ `0e3455434`（`v3.17.0.355-7-g0e3455434`，2026-09-06）。
> 范围：**只讲"启动"**（安装另议）；当前只关心 **Fabric**。
> 方法：`ref/HMCL` 源码逐文件抽读（`HMCLCore` 的 `launch/`+`game/`+`download/fabric/`、`HMCL` 编排层）＋ Fabric 官方 meta 实测对照。
> 相关：[`../../10-research/hmcl-存储模型.md`](../../10-research/hmcl-存储模型.md)（HMCL 总览 + 持久化模型）、[`../../10-research/启动器目录模型与版本隔离.md`](../../10-research/启动器目录模型与版本隔离.md)（实例模型/隔离）。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 17 条](../../00-current/现状基线.md)。

---

## 0. 结论速览

1. Fabric 的**启动** = 在 vanilla 启动之上：**mainClass 换成 `KnotClient` + classpath 追加 loader 一族库（fabric-loader / intermediary / ASM×5 / sponge-mixin 等）**；**其余（vanilla jar、vanilla 库、assets、natives、账户/窗口参数）与 vanilla 完全共用**。
2. 真正的复杂度全在**数据层**：必须先**解析 `inheritsFrom` 继承链**（官方安装器形态）或 **`patches[]` 按 priority 合并**（HMCL 自装形态），把 vanilla 基座展开后，才得到"等价 vanilla + Fabric 覆盖层"的启动清单。
3. Fabric **不声明 `javaVersion`**，Java 约束继承 vanilla；**不加任何 Fabric 专属 JVM 参数/系统属性**（`-DFabricMcEmu` 只存在于官方 profile，HMCL 自装不写）。
4. HMCL 的 loader 专属修复**只针对 Forge/NeoForge/OptiFine/LiteLoader（及 LegacyFabric 的 ASM 去重）**；**普通 Fabric/Quilt 走通用路径，无特判**。
5. 对我们：**必须新增 `inheritsFrom` 解析**；且**实例的"MC 版本"要解析到 vanilla 基座**（`fabric-loader-…` 既是目录名也是 json id，不是 MC 版本）—— 否则渲染后端/profile 会判错。

---

## 1. Fabric 实例在磁盘上有"两种形态"

HMCL 的数据模型**同时支持两种**，这是理解全部差异的前提。

| 形态 | 谁产出 | 关键字段 |
|---|---|---|
| **① 继承式（`inheritsFrom`）** | Fabric **官方安装器 / 官方 profile json**；外部导入实例 | `"inheritsFrom": "1.20.1"`，json 只列 Fabric 的 `mainClass` + `libraries`（+ 可选 `arguments.jvm`）；vanilla 的库/参数去父实例取 |
| **② 补丁式（`patches[]`，HMCL 自研模型）** | HMCL 自己安装 | 同一 `<dir>.json` **无 `inheritsFrom`**，而是 `"patches": [ {id:"game",priority:0}, {id:"fabric",priority:30000} ]`；顶层另有已展开的扁平字段 |

**Fabric 官方 profile（实测 `meta.fabricmc.net/v2/versions/loader/1.20.1/0.15.11/profile/json`）是形态①：**

```json
{
  "id": "fabric-loader-0.15.11-1.20.1",
  "inheritsFrom": "1.20.1",
  "mainClass": "net.fabricmc.loader.impl.launch.knot.KnotClient",
  "arguments": { "game": [], "jvm": [ "-DFabricMcEmu= net.minecraft.client.main.Main " ] },
  "libraries": [
    {"name":"org.ow2.asm:asm:9.6","url":"https://maven.fabricmc.net/"},
    {"name":"org.ow2.asm:asm-analysis:9.6","url":"https://maven.fabricmc.net/"},
    {"name":"org.ow2.asm:asm-commons:9.6","url":"https://maven.fabricmc.net/"},
    {"name":"org.ow2.asm:asm-tree:9.6","url":"https://maven.fabricmc.net/"},
    {"name":"org.ow2.asm:asm-util:9.6","url":"https://maven.fabricmc.net/"},
    {"name":"net.fabricmc:sponge-mixin:0.13.3+mixin.0.8.5","url":"https://maven.fabricmc.net/"},
    {"name":"net.fabricmc:intermediary:1.20.1","url":"https://maven.fabricmc.net/"},
    {"name":"net.fabricmc:fabric-loader:0.15.11","url":"https://maven.fabricmc.net/"}
  ]
}
```

同一 (game,loader) 的 **meta** 端点（`…/v2/versions/loader/1.20.1/0.15.11`）把库分组为：
`libraries.client=[]`、`common=[上面 6 个库]`、`server=[]`、`development=[mixinextras-fabric]`；
`mainClass={client:KnotClient, server:KnotServer}`。
→ 由此看：**生产 profile 的库实际全在 `common`**；`client`/`server` 为空。

**HMCL 自装（形态②）** 的 patch 构造见 [`FabricInstallTask.java`](#8-证据索引) `:99-130`：取 `launcherMeta.mainClass.client` + `libraries.common` + `libraries.server`，再追加 `net.fabricmc:intermediary`、`net.fabricmc:fabric-loader`，包成 `id="fabric"`、`priority=30000` 的补丁。

> ⚠️ **HMCL 自装会丢掉 `-DFabricMcEmu= net.minecraft.client.main.Main`**：该参数只在官方 `/profile/json` 里，而 HMCL 只读 `launcherMeta`（无此字段，构造 patch 时也不复制其 arguments）。但**形态①**的实例会把它作为子 `arguments.jvm` 合并进命令行。
> ⚠️ HMCL 源码自注："`common, server` is hard coded in fabric installer. Don't know the purpose of ignoring client libraries."（`:118-119`）——本例 `client=[]` 故无影响。

---

## 2. 启动解析管线（继承/补丁 → 合并 → 修复 → 拼参）

```
磁盘加载（逐个 json，不合并）
  → getResolvedManifest()                        // 惰性解析
     → DefaultGameRepositorySnapshot.resolve()   // 继承链 + patches
  → LaunchManifestNormalizer.repairForLaunch()   // 库去重 + loader 修复
  → DefaultLauncher.generateCommandLine()        // 拼 argv
```

### 2.1 `resolve()`（`DefaultGameRepositorySnapshot.java:186-237`）

- `inheritsFrom == null` 且是 root 清单 → **只保留 `patches`**，顶层扁平字段被忽略（`:191-195`）。
- `inheritsFrom != null` → 递归解析父实例（父缺失抛 `NoSuchGameInstanceException`）→ `child.merge(parentResolved)`（`:217-218`）。
- 之后按 `priority` **升序**合并自身 patches（`:224-232`）；解析完清空 `inheritsFrom`/`patches`。
- 注：解析阶段明确 **"without launch-library deduplication"**（`:180`）。

### 2.2 逐字段合并规则（`GameInstanceManifest.java:66-91`，已抽读核验）

`this=子`，参数=`父`：

| 字段 | 规则 |
|---|---|
| `mainClass` | 子非空**覆盖**父 → **Fabric 的 `KnotClient` 在此生效** |
| `minecraftArguments` / `jar` / `assetIndex` / `assets` / `javaVersion` / `type` / `time` / `releaseTime` | 子非空覆盖，否则父 |
| `arguments.game` / `arguments.jvm` | `Arguments.merge(parent, child)` → **父在前、子追加在后** |
| `libraries` | `Lang.merge(this.libraries, parent.libraries)` → **子在前、父在后**（与 arguments 相反） |
| `compatibilityRules` | 父在前、子在后 |
| `downloads` / `logging` | **整对象择一，不做深合并**（库内嵌 `downloads` 亦然） |
| `minimumLauncherVersion` | 取 max |
| `inheritsFrom` | 置 `null`（解析后清链）；`root` 置 `true` |

补丁层合并（`GameInstanceManifest.Builder.merge`，`:904-931`）：非空标量**补丁覆盖**；`arguments`/`libraries` 追加；按 priority 升序 → **基座(MC=0) 在前、loader(30000) 追加在后**。

### 2.3 库去重（`LaunchManifestNormalizer.uniqueLibraries`，`:277-330`）

- key = **`groupId:artifactId`（不含 version）**；
- `rules` 不同 → 都保留（平台变体）；rules 相同 → **高版本赢**，且**位置保持首次出现处**；同版本且对象相等 → 保留 JSON 更长者；同 id/version 但不等（如 jar vs natives）→ 都保留。

### 2.4 loader 修复（`LaunchManifestNormalizer.repairForLaunch`，`:48-82`）

- 只处理 Forge/NeoForge/OptiFine/LiteLoader（LaunchWrapper / ModLauncher / BootstrapLauncher）与 **LegacyFabric 的 ASM 去重**（`:74-78`）；
- **明确注释：`Vanilla and Fabric/Quilt need no loader-specific argument repair here`**（`:80`）；
- 输入必须是**已解析**清单（`:48-51`）。

---

## 3. 命令行如何拼（`DefaultLauncher.generateCommandLine`，`:277-367`）

### 3.1 add 顺序（关键段）

```
<java> [-Xmx/-Xms/...] [-D... 编码/log4j/GC/macOS/代理/渲染器 ...] [用户 jvm args]
  → manifest.arguments.jvm（无则 DEFAULT_JVM_ARGUMENTS，含 -Djava.library.path=${natives_directory} 与 -cp ${classpath}）
  → authInfo 的 jvm args → -javaagent:...
  → mainClass                                   // Fabric → KnotClient
  → minecraftArguments（legacy）/ arguments.game（modern）
  → auth game args → quickPlay/--server → --fullscreen → --graphicsBackend → 用户 game args
```

### 3.2 classpath（`:277-289`、`:819-858`）

- 取"已解析 manifest 中所有 **非 native** 且 os 规则通过的库 jar"（绝对路径，`LinkedHashSet` 去重）；
- **再追加实例自身 jar**（`instance.getInstanceJarFile()`，缺失直接抛 `IOException`）；Fabric **不替换**这个主 jar，仍是 vanilla jar；
- natives 的 jar 不进 cp（`isNative()` 过滤）；
- `${classpath}` 宏 = 上述串（`:294`）。

### 3.3 占位符 / 规则 / natives

- **占位符**（`getConfigurations()`，`:622-652`）：`${auth_player_name} ${auth_session} ${auth_access_token} ${auth_uuid} ${version_name} ${version_type} ${game_directory} ${assets_index_name} ${natives_directory} ${classpath} ${game_assets} ${assets_root} …`。**Fabric 与 vanilla 用的完全相同**；未知占位符原样保留。
- **规则求值**：`CompatibilityRule` 默认 DISALLOW，命中 ALLOW 才生效；OS 判 `name/arch/version`。HMCL 实际只提供 feature `has_custom_resolution`（`getFeatures()`，`:425-430`），`is_demo_user`/quickPlay 等规则一律不生效（quickPlay 改手工加参）。
- **natives**：按库的 classifier（OS/arch）选 → 解压到 `<instanceRoot>/natives-<platform>` → 靠 `-Djava.library.path` 生效。**Fabric 不改变此逻辑**。HMCL 不用 `-Dorg.lwjgl.librarypath`。

### 3.4 进程 / 环境（`:663-817`）

- cwd = `instance.getRunDirectory()`；环境变量：`INST_*` + 渲染器变量 + **每个 `ModLoaderType` 一个标记**：
  `env.put(modLoader.getEnvVarName(), "1")` → **Fabric ⇒ `INST_FABRIC=1`**（`:804-808`；`ModLoaderType.FABRIC("INST_FABRIC")`）。
- **Fabric 无专属 `-D` 系统属性**（对比：FML 有 `-Dfml.ignoreInvalidMinecraftCertificates` 等）。

---

## 4. Fabric vs vanilla：差异清单 + argv 模板

### 4.1 差异清单

| 项 | vanilla | Fabric |
|---|---|---|
| **mainClass** | `net.minecraft.client.main.Main` | **`net.fabricmc.loader.impl.launch.knot.KnotClient`**（来自 json/patch；HMCL 不硬编码） |
| **classpath** | vanilla 库 + 主 jar | vanilla 库 + 主 jar **+ fabric-loader + intermediary + ASM×5 + sponge-mixin（旧 loader 还可能有 tiny-remapper / access-widener / tiny-mappings-parser）** |
| **jvm 参数** | — | HMCL 自装**不加**；官方 profile 带 `-DFabricMcEmu= net.minecraft.client.main.Main` |
| **game 参数** | — | 现代 Fabric **不加**；仅老 loader（`launchwrapper` 元数据）加 `--tweakClass <clientTweaker>` |
| **env** | — | `INST_FABRIC=1`（HMCL 标记，**非 Fabric 要求**） |
| **javaVersion** | 自己声明 | **继承 vanilla**（`FabricInstallTask` 不写）→ Java 约束等价原版 |
| **assets / natives / logging / cwd / 账户参数** | — | **完全一致** |
| **mods/** | — | 启动器**不传参**；Fabric Knot 运行时自读游戏目录 `mods/`；Fabric API 只是 `mods/` 里一个 jar（`FabricAPIInstallTask` 不产出 patch） |
| **数据层** | 单层自洽清单 | 需**先解析**（`inheritsFrom` 链 / `patches` 按 priority）才等价 vanilla+Fabric |

### 4.2 argv 模板（modern，1.20.1 例）

```
# vanilla
<java> ... -Djava.library.path=<...>/natives-<p> -cp <vanilla libs>:<...>/1.20.1.jar \
  net.minecraft.client.main.Main --username .. --version 1.20.1 --gameDir .. --assetsDir .. \
  --assetIndex .. --uuid .. --accessToken .. --userType .. --versionType HMCL

# Fabric（HMCL 自装）
<java> ... 同上 -Djava.library.path/-cp ... 但 cp 追加 loader 一族、mainClass 换掉：
  -cp <vanilla libs>:<fabric-loader>:<intermediary>:<asm×5 + sponge-mixin>:<...>/1.20.1.jar \
  net.fabricmc.loader.impl.launch.knot.KnotClient --username .. (其后游戏参数与 vanilla 相同)
# 环境：INST_FABRIC=1
```

**与 vanilla 的 argv 差异 = mainClass 换了 + cp 多了那几个库（+ 可能的 `-DFabricMcEmu` / `--tweakClass`）。其余一模一样。**

---

## 5. Fabric 各要素来历

| 要素 | 来源 | 备注 |
|---|---|---|
| `mainClass` | Fabric meta `launcherMeta.mainClass.client` | 生产 = `KnotClient`；老版本 launchwrapper 路径为 `net.minecraft.launchwrapper.Launch` |
| 启动库 | meta `libraries.common`(+`server`) + 追加 `intermediary`/`fabric-loader` | 全来自 `https://maven.fabricmc.net/`；`development` 丢弃 |
| `-DFabricMcEmu` | 官方 `/profile/json` 的 `arguments.jvm` | 带多余空格（上游怪癖）；HMCL 自装不写 |
| `--tweakClass` | 老 loader 的 `launcherMeta.launchwrapper.tweakers.client` | 现代 Fabric 无 |
| `INST_FABRIC=1` | HMCL `ModLoaderType` | 仅标记，非 Fabric 必需 |
| 识别 Fabric | `GameComponentType`：补丁 id `"fabric"`（clear）或库 `net.fabricmc:fabric-loader`（猜测）；有 `net.legacyfabric` 组则判 `LEGACY_FABRIC` | `GameComponentAnalyzer.java:34-77` |
| Java 版本 | 不声明 → 继承 vanilla game 清单 | 约束等价 `GAME_JSON`（`JavaVersionConstraint.java:47`） |

**官方 Fabric meta 端点**（供后续安装用，本文不展开）：
`https://meta.fabricmc.net/v2/versions/loader`、`/v2/versions/game`、`/v2/versions/loader/<game>/<loader>`（launcherMeta）、`…/profile/json`（可直接用的版本清单）。

---

## 6. 对本项目的改动面与风险

1. **新增 `inheritsFrom` 解析**（核心工作）：官方 Fabric 安装器产出的实例是继承式；我们的 `VersionScanner`/`MinecraftLauncher` 目前**不解析继承链**。需要"加载父实例 → 逐字段合并（按 §2.2 规则）→ 得到等价 vanilla+Fabric 的启动清单"。
2. **★ MC 版本判定要解析到 vanilla 基座**：Fabric 实例的目录名**和** json `id` 都是 `fabric-loader-<loader>-<game>`，**不是 MC 版本**。`RendererPolicy` 现在读 json 内部 `id` 决定 GL profile / 渲染后端 → 对 Fabric 实例会**判错**。必须解析 `inheritsFrom`（或补丁式里 `game` 层的 `version`）拿到真实 MC 版本（如 `1.20.1`）。**这是既有坑 `meowcraft_instance_name_is_not_mc_version` 的延伸，对 Fabric 还要再往前解析一层**。
3. **classpath 追加**：把解析后多出的 loader 一族库纳入 staging/`-cp`；**去重 key 用 `groupId:artifactId`**（不能按文件名字符串）。
4. **主 jar 仍是 vanilla jar**（Fabric 不替换它）；我们现有的 `-cp`+主 jar 逻辑可复用，只是多了若干库 + mainClass 改变。
5. **现代 Fabric 无额外 JVM 参数**；natives/assets/账户参数**全部复用现有逻辑**。`-DFabricMcEmu` 可后置。
6. **识别/隔离**：可参照 HMCL 以 `net.fabricmc:fabric-loader` 判 Fabric；版本隔离仍只切运行目录，与 modloader 无关（mods 本就在运行目录下）。
7. **平台坑（手机用户存储拒 chmod，2026-09-27 定案）**：Fabric 首次 remap 经 `jdk.zipfs` 往 `<gameDir>/.fabric/remappedJars/` 写盘，而手机用户存储（FUSE/hmdfs）**拒绝 chmod** ⇒ `ZipFileSystem.sync()` 的 `setPosixFilePermissions` 抛 `EPERM` ⇒ 崩；修法（`jdk.zipfs` best-effort chmod 类补丁 + `--patch-module`）见 [`Fabric安装-方案.md`](../../90-archive/Fabric安装-方案.md) §6.2 与 [`现状基线.md`](../../00-current/现状基线.md) §5 第 27 条。

---

## 7. 未决问题 / 待验

- **形态选择**：我们只吃**官方安装器的 `inheritsFrom` 形态**，还是也要产出/兼容 HMCL 的 **`patches[]` 形态**？（用户机器上两种都可能存在。）
- **`-DFabricMcEmu` 是否必需**：HMCL 自装不写且可玩。**已实机验证（形态②，2026-09-13/2026-09-15）**：我们启动端也不设该旗标（全库零命中），Fabric 实例正常进游戏 ⇒ **非必需**。
- **`client` 库忽略是否安全**：本例 `client=[]`；需对旧 loader/旧 MC 复核（若官方 `/profile/json` 的 libraries 与 launcherMeta 分组不一致，应以哪个为准？）。
- **旧 loader 的 `--tweakClass` / launchwrapper 路径**是否需要支持（取决于我们要覆盖的 MC 版本段）。
- 其它 loader（Forge/NeoForge/Quilt/OptiFine）是否复用同一套解析，留待后续。

---

## 8. 证据索引（`ref/HMCL/…`，均为抽读核验）

| 结论 | 位置 |
|---|---|
| 磁盘加载 / 目录名=id | `HMCLCore/.../game/DefaultGameRepository.java:267-360`；`DefaultGameRepositoryLayout.java:52-71` |
| 继承+补丁解析 | `HMCLCore/.../game/DefaultGameRepositorySnapshot.java:186-237` |
| 逐字段合并 | `HMCLCore/.../game/GameInstanceManifest.java:66-91`（补丁合并 `:904-931`） |
| 补丁优先级 | `HMCLCore/.../game/GameInstancePatch.java:63-67`（MC=0 / LOADER=30000） |
| 库去重 | `HMCLCore/.../game/LaunchManifestNormalizer.java:277-330` |
| loader 修复 | `HMCLCore/.../game/LaunchManifestNormalizer.java:48-82` |
| Fabric patch 构造 | `HMCLCore/.../download/fabric/FabricInstallTask.java:99-130` |
| Fabric 识别 | `HMCLCore/.../game/GameComponentType.java:62-83`；`GameComponentAnalyzer.java:34-77` |
| argv / classpath / mainClass | `HMCLCore/.../launch/DefaultLauncher.java:277-367`、`:819-858`、`:804-808` |
| 编排链 / Java 选择 | `HMCL/.../game/LauncherHelper.java:160,244,429-729`；`HMCL/.../setting/GameSettings.java:877-993` |
| 官方 Fabric profile（实测） | `https://meta.fabricmc.net/v2/versions/loader/1.20.1/0.15.11/profile/json`（形态①） |

---

> **落地**：双形态（`inheritsFrom` + `patches`）支持的改动方案见 [`Fabric支持-改动方案.md`](../../90-archive/Fabric支持-改动方案.md)。
