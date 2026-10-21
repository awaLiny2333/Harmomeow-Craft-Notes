# 01 · Amethyst pojavexec 源码全景（编译单元级）

> 来源：子 agent A 侦查（read-only）。基准 = Amethyst-Android 仓库（下称 `<repo>`）。
> 目录：`<repo>/app_pojavlauncher/src/main/jni/`；Java 侧：`<repo>/jre_lwjgl3glfw/lwjgl-{3.3.3,3.4.1}/src/main/java/org/lwjgl/glfw/`。
> 注意：androidnsbypass/SDL/gl4es 等子模块在 checkout 中为空。

## 0. 模块边界（Android.mk 各 LOCAL_MODULE）

| 模块 | 源文件 | 依赖 | 说明 |
|---|---|---|---|
| `pojavexec` | 16 个 C 文件（见 §1） | `-ldl -llog -landroid`；SHARED: androidnsbypass；arm64 `-DADRENO_POSSIBLE` | 主桥 |
| `exithook` | native_hooks/{exit,chmod,sdl,dlopen}_hook.c | bytehook + pojavexec(用其 nominal_exit/pojav_environ) | 进程退出/钩子 |
| `linkerhook` | driver_helper/…/turnip/hook.c | androidnsbypass；`-z global` | Turnip/Vulkan 注入（Android linker 私有） |
| `glxshim` | driver_helper/glxshim/glxshim.c | pojavexec | glXGetProcAddress→getProcAddress |
| `pojavexec_awt` | awt_bridge.c | 无 | AWT 桥 |
| `awt_headless/awt_xawt` | 空 / awt_xawt/xawt_fake.c | — | xawt 假实现（链接后删 headless） |

- 构建：ndkBuild + ndk 27 + prefab(bytehook)。Application.mk: android-21、arm64-v8a、c++_shared。
- **没有** vulkan_zink/gl4es 模块：那是 `egl_bridge.c` 内的渲染路径名。

## 1. pojavexec 模块编译单元（16 个 C）

bigcoreaffinity.c · egl_bridge.c · ctxbridges/{loader_dlopen,gl_bridge,osm_bridge,egl_loader,osmesa_loader,swap_interval_no_egl}.c · environ/environ.c · jvm_hooks/{emui_iterator_fix_hook,java_exec_hooks,lwjgl_dlopen_hook}.c · input_bridge_v3.c · jre_launcher.c · utils.c · stdio_is.c
（含头：environ.h、ctxbridges/{bridge_tbl,common,gl_bridge,osm_bridge,egl_loader,osmesa_loader,loader_dlopen}.h、utils.h、stdio_is.h、jvm_hooks.h、global_state.h、log.h、include/SDL3、GL/{gl,glext,osmesa}.h）

### 关键依赖方向（符号供给）
- pojavexec ← exithook：`nominal_exit`、`pojav_environ`、notifyLauncher/get_attached_env、`Java_..._CallbackBridge_nativeClipboard`
- pojavexec ← glxshim：`getProcAddress`（egl_loader.c）
- pojavexec 内 self：`app_escapeNs`（egl_loader.c:34 定义；loader_dlopen/utils extern 用）、`pojav_environ`（environ.c:14）
- loader_dlopen/utils ↔ androidnsbypass（Android linker namespace，**OHOS 无**）
- 运行时按名 dlopen：libjli.so(JLI_Launch)@jre_launcher、libSDL3.so@input_bridge:590、libEGL/libOSMesa/libvulkan…

## 2. 逐文件要点

### input_bridge_v3.c（598 行）—— GLFW JNI + 事件中枢
- JNI_OnLoad（39-76）：首次=Dalvik(ART) 缓存 `dalvikJavaVMPtr` + 抓 CallbackBridge 静态方法/字段；第二次=JVM 缓存 `runtimeJavaVMPtr` + hookExec + installLwjglDlopenHook + installEMUIIteratorMitigation；Dalvik 每次加载 registerFunctions。
- 全部 `Java_org_lwjgl_glfw_GLFW_*` 导出：nativeInitializeGLFWNativeBridge（static 块回调，抓 glfwSetWindowAttrib/internalWindowSizeChanged/internalChangeMonitorSize + keyDownBuffer 317B/mouseDownBuffer 8B 直缓冲指针）、ADD_CALLBACK_WWIN 宏生成 7 个 nglfwSet{Char,CharMods,CursorEnter,CursorPos,Key,MouseButton,Scroll}Callback、nglfwGetCursorPos(+JavaCritical 双变体)、glfwSetCursorPos 系列、nglfwSetShowingWindow。
- `pojavPumpEvents/StartPumping/StopPumping`（122-210）：glfwPollEvents 泵（Start 快照 counter→每 window PumpEvents 分发 Char/CharMods/Key/MouseButton/CursorEnter/Scroll + 鼠标/监视器脏标志→Stop 回写）。**事件环形缓冲 8000**（environ.h）+ atomic counter，SPSC 式。
- CallbackBridge native：nativeClipboard（跨 VM 剪贴板）、nativeSetInputReady（含 JavaCritical）、nativeSetGrabbing（回叫 onGrabStateChanged）、nativeEnableGamepadDirectInput、nativeGetAndroidDPI、nativeNotifyLauncher、nativeSetWindowAttrib（ART 线程 attach JVM）。
- critical/noncritical 双 ABI：send_char/char_mods/cursor_pos/key(写 keyDownBuffer[max(0,key-31)])/mouse_button(写 mouseDownBuffer[button])/screen_size(置标志帧内 updateMonitor/WindowSize)/scroll。
- `dvm_testCriticalNative/tryCriticalNative`（ART CriticalNative 探测，经 `CriticalNativeTest`）→ OHOS 大概率无 → **退化 noncritical 路径**。
- gamepad：internalGetGamepadDataPointer + nativeCreateGamepad{Buffers} + SDL dlopen hack（Legacy4J）。

### environ/environ.{c,h}
- `pojav_environ` 全局 + `__attribute__((constructor))`：读/写 `POJAV_ENVIRON` env（hex 指针）→ **跨模块进程内共享**（机制可移植）。
- 关键字段：pojavWindow(ANativeWindow*)、config_renderer(1=GL4ES 2=VK_ZINK 4=VULKAN)、事件缓冲+索引、cursorX/Y、双 VM 指针、keyDown/mouseDownBuffer、7 个 GLFW_invoke_* 回调指针、gamepadState。`common.h` basic_render_window_t{state, nativeSurface, newNativeSurface} 依赖 ANativeWindow 类型。

### egl_bridge.c + ctxbridges/*
- 桥函数表 7 函数指针（br_init/init_context/make_current/get_current/swap_buffers/setup_window/swap_interval），gl_bridge 或 osm_bridge 二选一。
- gl_bridge：EGL（libEGL 经 egl_loader dlsym）；桌面 GL 分支按 `AMETHYST_RENDERER` 前缀 `opengles3_desktopgl` → eglBindAPI(EGL_OPENGL_API)；surface 来自 `pojav_environ->pojavWindow`（ANativeWindow），swap 检测 EGL_BAD_SURFACE 死亡重建，750ms usleep 等 surface 死亡。
- osm_bridge：OSMesa 离屏 + ANativeWindow lock/unlock 上屏（zink 实为 OSMesa 软渲）。
- egl_loader/osmesa_loader：全函数指针表 + dlsym（EGL/OSMesa）。`getProcAddress` 导出（glxshim 用）。
- loader_dlopen：dlopen + androidnsbypass namespace 兜底（Android-only）。
- swap_interval_no_egl：**AOSP ANativeWindow 内部结构体 vtable 逆向**（极端私有）。
- egl_bridge 顶层：pojav* C API 导出（pojavTerminate/GetCurrentContext/Init/SetWindowHint/SwapBuffers/MakeCurrent/CreateContext/SwapInterval）+ setupBridgeWindow(ANativeWindow_fromSurface)/releaseBridgeWindow + Vulkan(zink) 注入族（Turnip/nsbypass/api-level gate）。

### jvm_hooks/*
- java_exec_hooks：RegisterNatives 覆盖 `java.lang.UNIXProcess/ProcessImpl.forkAndExec`（xdg-open→clipboard；ffmpeg→POJAV_FFMPEG_PATH 重写 env 块）。JVM 类名/签名耦合但逻辑通用。
- lwjgl_dlopen_hook：覆盖 `org.lwjgl.system.linux.DynamicLinkLoader.ndlopen`（libvulkan→maybe_load_vulkan；其它普通 dlopen）——LWJGL native 加载拦截核心。
- emui_iterator_fix_hook：EMUI 专用（POJAV_EMUI_ITERATOR_MITIGATE 才装）。

### 其它
- bigcoreaffinity：sysfs 最高频核 + sched_setaffinity（纯 POSIX/Linux）。
- stdio_is：pipe/dup2 stdout 抓取→Logger；`nominal_exit`（_Noreturn，弹崩溃/System.exit）。
- utils：JNI 转换 + JRE 工具导出；`android_update_LD_LIBRARY_PATH`（**bionic 私密**）；nsbypass dlopen 兜底。
- jre_launcher.c：`VMLauncher.launchJVM`→dlopen libjli→JLI_Launch；信号重置 + abort_waiter（pipe 线程收 SIGABRT→nominal_exit）。纯 POSIX。

## 3. 平台依赖三维矩阵（文件 × Android API × 类别）

分类：A=纯 POSIX 可移植（照搬）；B=Android 独有需替换；C=可由上层注入。

| 文件 | Android 专属面 | 类别 |
|---|---|---|
| bigcoreaffinity.c | 无 | **A** |
| stdio_is.c | log.h | A（log 换 hilog） |
| jre_launcher.c | log.h | A |
| jvm_hooks/* | android/log.h、api-level | A（去 android 头即可） |
| ctxbridges/osmesa_loader.c | 无 | A |
| environ/environ.c | log.h；environ.h/common.h 的 ANativeWindow 类型 | A/C（类型替换） |
| input_bridge_v3.c | CriticalNative(ART 探测)；CallbackBridge 反向栈 | C（骨架照搬，critical 表退化/重写） |
| ctxbridges/gl_bridge.c | ANativeWindow surface | A/B 边缘 |
| ctxbridges/osm_bridge.c | ANativeWindow lock/unlock | B（换 OHOS 缓冲） |
| ctxbridges/egl_loader.c | app_escapeNs 定义 | A/B |
| ctxbridges/loader_dlopen.c | nsbypass namespace | **B（重写）** |
| ctxbridges/swap_interval_no_egl.c | AOSP 内部 ABI 逆向 | **B（整文件弃）** |
| egl_bridge.c | ANativeWindow×5、AHardwareBuffer、nsbypass/dlext、/system/lib64 硬路径 | **B（重写面大）** |
| utils.c | android_update_LD_LIBRARY_PATH、nsbypass、android.view.Surface 伪导出 | B（拆分重写） |

## 4. GLFW.java（Java 侧）契约速查
- static{System.loadLibrary("pojavexec"); nativeInitializeGLFWNativeBridge();}（行 556-564）
- `Library.loadNative(GLFW,"org.lwjgl.glfw","libpojavexec.so",true)`（635）→ dlopen handle
- GLFW$Functions dlsym 裸函数：pojavInit/CreateContext/GetCurrentContext/MakeContextCurrent/Terminate/SetWindowHint/SwapBuffers/SwapInterval/PumpEvents/StopPumping/StartPumping
- 7 个 setter native `(JJ)J`；nglfwGetCursorPos(+A 数组/JavaCritical 变体)；glfwSetCursorPos
- Java 兜底：glfwWindowShouldClose 读 Java 字段（HOML 从不翻转→关窗不退出）、keyDown/mouseDown 直缓冲（native 写、Java glfwGetKey/GetMouseButton 读）
- 事件泵：glfwPollEvents → StartPumping → 每 window PumpEvents → StopPumping

## 5. 逐文件移植判定汇总
**照搬**：bigcoreaffinity、stdio_is(log 换 hilog)、jre_launcher、jvm_hooks(去 android 头)、osmesa_loader、environ.c、emui hook。
**小幅适配**：gl_bridge、egl_loader（去 app_escapeNs）、java_exec/lwjgl_dlopen hook。
**需重写**：input_bridge_v3（骨架+事件泵照搬，去掉 ART CriticalNative 双表，CallBackBridge 反向改为 OHOS 注入或保留同名 Java 类）、egl_bridge（surface 换 OHNativeWindow/surfaceId、去掉 zink/turnip/nsbypass 分支或换 libGLv4 直连）、osm_bridge、loader_dlopen、swap_interval_no_egl、utils。
**模块外**：pojavexec_awt / awt_xawt / exithook / linkerhook / glxshim —— 非必需，先不移植。

> ⚠️ 结论：Android 版源码存在且机制可搬；真正要改的是 ① 平台类型/surface（ANativeWindow→OHNativeWindow/surfaceId）② 去掉 Android linker namespace/CriticalNative/AOSP 私有 ABI ③ log→hilog。渲染后端取我们已定案的 libGLv4（可大幅裁掉 zink/OSMesa 分支）。
