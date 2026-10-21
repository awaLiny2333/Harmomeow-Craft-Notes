> 外部项目研究（参照用，非本工程实现）。

# Amethyst 技术深潜（移植参照手册）

> 来源：`ref/Amethyst-Android` v3_openjdk 分支源码精读。作为鸿蒙移植的**历史参照实现**，
> 本文件记录关键文件与机制的精确定位，避免将来重新考古。
>
> **历史定位（2026-09-10）**：Amethyst 源码**未进入本项目**。现用 launcher/GLFW overlay/桥
> 均**净室自研**，Pojav/Amethyst/HOML 代码**已全部清除、无残留**；
> `ref/Amethyst-Android` 仅作工作区外部参照，不入仓库、不随包。

## 1. 双 VM 同进程模型

- AndroidManifest：`:launcher`（启动器 UI/输入）、`:game`（MainActivity + GameService）、
  `:gui_installer`（JavaGUILauncherActivity，Forge 安装器 GUI）。
- 游戏在 `:game` 进程：ART 与后来 dlopen 的 OpenJDK 共存；C 全局 `pojav_environ` 粘合两 VM。

## 2. JVM 启动

| 环节 | 文件 | 说明 |
|------|------|------|
| C 入口 | `jni/jre_launcher.c` | dlopen libjli.so → dlsym JLI_Launch → 调用 |
| Java native 声明 | `java/com/oracle/dalvik/VMLauncher.java` | 仅 `native int launchJVM(String[])` |
| Java 启动器 | `java/net/kdt/pojavlaunch/utils/JREUtils.java` | relocateLibPath/setJavaEnvironment/loadGraphicsLibrary/initJavaRuntime/chdir/VMLauncher.launchJVM |
| 参数 | `java/net/kdt/pojavlaunch/Tools.java` | launchMinecraft/generateLaunchClasspath/getMinecraftJVMArgs/getMinecraftClientArgs/getCacioJavaArgs |

要点：无自定义 classloader——直接把 version manifest 的 mainClass 放 argv 末尾让 JVM 执行。
启动前把 JRE 各 .so 先 dlopen 进进程（initJavaRuntime），保证 libjli 依赖可解析。
v3 用 `-javaagent:MioLibPatcher.jar`（+ `-Dmiolibpatcher.alc10=true`）做字节码兼容。

## 3. GLFW Java stub 与渲染

- Java 侧 stub 源码：`jre_lwjgl3glfw/lwjgl-3.3.3/src/main/java/org/lwjgl/glfw/`
  （GLFW.java + CallbackBridge.java），3.4.1 目录有带 SDL 后端变体。
- 构建：`jre_lwjgl3glfw/lwjgl-3.3.3/build.gradle` 把 stub 与官方 LWJGL 模块合并成
  `lwjgl-<v>-merged-modules.jar`，随启动器 assets/components/lwjgl3/<v>/ 打包。
- 关键导出（Functions 表用 dlsym 解析；以下为 Amethyst 历史名，本项目现对应 `meow*`）：pojavInit/pojavCreateContext/pojavGetCurrentContext/pojavMakeCurrent/pojavSwapBuffers/pojavSwapInterval/pojavSetWindowHint/pojavPumpEvents/pojavStartPumping/pojavStopPumping。
- 库加载：`Library.loadNative(GLFW.class, "org.lwjgl.glfw", "libpojavexec.so", true)`;
  static{} 里 System.loadLibrary("pojavexec") 触发 JNI_OnLoad 记录 runtimeJavaVMPtr。
- glfwCreateWindow → nglfwCreateContext → native pojavCreateContext（返回 context 指针即 window handle）。
- 事件泵送在 MC 每帧 glfwPollEvents：StartPumping→每 window PumpEvents→StopPumping；
  native 在渲染线程上回调 LWJGL thunk（关键：跨 VM 安全回 Java）。

## 4. EGL surface 与 GL 上下文

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

## 5. 输入

- input_bridge_v3.c：JNI_OnLoad 按 VM 分流（第一次=ART 记 dalvikJavaVMPtr；再被 OpenJDK 加载记
  runtimeJavaVMPtr + 装 hook）；CriticalNative 直通（nativeSendChar/Key/CursorPos/MouseButton/
  Scroll/ScreenSize），栈队列（StackQueue）现代 MC，ring buffer 8000 事件。
- Java ART 侧：CallbackBridge.java 发送 + 维护 keyDownBuffer/mouseDownBuffer（游戏侧 glfwGetKey 读）。
- grab：MC glfwSetInputMode(CURSOR_DISABLED) → nativeSetGrabbing → 跨 VM onGrabStateChanged →
  AndroidPointerCapture requestPointerCapture 相对位移 → sendCursorPos。

## 6. 版本相关

- LWJGL 版本选择：version json 依赖 org.lwjgl:lwjgl 版本 ≥341 → 3.4.1 目录，否则 3.3.3
  （1.21.10 = 3.3.3，即 3.3.3 集）。
- 老版本（iLwjglVersion<=299，LWJGL2）才追加 lwjglx.jar（lwjgl2→lwjgl3 兼容），1.21.10 不需要。
- Cacio：Java8 版 caciocavallo/（CTCToolkit+androidnw）；Java9+ caciocavallo17/（cacio-tta 1.18 +
  --add-exports/--add-opens）；老版走 -javaagent，java8 走 Xbootclasspath。AWTCanvasView 720x600
  像素回显（仅安装器 GUI 场景）。

## 7. 移植到鸿蒙时可直接对照的源码清单

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
