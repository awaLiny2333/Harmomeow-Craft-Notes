# 08 · M1 移植 + M2 Drop-in 验证（✅ 1.21.10 实机跑通）

> 2026-09-08 00:36 用户实机验证：画面/BGM 完全正常。**HOML 闭源 libpojavexec.so 已下线，自研版顶班。**
>
> ⚠️ 路径为当时快照；现源码在 `libs/meowcraftlib/src/main/cpp/meowcraftbridge/`，产物为 `libmeowcraftbridge.so`（见基线）。

## 交付内容
- 新原生模块 `libs/jrelib/src/main/cpp/meowcraftbridge/`（MeowPojav）：pojav_environ.{h,c} / input_bridge.c / egl_gl.c / meowlog.h（tag=MeowPojav）
- jrelib CMakeLists 新增 `pojavexec` SHARED target（SONAME=libpojavexec.so；链 libhilog_ndk/libnative_window/libEGL；jni.h 取自毕昇 JDK include 无条件注入）
- 删除预编译 asset `libs/jrelib/libs/arm64-v8a/libpojavexec.so`（git 可还原）→ 产物全由自编 CMake 输出
- jrebridge NAPI 新增 `setGameSurface(sid,w,h)`（dlopen/dlsym 自研 `pojavSetSurfaceId`）；d.ts/Index.ets/JreLibModule 同步
- GameWindow：首次 surface 就绪时先 `setGameSurface(sid,w,h)` 再 homl_bridge.surfaceChanged

## 实现要点（对应 05/07）
- env 结构体 0x27228 布局：前段 Amethyst 原样 + 红线槽（0x000 window / 0x27180/88 thunk / 0x271d4/d8 savedW/H）+ 尾段自排；`_Static_assert` 固化偏移
- env_init 构造器：POJAV_ENVIRON 复用/新建（同 HOML）
- 事件 ring：type char=1000/char_mods=1001/key=1005/mouse=1006/scroll=1007；cursor 直写 double；critical_send_* 8 个 + critical_set_stackqueue 导出
- JNI：JNI_OnLoad(JNI_VERSION_1_4) + 7 个 nglfwSet*Callback 存回调槽 + SetShowingWindow + GetCursorPos(+A/JavaCritical) + SetCursorPos + CallbackBridge×3 + RendererInit/VK 桩 + launchJVM 桩
- EGL：eglBindAPI(EGL_OPENGL_API) → 桌面 GL 3.2 context（ES2 兜底）；window surface 用 env+0；无窗 1×1 pbuffer 兜底；直接链 libEGL（不学 HOML dlsym 表）
- **pojavSetSurfaceId(sid,w,h)**：OH_NativeWindow_CreateNativeWindowFromSurfaceId → 写 env+0（补 HOML 缺失环节）+ SET_BUFFER_GEOMETRY

## 实机验证指纹（用户 .logs 00:36）
`pojavSetSurfaceId window=0x5a4b883d80` → `pojavInit (renderer=1 window=同址)` → `created desktop OpenGL 3.2 context` → `EGL window surface created for window 同址` → LWJGL stb/opengl/系统 libGLv4 → zink 帧 → 主菜单正常。
> ⚠️ 排查提示：导出 hilog.txt **不带 tag/domain 列**，搜正文而非 tag（MeowPojav 搜不到属正常）。

## 状态与下一步
- M1+M2 ✅（最小 drop-in：自主替代 libpojavexec.so 这一环达成；保留 homl_bridge）
- 自研 so NEEDED：deviceinfo_ndk/hilog_ndk/native_window/EGL/libc（56KB）
- M3（超越 HOML：关窗退出/键鼠输入/resize）已从"黑箱不可控"变为"自研代码可改"，**是否立项待用户拍板**（范围外：hook/gamepad/clipboard/JavaCritical 惰性等按 M1 约定未做）
