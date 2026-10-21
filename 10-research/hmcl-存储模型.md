# HMCL 参考：总览 + 数据/配置持久化模型（源码级）

> 写于 2026-09-12。对象：`ref/HMCL`（现代版本，三模块 `HMCLCore` / `HMCL` / `HMCLBoot`，含新版 `GameInstance` 术语）。
> 定位：**HMCL 自己怎么把启动器数据落盘**（配置文件、已添加文件夹、账户、版本隔离、每版本启动参数、实例元数据、迁移）；
> 末节 §12 **HMCL 架构总览**（模块划分 / 平台抽象 / 参数生成 / 下载 / 账户 / 游戏模型 / UI）已并入本文（原独立档 `hmcl.md` 归档于 [`../90-archive/hmcl.md`](../90-archive/hmcl.md)）。
> 姊妹篇：[`启动器目录模型与版本隔离.md`](启动器目录模型与版本隔离.md)（`.minecraft` **目录契约** + 隔离三值策略 + 安装流程，本文不重复）。
> ⚠️ **许可与净室**：HMCL 为 **GPL-3.0**。本文仅作**概念/设计参考**；若要落地，须**净室实现**（独立设计，勿照搬代码结构、命名与表达）——与本项目去 Pojav/LGPL 血统的做法一致。
> 证据均给 `文件:行`；行号以当前 `ref/HMCL` 为准。

---

## 0. 结论先行（TL;DR）

1. **一个存储域 = 一个带 `$schema` 的 JSON 文件**。schema 是**手写 JSON Schema 文档**（`docs/schemas/<id>/<version>.json`），Java 侧只存 `CURRENT_SCHEMA` 常量并运行时校验。
2. **两个根**：`HMCL_LOCAL_HOME`（workspace 局部，默认 `<cwd>/.hmcl`）与 `HMCL_USER_HOME`（用户全局，Linux `~/.local/share/hmcl`）；同名域各存一份，运行时合并（local 优先）。
3. 设置类用 **JavaFX Property + `@SerializedName`** 声明，反射序列化；**只写"脏"字段**（默认值不落盘）、**保留未知键与 `$schema`**（前向兼容）。
4. **已添加文件夹**独立文件；**选中项**在主设置里。
5. **账户=公开元数据 + 私密凭据两个文件**；凭据用 `ProtectedPayload` 信封（默认 ChaCha20-Poly1305 + **硬编码密钥**，属"混淆"非真安全）。
6. **版本隔离没有布尔字段**：= 每实例设置里 `overrideProperties` 是否含 `"runningDirectory"` + 该值；全局默认是预设的 `defaultIsolationType`（`ALWAYS|MODDED|NEVER`），**只在新建/安装时**物化。
7. **每版本参数=全局预设 + 每实例覆盖**两层，物理分文件；覆盖靠**显式白名单** `overrideProperties`（不是"键是否存在"）。
8. 写入：临时文件 + move（`saveSafely`）；高频走单后台线程 `FileSaver`（200ms 防抖）；敏感数据同步写。**先写私密、后写元数据**。
9. 迁移：旧文件字段改名 + **确定性 UUID** + `MigrationReceipt`（SHA-256）防重放；schema 主版本不兼容则**只读、绝不覆盖**。

---

## 1. 双根目录与文件全景

### 1.1 两个根

- `HMCL_LOCAL_HOME`：默认 `<当前工作目录>/.hmcl`；可用 `-Dhmcl.dir` 或 `HMCL_LOCAL_HOME` 覆盖（`HMCL/Metadata.java:88-91`）。
- `HMCL_USER_HOME`：Linux 为 `$XDG_DATA_HOME/hmcl` 或 `~/.local/share/hmcl`；其他平台为系统 working dir（`HMCL/Metadata.java:71-86`）。

### 1.2 文件清单（`HMCL/setting/SettingsManager.java:73-243`）

| 作用域 | 路径 | 内容 |
|---|---|---|
| local | `<LOCAL>/config/launcher-settings.json` | 主启动器设置 |
| local | `<LOCAL>/config/game-directories.json` | 已添加游戏文件夹 |
| local | `<LOCAL>/config/game-settings.json` | 游戏设置**预设** |
| local | `<LOCAL>/config/accounts.json` | 账户**元数据** |
| local | `<LOCAL>/private/account-private-data.json` | 账户**私密数据** |
| local | `<LOCAL>/config/authlib-injector-servers.json` | 外置登录服务列表 |
| local | `<LOCAL>/state/launcher-state.json` | 窗口位置、提示状态等 |
| user | `<USER>/config/user-settings.json` | 用户级设置 |
| user | `<USER>/config/user-game-directories.json` | 共享文件夹 |
| user | `<USER>/config/user-accounts.json` | 共享账户元数据 |
| user | `<USER>/private/user-account-private-data.json` | 共享账户私密数据 |
| user | `<USER>/state/user-state.json` | 用户级状态 |

- 格式：Gson pretty-print JSON（`HMCL/setting/LauncherSettings.java:101-111`）。
- 每个文件顶层带 `$schema` 键（`JsonSchema.PROPERTY_SCHEMA = "$schema"`，`HMCL/util/io/JsonSchema.java:62`）。
- 实例内另有：`versions/<id>/.hmcl/config/instance-game-settings.json`（见 §6）、`versions/<id>/.hmcl/state/*`。

---

## 2. schema 机制（手写 + 运行时校验）

- schema 文档手写，放 `ref/HMCL/docs/schemas/<id>/<version>.json`（例：`launcher-settings/1.0.0.json`、`game-directories/1.0.0.json`、`game-settings/…`、`accounts/1.0.0.json`、`instance-game-settings/1.0.0.json`）。
- URL 形如 `https://schemas.glavo.site/hmcl/<id>/<version>`（`JsonSchema.java:65`）；Java 侧只存 `CURRENT_SCHEMA` 常量（`LauncherSettings.java:65`、`GameDirectories.java:45`）。
- 运行时用 `JsonSchema.check` 做兼容性比对（`JsonSchema.java:128-169`，状态枚举 `:315-323`）：
  - id 不符 / 主版本不支持 / 非法 / 缺失 → **不可读**：加载默认对象且 `savable=false`；
  - minor 更新 → 只读但保留原 schema（`READ_ONLY_PRESERVE_SCHEMA`）；
  - 仅 patch 不同 → 可读写，**保留原 `$schema` 字符串与未知字段**。

---

## 3. 设置声明与写入机制

### 3.1 声明方式（无注解处理器 / 无代码生成）

- `ObservableSetting`：用 `ClassValue` 缓存每个类的 `非 transient/静态` 字段，按类型包装成 `PropertyField` / `CollectionField` / `MapField`（`HMCL/setting/ObservableSetting.java:64-201`）。
- 字段名用 `@SerializedName`（支持 `alternate` 旧名，`:155-162`）；`@JsonSerializable` 只是 SOURCE 级提醒注解（`JsonSerializable.java:22-31`）。
- 自定义序列化器：`Path`、`UUID`、`Paint`、JavaFX property、`PortablePath`、`TypedID`、`LocalizedText`、`JsonSchema`（`LauncherSettings.java:101-111`）。

### 3.2 读写行为

- **只写脏字段**：`ObservableField` 按 `DirtyTracker` 序列化，未被改过的字段不落盘 → 磁盘文件稀疏、默认值不落盘（`ObservableSetting.java:352-361`、`DirtyTracker.java:30-70`）。
- **未知键保留**：未识别成员存 `unknownFields`，再次序列化原样写回（`ObservableSetting.java:359,397`）；`RawPreservingObjectProperty` 保留无法解析的原始 JSON（`:44-57`）。
- **读失败保守化**：schema/JSON 异常时加载默认值并置 `savable=false`，**绝不回写覆盖用户文件**（`JsonSettingFile.java:107-130`；`SettingsManager.java:1187-1214`）。

### 3.3 落盘实现

- `JsonSettingFile<T>`（`HMCL/setting/JsonSettingFile.java:43`）：泛型文件读写器，负责 schema 检查、写回 `savable`/`backupOnNextSave`、`installAutoSave`（变更监听）、`save`/`saveSync`、`backupAndOverwrite`（`:84-217`）。只接受 `ObservableSetting & JsonSchemaSetting`。
- `JsonSchemaSetting`（`JsonSchemaSetting.java:27`）：暴露 `get/setSchema`、`is/setSavable`、`is/setBackupOnNextSave`。
- `FileUtils.saveSafely`：先写同目录 `.<name>.tmp`，再 `Files.move(REPLACE_EXISTING)`（`HMCL/util/io/FileUtils.java:505-532`）。⚠️ **未 fsync、未用 ATOMIC_MOVE**。
- `FileSaver`：单后台线程，按 `Path` 去重（`HashMap<Path,String>`），**200ms 防抖**批量落盘，超时/shutdown 刷新，挂 JVM shutdown hook（`FileSaver.java:36-152`）；高频设置走它，账户等敏感数据走 `saveSync`。
- 坏文件先备份：`backupOnNextSave` → `SettingFileUtils.backupInvalidConfig` 按 `.json.1/.2/...` 递增改名保留原始字节（`SettingFileUtils.java:38-57`）。
- `SettingsManager`：静态门面/生命周期所有者，集中定义路径与 `JsonSettingFile` 助手，`init()` 加载全部 + 安装自动保存监听 + 执行迁移（`SettingsManager.java:1085-1150`）。

---

## 4. 已添加的游戏文件夹

### 4.1 存储

- 独立文件 `config/game-directories.json`（local）与 `config/user-game-directories.json`（user），类 `GameDirectories`；顶层键 `directories`（数组）（`GameDirectories.java:43-46,104-105`；schema `docs/schemas/game-directories/1.0.0.json:17-46`）。
- 每条由手写 `GameDirectory.Serializer` 序列化（`GameDirectory.java:164-207`）：
  - `id`：`game-directory:<uuid>` 强类型 ID（`GameDirectoryID.java:35-68`，**UUIDv7 时间有序**；内置目录用固定 UUID，`GameDirectoryManager.java:58-63`）。
  - `path`：`PortablePath`（相对路径用 `/`，绝对路径保留平台分隔符，`PortablePath.java:34-55`）。
  - `name`（可选）：`LocalizedText`（可序列化为字符串或 `{locale: text}` 对象，`LocalizedText.java:54-79,204-214`；schema `game-directories/1.0.0.json:56-69`）。
  - `legacyGameSettings`（可选）：旧版迁移来的 `game-settings-preset:<uuid>`。

### 4.2 选中项（不在目录文件里）

- `selectedGameDirectory`：`GameDirectoryID`（`LauncherSettings.java:601-603`）。
- `selectedInstance`：`Map<GameDirectoryID, GameInstanceID>`（每目录默认实例，`LauncherSettings.java:626-641`）。
- `defaultGameSettingsPreset`：`GameSettingsPresetID`（`LauncherSettings.java:614-615`）。

### 4.3 合并规则与"公共目录"

- local/user 两份合并：**同 ID 时 local 优先**（`GameDirectoryManager.rebuildGameDirectories`，`GameDirectoryManager.java:253-268`）；选择落地写回 `selectedGameDirectoryProperty`（`:199-220`）。
- `EnumCommonDirectory`「公共目录」是**另一回事**：以两个键存在 `launcher-settings.json` —— `commonDirectoryType`（`DEFAULT`/`CUSTOM`）+ `commonDirectory`（路径字符串）（`LauncherSettings.java:223-233`），由 `getResolvedCommonDirectory()` 解析（`:248-255`）。内置 `.minecraft` 目录用固定 ID + 内置路径（`GameDirectoryManager.java:58-69,166-183`）。

---

## 5. 账户持久化

### 5.1 文件与结构

| 内容 | 路径 |
|---|---|
| 本地账户元数据 | `<LOCAL>/config/accounts.json`（`SettingsManager.java:133-134,173-178`） |
| 共享账户元数据 | `<USER>/config/user-accounts.json`（`:137-138,181-186`） |
| 本地账户私密数据 | `<LOCAL>/private/account-private-data.json`（`:140-142,189-194`） |
| 共享账户私密数据 | `<USER>/private/user-account-private-data.json`（`:145-146,197-202`） |
| 当前选中账户 | `<LOCAL>/config/launcher-settings.json` 的 `selectedAccount`（`LauncherSettings.java:669-675`；`SettingsManager.java:105-106`） |

- `accounts.json` 顶层：`{ "$schema": <url>, "accounts": [ …原始 JsonObject… ] }`，schema 名 `accounts` v1.0.0（`AccountMetadataStore.java:37-45,127-129`）。
- 每条至少含 `type` 与 `accountID`（`Accounts.java:125-131,266-274`；键名串 `accountID` 见 `Account.java:50-51`）。
- 列表是 `ObservableList<JsonObject>`，**不强类型解析**；加载时按 `type` 路由到对应 `AccountFactory.fromStorage`（`Accounts.java:265-279`）。
- **选中账户只存一处** = `LauncherSettings.selectedAccount`（AccountID），不在每条冗余；旧格式的 `"selected": true` 仅作加载兼容（`Accounts.java:319`）。
- 写序：**先保存私密数据、再保存元数据**，防"有账户无凭证"（`SettingsManager.java:492-519,649-682`）。

### 5.2 敏感数据与保护

- `ProtectedPayload` 信封（`ProtectedPayload.java:39-59,87-116,210-233`）：字段 `protection` / `payload` / `nonce`。
- 默认 `OBFUSCATED_V1` = **ChaCha20-Poly1305 + 硬编码 32 字节密钥**，nonce 每次随机（`:107-116`）。可用 `-Dhmcl.account.privateData.protection=plain` 关闭；**未知值回退到加密而非明文**（`AccountPrivateData.java:55-56,102-104`；`ProtectedPayload.java:316-329`）。代码明确警告**不应视为设备绑定密钥库**（`:82-86`）。
- 三者分工：
  - `AccountMetadataStore` = 公开元数据（写 `accounts.json`，**禁止含凭据**）（`AccountMetadataStore.java:35-42`；`Account.java:100-109`）。
  - `AccountPrivateData` = `accountID → JsonObject` 映射，序列化为保护信封；解出 payload 形如 `[{"accountID":…,"privateData":{…}},…]`（`AccountPrivateData.java:69-71,130-145,186-204`）。
  - `ProtectedPayload` = 信封格式与加解密实现。
- token 落私密：
  - MSA `refresh_token` / `access_token` / `notAfter` / `tokenType` / `userid` / `profileName`（`MicrosoftSession.java:56-87`）。
  - Minecraft accessToken = 微软 `minecraftResponse.accessToken`，以 `accessToken` 存私密（`MicrosoftService.java:179`；`MicrosoftSession.java:82-86`）。
  - **XSTS 不持久化**（每次登录现取；`MicrosoftService.java:118-180`）。
  - authlib/Yggdrasil：`clientToken`/`accessToken`/`userProperties`/`profileProperties`（`YggdrasilSession.java:84-110`；`YggdrasilAccount.java:186-191`）。

### 5.3 三类账户字段差异

| type | 元数据字段 | 私密字段 |
|---|---|---|
| `offline` | `type`/`accountID`/`profileID`/`profileName`/`skin`（`OfflineAccount.java:191-203`；`OfflineAccountFactory.java:69-83`） | 无（全公开） |
| `microsoft` | `type`/`accountID`/`profileID`（`MicrosoftAccount.java:139-149`） | `profileName`/`tokenType`/`accessToken`/`refreshToken`/`notAfter`/`userid`（`MicrosoftSession.java:76-87`） |
| `authlibInjector` | `type`/`accountID`/`serverBaseURL`/`loginName`/`profileID`（`AuthlibInjectorAccount.java:145-149`；`YggdrasilAccount.java:178-183`） | `clientToken`/`accessToken`/`profileName`/`userProperties`（+可缓存 `profileProperties`）（`YggdrasilAccount.java:186-191`；`AuthlibInjectorAccountFactory.java:91-100`） |

- type↔工厂映射串固定 `"offline"` / `"authlibInjector"` / `"microsoft"`（`Accounts.java:77-83`）。
- 离线账户 `profileID` 缺失时用 `OfflinePlayer:<name>` 派生离线 UUID（`OfflineAccountFactory.java:85-87`）。

### 5.4 ID / 去重 / 排序 / 重名

- ID 格式 `account:<uuid>`（`TypedID.java:37,47-50`；`AccountID.java:40`）。
- 新建：随机 **UUIDv7**（时间有序）（`AccountID.generate()`，`AccountID.java:52-55`）。
- 迁移：旧记录用 **UUIDv5**（固定命名空间 + 旧标识）→ 同输入同 ID（`LegacyConfigMigrator.java:530-580,702-750`）。
- 去重：`ensureUniqueAccountIDs()` 先本地后共享，冲突重新生成（`Accounts.java:134-146`）。
- 排序：无显式排序，按"本地列表顺序 → 共享列表顺序"追加（`Accounts.java:314-330`）。
- 选中回退：ID 找不到用第一个；空列表为 null；选中项被删自动切第一个（`Accounts.java:332-344,376-405`）。
- 重名：身份只看 `AccountID`（+portable），`equals/hashCode = portable+accountID`，`profileName` 可重复、不合并（`Account.java:193-207`）。
- authlib 服务器：按 URL 去重（`Accounts.java:469-478`）；服务器被删则**级联删除**悬空账户（`:484-492`）。

---

## 6. 版本隔离（**不存在 `isolated` 布尔**）

> 目录契约细节见 [`启动器目录模型与版本隔离.md`](启动器目录模型与版本隔离.md) §2；此处只讲**持久化与判定**。

### 6.1 "是否隔离"存在哪

- **实例级**：`GameSettings.Instance.overrideProperties`（JSON 键 `"overrideProperties"`，`HMCL/setting/GameSettings.java:162-169`）集合里**是否含 `"runningDirectory"`**（键名常量 `PROPERTY_RUNNING_DIRECTORY = "runningDirectory"`，`:536`）；该实例的 `runningDirectory` 属性值（JSON 键 `"runningDirectory"`，默认 `""`，`:539-540`）。
- **预设级（全局默认策略）**：`GameSettings.Preset.defaultIsolationType`（JSON 键 `"defaultIsolationType"`，默认 `MODDED`，`GameSettings.java:223-230`），存 `config/game-settings.json` 的 `presets[]`（`GameSettingsPresets.java:37,114-116`）；当前默认预设 ID 在主设置 `defaultGameSettingsPreset`（`LauncherSettings.java:68,615`）。
- 三值 `DefaultIsolationType`：`ALWAYS` / `MODDED` / `NEVER`（`HMCL/setting/DefaultIsolationType.java:21-29`）。
- 默认判定：`HMCLGameRepository.shouldIsolateNewInstance(modded)`（`HMCL/game/HMCLGameRepository.java:435-443`）：`ALWAYS→true`、`NEVER→false`、`MODDED→modded`；`modded` = 安装时是否勾选任意 modloader（`HMCL/ui/download/DownloadPage.java:324-329`）。**该策略只决定"安装新版本"时是否隔离，并立刻物化为实例 override，不是每次启动再读。**

### 6.2 隔离语义（只有一个变量：运行目录）

- mods/resourcepacks/saves/backups/schematics 全是**运行目录的相对子目录**（`HMCLCore/game/GameInstance.java:134-164`）；无逐目录开关。
- 运行目录决策在仓库侧 `HMCLGameRepository.computeRunDirectory`（`HMCLGameRepository.java:225-248`）：
  - modpack → 强制 `instanceRoot`（`:230-232`）；
  - 否则 `useInstanceRunningDirectory = overrideProperties 含 "runningDirectory"`（`:234-236`）；
  - 值为空且隔离 → `versions/<id>/`；值为空且不隔离 → 仓库基目录（共享 `.minecraft`）（`:239-241`）；
  - 值为非空路径 → 使用该自定义绝对路径（`:243-246`）。
- `GameRepositoryLayout` 只做**纯路径计算、无 I/O**（`HMCLCore/game/GameRepositoryLayout.java:24-36`；`DefaultGameRepositoryLayout.java:52-117`），**不决定隔离**；`HMCLGameInstance.getRunDirectory()` 委托 `computeRunDirectory`（`HMCLGameInstance.java:161-163`）。
- 安装期：隔离则写 `getInstanceRoot`，否则更新目标原目录或基目录（`HMCLCore/download/DefaultGameBuilder.java:141-146`）。
- 日志/崩溃报告跟随工作目录（`HMCLGameRepository.clean()`，`:310-320`）。

### 6.3 UI 开关 = 增删 override

- 开 = 置空值并加入 `overrideProperties`；关 = 移除集合项（`HMCL/ui/…/GameSettingsPage.java:1726-1731`；等价 `HMCLGameInstance.enableIsolation()`，`:219-229`）。
- 结论：**预设给默认，实例文件定事实**；父预设的 `runningDirectory` 仅在未被 override 时被继承（`HMCLGameRepository.java:250-262`）。
- 复制/迁移实例时显式重写该 override（`HMCLGameRepository.java:364-367`）。

---

## 7. 每实例（版本）启动参数

### 7.1 文件与结构

- 路径：`<游戏目录>/versions/<id>/.hmcl/config/instance-game-settings.json`（`HMCL/game/HMCLGameRepositoryLayout.java:26-62`；文件名常量 `:36`，`getInstanceGameSettingsFile` `:60-62`）。
- 类别 `GameSettings.Instance`（`GameSettings.java:82`），schema `instance-game-settings/1.0.0`（`:84-85`）。

### 7.2 键清单（JSON 名 = `PROPERTY_*` 常量，均在 `HMCL/setting/GameSettings.java`）

| 类别 | JSON 键 | 行 |
|---|---|---|
| 结构 | `$schema` / `parent` / `icon` / `overrideProperties` | 94 / 145 / 154 / 163 |
| Java | `javaType` / `customJavaVersion` / `customJavaPath` / `detectedJava` | 344 / 356 / 368 / 380 |
| JVM | `jvmOptions` / `noJVMOptions` / `noOptimizingJVMOptions` / `notCheckJVM` | 392 / 404 / 416 / 428 |
| 内存 | `autoMemory` / `minMemory` / `maxMemory` / `permSize` | 452 / 464 / 476 / 488 |
| 窗口 | `windowType` / `width` / `height` / `runningDirectory` | 500 / 512 / 524 / 536 |
| 进程/启动器 | `processPriority` / `launcherVisibility` / `allowAutoAgent` / `disableAutoGameOptions` / `showLogs` | 548 / 560 / 572 / 584 / 756 |
| 游戏参数 | `gameArguments` | 597 |
| 图形 | `graphicsBackend` / `openGLRenderer` / `vulkanRenderer` / `highPerformance` | 609 / 621 / 634 / 647 |
| 环境/包装 | `environmentVariables` / `commandWrapper` | 660 / 672 |
| 前置/后置命令 | `preLaunchCommand` / `postExitCommand` | 684 / 696 |
| 快速进入 | `quickPlay` / `quickPlayMultiplayer` / `quickPlaySingleplayer` / `quickPlayRealms` | 708 / 720 / 732 / 744 |
| 日志/native | `enableDebugLogOutput` / `notPatchNatives` / `useCustomNatives` / `nativesDirectory` / `useNativeGLFW` / `useNativeOpenAL` | 768 / 780 / 792 / 804 / 816 / 828 |

要点：
- **"最大内存"键 = `maxMemory`（MiB 整数）**。
- **无独立"全屏"布尔**；全屏 = `windowType = FULLSCREEN`（`GameSettings.java:504`；`HMCLGameInstance.java:609`）。
- 服务器自动进入 = `quickPlay=MULTIPLAYER` + `quickPlayMultiplayer=<ip>`（`:1030`）。

### 7.3 两层模型（预设 + 实例覆盖）

- 全局可复用 `GameSettings.Preset`（存 `config/game-settings.json` 的 `presets[]`，`GameSettingsPresets.java:37-38,114-115`），自身键：`id` / `name` / `autoNameNumber` / `defaultIsolationType` + 全套可继承属性（`GameSettings.java:196,206,215,224`）；ID 形如 `game-settings-preset:<uuidv7>`（`GameSettingsPresetID.java:37,54`）。
- 每实例 `GameSettings.Instance` 只存覆盖，`parent` 指向 preset ID（`GameSettings.java:145-146`）；无 parent 时回退默认 preset（`HMCLGameRepository.getParentGameSettings` `:414-418`）。
- **覆盖判定靠 `overrideProperties` 白名单，而非"键是否存在"**：只有属性名 ∈ 集合才用实例值，否则用 preset 值（`GameSettings.java:853-897`，判定 `:889-891`）；测试明确验证"属性可独立继承"（`HMCL/src/test/java/org/jackhuang/hmcl/setting/GameSettingsInstanceTest.java:146-168`）。
- 运行时合成 `GameSettings.Effective`（`:848-850,900-1043`），启动时逐项取构造 `LaunchOptions`（`HMCLGameInstance.java:568-652`：`jvmOptions→overrideJavaArguments` `:593`、`maxMemory` `:582/594`、`windowType→fullscreen` `:609`、`preLaunchCommand` `:612`）。

### 7.4 读写 / 默认值 / 缺失键 / 迁移

- 全走 `LauncherSettings.SETTINGS_GSON`（`LauncherSettings.java:101-111`）。
- 默认值：`SimpleSettingProperty` 构造时保存默认，取值 `value != null ? value : defaultValue`（`SimpleSettingProperty.java:33-50`；`GameSettings.java:894-897`）。典型默认：`maxMemory=SUGGESTED_MEMORY`（`:480`）、`windowType=WINDOWED`（`:504`）、`width=854/height=480`（`:516/528`）、`autoMemory=true`（`:456`）。
- 缺失键：不触碰该属性、保持默认、不标 dirty、不写回。
- 每实例自动监听自身属性变化触发保存（`HMCLGameInstance.saveSettings / saveSettingsSync`，`:259-311`）；schema 校验与只读保护同 §2/§3。
- Legacy 迁移：旧 `versions/<id>/hmclversion.cfg` → 新属性映射（`javaArgs→jvmOptions`、`minecraftArgs→gameArguments`、`fullscreen(bool)→windowType`、`serverIp→quickPlayMultiplayer`、`javaDir→customJavaPath` 等，`LegacyGameSettingsMigrator.java:287-347`）；成功后写回执 `<instance>/.hmcl/state/instance-game-settings.migration-receipt.json`（`:47-49,140-145,553`）；**仅在实例设置文件不存在时**才做（`HMCLGameInstance.java:533-562`）。

---

## 8. 实例元数据（"这个版本是什么"）

- **版本清单**（指向哪个版本/主要元数据）：`<游戏目录>/versions/<id>/<id>.json`，类 `GameInstanceManifest`（`DefaultGameRepositoryLayout.java:61-63`；`GameInstanceManifest.java:41-64`）。字段：`id`/`inheritsFrom`/`jar`/`mainClass`/`arguments`/`libraries`/`assetIndex`/`assets`/`downloads`/`logging`/`type`/`time`/`releaseTime`/`minimumLauncherVersion`/`root`/`hidden`/`patches`（`:132-287`）。
- **图标**：逻辑类型存实例设置 `icon`（`GameSettings.java:154-155`，枚举 `GameInstanceIconType`）；自定义图标文件 `versions/<id>/icon.<ext>`（`HMCLGameInstance.java:336-344`，选择/派生 `:447-481`）。
- **显示名**：HMCL **不单独存**——实例名 = 目录/ID（`GameInstanceID.java:31`）；"重命名"实为改目录名（`HMCL/ui/instances/Instances.renameInstance` `:140-150`）。只有 preset 有可本地化 `name`。
- **创建时间**：**不持久化**；列表排序用 manifest 的 `releaseTime`（缺失取 `Instant.EPOCH`）（`HMCLGameRepository.java:300-302`）。
- 其它：异常启动标记 `.abnormal`（`HMCLGameInstance.java:490-513`）；modpack 配置 `modpack.cfg`（`:132-135`；layout `:73-75`）。

---

## 9. 迁移机制（三套，别混）

1. **Legacy 文件迁移**（旧 `hmcl.json` / `.hmcl.json` → 新文件）：
   - 触发：当前 `launcher-settings.json` 不存在时才尝试（`SettingsManager.loadLauncherSettings:1154-1225`）；user 设置在 `user-settings.json`+`user-state.json` 都缺时（`:1103-1108`）；user 账户缺失时（`:1518-1520`）。
   - `LegacyConfigMigrator` 读旧文件、删旧数值版本号 `_version`（`LEGACY_CURRENT_CONFIG_VERSION=2`），必要时 `upgradeConfig`；大量字段改名（`commonpath→commonDirectory`、`bgpath→customBackgroundImagePath`…），并把 `configurations`/`accounts`/窗口状态拆到独立文件（`LegacyConfigMigrator.java:60-61,174-288,1133-1185`）。
   - 迁移 ID 用**确定性 UUIDv5**（profile / game settings / account 各一命名空间，`:64-73,132-140`），保证重复迁移稳定。
2. **MigrationReceipt（防重放）**：记录源文件 `sourceSize`/`sourceLastModified`/`sourceSHA256`/`migratedAt`，`matches` 只比 SHA-256（`MigrationReceipt.java:43-96`）；receipt 放 `state/*.migration-receipt.json`（`LegacyConfigMigrator.java:94-109`）；**只有迁移数据（尤其账户私密数据）成功写盘后才写 receipt**（`SettingsManager.java:1133-1139`），旧文件保持不动。
3. **schema 版本守卫**（同格式演进）：见 §2。

---

## 10. 可借鉴点与坑

### 借鉴

1. **按域分文件 + `$schema` + 版本守卫**：旧数据可安全读，前向兼容不丢字段。
2. **只写脏字段 + 保留未知键**：文件稀疏、跨版本安全。
3. **全局预设 + 每实例覆盖两层**，物理分文件；**覆盖用显式白名单** `overrideProperties`（"恢复继承"= 移除名字），而非以"键存在"判覆盖。
4. **身份/凭据 与 启动参数 分层**：账户体系独立于游戏设置。
5. **强类型前缀 ID**（`account:` / `game-directory:` / `game-settings-preset:`），与显示名解耦，重命名/移动路径不破坏引用。
6. **原子写**（临时文件 + move）、**异步防抖合并写**（`FileSaver`）、**坏文件先备份 `.N`**、**读失败只读不覆盖**。
7. **先写私密数据、后写元数据**。
8. **隔离=运行目录一个变量 + override 标记**（可表达"跟随默认 / 显式隔离 / 自定义路径"三态）。

### 坑

1. 写失败**静默**（`FileSaver.saveSync` 只 `LOG.warning` 不抛，`FileSaver.java:63-70`）。
2. **非原子语义**：`Files.move` 无 `ATOMIC_MOVE`、无 fsync，掉电/崩溃可能丢最后一批写。
3. **跨进程无锁**：多实例同跑会互相覆盖（仅内存 `DirtyTracker` + 合并写）。
4. **只写脏字段的副作用**：文件依赖运行期默认值；日后改默认值会给旧文件"补全"。
5. **迁移顺序耦合**：账户迁移依赖 private 可写，任一 store 只读则整体跳过（`SettingsManager.java:625-629,1133-1139`）。
6. **平台/权限特判**：root 读他人文件标 `ownerChanged`；Windows Samba/OpenJDK 可写性误报有专门 `SambaException` 路径（`SettingsManager.java:1617-1661`）。
7. **schema 文档手写**：Java 常量 ↔ `docs/schemas/*.json` ↔ 字段名三处需人工同步，无生成校验。
8. **"加密"名不副实**：账户私密数据仅硬编码密钥混淆，非真安全。

---

## 11. 与本项目现状对照

> 仅**对照**，不在此定方案（用户指示"先不开工"）。

| 维度 | HMCL | 我们现状（代码核实） |
|---|---|---|
| 配置根 | 双根 local `.hmcl` + user home，按域分 JSON 文件 | **应用沙箱** `<filesDir>/meow-settings/*.json`（目录枚举 + 账户含 token + 全局设置 `global` 段；2026-09-15 起，Preferences 已彻底移除，连迁移代码一并删除）+ **游戏根内 `<gameRoot>/versions/<id>/.hmmcraft/instance-settings.json`**（仅逐版本设置）+ 少量散落 rawfile |
| 已添加文件夹 | `game-directories.json`（强类型 ID + PortablePath）；选中项在主设置 | `filesDir/meow-settings/app-settings.json` 的 `dirs`（`GameDirsTools`）；选中项 `selectedDir` + 授权持久化（`FileAccess`） |
| 账户 | 元数据/私密**两文件**，私密用 `ProtectedPayload` 信封 | `filesDir/meow-settings/accounts.json`（含 token，`format:1`）；无保护信封（Asset Store 为可选更安全替代） |
| 账户选中 | 主设置 `selectedAccount` 单一指针 | `app-settings.json` 的 `selectedAccount` |
| 登录有效期 | 私密数据 `notAfter`；启动期校验 | `notAfter` + `ensureMicrosoftFresh`（主进程门控 + 启动拦截），已对齐 HMCL 语义 |
| 版本隔离 | **无布尔**；`overrideProperties` 含 `runningDirectory` + 预设 `defaultIsolationType`（`ALWAYS/MODDED/NEVER`），安装时物化 | **逐版本布尔**，只切"运行目录"一个变量（本质一致，粒度更粗） |
| 每版本参数 | `<instance>/.hmcl/config/instance-game-settings.json`（预设+实例覆盖） | **全局** = `app-settings.json` 的 `global` 段（应用级、全局唯一；显示缩放/采样率/CPU 线程/最大内存/滚轮…）；**逐版本** = `<id>/.hmmcraft/instance-settings.json`（隔离/后端/glthread） |
| 实例元数据 | `versions/<id>/<id>.json`（manifest） | `versions/<id>/<id>.json`（原版）+ 扫描结果 |
| 迁移 | 字段改名 + 确定性 UUID + `MigrationReceipt` | 数据令牌门（JRE `meow_jre_data`、`EXTRAS_VERSION`） |

**潜在对齐方向（仅列出，未设计）**：① 账户把凭据拆独立文件并考虑加保护；② 高级选项升级为"全局默认 + 每版本覆盖"两层；③ 隔离从裸布尔升级为"override + 值"（支持自定义运行目录 / 跟随默认）；④ 持久化引入 schema/版本号 + 未知键保留。

---

## 12. HMCL 架构总览（原《HMCL 深度分析》并入）

> 本节原为独立档 `hmcl.md`（描述 HMCL **旧类名体系** `Version`/`DefaultLauncher`），与当前 `ref/HMCL` 新版重构（`GameInstance`/`GameRepositoryLayout`）**不是同一套代码**；但**架构层面的划分与抽象仍成立**，故并入本档（旧档归档于 [`../90-archive/hmcl.md`](../90-archive/hmcl.md)）。
> HMCL 是开源跨平台 MC 启动器（Windows/Linux/macOS/FreeBSD），支持 x86/ARM/RISC-V/MIPS/LoongArch 等架构，是多平台启动器的"教科书级"实现。

### 12.1 模块划分（三模块 + 两个游戏内库）

```
HMCL (rootProject "HMCL3")
├── HMCLCore/   # 核心库：纯逻辑、无 UI（下载 / 版本 / 账户 / 启动 / 平台抽象）
├── HMCL/       # UI 层（JavaFX / Swing）
├── HMCLBoot/   # 引导层（EntryPoint / Main）
└── minecraft/libraries/
    ├── HMCLTransformerDiscoveryService    # 注入 MC 进程的 Transformer 发现服务
    └── HMCLMultiMCBootstrap               # MultiMC 兼容引导
```
**分层哲学**：`HMCLCore` 与 UI 完全解耦、可被任何 UI 复用 —— 值得借鉴：把"版本解析 / 下载 / 账户 / 参数"独立成 Core，UI 只是壳。

### 12.2 HMCLCore 核心包

```
org/jackhuang/hmcl/
├── auth/        账户：Account/OAuth + authlibinjector / microsoft / offline / yggdrasil
├── download/    下载：DependencyManager + forge/fabric/neoforge/optifine/quilt/…
├── game/        游戏模型：GameVersion/Library/Arguments/Rule…
├── launch/      启动：DefaultLauncher/Launcher
├── java/        JRE 管理：JavaRepository/JavaRuntime/JavaInfo
├── modpack/     模组包：curse/modrinth/mcbbs/multimc/server
├── addon/       mod/datapack/resourcepack 抽象
├── task/        通用异步任务框架
└── util/platform/  平台抽象（见 §12.3）
```

### 12.3 平台抽象（`util/platform/`）

HMCL 能跨 Win/Mac/Linux/FreeBSD + 多架构的关键：
- `OperatingSystem` 枚举（WINDOWS/LINUX/MACOS/FREEBSD/UNKNOWN；每个 OS 有 `checkedName` 运行时检测 + `mojangName` 官方命名，注意 mojang 叫 `osx`）。
- 配套：`Architecture`（x86/arm64/… + `SYSTEM_ARCH`）、`Bits`、`CommandBuilder`（跨平台命令行构建、引号/转义）、`ManagedProcess`、`SystemInfo`/`OSVersion`/`HardwareVendor`、`hardware/`+`linux/`+`macos/`+`windows/` 特定实现。
- 平台支持矩阵（HMCL 仓库的 docs/PLATFORM.md 非常详尽）：ARM64 Win/Linux/macOS 全支持；ARM32 Linux 有限；RISC-V64/LoongArch64 Linux 支持。

### 12.4 启动器参数生成（`launch/DefaultLauncher.java`，约 1023+ 行）

`generateCommandLine()` 最值得学习：进程优先级（Win `start /高`、*nix `nice`）、内存（`-Xmx/-Xms/-XX:MetaspaceSize`）、编码（`sun.stdout/stderr.encoding`）、log4j RCE 防护、GC/JIT 参数组、平台差异（macOS `-Xdock:*`）、**占位符替换**（`${auth_player_name}`/`${classpath}`/`${version_name}`… 结合 `CompatibilityRule` OS/feature 规则）、natives 解压（按 `ExtractRules`、跳过 GLFW/SDL/OpenAL）、`makeLaunchScript()` 导出 `.bat/.sh/.ps1`。
（对比 HomoLauncher：HMCL 的规则引擎 + 占位符更严谨。）

### 12.5 依赖下载架构（`download/`）

`DependencyManager`（接口）→ `DefaultDependencyManager`；`DownloadProvider`（Mojang / BMCLAPI 镜像）；`GameBuilder`（抽象，AutoCloseable）→ `DefaultGameBuilder`；各 modloader 独立任务（`ForgeInstallTask`/`FabricInstallTask`/`NeoForge*`/`OptiFine*`/`Quilt*`/`LiteLoader*`/`Cleanroom*`/`LegacyFabric*`）；`java/` 下 JRE 下载（disco/mojang 两源）。

### 12.6 账户体系（`auth/`）

抽象 `Account`（含 `AuthInfo`）+ 工厂 `AccountFactory`；实现 `OAuthAccount`（微软）/ `ClassicAccount`（Yggdrasil / 离线）/ `authlibinjector`（第三方皮肤站）；`microsoft/MicrosoftService` 四级 OAuth（XBL→XSTS→Minecraft）；账户数据结构有 JSON Schema（`docs/schemas/accounts/1.0.0.json`）。

### 12.7 游戏模型（`game/`）

`GameVersion` / `GameInstance` / `GameRepository`（`.minecraft` 布局）/ `GameRepositoryLayout`（可插拔布局，含 MultiMC）/ `Library`/`Artifact`（含 natives/rules/extract）/ `Arguments`（StringArgument/RuledArgument）/ `CompatibilityRule`（OS/feature 规则）/ `Renderer`/`GraphicsAPI`。
> mod loader（尤其 **Fabric**）的实例模型 / 继承·补丁解析 / 与原版启动差异，见 [`../20-design/launch/Fabric支持-调研.md`](../20-design/launch/Fabric支持-调研.md)。

### 12.8 UI（HMCL 模块，JavaFX）

`ui/main/MainPage.java` + `ui/account/`、`ui/download/`、`ui/installer/`、`ui/version/` 等；`terracotta` 主题/皮肤引擎；内置 `com/jfoenix`（JFoenix fork）；`i18n` 多语言。

### 12.9 两个游戏内库

- `HMCLTransformerDiscoveryService`：实现 ModLauncher 的 `ITransformerDiscoveryService` SPI，经 `-Dhmcl.transformer.candidates` 注入候选 jar（对应 HomoLauncher resfile 里的 `HMCLTransformerDiscoveryService-1.0.jar`）。
- `HMCLMultiMCBootstrap`：MultiMC 实例引导。

### 12.10 元数据与运行要求

最低/支持 Java 17、推荐 Java 21（`Metadata.java`）；版本号从 jar manifest `hmcl.version` 读取。

### 12.11 对"鸿蒙 PC"落地的价值总结

1. **分层架构**：Core/UI/Boot 分离，值得在鸿蒙启动器整体设计时模仿。
2. **平台抽象层**：`OperatingSystem`/`Architecture`/`CommandBuilder` 的 enum+接口设计，是把启动器做成多平台可复用的样板（鸿蒙 = 新增一个 `HARMONYOS` 枚举值 + 平台实现包）。
3. **参数规则引擎**：`Arguments` + `CompatibilityRule` + 占位符映射比手工拼参更健壮。
4. **下载指标体系**：`DependencyManager`+`DownloadProvider` 镜像源设计（解决国内下载慢）。
5. **账户体系**：多账户类型 + JSON Schema。
6. **数据模型完整性**：`game/` 的结构化模型可作为鸿蒙侧 `MinecraftVersion` 模型的扩充蓝本。

---

### 12.12 旧档补充事实（原《HMCL 深度分析》）

- **平台矩阵**：ARM64 Win/Linux/macOS 全支持；ARM32 Linux 有限；RISC-V64/LoongArch64 Linux 支持。
  游戏兼容按 OS×架构列表：ARM64 Linux 上 MC 1.8–26.2 可用，1.19+ 为官方支持面。
- **参数细节**：`Java<8` 用 `-XX:PermSize`；编码参数在 `java<19`（`sun.stdout/stderr.encoding`）与 `19+`
  （`stdout/stderr.encoding`）分叉；macOS 加 `-Xdock:*`；非 Windows 加 `-Duser.home`；渲染器差异化 env。
- **占位符全集**：`${auth_player_name}` / `${auth_session}` / `${classpath}` / `${natives_directory}` /
  `${version_name}` 等，由 `Arguments.parseArguments` + `CompatibilityRule` 填充。
- **natives 解压**：按 `ExtractRules`，跳过 GLFW/SDL/OpenAL；`makeLaunchScript()` 可导出 `.bat/.sh/.ps1`。
- **与 HOML 的关系**：HOML 把同一套思想简化为 ArkTS 的 `replaceAllArgs`；HMCL 的规则引擎更完整。
- **元数据**：最低 Java 17、推荐 21；版本号读 jar manifest 的 `hmcl.version`。

## 13. 证据索引

**全局配置/机制**
- `HMCL/Metadata.java`（双根）、`HMCL/setting/SettingsManager.java`（路径注册 + 加载 + 迁移）、`HMCL/setting/LauncherSettings.java`（主设置）、`HMCL/setting/UserSettings.java`、`HMCL/setting/JsonSettingFile.java`、`HMCL/setting/JsonSchemaSetting.java`、`HMCL/util/io/JsonSchema.java`、`HMCL/setting/ObservableSetting.java`、`HMCL/setting/SettingFileUtils.java`、`HMCL/util/io/FileUtils.java`、`HMCL/util/io/FileSaver.java`。
- schema 文档：`ref/HMCL/docs/schemas/`。
- 迁移：`HMCL/setting/LegacyConfigMigrator.java`、`HMCL/setting/MigrationReceipt.java`、`HMCL/src/test/java/org/jackhuang/hmcl/setting/LauncherSettingsMigrationTest.java`。

**文件夹**
- `HMCL/setting/GameDirectories.java`、`GameDirectory.java`、`GameDirectoryID.java`、`GameDirectoryManager.java`、`EnumCommonDirectory.java`。

**账户**
- `HMCL/setting/Accounts.java`、`AccountMetadataStore.java`、`AccountPrivateData.java`、`ProtectedPayload.java`、`AuthlibInjectorServer*.java`。
- `HMCLCore/auth/`（`Account.java`、各 Factory/Session）、`HMCLCore/auth/microsoft/MicrosoftService.java`、`MicrosoftSession.java`。

**隔离**
- `HMCL/setting/DefaultIsolationType.java`、`GameSettings.java`（`overrideProperties`/`runningDirectory`/`defaultIsolationType`）。
- `HMCL/game/HMCLGameRepository.java`（`computeRunDirectory`/`shouldIsolateNewInstance`）、`HMCLGameInstance.java`（`enableIsolation`）。
- `HMCLCore/game/GameRepositoryLayout.java`、`DefaultGameRepositoryLayout.java`、`GameInstance.java`、`DefaultGameBuilder.java`。

**每实例设置**
- `HMCL/setting/GameSettings.java`、`GameSettingsPresets.java`、`GameSettingsPresetID.java`、`setting/property/*`、`HMCL/game/HMCLGameRepositoryLayout.java`、`HMCLGameInstance.java`、`LegacyGameSettingsMigrator.java`、`HMCL/src/test/java/org/jackhuang/hmcl/setting/GameSettingsInstanceTest.java`。
- `HMCLCore/game/LaunchOptions.java`、`GameInstanceManifest.java`。

**复现（只读）**
```sh
# 看 HMCL 双根与文件清单
sed -n '60,250p' ref/HMCL/HMCL/src/main/java/org/jackhuang/hmcl/setting/SettingsManager.java
# 看每实例设置键定义
grep -n "PROPERTY_" ref/HMCL/HMCL/src/main/java/org/jackhuang/hmcl/setting/GameSettings.java | head -80
# 看隔离判定
grep -n "computeRunDirectory\|shouldIsolateNewInstance\|overrideProperties" ref/HMCL/HMCL/src/main/java/org/jackhuang/hmcl/game/HMCLGameRepository.java
```

## 相关

- 目录契约 / 隔离三值策略 / 安装流程：[`启动器目录模型与版本隔离.md`](启动器目录模型与版本隔离.md)
- 架构总览（模块 / 平台抽象 / 参数生成 / 下载 / 账户 / 游戏模型 / UI）：本文 §12
- 本目录索引：[`README.md`](README.md)
- 记忆：`hmcl_storage_model`（本档压缩版）、`meowcraft_account_system_research`、`meowcraft_microsoft_token_lifecycle`
