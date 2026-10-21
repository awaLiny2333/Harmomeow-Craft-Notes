# launcher.jar 自编重建 — 实操指南（2026-09-10）

> 已归档（2026-10-02；描述 Pojav 派生的 `launcher.jar` 构建链，已被净室 `meow.launcher` 取代、且 `launcher.jar` 随方案 A 退役 ⇒ 双重过时；现役口径见 [`现状基线.md`](../00-current/现状基线.md) §3 与 [`工程与规范.md`](../00-current/工程与规范.md)）。
> `launcher.jar` 曾由 [`launcher净室-设计.md`](launcher净室-设计.md) + `tools/meow-launcher/` 生产（自研、**无 GPL/Pojav/HMCL**）。
> 本文保留为 **Pojav 派生版的历史记录与参照**；`tools/launcher/` 降为 legacy。
> 正文中的 `POJAV_*`/`pojav*`/`net.kdt.*` 均为旧名（现为 `MEOWCRAFT_*`/`meow*`/`meow.launcher.*`），仅供考古，勿作现状引用。

> 目标：把随包 `launcher.jar`（早期外部件、无源码的半黑箱）打成**源码级自编、可复现、鸿蒙化**的产物。
> 结论：**可行**。真身 = **PojavLauncher_iOS `JavaApp/src/launcher` @ `1eeab5c1ee6f80991e09cc411054419374852cff`**
> （GPL-3.0）+ HOML 鸿蒙 deltas（`bridge/ArkUIKit`、`Server_Ip` 快连等）。
> 源码已 clone：`ref/PojavLauncher_iOS`（HEAD 即钉死提交）。4 个调研 agent 报告留档：
> `stuffs/research/homl/glue/REPORT.md`（glue 逆向）、`stuffs/research/launcher_build/REPORT.md`（依赖/构建）、
> 另两份见会话（Amethyst 映射 / 集成契约，核心结论摘要于 §3/§5）。

## 0. 一句话

```
ref/PojavLauncher_iOS/JavaApp/src/launcher  ← 上游（35 .java，全齐）
   + HOML deltas（ArkUIKit→MeowUIKit、PojavLauncher/Tools 小改）
   + android/util + text2speech stubs + HMCL ServerAddress
   → javac --release 17 + pack_jar.py + relocate_gson.py
   → tools/launcher/ 产物 launcher.jar（逐字节可复现）
```

## 1. 血统判定（别再找 Amethyst 当主源）

| 事实 | 依据 |
|---|---|
| launcher.jar = **PojavLauncher_iOS headless launcher**（Java 17，major 61），**不是** Amethyst v3 | Amethyst 无 `PojavLauncher`/`PojavClassLoader`（直跑 manifest main + MioLibPatcher）；iOS 树有 |
| 类结构逐一对上 iOS `JavaApp/src/launcher` | 35 文件覆盖 jar 全部 net.kdt 类（除 HOML 私有 bridge） |
| Amethyst 仅作**参考**（android/util AOSP 拷贝、jre_lwjgl3glfw GLFW ABI） | Agent 1 映射 |

## 2. 源码清单（ref/PojavLauncher_iOS/JavaApp/src/launcher，35 .java）

- `net/kdt/pojavlaunch/`：`PojavLauncher` `PojavClassLoader` `Tools` `JMinecraftVersionList`
  `JAssetInfo` `JAssets` `JVersion` `LWJGLGLFWKeycode`
- `net/kdt/pojavlaunch/{uikit,utils,value,value/launcherprofiles}/…`：`UIKit`/`UIKitCallback`、
  `JSONUtils`、`MCOptionUtils`、`MinecraftAccount`/`DependentLibrary`/`ForgeInstallProfile`/
  `MinecraftClientInfo`/`MinecraftLibraryArtifact`、`launcherprofiles/*`(7)
- `android/util/`（AOSP Apache-2.0）：`ArrayMap` 等 5（**不能丢**：HOML `lwjgl.jar` 的
  `GLFW.mGLFWWindowMap` 是 `ArrayMap`，仅换 `Tools` 侧不够）
- `com/mojang/text2speech/`（iOS no-op stubs，GPL-3.0）：`Narrator` 系 6 —— **不能丢**：
  MC 运行时调 `Narrator.getNarrator()`，`Tools.preProcessLibraries` 已 `_skip` 真实 text2speech
- 缺的：`net/kdt/pojavlaunch/bridge/ArkUIKit` + `UIKitCallback`（**HOML 私有**，需自写 Meow 版）

## 3. HOML deltas（相对 iOS 上游要改什么，已逆向确认）

| 文件 | iOS 原样 | HOML 版改动 | Meowcraft 版（我们要写） |
|---|---|---|---|
| `PojavLauncher.java` | `uikit.UIKit`、macOS(eawt/字体)块、无 cacio 门 | import `bridge.ArkUIKit`；删 macOS 块；cacio 门 `java.specification.version<=21`；log4j 选 security 补丁 | 照 HOML 语义重写；崩溃处理接 Meow 端 |
| `Tools.java` | 无 `Server_Ip` | `getMinecraftArgs` 加 `Server_Ip`→`--server/--port/--quickPlayMultiplayer`（HMCL `ServerAddress`） | 保留（或去掉快连） |
| `bridge/ArkUIKit` | 无（iOS 用 `uikit/UIKit`） | `System.loadLibrary("homl_bridge")` + native `ShowCrashMessage`/`updateMCGuiScale` | **自写 `MeowUIKit`**：只保留崩溃 sink，去掉 homl_bridge |
| `PojavClassLoader` | iOS 已有（URLClassLoader + addURL 追 java.class.path） | 基本一致 | **直接用上游**，勿改 |
| `uikit/UIKit` | iOS | jar 里是死代码 | 不编 |

> 契约（反向恒定，勿动）：main 类 `net.kdt.pojavlaunch.PojavLauncher`、`main(String[])` +
> `launchMinecraft(String[])`；argv `[player, versionId]`；`-Djava.system.class.loader=…
> .PojavClassLoader`（须 `(ClassLoader)` 构造）；`Tools.launchMinecraft` → `loadClass(mainClass)`
> 反射 `main`；读（旧名）`POJAV_HOME/POJAV_GAME_DIR/user.dir/cacio.managed.screensize/Server_Ip/
> java.library.path`。完整清单见会话 Agent 3 报告。

## 4. 鸿蒙化规则（像 HOML 一样保证 OHOS 兼容）

1. **零 Android API**：iOS 树本就 headless（无 Activity/Context）；扫掉残留 `android.*` 只留 `android/util`（AOSP 件，纯 Java）。
2. **路径全来自系统属性**：`BUNDLE_PATH`/`POJAV_HOME`/`POJAV_GAME_DIR`/`user.dir`（`POJAV_*` 为旧名）派生目录（勿硬编码 `/games/...`）。
3. **native 面**：不 `System.loadLibrary("homl_bridge")`；崩溃上报走我们的 ArkTS（或 native `libmeowjrebridge` 回传）。
4. **系统类加载器契约**是 JVM 硬性要求：`PojavClassLoader` 的 `(ClassLoader)` 构造 + URLClassLoader 必须原样。
5. `os.name=Linux`（走 `-D`，由 ArkTS 传，launcher 不改）；cacio/CTC 只在 java≤21 时探测（无害）。
6. 打印用 `System.out`/`System.err`（桥已接 hilog），不引 `android.util.Log`。

## 5. MUST-preserve 契约清单（摘自 Agent 3，部署不变即可沿用）

见 `notes/00-current/` 与本会话 Agent 3；要点：
- `LaunchContract.ets` 的 `POJAV_MAIN_CLASS`/`POJAV_CLASS_LOADER`（旧名）名字不变 → 新 jar 同名即兼容。
- 若源码用 `com.google.gson` 编译 → **必须重跑 `relocate_gson.py`** 打回 `meow.gson`（避免遮蔽 MC gson）。
- `EXTRAS_VERSION` 每次换 jar 递增（staging 缓存失效）。
- `BUNDLE_PATH` 当前未设 → `Tools.<clinit>` 的 `DIR_BUNDLE=null`（现无害，因 lwjgl 已在 `-cp`）；自编时保持 `generateLibClasspath` 容忍 null 或显式传。

## 6. 依赖与构建配方（照 oshi，脚本化）

- 编译 classpath：`gson-2.13.1.jar`（Maven Central；MC libs 只有 2.13.2，**锁 2.13.1** 对齐现状）
  + HOML `lwjgl.jar`（`meowcraft_extras.tar.gz` 解出，含自定义 GLFW ABI；只读；历史外部件）
  + `org.jetbrains:annotations:26.1.0`（HMCL `ServerAddress` 用）
- `javac --release 17 -g:none`（JRE 25；勿用 8）
- 确定性打包：`tools/oshi/pack_jar.py`；gson shade：`tools/relocate_gson.py`
- 来源：`ref/PojavLauncher_iOS`（钉死 commit）worktree → patch → javac → pack

## 7. 风险 / 决策点

1. **GPL-3.0**：launcher.jar 合体为 GPL-3.0（Pojav iOS + HMCL `ServerAddress`）。`ServerAddress` ~100 行，
   可 clean-room 去掉 HMCL 依赖（或用我们自己实现同 FQCN）→ 只剩 Pojav GPL。
2. **gson 2.13.1 vs 2.13.2**：锁 2.13.1 与现状 byte 对齐；换 2.13.2 也行但需重跑 shade + 全量回归。
3. **`android/util` 与 lwjgl.jar 耦合**：本轮不动 lwjgl.jar（单独课题）；重建 launcher 时 `-cp` 含它即可。
4. **agent 无 JVM**：`javac` 由用户在可执行 shell 跑（`sh tools/launcher/rebuild_for_meowcraft.sh`）。

## 8. 里程碑

- [x] 调研（4 agent）+ 血统判定 + 源码获取（`ref/PojavLauncher_iOS` @ 钉死 commit）
- [x] `tools/launcher/` 构建脚本 + deltas 补丁（`0001-pojavlauncher-meow` / `0002-tools-meow` / `0003-minecraftaccount-meow`）+ `MeowUIKit`
- [x] 用户 javac 出 `launcher.jar` → relocate_gson → 替换 rawfile tar → **实机 1.21.10 可玩**
- [x] **减脂**：35→23 源编译 / jar 41 类；编译 CP = gson only（build 脚本内置排除）
- [x] **逐字节可复现实证**：拼装 jar ≡ `sh rebuild+finalize` 产物（sha 全等）
- [x] digest v11 入库 + 供应链分级升级（launcher.jar：外部历史件 → 源码级）
- 遗留：`android/util` 随包保留（lwjgl.jar GLFW 运行时用）；待 lwjgl 重建换 HashMap 后连根拔；
  净室 `meow.launcher`（~1000 LOC）为候选，见 [`../90-archive/自研收编-总览与交接.md`](../90-archive/自研收编-总览与交接.md)。

> 踩坑实录（勿重蹈）：① 补丁重生成会丢 hunk（0002 曾丢 getenv→getProperty → `null/accounts` 崩），
> 改后须 pristine 全量 apply 验证；② 不清 `out/classes` → 旧类混包；③ 换 jar 必升 `EXTRAS_VERSION`。

## 附录 A：旧 `tools/launcher/`（Pojav 派生构建链，2026-09-10 归档后删除）

> 被净室 `tools/meow-launcher/` 取代后**已从仓库删除**；本附录保留结构与 delta 要点（原目录 10 文件）。

```
tools/launcher/
├── README.md
├── rebuild_for_meowcraft.sh        # ref/PojavLauncher_iOS @1eeab5c1 worktree → patches → overlay → javac → pack
├── build_launcher_meow.sh          # javac + pack（CP=gson；内置死源排除）
├── finalize_for_meowcraft.sh       # pre-shade tar + relocate_gson.py + 换 rawfile tar
└── deltas/
    ├── README.md
    ├── 0001-pojavlauncher-meow.patch     (148 行)
    ├── 0002-tools-meow.patch             (29 行)
    ├── 0003-minecraftaccount-meow.patch  (17 行)
    └── overlay/net/kdt/pojavlaunch/bridge/{MeowUIKit,UIKitCallback}.java
```

**deltas 要点（相对 PojavLauncher_iOS 上游）**
- `0001` PojavLauncher：删 macOS(eawt/字体) 块；崩溃 → `bridge.MeowUIKit` + `exit(0)`；cacio 门 `java.specification.version<=21`；`-jar` 走 MeowUIKit；删 `libMoltenVK.dylib`；修 forge splash replace bug；log4j 走 `DIR_BUNDLE/security/…`。
- `0002` Tools：`DIR_BUNDLE/DIR_GAME_HOME/DIR_GAME_NEW/DIR_APP_DATA` 由 `getenv` → **`System.getProperty`**（OHOS 以 `-D` 传）；删无用 `uikit.UIKit` import。
- `0003` MinecraftAccount：**删 `System.loadLibrary("PojavAccountJNI")`**（iOS 钥匙串，OHOS `UnsatisfiedLinkError`）；`getAccessTokenFromKeychain` → 常量 `88888888-8888-8888-8888-888888888888`（HOML 同款）。
- `overlay/MeowUIKit`：纯 Java 替代 HOML `bridge/ArkUIKit`（去 `libhoml_bridge`）：崩溃 → stderr；`-jar` 反射。`UIKitCallback` 接口占位。

**决策**：`Server_Ip` 快连不做（去 HMCL `ServerAddress` GPL-3.0）；`uikit/UIKit` 死类不编；gson 编后必 `relocate_gson.py` 打回 `meow.gson`。
（注：`tools/launcher/pack_jar.py` 曾指向缺失文件 → 删除前该目录已不可完整运行。）
