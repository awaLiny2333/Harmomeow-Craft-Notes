# 04 · 可行性结论 + 移植/编译规划（pojavexec 大战路线图）

> 综合 01/02/03 三份侦查。状态：规划稿（待用户拍板起步）。
>
> ⚠️ **历史规划稿**：其范围决策"保留 homl_bridge 不动"**已被 Stage B（[`15-stage-b-remove-homl-bridge.md`](15-stage-b-remove-homl-bridge.md)）取代**；现状见 `../../00-current/现状基线.md`。

## 一、可行性结论：能自己编，且路径清晰

1. **源码在手**：Amethyst-Android `jni/` 含 Android 版 pojavexec 完整 C 源码（16 编译单元，Android.mk 全清单），机制（事件环形缓冲/双 VM/JNI_OnLoad/hooks）可整体搬运。
2. **能编出来**：OHOS NDK（BiSheng clang + openharmony musl sysroot）+ 毕昇 JDK 头（jni.h）即可编 C 产物；hvigor CMake 骨架现成（jrelib 增加 target 即可）；现有 HOML 预编译 OHOS `libpojavexec.so` 证明同源桥在 OHOS 能跑。
3. **替换契约已量化**：02 表 (a) 给出强制符号面——A1 JNI 入口、A2 jar 声明 Java_* 全集、A3 pojav* 12 函数指针、A4 homl_bridge UND critical_send_* 族（保留旧桥时）+ A5 可私有化清单。
4. **可裁剪**：Android 独有面集中且可删/换——log.h→hilog shim、ANativeWindow→OHNativeWindow/surfaceId、nsbypass/dlext/AOSP 私有 ABI 整删、ART CriticalNative 双表退化为 noncritical；渲染后端用我们已定案的**系统 libGLv4**（zink/OSMesa/turnip 分支可整段剪掉，egl 走 dlsym 指针表不静态链）。
5. **为什么要做**：HOML 黑箱三兄弟的"关窗不退出 / resize 不跟 / 输入不通"全卡在 pojavexec 语义缺失或行为不透明；自研件 = 打开这些功能 + 摆脱闭源。

## 二、范围决策（用户 2026-09-07 已定：最小 drop-in）
- ✅ **目标 = 且只是**：平替 HOML 的 `libpojavexec.so`，实现这一环的自主替代（行为等价、跑通 1.21.10）。
- ✅ **homl_bridge 保留不动** → 新 so 必须满足 02 表(a) A4（homl_bridge UND：pojav_environ/launchJVM/critical_set_stackqueue/critical_send_{char,char_mods,cursor_pos,key,mouse_button,screen_size,scroll}）。
- ✅ **只做 LWJGL 3.3.3**（不预留 3.4.1/26.x）。
- ⚠️ **最大隐藏风险 = environ 结构布局 ABI**：homl_bridge 通过 UND `pojav_environ` 直接读写字段（surface 注入、尺寸等），若自研 struct 布局与 HOML 不一致 → 内存错乱。M0 之前先做 homl_bridge 反汇编取证（字段偏移 vs Amethyst environ.h 布局）确认可复用 Amethyst 布局（大概率 HOML 亦源自同源头）。
- 部署：产物放 jrelib libs/arm64-v8a（同名 SONAME=libpojavexec.so），先对照保留原 so，验证后删原 so。

## 三、里程碑规划（每步有可验证判据）

### M0 · 冒烟编译（半~1 天）——"能编出来"
- 手工 clang：glfwstub.c（pojav_environ + JNI_OnLoad(JNI_VERSION_1_4) + pojavInit + 2-3 个 nglfw*/CallbackBridge 桩 + log.h shim + 毕昇 jni include）→ libpojavexec.so。
- 判据：readelf 验 `.dynsym` 含 JNI_OnLoad/Java_*/pojav_environ/pojavInit；NEEDED 精简（hilog+c 等）。
- 产出文档：编译命令/头文件清单固化进 03。

### M1 · 源码移植骨架（2-4 天）——"跑得起"
- 搬运 01 判定"照搬/小幅"文件：environ.c/h(类型换 void*/OHNativeWindow)、stdio_is(去 Logger/Exit 换 hilog+nominal_exit 简化)、jre_launcher 精简、jvm_hooks 三件（去 android 头）、bigcoreaffinity、egl_loader+osmesa_loader（去 app_escapeNs）、gl_bridge（EGL 分支保留，desktop GL via BindAPI(EGL_OPENGL_API)）。
- input_bridge_v3 重写：去 ART CriticalNative 双表/探测（退化 noncritical），事件缓冲+pump+GLFW JNI 全保留，CallbackBridge 反向回调若 ArkTS 侧无 Java 对应类则先留桩。
- egl_bridge/loader_dlopen/swap_interval_no_egl：裁剪（GLv4 后端：不搞 OSMesa/zink/turnip/nsbypass/swap_interval AOSP hack）。
- 编进 jrelib CMake（新 target pojavexec，删预编译 so 或改 SO 名并行对照）。
- 判据：link 通过 + .dynsym 符号面 ≥ 02 表(a) A1+A3 全 + A2 核心（12 GLFW + 3 CallbackBridge）；可先不接启动链。

### M2 · Drop-in 替换（2-3 天）——"替代黑箱，行为不变"
- 覆盖 A2 全集 + A4（critical_send_* 与 launchJVM 桩），SONAME=libpojavexec.so。
- 删除预编译 HOML pojavexec.so，启用自编译件，跑 1.21.10。
- 判据（用户日志）：启动画面/BGM 正常、无 UnsatisfiedLinkError、render 走 libGLv4、JNI_OnLoad hook 生效。

### M3 · 超越黑箱：关窗/输入/resize（3-6 天）——"干掉三大遗留"
- 关窗：02 §缺口1 方案 (b) homl_bridge(或新 NAPI) closeWindow → 翻转 Java shouldClose（或 Java 字段注入），MC 走 glfwWindowShouldClose 正常退出 → 关窗退游戏。
- 输入：ArkTS 键鼠 → homl_bridge send_* → critical_send_* → pump → 回调（key/char/mouse/scroll/cursor），验证键盘移动/鼠标视角/点击。
- resize：surfaceChanged 真尺寸 → pojav 尺寸事件 → internalWindowSizeChanged/glfwSetWindowSize 同 handle → 渲染 surface 重建（libGLv4/EGL 路径）。
- 每项独立验证（用户日志），单变量迭代（empirical 铁律）。

### M4 · 硬化与收尾（机动）
- 符号表自动化测试（读 .dynsym vs 02 契约表）；可选 R2（去掉 homl_bridge、输入 NAPI 并入我们的桥）；支持边界决定（D1）落地；文档回写 06/08。

## 四、风险与对策速记
| 风险 | 对策 |
|---|---|
| LWJGL jar 与移植 C 签名细微不匹配 | M1/M2 用 .dynsym 对照 + 真机符号差集测试（读日志 UnsatisfiedLinkError 定位） |
| egl/GLv4 surface 生命周期语义不明 | 单变量实验 + 我们已有 egl_render/GameWindow resize 经验兜底 |
| JNI 回调跨线程（ArkTS 主线程写、渲染线程 pump） | 事件缓冲/原子计数机制本身支持 SPSC；确保 ArkTS NAPI 线程 attach 姿势正确 |
| 渲染线程 vs UI 线程 jclass/jmethodID 混用 | 照抄 Android 原实现的双 VM 槽位设计（dalvik 槽=UI 侧、runtime 槽=JVM 侧），不混 |
| pojav* 内部对 libGLv4 的函数指针表初始化顺序 | pojavInitOpenGL 在 JLI 前由 jre_bridge 预 dlopen libGLv4（现状），移植保持 |

## 五、估算
总工程量 ≈ **1.5~2.5 周（单人逐里程碑实证）**，其中 M0 半天内可验证"自研可行"这一核心问题。
