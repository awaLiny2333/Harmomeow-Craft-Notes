# 跨层精确时序（证据存档：launchJvm / 线程 / want / glguard）

> **本文为「证据存档」，不是现状** ⇒ 别当现状引用；行号是**记录时的现值**，会随重构失效（符号名才稳定）。
> 归属：`00-current/渲染链与迁移结论.md` 的证据层；结论层留在那里 + [`../../00-current/现状基线.md`](../../00-current/现状基线.md)。
> 记录口径：源码核实（`GameWindow.ets` / `GameLauncher.ets` / `JvmLauncher.ets` / `meowjrebridge.cpp` / `egl_gl.c` / `input_bridge.c` / `meowglguard.c`）。

## （1）`launchJvm` 精确先后

`GameWindow.injectAndLaunch`（`GameWindow.ets:159`）→ `launchGame`（`GameLauncher.ets:23`）→ `startJvm`
（`JvmLauncher.ets:65`）→ `craft.launchJvm(...)`（`JvmLauncher.ets:78`）。NAPI 收 8 参
（`meowjrebridge.cpp:117-191`）后**立即 spawn detached `std::thread` 并返回**（`:196`,`:459-460`）。
线程体内依次（均 `meowjrebridge.cpp`）：

1. **setenv**（顺序即代码顺序；全在预 dlopen 渲染器前）：

   | # | 变量 | 值/说明 | 行 |
   |---|---|---|---|
   | 1 | `LD_LIBRARY_PATH` | `自研libs:JRE el1 libs:javaHome/lib` | :205 |
   | 2 | `OHOS_JAVA_HOME` | `jreHome`（默认 `filesDir/meow-jres/meow_jre`） | :213 |
   | 3 | `OHOS_DL_DIR` | `jreLibsDir` | :215 |
   | 4 | `HOME` | `filesDir` | :229 |
   | 5 | `MEOWCRAFT_RENDERER` | `openglv4` / `gl4es` | :231 |
   | 6 | `MEOWCRAFT_GL_PROFILE` | `core` / `compat` | :232 |
   | 7 | `MEOWCRAFT_NATIVEDIR` | 自研 libs dir | :233 |
   | 8 | `NGG_DIR_PATH` | `<cache>/` | :234 |
   | 9 | `LIBGL_*`（仅 `gl4es`） | `LIBGL_GL=21`、`LIBGL_ES=2`、`LIBGL_NORMALIZE=1`、`LIBGL_NOINTOVLHACK=1`、`LIBGL_NOERROR=0`、`LIBGL_NOBANNER=1`、`LIBGL_SILENTSTUB=1` | :237-245 |
   | 10 | `ALSOFT_LOGLEVEL` | `0` | :246 |
   | 11 | `vblank_mode` | `0` | :250 |
   | 12 | `GALLIUM_THREAD` | 基值 `0`（上层 extra env 可置 1） | :256 |
   | 13 | `extraRenderEnv` 逐条 | `K=V`（`\n`/`;` 分隔），最后应用、可覆盖以上 | :259-284 |

2. 绑核/QoS：`meow_affinity_apply_current_thread()`（`MEOW_AFFINITY`）+ `meow_qos_apply_current_thread()`
   （`MEOW_QOS`）（:292-293）。
3. **预 dlopen 的唯一库 = `rendererSo`**（`RTLD_NOW|RTLD_GLOBAL`）：按名 `dlopen(rendererSo)`（:298），
   失败且名不含 `/` 再试 `libsDir + "/" + rendererSo`（:299-302）。现代 = `libmeowglguard.so`、
   ≤1.16/legacy = `libgl4es.so`（`LaunchDefaults.ets:36,:41`）。
4. guard 失效安全（仅 `rendererEnv=="openglv4"`）：若 glthread 开而 `dlsym(rendererSo,"meow_glguard_armed")()`
   ≠1 → 强制 `GALLIUM_THREAD=0`（:315-328）。
5. stdout/stderr → pipe；起 2 个 detached reader 线程（`jre_stderr`/`jre_stdout`，:335-371）。
6. `dlopen(<jreLibsDir>/libjli.so, RTLD_NOW|RTLD_GLOBAL)`（:393）→ `dlsym("JLI_Launch")`（:402）→
   自检 argv 的 `-Dorg.lwjgl.opengl.libname=` 必须 == `rendererSo`，否则中止（:416-428）。
7. `JLI_Launch(...)`（:444-447，阻塞到 JVM 退出）→ 返回后 `close(1/2)` → `usleep(200000)` → `_exit(code)`
   （:454-458）。老版本 JLI 内部 `exit()` 不返回；26.2+ 正常返回才走收尾（:450-453）。

**`libmeowcraftbridge.so` 何时载入**：**不在 `launchJvm` 预 dlopen**。`MeowCraftBridgeLib()` 惰性
`dlopen(SelfDir()+"/libmeowcraftbridge.so", RTLD_GLOBAL)`（:468），并顺带 `critical_set_stackqueue(1)`
（:479-480）——首次由 `setGameSurface`/`resizeGameSurface`/`requestGameWindowClose`/输入发送器触发。
实际启动中 surface 注入先于 JVM，故桥先载入。

## （2）线程归属

| 工作 | 线程 |
|---|---|
| `launchJvm` NAPI 本身 | ArkTS UI 线程（spawn 后立即返回；`:196`,`:460`） |
| setenv / 预 dlopen / `dlopen(libjli)` / `JLI_Launch` | **新建 detached `std::thread`**（`:196`,`:459`） |
| `setGameSurface` / `resizeGameSurface` NAPI | ArkTS UI 线程（同步 NAPI；`:490`,`:531`） |
| 输入生产者 `critical_send_*` | 任意 ArkTS/UI 线程（`input_bridge.c:13-19`） |
| 输入 pump 消费者 | **JVM 渲染线程**（MC `glfwPollEvents`→`meowPumpEvents`；桥不自建渲染线程；`input_bridge.c:10-19`、`egl_gl.c:13-16`） |
| 日志 reader ×2 | `launchJvm` 起的 detached 线程（`:370-371`） |

## （3）`setGameSurface` 与 `launchJvm` 的调用顺序

**同一 `injectAndLaunch` 回调内串行：surface 先、JVM 后**（非并行）。`GameWindow.ets`：
- `onSurfaceCreated` → `onSurfaceReady(sid,0,0)`（:40-43）→ `injectAndLaunch`：
  - surface：`import('meowjre')` → `setBridge`/`bindOverlay` → `setGameSurface(sid,1280,720)`（:170-187；
    w=h=0 走 `:186` 分支）。
  - **推迟 JVM**：`w<=0` 时挂 `setTimeout(..., LAUNCH_FALLBACK_MS)`（=1500，`Constants.ets:100`）并 `return`
    （:213-231）。
- `onSurfaceChanged`（真实尺寸）→ 再进 `injectAndLaunch`：先 `resizeGameSurface(sid, realW, realH)`
  （:179-182）→ 再 `launchGame`（:238）。
- **1.5s 兜底**只在 `w<=0` 分支（:219-230）：到点仍无尺寸则用默认 `WINDOW_DEFAULT_W/H` 直接 `launchGame`。
- **GLFW / SDL 无 ArkTS 层差异**：唯一 `injectAndLaunch`；native 侧两者都读 `meowSetSurfaceId` 写进
  `meow_environ->window` 的同一窗口。SDL3 ohos 驱动从共享 block 取窗：
  `Harmomeow-Craft-Launcher/tools/sdl/src/video/ohos/SDL_ohoswindow.c:38-54`（`OHOS_ResolveNativeWindow`）、
  `:199-217`（全屏请求写回同一 block）。[`../../20-design/render/SDL3桥接-设计.md`](../../20-design/render/SDL3桥接-设计.md)
  的「等首个 `onSurfaceChanged`」即上述通用 defer，非 SDL 专属。

## （4）`:game` 的 want 字段（完整表）

`want.parameters` 由 `WindowHolder.openGameWindow`（`WindowHolder.ets:42-51`）打包、`VersionLaunch.ets:69-75`
填值，仅 3 字段：

| 字段 | 类型 | 含义 | 写 | 读（`:game`） |
|---|---|---|---|---|
| `gameRoot` | string | `.minecraft` 根（存档/libraries/assets） | `VersionLaunch.ets:70` | `GameAbility.ets:42` → `setGameLaunchParams`（`GameLaunchParams.ets:21-25`）→ `GameWindow.ets:161` → `GameLauncher.launchGame` |
| `jsonPath` | string | 版本 json 绝对路径 | `VersionLaunch.ets:71` | `GameAbility.ets:43` → `GameLaunchParams.ets:23` → `GameWindow.ets:162,:194,:226,:238` |
| `versionId` | string | 实例名（目录名，**非** MC 版本号） | `VersionLaunch.ets:72` | `GameAbility.ets:44`、`:72`（窗口标题）→ `GameLaunchParams.ets:24` → `GameWindow.ets:161,:226,:238` |

- **几何经 `startAbility` 的 StartOptions，不经 want**（`WindowHolder.ets:53-63`）：`displayId=0`、
  `windowLeft/Top`（`WINDOW_DEFAULT_X/Y`）、`windowWidth/Height`（`WINDOW_DEFAULT_W/H`）、
  `supportWindowModes=[FLOATING,FULL_SCREEN]`（`LaunchDefaults.ets:7-10`）。
- **账户不经 want**：应用沙箱 `filesDir/meow-settings/accounts.json`（含 token）+ `app-settings.json` 的
  `selectedAccount`（`AccountsTools.ets`、`AppSettings.ets`；不使用 Preferences），
  游戏进程 `AccountsTools.writeAccountFile` 落 `<filesDir>/meow-home/accounts/<name>.json`
  （`GameLauncher.ets:61`）。其余运行选项**读应用沙箱文件**：全局设置读 `app-settings.json` 的 `global` 段（`readAppGlobalSettings(ctx)`）；
  逐版本设置读 `<gameRoot>/versions/<id>/.hmmcraft/instance-settings.json`
  （[`../../20-design/launch/实例设置存储-方案.md`](../../20-design/launch/实例设置存储-方案.md) §3）。
- `startAbility` 唯一调用点：`WindowHolder.ets:53`。

## （5）glguard 物理位置与转发链

- 物理件：`libs/meowcraftlib/src/main/cpp/meowcraftbridge/meowglguard.c`，随 `meowcraftlib` 静态并入
  `meowjre` HSP（`meowcraftlib` 同时带 `libmeowjrebridge.so` + `libmeowcraftbridge.so`）。
- 被指名：`RENDERER_LIB='libmeowglguard.so'`（`LaunchDefaults.ets:36`）经 `RendererPolicy.rendererForVersion`
  （`RendererPolicy.ets:70-85`）→ `-Dorg.lwjgl.opengl.libname=`（`MinecraftLauncher.ets:213`）= 桥预 dlopen 的
  `rendererSo`（`meowjrebridge.cpp:298`）。
- guard 取真 GL：`__attribute__((constructor)) meow_gl_guard_init()` 里
  `dlopen("libGLv4.so", RTLD_NOW|RTLD_GLOBAL)`（`meowglguard.c:255`），失败回退
  `dlopen("/system/lib64/ndk/libGLv4.so")`（`:257`）。
- 转发：导出 `glXGetProcAddress`/`glXGetProcAddressARB`（`:373-380`）→ `meow_gl_guard_resolve`：先调 libGLv4
  自己的 `glXGetProcAddress`（退 `ARB`、再退 `eglGetProcAddress`），再 `dlsym(g_realLib, name)`
  （`:265-271`,`:316-329`）；只对 8 个贴图上传入口返回 wrapper（`:332-355`）。
- 逐级次序 **guard → `libGLv4.so` → Zink → Vulkan**：前两跳由 guard 直接 `dlopen`/`dlsym` 证实
  （`:255`,`:327`）；**Zink→Vulkan 是系统 `libGLv4.so` 自身的实现**（设备 GL 画像：`Mesa 25.0.1` /
  renderer `zink Vulkan 1.2(Maleoon 916)`），出处见 [`../../00-current/版本支持边界.md`](../../00-current/版本支持边界.md)，
  非 guard 代码可证。
