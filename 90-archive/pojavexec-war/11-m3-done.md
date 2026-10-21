> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)。

# 11 · M3 达成：关窗退出 + 实时 resize + 独立进程（2026-09-08 实机 ✅）

> 用户实机判定"堪称完美"。配套：resize 50ms 节流；游戏独立进程；主窗"游戏中"防误点。

## 实现摘要（对应 10 号规格）
- 关窗：`meowGlfwRequestClose`（JNI 调 `GLFW.glfwSetWindowShouldClose(JZ)`）→ MC 下帧优雅退出。窗口关闭由 GameWindow XComponent onSurfaceDestroyed 触发（一次幂等）。
- resize：pump diff 驱动（render 线程）：(b) `GLFW.internalWindowSizeChanged(JII)` 通知 MC 重排（HOML jar 签名 `(JII)V`）；(a) `SET_BUFFER_GEOMETRY` + destroy/recreate EGL surface（同 handle，先 destroy 再 create）。**50ms 最小间隔节流**（拖拽高频事件按帧合并；diff 自愈保证终值必达；不阻塞输入事件泵）。
- NAPI：`resizeGameSurface(sid,w,h)` / `requestGameWindowClose()`（jrebridge dlopen/dlsym meow*）。
- 独立进程：GameAbility `process:":game"`（API14+/2in1 支持，同 module 一行生效）→ JVM exit() 只杀游戏进程，主启动器常驻。WindowHolder want 显式加 moduleName='entry'。
- 主窗状态：`GameProcessScanner.isGameProcessRunning()`（appManager.getRunningProcessInformation 免权限，进程名 `:game` 后缀）→ LauncherState.gameRunning @Trace → 版本区 2s 轮询提示"游戏运行中"并禁用启动。

## 日志指纹（正文可搜）
- 关窗：`meow request close`
- resize：`meow resize surface mark WxH` / `java window size upcall WxH` / `egl resize apply WxH`（旧 `pump: monitor size … pending` 已移除）

## 踩坑记录
- implementation agent 漏声明 `g_mid_set_close` → hvigor 编译错（本地 clang 却通过）——**教训：agent 交付后必须主会话 hvigor build 复核**。
- 节流初版用 early-return 会跳过输入事件泵——改为条件合并不 return。
- 背景色实验：给游戏窗/EGL 面设非黑背景色(#DD5051)与渲染打架（颜色诡异）→ 回退保留黑色（不可对游戏渲染面设纯 UI 背景色）。

## 待办：输入透传（临门一脚）
键鼠 → ArkTS 事件 → homl_bridge send_*（已接到我们的 critical_send_*→ring→pump→LWJGL 回调，M1 已就绪）→ 只差 ArkTS 转发层 + 键码映射 + grab/相对位移（LOCK_WINDOW_CURSOR）。
