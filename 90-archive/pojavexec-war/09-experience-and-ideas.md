# 09 · pojavexec 大战：全经历 + 想法落盘（2026-09-07~08）

> 本文是整场战役的"记忆档案"：做了什么、学到什么、踩了什么、还剩什么想法。
> 供未来接手/续战者快速进入状态。前情见 01-08 各报告。

## 一、战役时间线（复盘）

1. 侦查三连（子 agent 并行）：Amethyst 源码全景 / 接口契约 / OHOS 编译可行性。
2. 决策：最小 drop-in（仅平替 libpojavexec.so；保留 homl_bridge；只做 LWJGL 3.3.3）。
3. M0 冒烟：最小桩一次编出（BiSheng clang + musl sysroot + 毕昇 jni.h），符号面全中。
4. ABI 取证：homl_bridge 只碰 environ 3 处 → 红线槽量化；**不能整抄 Amethyst 尾段**。
5. 握手查实：**两 so 无人写 env+0x000**；HOML 原设计依赖"第三方驱动 dlopen 时写"（随包缺席）。
6. M1 移植 + M2 drop-in 一次成功：自研 so 顶班，1.21.10 实机画面/BGM 正常（日志指纹铁证）。

## 二、核心知识沉淀（每一条都踩过/验过）

### 架构与 ABI
- `pojav_environ` 是 **8B BSS 指针变量**，指向 `calloc(0x27228)` 结构体；构造器 env_init 建后 `setenv("POJAV_ENVIRON")` 供多库共享。
- env 布局红线：0x000(窗口指针,homl 读)、0x27180/0x27188(homl 写 JS 通知 thunk)、0x271d4/d8(savedW/H,homl 写)。**0x271d4..0x271dc 禁放 8B 指针**。
- 事件 ring：`GLFWInputEvent{type,i1..i4}` 20B ×8000；counter@0x018；type char=1000/char_mods=1001/key=1005/mouse=1006/scroll=1007；cursor **不入 ring** 直写 double；send_screen_size 只写 savedW/H+标志。
- LWJGL GLFW stub 全 Java 假窗口；`windowShouldClose` 读 Java 字段（HOML 从不翻转=关窗不退的根源）；keyDown(317B)/mouseDown(8B) 是 Java 分配直缓冲、native 写、Java glfwGetKey 读。
- 渲染窗口：EGL 建窗点在 gl_swap_surface 语义 = 用 `[env+0]` 当 nativeWindow；谁写 env+0 = drop-in 必须自己补。

### 鸿蒙工具链
- **NDK 无 jni.h** → 方案：毕昇 JDK include（现已在仓库内 vendor 到 `pojavexec/include/{jni.h,linux/jni_md.h}`，GPL+CE，免机器绝对路径）。
- 编译：BiSheng clang `--target=aarch64-linux-ohos --sysroot=openharmony/native/sysroot -D__MUSL__`；sysroot 库名带 `.z`（libhilog_ndk.z.so）；EGL/GL 桌面头齐备；EGLNativeWindowType 两种分支需 `(uintptr_t)` 兜底。
- `-Wl,--no-undefined` 默认开：直接调用的函数必须链库或全走指针表。
- hvigor 会自动补 deviceinfo_ndk/unwind；CMake native target 随 App build 一起编并打进 HSP（无手工丢 so）。
- **hvigor 不追踪 libs/ 目录的删除**：删随包 asset 后必须 `devecocli build clean` 再全量，否则 ProcessLibs UP-TO-DATE 打包旧文件。
- 多模块产物：`devecocli build` 不产 jrelib 的 assembleHsp；用 `devecocli run --module entry jrelib` 才产并装。
- 部署顺序铁律：**先 hsp/har 再主 hap**；更新用 `hdc install -r`（保数据）。

### 排查方法（重要）
- **导出的 hilog.txt 不带 tag/domain 列** → 搜"消息正文"而非 tag（曾因 grep MeowPojav 之类 tag 归零而误判；自研模块日志 tag=MeowPojav）。
- 换 so 是否生效看**独有指纹**（我们：pojavSetSurfaceId/`created desktop OpenGL 3.2 context`/EGL window surface…；HOML 无）。
- 子 agent 侦查给"要产出什么表/结论"最有效；编译类粗活丢 general agent 并让它自带 clang 自验。
- 单变量、实证、日志由用户导（禁自抓）。

## 三、当时仓库 so 账（39 个，历史快照；现为 36 = meowjre25 30 + meowlwjgl3 6，见 `../../30-supply-chain/per-so-catalog.md`）
- JRE 运行时 31（libjvm/jli/java/zip/nio/net/…+freetype；JVM 经 OHOS_DL_DIR 按需 dlopen，勿动）
- homl_bridge 家族 8：libhoml_bridge(NAPI 入口) / libdriver_helper、libc++_shared(homl DT_NEEDED) / liblwjgl、liblwjgl_opengl、liblwjgl_stb、libopenal(LWJGL) / libjnidispatch(JNA)
- 自研 CMake 产物：libpojavexec.so（56KB）、libjrebridge.so、entry libmeowassets.so
- 已被替代并删除：HOML libpojavexec.so（git 历史可还原）

## 四、遗留/候选（想法库）
### M3 三大遗留（现在是自研代码，方案草稿）
1. **关窗退出**：Java 侧 windowShouldClose 读 GLFWWindowProperties.shouldClose。方案 A：我们 so 加 `pojavSetWindowShouldClose`，经 JNI 缓存类静态方法调 `glfwSetWindowShouldClose(handle,true)`（需在 JNI_OnLoadGLFW 缓存 class/methodID，同 HOML 原做法）。方案 B：ArkTS GameWindow 关窗(onWindowStageDestroy/onDestroy) → 新 NAPI 通知 → 同上翻转；或干脆整进程退出（同进程内 JVM 无法优雅停，见旧 §7.1）。
2. **键鼠输入**：homl_bridge send_* 已直连我们的 critical_send_*（homl UND 解析到我们的导出）→ ring → pump → LWJGL 回调，**只差 ArkTS 事件转发**（onKeyEvent/鼠标/滚轮 + keycode 映射 FCLKeycode/LWJGLKeycode）。注意 GLFW key 回调的 keyDownBuffer/mouseDownBuffer 写入已实现。
3. **resize**：send_screen_size 已写 savedW/H+标志；需在 pump/NAPI 里"尺寸变化→调用 Java internalWindowSizeChanged(window,w,h)"（HOML 的断点），再让 EGL 侧按新窗口重建 surface（env+0 由 homl_bridge 换窗时已处理）。
### 硬化/自控路线（更远期）
- 去掉 homl_bridge：把 surfaceChanged/输入全部并入我们 so + jrebridge NAPI（当前 homl_bridge 仍是闭源搭档，但依赖面已收敛到 surfaceChanged/send_*）。
- vendored jni 头已完成；可再加 lint/CI：`.dynsym` 契约自动比对（对照 02 表）。
- 事件/pump 单测：脱离真机用 host clang 编桩测 ring。
- 版本带：若要 26.x 需 LWJGL 3.4.1 契约（Java 侧另案）。
- 观察项：MC 26.1 崩溃=API 代差（glfwPlatformSupported 缺失），非本次回归。
### 工程体验备注
- notes 只放容器级 `/Meowcraft/notes/`（不入 git）；本目录 09 即战场全档案。
- 重要结论同步 memory（meowcraft_pojavexec_war_started 持续更新）。
