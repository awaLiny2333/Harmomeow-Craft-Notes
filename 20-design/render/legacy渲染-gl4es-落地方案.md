# ≤1.16 legacy 正确渲染：GLES + gl4es 路线可行性（2026-09-11 调研）

> 问题：MC ≤1.16 能启动但渲染错乱。能否改用 **OpenGL ES**（鸿蒙支持 GLES 3.2）实现"正确渲染"？
> **结论：已打通（2026-09-11）**——GLES 无固定管线，必须叠 **gl4es**（**自编**上游 ptitSeb/gl4es v1.1.7，弃黑盒 ng_gl4es）；
> **1.16.5 实机渲染正常**（同一 gl4es 亦服务 **1.6.x–1.12.2 legacy**，叠加自编 LWJGL2）。关键：原生 `libGLESv3.so` + **`set_getprocaddress()`**（否则全黑）。§8 为自编实测，§9 为落地结果/坑。
> 相关：[`../../00-current/版本支持边界.md`](../../00-current/版本支持边界.md) §下界/§Backlog 1、[`../../90-archive/鸿蒙OpenGL渲染-早期研究.md`](../../90-archive/鸿蒙OpenGL渲染-早期研究.md)。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 2 条](../../00-current/现状基线.md)。

## 1. 平台/设备事实（2026-09-11 实测）

| 项 | 实测（`stuffs/research/gl/probe_gles.py` / `probe_gl_profile.py`） |
|---|---|
| 桌面 GL（现用） | `libGLv4.so` = **Mesa 25.0.1 Zink（GL→Vulkan）**，GL 4.2 core/compat，GLSL 4.60 |
| **GLES（原生）** | `libGLESv3.so`，**`OpenGL ES 3.2 B312`**，renderer **Maleoon 916**，vendor **HUAWEI**，GLSL ES **3.20** |
| 关键差异 | GLES 是**原生华为驱动**（非 Zink），但 **ES 无固定管线**：`glMatrixMode`/`glEnableClientState`/`glFogfv` 指针全 **NULL** |
| 文档 | HarmonyOS 支持 OpenGL ES 3.2（`API参考/OpenGL_ES/opengles` + 3.2 符号列表） |

**核心**：ES 是"只有 core、没有 compatibility"的 API。MC ≤1.16 用固定管线 → **裸 GLES 跑不了，和 core profile 同一堵墙**。

## 2. 为什么现用路径错乱（回顾）

给 <1.17 请求 **compatibility profile** → 固定管线调用被接受（能启动）→ 但渲染走 **Zink**：
(a) 底层 Maleoon Vulkan 驱动缺 Zink 必需扩展（`EXT_custom_border_color`/`EXT_line_rasterization`），Zink 自报 "incorrect rendering"；
(b) Zink 的 compat/固定管线模拟不完整 → 贴图/文字错乱。

→ **要"正确渲染"，本质是要绕开 Zink 的 compat 路径**。gl4es-on-GLES 正是走"native GLES + 固定管线仿真"，绕过 Zink。

## 3. gl4es 是什么 / 现有资产

- **gl4es**：桌面 **GL 1.x–2.x（含固定管线）→ GLES** 翻译层，用生成式 shader（FPE）仿真固定管线。本项目要的正是这一层。
- **NG-GL4ES**：gl4es 的现代分支/包装（HOML 私有 `hml_ohos/java_runtime/NG-GL4ES`）。
- 现成 OHOS 产物：`stuffs/research/homl/**/libng_gl4es.so`（5.34MB，OHOS ELF，`.note.ohos.ident`，NEEDED=`libhilog_ndk.z.so/libc++_shared.so/libc.so`，BuildID `ab7a332b…`，版本串 `NGG_NG_VERSION 042PATCH`）。
  - **导出 1316 个 `gl*`，固定管线入口为真实实现**（`glFogfv` 988B / `glMatrixMode` 544B / `glEnableClientState` 76B …）；目标 GLES2/3（`LIBGL_ES`/`LIBGL_GL` env），支持到 GLES 3.2。
  - **不碰 OHNativeWindow/EGL**（无、也不导出 `egl*`）：它要求**宿主先建好 EGL context+window surface 并 make current**，再在其上做翻译（Pojav/HOML 模式）。
  - **无源码/无构建脚本**（仓库里 `ref/PojavLauncher_iOS/Natives/external/gl4es/` 只有 iOS 用的 3 个文件，**不是引擎**；真正引擎只有 iOS dylib + 这个黑盒 .so）。许可 **MIT**。
- 对比 **MobileGlues**（另一个 OHOS 产物）：定位是 **GL 4.x → GLES 3.x**（面向 1.17+），固定管线入口多为 4B 派发桩，**不适合 ≤1.16**；且 **LGPL-2.1**、AAR 是 Android 产物不能直用。→ ≤1.16 首选 **gl4es**。

## 4. 我方现状（半成品路径已在，但未接通）

| 组件 | 现状 | 缺口 |
|---|---|---|
| `meowcraftbridge/egl_gl.c` | 有 **GLES2 被动回退**（`EGL_OPENGL_ES2_BIT`，仅桌面 GL 全失败时触发）；只读 `MEOWCRAFT_GL_PROFILE` | 不能**主动**选 GLES；不读 `MEOWCRAFT_RENDERER` |
| `meowcraftbridge_environ.c` `config_renderer` | **硬编码 1** | 应从 env 解析 |
| `overlay/.../opengl/RendererInit.java` | 有分派：`libname.endsWith("libng_gl4es.so")` → `nativeInitGl4esInternals` | 依赖硬编码库名 |
| `input_bridge.c` `nativeInitGl4esInternals` | **空操作** | 需实现 gl4es 初始化（参考 Amethyst `gl_bridge.c`） |
| `meowjrebridge.cpp` | `setenv("MEOWCRAFT_RENDERER")` | **只设不读**（native 决策只读 GL_PROFILE） |
| ArkTS `GameLauncher.glProfileForVersion` | 已有**按 MC 版本分派点**（<1.17→compat） | 只切 profile，不切**库** |
| 随包 natives | 无 gl4es | **gl4es .so 未随包**（硬阻塞） |

## 5. 最小改动集（若决定做）

1. **随包 gl4es**：把 `libng_gl4es.so`（+ 其 `libspirv-cross-c-shared.so`/`libshaderc.so` 依赖，注意与现有 shaderc 件的关系）放入 `libs/meowlwjgls/libs/arm64-v8a/` + `natives.manifest`（`install_natives.sh` 治理）。（**优先自编**：从上游 gl4es 源码 + OHOS NDK 构建，避免黑盒——需引入 gl4es 源码仓到 `ref/`。）
2. **ArkTS 按版本切库**：扩 `glProfileForVersion`/`buildLaunchArgv`，≤1.16（含 **1.6.x–1.12.2 legacy**）→ gl4es（+ GLES），≥1.17 → `libGLv4.so`；两处（`MinecraftLauncher.ets` 的 `-Dorg.lwjgl.opengl.libname`、`GameLauncher` 的 rendererLib）同时切。
3. **native 主动 GLES + gl4es 符号**：`egl_ensure_context()` 在 gl4es 模式下走 `EGL_OPENGL_ES*_BIT` + `eglBindAPI(EGL_OPENGL_ES_API)`；`config_renderer` 从 env 解析。
4. **实现 gl4es JNI 钩子**：`nativeInitGl4esInternals` 由空操作改为真实初始化（尺寸回调注入等）。
5. **一致性自检放行**：`meowjrebridge.cpp` 要求 argv libname == 预 dlopen 的 so，gl4es 版两处都得是 `libng_gl4es.so`。
6. **实机回归**：1.16.5（固定管线）先验；**另验 1.6.x–1.12.2 legacy**（叠加自编 LWJGL2）；确认不破坏 ≥1.17（同一 Zink 路径）。

## 6. 风险 / 代价

- **黑盒 / 供应链**：现成 gl4es 是第三方预编译、无源码/构建脚本（HOML 私有树）→ 违"源码级自编"纪律。要合规须**自编 gl4es**（引入上游源码）。
- **集成长尾**：gl4es 不管 OHNativeWindow/EGL，宿主须先建 GLES context+surface；1316 个 `gl*` 导出 + BIND_NOW → **符号冲突/`glGetError` 指针同一性**风险（26.3 有同类前科）；依赖 `libspirv-cross-c-shared.so`/`libshaderc.so` 动态链。
- **双后端维护**：gl4es 只覆盖 GL 1.x–2.1 → ≥1.17 仍走 Zink ⇒ 两套渲染后端长期并存。
- **性能**：固定管线走 FPE 生成 shader，有额外翻译开销（老版本 MC 历史上可接受）。
- **收益边界**：救 **≤1.16**——**1.13–1.16**（现代格式）+ **1.6.x–1.12.2**（legacy，另需自编 LWJGL2，已完成）。JRE8 实测**非必需**（当前 JRE 25 可跑）。

## 7. 结论

- **"用 GLES 正确渲染" = 必须叠 gl4es**；裸 GLES 无固定管线，与 core profile 一样不可行。
- **技术可行**（已有可运行的 OHOS gl4es 二进制为证；我方代码也留了半成品钩子），但需：随包 gl4es（最好自编）+ 按版本切后端 + native GLES 路径 + JNI 初始化。
- **主要顾虑**是**黑盒/溯源**与**集成长尾**，而非 GL 能力本身。
- 状态：**调研完成 → 已自编落地并打通（见 §8 / §9）**（此前 `版本支持边界.md` Backlog 1 记为"用户暂决定不做"）。

## 8. ★ 自编实测（2026-09-11，成功）

- 源码：`ref/gl4es` = **上游 ptitSeb/gl4es v1.1.7**（`v1.1.6-91-g81547d98`，`version.h` 1.1.7），**MIT**，**不依赖 glslang/SPIRV-Cross**（shader 转换内建 `shaderconv.c`/`fpe_shader.c`）。
  （`ref/NG-GL4ES` 是已 archive 的 fork，引入 3rdparty glslang/SPIRV-Cross，且是黑盒 `libng_gl4es.so` 的出处 → **不使用**。）
- **构建命令**（复用本工程 `Harmomeow-Craft-Launcher/tools/sdl/sdl_ohos.toolchain.cmake` 做 OHOS→Linux 伪装，否则 `src/CMakeLists.txt:140` 会漏编 `glx/*`，丢掉 `glXGetProcAddress`）：
  ```sh
  cmake -G Ninja -S ref/gl4es -B <build> \
    -DCMAKE_TOOLCHAIN_FILE=$PWD/Harmomeow-Craft-Launcher/tools/sdl/sdl_ohos.toolchain.cmake \
    -DNOX11=1 -DNOEGL=1 -DDEFAULT_ES=2 -DNO_INIT_CONSTRUCTOR=1 \
    -DGBM=OFF -DEGL_WRAPPER=OFF -DGLX_STUBS=OFF -DSTATICLIB=OFF \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_POLICY_VERSION_MINIMUM=3.5
  cmake --build <build> -j
  ```
- **产物**：`ref/gl4es/lib/libGL.so.1`：ELF arm64，**`DT_NEEDED` 仅 `libc.so`**，`SONAME=libGL.so.1`，`BIND_NOW`，`.note.ohos.ident`，3.3MB（RelWithDebInfo 未 strip）。**导出固定管线真实现**：`glFogfv`(840B)/`glMatrixMode`(504B)/`glEnableClientState`(84B)/`glBegin`(104B)/`glGetString`(564B)…（`readelf --dyn-syms` 实证）。
- 结论：**可自编替代黑盒 gl4es**；供应链从"外部历史件"升级为"源码级自编"。
- ~~待办~~ **均已完成**：① strip + 构建期断言 —— 已并入 `tools/gl4es/` 构建脚本；② 工具化到 `tools/gl4es/`（路径参数化脚本 + README + 可复现校验）—— **`tools/gl4es/` 已存在**；③ 运行期集成（宿主 GLES context + `initialize_gl4es()`）—— **已落地并实机打通（见 §9）**；产物随包 **`libs/meowlwjgls/libs/arm64-v8a/libgl4es.so` 已存在**。


## 9. 落地结果（2026-09-11，已打通）

- **MC 1.16.5 实机：启动 + 渲染正常**；F3 CPU 行 `20x KirinX90`。**同一 gl4es 也服务 1.6.x–1.12.2 legacy**（叠加自编 LWJGL2：`liblwjgl.so` 的 GL 取址指向 `libgl4es.so`）。
- 集成（已提交主仓 `3299abe` / oshi `34e0506`）：
  - `tools/gl4es/`：自编上游 **v1.1.7**（`NOX11/NOEGL/DEFAULT_ES=2/NO_INIT_CONSTRUCTOR`）；产物 `libgl4es.so` 随包（`natives.manifest` tag `common`）。
  - 桥 `egl_gl.c`：`MEOWCRAFT_RENDERER=gl4es` → 建 **GLES** 上下文（原生 `/system/lib64/libGLESv3.so`）→
    `set_getprocaddress(eglGetProcAddress → dlsym(RTLD_DEFAULT) → dlsym(GLES))` + `set_getmainfbsize` →
    `initialize_gl4es()`（**必须 context 已 current**）；`LIBGL_*` 仅 gl4es 模式设置。
  - ArkTS `RendererPolicy`：**profile 永远按版本**（`<1.17` compat / `≥1.17` core），后端覆盖只切 lib/env；
    逐版本「渲染后端」下拉（推荐 / OpenGLv4 / GL4ES(兼容)）持久化到实例目录内 `<gameRoot>/versions/<id>/.hmmcraft/instance-settings.json`（[`../launch/实例设置存储-方案.md`](../launch/实例设置存储-方案.md) §3.1）。
- **三个关键坑（复现必读）**：
  1. GLES 后端必须用**原生** `/system/lib64/libGLESv3.so`；`ndk/libGLESv2.so` 那条会崩（`glCheckFramebufferStatus` 返回 0）。
  2. **NOEGL 下必须 `set_getprocaddress()`**（gl4es 文档明示）；不设则跳过硬件探测（"unknown renderer"）→ **渲染全黑**。
  3. `initialize_gl4es()` 必须在 GLES context **已 current 之后**调用（桥在 `egl_bind()` 里做）。
- 平台事实：该 2in1 的 GL/GLES 栈 = **Mesa（gallium 25.0.1）+ Zink**（`libEGL_mesa.so`、`const.graphic.gl_to_vk_support=true`），
  桌面 GL 明确是 Zink；gl4es 之所以有效，是它用自己的 FPE 在 GLES 上仿真固定管线，**绕开了 Zink 的 compat 固定管线**。
- **1.16.5 游戏内无文字**：已修（EXP/EXP2 + `density==0` 的恒等雾被渲染成雾色）；取证与两级坑见 [`gl4es固定管线雾-取证与修复.md`](gl4es固定管线雾-取证与修复.md) §11。
