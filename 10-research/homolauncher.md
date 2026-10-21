> 说明（2026-09-15）：HOML 血统已全部清除（见 [`../00-current/现状基线.md`](../00-current/现状基线.md) §3/§5）；本文是 HOML 的主要集中档案，仅作外部学习参考（跨启动器对照另见 [`pojav系-启动渲染对照.md`](pojav系-启动渲染对照.md)）。

# HomoLauncher (HOML) 深度分析

> 位置：`ref/HomoLauncher`
> 分支：**`master`（真正资产）**，`main` 分支几乎为空（只有 README + 3 个 commit）。
> 定位：Minecraft: Java Edition 启动器，适用于 HarmonyOS NEXT，目前处于"早期预览"阶段。

## 1. 仓库结构（master 分支）

```
HomoLauncher/
├── AppScope/                  # 应用签名/配置
├── entry/                     # 主模块（ArkTS 源码 + 资源）
├── libs/
│   ├── jre17/                 # JRE 17 HSP 模块（arm64-v8a 全套 .so + jre17-ohos-arm64.tar.xz）
│   ├── jre25/                 # JRE 25 HSP 模块（同上）
│   ├── lwjgl3/                # LWJGL3 渲染库模块（liblwjgl_opengles.so 等）
│   └── launcher.har           # 预打包的 launcher HAR（5.4MB）
├── xb_components/             # （submodule，未克隆，空）第三方 UI 组件库
├── build-profile.json5        # 工程配置（targetSdk 6.0.2(22)）
└── oh-package.json5           # 依赖 @mysoft/archive
```

**模块关系（build-profile.json5）**：
- `entry` 依赖 `jre17`、`jre25`（dynamicDependencies）+ `xb_components`
- `lwjgl3`、`jre17`、`jre25` 都是独立的 library 模块

## 2. 核心目录结构（entry/src/main/ets）

```
ets/
├── auth/                     # 微软账户鉴权
│   ├── MicrosoftService.ets  # Xbox Live / XSTS / Minecraft 三级 OAuth
│   ├── OAuth.ets             # OAuth 设备码流程
│   └── OAuthServer.ets       # 本地回调服务器
├── common/                   # 常量、事件、工具
├── components/               # 通用组件（列表等）
├── core/                     # ★核心逻辑★
│   ├── JVMLauncher.ets       # JVM 启动器（参数拼接 + 环境变量 + dl_open 渲染驱动）
│   ├── HOMLBridge.ets        # 与 JVM 交互的原生桥接口
│   ├── HomlViewModel.ets     # 主视图模型（版本加载/登录/启动）
│   ├── GameViewModel.ets     # 手柄/输入事件处理
│   ├── NativeInput.ets       # 键鼠输入桥
│   ├── FCLKeycode.ets        # FCL 键盘码映射
│   ├── LWJGLKeycode.ets / LWJGLGLFWKeycode.ets  # 键码转换
├── entryability/             # EntryAbility（窗口/断点/避让）
├── model/                    # 数据模型（MinecraftVersion、VersionSetting、GameProfile...）
├── pages/                    # 页面（Index/Home/Game/Settings）
└── view/                     # 子视图（Versions/VersionDetail/About/Logs...）
```

## 3. JVM 启动链路（★最核心，`core/JVMLauncher.ets`）

### 3.1 JRE 加载（`switchJre`）

```ts
// 检查 HSP 是否安装 → 解压 jre25-ohos-arm64.tar.xz → 动态 import HSP → 拿到 bridge
if (!hasJreXz(context, jre)) { 提示安装 hsp }
await installJre(context, jre)          // 解压到 filesDir
let ns: ESObject = await import(jre);   // import "jre25" 动态加载 HSP
this.bridge = ns.homl_bridge            // 拿到原生桥
```

**关键点**：JRE 被打包成独立的 HSP（Harmony Shared Package），运行时通过 `import(jre)` 动态加载，
其导出的 `homl_bridge` 就是 C++ 侧实现的原生桥（`HOMLBridge` 接口）。

### 3.2 启动参数拼接（`launch` / `getMinecraftJVMArgs`）

`launch()` 构造一串 JVM 参数（`overridableArguments`），核心内容包括：

- **OS 伪装**：`-Dos.name=Linux`、`-Dos.version=harmonyos`、`-Dcpu.name=harmonyos`（过 1.21.10 的 OS rules）
- **路径类**：`-Djava.home`、`-DPOJAV_HOME`、`-DPOJAV_GAME_DIR`、`-Duser.home`、`-DBUNDLE_PATH`
- **原生库**：`-Djna.boot.library.path`、`-Djna.nosys=false`
- **LWJGL 渲染**（见渲染章节）：
  - `-Dorg.lwjgl.opengl.libname=${renderer}`（关键：指定加载哪个渲染 .so）
  - `-Dglfwstub.windowWidth/Height`（窗口尺寸）
  - `-Dorg.lwjgl.vulkan.libname=libvulkan.so`
- **AWT/Caciocavallo**（JRE8 以上）：
  - `-Dawt.toolkit=com.github.caciocavallosilano.cacio.ctc.CTCToolkit`
  - 一堆 `--add-exports` / `--add-opens` 给 cacio 注入桌面模块
  - `-Xbootclasspath/a:.../caciocavallo17/*.jar`
- **安全**：log4j RCE patch（`-Dlog4j2.formatMsgNoLookups=true`）、`java_sandbox.policy`
- **agent**：`-javaagent:patchjna_agent.jar`、`-javaagent:arc_dns_injector.jar=23.95.137.176`
- **主入口**：`net.kdt.pojavlaunch.PojavLauncher`（继承 Pojav 的启动类路径）

最终 `bridge.jvm_Launcher(overridableArguments)` 把参数交给原生侧启动 JVM。

### 3.3 环境变量与渲染驱动加载（`initEnv`）

```ts
// 根据 renderer 设置 POJAV_RENDERER
gl4es        → "opengles3"
mobileglues  → "opengles_mobileglues"
glv4         → "openglv4"
setenv("LIBGL_USE_MC_COLOR","1"); setenv("LIBGL_GL","31"); setenv("LIBGL_ES","3");
setenv("OHOS_DL_DIR", java_dl_dir); setenv("OHOS_JAVA_HOME", java_home);
setenv("LD_LIBRARY_PATH", java_dl_dir); setenv("jli_path", ...libjli.so);
let ret = this.bridge.dl_open(glibName);   // ★dl_open 动态加载渲染 .so
```

**渲染 .so 三选一（`model/VersionSetting.ets` 的 `RENDERER_LIB`）**：
- `libng_gl4es.so`（NG-GL4ES / Krypton 包装）
- `libmobileglues.so`（MobileGlues，**默认**）
- `libGLv4.so`（**仅鸿蒙 PC 或平板可用**——代码里 `dl_open` 失败时 toast 提示"当前图形驱动仅鸿蒙pc或平板可用"）

## 4. 原生桥接口（`core/HOMLBridge.ets`）

ArkTS 侧与 JVM/原生侧通信的接口契约：

```ts
export interface HOMLBridge {
  jvm_Launcher(args: string[]): number;      // 启动 JVM
  surfaceChanged(id,w,h): void;              // XComponent surface
  send_mouse_button(button,action,mods): void;
  send_cursor_pos(x,y): void;
  send_screen_size(w,h): void;
  send_key(key,scancode,action,mods): void;
  send_char_mods(key,mods): void; send_char(key): void;
  send_scroll(x,y): void;
  set_env(key,value): void;                  // 设置环境变量
  dl_open(key): boolean;                     // ★dlopen 渲染驱动
  on_cursor_enabled(cb): void;  // 光标抓取状态回调
  on_crash_message(cb): void; on_log_message(cb): void;
  on_nominal_exit(cb): void; accessClipboard(cb): void;
}
```

## 5. 游戏画面与输入（`pages/Game.ets` + `core/NativeInput.ets`）

- **渲染载体**：`XComponent({ type: XComponentType.TEXTURE })`，`onSurfaceCreated` 时调用
  `bridge.surfaceChanged(surfaceId,...)` 把 surface id 传给原生侧作为 EGL 渲染目标。
- **横屏**：进入游戏页把 orientation 设为 `LANDSCAPE`，退出恢复。
- **输入桥 `NativeInput`**：
  - 鼠标/键盘事件通过 `toGLFW(keycode)` 转成 GLFW 键码后 `bridge.send_key(...)`。
  - 光标抓取（grab）通过 `on_cursor_enabled` 回调控制虚拟鼠标（`Xb_GameMenuState.cursorEnabled`）。
  - 手柄（虚拟按键）走 `Xb_GameControllerViewModel` + 自定义 controller 布局（resfile/controllers/*.json）。

## 6. 账户鉴权（`auth/MicrosoftService.ets`）

完整实现微软 OAuth → Xbox Live → XSTS → Minecraft 四级链路：

1. `OAuth.MICROSOFT.authenticate(GrantFlow.DEVICE,...)` 设备码流程拿到 live access/refresh token
2. `https://user.auth.xboxlive.com/user/authenticate`（XBL 认证，拿 XBL token + uhs）
3. `https://xsts.auth.xboxlive.com/xsts/authorize`（XSTS 认证，拿 XSTS token）
4. `https://api.minecraftservices.com/authentication/login_with_xbox`（换取 MC access token）
5. `https://api.minecraftservices.com/entitlements/mcstore`（检查是否拥有 MC）
6. `https://api.minecraftservices.com/minecraft/profile`（拿 UUID + 皮肤）

结果存入 `MicrosoftSession`，`toAccount()` 转成 `MinecraftAccount` 并落盘到 `accounts/` 目录。

## 7. 版本管理（`core/HomlViewModel.ets` + `model/MinecraftVersion.ets`）

- **读取**：扫描 `homeDir + ".minecraft/versions/*/<id>.json"`，解析为标准 MC 版本 JSON 结构
  （`MinecraftVersion` 含 `arguments`/`libraries`/`assetIndex`/`logging` 等，且兼容 PCL 的 `clientVersion`、
  FCL 的 `patches[]`）。
- **导入**：`loadZip()` 选择 .zip → 解压 → `fixGameHome()` 递归（`findMinecraftDir`，深度 5）找
  `.minecraft/` 或 `versions/` 目录再搬移。
- **目录**：三种 home 类型（`HomeDirectoryType`）：Sandbox（filesDir）、Download（下载目录）、Custom（自定义）。
- **版本隔离**：`isolation` 开关决定运行目录是 `.minecraft/` 还是 `.minecraft/versions/<id>/`。
- **JVM 参数模板**：`getMinecraftJVMArgs()` 读取版本 JSON 里的 `arguments.jvm` 并按
  `classpath`/`library_directory`/`version_name`/`natives_directory` 等占位符替换。

## 8. 资源清单（resfile，运行时数据）

`entry/src/main/resources/resfile/` 下是与游戏运行有关的关键资源：

- game/versions.txt：受支持版本列表，列到 **1.21.10**。
- `app_runtime/caciocavallo*/`：Caciocavallo AWT 移植 jar（cacio-tta、cacio-ctc）
- `game/MioLaunchWrapper.jar`、`MioLibPatcher.jar`、`HMCLTransformerDiscoveryService-1.0.jar`：启动/补丁辅助
- `game/log4j2-1.7.xml`、`log4j2-1.12.xml`：日志配置
- `security/java_sandbox.policy`、`log4j-rce-patch-*.xml`、`pro-grade.jar`：安全
- `arc_dns_injector.jar`、`patchjna_agent.jar`、`jsr305.jar`、`gson-2.13.1.jar`：运行时依赖
- `microsof
t_auth.html`：微软登录页
- `map.json`：**FCL 版本的 Minecraft 混淆名反混淆映射**（各版本 vanilla/forge/fabric 的字段/方法名，
  用于按键注入等功能）
- `controllers/*.json`：虚拟手柄按键布局

## 9. 关键权限（module.json5）

```jsonc
"requestPermissions": [
  "ohos.permission.INTERNET",
  "ohos.permission.kernel.ALLOW_WRITABLE_CODE_MEMORY",  // ★JIT 可写代码内存
  "ohos.permission.LOCK_WINDOW_CURSOR",                  // 光标锁定
  "ohos.permission.FILE_ACCESS_PERSIST",
  "ohos.permission.NDK_START_SELF_UI_ABILITY"
]
```

`deviceTypes` 包含 `"2in1"`（二合一设备）与 car/tv/tablet/phone。

## 10. 已知限制与 TODO（来自源码注释）

- **AWT 目前不能工作**（`JVMLauncher.ets` 中 `//TODO awt 目前不能工作`，但代码仍预置了 cacio 全套）。
- `isJre8` 分支为空（JRE8 分支未完善，cacio 分流逻辑只写了 JRE8+ 分支）。
- 手柄 mods（Ctrl/Shift 等）在 `NativeInput.getCurrentMods()` 中被注释掉，统一返回 0。
- `xb_components` 是外部 submodule（未克隆），UI 强依赖该库（`Xb_*` 系列是第三方 HarmonyOS UI 库）。
- 键盘编码固定 `-Duser.language=zh`、`-Duser.country=CN`、时区 `Asia/Shanghai`。

## 11. 对"鸿蒙 PC"落地最值得抄的部分

1. **HSP 化 JRE**：把 `libjvm.so` 等整套 JRE 打包成 HSP 模块，运行时解压 + 动态 `import()` 加载
   —— 这是鸿蒙上内嵌 JVM 的关键手段。
2. **`dl_open(renderer)` + 环境变量**：动态选择渲染 .so 并设置 `POJAV_RENDERER` 的完整范式。
3. **`HOMLBridge` 接口契约**：ArkTS ↔ 原生 ↔ JVM 的通信面设计（输入/渲染/日志/剪贴板/退出）。
4. **XComponent TEXTURE + surfaceChanged**：把鸿蒙 surface 作为 EGL 渲染目标的标准做法。
5. **完整微软 OAuth 四级链路**：直接可复用。
