> 已归档（2026-10-02；本文描述 HMCL **旧类名体系**（`Version`/`DefaultLauncher`），与当前 `ref/HMCL` 新版重构（`GameInstance`/`GameRepositoryLayout`）**不是同一套代码**；仍有效的总览内容已并入 [`../10-research/hmcl-存储模型.md`](../10-research/hmcl-存储模型.md)）。

# HMCL 深度分析（旧类名体系）

> 位置：`ref/HMCL`
> 定位：开源跨平台 Minecraft 启动器（Windows/Linux/macOS/FreeBSD），支持 x86/ARM/RISC-V/MIPS/LoongArch 等架构。
> 它是多平台启动器的"教科书级"实现，架构最成熟。
> 持久化（配置文件 / 账户 / 每实例设置 / 隔离如何落盘）单列：[`../10-research/hmcl-存储模型.md`](../10-research/hmcl-存储模型.md)。

## 1. 模块划分（三模块 + 两个游戏内库）

```
HMCL (settings.gradle.kts 的 rootProject "HMCL3")
├── HMCLCore/       # ★核心库：纯逻辑，无 UI（下载/版本/账户/启动/平台抽象）
├── HMCL/           # UI 层（JavaFX/Swing，用户界面）
├── HMCLBoot/       # 引导层（EntryPoint/Main，负责启动 UI）
└── minecraft/libraries/
    ├── HMCLTransformerDiscoveryService    # 注入到 MC 进程的 Transformer 发现服务
    └── HMCLMultiMCBootstrap               # MultiMC 兼容引导
```

**分层哲学**：`HMCLCore` 与 UI 完全解耦，可被任何 UI 复用。这是 HomoLauncher 值得借鉴的架构 —— 把
"版本解析/下载/账户/参数"逻辑独立成 Core，UI 只是壳。

## 2. HMCLCore 核心包

```
org/jackhuang/hmcl/
├── auth/                  # 账户：Account/OAuth + authlibinjector/microsoft/offline/yggdrasil
├── download/              # ★下载：DependencyManager + forge/fabric/neoforge/optifine/quilt/...
│   ├── DependencyManager.java        # 依赖管理接口（核心）
│   ├── GameBuilder.java              # 游戏构建器（抽象类，AutoCloseable）
│   ├── DefaultDependencyManager.java
│   ├── DefaultGameBuilder.java
│   ├── DownloadProvider.java         # 下载源抽象（Mojang/BMCLAPI）
│   └── game/java/forge/fabric/...    # 各组件安装任务
├── game/                  # ★游戏模型：GameVersion/Library/Arguments/Rule...
│   ├── Argument.java / Arguments.java   # 参数模型（支持规则表达式）
│   ├── CompatibilityRule.java           # OS 兼容规则
│   ├── Library.java / Artifact.java     # 依赖库模型
│   ├── GameRepository.java / Layout     # .minecraft 目录布局
│   └── ...
├── launch/                # ★启动：DefaultLauncher/Launcher/DefaultLauncher
├── java/                  # JRE 管理：JavaRepository/JavaRuntime/JavaInfo
├── modpack/               # 模组包：curse/modrinth/mcbbs/multimc/server
├── addon/                 # mod/datapack/resourcepack 抽象
├── task/                  # 通用异步任务框架
└── util/platform/         # ★平台抽象（见下）
```

## 3. 平台抽象（★多平台教科书，`util/platform/`）

这是 HMCL 能跨 Win/Mac/Linux/FreeBSD + 多架构的关键：

```java
// OperatingSystem 枚举：WINDOWS/LINUX/MACOS/FREEBSD/UNKNOWN
// 每个 OS 有 checkedName（运行时检测）和 mojangName（MC 官方命名）
public enum OperatingSystem {
    WINDOWS("windows"),
    LINUX("linux"),
    MACOS("macos", "osx"),   // 注意 mojang 叫 osx
    FREEBSD("freebsd", "linux"),
    UNKNOWN("universal");
}
```

配套抽象：
- `Architecture.java`（x86/x86_64/arm/arm64/... + `SYSTEM_ARCH`）
- `Bits.java`（BIT_32/BIT_64）
- `CommandBuilder.java`（跨平台命令行构建，处理引号/转义）
- `ManagedProcess.java`（进程封装）
- `SystemInfo.java` / `OSVersion.java` / `HardwareVendor`（硬件探测）
- `hardware/`、`linux/`、`macos/`、`windows/`（平台特定实现：WinReg、Kernel32、Homebrew...）

**平台支持矩阵**（docs/PLATFORM.md 非常详尽）：
- ARM64：Win/Linux/macOS 全支持；ARM32：Linux 有限支持；RISC-V64/LoongArch64：Linux 支持。
- 游戏兼容也按 OS×架构 列表（ARM64 在 Linux 上 MC 1.8~26.2 可用，1.19+ 官方支持）。

## 4. 启动器参数生成（★launch/DefaultLauncher.java，约 1023+ 行）

`generateCommandLine()` 是最值得学习的方法，完整展示 JVM 参数如何按版本/OS/渲染器动态生成：

- **进程优先级**：Windows 用 `start /高`，Linux/macOS 用 `nice -n`。
- **内存**：`-Xmx`/`-Xms`/`-XX:MetaspaceSize`（Java<8 用 PermSize）。
- **编码**：`-Dfile.encoding` + `sun.stdout/stderr.encoding`（java<19）或 `stdout/stderr.encoding`（19+）。
- **log4j RCE 防护**：`-Djava.rmi.server.useCodebaseOnly` 等 + `-Dlog4j2.formatMsgNoLookups=true`。
- **GC/JIT 优化**：G1GC 参数组、Unlock 参数、大内存时 ReservedCodeCacheSize 等。
- **平台差异**：macOS 加 `-Xdock:name/icon`；非 Windows 加 `-Duser.home`；渲染器差异化环境变量。
- **参数占位符替换**：`getConfigurations()` 提供 `${auth_player_name}`/`${auth_session}`/`${classpath}`/
  `${natives_directory}`/`${version_name}` 等完整映射，然后 `Arguments.parseArguments` 结合
  `CompatibilityRule`（OS/feature 规则）填充。
- **natives 解压**：`decompressNatives()` 按 Library 的 ExtractRules 解压，跳过 GLFW/SDL/OpenAL（如用了原生）。
- **启动脚本导出**：`makeLaunchScript()` 可生成 `.bat`/`.sh`/`.ps1` 调试脚本。

**对比 HomoLauncher**：HMCL 的参数生成更严谨（规则引擎 + 占位符 + 后端校验），HomoLauncher 是
把 HMCL 同款思想做了 ArkTS 简化版（`replaceAllArgs`）——但 HMCL 的全面性可作为补齐功能的参照。

## 5. 依赖下载架构（download/）

- `DependencyManager`（接口）→ `DefaultDependencyManager`，负责下载 libraries/assets/natives。
- `DownloadProvider`（接口）→ `MojangDownloadProvider` / `BMCLAPIDownloadProvider`（国内镜像）。
- `GameBuilder`（抽象，AutoCloseable）→ `DefaultGameBuilder`：构建完整游戏实例。
- 各 modloader 独立任务：`ForgeInstallTask`、`FabricInstallTask`、`NeoForge*`、`OptiFine*`、
  `Quilt*`、`LiteLoader*`、`Cleanroom*`、`LegacyFabric*`。
- `java/`：JRE 下载（disco/mojang 两个源）。

## 6. 账户体系（auth/）

- 抽象 `Account`（含 `AuthInfo`），工厂 `AccountFactory`。
- 实现：`OAuthAccount`（微软）、`ClassicAccount`（Yggdrasil/离线）、`authlibinjector`（第三方皮肤站）。
- `microsoft/MicrosoftService` 与 HomoLauncher 同款四级 OAuth（XBL→XSTS→Minecraft）。
- 账户数据结构有 JSON Schema（docs/schemas/accounts/1.0.0.json）。

## 7. 游戏模型（game/）

高度结构化的数据模型：`GameVersion`、`GameInstance`、`GameRepository`（.minecraft 布局）、
`GameRepositoryLayout`（可插拔目录布局，含 MultiMC 等）、`Library`/`Artifact`（含 natives/rules/extract）、
`Arguments`（StringArgument/RuledArgument）、`CompatibilityRule`（OS/feature 规则）、`Renderer`/`GraphicsAPI`。

**与 HomoLauncher 的 `MinecraftVersion.ets` 对比**：结构几乎一一对应（HMCL 更完整，多了
RuledArgument 规则求值、多个 GameRepository 实现等）。
> mod loader（尤其 **Fabric**）的**实例模型 / 继承·补丁解析 / 与原版启动差异**，见 [`../20-design/launch/Fabric支持-调研.md`](../20-design/launch/Fabric支持-调研.md)。

## 8. UI（HMCL 模块，JavaFX）

- `ui/main/MainPage.java`（主界面）、`ui/account/`、`ui/download/`、`ui/installer/`、`ui/version/` 等页面。
- `terracotta`：主题/皮肤引擎。
- 内置 `com/jfoenix`（JFoenix，Material 风格控件库的 fork）。
- `i18n`：多语言（translator 子包）。

## 9. 两个游戏内库

- `HMCLTransformerDiscoveryService`：实现 `ITransformerDiscoveryService`（ModLauncher 的 SPI），
  通过 `-Dhmcl.transformer.candidates` 属性注入候选 jar，用于 HMCL 向 MC 进程注入 transformer
  （对应 HomoLauncher resfile 里的 `HMCLTransformerDiscoveryService-1.0.jar`！）。
- `HMCLMultiMCBootstrap`：MultiMC 实例引导。

## 10. 元数据与运行要求

- 最低/支持 Java 17，推荐 Java 21（`Metadata.java`）。
- 版本号从 jar manifest `hmcl.version` 属性读取。

## 11. 对"鸿蒙 PC"落地的价值总结

1. **分层架构**：Core/UI/Boot 分离，值得在鸿蒙启动器整体设计时模仿。
2. **平台抽象层**：`OperatingSystem`/`Architecture`/`CommandBuilder` 的 enum+接口设计，是未来若要把
   启动器做成多平台可复用的样板（鸿蒙 = 新增一个 `HARMONYOS` enum 值 + 平台实现包）。
3. **参数规则引擎**：`Arguments` + `CompatibilityRule` + 占位符映射的严谨实现，比 HomoLauncher 的
   手工拼参更健壮，可作为补齐完整体。
4. **下载指标体系**：`DependencyManager`+`DownloadProvider` 镜像源设计，解决国内下载慢问题。
5. **账户体系**：多账户类型 + JSON Schema，可借鉴。
6. **数据模型完整性**：`game/` 包的结构化模型可作为鸿蒙侧 `MinecraftVersion` 模型的扩充蓝本。
