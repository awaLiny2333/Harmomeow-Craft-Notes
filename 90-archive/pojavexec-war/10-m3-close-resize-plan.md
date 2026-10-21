> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)。

# 10 · M3 关窗 + resize：可执行实现规格（调研定稿）

> 依据 R1（lwjgl.jar Java 机制解码）与 R2（resize 断点/改法侦查）。实现照此执行。

## 一、关窗（让 MC 优雅退出）
- Java 事实：MC 每帧 `glfwWindowShouldClose(handle)` 直接读 `GLFWWindowProperties.shouldClose`（字段直读，无锁）。翻转即退出。
- 推荐路径：C 侧 JNI `CallStaticVoidMethod(org/lwjgl/glfw/GLFW, glfwSetWindowShouldClose, "(JZ)V", handle, true)`。
- handle：Java key = `pojavCreateContext` 返回值（现 M1 返回 `&g_fakeWindowAddress`）；C 侧可靠来源 = `env->showingWindow`（0x27178），回退 `&g_fakeWindowAddress`。
- 新导出（我们自有、可 meow 前缀）：`int meowGlfwRequestClose(void)`——从当前线程拿/附 JNIEnv（JavaVM 已在 env 缓存，见 input_bridge.c JNI_OnLoad），lazy 缓存 class+methodID，调上述方法。

## 二、resize（画面跟随 + MC 感知）
数据流已通：GameWindow onSurfaceChanged → (计划) 自研 NAPI + homl_bridge send_screen_size → `critical_send_screen_size` 写 env savedWidth/Height(0x271d4/d8) + width/height 镜像(0x271dc/e0) + shouldUpdateMonitorSize(0x271e5)。
### (a) 渲染面跟随（render 线程）
- Java 无感，纯鸿蒙侧。`pojavPumpEvents` 每帧 diff：期望 `env->width/height` ≠ 上次已应用 → 执行：
  1. `OH_NativeWindow_NativeWindowHandleOpt(win, SET_BUFFER_GEOMETRY, w, h)`（EGL 建窗前先设好）
  2. 若已存在 EGL surface：`eglMakeCurrent(display, NO,NO,NO)` → `eglDestroySurface` → surface=NO、surfaceWindow=NULL
  3. 复用建 surface 路径（eglCreateWindowSurface，同 env->window handle）→ `eglMakeCurrent` 恢复
  - 教训：**先 destroy 再 create**（同 handle 上重复 create 报 EGL_BAD_NATIVE_WINDOW）。
- 首次建 surface 时也先 SET_BUFFER_GEOMETRY（修“起窗 rect 1280x664 却建 720 高”的既有偏差）。
- 兜底：`pojavSwapBuffers` 顶部同样做一次 diff 自愈（漏事件也不丢）。
### (b) MC 感知（render 线程 pump 内、渲染前）
- Java 入口（HOML 定制 jar）：`GLFW.internalWindowSizeChanged(JII)V` public static —— 内部一次完成：internalChangeMonitorSize(w,h)+glfwSetWindowSize+fire framebuffer/window 回调。
- C：diff 驱动（≠上次已通知）→ `CallStaticVoidMethod(cls, mid, (jlong)env->showingWindow, w, h)`；GetEnv 在 render 线程直接成功。
- 顺序：先 (b) 后 (a)（固定即可）。
- 方法与 class 的缓存：lazy（首次用时 FindClass+GetStaticMethodID+NewGlobalRef），线程安全以简单加锁/一次初始化处理。
### (c) 新 NAPI/ArkTS
- C 新导出：`int meowResizeSurface(int64_t sid, int w, int h);`——若 sid≠env->surfaceId 退化为 pojavSetSurfaceId 全建窗；否则更新 env savedW/H、width/height，log，返回 0（UI 线程只写 env，不碰 EGL/native window）。
- jre_bridge.cpp 增 NAPI：`resizeGameSurface(surfaceId,w,h):boolean`（dlopen/dlsym meowResizeSurface）；`requestGameWindowClose():boolean`（dlopen/dlsym meowGlfwRequestClose）。
- d.ts / Index.ets / JvmLauncher(JreLibModule) 同步；GameWindow：
  - resize 分支（w>0&&h>0，现调 bridge.send_screen_size 处）追加 `jrelib.resizeGameSurface?.(sid, fw, fh)`（send_screen_size 可保留）。
  - 关窗：XComponentController.onSurfaceDestroyed 加回调（参照现有 onSurfaceReady 模式），GameWindow 页在回调里 `import('jrelib').requestGameWindowClose?.()`；GameAbility.onWindowStageDestroy 也可顺带（选一即可，避免重复无害）。

## 三、日志指纹（供实现埋点，正文可搜）
- `screen size -> %d x %d`（已有）
- 新增：(a) `egl resize apply %dx%d` / 重建时复用 `EGL window surface created for window %p`；(b) `java window size upcall %dx%d`；(c) close: `meow request close window=%p`
- 移除/不再期待：`pump: monitor size ... pending (M1: no Java upcall)`

## 四、风险清单（照做）
- 重建前必 destroy；同 handle 不重复 create。
- UI 线程只写 env；EGL/NativeWindow 操作只在 render 线程（pump/swap）。
- diff 驱动幂等（同值 0 成本）；StopPumping 清标志可留（自愈兜底）。
- internalWindowSizeChanged 签名 `(JII)V`（勿用 Amethyst `(J)V`）。
- 新导出名建议 meow 前缀（延续 meowcraftbridge 品牌）。
