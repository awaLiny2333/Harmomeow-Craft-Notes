# 净室 meow.launcher — 设计与实施

> 已归档（2026-10-01；因为 2026-10-01 方案 A 已整体退役 MeowLauncher / MeowClassLoader / launcher.jar；现役口径见 [`决策与不变量.md`](../20-design/launch/决策与不变量.md)）。

> **⚠️ 历史设计记录（横幅，2026-10-01）**：**方案 A 已退役 `MeowLauncher` / `MeowClassLoader`** ——
> 随包 `launcher.jar`（连同其 `gson-for-launcher.jar`）自 `meowcraft_extras.tar.gz` 摘除，所有形态
> **一律直启 `json.mainClass`、恒不设 `-Djava.system.class.loader`**（见 [`../20-design/launch/启动链-总览.md`](../20-design/launch/启动链-总览.md)）。
> **本文以下内容保留为历史设计记录**，不再描述当前实现。

> 2026-09-10 立项并落地。目标：用**自研 Java 启动器**替换 `launcher.jar`（原为 PojavLauncher_iOS 派生，
> **GPL-3.0** + `net.kdt` 命名；现已净室取代并删除），彻底去掉 GPL 与 Pojav 血统，同时保持外部启动契约稳定。
> 契约依据（本仓 agent 卷宗）：launcher 侧接口面 + Pojav 行为面（已提取为"行为契约"，非抄代码）。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 7 条](../00-current/现状基线.md)。

## 0. 一句话
把 launcher.jar 从"Pojav 派生件"换成"**meow.launcher 净室实现**"：同 jar 成员名、同 argv/属性/路径契约，
类名成对改名；只依赖 **Apache-2.0** 件（gson、AOSP `android/util`），**不再含任何 GPL 代码**。

## 1. 范围
- **产出**：新 `launcher.jar`，内含 `meow.launcher.*` + clean-room `com.mojang.text2speech` 桩
  + vendored Apache-2.0 `android/util/*`（现被 lwjgl.jar 的 GLFW 使用）。
- **不改**：MC 版本 / `lwjgl.jar` / 3 so / ArkTS 启动编排逻辑（仅改 2 个契约常量）。
- **不做**：原生解压（1.17–1.21.x 不需要，卷宗确认原实现也没有）；`Server_Ip` 快连（去 HMCL GPL）；
  macOS/eawt 块；把 cacio 门降级为无害可选探测。

## 2. 净室协议（必须遵守）
- 我们**已读过** Pojav/HOML 源码 → 不满足严格双团队净室；因此纪律是：**只按"契约/行为"独立实现，不复刻其代码结构、命名与表达**。
- 契约来源 = 本仓 ArkTS（`MinecraftLauncher.ets`/`LaunchContract.ets`）+ **Mojang 公开 JSON schema** + 实机观测（日志 `CMD:`/属性）。
- 已完成的"行为卷宗"（本例依据）：接口面 + 行为面两份，落于会话与本节 §4/§5 摘要。

## 3. 命名决策
| 项 | 现（Pojav） | 新（净室） |
|---|---|---|
| 主类 | `net.kdt.pojavlaunch.PojavLauncher` | `meow.launcher.MeowLauncher` |
| 类加载器 | `net.kdt.pojavlaunch.PojavClassLoader` | `meow.launcher.MeowClassLoader` |
| 其它内部类 | `net.kdt.pojavlaunch.*` | `meow.launcher.*` |

成对改 ArkTS **两处**：`LaunchContract.ets`（`MEOW_MAIN_CLASS`/`MEOW_CLASS_LOADER`）+ `MinecraftLauncher.ets`（`-Djava.system.class.loader` 与 main class）。
**属性键**（`MEOWCRAFT_HOME`/`MEOWCRAFT_GAME_DIR`/`meowcraft.path.*`/`glfwstub.*`…）——牵动桥/原生/策略。

## 4. 外部契约（不可变，或成对改）
- jar 成员名：`lwjgl.jar` / `launcher.jar` / `gson-for-launcher.jar`（**不变**；staging 白名单）。
- argv：`[<playerName>, <versionId>]`；主类 `main(String[])`；另有 `launchMinecraft(String[])`。
- 类加载器：`extends java.net.URLClassLoader`，**public `(ClassLoader)` 构造**；`addURL` 追加到 `java.class.path`；父优先。
- 启动路径/宏/账号键/版本 JSON 键/`options.txt`：Mojang 事实，**保持**。
- 属性/env：见 §5（保持）。
- gson 编译期用 `com.google.gson`，打包前 **shade 到 `meow.gson`**（避免遮蔽 MC gson）。
- 换 jar ⇒ **`EXTRAS_VERSION` 递增**。

## 5. 行为面要点（重实现必须覆盖）
1. **目录模型**（属性派生）：`MEOWCRAFT_HOME`(home)、`MEOWCRAFT_GAME_DIR`(game)、`user.dir`(profile)、`java.library.path`(natives)；
   派生 `accounts/`、`versions/`、`libraries/`、`assets/`。
2. **accounts**：读 `MEOWCRAFT_HOME/accounts/<name>.json`（键 `accessToken/clientToken/profileId/username/xuid`）；
   xuid 非空 ⇒ accessToken 用常量离线令牌 `88888888-…`；null 归 `"0"`。
3. **version json**：读 `versions/<id>/<id>.json`；`inheritsFrom` 递归合并（子覆盖父：libraries 按 `group:artifact`、args.game 去重）。
4. **args**：宏表 15 键（`auth_*`/`assets_*`/`clientid`/`game_directory`/`user_properties`/`user_type`/`version_*`/`natives_directory`）；
   `${…}` 文本替换；`Demo.` 前缀 ⇒ 加 `--demo`；`arguments.game` 只取字符串（rules 忽略）；legacy `minecraftArguments` 兜底。
5. **classpath**：库 `downloads.artifact.path`（兜底按 name 派生）；**跳过** `com.mojang:text2speech`/`net.java.dev.jna:platform:`/`org.lwjgl`/`tv.twitch`；
   去重 + 跳过不存在文件 + 追加 `versions/<id>/<id>.jar`；`:` 连接。
6. **调用**：`System.getSystemClassLoader()` 转成我们的 loader → 注入 `java.class.path` 与生成 classpath → `loadClass(mainClass)` 反射 `main(String[])`。
7. **副作用**：`glfw.windowSize`（来自 `cacio.managed.screensize`）；`appdir=./spiral`、`resource_dir=./spiral/rsrc`；
   log4j 配置选择（`security/log4j-rce-patch-1.12/1.7.xml` 或 `<game>/<id>`）；~~Forge splash `enabled=false`（除非 `pojav.internal.keepForgeSplash`）~~ **★2026-09-29 该策略已整体删除**（原因 + 原地留档见 `Harmomeow-Craft-Launcher/tools/meow-launcher/src/meow/launcher/MeowLauncher.java` 与 [`已知限制与待解.md`](../00-current/已知限制与待解.md) C11：Pojav 血统、在实例隔离布局下从未生效、写游戏目录违反兼容铁律、HMCL 也不这么做）；**真正的问题已由 LWJGL2 shim 尊重 `share` 实参解决**，并进一步由 gl4es「每 EGL 上下文隔离 glstate」修掉其原生崩溃 ⇒ 共享上下文现**默认允许**（`MEOW_ALLOW_SHARED_CTX` 为**显式退出**开关，见 [`运行时环境变量.md`](../00-current/运行时环境变量.md) §1）；
   `options.txt` 写 `fullscreen=false`/`overrideWidth/Height` + 默认 `mipmapLevels=0/particles=1/renderDistance=2/simulationDistance=5`；
   崩溃 → stderr + `exit(0)`；只用 `System.out/err`（桥转 hilog）。

## 6. 文件规划（自研，~12–15 源）
```
meow/launcher/
  MeowLauncher.java     # main + launchMinecraft 编排（§5.1/3/7）
  MeowClassLoader.java  # URLClassLoader 子类（§4 契约）
  GameDirs.java         # 目录模型（§5.1）
  Account.java          # 账号 DTO + load（§5.2）
  VersionJson.java      # 版本 DTO（含 DependentLibrary）
  VersionLoader.java    # 读 + inheritsFrom 合并（§5.3）
  ArgBuilder.java       # 宏替换 + 参数拼装（§5.4）
  ClasspathBuilder.java # 库→classpath + 跳过表（§5.5）
  McOptions.java        # options.txt（§5.7）
  Log4jConfig.java      # log4j 配置选择（§5.7）
  ForgeSplash.java      # splash 开关（§5.7）
  CrashSink.java        # 未捕获异常 → stderr + exit0（§5.7）
com/mojang/text2speech/ # clean-room 兼容桩：Narrator(interface) + NarratorDummy（MC 调 getNarrator()）
android/util/           # vendored AOSP（Apache-2.0）：ArrayMap/MapCollections/ContainerHelpers/EmptyArray/Objects
```

## 7. 构建与部署
- `javac --release 17 -g:none`，CP = `gson-2.13.1`（Maven Central，下载）；AOSP `android/util` 随源编译。
- 确定性打包 `tools/oshi/pack_jar.py`；shade `tools/relocate_gson.py`（`com.google.gson`→`meow.gson`）。
- finalize：替换 `meowcraft_extras.tar.gz` 内 `launcher.jar` + **bump `EXTRAS_VERSION`** → build/run 实机回归。
- 工具落 `tools/meow-launcher/`（仿 `tools/launcher/`，脚本参数化；javac 由用户跑）。

## 8. 风险 / 开放点
1. **类加载器契约**是硬绑定（JVM 起 + 转型）；构造函数形状不能错。
2. `BUNDLE_PATH` 未设 ⇒ 原实现有 `null/...` 路径（无害）；净室要**显式处理**（缺失即跳过）。
3. JNA/asm 版本改写：现路径由 staging 的 oshi-overrides + MC 自带承担；净室**先不做**该改写，只保留跳过表（回归验证）。
4. MC 1.17–1.21.x 版本面：版本 JSON `inheritsFrom`/`arguments` 差异 — 用真实版本回归（1.17.x / 1.19.4 / 1.21.10）。
5. gson shade 必须成功，否则遮蔽 MC gson（历史坑）。
6. 合法性：`com.mojang.text2speech` 只实现 MC 调用的接口面（由 MC 调用契约决定），非抄 Pojav 桩。

## 9. 里程碑
- [x] 契约/行为卷宗（2 agent）
- [x] 设计档（本文）
- [x] 自研源（12 源/20 类）+ 构建脚本（`tools/meow-launcher/`）
- [x] 用户 javac → finalize（换 tar + shade）→ 部署
- [x] 实机回归 **1.21.10 可玩**（日志证 main=`meow.launcher.MeowLauncher`、loader=`meow.launcher.MeowClassLoader`、无 `net.kdt`）；后续战役进一步覆盖 **1.6.x–26.3 全窗口**（见 [`../00-current/现状基线.md`](../00-current/现状基线.md) §5 关键定论第 8 条）
- [x] digest v15 + 供应链（launcher.jar：源码级且**去 GPL**）+ 记忆归档

## 10. 达成
**launcher.jar 现为完全自研、可脚本复现、无第三方启动器血统（去 GPL/Pojav/HMCL）。** 旧 `tools/launcher/`（PojavLauncher_iOS 派生）降为 legacy/参照。
产物（**该文撰写时基线** digest v25；**现役值以 [`assets-digests.txt`](../30-supply-chain/assets-digests.txt) 为准**）：`launcher.jar`(shaded) `71f1deab…`（20 类）；`meowcraft_extras.tar.gz` `b76f45f7…`（3 jar = lwjgl-3.4.3 + launcher + gson）；令牌 `EXTRAS_VERSION=20260915-lwjgl-tagname`（v25；launcher.jar 自 v23 起：离线 UUID 派生 + userType=msa）。**2026-09-16（v26）**：两个 jar 由脚本重建并去掉不实的 `Multi-Release`（详见同处 digest 记录与 `tools/README.md`），上述值已过期。
