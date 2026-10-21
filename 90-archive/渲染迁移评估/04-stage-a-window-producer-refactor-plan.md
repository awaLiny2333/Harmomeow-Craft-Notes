> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../20-design/render/渲染链-结论.md`](../../20-design/render/渲染链-结论.md)。

# 04 - 阶段 A 备用计划：窗口生产者可插拔（纯重构，零行为变化）

> 状态：**备用，未执行**。仅在将来决定迁 SurfaceHolder（或需要第二套窗口来源）时启用。
> 前置阅读：[`../../20-design/render/渲染链-结论.md`](../../20-design/render/渲染链-结论.md) §5、[`01-current-render-chain.md`](01-current-render-chain.md) §2.3 / §4 / §5。
> 原则：**纯重构，不引入任何行为变化**；可单独提交、单独回归、单独回滚。

---

## 1. 目标与非目标

**目标**：把"窗口从哪来"收敛成**唯一一个 native 入口**，让窗口生产者（现：ArkUI surfaceId）可被替换（将来：SurfaceHolder 的 `OHNativeWindow*`），而 EGL/输入/尺寸/关闭逻辑一行不改。

**非目标（阶段 A 明确不做）**：
- 不引入 NDK 节点、不动 `OH_ArkUI_SurfaceHolder_*`。
- 不改 ArkTS/NAPI 接口、不改 `Index.d.ts`。
- 不改 EGL 配置、swapInterval、resize 节流、输入链路。
- 不新增帧率/VSYNC 相关代码。

**验收的最终形态**：`pojavSetSurfaceId` 退化为一个"创建 OHNativeWindow 的适配器"，真正落地窗口的只有一个内部 sink；新增的 `meowSetSurfaceWindow` 可在**不改任何其他代码**的前提下被第二阶段调用。

---

## 2. 现状锚点（改造前，务必逐条核对）

| 位置 | 现状 |
|---|---|
| `libs/meowcraftlib/src/main/cpp/meowcraftbridge/egl_gl.c:355-398` | `pojavSetSurfaceId(int64_t sid,int w,int h)`：sid 幂等短路 → `OH_NativeWindow_CreateNativeWindowFromSurfaceId` → 写 `env->window`/`env->surfaceId` → `SET_SOURCE_TYPE=OH_SURFACE_SOURCE_GAME` → `SET_BUFFER_GEOMETRY` → 重置 `g_lastAppliedW/H=0` |
| `egl_gl.c:409-427` | `meowResizeSurface(sid,w,h)`：sid 不同 → 走完整 `pojavSetSurfaceId`；sid 相同 → 只写 `env->savedWidth/Height/width/height` |
| `egl_gl.c:171-193 / 209-235 / 308-335` | 渲染线程按 `env->window` 变化 `eglMakeCurrent`；`pojav_egl_apply_resize` 重建 surface；swap 失败自愈 |
| `libs/meowcraftlib/src/main/cpp/meowjrebridge/meowjrebridge.cpp:312-348` | NAPI `setGameSurface` → `dlsym("pojavSetSurfaceId")` |
| `meowjrebridge.cpp:353-387` | NAPI `resizeGameSurface` → `dlsym("meowResizeSurface")` |
| `libs/meowcraftlib/Index.ets:12-13` | 导出 `setGameSurface` / `resizeGameSurface` |
| `entry/src/main/ets/pages/GameWindow.ets:916-929` | `parseInt(surfaceId,10)` → 首帧 `setGameSurface` / 变化 `resizeGameSurface` |

**关键不变量（阶段 A 必须保持）**
- `pojav_environ->window` 的偏移（`env+0x000`）与语义不变。
- `env->surfaceId` 仍被写入（`meowResizeSurface` 的 sid 比对依赖它）。
- `SET_SOURCE_TYPE=OH_SURFACE_SOURCE_GAME` 与 `SET_BUFFER_GEOMETRY` 行为不变。
- `g_lastAppliedW/H` 重置逻辑不变（否则首帧不会重建 EGL surface）。
- 日志指纹不变（回归时用作对照）：`pojavSetSurfaceId: sid=… W x H window=0x…`、`meow resize surface mark …`。

---

## 3. 任务清单（顺序执行）

### A1 — 抽出唯一窗口 sink（native，`egl_gl.c`）
- 新增 `static int meow_publish_window(OHNativeWindow* win, int64_t token, int w, int h)`：
  写 `env->window`、`env->surfaceId = token`、`SET_SOURCE_TYPE`、按需 `SET_BUFFER_GEOMETRY` + 尺寸镜像、`g_lastAppliedW/H = 0`；成功返回 0。
- 新增导出 `int meowSetSurfaceWindow(void* nativeWindow, int64_t token, int w, int h)`：
  **不创建**窗口，直接调 `meow_publish_window`；`nativeWindow == NULL` 返回 -1 并打错误日志。
- **验收**：`nm -D libmeowcraftbridge.so | grep -E "meowSetSurfaceWindow|meow_publish"` 能看到 `meowSetSurfaceWindow`（`meow_publish_window` 为 static，不应出现在动态符号表）。
- **风险**：低。无调用方，纯新增。

### A2 — `pojavSetSurfaceId` 改为适配器（native，`egl_gl.c:355-398`）
- 保留开头的 sid 幂等短路（同 sid + 有 window → 只更新尺寸并返回 0）。
- 保留 `OH_NativeWindow_CreateNativeWindowFromSurfaceId` 与失败日志。
- 创建成功后**改为调用 `meow_publish_window(win, sid, w, h)`**，删除内联的写入逻辑。
- **日志文案保持逐字一致**（`MEOWLOGI("pojavSetSurfaceId: sid=… window=…")` 位置/内容不变）。
- **验收**：diff 中该函数只剩"幂等短路 + 建窗 + 调 sink"；`git diff` 无其他文件受影响。

### A3 — 无 token 的尺寸入口（native，`egl_gl.c`，**Stage B 使能项**）
- 新增导出 `int meowResizeSurfaceSize(int w, int h)`：`w/h <= 0` 或 environ 未就绪返回 -1；否则只写 `env->savedWidth/Height/width/height`（与 `meowResizeSurface` 同 sid 分支等价，但不比对 sid）。
- `meowResizeSurface` 同 sid 分支改为调用它（去重，行为不变）。
- **理由**：SurfaceHolder 的 `onSurfaceChanged` 只有 width/height、**没有 sid**；提前把"无 token 尺寸"作为一等入口，阶段 B 才不必再改 native。
- **验收**：`nm -D` 可见 `meowResizeSurfaceSize`；既有 resize 路径日志与行为不变。

### A4 — 导出与符号核对（native）
- 确认新增符号：`meowSetSurfaceWindow`、`meowResizeSurfaceSize`。
- 确认既有导出未变（对照 [`01-current-render-chain.md`](01-current-render-chain.md) §3.5 清单）。
- **验收**：符号差集 = 恰好这 2 个新增，0 个删除/改名。

### A5 — ArkTS / NAPI：**不改**
- 本阶段**不新增** NAPI、不改 `Index.d.ts`、不改 `Index.ets`、不改 `GameWindow.ets`。
- **验收**：`git status` 中 ArkTS 文件与 `*.d.ts` 均无改动。

### A6 — 构建 + 实机回归（零行为变化验证）
- `devecocli run --module entry meowjre25 --device 127.0.0.1:<port>`（端口以实际为准）。
- 回归清单（全部必须通过，且与改造前对照日志）：
  1. 启动 MC，画面正常，`pojavSetSurfaceId: sid=… window=0x…` 出现一次。
  2. 非 grab：hover/菜单跟手（mouse filter 直通仍生效）。
  3. grab：转视角、点击、滚轮正常。
  4. 中文 IME 输入正常。
  5. 窗口 resize：`meow resize surface mark W x H` + 渲染线程重建，画面不黑不撕裂。
  6. 关窗：MC 优雅退出（`requestGameWindowClose` 链路）。
  7. 二次进入游戏窗口：surface 重新注入成功。
- **验收**：以上全过 + 日志指纹无意外新增/缺失。

### A7 — 提交（独立可回滚）
- 单 commit，message 示例：
  `refactor: make native window producer pluggable (no behavior change)`
  body：`pojavSetSurfaceId now only creates the OHNativeWindow and delegates to meowSetSurfaceWindow; add tokenless meowResizeSurfaceSize. Stage B enabler for SurfaceHolder.`
- **验收**：`git show --stat` 仅含 `egl_gl.c`（+ 如需 `CMakeLists.txt` 无改动则不含）。

---

## 4. 阶段 A 完成后的状态（为 B/C 铺路）

- 第二套窗口来源只需：在 `onSurfaceCreated` 拿到 `OHNativeWindow*` → 调 `meowSetSurfaceWindow(win, token, w, h)`。
- `onSurfaceChanged` 只有 vp 尺寸 → 调 `meowResizeSurfaceSize(w, h)`（**注意**：需在调用侧自行换算 px，见 [`03-sdk-header-facts.md`](03-sdk-header-facts.md) 密度缺口）。
- 输入/IME/焦点仍走 ArkTS，阶段 B 期间**两套窗口来源并存**，可随时回退。

---

## 5. 回滚方案

- 阶段 A 为纯新增 + 内联改写，**单 commit revert 即可**（`git revert <hash>`）。
- 因 ArkTS/NAPI 未动，回滚不涉及重新签名或数据目录变更。

---

## 6. 风险表

| 风险 | 等级 | 缓解 |
|---|---|---|
| 内联改写漏掉 `g_lastAppliedW/H` 重置 → 首帧不重建 surface（黑屏） | 中 | A2 验收 diff 逐行核对；A6 第 1 条 |
| 日志文案变动导致回归对照失效 | 低 | A2 明确要求逐字保留 |
| `meowResizeSurfaceSize` 被误用于 sid 变更场景 | 低 | 阶段 A 无调用方；阶段 B 文档注明只用于同表面尺寸变化 |
| 符号导出被 `-fvisibility=hidden` 影响 | 低 | A4 用 `nm -D` 核对；现有导出已证明可见性配置正确 |
