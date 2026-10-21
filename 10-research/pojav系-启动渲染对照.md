> 外部项目研究（参照用，非本工程实现）。

# 移动/鸿蒙平台启动链路：Pojav 系对照

> 覆盖 Amethyst-Android（v3_openjdk，源码完整）与 HomoLauncher（鸿蒙，native 部分黑盒）。
> 核心洞察：**鸿蒙版 = Android Pojav 的"进程模型/渲染思想" + "鸿蒙 UI/surface 新写层"**，
> 大量 jar 与 JVM 参数是直接搬运。理解 Amethyst 就等于理解 HomoLauncher 的底层。
>
> **历史定位（2026-09-10）**：本文是早期对 HomoLauncher/Pojav 系的研究记录。本项目现用
> launcher/GLFW overlay/桥均为**净室自研**，Pojav/Amethyst/HOML 代码**已全部清除、无残留**；
> `ref/Amethyst-Android`、`ref/PojavLauncher_iOS` 仅作工作区外部参照，不入仓库、不随包。

## 1. 双 VM 同进程模型（Amethyst 核心架构）

Android 版把"启动器 UI"（ART VM）与"游戏"（dlopen 进来的 OpenJDK）放**同一进程**，
`pojav_environ`（C 全局结构）是两 VM 的粘合剂：

```
Android ART（启动器/输入/UI）
   └── nativeSend*(InputBridge/pojavexec) ──事件/尺寸──> pojav_environ
OpenJDK（游戏，由 JLI_Launch 拉起的第二个 VM）
   └── org.lwjgl.glfw.GLFW (Java stub) ←──回调函数指针── pojav_environ
```

要点：
- **JVM 启动**：没有 java 可执行文件，`dlopen(libjli.so)` + 调 `JLI_Launch(argv)`（jre_launcher.c）
  等价于进程内跑 `java ...`。HomoLauncher 同机制（jli_path env + bin/java 作 argv[0]）。
- **无 PojavClassLoader/PojavLauncher 包装**（v3_openjdk 已移除）：JVM 直接跑 manifest 的
  mainClass（1.21.10 = net.minecraft.client.main.Main）；字节码兼容交给 `-javaagent:MioLibPatcher.jar`。
- 鸿蒙 Homolauncher 保留了 `PojavClassLoader`/`PojavLauncher`（launcher.jar 内），属老架构残留。

## 2. GLFW 被 Java stub 取代（渲染/输入的关键）

LWJGL 的 GLFW 没有真 `libglfw.so`，取而代之：
- **Java 侧伪 GLFW**（org/lwjgl/glfw/GLFW.java）：用 Java 字段存回调、伪造 window handle
  （=native context 指针）、假 monitor/videoMode；glfwCreateWindow 内部调 `pojavCreateContext`。
- **native stub 库**（旧名 libpojavexec.so）：导出（旧名）`pojavInit/pojavCreateContext/pojavMakeCurrent/pojavSwapBuffers/pojavSwapInterval/pojavPumpEvents/pojavStartPumping/pojavStopPumping` 等 C 函数。
- **函数来源**：GLFW.java `Library.loadNative(..., "libpojavexec.so")` 用 dlsym 解析上面 pojav* 函数。

事件流（现代 MC，队列模式）：
```
UI 线程输入 → nativeSendKey/Mouse/Cursor/Scroll（CriticalNative 直通）
  → pojav_environ 8000 深环形缓冲
  → MC 渲染线程 glfwPollEvents → pojavStartPumping/pojavPumpEvents/pojavStopPumping（旧名）
  → 回调 GLFW_invoke_*(window,...) 指针（即 LWJGL Java 回调 thunk）
```

## 3. 渲染 surface 与 GL 上下文

- **surface**：Android 是 SurfaceView/TextureView 的 Surface → `ANativeWindow_fromSurface`。
  鸿蒙是 `XComponent(XComponentType.TEXTURE)` 的 surfaceId → native OH_NativeWindow（同思路）。
- **EGL 上下文**：egl_bridge/gl_bridge.c：`eglCreateWindowSurface(display, config, nativeWindow)`
  + `eglMakeCurrent`，把 EGLSurface 绑到系统 surface。
- **绑定 API**：默认 `EGL_OPENGL_ES_API`（ES 2/3，client version 由 `LIBGL_ES` 决定）；
  只有 Zink/Kopper 桌面 GL 路才绑 `EGL_OPENGL_API`。
- **MC 拿到的 GL**：绝大多数渲染器下 MC 实际是在 **EGL + GLES 上下文**上，经翻译层伪装成桌面 GL。

## 4. 渲染驱动如何"混进" LWJGL

不是 `libGL.so.1` 名义 dlopen，而是双通道：
1. **JVM 启动前**：按渲染器选择 dlopen 驱动 + 设环境变量（旧名：`POJAV_RENDERER`、`LIBGL_*`、`POJAVEXEC_EGL`…）。
2. **LWJGL 的 GL FunctionProvider**：`-Dorg.lwjgl.opengl.libname=<驱动 .so>` → LWJGL 的
   `GL.createCapabilities()` 从该 .so 解析全部 GL 函数指针（真正绕开真 GLFW/桌面 GL 加载）。

渲染器 ↔ 驱动映射（Amethyst 完整版，HomoLauncher 子集）：

| renderer 标识 | 驱动 | 说明 |
|---------------|------|------|
| opengles2/3 | libng_gl4es.so | gl4es 系（OpenGL→GLES 翻译） |
| opengles_mobileglues | libmobileglues.so | **默认**（MobileGlues 统一层） |
| opengles3_desktopgl_zink_kopper | libglxshim.so | 真桌面 GL 路（Kopper/Zink），不常用 |
| vulkan_zink | libOSMesa.so | 软件/虚拟 GPU |
| opengles3_ltw | libltw.so (ANGLE) | ANGLE 系 |
| (鸿蒙) openglv4 | libGLv4.so | **仅鸿蒙 PC/平板**原生 GL4 驱动 |

## 5. AWT/Caciocavallo：现代原版其实可不需要

- Caciocavallo 是一套"无 X11 的 AWT 实现"（cacio-tta/cacio-shared），配合
  `awt.toolkit=...CTCToolkit`、一堆 `--add-exports/--add-opens java.desktop`、`-Xbootclasspath/a`。
- Amethyst 对 **1.21.10 原版游戏启动也无条件注入**（Tools.getCacioJavaArgs 被无条件调用）；
  HomoLauncher 同样无条件带 cacio17。
- 但**原版 1.21.10 正常游戏流程不依赖 AWT**（AWT 只被老版本/Forge 安装器 GUI/个别 mod 使用）。
  → 若只追求"原版 1.21.10 + OpenGL"，Cacio 是可砍项（代价：必须同步改掉 launcher.jar 里
  硬编码的 cacio 初始化）。

## 6. 鸿蒙 HomoLauncher 的"资产清单"（对照可裁剪面）

**直接搬自 Amethyst/Pojav（jar/思路）**：arc_dns_injector（Artdeell 披风，非必需）、
caciocavallo17、MioLibPatcher（鸿蒙未接线）、log4j-rce-patch、GLFW stub + pojav* 思路、
整份 JVM -D 清单、JLI 拉起 JVM、`org.lwjgl.opengl.libname` 驱动注入、渲染器 env。

**鸿蒙特有新写**：ArkTS UI/状态、N-API 桥（HOMLBridge + libhoml_bridge.so）、
HSP 化 JRE（jre17/jre25 动态依赖）、XComponent surface、launcher.jar（Java 侧主库）、
patchjna_agent（JNA/Oshi 鸿蒙修正）、ArkTS↔GLFW keycode 双映射。

**launcher.har 内含**：libhoml_bridge.so、libpojavexec.so、libpojavexec_awt.so、libjnidispatch.so
（JNA）、libawt_xawt.so、libdriver_helper.so、libmobileglues.so、libng_gl4es.so、libopenal.so、
libspirv-cross-c-shared.so、libc++_shared.so。

**jre HSP**：jre17 (17.0.18) / jre25 (25.0.1) OpenJDK aarch64 **musl**（OS_NAME=Linux），
完整 `libjvm/libjli/libjava/libawt/libfontmanager/...` + tar.xz 含 bin/java、lib/modules、cacerts。
jre25 向下兼容 Java 21 字节码 → **只跑 1.21.10 时 jre25 即可，jre17 可砍**。

## 7. HomoLauncher 的鸿蒙细节证据

- `-Dos.name=Linux -Dos.version=harmonyos -Dcpu.name=harmonyos`：伪装 Linux 过 1.21.10 的 OS rules。
- `-Dglfwstub.windowWidth/Height`：把 UI 层尺寸传给 Java GLFW stub。
- `dl_open(glibName)` 在 `jvm_Launcher()` 前执行：先把渲染库 dlopen 进进程。
- `OHOS_DL_DIR/OHOS_JAVA_HOME/LD_LIBRARY_PATH/jli_path`：告知 native 层 JRE 库位置。
- XComponent surfaceId 字符串 parseInt → `bridge.surfaceChanged(id, w, h)`（w/h 写死，真实尺寸走 glfwstub）。
- 权限：`ALLOW_WRITABLE_CODE_MEMORY`（JVM JIT 需可写可执行内存）、`LOCK_WINDOW_CURSOR`（抓鼠标）、
  `FILE_ACCESS_PERSIST`（目录授权持久化）、`NDK_START_SELF_UI_ABILITY`（native 拉起 UI，用途未确认）。
- 1.21.10 明确受支持：resfile/game/versions.txt 列到 1.21.10；caciocavallo17/HMCLTransformerDiscovery/
  log4j2-1.12 等现代组件就位。
