# glthread B 方案：GL guard 转发层（2026-09-14）

> 目标：让 **`GALLIUM_THREAD=1` 在 MC 26.x 上不崩**，从而拿到 glthread 的帧数收益。
> 根因见 [`../render/MC26.x渲染栈-差异分析.md`](../render/MC26.x渲染栈-差异分析.md) §5：Mesa **`tc_texture_subdata` 不做客户端数据同步拷贝**，
> 把客户端像素指针原样转发给 `zink_buffer_subdata`，TC flush（在 Render 线程）时读**已释放**的客户端缓冲 → UAF。
> 提交版证据：[`glthread崩溃-Bug报告.md`](glthread崩溃-Bug报告.md) §C/§D。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 16 条](../../00-current/现状基线.md)。

## 0. 为什么这条路成立（关键事实）

- **LWJGL 从 `-Dorg.lwjgl.opengl.libname` 指定的库解析全部 GL 函数**：`GL.create()` 优先用该库导出的
  `glXGetProcAddress`（再 `eglGetProcAddress`），失败才对该句柄 `dlsym`（调研见 §5）。
  ⇒ **只要把 libname 指向我们的 guard 库、并让它导出 `glXGetProcAddress`/`eglGetProcAddress`，我们就能对每个名字决定"拦截 or 透传"**，
  无需导出全套（LWJGL 3.4.3 有 2270 个槽）。
- LWJGL 必需入口只有 `glGetError`/`glGetString`/`glGetIntegerv`（缺则抛异常）→ 这三个我们直接透传导出即可。
- **我们有 LWJGL 源码级能力**（`tools/lwjgl` overlay 自编 jar）⇒ 必要时也可改 overlay（如 `GLCapabilities` 槽替换）作为备选。

## 1. 设计

新增 native `libmeowglguard.so`（由 **`meowcraftlib` 的 CMakeLists 构建**、随 **`meowjre` HSP** 打包——**不在**
lwjgl HAR 的扁平目录/`natives.manifest` 里）：

1. 加载时 `dlopen("libGLv4.so")`（按名；失败再绝对路径），解析**真** `glXGetProcAddress`/`eglGetProcAddress`。
2. 导出 `glXGetProcAddress(name)` / `eglGetProcAddress(name)`：
   - `name` ∈ 目标集合 → 返回**我们的 wrapper**；
   - 否则 → 返回真解析器结果（**透传**）。
3. 导出 `glGetError` / `glGetString` / `glGetIntegerv`（透传，满足 LWJGL 必需）。
4. **wrapper 语义（首批 `glTexSubImage2D`；2026-09-15 扩展到 8 个贴图上传入口，见 §2.5）**：进入时把客户端像素**同步拷进池化 staging**（fence 守护、安全回收）
   → 调真函数 → 插 `glFenceSync`；staging 槽位在 fence 已 signal 后复用。

**桥侧改动**（`meowjrebridge.cpp`）：
- 预 dlopen 目标由 `libGLv4.so` 改为 `libmeowglguard.so`（仍在 screen init 前，保证 GL 符号全局）；
- 同步 `-Dorg.lwjgl.opengl.libname` 与既有"libname 必须 == rendererSo"自检（`meowjrebridge.cpp:372-386`）。
- `MEOWCRAFT_RENDERER` 语义（`egl_gl.c`）不变（GL profile 仍走 EGL/桥，不依赖装载名）。

## 2. 阶段（每阶段可单独验证/回滚）

| 阶段 | 内容 | 验证 |
|---|---|---|
| **B1** | guard 库骨架：只做 resolver **透传** + 换 libname | MC 正常跑（行为应无变化）——证明"接管 GL 解析不破坏渲染" |
| **B2** | 加 `glTexSubImage2D` wrapper（拷贝 + fence 回收） | `GALLIUM_THREAD=1` 多次加载（原 ~50% 崩）→ **不再崩**；帧数不降 |
| **B3** | 铺开到其余"客户端内存入口"（1D/3D/Compressed 纹理、`glBufferData/SubData`、`glDrawElements*` 客户端指针、`glVertexAttribPointer`、`glReadPixels`…） | 长跑多场景；换函数不再复现 |

**验证基准**：26.2+Fabric+Sodium，加载屏反复开关（原崩点），并对比 `GALLIUM_THREAD=0/1` 帧数。

## 2.1 结果（2026-09-14）

- **B1 ✅（接管 + 零行为变化）**：guard 探针证实——`resolver=(nil)`（libGLv4 无 glX/egl 解析器，走 dlsym，与旧路径同构）、`first resolve 'glGetError'`、**`glTexSubImage2D -> 0x… (resolve #337)`** ⇒ LWJGL 确实把 GL 名（含目标入口）交给 guard；游戏正常。
- **B2a ✅（根因证实）**：wrapper = 真调用后 **`glFinish()`**（仅 glthread 时）。
  **11 份含 guard 日志、9 次 `GALLIUM_THREAD=1` ⇒ 致命崩溃 0**（此前 ≈50%）。唯一残留 `FAULT` 是 `Worker-Main-1` 命中的**恒定 `---p 4KB` 页（HotSpot safepoint polling page，良性、被恢复）**。
  ⇒ **根因 = "上传入队 → 之后某次 flush 才读客户端指针"**（glthread 未在入口同步拷贝）；把 flush 压到"仍在 wrapper 内、指针还有效"即不崩。**B 路可行。**
  - 代价：每个上传一次 `glFinish` → **加载末期明显变慢**（预期，验证用）。
- **B2b（进行中）**：把同步强度做成 env 可调（`MEOW_GUARD_SYNC=none|flush|finish`，默认 `flush`）——用 `glFlush`（冲刷 TC 队列让驱动立刻消费指针、不等 GPU）替代 `glFinish`，期望"不崩且不慢"。若 `flush` 不够 → 回 `finish`，走 **B2c = 拷贝 + fence 回收**（需像素尺寸/`GL_UNPACK_*` 计算）。
- **B2 因果闭合（2026-09-14，决定性）**：
  - `MEOW_GUARD_SYNC=**none**`（对照）→ **一开就崩**，且 crash 签名与修复前**逐字一致**：`lr=libgallium+0xE26CC4`（=`zink_buffer_subdata`）、`pc=ld-musl memcpy`、`addr` 未映射、`deaths=3`；
  - `flush`（3 次）/ `finish`（9 次）→ **0 致命崩溃**（残留仅恒地址 polling-page 良性 fault）。
  ⇒ **"上传入队→延后 flush 才读客户端指针"确认为根因；"入口处同步"确认为有效修复。**
  - 速度：`#1→#10000` finish 5.8s vs flush 4.9s（≈快 16%）；**每次上传仍有一次同步**（原生为零）。
- **B2c ❌ 实测失败（2026-09-14）**：`MEOW_GUARD_SYNC=copy` **会崩**（`flush`/`finish` 全 0 崩）。
  - 现场：`sync=3 copy=1,2,3 fallback=0`（copy 路径在跑）→ `FAULT#1 addr=0x59e34f2000`（polling page, ACCERR, JIT, Render 线程）→ `repeat x2/x3`（多线程 safepoint 风暴）→ `signo(11) si_code(1)=MAPERR → rethrow → 死`。**致命那条未被 `MEOW_BT` 抓到**（发生在异常状态）。
  - 最可能原因（回收时机/围栏用法）：① **staging 被过早释放**（`glFenceSync` 在 glthread 下的信号时机与假设不符）→ 驱动稍后读已释放 staging；② **每次上传一个 fence（上万次）的风暴**干扰 glthread/驱动。
  - **处置**：**默认仍是 `flush`**（已 12 次实机 0 崩）；`copy` 属实验性、**不采纳**。若要再试，方向 = **ring + 单次周期性 fence**（而非每上传一 fence）+ 回收前显式验证（例如对 staging 用 `glFlush` 后再回收）。
- **B3 当时暂缓（2026-09-14）**：只保留 `glTexSubImage2D`；其余同类入口按需再补。**2026-09-15 已扩到 8 个贴图上传入口（见 §2.5）**，其余同类热路径入口仍按需再补。

## 2.2 收口与验收（2026-09-14）

- **代码收口**：移除失败的 copy（只留 `none/flush/finish`，默认 `flush`）；`meowglguard.c` 文件头完整记录 bug 链/符号化/修复/证据/范围/回滚（含 copy 失败一节）。guard 在**默认渲染路径**（≥1.17）；**glthread 关时是薄转发**（行为等同透传）。
- **回归（默认、glthread 关）**：跑 1.18.2 / 1.21.10 等，画面/性能正常；日志里偶见的 `rethrow sig(6)` 经查是 **`appspawn: Unexpected call: exit(-1)` = 老版本 JLI 退出路径**（出现在日志最末、伴随 `Stopping`），**与 guard/glthread 无关**。
- **修复复核（glthread 开）**：26.2 连跑多次，**0 致命崩溃**；用户体感**帧数明显提升（最高 >100%）**、加载正常。
- **默认决定（2026-09-14；同日收敛为逐版本）**：「线程化渲染」为**「编辑版本」里的逐版本 Toggle（默认开）**（撤掉高级选项的全局开关，见 §2.4），"有问题再关单版本"。落地：**关闭表**（未列入 = 开）——2026-09-14 当时落 Preferences 的 `glthread_off`（JSON 版本 id 数组）；**2026-09-15 起改存各实例目录内 `.hmmcraft/instance-settings.json` 的 `hmmcraftGlThreadEnabled`**（见 [`../launch/实例设置存储-方案.md`](../launch/实例设置存储-方案.md)）；`GameLauncher` 取 `instance.glThreadEnabled && renderer.env ∈ {openglv4, gl4es}`，在 `extra render env` **之前**拼 `GALLIUM_THREAD=1|0`；用户的「额外渲染环境变量」拼在其后 ⇒ **可覆盖**。**GL4ES 路径也生效**（其 GLES 后端亦是 Mesa ⇒ Zink；实测 1.20.6 core **50–60→90 FPS**，见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 16 条）。UI：编辑面板 Toggle（非上述两后端灰化提示，仍可编辑/存值，仅启动时不生效）。

## 2.3 独立审查与处置（2026-09-14）

两个**只读 review agent**（明确文件清单、禁大范围查找）分别审「修复路径」与「其余改动」：**无 BLOCKER**。

**已修（本次提交 `b517be4` 等）**：
- **fail-open（两个 agent 都判 MAJOR，最高优先）**：原先"回滚 `RENDERER_LIB` 回 `libGLv4`"或"guard 加载了但未武装"时，`GALLIUM_THREAD=1` 仍生效 → UAF 原样复现。修法：① guard 导出 **`meow_glguard_armed()`**；guard 自身在**未武装**时 `setenv("GALLIUM_THREAD","0")`（其 constructor 在桥 pre-dlopen 时执行，晚于 env 设置、早于 Mesa screen init ⇒ 有效）；② **桥侧兜底**：pre-dlopen 后若 `MEOWCRAFT_RENDERER=openglv4` 且 glthread 开、而渲染器不是已武装的 guard → 强制回 0。
- **`meowbt.c` `walk_fp`**：读 `frame[0]/[1]` 前用已快照的 maps 校验（可读且留 16B），避免 handler 内二次踩未映射页被内核强杀（绕过 JVM）。
- **`meowbt.c` 线程名**：`pthread_getname_np`（非 async-signal-safe，可能死锁）→ 纯 `syscall(SYS_prctl, PR_GET_NAME, …)`。
- **extra render env 的 value 去空白**（与注释一致）；**maps 名去掉尾随 `\n`**；**stale 注释刷新**（`meowjrebridge.cpp` 的"保持 0"、`RendererPolicy.ets` 的"走 libGLv4"、`egl_gl.c` 的 `%p`→`%{public}p`）。

**已核实无误**：QoS/绑核 `meowqos.c` 解析/降级稳健；`egl_gl.c` 探针仅 env 门控且在 context current 后；**去掉 LWJGL 调试开关**无任何代码依赖（LWJGL 默认 false，legacy 同样正确）；env 拼接顺序/分隔与桥解析一致（**用户覆盖确为最后生效**）；开关持久化/UI 同步正确；**打包已在 HSP 内实测**（多次实机 guard 加载）。

**记录不修**：`RTLD_GLOBAL` 下 guard 的 `glXGetProcAddress` 会对全进程可见（风险低；改 `RTLD_LOCAL` 会动到桥的符号可见性契约）；`eglGetProcAddress` 兜底（**与 LWJGL 自身的 glX→ARB→egl→dlsym 顺序一致**，非超集）；`addr<64K` 良性过滤的折中（诊断工具；真故障若为"空基址+小偏移"会被静默 —— 已知）；计数器非原子（仅日志）；`SA_ONSTACK` 无 altstack（POSIX 允许回退，非 bug）。

## 2.4 实机回归暴露的代价与"按版本收口"（2026-09-14）

并代（现代统一 3.4.3）后实机回归：**各版本都能跑，但 1.21.10 进主菜单后奇卡**。

**日志定位**（用户导出 `.logs`；1.21.10、`gen=3.4.3`、`libname=libmeowglguard.so`、`glthread=1`）：

```
guard: texSubImage2D #1 16x16 … #40000 1x1 … #80000 32x32   glthread=1 sync=1   ← 28 秒内 8 万次
```

- 1.21.10 主菜单以 **~2800 次/秒**上传小图（`1x1…32x32` / `5x8`，字形/图集 + mip 链），守卫**每次**都
  `glFlush` → 每秒 2800 次跨线程同步 → 帧时间被吃光。
- **不是并代造成的**：旧日志（1.21.10 + `gen=3.3.3`，**无守卫**）里 `zink: PERF WARNING! > 100 copy boxes`
  同样是 3 条 ⇒ 上传行为与 LWJGL 世代无关；差别只在当时没有守卫（无每次同步）。并代只是让 1.21.10
  稳定跑到主菜单，把这个一直存在的代价暴露出来。
- 对照：26.2 的同口径上传率仅 ~100/s，故只有 1.21.10 撞上。
- 用户实机 A/B：**关掉「线程化渲染」即不卡** ⇒ 确认代价 = 守卫的每次同步（glthread 关时守卫纯透传，源码 `if (g_glthread)`）。

**收口（已落地）**：

- `RendererPolicy.guardNeedsSync(mcVersion)`：**仅 ≤1.21.x → 不同步**（注入 `MEOW_GUARD_SYNC=none`，守卫退化为
  纯透传、glthread 照开）；**其余（1.22–25.x、≥26.x、认不出/legacy）→ 每次 `flush`**。即"仅 ≤1.21.x 免这笔正确性税"。
- **逐版本「线程化渲染」开关**（用户 2026-09-14 收敛：**撤掉高级选项里的全局开关**，只留逐版本——
  "高级选项管默认"那套是多余的，逐版本一个开关更直白）：编辑面板一个 **Toggle（开 / 关，默认开）**；
  **桌面 GL 与 GL4ES 后端生效**（2026-09-26 起）—— 其它后端只是灰化提示，仍允许用户编辑、值照存，只是启动时不生效。
  **只有一张"关闭表"**（未列入 = 开）。**2026-09-14 当时**落 Preferences（`glthread_off`，JSON 版本 id 数组）；
  **2026-09-15 起**改存各实例目录内 `.hmmcraft/instance-settings.json` 的 `hmmcraftGlThreadEnabled`，
  旧键弃用（见 [`../launch/实例设置存储-方案.md`](../launch/实例设置存储-方案.md)）；`GameLauncher` 取
  `instance.glThreadEnabled && renderer.env ∈ {openglv4, gl4es}`（2026-09-26 起 GL4ES 也生效）。
- 用户「额外渲染环境变量」仍可显式覆盖（拼在我们的注入**之后** ⇒ 用户优先）。

## 2.5 机制扩展：贴图上传家族 8 入口 + 未包热路径点名日志（2026-09-15 实机结案）

**现象**：`26.2-Fabric` + 线程化渲染**开**时，**GUI 贴图部分未上传**（例：背包背景只画出一半、另一半透明）；**关掉线程化渲染即恢复正常**。

**为什么是同类**：与已知 Mesa glthread 延迟读（`tc_texture_subdata` 不做客户端数据同步拷贝、把指针**延后到 flush** 才读）**同一类**，只是打在我们**当时没包**的入口上——此前 guard 只包了 `glTexSubImage2D`。上传入队后客户端指针已失效/被复用 → 部分像素未被正确读取 ⇒ 表现为"半张图"。

**修法（已落地；2026-09-15 实机通过）**：把**整个"客户端内存·贴图上传家族"**都接上后置同步（共用 `meow_gl_sync_after_upload()`），共 **8 个**入口：
`glTexImage2D` / `glTexImage1D` / `glTexImage3D` / `glTexSubImage1D` / `glTexSubImage3D` / `glCompressedTexImage2D` / `glCompressedTexSubImage2D`（+ 原有 `glTexSubImage2D`）。
实现 `libs/meowcraftlib/src/main/cpp/meowcraftbridge/meowglguard.c`；app 提交 `8c62c0d`。

**新增自诊断（15 个故意不包的热路径入口）**：对 `glBufferData` / `glBufferSubData` / `glNamedBufferData` / `glNamedBufferSubData` / `glMapBuffer` / `glMapBufferRange` / `glUnmapBuffer` / `glReadPixels` / `glShaderSource` / `glDrawArrays` / `glDrawElements` / `glVertexPointer` / `glTexCoordPointer` / `glNormalPointer` / `glColorPointer`，**第一次被解析时各打一行**：
`guard: unwrapped client-memory entry used: <name> (deferred-read risk; wrap it if textures/buffers corrupt)`。
2026-09-15 的 26.2-Fabric 实机日志里这 15 个**全部出现（各 1 次）** —— 即"同一类缺陷的理论剩余面"。

**实机结案（用户 2026-09-15）**：扩展后 26.2-Fabric + glthread 开 ⇒ **GUI 贴图正常（"好了"）**。

**守卫版本可辨**：初始化行现在会打出每个被包入口的解析指针（`tex=… tex1d=… tex3d=… sub1d=… sub3d=… comp2d=…`），**可用于确认设备上跑的是哪一版守卫**。

**操作法（下次若再花屏）**：查日志里的 `unwrapped client-memory entry used: <name>` —— 哪一项被点到，就把 `<name>` 补进贴图上传家族（同款后置同步）；未被点到的项维持不包（省同步税）。

## 3. 难度与未知（决定成败的点）

- **难度**：B1 **低**；B2 **中**；B3 **中–高**（覆盖面 + fence 回收正确性）。
- **未知/风险**：
  1. LWJGL 对 `glXGetProcAddress` 的信任度（是否所有名字都问我们；有无回退到句柄 dlsym）。
  2. **staging 回收**：必须保证"拷贝在 TC 消费完之前不释放"（fence/池化）；做错就复现同款 UAF。B2 是先验证点。
  3. 26.x 实际调用的入口集合（需抓调用/逐步铺开）。
  4. **gl4es 路径（≤1.16/legacy）不受益**（那条走 `libgl4es.so`）——只服务现代路径（≥1.17，含 26.x）。
  5. **glthread 本身增输入/present 延迟**（当年关它的原因）⇒ B 换来帧数但可能牺牲手感，需一起评估。
- **回滚**：libname 指回 `libGLv4.so` 即可（guard 库留着不影响）。

## 相关

- [`../render/MC26.x渲染栈-差异分析.md`](../render/MC26.x渲染栈-差异分析.md) §5（B/C 可行性）、[`glthread崩溃-Bug报告.md`](glthread崩溃-Bug报告.md)（证据）
- [`../../00-current/运行时环境变量.md`](../../00-current/运行时环境变量.md)（`GALLIUM_THREAD` / `MEOW_*`）
