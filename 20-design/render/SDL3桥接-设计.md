# SDL3 桥接方案（解锁 MC 26.3+）

> 状态：2026-09-10 调研/定稿；**2026-09-11 已落地 —— 26.3-rc-1 实机可玩（画面/键鼠/转视角/文本/全屏）**。
> 现支持窗口 = **MC 1.6.x – 26.3**（本文只覆盖 ≥26.3 的 SDL3 路径）。
> 关联：[`../../00-current/版本支持边界.md`](../../00-current/版本支持边界.md)「26.3-rc1」、
> [`../../90-archive/自研收编-总览与交接.md`](../../90-archive/自研收编-总览与交接.md) 候选 D、[`GLFW净室桥-设计.md`](GLFW净室桥-设计.md)。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 8 条](../../00-current/现状基线.md)。

## 0. 结论先行

- MC 26.3 把窗口/输入/GL 从 **GLFW 换成 SDL3**（绑定 `org.lwjgl.sdl`，移除 `org.lwjgl.glfw`）；
  同时引入后端层 `com.mojang.renderpearl.backend.{opengl,vulkan}`。
- **路线（用户拍板，2026-09-10）：真 SDL3 fork** —— 把 SDL3 编进 app（随包 `libSDL3.so`），自写 `ohos` 驱动。
  - ABI 钉死：LWJGL 官方 `libSDL3.so` 构建自 SDL `147a8ee3…` = **tag `release-3.4.14`** → 我们 pin **3.4.14**。
  - 备选（未采用）：净室 shim（复用 `meow_environ`/368 符号/83 实调）；理由与进展见 §6。
- MC 默认 **OpenGL 优先**（`DEFAULT → [Gl, Vulkan]`）：后端由启动器按「渲染后端」决定（选 Vulkan ⇒ 给 MC 附
  `--graphicsBackend vulkan`，Vulkan 路径失败时 MC 内部回退 GL）。见 [`Vulkan后端-实现与原理.md`](Vulkan后端-实现与原理.md) §4.5。

## 1. 证据（关键事实）

| 项 | 结论 | 出处 |
|---|---|---|
| MC 26.3 依赖 | 版本 json 无 `lwjgl-glfw`，增 `org.lwjgl:lwjgl-sdl:3.4.3`；LWJGL 3.4.3 / Java 25 | `stuffs/.minecraft/versions/26.3-rc-1/26.3-rc-1.json` |
| 崩溃 | `Loading library SDL` → `NoClassDefFoundError: org/lwjgl/sdl/SDL` | 用户日志 |
| LWJGL 加载 | `Library.loadNative(SDL.class,"org.lwjgl.sdl", mapLibraryNameBundled("SDL3"), true)` → `libSDL3.so`；可 `-Dorg.lwjgl.sdl.libname` 覆盖 | LWJGL 3.4.3 `sdl/src/generated/java` |
| 符号解析 | **按绑定类懒解析**：首次用到该类即全量解析其 `Functions`，缺一抛 `NullPointerException` | 同上 `APIUtil` |
| 必需导出 | MC 只触 17 个绑定类 → **并集 368 个**（无 optional）；其中 MC **实调 83** | 清单 `stuffs/research/sdl/sdl-required-symbols.txt` |
| SDL 本体 | 无 OHOS video/events/EGL/main；CMake 平台链无 final else（unknown → 无 core 后端） | `ref/SDL` |
| 后端选择 | `PreferredGraphicsApi{DEFAULT,OPENGL,VULKAN}`，默认 `DEFAULT`；`DEFAULT→[Gl,Vulkan]`，`VULKAN→[Vulkan,Gl]`；`options.txt: preferredGraphicsBackend=opengl`；启动参数 `--graphicsBackend opengl` | MC 26.3 jar |
| SDL 初始化 | `RenderSystem.initBackendSystem`：7×`SDL_SetAppMetadataProperty` → hints → `SDL_Init(0x20=VIDEO)`；hints 含 `SDL_IME_IMPLEMENTED_UI=composition`、`SDL_NO_SIGNAL_HANDLERS=1`、`SDL_MOUSE_FOCUS_CLICKTHROUGH=1`、`SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS=0`、`SDL_QUIT_ON_LAST_WINDOW_CLOSE=0`、`SDL_ENABLE_SCREEN_KEYBOARD=0` | 同上 |
| Vulkan | `Minecraft.<init>` 在 API==DEFAULT 时 `VulkanBackend.checkBackendAvailable()`（`SDL_Vulkan_LoadLibrary`+`GetVkGetInstanceProcAddr`+设备探测）；`SDL_Vulkan_CreateSurface` 仅真正选 Vulkan 时 | 同上 |
| 26.2 vs 26.3 | 26.2 全 `org/lwjgl/glfw`（0 SDL）；26.3 全 SDL（0 GLFW） | 两 jar 对比 |

## 2. 设计

### 2.1 组成
- **jar**：`lwjgl-3.4.3.jar` 增补 `org.lwjgl.sdl` 模块（stock Java，走既有 overlay/合并管线，见 `tools/lwjgl/README.md` §1）。
- **native**：新 **`libSDL3.so`（净室 shim）** → 落 `libs/meowlwjgls/libs/arm64-v8a/`，随包（fs-verity 要求，见 `tools/README.md` §4）。
- **加载名**：沿用 `bundledLibrary.nameMapper` 机制（与 core/opengl/stb/tinyfd 同），把 `SDL3` 映射到我们随包件名。
- **shim 内部**：`dlopen` 既有 `libmeowcraftbridge.so` 的 `meow*`/`critical_*` 符号 + **采纳 `meow_environ` 共享块**；
  GL proc-address 自己 `eglGetProcAddress`/`dlsym` 取（现有 C 桥不导出该 helper）。

### 2.2 符号策略（368 / 83）
- 自动生成 **368** 个导出符号：其中 **~83 个实现真实行为**（MC 实调），其余 **no-op / 默认返回**（仅被解析、不被调用）。
- 真实实现分组：
  - `SDLVideo`（窗口/GL/显示查询，40）
  - `SDLEvents`（`Poll/Pump/Flush/GetWindowFromEvent`，4）
  - `SDLKeyboard`/`SDLMouse`（键盘状态/键名/scancode、光标/相对模式，15）
  - `SDLClipboard`（2）、`SDLInit`（`Init/Quit/SetAppMetadataProperty`）、`SDLTimer`/`SDLPlatform`/`SDLPixels`/`SDLMisc`/`SDLError`/`SDLSurface`（用到 3 个）
  - `SDLLog`（`SetLogOutputFunction` → 接 MC `SdlDebug`）、`SDLMessageBox`（2）
  - `SDLVulkan`（7）：**探测失败降级**（LoadLibrary/GetVkGetInstanceProcAddr 返回失败/空）→ 落 GL。

### 2.3 输入 / 事件 / 线程
- 把既有输入链（`critical_send_*` + grab + IME）映射为 **SDL3 事件**（scancode/keycode、mouse motion/button/wheel、
  text input/editing、window/display），`SDL_PollEvent` 从 shim 内部队列出队；事件 struct **按 vendor 头填**。
- IME：MC 设 `SDL_IME_IMPLEMENTED_UI=composition` → 走 `SDL_StartTextInput/SetTextInputArea/ClearComposition`
  + `TEXT_EDITING`/`TEXT_INPUT` 事件；接既有 `onKeyPreIme` 通路（见 [`../input/输入-总览.md`](../input/输入-总览.md) §2.2）。
- 线程：MC 在自己的线程调 SDL_*；shim 与既有"UI=生产 / 渲染线程=消费+EGL"契约对齐。

### 2.4 窗口 / GL / 显示
- `SDL_CreateWindow`（flags 2=OPENGL）→ 复用既有 surface（surfaceId→`OHNativeWindow`）。
- `SDL_GL_CreateContext/MakeCurrent/SwapWindow/GetProcAddress/Set(Get)Attribute/SetSwapInterval/LoadLibrary` →
  走既有 EGL 上下文管理（`meowCreateContext/...`），属性请求松处理。
- 显示枚举合成 **单显示器**（尺寸=窗口、刷新=系统档位 60/90）；全屏走既有 `meowTakeFullscreenRequest` + ArkTS 轮询。

## 3. 分阶段计划（增量可验证）

| 阶段 | 内容 | 验证点 |
|---|---|---|
| **P0 接通** | jar 加 `lwjgl-sdl` 模块 + 368 符号骨架（stub）+ `libSDL3.so` 随包 + 名映射 | 26.3 不再 `NoClassDefFoundError`，跑到 `SDL_Init` |
| **P1 窗口+GL** | `CreateWindow`/GL 上下文/proc-address/显示查询 | 出画面（无输入） |
| **P2 事件+输入** | `Poll/Pump` + 键盘/mouse/text/IME | 可操作菜单、进世界 |
| **P3 打磨** | 显示/全屏/剪贴板/日志/MessageBox/Vulkan 降级/光标 | 1.21.10 与 26.2 回归 |
| **P4 收编** | `tools/sdl/` 脚本化 + 确定性 + 断言 + `EXTRAS_VERSION` | 逐字节可复现（≥3 次 `cmp`） |

## 4. 风险

- `SDL_Event` union / `SDL_DisplayMode` 等 **ABI 对齐**（用 vendor 头规避）；scancode/keycode 表。
- 线程/主线程语义、`SDL_PumpEvents` 调用时机。
- 显示枚举值供 MC 判断（分辨率/刷新/全屏模式）须自洽。
- `SDL_CreateSystemCursor`/`SetCursor` 等硬件光标在 OHOS 的落地（可退化软光标）。
- hvigor 扁平打包 / native 命名（世代号紧跟基名）/ `--modules` 出 HSP（见 `tools/README.md` §4、`现状基线.md` §5 关键定论第 10 条）。

## 5. 验证方式

- 每阶段：`check_cpp_files` → `devecocli build --modules entry meowjre` → `run` → **用户**导出 `.logs`（禁 agent 自抓）。
- 终态（2026-09-11 实测）：**26.3 可玩（GL 路径）**；26.1.2 / 26.2 / 1.21.10 **回归通过**。

## 6. 路线变更与进展（2026-09-10：改走真 SDL3 fork）

> §2/§3 为当初（shim）设计存档；实际按本节执行。

### 6.1 关键事实（取证）
- **ABI pin**：LWJGL `lwjgl-sdl:3.4.3` 官方 `libSDL3.so` ⇐ SDL 提交 `147a8ee3…` = `release-3.4.14`
  （`libSDL3.so.git` 标记 + `SDL_version.h`=3.4.14）。工作树 `ref/SDL-3.4.14`。
- LWJGL 加载 `mapLibraryNameBundled("SDL3")`→`libSDL3.so`（可 `-Dorg.lwjgl.sdl.libname` 覆盖）；函数按绑定类懒解析。
- MC 触 17 绑定类 → 需 **368** 符号（清单 `stuffs/research/sdl/sdl-required-symbols.txt`），实调 83；MC 默认 GL 优先。

### 6.2 P0（已达成，可复现）
- **OHOS→Linux 伪装工具链** `Harmomeow-Craft-Launcher/tools/sdl/sdl_ohos.toolchain.cmake`
  （OHOS SDK 设 `CMAKE_SYSTEM_NAME=OHOS` → CMake `UNIX` 假；包装后重标 Linux）。
- configure 需 `-DSDL_UNIX_CONSOLE_BUILD=ON`；**补丁**：`SDL_systhread.c` 的 `pthread_setcanceltype`
  加 `!defined(__OHOS__)`（OHOS 动态 libc 未导出）。
- `libSDL3.so` 构建成功（dummy/offscreen video）。

### 6.3 P1（`ohos` 驱动已编入）→ 已落地（2026-09-11 实机通过）
- `Harmomeow-Craft-Launcher/tools/sdl/src/video/ohos/{video,window,events,gl}`：外部 `OHNativeWindow`
  （读 `MEOWCRAFT_ENVIRON`→offset 0 `window`；尺寸 0x271dc/0x271e0）+ SDL EGL 路径；`PumpEvents` 暂 no-op。
- 补丁器 `patch_sdl_ohos.py`（幂等）：CMake `if(OHOS)` 分支、`SDL_build_config.h.cmake`、`SDL_video.c` bootstrap[]、
  `SDL_sysvideo.h`、`SDL_egl.c`（`libEGL.so`+桌面 `libGLv4.so`）、`eglplatform.h`（`EGLNativeWindowType=struct OHNativeWindow*`）。
- 构建脚本 `build_sdl_meow.sh`（通用）+ `rebuild_for_meowcraft.sh`（项目）。
- **结果**：`Video drivers: dummy offscreen ohos`；链接成功；`DT_NEEDED=libc.so`；1270 `SDL_*`；
  `stuffs/research/sdl/out/libSDL3.so`（sha `0925c24a…`）。

### 6.4 P0b（接线，2026-09-11 agent 侧已完成）
- `build_lwjgl_jar.sh`：LWJGL ≥3.4.x 自动增补 `lwjgl-sdl` 模块（+ sanity `org/lwjgl/sdl/SDL.class`）。
- `install_natives.sh --sdl <file>`：把我们的 `libSDL3.so` **不带后缀**随包（manifest tag `common`，类 tinyfd）；
  已安装 `libs/meowlwjgls/libs/arm64-v8a/libSDL3.so`（sha `0925c24a…`）。
- 命名：`MeowBundledNameMapper` 对 `SDL3` 透传 → `libSDL3.so`（**无需改映射器**）。
- `EXTRAS_VERSION` → `20260911-sdl3`。
- **已由用户重打** 3.4.3 jar（含 `lwjgl-sdl` 模块）
  `sh tools/lwjgl/build_lwjgl_jar.sh --version 3.4.3 --overlay tools/lwjgl/deltas/overlay --overlay tools/lwjgl/deltas/overlay-3.4.3`，
  再 `pack_extras.py`（3.3.3 从 base 复用）→ 清模块 build → `devecocli build --modules entry meowjre` → run。
- `--graphicsBackend opengl`：最终未加（MC 默认 GL 优先，实测稳定落 GL；无需改 launcher ArgBuilder）。

### 6.5 收尾核对 → **已落地（2026-09-11 实机通过）**
- **P1 实机**：✅ EGL/GL 上下文 + 外部窗语义打通（§7）。
- **P2**：✅ `PumpEvents` 读 meow 输入环 → 键鼠/text/IME 事件（§7.1）。
- **P3**：✅ 显示/全屏/剪贴板/日志/Vulkan 降级 + 回归（全屏已通，见 [`SDL3适配-复盘.md`](SDL3适配-复盘.md) §六）。

## 7. P2 输入：实机打通 + 坐标根因（2026-09-11）

### 7.1 输入无反应（根治）
- 现象：26.3 有画面/BGM 但键鼠全无反应（ArkTS 有 `meowSendKey`）。
- 根因：`input_bridge.c` 的 6 个生产者都以 `env->invoke{Key,MouseButton,Scroll,CursorPos,Char} == NULL` 就 `return` ——**只在 GLFW thunk 已注册时才入环**；26.3 无 GLFW stub → **每次输入被静默丢弃**。
- 修：无 thunk 时**回落到输入环**（`if (isUseStackQueueCall || invokeX == NULL) ring else invokeX`），≤26.2 路径不变。
- SDL 侧：`OHOS_PumpEvents` drain 该环 → `SDL_SendKeyboardKey/MouseMotion/MouseButton/MouseWheel/KeyboardText`（GLFW→SDL scancode 全表映射）。

### 7.2 鼠标垂直偏移（★ 真根因，务必保留）
- 现象：hover/点击**都**随 y 偏移（≈ +20px@y260、+40px@y455，底面 56px 够不到），**与窗口顶栏相关、resize 后变化**；GLFW 路径（≤26.2）**无**此问题。
- 根因：MC 鼠标映射 `getScaledYPos = y × guiScaledHeight / **getScreenHeight()**`；26.3 的 `Window.height` **取自启动参数 `--height`**，且**只有 `SDL_EVENT_WINDOW_RESIZED` 会更新它**。我们用 `GameLauncher` **硬编码** `width/height = WINDOW_DEFAULT (1280×720)` → `Window.height=720`，而真实客户区/framebuffer 是 **664**（顶栏占 56）→ 比例错 720/664，底面需 raw>664 → 够不到。
- **GLFW 路径为何没事**：我们的 stub 会 `internalWindowSizeChanged(664)` → `Window.onResize(664)` 把 `Window.height` 刷成真实值；SDL 路径没有任何东西推这个事件。
- 修（**保留顶栏/窗口模式**）：
  1. **启动参数用真实客户区尺寸**：`GameWindow` 等首个 `onSurfaceChanged`（拿到 664）再启动；`launchGame(ctx, …, w, h)` → `glfwstub.*`/`cacio.managed.screensize` 用 664。⇒ MC `Window.height` = 664 = framebuffer。
  2. **`OHOS_SyncSurfaceSize` 按序发事件**：在改 `window->w` **之前** `SDL_SendWindowEvent(RESIZED, …)`（SDL 遇到"尺寸与 `window->w` 相等"会**丢弃** → 之前静默无效），并同时发 `PIXEL_SIZE_CHANGED`。⇒ 运行时 resize 也同步。
- ✗ 走过的弯路（勿重蹈）：给 y 加常量 56 / 换 `sendAbsCursor` / 关 native filter —— 都治标。**关 filter 还导致"鼠标采样率恒 0"**（`meow_rate_tick` 只在 filter 与 grab overlay 里 tick）。

### 7.3 文本乱码（§8 已归因并修复）
- **文本乱码**：按一个键出现 `a<?>][`（`<?>`=U+FFFD）且疑似重复。我们发出的码点是干净的（97/110/30340）。**根因已在 §8.1 定位**（`SDL_UCS4ToUTF8` 未 NUL 终止 + `MeowSendChar` 双发 `TEXT_INPUT`）并修复，**§8.3 实机验证无乱码**。

## 8. 理论研究结论：文本乱码 + 鼠标锁定（2026-09-11，3 子 agent，纯静态）

> 报告全文（工作区产物）：`stuffs/research/sdl/reports/{text-input-mc263,mouse-grab-mc263,sdl-ohos-driver-contract}.md`。
> 以下为结论层；**已改代码并实机验证**（2026-09-11，见 §8.3 清单；改动落 `tools/sdl/src/video/ohos/`）。

### 8.1 文本乱码 —— 两个 bug 叠加（均经源码/反汇编核实）
1. **未 NUL 终止 → 垃圾尾巴**：`SDL_UCS4ToUTF8(cp, buf)` **只写 UTF-8 字节、不加 `'\0'`**（`ref/SDL-3.4.14/src/stdlib/SDL_string.c`），我们 `char buf[8]` 未初始化 → `SDL_SendKeyboardText(buf)` 读到栈上未初始化字节 → MC `memUTF8` 解出 U+FFFD + `[`/`]`。
   **修**：`SDL_ohosevents.c` char 分支 `char *end = SDL_UCS4ToUTF8(cp, buf); *end = '\0';`。
2. **每字两次 TEXT_INPUT**：`meowjrebridge.cpp:676-677` `MeowSendChar` **同时**调 `charMods` 与 `ch`；SDL 路径两 thunk 皆 NULL → 都**回落入环**（`MEOW_EV_CHAR_MODS`+`MEOW_EV_CHAR`）→ pump 两条 → 插两次。
   **修**：只允许**一个**回落（建议仅 `char_mods` 回落、`char` 保持需 thunk），或 `MeowSendChar` 只发一个；二者都不影响 GLFW（有 thunk）路径。
3. **MC 26.3 文本模型（已核实）**：文本唯一由 **`SDL_EVENT_TEXT_INPUT`** 插入（`SDLEventHandler.handleTextInputEvent → KeyboardHandler.textInput → EditBox.charTyped`）；`KEY` 仅用于**按键绑定/导航**，**不从 KEY 派生文本**；`TEXT_EDITING` 只驱动 `IMEPreeditOverlay`（不插字）。⇒ 我们**只需**发 `KEY`（绑定）+ 每提交字符一个 `TEXT_INPUT`；IME 预编辑可选发 `TEXT_EDITING`（MC 设了 `SDL_IME_IMPLEMENTED_UI=composition`，但当前 ArkUI IME 直出中文即可不补）。

### 8.2 鼠标锁定（grab）—— 驱动缺 `SDL_Mouse` 相对模式
- **根因**：MC 26.3 用 `SDL_WarpMouseInWindow` + `SDL_SetWindowRelativeMouseMode(handle,true)` 做 grab（`InputConstants.grabMouse`）。我们 `ohos` 驱动**未挂 `SDL_Mouse.SetRelativeMouseMode`**（`SDL_ohosvideo.c` 只设 video vtable；`SDL_Mouse` 在 `src/events/SDL_mouse_c.h`，经 `SDL_GetMouse()` 安装）→ SDL 返回 `Unsupported` → `env->grabbing` 永不置位 → ArkTS 不锁光标、NDK overlay 无 delta。
- **修（仅驱动；ArkTS 不动）**：新增 `SDL_ohosmouse.c` + 在 `OHOS_VideoInit` 调 `OHOS_InitMouse()`：
  - `mouse->SetRelativeMouseMode(enabled)` → 写 `env->grabbing`/`isGrabbing`（同 `nativeSetGrabbing` 语义）并重置 delta 基线；
  - `mouse->WarpMouse` → `dlsym("meowGrabReset")`（复用既有虚拟光标居中）；
  - `OHOS_PumpEvents`：`env->grabbing` 时**改发相对位移** `SDL_SendMouseMotion(ts,win,0,true,dx,dy)`（对 `env->cursorX/Y` 做差分），否则维持绝对；SDL 在相对模式下会**丢弃绝对** motion（`SDL_mouse.c`）。
  - 可选：`ShowCursor`（相对模式自动隐藏光标在无该钩子时是 no-op；我们靠 `env->grabbing` 已隐藏指针）。

### 8.3 落地清单（2026-09-11 已实现，待设备验证）
- [x] `SDL_ohosevents.c`：字符 NUL 终止（8.1-1）。
- [x] char 单发：`OHOS_PumpEvents` **折叠 CHAR_MODS/CHAR 对**（`MeowSendChar` 两个都入环；GLFW 路径不变）。
- [x] 新增 `SDL_ohosmouse.c/.h` + `OHOS_VideoInit` 调 `OHOS_InitMouse()`（`SetRelativeMouseMode`→`env->grabbing`；`WarpMouse`→置虚拟光标）。
- [x] `OHOS_PumpEvents`：`grabbing` 时发**相对位移** `SDL_SendMouseMotion(...,true,dx,dy)`（差 `env->cursorX/Y`，进入时重置基线）。
- [x] 实机验证（2026-09-11，26.3-rc-1）：打字无乱码；进游戏光标锁定 + 转视角正常；全屏正常。
