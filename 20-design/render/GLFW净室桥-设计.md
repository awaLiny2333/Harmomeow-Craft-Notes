# 净室 lwjgl GLFW stub + 桥（去 Pojav/LGPL）

> 2026-09-10 立项并落地。目标：把 **lwjgl.jar 的 GLFW overlay**（原取自 Amethyst `jre_lwjgl3glfw`，LGPL/Pojav 系）
> 与 **`libmeowcraftbridge.so`**（原自述 "Port of Amethyst input_bridge_v3.c"）换成**自研净室实现**，
> 只按契约独立编写；两者均已净室重写。顺带把 `android.util.ArrayMap` 换成 `java.util.HashMap` → **连 android/util 一起甩掉**
> （launcher.jar 也就不再需要它）。契约依据：本会话两份行为/接口卷宗 + 源码事实。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 7 条](../../00-current/现状基线.md)。

## 1. 范围
- **❶ GLFW stub（Java overlay）**：`org.lwjgl.glfw.{GLFW, CallbackBridge, Callbacks, GLFWWindowProperties, GLFWNative*}` + `org.lwjgl.opengl.RendererInit` + `GLCapabilities` 两处编辑。
- **❷ 桥（C）**：`libmeowcraftbridge.so` 重写（`meow_environ` / `input_bridge` / `egl_gl`）。
- **不改**：stock LWJGL 8 模块（BSD-3）、3 so、launcher.jar / ArkTS（仅"去掉 android/util"一处）。
- **不做**：gamepad/SDL/CriticalNative/ART 专有；joystick 保留最小空实现即可。

## 2. 净室协议
已读 Amethyst / 我方桥源 → 非严格双团队。纪律：**只按契约独立实现，不复刻其结构、命名、表达**。
契约来源 = 本会话卷宗 + 源事实（Amethyst overlay 仅作行为面；我方桥是我们自己的代码；JGLFW/JCB 的 Java 声明）+ LWJGL/Mojang 公开 API。

## 3. 不可协商契约（摘要）

### 3.1 GLFW stub（Java）
- **静态初始化顺序**：先分配 `keyDownBuffer`(317B)/`mouseDownBuffer`(8B) → `System.loadLibrary("meowcraftbridge")`（触发 `JNI_OnLoad` 缓存两 buffer 地址）→ `nativeInitializeGLFWNativeBridge()` → `Library.loadNative(GLFW.class, "org.lwjgl.glfw", "libmeowcraftbridge.so", true)` 得 SharedLibrary → `Functions` 用 `apiGetFunctionAddress` 解析 **11 个 `meow*`**。
- **13 个 GLFW JNI natives**：`nglfwSet{Char,CharMods,CursorEnter,CursorPos,Key,MouseButton,Scroll}Callback(JJ)J`、`nglfwSetShowingWindow(J)V`、`nativeInitializeGLFWNativeBridge()V`、`internalGetGamepadDataPointer()J`、`nglfwGetCursorPos(J,Ljava/nio/DoubleBuffer;L…;)V`、`nglfwGetCursorPosA(J,[D,[D)V`、`glfwSetCursorPos(JDD)V`。
- **9 个 `CallbackBridge` natives**：`nativeSendData(ZILjava/lang/String;)V`、`nativeSetInputReady(Z)Z`、`nativeClipboard(I[B)Ljava/lang/String;`、`nativeSetGrabbing(Z)V`、`nativeCreateGamepadButtonBuffer()Ljava/nio/ByteBuffer;`、`nativeCreateGamepadAxisBuffer()Ljava/nio/ByteBuffer;`、`nativeEnableGamepadDirectInput()Z`、`nativeGetAndroidDPI()F`、`nativeNotifyLauncher(I[I)Z`。
- **11 个 `meow*` dlsym**（缺一 → 启动即 `apiGetFunctionAddress` 抛错）：`meowInit/meowCreateContext/meowGetCurrentContext/meowMakeCurrent/meowTerminate/meowSetWindowHint/meowSwapBuffers/meowSwapInterval/meowPumpEvents/meowStartPumping/meowStopPumping`。
- **跨边界公有字段**（launcher/桥都碰）：`public static int mGLFWWindowWidth, mGLFWWindowHeight`；`public static final ByteBuffer keyDownBuffer/mouseDownBuffer`。
- **桥 upcall 的 Java 方法**：`internalWindowSizeChanged`（提供 `(JII)V` 与 `(J)V` 两种以兼容；桥会双探测）、`glfwSetWindowShouldClose(JZ)V`。
- **回调**：7 输入类走桥（`memAddressSafe(cb)`→`nglfwSet*Callback`，返回旧指针包成 `GLFWXxxCallback.createSafe`）；其余（error/joystick/monitor/close/… /framebufferSize/windowSize）Java 侧存储；**必须复用 stock LWJGL 的 `GLFWXxxCallback(I)` 接口/类**（互操作边界）。
- **事件 pump**：`glfwPollEvents` → `StartPumping` → 每窗 `PumpEvents(window)` → `StopPumping`（带重入 guard）。
- **`android.util.ArrayMap` → `java.util.HashMap`**（私有字段，可换；换后不再需要 android/util）。
- `GLCapabilities`：取 **上游对应版本 generated**（BSD-3；历史为 `ref/lwjgl3@3.3.3`，现现代单代 `@3.4.3`）**重打 2 处**：① 构造器顶部插 `RendererInit.onCreateCapabilities(provider)`；② 扩展/版本探测改**非短路 `&`**（去掉提前 return，使函数指针仍加载）。
- `RendererInit`（原 `PojavRendererInit` 改名）：`onCreateCapabilities(FunctionProvider)`；gl4es 分支我们的桥 no-op。

### 3.2 桥（C）
- 导出符号名解析（**无 RegisterNatives**）：`JNI_OnLoad`(缓存 JavaVM + 调 `JNI_OnLoadGLFW`) / `JNI_OnLoadGLFW`(缓存 `keyDownBuffer`/`mouseDownBuffer` 地址) + 上面 13+9 个 `Java_*` + `Java_org_lwjgl_opengl_RendererInit_nativeInitGl4esInternals` + `Java_org_lwjgl_vulkan_VK_getVulkanDriverHandle`。
- **11 个 `meow*` C 原型**（注意"少参"约定：LWJGL `invoke*` 会补 `JNIEnv*,jclass`，**勿"修正"arity**）。
- **environ 块**：总大小 `0x27228`，尺寸/偏移 **ABI 冻结**（0x271d4..dc 红线不可放指针；`isInputReady` 默认 1 → 输入不会因 Java 未调而停）。
- **EGL/GL**：desktop GL **3.2**（失败回退 ES2）；surface 来自 `env->window`；建面前 `SET_BUFFER_GEOMETRY`（首帧修正）；resize **先 destroy 旧 surface 再建**（否则 `EGL_BAD_NATIVE_WINDOW`）；swap interval 恒 0；`meowSwapBuffers` 带 resize 自愈。
- **表面注入**：`meowSetSurfaceId(sid,w,h)`（`OH_NativeWindow_CreateNativeWindowFromSurfaceId` + `OH_SURFACE_SOURCE_GAME`）；`meowResizeSurface`（UI 线程只写尺寸镜）。
- **输入**：SPSC ring（8000×20B）+ 最新值槽；`critical_send_*` 生产者（**多线程**：窗口级 filter 回调不在 ArkTS 线程上 ⇒ `meow_ring_push` 用叶锁串行化）；`keyDownBuffer[key-31]` clamp `[0,317)`；`meowGrabDelta/Reset/SetSens` + `meowMouseFilter*` / `meowTouchFilter*` / `meowKeyFilterStart/Stop`（Tab 与 F 行接管，机制见 [`../input/输入-总览.md`](../input/输入-总览.md) §2.1）+ `meowInputKeyTick`；`meowRateGet`。
- **窗口杂项**：`meowGlfwRequestClose`、`meowGetGrabbing`、pump 里 50ms 节流的尺寸 upcall（写 `mGLFWWindowWidth/Height` 再调 `internalWindowSizeChanged`）。

## 4. 文件规划
```
Harmomeow-Craft-Launcher/tools/lwjgl/deltas/overlay/org/lwjgl/glfw/{GLFW,CallbackBridge,Callbacks,GLFWWindowProperties,GLFWNative*}.java   ← 自研
Harmomeow-Craft-Launcher/tools/lwjgl/deltas/overlay/org/lwjgl/opengl/RendererInit.java
Harmomeow-Craft-Launcher/tools/lwjgl/deltas/overlay/org/lwjgl/opengl/GLCapabilities.java   ← 上游 generated + 2 编辑（历史 3.3.3；现现代单代 3.4.3 走 `overlay-3.4.3/`）
Harmomeow-Craft-Launcher/libs/meowcraftlib/src/main/cpp/meowcraftbridge/{meowcraftbridge_environ.h,meowcraftbridge_environ.c,input_bridge.c,egl_gl.c}  ← 重写
```
- `tools/lwjgl/build_lwjgl_jar.sh`：`--overlay` 默认改指我们自己的 `deltas/overlay`；**不再并入 android/util**；`RendererInit` 改名逻辑保留。
- 桥沿用现有 CMake 目标重建（agent 可编）。

## 5. 构建 / 验证
- jar：`javac --release 8` overlay（用户跑）→ 合并 8 模块 → pack → shade → finalize。
- 桥：CMake/ninja（agent 可编）→ 断言导出面（13 GLFW + 9 CB + 11 `meow*`）+ NEEDED/`.note.ohos`。
- 实机 1.21.10：画面 / 输入 / resize / 关窗回归。

## 6. 风险 / 开放点
1. GLFW API 面大（原 1622 行级）——只保证**启动路径 + 输入 + resize/close** 完整，其余可合法 no-op（与原实现一致）。
2. `glfwGetProcAddress` 原抛 `UnsupportedOperationException`；保留该行为或按需。
3. `nativeGetAndroidDPI`=160.0 存疑（GUI scale）；先照旧、回归再看。
4. `GLCapabilities` **必须从对应版本官方 generated 重打**（历史 3.3.3，现现代单代 3.4.3；Amethyst 件是 3.3.0 时代，地址布局不同）。
5. LGPL 判定建议法务复核（我们做的是"契约独立实现"）。

## 7. 里程碑
- [x] 卷宗（2 agent）
- [x] 设计档（本文）
- [x] 自研 GLFW stub（14 文件）+ 桥实现（C 编译链接通过，48 符号）
- [x] 构建/部署 + 实机回归（1.21.10 出画面/输入/resize/关窗）
- [x] digest v16 + 供应链（**lwjgl overlay 与桥 → 源码级/去 LGPL**）+ 记忆

## 8. 达成（2026-09-10）
**lwjgl.jar 的 GLFW overlay 与 `libmeowcraftbridge.so` 均已净室自研**：Java 侧 + 桥的 **Pojav/LGPL 血统清除**。产物（**该文撰写时基线** digest v25；**现役值以 [`assets-digests.txt`](../../30-supply-chain/assets-digests.txt) 为准**）：`lwjgl-3.4.3.jar` `7783219a…`（6185 类；现代单代，`lwjgl-3.3.3.jar` 已移除）、`launcher.jar` `71f1deab…`（20 类，android/util 已去）、`meowcraft_extras.tar.gz` `b76f45f7…`；`EXTRAS_VERSION=20260915-lwjgl-tagname`（v25）。**2026-09-16（v26）**：lwjgl jar 重建（去掉不实的 `Multi-Release`）后上述 digest 已过期。
- 顺带：GLFW stub 载库名直接写死 `meowcraftbridge` → **不再需要 libname 二进制补丁**；`android/util` 从 lwjgl+launcher 双双移除。
- ~~已知（可接受）~~ **已修（2026-09-11）**：`GLCapabilities` 去短路（`||`→`|`）会让 LWJGL 对**每个**版本/扩展都打印
  `[LWJGL] [GL] … an entry point is missing.`（功能无害但误导）；`gen_glcap.py` 增**第 4 项编辑**把纯日志调用
  `reportMissing(...)`→`false`，重生成 overlay 后该刷屏消失（指针仍照常加载）。**已重打 lwjgl jar 生效**（当时重生成两代 overlay；**现现代单代 3.4.3**，旧 `_333` 已移除。**该文撰写时** `EXTRAS_VERSION=20260911-accounts`（现役值见 [`assets-digests.txt`](../../30-supply-chain/assets-digests.txt)）；launcher.jar 于 digest v23 再重打）。
- `meowlog.h`（原名 `pjlog.h`，已改名）hilog tag 已 `MeowPojav` → `MeowBridge`；CMake 注释同步去"源自 Amethyst"。
- 剩余第三方（正规）：上游 LWJGL(BSD-3)、gson(Apache-2.0)、SDL3(zlib)、shaderc(Apache-2.0)、SPIRV-Cross(Apache-2.0)、JRE(外部历史件)。
