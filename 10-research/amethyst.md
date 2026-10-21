> 说明（2026-09-15）：外部项目研究（参照用）；本工程已净室重写，未采用其代码。

# Amethyst-Android 深度分析

> 位置：`ref/Amethyst-Android`
> 主分支：`v3_openjdk`（默认 checkout）。另一个重要分支 `master` 也存在。
> 定位：Android + iOS 的 Minecraft: Java Edition 启动器，源自 Boardwalk + PojavLauncher。
> 官网自述："From Boardwalk's ashes and PojavLauncher's ruined reputation, here comes Amethyst!"
>
> **注意**：README 里明确写"app_pojavlauncher"，包名 `net.kdt.pojavlaunch` —— 这是 Pojav 血统的直接延续。

## 1. 技术定位

- 与 HomoLauncher **同源**（都源自 PojavLauncher），因此它的 JNI 层、渲染驱动加载、输入桥、AWT 移植
  都是理解 HomoLauncher 底层实现细节的"完整版教科书"。
- 核心值：它拥有**完整、可编译、可运行的 JNI 原生层**，而 HomoLauncher 的原生层被打包在
  `launcher.har`/HSP 里看不到源码。要理解"鸿蒙 PC 如何跑 OpenGL ES"，Amethyst 的源码是打开的窗口。

## 2. 模块结构（settings.gradle）

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

## 3. 主应用目录（app_pojavlauncher/src/main）

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

## 4. 完整 JNI 原生层（★渲染/JVM 教科书）

这是 Amethyst 最有价值的部分，对应 HomoLauncher 里被 HAR 包住的实现。

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

## 5. JVM 启动（jre_launcher.c）

```c
// 核心：dlopen libjli.so，取 JLI_Launch 符号，然后调用
void* libjli = dlopen("libjli.so", RTLD_LAZY | RTLD_GLOBAL);
JLI_Launch_func *pJLI_Launch = dlsym(libjli, "JLI_Launch");
return pJLI_Launch(margc, margv, 0,NULL,0,NULL, FULL_VERSION, DOT_VERSION, ...);
```

- **信号处理**：`abort_waiter_setup()` 用 pipe + 线程捕获 SIGABRT，弹出用户友好的崩溃对话框。
- **对比 HomoLauncher**：HomoLauncher 的 `jvm_Launcher` 就是这一套的鸿蒙版（`libjli.so` + `JLI_Launch`）。

## 6. 输入桥（input_bridge_v3.c，598 行）

是理解"鸿蒙 PC 键鼠如何进 MC"的最佳参考：

- **数据结构**：`pojav_environ_s`（environ.h）维护一个 8000 容量的环形事件队列
  `GLFWInputEvent events[EVENT_WINDOW_SIZE]`，用 `atomic_size_t eventCounter` 计数。
- **JNI_OnLoad**：首次加载保存 Dalvik JavaVM 指针；第二次加载（在 JVM 内）保存 runtime JavaVM 指针并
  安装 `hookExec` / `installLwjglDlopenHook`。
- **事件注入**：`critical_send_key/mouse_button/cursor_pos/scroll/char` 等，**CriticalNative** 快路径
  （`tryCriticalNative` 检测可用则注册带 "!" 的临界方法，号称快 4.6x）。
- **事件泵**：`pojavStartPumping/StopPumping` 在渲染线程安全地消费队列并回调 GLFW。
- **手把**：`internalGetGamepadDataPointer` + 直接 ByteBuffer。
- **SDL3**：末尾 `initSubsystem()` hack，为 Legacy4J 这样的 mod 提前 `SDL_Init`。
- **HomoLauncher 对应**：`HOMLBridge.send_key/send_mouse_button/...` 就是这套的 ArkTS 封装，
  事件队列结构在鸿蒙 HSP 原生侧（看不到源码但接口一一对应）。

## 7. 关键 Java 类（上层）

- `LauncherActivity` / `MainActivity`：UI 入口。
- `MinecraftGLSurface`：GL surface 生命周期（对应 HomoLauncher 的 XComponent）。
- `AWTCanvasView` / `AWTInputBridge` / `AWTInputEvent`：AWT 输入桥（对应 cacio）。
- `Tasks.MinecraftDownloader`：负责拉版本 JSON、libraries、assets、natives。
- `modloaders/`：Forge / NeoForge / Fabric / OptiFine / BTA（Better Than Adventure）/ LWJGL3ify 等的
  版本列表 + 下载任务。
- `modloaders/modpacks/api/`：CurseForge / Modrinth 模组包 API 抽象。
- `authenticator/`：微软 OAuth（与 HomoLauncher 的 MicrosoftService 同族）。
- `profiles/`：版本 profile 选择器。

## 8. 渲染驱动家族（README 的 Credits 揭示完整链条）

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

## 9. 多 JRE 多架构

- README 明确支持 jre8/17/21/25，架构 ARM32/ARM64/x86/x86_64。
- JRE 由独立 repo `openjdk-build-multiarch` 预编译，CI 发布 `jre8-pojav` 等 artifact。

## 10. 对"鸿蒙 PC"落地的价值总结

1. **完整 JNI 输入桥源码**：事件队列 + CriticalNative + 光标抓取，可对照理解鸿蒙 HSP 内部实现。
2. **jre_launcher.c 的 dlopen libjli.so 范式**：说明 JVM 嵌入思路完全一致。
3. **ctxbridges + egl_bridge + glxshim**：理解 OpenGL 上下文如何在移动/嵌入式环境建立。
4. **渲染驱动全家桶**：gl4es/mobileglues/ANGLE/mesa/virgl 的选择依据。
5. **modloader/modpack 上层**：比 HomoLauncher 完善，可参考补齐启动器功能。
