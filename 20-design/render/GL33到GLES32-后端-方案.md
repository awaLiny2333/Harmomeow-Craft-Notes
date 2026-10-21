# GL 3.2/3.3 core → GLES 3.2 后端（一份 `libgl4es.so` 通吃 MC 1.6.x–1.21.x）——方案

> **本文是方案 / 决策记录，不复述现状**。
> **2026-09-22 记录：本方案已实现（r9）。** 一份 `libgl4es.so` 已通吃 ≤1.16/legacy（FPE）与
> 1.17–1.21.x（GL 3.2/3.3 core → 原生 GLES 3.2，env `MEOW_GL3`）；**2026-09-22 用户实测定案：
> 手机（HUAWEI Mate XT，Maleoon 910）1.17.1 / 1.19.4 可玩（r6）、2in1（MateBook Fold）1.21.10 可玩（r9）**
> （技术发现见 §15–§18）。**当前状态（版本 / 产物哈希 / 未验项）见
> [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 26 条；未决 / 受限登记见
> [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §A8 与 §C（C8）。**
> **立项**：2026-09-22（用户目标 = 手机无桌面 GL 时也能跑 1.17–1.21.x）。
> **可行性依据**（本机只读实验，2026-09-22）：工作区根 `stuffs/research/gl4es/EXPERIMENTS-findings.md`
> （着色器链 726/726 + 真机 GLES 3.2 编译/链接/按名解析全通过）；入口全名单见 工作区根
> `stuffs/research/gl4es/gl-entrypoints-<ver>.txt` 与 `stuffs/research/gl4es/gl-entrypoints-summary.md`。
> 相关：[`legacy渲染-gl4es-落地方案.md`](legacy渲染-gl4es-落地方案.md)（≤1.16 的既有 gl4es 路径）、
> [`渲染链-结论.md`](渲染链-结论.md)（两条渲染链）、
> [`../../00-current/版本支持边界.md`](../../00-current/版本支持边界.md)（版本 × LWJGL × GL 后端）。

---

## 0. 目标 / 非目标

**目标**
- **一份 `libgl4es.so`** 同时服务 **≤1.16 与 1.6.x–1.12.2 legacy**（现有 FPE 固定管线路径，**不动**）与 **1.17–1.21.x**（新增 GL 3.2/3.3 core → GLES 3.2 后端）。
- 使**没有 `/system/lib64/libGLv4.so` 的手机**可跑 1.17–1.21.x（走原生 GLES 3.2，而非系统 Zink）；2in1 上作为**可选**后端（默认仍可用系统桌面 GL）。
- 后端由**请求的上下文版本自动分流**：MC 经 GLFW 请求 3.2/3.3 core ⇒ 走新后端；请求 compat / 固定管线 ⇒ 走 FPE。

**非目标**
- MC ≥26.2 的 **Vulkan** 后端、≥26.3 的 **SDL3** 窗口层（各自已有路径，不并入）。
- 重写桌面 GL 的 `compatibility` profile 语义（仍由 FPE 承担）。
- compute / tessellation / geometry shader（**MC 一个都不引用**，入口扫描实证）。
- GL 4.x（MC 只请求 3.2/3.3）。

---

## 1. 架构总览

```
MC（Java：请求 3.2/3.3 core）
   │  LWJGL 3.4.3：GL 函数指针经 GLFW（我方 stub）的 glfwGetProcAddress 解析
   ▼
libgl4es.so ── 按请求的 GL 版本分流 ──┬─ FPE 路径（现有；≤1.16 / legacy）
                                      └─ ★新：CORE 路径（GL 3.2/3.3 → GLES 3.2）
   CORE 路径内部分层：
   A 入口层：156 个入口（MC union）分类转发
   B 拦截层：glShaderSource / glGetString(ii) / glGetIntegerv / 名字类（Attrib·Uniform·Block）
   C 着色器翻译：GLSL 150/330 →（升 450 + auto map）→ SPIR-V →（SPIRV-Cross）→ #version 320 es
   D 反射/名字表：per-program name → (location | binding)
   E 修面：版本串 / 扩展表 / limits；可选 ARB 能力按缺失上报
   ▼ dlopen("/system/lib64/libGLESv3.so")（宿主已建 ES 3.2 上下文）
原生 GLES 3.2（2in1 与手机均具备；2in1 实测 Maleoon 916 / ES 3.2 B312 / ESSL 3.20 / 104 扩展）
```

**复用 / 新建**：复用 gl4es 的 `loader.c`（dlopen GLES）、`gl_lookup.c`、env 机制、扩展表构建、FBO/buffer/texture 对象跟踪，以及既有的"宿主自持 GLES 上下文 + `initialize_gl4es()`"集成；**新写** A–E 五层（FPE/renderlist 一概不用）。

---

## 2. 设计决策（先钉死，避免返工）

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| D1 | 载体 | **fork gl4es 加 CORE 后端**（不另起独立 shim） | 目标"一份 so"；复用 loader/env/集成；旧路径零风险共存 |
| D2 | 着色器翻译 | **SPIR-V 往返**：shaderc(glslang) → SPIR-V → SPIRV-Cross → ESSL 320 | 实测 726/726；自动解决 int/float 隐式转换与精度声明；两库已自编随包 |
| D3 | 名字/位置策略 | **按名**：翻译期确定 loc/binding，MC 的 `glGet*` 一律查表按名返回 | MC 全程按名查询（链接前也可能查）；其给定 index 一律忽略 |
| D4 | 版本/扩展修面 | `glGetString` 报 3.3 / 3.30；合成 MC 需要的 ARB flag；可选 ARB 按缺失上报 | 这是最强杠杆：决定 MC 走哪条代码路径 |
| D5 | 1.21.11 的 DSA / buffer_storage / vertex_attrib_binding | **不上报** ⇒ MC 走经典路径 | 省掉 19 个 ES 3.2 缺失入口；经典路径全部可直转 |
| D6 | KHR_debug | 上报 `GL_KHR_debug`（ES 3.2 里是 core、名字无后缀） | 直转即可；MC 仅调试用 |
| D7 | 与 libshaderc / libspirv-cross 的链接 | **静态并入 `libgl4es.so`** | 保不变量"gl4es `DT_NEEDED` 仅 libc"；避免打包复杂度；代价 = 体积（约 +11 MB，可裁语言后端） |
| D8 | glthread / GL guard | CORE 路径**不启用**（glthread 是 Mesa/Zink 特性，原生 GLES 无） | 需实测确认（R3）；GL guard 仍只服务桌面 GL 路径 |
| D9 | `MEOW_MASK_EXTENSIONS` | CORE 路径**默认不屏蔽 compute**，但保留机制备用 | 1.21.1 + Flywheel 崩溃"链 A"是否在 GLES 复现须实测（R3） |
| D10 | 着色器缓存 | 两级：per-program 内存缓存 + ESSL 文本落盘缓存（可选） | MC 启动期编译上百 program（含 `#ifdef` 变体） |
| D11 | 失败兜底 | 翻译失败 ⇒ 记日志 + 让 MC 收到 compile 失败（不静默）；env 可切"原文直通"（诊断） | 可诊断；避免"看着能跑其实全错" |
| D12 | 后端档位/默认 | 手机：`≥1.17` 默认走 **gl4es-core（GLES）**；2in1：保留系统桌面 GL 为默认，gl4es-core 作可选档；上**设备能力门** | 与 `已知限制与待解.md` §A8 的重开条件一致 |

---

## 3. GL 入口映射（核心工作表）

**数据来源**（本机实测）：工作区根 `stuffs/research/gl4es/gl-entrypoints-<ver>.txt` 与 `stuffs/research/gl4es/gl-entrypoints-summary.md`。
计数：1.17.1 = 100 ｜ 1.19.4 = 107 ｜ 1.21.1 = 107（**与 1.19.4 完全相同**）｜ 1.21.11 = 124 ｜ **union = 156**。
清单里混有 **LWJGL Java 便捷方法**（`glGetInteger`/`glGetFloat`/`glGetShaderi`/`glGetProgrami`/`glGetQueryObjecti`/`glGetShaderInfoLog`/`glGetProgramInfoLog` 的便捷重载）——shim **只需导出原生名**（`glGetIntegerv`/`glGetShaderiv`/`glGetProgramiv`/`glGetQueryObjectuiv`…），便捷方法在 Java 侧解析。

### 3.1 分类规则与具体归属

| 类 | 含义 | 处置 | 规模 |
|---|---|---|---|
| **A 直转** | ES 3.2 同名同义 | 表驱动 `dlsym` 转发（统一 trampoline） | **约 130 个**（union 主体） |
| **B 微修转发** | 名字/参数微差 | 小 wrapper | 4 个：`glClearDepth→glClearDepthf`、`glGetFloat→glGetFloatv`、`glDrawBuffer→glDrawBuffers`、`glMapBuffer→glMapBufferRange` |
| **C 需模拟** | ES 无对应 | 自实现或降级 | 3 个：`glGetTexImage`（FBO + `glReadPixels`）、`glPolygonMode`（存状态；线框可不实现）、`glDrawPixels`（stub；疑为死引用，须确认） |
| **D 拦截** | 语义需改写 | 见 §4/§5/§6 | 见 §3.2 |
| **E 上报缺失** | 不列该 ARB ⇒ MC 走经典路径 | 扩展表不列 | 6 类：`ARB_direct_state_access`(11 调用)、`ARB_buffer_storage`(1)、`ARB_vertex_attrib_binding`(4)、`EXT_debug_label`(1)、`ARB_debug_output`(2)、`ARB_timer_query`(64-bit) |
| **F 调试直转** | ES 3.2 core（KHR_debug） | 直转 | 5 个：`glDebugMessageCallback`/`Control`、`glPush`/`PopDebugGroup`、`glObjectLabel` |

### 3.2 D 拦截层清单（必须亲手改写）

| 入口 | 为什么拦 | 做什么 |
|---|---|---|
| `glShaderSource` / `nglShaderSource` | MC 送 GLSL 150/330 desktop | 走 §4 翻译管线，交 ESSL 320 给真 GLES |
| `glCompileShader` / `glGetShaderiv` / `glGetShaderInfoLog` | 状态与日志要与翻译一致 | 记录翻译期错误；`GL_COMPILE_STATUS` 返回真 GLES 结果；日志合并 |
| `glCreateProgram`…`glLinkProgram` / `glGetProgramiv` / `glGetProgramInfoLog` | 同上 + 生成名字表 | 链接后固化 §5 名字表 |
| `glBindAttribLocation` / `glGetAttribLocation` | MC 链接前指定/查询 attrib 名 | 忽略其 index；按名返回自分配 location |
| `glGetUniformLocation` | MC 按名取 uniform | 查名字表（含数组/结构体成员别名） |
| `glGetUniformBlockIndex` / `glUniformBlockBinding` / `glGetActiveUniformBlockName` | UBO 按块名 | 查名字表 + 转发 binding |
| `glGetString` / `glGetStringi` / `glGetIntegerv` / `glGetIntegeri_v` | 版本/扩展/limits 决定 MC 路径 | §6 修面 |
| `glGetError` | 防把 wrapper 噪声抛给 MC | §6.4 |
| B 类各入口 | — | §3.1 |

### 3.3 关键版本差异（决定测试矩阵）
- **1.19.4 ≡ 1.21.1**（GL 面完全相同）⇒ 两者可共用一套验证。
- **1.21.11**：新增 56、移除 31。移除大头（`glUniform*fv/iv`、`glUniformMatrix*fv`、`glGetAttribLocation`、`glStencil*`、`glMapBuffer`、`glGetTexImage`、`glDrawPixels`、renderbuffer 族）说明其渲染管线**换了机制**（UBO 上传 + 可选 DSA）：**1.17–1.21.1 的 uniform 走 `glUniformMatrix4fv` 等，1.21.11 走 UBO buffer**。
- ⇒ 重点覆盖 **1.21.1（普通 uniform 世代）** 与 **1.21.11（UBO 世代）** 两端，中间版本风险低。

---

## 4. 着色器翻译管线

**输入**：`glShaderSource` 收到的源码 —— `#moj_import` 已由 MC 自己展开、程序 `#define` 已注入（`#version 150/330`）。

**步骤**
1. 记录源码原文（诊断用）与 program/shader 关联（vsh/fsh 同名 program 用于名字统一）。
2. **预处理**：`#version 150|330` → `#version 450`（330 不允许 varying 的 `layout(location)` 与 UBO 的 `layout(binding)`）；保证 `#version` 是首行。
3. **编译到 SPIR-V**：用 **shaderc C API**（非 CLI）：`shaderc_compile_into_spv` + `shaderc_compile_options_set_auto_map_locations` / `set_auto_map_bindings` + `set_target_env(open_gl)`。
   - **不在 GLSL 文本里手写 location/binding**（实验中手动注入只为证明可行；生产用 auto-map 更稳，且 auto-map 结果即名字表来源）。
4. **SPIR-V → ESSL 320**：SPIRV-Cross C API（`spvc_*`），目标 ES / version 320；同时用其**反射**导出名字表（§5）。
5. 把 ESSL 320 交给真 GLES 的 `glShaderSource`/`glCompileShader`；结果与日志回给 MC（D11）。
6. **缓存**：按 (stage, 源码 hash) 缓存翻译产物 + ESSL 文本。

**已验证（沿用）**：① `#moj_import` 由 MC 展开（含 include-once 与"剥被包含文件的 `#version`"）；② 译文**UBO 块名 / 采样器名 / 普通 uniform 名逐名保留**（SPIRV-Cross 只改 UBO **实例名**为 `_NN`，块名保留）；③ 1.17.1(150)…1.21.11(330) 共 726 单元 0 失败；④ 真机 ES 3.2 上编译+链接 OK，且 `glGetUniformBlockIndex`/`glGetUniformLocation` 按名可解析。

**风险与兜底**：SPIRV-Cross 的 ESSL 输出在**非 Maleoon 驱动**（手机）上有待实测（R2）；提供"翻译失败 → 原文直通"env（诊断）与"退回 FPE / 桌面 GL"的档位切换。

---

## 5. 名字/位置映射层

**要建的表**（per program）：
```
attrs[]    : name -> location     # 顶点输入
varyings[] : name -> location     # vsh out / fsh in（同号）
fragOut[]  : name -> location
uniforms[] : name -> location     # 非不透明 uniform
blocks[]   : blockName -> binding # UBO
samplers[] : name -> binding      # 不透明 uniform
```
**填充时机**：翻译期（auto-map + SPIRV-Cross 反射）即得；`glGetUniformLocation` 等可能早于 link 被调用 ⇒ 表在 `glCompileShader` 阶段按 stage 暂存、link 时按 program 合并。

**语义**
- `glBindAttribLocation(p, idx, name)`：记录 `name`、忽略 `idx`（MC 的 want-index 与我们的 location 不同，以**名**为准）。
- `glGetAttribLocation(p, name)`：返回表内 location；未命中返回 `-1`（与 GL 语义一致）。
- `glGetUniformLocation(p, name)`：查表；**须处理数组名（`Foo[0]`）与结构体成员（`inst.Member`）**——SPIRV-Cross 会保留成员名但**改 UBO 实例名**（`inst`→`_NN`）⇒ **必须做别名映射**（或在反射里直接取成员名）。
  - ⚠️ **本层最易踩的坑**（实验已观察到）。缓解：用 SPIRV-Cross 的 rename 接口把实例名改回原名，或建立别名表。
- `glUniformBlockBinding(p, idx, binding)`：记下 MC 要的 binding，绑定/上传时沿用（或直接透传）。
- `glGetActiveUniformBlockName`：从表反查。

---

## 6. 能力/版本/扩展修面

### 6.1 版本与 GLSL
`GL_VERSION` = 3.3、`GL_SHADING_LANGUAGE_VERSION` = 3.30、`GL_MAJOR/MINOR_VERSION` = 3/3；`GL_RENDERER`/`GL_VENDOR` 透传设备真值（排障）。

### 6.2 扩展表
- 以 **ES 3.2 真实扩展表**打底（2in1 实测 104 项）。
- **名字对齐**：把 MC 检查的 ARB flag 与 ES 扩展对齐（如 ES 的 `EXT_disjoint_timer_query` ⇒ 让 MC 认为 timer query 可用；报 `GL_KHR_debug`）。
- **按缺失上报**（D5）：**不列** `ARB_direct_state_access` / `ARB_buffer_storage` / `ARB_vertex_attrib_binding` / `EXT_debug_label` / `ARB_debug_output` / `ARB_timer_query`。
- 与项目既有纪律一致：**只做"真→假"、不伪造**；此处 = 按 ES 真相 + 有意的可用性裁剪。

### 6.3 limits
`GL_MAX_*` 以真 ES 值透传；核对 MC 用于判路径的项（`GL_MAX_VERTEX_ATTRIBS`、`GL_MAX_TEXTURE_SIZE`、`GL_NUM_EXTENSIONS`、`GL_MAX_COLOR_ATTACHMENTS`）；我们不提供的能力，把对应 limit 报 0。

### 6.4 `glGetError`
建议：**透传真 GLES 错误**（MC 能看到真实错误）+ 在 wrapper 内部先 clear 自身产生的错误（否则 MC 因我们的噪声误判）。

---

## 7. 集成（ArkTS / 桥 / 打包）

1. **ArkTS `RendererPolicy`**：扩展后端档（gl4es 增加 core 能力，或新档 `gl4es-core`）；**加设备能力门**（`libGLv4.so` 存在性 + `devicetype`）——既是 §A8 的重开条件，也是本后端落点；手机 `≥1.17` 默认落 gl4es-core。
2. **`MinecraftLauncher`**：`-Dorg.lwjgl.opengl.libname=libgl4es.so`（沿用现有 gl4es 机制）；不注入额外 env。
3. **桥 `egl_gl.c`**：gl4es 模式需能建 **ES 3.2** 上下文（现为 ES2）。新增 `LIBGL_ES=3` 分支：`EGL_CONTEXT_CLIENT_VERSION=3` + `EGL_CONTEXT_MINOR_VERSION=2`；`eglBindAPI(EGL_OPENGL_ES_API)`；`initialize_gl4es()` 时序不变（context current 之后）。
4. **分流信号**：桥在 `JLI_Launch` 前 `setenv("MEOWCRAFT_GL_PROFILE", "core|compat")`（**已有**）⇒ gl4es 据此选 CORE / FPE。
5. **打包**：`libgl4es.so` 随包（`libs/meowlwjgls/libs/arm64-v8a/`，`natives.manifest` tag `common`）；**静态并入** glslang/SPIRV-Cross（D7）。
6. **UI**：逐版本「渲染后端」下拉增/改档位；文案走 `resources/base/element/string.json`。
7. **★ LWJGL 的 GL 取址路径（易漏的承重点）**：MC ≤1.21.x 用 **GLFW**，其 GL 函数指针经 **`GLFW.glfwGetProcAddress`**（= 我方 GLFW 净室 stub / 桥）解析，`-Dorg.lwjgl.opengl.libname` 只是库名/兜底 ⇒ 必须在 stub 的 `glfwGetProcAddress` 让 CORE 路径解析到新后端入口（现状解析到 guard / `libGLv4`）。
   - 同族：`nglShaderSource`（`GL20C`）等"函数指针变体"在 Java 侧最终调用的仍是原生名 `glShaderSource` ⇒ shim 只需导出原生名。
   - 26.3+ 走 SDL（`SDL_GL_GetProcAddress`）——不在本方案范围。
   - 回归点：切换后确认 `glfwGetProcAddress("glTexImage2D")` 等返回 shim 地址（日志自证）。

---

## 8. 构建与工具链

- **gl4es fork**：在 `tools/gl4es/` 现有脚本（`NOX11=1 NOEGL=1 NO_INIT_CONSTRUCTOR=1`）上**新增 CORE 后端源与开关**（如 `-DMEOW_CORE_BACKEND=ON`）；`DEFAULT_ES` 需支持 3。
- **着色器翻译依赖（落地口径）**：实现**并未**静态并入 —— `libgl4es.so` 在**运行期 `dlopen`** 与它**同目录**的 `libshaderc.so` + `libspirv-cross.so`（随包在 `meowjre` HSP 的 `libs/arm64/`，两者均已登记 `natives.manifest`；自编配方见 `tools/shaderc/`）⇒ 自身 `DT_NEEDED` 仍仅 `libc.so`。（落地改 dlopen：产物更小，且与既有 MC 26.3 的 LWJGL shaderc/spvc 路径**共用同一对库**。）
  - ⚠️ 构建期断言（沿用现有做法）：`DT_NEEDED` 白名单**保持不变**；固定管线入口 + 新增 CORE 入口都在；体积记录。
- **可复现**：同 tag / SDK / 路径下 ≥2 次干净重建 + `cmp` 逐字节（项目铁律）。
- **本机 host 工具**（离线回归）：用 hnp clang（见记忆 `meowcraft_shell_native_build_run_caps`）。

---

## 9. 里程碑与工作量粗估

> **粗估（单人，2in1 先跑通）**：M0 0.5d · M1 2–3d · M2 3–5d · M3 2–3d · M4 3–5d · M5 3–5d · M6 1–2d · M7 1d · M8 1d
> ⇒ **合计约 3–5 周**（首次跑通 vanilla）；手机适配与驱动边界（R2）可能再加 1 周。
> **A 类约 130 个直转入口用"表驱动 / 宏生成"**，勿手写；只有 B/C/D 类写代码。

| # | 里程碑 | 内容 | 验收判据 |
|---|---|---|---|
| **M0** | 前置探针 | ①手机 GLES 版本/扩展面；②手机 ES 3.2 上编译 MC 译文样例 | 手机报 ES 3.2 + 所需扩展；样例编译 OK |
| **M1** | fork 骨架 + 分流 | CORE 后端框架；A 类直转；版本修面；桥 ES 3.2 上下文 | gl4es-core 起 1.17.1 不崩、能建上下文、日志见修面 |
| **M2** | 着色器翻译接入 | `glShaderSource` 拦截 + shaderc/SPIRV-Cross + 缓存 | 1.17.1 core shaders 全部翻译成功（对照 726/726 基线） |
| **M3** | 名字映射层 | §5 全表 + 实例名别名 | `glGetUniformLocation`/`BlockIndex`/`AttribLocation` 与 MC 期望一致 |
| **M4** | 1.17.1 上机跑通 | B/C/D 类补齐 | 进世界（2in1 + 手机），文字/贴图正确 |
| **M5** | 1.21.11 上机跑通 | UBO/fence/sampler/instancing 世代 | 进世界；F3 正常；无致命崩溃 |
| **M6** | 档位/设备门/UI | §7 全部 + 能力门 | 手机默认落 core；2in1 可选；无桌面 GL 时不再短时闪退 |
| **M7** | 回归 ≤1.16 / legacy | 确认 FPE 路径零回归 | 1.6.4 / 1.7.10 / 1.8.9 / 1.12.2 / 1.16.5 与立项前一致 |
| **M8** | 打包 / 复现 / 文档 | 体积；notes 回写 | 逐字节可复现；`现状基线` §5 第 26 条 与 `已知限制与待解.md` §A8 回写 |

---

## 10. 验收 / 回归矩阵

| MC | 世代 | 2in1 | 手机 | 判据 |
|---|---|---|---|---|
| 1.6.4 / 1.7.10 / 1.8.9 / 1.12.2 | legacy(FPE) | 回归 | — | 与立项前一致 |
| 1.16.5 | gl4es(FPE) | 回归 | — | 同上 |
| 1.17.1 / 1.18.2 / 1.19.4 / 1.20.6 | core 3.2 / 普通 uniform | ✓ | ✓ | 进世界 |
| 1.21.1 | core 3.2 / 普通 uniform | ✓ | ✓ | 进世界 |
| 1.21.10 / 1.21.11 | core 3.3 / UBO | ✓ | ✓ | 进世界 |

> **2026-09-22 实测（用户 = 项目拥有者）**：core 后端设计面（MC 1.17–1.21.x）在 **2in1（MateBook Fold）** 与 **手机（HUAWEI Mate XT，Maleoon 910 / Kirin 9010，r10）** 两台设备上均已实测可玩 —— 2in1：1.17.1 / 1.19.4 / 1.20.6 / 1.21.10 ✓、1.6.4 legacy ✓ 无回归；手机：1.17.1 / 1.19.4 / 1.20.6 / 1.21.10 ✓（1.20.6 / 1.21.10 为手机首次；用户自测，未导出 logs）。仍未验：1.18.x、1.20.x 其余、1.21.x 其余（含 1.21.11）、性能未测。

**统一判据**：进主菜单 → 进世界 → 无致命崩溃 → F3 可读帧率 → 文字/HUD/贴图正确 → 长时间运行无丢器件类错误。
**方法**：`devecocli build --modules entry meowjre` + `run`（先 HSP 后 entry）；**实机 UI 交互归用户、日志由用户导出**（项目铁律）。

---

## 11. 风险登记

| # | 风险 | 影响 | 缓解 | 重开条件 |
|---|---|---|---|---|
| R1 | 翻译开销 / UBO 上传路径慢 | 帧率 | 缓存；仅 core 路径启用；先测基线 | 实测低于可玩线 |
| R2 | **非 Maleoon 驱动**（手机 GLES）的 ESSL 兼容性未知 | 编译失败 / 花屏 | **M0 先探**（手机跑探针 + 编译样例） | 手机实测不通过 |
| R3 | 1.21.1 + Flywheel 崩溃"链 A"（厂商着色器编译器）是否在 GLES 路径复现 | 崩溃 | 实测；若复现则复用 `MEOW_MASK_EXTENSIONS`（D9） | 出现即启用屏蔽清单 |
| R4 | SPIRV-Cross 改 UBO **实例名** | uniform 取不到 | §5 别名映射 / rename 接口 | 出现取不到即修 |
| R5 | MC `GLCapabilities` 对可选 ARB 的探测 | 走到我们没有的路径 | D4/D5 按缺失上报 | 出现 `UnsatisfiedLinkError` / 黑屏 |
| R6 | gl4es 原有 1235 个导出与新入口冲突/重名 | 链接/覆盖 | fork 内统一符号表（两路径入口并存） | 出现覆盖即整理 |
| R7 | `#ifdef` 变体多 ⇒ 首次进世界卡顿 | 体验 | 缓存（D10）+ 预编译 | 卡顿不可接受 |
| R8 | 体积（原估静态并入约 +11 MB；**落地改为随包另两个 .so**，见 §8） | 包体 | `--gc-sections` + 裁 glslang 语言后端 | 包体超限 |

---

## 12. 与现有机制 / 文档的关系

- **glthread / GL guard**：CORE 路径不适用（原生 GLES 无 Mesa glthread）——R3 实测确认后注明。
- **`MEOW_MASK_EXTENSIONS`**：CORE 路径默认不屏蔽，机制保留（R3）。
- **运行时环境变量清单**：新增开关（如 `MEOW_GL3_TRANSLATE` / `MEOW_GL3_PASSTHROUGH`）须登记进 [`../../00-current/运行时环境变量.md`](../../00-current/运行时环境变量.md)（唯一清单）。
- **不改的前提**：`-Duser.dir` / `--gameDir` / 版本隔离 / 既有 GL 环境链**不动**；CORE 路径只替换"GL 提供者"。

---

## 13. 交付物清单

**主仓代码**
- `libs/meowcraftlib/src/main/cpp/meowcraftbridge/glcore/`（新）：入口层 A/B/C、拦截层 D、修面 E、名字表、着色器翻译封装
- `libs/meowcraftlib/src/main/cpp/meowcraftbridge/egl_gl.c`（改）：ES 3.2 上下文分支
- `libs/meowcraftlib/src/main/cpp/meowcraftbridge/input_bridge.c` 或 `meowcraftbridge_environ.c`（改）：GLFW `glfwGetProcAddress` 在 CORE 模式解析到 `libgl4es.so`（§7.7；预 dlopen 的 `RENDERER_LIB` 同步切）
- `libs/meowcraftlib/src/main/cpp/meowjrebridge/meowjrebridge.cpp`（改）：env 分流
- `libs/meowcraftlib/Index.ets` + `types/libmeowjrebridge/Index.d.ts`（新增 bridge 方法须**六处齐全**）
- ArkTS：`common/data/RendererPolicy.ets`、`common/data/MinecraftLauncher.ets`、`components/GameVersionsView.ets`、`components/AdvancedOptionsView.ets`、`resources/base/element/string.json`

**主仓工具**
- `tools/gl4es/`（改）：加 CORE 后端（delta `deltas/glcore`；**开关是运行期 env `MEOW_GL3`，非编译期宏**）+ 运行期 `dlopen` 同目录 shaderc/spirv-cross（见 §8）+ 构建期断言

**工作区（已就绪，作为本方案依据）**
- 工作区根 `stuffs/research/gl4es/`：`stuffs/research/gl4es/EXPERIMENTS-findings.md`（实验结论）、`stuffs/research/gl4es/PLAN-gl33-to-gles32-backend.md`（本方案工作版）、`stuffs/research/gl4es/gl4es-specs-capability-audit.md`、`stuffs/research/gl4es/mc-1.17-1.21-gl-requirements.md`、`stuffs/research/gl4es/phone-gl-alternatives.md`、`stuffs/research/gl4es/gl-entrypoints-*.txt`、`stuffs/research/gl4es/gl-entrypoints-summary.md`、`stuffs/research/gl4es/shader-test/run_chain4.py`、`stuffs/research/gl4es/shader-test/probe_gles_compile.py`、`stuffs/research/gl4es/tb/`（host 工具）

---

## 14. 附录：已核事实（沿用，勿重测）

1. 着色器链：`#version 150|330` →（升 450 + auto layout/binding）→ SPIR-V → ESSL 320：**726/726**（1.17.1 / 1.18.2 / 1.19.4 / 1.20.6 / 1.21.1 = 150；1.21.10 / 1.21.11 = 330）。
2. 名字保留：UBO 块名 15–17、采样器名 17–20、普通 uniform 名；SPIRV-Cross 只改 UBO 实例名。
3. 真机 ES 3.2：译文 vsh+fsh 编译+链接 OK；`glGetUniformBlockIndex` / `glGetUniformLocation` 按名可解析。
4. 设备 ES 3.2：`ES 3.2 B312 / Maleoon 916 / ESSL 3.20 / 104 扩展`（含 timer query、buffer storage、texture buffer、BGRA、sRGB、gpu_shader5）。
5. MC 入口：union 156；1.19.4 ≡ 1.21.1；1.21.11 新增 DSA / buffer_storage / vertex_attrib_binding（可缺失上报）并改用 UBO。
6. 本 shell 可编译+运行 hnp-clang 产物；SDK 工具链产物 exec/dlopen 一律 EPERM。

---

## 15. 2026-09-22 记录：手机端 r6 —— ES 非法 texImage 三元组与深度附件

> 本节为**带日期的记录**（技术发现 + delta + 验证结论），不复述现状；活状态见
> [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 26 条、
> [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §A8。

### 15.1 技术发现：ES 非法的 texImage 三元组

- **现象**：手机（原生 GLES 3.2，无桌面 GL）上 1.17.1 / 1.19.4 走 core 后端，启动到
  `Description: Initializing game` 崩；抛 `GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT`，来自 RenderTarget/TextureTarget
  的完整性检查（混淆名 `efr.b:167` / `doy.b:167`）。崩前唯一一条 HIGH GL 报错文案：
  `Error:glTexEnvx::<format>, <type> and <internalformat> are not a valid combination`。
- **根因**：MC **1.17.1 与 1.19.4** 建 render target 的**深度附件**都用同一条
  `glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT(0x1902), w, h, 0, GL_DEPTH_COMPONENT, GL_FLOAT(0x1406), NULL)`
  （**字节码核实**：1.17.1 `dov`/`doy`、1.19.4 `efo`/`efr`）。该三元组 **桌面 GL 合法、ES 3.2 非法**（ES 要求 sized internalformat）。
- **为什么桌面栈不炸**：电脑侧 2000 行级 log 里该 GL 报错**一条都没有** —— Mesa/桌面栈宽容 ⇒ 附件建得上；
  手机 ES 栈严格 ⇒ 拒绝 ⇒ 无深度附件 ⇒ FBO 不完整 ⇒ 崩。⇒ **设备差异类，不是版本差异类**。
- **判据 / 指纹**：`tag=2026-09-22-r6` + `ifmt=0x1902 fmt=0x1902 type=0x1406 -> 0x8cac` + `Sound engine started`，
  无 `OpenGL debug message`、无 crash report。

### 15.2 r6 delta（`主仓 tools/gl4es/deltas/glcore/src/gl/meowcore/meowcore.c`）

- 新增 `mc_es_depth_internalformat`：把**桌面合法 / ES 非法**的 depth(stencil) 三元组改写为 sized internalformat；
  改 `mc_glTexImage2D`（**仅在非法时改写**）；另加防御性 `mc_glTexStorage2D` / `mc_glRenderbufferStorage`
  （两类 MC 均无调用点）。
- 映射表：`DEPTH_COMPONENT+FLOAT→DEPTH_COMPONENT32F(0x8cac)`、`+UINT→DEPTH_COMPONENT24`、`+USHORT→DEPTH_COMPONENT16`、
  `DEPTH_STENCIL+U32_8→DEPTH24_STENCIL8`、`+FLOAT32_UINT_24_8_REV→DEPTH32F_STENCIL8`。
- **未新增任何 env 开关**（故 [`../../00-current/运行时环境变量.md`](../../00-current/运行时环境变量.md) 本次未变）。
- 低频诊断行 `[meowcore] texImage2D remap: target=… ifmt=… fmt=… type=… -> …`（每次进程个位数条）；
  `MC_BUILD_TAG` = `2026-09-22-r6 (ES-legal tex images)`。
- 产物 `stuffs/research/gl4es/out/libgl4es.so`（**1,247,512 B**，sha256 `6c9065bb…`；`DT_NEEDED` 仅 `libc.so`、
  无 RUNPATH/RPATH、SONAME `libGL.so.1`）；随包副本 `主仓 libs/meowlwjgls/libs/arm64-v8a/libgl4es.so` +
  `libs/meowlwjgls/libs/natives.manifest`（第 12 行 `common libgl4es.so 6c9065bb…`）已同哈希同步。

### 15.3 验证结论（2026-09-22，用户实测定案；用户 = 项目拥有者）

- 手机（HUAWEI Mate XT，Maleoon 910 / Kirin 9010）：**1.17.1 ✓ 可玩、1.19.4 ✓ 可玩**。
- 2in1（MateBook Fold）：**1.17.1 ✓ / 1.19.4 ✓ 无回归**。
- 四份日志（`主仓 .logs/`）指纹一致（见 §15.1）；⇒ `DEPTH_COMPONENT32F` 在两台设备上都
  **已被证明可作渲染目标**（FBO 完整性检查通过即证）。

### 15.4 残留风险

- 若将来遇到**不接受 32F 作渲染目标**的驱动，**退路 = 把 FLOAT 映射换成 `DEPTH24_STENCIL8`**（同映射表）。
- 手机上 1.18 / 1.20 / 1.21.x 未测。

---

## 16. 2026-09-22 记录：r7 —— 桌面-only cap / legacy 常量 + MC 1.21.10 主动查 `glGetError`

> 本节为**带日期的记录**，不复述现状；活状态见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 26 条。

- **背景**：**MC 1.21.9+ 全换新 RenderPipeline 体系**，1.21.10 启动即崩（与 ≤1.21.1 的旧管线不同代）。
- **现象**：① `glEnable(GL_TEXTURE_CUBE_MAP_SEAMLESS)`（`0x884F`，**桌面-only cap**）；②
  `glTexImage2D(… internalformat = GL_DEPTH_COMPONENT32(0x81A7) …)`（**桌面 legacy 常量**，core 后端映射表未覆盖）。
  且 **MC 1.21.10 会主动 `glGetError` 并在非 0 时抛 `IllegalStateException: OpenGL error 1282`**（1.20.6 不抛）
  ⇒ wrapper 里残留的 GL 错误会被 MC 当致命异常。
- **根因**：桌面-only 特性未在 core 面吞掉；depth internalformat 映射未含 legacy 常量 `0x81A7`；诊断行高频重复。
- **修法**：`mc_glEnable` / `mc_glDisable` 在 core 面**经 `mc_cap_desktop_only` 吞掉桌面-only cap**；depth 映射**补 `0x81A7`**；诊断行**改去重**。
- **实机结论**（2026-09-22）：修后**两条 GL 错误消失、崩点后移**。
- **产物（历史值，逐轮更替）**：`MC_BUILD_TAG=2026-09-22-r7 (depth32 + core caps)`，1,247,512 B / sha256 `7f0fa55a…`。

---

## 17. 2026-09-22 记录：r8 —— glslang 按阶段 auto-bind ⇒ UBO 块跨 stage 不一致

> 本节为**带日期的记录**，不复述现状。

- **现象**：r7 修后，1.21.10 报
  `Failed to load required shader programs: … buffer block with binding '1' has mismatching definitions`（**16 个 pipeline**）。
- **根因**：**glslang 的 `auto_bind_uniforms` 按阶段（VS / FS）、按首次引用顺序给块编号** ⇒ 同一个 `binding 1`
  在 VS 是 `Projection`、在 FS 是 `DynamicTransforms` ⇒ 跨 stage 同一 binding 指向不同块。
- **修法**：`mc_remap_block_bindings()` —— 按**块名**用**进程级表**统一各 stage 的 `layout(binding=)`。
- **离线自证**（对照）：1.21.10 **13→0**、1.21.11 **14→0**、1.17.1 **0→0**。
- **实机结论**（2026-09-22）：**16 个失败降到 1 个**（剩的是采样器，见 §18）。
- **产物（历史值）**：`MC_BUILD_TAG=2026-09-22-r8 (uniform block cross-stage)`，1,247,512 B / sha256 `637c033d…`。

---

## 18. 2026-09-22 记录：r9 —— 采样器同病 + shader 诊断行

> 本节为**带日期的记录**，不复述现状；当前基准产物与验收态见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 26 条。

### 18.1 采样器绑定：与 UBO 同病、对象不同

- **现象**：r8 后最后一个失败是**同一类病、但对象是采样器** —— VS `layout(binding = 2) … sampler2D Sampler2;` /
  FS `layout(binding = 0) … Sampler2;` ⇒ 驱动报 `explicit bindings for uniform 'Sampler2' have …`；
  **本机 GLES 3.2 复现文案**：`L0001 The fragment sampler variable Sampler2 does not match the vertex variable Sampler2. The binding does not match.`。
- **根因**：同 §17（glslang `auto_bind_uniforms` 按 stage、按首次引用顺序编号）；**UBO 的按名表不覆盖不透明采样器**。
- **修法**：`mc_remap_opaque_bindings()` —— 与 UBO **分开**的**按名表**，同为进程级、统一各 stage 的采样器 `layout(binding=)`。
- **离线自证**（对照）：1.21.10 **全 36 pipeline 不一致 1→0**、1.21.11 **41 个 1→0**。
- **实机结论**（2026-09-22，用户实测）：**1.21.10 在 2in1 ✓ 可玩**（日志指纹见现状基线 §5 第 26 条）。
- **产物（当前基准）**：`MC_BUILD_TAG=2026-09-22-r9 (sampler bindings + shader diag)`，**1,251,608 B** / sha256 **`2fbf08bce987bb4a75155b27ab23bde14c4d4feddd80627178c67a401a0a8fac`**。

### 18.2 新诊断行怎么读

r9 新增 `glCompileShader / glGetShaderiv / glGetShaderInfoLog / glLinkProgram / glGetProgramiv / glGetProgramInfoLog`
包装，**仅失败时**去重打印：

- `[meowcore] shader compile FAILED stage=0x%x srcLen=%zu esslLen=%zu head="<前40字节>": <info log>`
  - `stage`：GL 枚举（`0x8B31`=VERTEX、`0x8B30`=FRAGMENT）；
  - `srcLen`：MC 给的原 GLSL 字节数；`esslLen`：翻译出的 ESSL 320 字节数（**`esslLen=0` ⇒ 翻译阶段就失败**）；
  - `head`：原 GLSL **前 40 字节**（定位是哪个 shader）。
- `[meowcore] program link FAILED: <info log>`：链接失败（如跨 stage 绑定不一致）。

### 18.3 已知非本后端问题（如实登记）

- 1.21.10 出现过 `Couldn't find source for VERTEX/FRAGMENT shader (minecraft:core/position_tex_color)`，
  但该源与 `core/gui.{vsh,fsh}` 在 1.21.10.jar 中**确认存在且完整**（各 476–592 B）⇒ 属 **MC Java / 资源侧**，不归本后端。

### 18.4 残留风险

- 若将来遇到**不接受 `DEPTH_COMPONENT32F` 作渲染目标**的驱动，**退路 = `DEPTH24_STENCIL8`**（§15.2 映射表）。
- 采样器重编号**依赖 MC 自行 `glUniform1i` 绑定**（低风险）；**绑定表满则不改**（fail-safe）。

---

## 19. 2026-09-26 记录：r11–r13 —— Sodium 地形不可见 = core 入口面「静默 no-op」缺口

> 本节为**带日期的记录**，不复述现状；活状态见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 26 条、
> [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §I；审计报告 工作区根 `stuffs/research/gl4es/noop-audit/`。

- **现象**：MC 1.20.6 + Fabric + Sodium 0.5.11 走 core 后端 ⇒ **方块/地形全透明**（实体、GUI 正常）。
- **根因**：`meowcore_GetProcAddress` 只按**裸名**查包装表 / `dlsym(libGLESv3.so)`，都不中即返回空操作（**永不 NULL**，防 LWJGL 回落未初始化 FPE）⇒ 设备把多批 core 名**只导出为 `…EXT`**、而分发只看裸名时，该入口**静默失效**。
- **r11**：`glMultiDrawElementsBaseVertex`（Sodium 地形批量绘制；设备只有 `…EXT`）→ 包装：优先 `…EXT`，否则回退循环 `glDrawElementsBaseVertex`。
- **r12（真凶）**：`glBindAttribLocation` 原为 no-op；Sodium 按名把 `a_PosId/a_Color/a_TexCoord/a_LightCoord` 绑到 **1–4**（`ChunkShaderBindingPoints`）且**不 query**；glslang 默认烘焙 **0–3** ⇒ `a_PosId` 读从未喂过的 0 号槽 ⇒ 全部顶点塌缩 ⇒ 地形不可见。修法 = ① 剥顶点阶段 `in` 的烘焙 location（`mc_strip_vertex_input_locations`）② **转发 `glBindAttribLocation`**。**实机：方块恢复显示**。
- **r13**：对称修 `glBindFragDataLocation`（转发 `…EXT` + **守卫式**剥片元 `out` location：仅当原始 shader 未声明任何 `layout(location=) out` 时才剥）。
- **测量事实**：MC 的 **116 个 core shader 零** `layout(location`（靠 `glBindAttribLocation` + 默认序；输出单值/声明序）；Sodium 亦无。
- **三路审计（只读）**：入口级 / 参数级 / 其它层 → 同类在册项与"当前不触发"判定见 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §I。
- **产物**：r13 = `24cd5f33…`，1,255,704 B。（历史：r11 = `aac4a628…`、r12 = `7babd51c…` 同尺寸；r10 = `2c2b6f09…`，1,251,608 B。）
- **坑**：本配方为 RelWithDebInfo ⇒ **注释行数也会影响 digest**（行号进产物）；改注释须一并重装并同步 digest。

---

## 20. 2026-09-26 记录：core 的 GLES 也是 Mesa/Zink —— glthread 才是 core 性能的真杠杆

> 本节为**带日期的记录**；活状态见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 16/26 条、
> [`../../00-current/运行时环境变量.md`](../../00-current/运行时环境变量.md) 的 `GALLIUM_THREAD`。

- **★前提更正（用户纠正 + 实证）**：本节所述 core 后端的"原生 GLES"**并非厂商驱动，而是 Mesa**：
  `/system/lib64/libgallium-25.0.1.so`（Huawei fork，含 `ZINK:` / `mesa_glthread` / `GALLIUM_THREAD` / `Set an app profile enablement for glthread` 串）+ `libEGL_mesa.so`；`libGLESv3.so`（368 KB；`DT_NEEDED` 仅 libhilog/libc，运行期 dlopen gallium）= Mesa 的 **ES 前端**。
  **用户日志实证**：GL4ES(core) 会话内出现 `selected Vulkan device (Maleoon 916) doesn't support base Zink requirements` 与 `MESA zink: PERF WARNING …`（同进程、`MEOWCRAFT_RENDERER=gl4es`）。
  ⇒ **两条链都走 Zink**：core = MC→gl4es(桌面 GL 3.3→**ES 3.2 API**)→Mesa ES 前端→`libgallium`→**Zink**→Vulkan→Maleoon；桌面 = MC→Mesa 桌面前端→`libgallium`→Zink→Vulkan。
- **⇒ 真杠杆 = 现有「线程化渲染」开关（`GALLIUM_THREAD`）对 GL4ES 路径生效**，**不是**自造 glthread 队列。
  （曾据错误前提"core 是原生 GLES、无 Zink、故 glthread 无用"提出"给 core 自造命令队列"方案 —— **作废**。）
- **实测**（用户，同地点）：core（`GALLIUM_THREAD=0`，桥基值）**50–60 FPS** ≈ 桌面 GL 未开；桌面 GL 开 glthread 80–90；
  **core 经「额外渲染环境变量」写 `GALLIUM_THREAD=1`（零重编）= 稳定 90 FPS**。
- **落地（2026-09-26）**：启动器「线程化渲染」开关改为**对 GL4ES 也生效**（`renderer.env ∈ {openglv4, gl4es}`；
  `GameLauncher.ets` 拼 `GALLIUM_THREAD=1`、`GameVersionsView.ets` 的 `glThreadSupported` 与 UI 提示同步）；
  `MEOW_GUARD_SYNC` 仍**只对桌面 GL 路径有意义**（GL4ES 路径无 guard ⇒ 对它是 no-op）。
- **风险 / 未决（登记）**：GL4ES 路径**无 GL guard** ⇒ Mesa `tc_texture_subdata` 的客户端内存 UAF 未加保护；
  项目既有口径 = **MC ≤1.21.x 从不因它崩**（core 只服务 1.17–1.21.x）⇒ 现状接受（用户：出问题再说）；
  **FPE(<1.17) 子路径未验**、**长局稳定性未专项复测**。见 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §C（C9）。

---

## 21. 2026-09-27 记录：r14–r16 —— `glMultiDrawElementsBaseVertex` 的 `…EXT` 变体**不可移植**（被手机静默吞）

> 本节为**带日期的记录**；活状态见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 26 条、
> [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §I。

- **现象**：MC 1.20.6 + Fabric + Sodium 在**手机**上**方块全透明**；日志满是
  `C01400/OpenGLWrapper  E  glMultiDrawElementsBaseVertexEXT is invalid.`（同会话 **5598** 条）+ 3× `glBindFragDataLocationEXT is invalid`。
- **对照**：同一 build 在 **2in1** 上 `is invalid` = **0 条**（r11 的 `…EXT` 路线在 2in1 可用、地形正常）。
- **根因**：手机的 OHOS GLES wrapper 对**未支持的 `…EXT` 入口**只记一条 E 日志并**吞掉调用**、**且不置 GL 错误** ⇒ 地形 draw 不发出。
- **r15 的失败尝试**：调 `…EXT` 后用 `glGetError` 探一次以决定是否回退 ⇒ **无效**（`glGetError()` 恒 0，日志无 "rejected" 行）⇒ **运行期探测不可行**。
- **r16 定案**：`mc_glMultiDrawElementsBaseVertex` 改用 **ES 3.2 core 的 `glDrawElementsBaseVertex` 循环**（可移植、语义等价）；
  `…EXT` 仅在 core 入口缺失时兜底（从未发生）。另加一次性诊断 `mc_log_relevant_extensions()`（打印 multi_draw/base_vertex/frag_data 相关扩展名，备查）。
- **性能**：本机栈（Mesa ES 前端→Zink→Vulkan）里一次 multidraw 本就被 Zink 拆成 N 次 `vkCmdDrawIndexed` ⇒ **GPU 侧等价**，
  差别只在应用线程 CPU（1 次 vs N 次调用），而 **glthread 已开**（重叠）⇒ **用户实机对比无性能损失（2026-09-27 确认）**。
- **产物**：r16 = `f96d54a5…`，1,255,704 B（r14 = `3e152749…`、r15 = `0c2075e7…`，均同尺寸）。**r14/r15 为过程版、未被用户验证即被取代**。
