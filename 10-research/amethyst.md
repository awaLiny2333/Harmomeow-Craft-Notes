> 说明（2026-09-15）：外部项目研究（参照用）；本工程已净室重写，未采用其代码。

# Amethyst-Android 深度分析（含源码定位）

> 位置：`ref/Amethyst-Android`
> 主分支：`v3_openjdk`（默认 checkout）；`master` 亦存在。
> 定位：Android + iOS 的 Minecraft: Java Edition 启动器，源自 Boardwalk + PojavLauncher。
> 官网自述："From Boardwalk's ashes and PojavLauncher's ruined reputation, here comes Amethyst!"
> **血统**：README 明写 `app_pojavlauncher`、包名 `net.kdt.pojavlaunch` —— Pojav 的直接延续。
> **历史定位（2026-09-10）**：Amethyst 源码**未进入本项目**；现用 launcher / GLFW overlay / 桥均**净室自研**，
> Pojav / Amethyst / HOML 代码**已全部清除、无残留**；`ref/Amethyst-Android` 仅作外部参照，不入仓库、不随包。

## 1. 技术定位

- 与 HomoLauncher **同源**（都源自 PojavLauncher），因此它的 JNI 层、渲染驱动加载、输入桥、AWT 移植
  都是理解 HomoLauncher 底层实现细节的"完整版教科书"。
- 核心值：它拥有**完整、可编译、可运行的 JNI 原生层**，而 HomoLauncher 的原生层被打包在
  `launcher.har`/HSP 里看不到源码。要理解"鸿蒙 PC 如何跑 OpenGL ES"，Amethyst 的源码是打开的窗口。

## 2. 双 VM 同进程模型

- AndroidManifest：`:launcher`（启动器 UI/输入）、`:game`（MainActivity + GameService）、
  `:gui_installer`（JavaGUILauncherActivity，Forge 安装器 GUI）。
- 游戏在 `:game` 进程：ART 与后来 dlopen 的 OpenJDK 共存；C 全局 `pojav_environ` 粘合两 VM。

## 3. 模块结构（settings.gradle）

```
include ':jre_lwjgl3glfw'          # GLFW stub + LWJGL 构建
include ':app_pojavlauncher'       # ★主应用
include ':arc_dns_injector'        # DNS 注入 agent
include ':MioLibPatcher'           # 补丁器
include ':forge_installer'         # Forge 安装器
include ':androidnsbypass'         # Android namespace 绕过
```

根 `build.gradle` 有个巧妙机制：所有 subproject 的 Jar 任务产物会自动拷贝到
`app_pojavlauncher/src/main/assets/components/<name>/` 并生成 `version` 文件（SHA-1）。

## 4. 主应用目录（app_pojavlauncher/src/main）

```
java/
├── com/oracle/dalvik/VMLauncher.java     # JVM 启动入口（Java 侧）
├── net/kdt/pojavlaunch/                  # ★主包（Pojav 血统）
│   ├── AWTCanvasView / AWTInputBridge / AWTInputEvent   # AWT 输入
│   ├── LauncherActivity / MainActivity / BaseActivity    # Activity
│   ├── MinecraftGLSurface.java           # GL surface 容器
│   ├── ModLoader/*、modloaders/*          # modloader（Forge/Fabric/NeoForge/OptiFine...）
│   ├── authenticator/*                   # 账户（微软 OAuth）
│   ├── profiles/*                        # 版本 profile
│   ├── tasks/*                           # 下载任务（MinecraftDownloader 等）
│   └── ...
├── org/lwjgl/glfw/                       # GLFW 绑定（CallbackBridge、GLFW）
└── org/libsdl/app/                       # SDL 集成
jni/                                       # ★完整原生层（见下）
assets/components/                         # 打包好的组件 jar（caciocavallo、lwjgl3、等）
```

## 5. JNI 原生层（★渲染 / JVM 教科书）

对应 HomoLauncher 里被 HAR 包住的实现。

```
jni/
├── jre_launcher.c          # ★JVM 启动：dlopen libjli.so → JLI_Launch
├── input_bridge_v3.c       # ★★输入桥（V3）：GLFW 事件队列 + CriticalNative 优化
├── awt_bridge.c / awt_xawt/xawt_fake.c   # AWT/XAWT 桥（伪造 X Toolkit）
├── egl_bridge.c            # EGL 桥
├── bigcoreaffinity.c       # CPU 大核心亲和
├── ctxbridges/             # ★GL 上下文桥
│   ├── gl_bridge.c / gl_bridge.h
│   ├── egl_loader.c / egl_loader.h
│   ├── osm_bridge.c / osmesa_loader.c
│   └── loader_dlopen.c
├── driver_helper/
│   ├── glxshim/glxshim.c            # GLX shim（桌面 GL 调用伪装）
│   └── internal_android_dlopen_hook/turnip/hook.c   # Turnip/Vulkan 驱动 hook
├── jvm_hooks/
│   ├── java_exec_hooks.c            # java exec hook
│   ├── lwjgl_dlopen_hook.c          # lwjgl dlopen hook
│   └── emui_iterator_fix_hook.c
├── native_hooks/
│   ├── dlopen_hook.c / chmod_hook.c / exit_hook.c / sdl_hook.c
├── environ/environ.c / environ.h    # ★全局状态（pojav_environ_s 结构体）
└── stdio_is.c / utils.c
```

## 6. JVM 启动

| 环节 | 文件 | 说明 |
|---|---|---|
| C 入口 | `jni/jre_launcher.c` | dlopen libjli.so → dlsym JLI_Launch → 调用 |
| Java native 声明 | `java/com/oracle/dalvik/VMLauncher.java` | 仅 `native int launchJVM(String[])` |
| Java 启动器 | `java/net/kdt/pojavlaunch/utils/JREUtils.java` | relocateLibPath/setJavaEnvironment/loadGraphicsLibrary/initJavaRuntime/chdir/VMLauncher.launchJVM |
| 参数 | `java/net/kdt/pojavlaunch/Tools.java` | launchMinecraft/generateLaunchClasspath/getMinecraftJVMArgs/getMinecraftClientArgs/getCacioJavaArgs |

```c
// 核心：dlopen libjli.so，取 JLI_Launch 符号，然后调用
void* libjli = dlopen("libjli.so", RTLD_LAZY | RTLD_GLOBAL);
JLI_Launch_func *pJLI_Launch = dlsym(libjli, "JLI_Launch");
return pJLI_Launch(margc, margv, 0,NULL,0,NULL, FULL_VERSION, DOT_VERSION, ...);
```

- **无自定义 classloader**：直接把 version manifest 的 mainClass 放 argv 末尾让 JVM 执行。
- 启动前把 JRE 各 `.so` 先 dlopen 进进程（`initJavaRuntime`），保证 libjli 依赖可解析。
- v3 用 `-javaagent:MioLibPatcher.jar`（+ `-Dmiolibpatcher.alc10=true`）做字节码兼容。
- **信号处理**：`abort_waiter_setup()` 用 pipe + 线程捕获 SIGABRT，弹出用户友好的崩溃对话框。
- **对比 HomoLauncher**：HOML 的 `jvm_Launcher` 就是这一套的鸿蒙版（`libjli.so` + `JLI_Launch`）。

## 7. GLFW stub 与渲染

- Java 侧 stub 源码：`jre_lwjgl3glfw/lwjgl-3.3.3/src/main/java/org/lwjgl/glfw/`
  （GLFW.java + CallbackBridge.java），3.4.1 目录有带 SDL 后端变体。
- 构建：`jre_lwjgl3glfw/lwjgl-3.3.3/build.gradle` 把 stub 与官方 LWJGL 模块合并成
  `lwjgl-<v>-merged-modules.jar`，随启动器 assets/components/lwjgl3/<v>/ 打包。
- 关键导出（Functions 表用 dlsym 解析；以下为 Amethyst 历史名，本项目现对应 `meow*`）：pojavInit/pojavCreateContext/pojavGetCurrentContext/pojavMakeCurrent/pojavSwapBuffers/pojavSwapInterval/pojavSetWindowHint/pojavPumpEvents/pojavStartPumping/pojavStopPumping。
- 库加载：`Library.loadNative(GLFW.class, "org.lwjgl.glfw", "libpojavexec.so", true)`;
  static{} 里 System.loadLibrary("pojavexec") 触发 JNI_OnLoad 记录 runtimeJavaVMPtr。
- glfwCreateWindow → nglfwCreateContext → native pojavCreateContext（返回 context 指针即 window handle）。
- 事件泵送在 MC 每帧 glfwPollEvents：pojavStartPumping→每 window PumpEvents→pojavStopPumping；
  native 在渲染线程上回调 LWJGL thunk（关键：跨 VM 安全回 Java）。

## 8. EGL surface 与 GL 上下文

- Android surface：MinecraftGLSurface.java（SurfaceView/TextureView 二选一）→
  JREUtils.setupBridgeWindow(surface) → `ANativeWindow_fromSurface` 存 pojav_environ->pojavWindow。
- egl_bridge.c：pojavCreateContext 按渲染器分派（Vulkan/NO_API 直接返回 ANativeWindow，
  否则 br_init_context 建 GL 上下文）；gl_bridge.c：
  - gl_init：eglGetDisplay/eglInitialize；
  - gl_init_context：默认 eglBindAPI(EGL_OPENGL_ES_API)，client version 读 LIBGL_ES；
    renderer 前缀 opengles3_desktopgl 才绑 EGL_OPENGL_API（Kopper/Zink 桌面 GL）；
  - gl_make_current：首次 gl_swap_surface 用 eglCreateWindowSurface(display, config, window) 再 eglMakeCurrent；
  - gl_swap_buffers 处理 surface 死亡重建（1x1 pbuffer 兜底）。
- 渲染驱动双通道（JREUtils.loadGraphicsLibrary + `-Dorg.lwjgl.opengl.libname=<so>`）。

## 9. 输入桥

- input_bridge_v3.c（598 行）：JNI_OnLoad 按 VM 分流（第一次=ART 记 dalvikJavaVMPtr；再被 OpenJDK 加载记
  runtimeJavaVMPtr + 装 `hookExec` / `installLwjglDlopenHook`）。
- **事件队列**：`pojav_environ_s`（environ.h）维护 `GLFWInputEvent events[EVENT_WINDOW_SIZE]`（8000 容量）
  + `atomic_size_t eventCounter`；v3 对现代 MC 走栈队列（StackQueue）。
- **CriticalNative 快路径**：`tryCriticalNative` 可用时注册带 "!" 的临界方法（号称快 4.6x）；
  入口 = `critical_send_key/mouse_button/cursor_pos/scroll/char`（JNI 侧 `nativeSend*`）。
- Java ART 侧：CallbackBridge.java 发送 + 维护 keyDownBuffer/mouseDownBuffer（游戏侧 glfwGetKey 读）。
- grab：MC glfwSetInputMode(CURSOR_DISABLED) → nativeSetGrabbing → 跨 VM onGrabStateChanged →
  AndroidPointerCapture requestPointerCapture 相对位移 → sendCursorPos。
- 手把：`internalGetGamepadDataPointer` + 直接 ByteBuffer。
- SDL3：末尾 `initSubsystem()` hack，为 Legacy4J 这样的 mod 提前 `SDL_Init`。
- **HomoLauncher 对应**：`HOMLBridge.send_key/send_mouse_button/...` 就是这套的 ArkTS 封装，
  事件队列结构在鸿蒙 HSP 原生侧（看不到源码但接口一一对应）。

## 10. 版本与 JRE

- LWJGL 版本选择：version json 依赖 `org.lwjgl:lwjgl` 版本 ≥341 → 3.4.1 目录，否则 3.3.3
  （1.21.10 = 3.3.3，即 3.3.3 集）。
- 老版本（iLwjglVersion<=299，LWJGL2）才追加 `lwjglx.jar`（lwjgl2→lwjgl3 兼容），1.21.10 不需要。
- Cacio：Java8 版 `caciocavallo/`（CTCToolkit+androidnw）；Java9+ `caciocavallo17/`（cacio-tta 1.18 +
  `--add-exports/--add-opens`）；老版走 `-javaagent`，java8 走 `Xbootclasspath`。AWTCanvasView 720x600
  像素回显（仅安装器 GUI 场景）。
- README 明确支持 jre8/17/21/25，架构 ARM32/ARM64/x86/x86_64；JRE 由独立 repo
  `openjdk-build-multiarch` 预编译，CI 发布 `jre8-pojav` 等 artifact。

## 11. 渲染驱动家族（README 的 Credits 揭示完整链条）

| 组件 | 用途 | 许可 |
|------|------|------|
| GL4ES | OpenGL → GLES 翻译 | MIT |
| MobileGlues | GLES 统一层（HomoLauncher 默认） | LGPL-2.1 |
| Krypton Wrapper (NG-GL4ES) | 另类 gl4es 包装 | MIT |
| ANGLE | 更近原生的 GLES/Vulkan | BSD |
| virglrenderer | 虚拟 GPU（软件渲染） | MIT |
| Mesa 3D | 软件/驱动实现 | MIT |
| LWJGL3 / LWJGLX | Java GL 绑定 / LWJGL2 兼容层 | BSD-3 |
| OpenAL-Soft + oboe | 音频 | GPLv2 / Apache2 |
| libepoxy | GL 入口解析 | MIT |
| bhook | 退出码捕获 | MIT |
| SDL3 / sdl2-compat | 输入/窗口 | zlib |

这正是 HomoLauncher `lwjgl3` 模块里那些 `.so`（liblwjgl_opengles、libgl4es、libmobileglues、libshaderc...）
的来源对照。

## 12. 关键 Java 类（上层）

- `LauncherActivity` / `MainActivity`：UI 入口。
- `MinecraftGLSurface`：GL surface 生命周期（对应 HomoLauncher 的 XComponent）。
- `AWTCanvasView` / `AWTInputBridge` / `AWTInputEvent`：AWT 输入桥（对应 cacio）。
- `Tasks.MinecraftDownloader`：负责拉版本 JSON、libraries、assets、natives。
- `modloaders/`：Forge / NeoForge / Fabric / OptiFine / BTA（Better Than Adventure）/ LWJGL3ify 等的
  版本列表 + 下载任务。
- `modloaders/modpacks/api/`：CurseForge / Modrinth 模组包 API 抽象。
- `authenticator/`：微软 OAuth（与 HomoLauncher 的 MicrosoftService 同族）。
- `profiles/`：版本 profile 选择器。

## 13. 对"鸿蒙 PC"落地的价值总结

1. **完整 JNI 输入桥源码**：事件队列 + CriticalNative + 光标抓取，可对照理解鸿蒙 HSP 内部实现。
2. **jre_launcher.c 的 dlopen libjli.so 范式**：说明 JVM 嵌入思路完全一致。
3. **ctxbridges + egl_bridge + glxshim**：理解 OpenGL 上下文如何在移动/嵌入式环境建立。
4. **渲染驱动全家桶**：gl4es/mobileglues/ANGLE/mesa/virgl 的选择依据。
5. **modloader/modpack 上层**：比 HomoLauncher 完善，可参考补齐启动器功能。

## 14. 可直接对照的源码清单

```
ref/Amethyst-Android/app_pojavlauncher/src/main/jni/            # C 全栈
  jre_launcher.c / egl_bridge.c / gl_bridge.c / egl_loader.c
  input_bridge_v3.c / environ.{c,h} / ctxbridges/
  awt_bridge.c / jvm_hooks/* / native_hooks/*
ref/Amethyst-Android/app_pojavlauncher/src/main/java/
  org/lwjgl/glfw/CallbackBridge.java        # ART 侧输入发送参考
  net/kdt/pojavlaunch/utils/JREUtils.java   # JVM 参数/环境/驱动装载参考
  net/kdt/pojavlaunch/Tools.java            # manifest 解析/classpath/cacio args
  net/kdt/pojavlaunch/MinecraftGLSurface.java # surface 生命周期参考
ref/Amethyst-Android/jre_lwjgl3glfw/lwjgl-3.3.3/src/main/java/org/lwjgl/glfw/
  GLFW.java / CallbackBridge.java            # Java 侧 GLFW stub（历史参照；现为净室重写）
```
