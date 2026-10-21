> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)。

# 02 · 自研 libpojavexec 接口契约（替换 HOML 版必须满足的符号面）

> 来源：子 agent B 侦查（nm/readelf + jar class 解析，只读）。
> 目标二进制：`libs/jrelib/libs/arm64-v8a/libpojavexec.so`（48000B，HOML 闭源）。
> 契约源：`stuffs/research/misc/jarx/lwjgl.jar`（HOML 定制 LWJGL 3.3.3-snapshot）+ `libhoml_bridge.so`。

ELF：AArch64 ET_DYN，`SONAME=libpojavexec.so`，`BIND_NOW`，NEEDED = libdriver_helper/libace_napi.z/libhilog_ndk.z/libnative_window/libability_{access_control,base_want,runtime}/libc。

## 表 (a)：必须导出的动态符号全集（按谁消费分类）

### A1 JNI 入口（System.loadLibrary 触发）—— 强制
- `JNI_OnLoad`：存 JavaVM* → hookExec(forkAndExec) → installLwjglDlopenHook(RegisterNatives 覆盖 `org/lwjgl/system/linux/DynamicLinkLoader.ndlopen`) → EMUI 缓解（POJAV_EMUI_ITERATOR_MITIGATE 门控）→ 未设 POJAV_SKIP_JNI_GLFW 则 JNI_OnLoadGLFW → 返回 JNI_VERSION_1_4。
- `JNI_OnLoadGLFW`：FindClass("org/lwjgl/glfw/GLFW") + 缓存静态方法/字段 ID + keyDownBuffer/mouseDownBuffer 地址到 environ。

### A2 Java_* / JavaCritical_*（按 jar 声明查找）—— 强制（带 ❌=当前 so 也缺）
**org.lwjgl.glfw.GLFW（jar 声明 12 个）**
- nglfwSet{Char,CharMods,CursorEnter,CursorPos,Key,MouseButton,Scroll}Callback(JJ)J —— 存 cb 指针到 environ 回调槽（pump 分发用）
- nglfwSetShowingWindow(J)V
- nglfwGetCursorPos(J,DoubleBuffer,DoubleBuffer)V / nglfwGetCursorPosA(J[D[D)V（+JavaCritical 变体）
- glfwSetCursorPos(JDD)V
- internalGetGamepadDataPointer()J —— **❌ 当前 so 未导出**

**org.lwjgl.glfw.CallbackBridge（jar 声明 7 个）**
- nativeSetInputReady(Z)Z（+JavaCritical）✅ / nativeClipboard(I[B)String ✅ / nativeSetGrabbing(Z)V ✅
- nativeSendData(ZILjava/lang/String;)V、nativeCreateGamepadButtonBuffer/AxisBuffer()、nativeEnableGamepadDirectInput()Z —— **❌ 当前 so 未导出（休眠缺口）**

**其它**：`Java_org_lwjgl_opengl_RendererInit_nativeInitGl4esInternals(FunctionProvider)V` ✅（GL4ES fbsize 注入，GLCapabilities 引用）；`Java_org_lwjgl_vulkan_VK_getVulkanDriverHandle()J` ✅。

> 反向多出（HOML so 有、本 jar 未声明，自研可省）：nglfwSetFramebufferSizeCallback/nglfwSetWindowSizeCallback/CallbackBridge_getFps/CallbackBridge_nativeSetWindowAttrib。

### A3 pojav* 函数指针 ABI（GLFW$Functions dlsym 逐名取址，缺一即启动崩）—— 强制
| dlsym 名 | 语义 |
|---|---|
| pojavInit | 返回 1（只调 pojavInitOpenGL） |
| pojavCreateContext | (share)J → 在当前 surface 建 EGL/GL 上下文，返回 window 句柄 |
| pojavGetCurrentContext / pojavMakeCurrent | 当前上下文 get/set |
| pojavTerminate | 反初始化 |
| pojavSetWindowHint | (hint,value)V（Java 只特殊处理 VISIBLE） |
| pojavSwapBuffers / pojavSwapInterval | swap / vsync |
| pojavPumpEvents | (window)V 消费 environ 环形缓冲→分发到 A2 回调指针 |
| pojavStartPumping / pojavStopPumping | glfwPollEvents 起止泵 |

私有可省：pojavInitOpenGL（按 POJAV_RENDERER 装桥表）、pojavSetHitResultType、BSS `pojav_environ`。

### A4 homl_bridge → pojavexec 硬链接（保留 HOML 闭源 bridge 时 1:1 必须）—— 强制
UND = `pojav_environ(B)`、`launchJVM`、`critical_set_stackqueue`、`critical_send_char/char_mods/cursor_pos/key/mouse_button/screen_size/scroll`。
→ NAPI send_* 直接写 environ 环形缓冲（20B/条）。新 so 缺任一 → homl_bridge 加载失败。
（launchJVM 是 HOML 桥自带 JLI 入口；本项目实际由 jre_bridge.cpp 启动，但为动态解析仍需导出。）

### A5 可私有化（无外部消费者）
set_gl/osm_bridge_tbl、gl_*/osm_*/virgl_*、egl*/OSMesa 指针表、sendData、noncritical_send_*、hookExec 族、loader_dlopen、maybe_load_vulkan、abort_waiter 等。

## 表 (b)：行为缺口 & “超越 HOML”清单
1. **关窗→游戏退出（§7.1）**：本 jar 的 `windowShouldClose` 全在 Java（读 GLFWWindowProperties.shouldClose 字段），HOML 从不翻转 → 关窗不退。自研件可 (a) 新导出经 internalGetWindow+SetBooleanField 翻转；(b) homl_bridge 加 NAPI closeWindow(handle)；(c) 整进程退出。→ 最干净的“超越”落点。
2. **实时 resize（§7.2）**：Java 侧已有 `internalWindowSizeChanged(JII)V` 就绪回调，断点：(i) surfaceChanged→nativeWindow 重建在渲染后端层；(ii) pojavexec fbsize 事件没进 internalWindowSizeChanged。自研件把“surface 新尺寸→pojav 事件→Java internalWindowSizeChanged/glfwSetWindowSize 同 handle”接通即超越 HOML。
3. **输入未接（§7.3）**：homl_bridge send_* 已就位且依赖 A4；差 ArkTS 事件转发 + pump 分发验证。自研 so 需保证：事件写环形缓冲 → pump 弹事件 → 调 A2 回调；同时刷 keyDownBuffer/mouseDownBuffer/cursor 区。
4. **补缺省符号**：额外导出 A2 中 ❌ 的 5 个（gamepad 4 + internalGetGamepadDataPointer），杜绝 mod 路径 UnsatLink。
5. **保真项**：pojavSetWindowHint 存档并在 createContext 应用 GL 版本；JNI_OnLoad 仍需 forkAndExec/ndlopen hook（生态依赖）。
6. **SONAME**：产物必须名 `libpojavexec.so` 且 SONAME 同名；命中 el1 `libs/arm64` java.library.path 即可。

> 自研替代策略两条路线：**R1 逐符号 drop-in**（严格按上表 A1-A4 实现，先接替黑箱、行为不变，再逐项加超越功能）；**R2 重构式**（保留 A3 pojav* + A1 + 核心 A2，homl_bridge 的输入注入改为我们自己的 NAPI/直写，去掉 A4 对旧桥的绑定）。先做 R1 冒烟 → 渐进重构到 R2。
