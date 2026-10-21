# Vulkan 后端性能：瓶颈清单与决定性实验计划（2026-09-19）

> 定位：回答「MC 26.2 原生 Vulkan 后端世界档 **21–24 FPS**（GL 档 60–70）差距在哪、下一步打哪」。
> 方法：全链路**五路并行只读审计**（shim 热路径 / 窗口与 WSI / 启动参数 / 既有结论 / LWJGL-VMA-native），主会话抽查定性。
> 证据原文（临时件，工作区根相对）：`stuffs/research/vulkan/perf/PA-shim-hotpath.md`、`stuffs/research/vulkan/perf/PB-wsi-present.md`、
> `stuffs/research/vulkan/perf/PC-jvm-args.md`、`stuffs/research/vulkan/perf/PD-existing-levers-and-experiments.md`、`stuffs/research/vulkan/perf/PE-lwjgl-vma-native.md`。
> 行号为**本文撰写时**值（记录 1–10 的基线 = shim tag `.64 quiet-push-counters`，`meowvulkan.c` 5935 行；记录 11–16 的行号/基线见各记录标注的 tag）。
> 本文为决策记录 / 证据存档，**不复述现状**；性能现状与差距登记见 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §H。

---

## 0. 结论摘要

1. **B0（口径）已结案（2026-09-19 用户实测）**：**纯原版**实例（无 Fabric/Sodium）同场景 **GL 50–60 FPS ｜ Vulkan 20–30 FPS**
   ⇒ 差距**真实存在、与 Sodium 无关** ✓（Sodium 只解释此前 60–70 那一档的一部分）。靶子成立，见 §5 记录 1。
2. **代码侧已锁定 3 处真实热路径开销**（全部代码可证，见 §1 B2/B3/B1）：`wd_note` 未门控、每次调用重解析函数指针、F72 每 push 放大（净 +2 驱动调用）。
3. **旋转/`preTransform` 不一致**（F73 强制 IDENTITY × surface 报 ROTATE_90）本桥**无任何旋转代码**（PB 可证）⇒ 代价在 shim/WSI/合成器，
   是否每帧全屏变换**未定性**，需一次 A/B。
4. **JVM 侧**（线程超订 / GC 与堆默认）**从未试过**，且可用既有「额外 JVM 参数」零改动 A/B（PC、PD）。
5. **已排除清单**（沿用 PD）：OpenGTX/LTPO、超帧/ABR、XEngine、QoS+绑核、90Hz/NativeVSync、SurfaceHolder 迁移、
   Mesa 缓存开关、Vulkan vsync/队列全刷/池泄漏。`meowqos`/`meowbt` **默认关**（PE 代码可证）⇒ 对现状零贡献。
6. **对"per-call 包装拖慢一切"的证伪**（PE）：GL guard 只在 8 个纹理上传族包 `glFlush`，`glDraw*`/`glBufferData`/`glMapBuffer` 等热路径**不包装**。
   ⇒ GL 能跑 60–70 **不能**用来免责我们的 Vulkan 包装（GL 恰恰没包装热路径）；反过来**抬高了 B1/B3 的嫌疑**。

---

## 1. 瓶颈清单（按影响排序；证据强度 = ①用户实测 ②代码可证 ③推测）

| # | 位置（符号 / 行号） | 机制 | 每帧量级 | 影响排序 | 证据强度 |
|---|---|---|---|---|---|
| **B0** | 对比口径（实例 mod / 场景 / 视距 / 分辨率 / glthread） | GL 档带 Sodium、Vulkan 档可能无 ⇒ 差值是**渲染器差异**而非我们的开销 | — | **第 0 位（先排除）** | ②+③ |
| **B1** | F72 `meow_f72_emulate_push`（`meowvulkan.c:2107` 起，驱动调用 `:2147-2194`） | 每次 push = `Allocate`+`Update`+`Bind`（原生 1 次）⇒ **净 +2 驱动调用**；另加 2×`getenv`(`:914`+`:922`) + 2×O(256) 线性查表(`:1828`/`:1861`) + `malloc`/`free`(`:2185`) + `memcpy`(`:2190`) + 3×函数指针解析(`:1782`) | 会话累计 **1452 万次**；按世界档 22 FPS 推算 **≈1.1k–2.2k 次/帧**（推算，非实测） | **1** | ①② |
| **B2** | `wd_note`（`meowvulkan.c:979-984`） | **未门控** ✗：每次调用 `clock_gettime` + `snprintf`，`MEOW_VK_WD` 默认关也**不早退**；被 ~20 个热 wrapper 调用（`vkCreateBuffer/Image/BindBufferMemory/QueueSubmit(2)/WaitSemaphores/…`） | 每帧数百–数千 | **2** | ② |
| **B3** | 各 wrapper 体内的 `g_gdpa(g_dev_seen, "vkXxx")`（样本 `:1023`） | **每次调用**重新解析真实函数指针（无缓存） | 每个被包装调用 1 次 | **3** | ② |
| **B4** | `preTransform=IDENTITY`（`meowvulkan.c:4833`/`4879`）× surface `ROTATE_90` | 本桥无旋转代码 ⇒ 变换由 shim/WSI/合成器承担；若 WSI 每帧做全屏旋转/拷贝则可观 | 每帧 1 次（若真存在） | **4** | ③ |
| **B5** | JVM 线程模型（`MinecraftLauncher.ets:296-298` 无 `-XX:ActiveProcessorCount`） | 20 核 / 6 簇，未封顶 ⇒ GC/JIT 工作线程可能抢占大核 | — | **5** | ③ |
| **B6** | 堆与 GC（`MinecraftLauncher.ets:212-214` 无 `-Xms`/`-Xmx`/GC 选择） | 默认堆 + 默认 GC ⇒ 可能有停顿；MC 版本 json 自带的 `-Xmx` 未核 | — | **6** | ③ |
| **B7** | barrier2 翻译（`meowvulkan.c:3876`，`getenv` `:1261`） | 每 barrier `calloc`×≤3 + `free` + `getenv` | 每 barrier 1 次 | **7** | ② |
| **B8** | F66 合并提交（`meowvulkan.c:2717` 区） | 多 entry → 1 条 v1 提交：是否引入额外拷贝/串行化**未定性** | 每帧 1–2 次 | **8** | ③ |
| **B9** | resize 路径（`input_bridge.c:41`/`380`；`egl_gl.c:419`/`491`/`520`；`SET_BUFFER_GEOMETRY` `egl_gl.c:550`） | 50ms 节流 + 重建；**仅 resize 时**，非常态 | 非稳态 | **9** | ② |
| **B10** | `meow_mouse_filter` 每 move（`input_bridge.c:901`/`922`） | `clock_gettime` + 浮点；有 100ms 节流（`GameInputController.ets:819`） | 事件级 | 10 | ② |
| — | `meowqos.c:52`/`127`、`meowbt.c:656-659` | 默认关 ⇒ **零贡献** | — | — | ② |
| — | 无 fps 上限 / `eglSwapInterval(0)`（`egl_gl.c:374`/`508`，`meowSwapInterval` 丢入参 `:852`） | 不影响"22 FPS 是被算力限制"的判定 | — | — | ② |

**口径提醒**：F72 计数有**两代不兼容读数**（早期 1.688M / `pools=8180`；当前 14.52M / `pools=27`、`resets=66048`）⇒ 计数是**会话累计**，
且池语义经 F72c 改过，**跨世代不可比**，只可同世代内看增量。

---

## 2. 决定性实验（E0 先做；全部由用户在 UI/导出的 `.logs` 上完成，agent 不抓日志不点 UI）

| # | 假设 | 用户步骤（要点） | 读数 | 判定阈值 | 耗时 |
|---|---|---|---|---|---|
| **E0** | 现有差值至少部分是 **Sodium×后端** 与口径差异 | ① **纯原版实例**（无 Fabric/Sodium）：同一世界/坐标/朝向，GL 档静置 60s 记 FPS 并导出日志；切 **Vulkan 档**重复 ② 再对**带 Sodium 实例**重复同一对比 | F3 FPS；`.logs` 的 `gapMs` 众数/p95、`present=` 行、`extra render env:` 行 | 原版 GL ≈ 原版 Vulkan ⇒ **差距主因=Sodium**，我链已接近同水位；原版也差 2–3× ⇒ 瓶颈确在我链/ICD | ~20 min |
| **E1** | 缩放能显著抬 Vulkan FPS ⇒ 像素/GPU 受限；几乎不变 ⇒ 固定每帧成本（shim/JVM/present） | 固定世界/坐标/朝向、F1 关 GUI；「显示缩放」1x→2x→4x，每档静置 60s 记 FPS 并导出日志；GL 与 Vulkan 各跑一遍（`renderScale` = ArkUI `.scale(S)` + 组件按 1/S 布局 ⇒ **确实改渲染分辨率**，`GameInputController.ets:823-829` 代码可证） | F3 FPS；日志 `gapMs` | 4x ≥ 2×1x 且逼近 GL ⇒ GPU/像素主导；各档变化 <15% 且仍 21–24 ⇒ 固定成本主导 | ~20 min |
| **E2** | F72 占可观的每帧 CPU | 「渲染 env」填 `MEOW_VK_DROP_PUSH_DESCRIPTOR=1`（B 级开关，`meowvulkan.c:871`；**画像会错但 FPS 可比**），进世界静置记 FPS | F3 FPS | FPS 明显跳升（>20%）⇒ **F72 确诊**，按 §3 优化；几乎不动 ⇒ F72 非主因，转向 B2/B3/B4 | ~5 min |
| **E3** | 旋转变换有实代价 | 「渲染 env」填 `MEOW_VK_FIX_SURFACE_TRANSFORM=requested`（A/B 逃生，`:4880`）⇒ 保留 `ROTATE_90`（画像会转 90°，仅测帧率） | F3 FPS | FPS 明显变化 ⇒ B4 确诊 | ~5 min |
| **E4** | JVM 线程超订 / GC 默认有代价 | 「额外 JVM 参数」填 `-XX:ActiveProcessorCount=6`（或 `-XX:ParallelGCThreads=6`）对比基线；再试 `-Xms4g -Xmx4g -XX:+UseG1GC -XX:MaxGCPauseMillis=20` + `-Xlog:gc` | F3 FPS；GC 日志停顿 | 任一档显著抬升 ⇒ 采纳为默认（按"UI 能承载就不加 env"口径走设置项） | ~5 min/档 |
| **E5** | §3 的廉价修复能拿回一部分 | 修完 shim 后**重跑 E2 同基线的 FPS** 对比 | F3 FPS + 新 tag 日志 | 修复前后差值即收益 | 构建 ~1 min |

**单点建议**：只做一个 ⇒ **E0**。它最便宜，且**可能直接改写问题定义**（若差距=Sodium，则后续所有 shim 优化都是错靶）。

---

### 2.1 由实机记录 2 加定的测试（T 系列；环境变量名均已核 `meowvulkan.c:38-57`）

| # | 假设 | 用户步骤 | 判定阈值 | 风险 |
|---|---|---|---|---|
| **T0** | 先取 MC 自己的归因 + 确认读数性质 | ① FPS **是不是卡在整数**（如恰好 30.0/20.0，而非 27.4）② F3 的帧时间曲线形状（均匀高位 vs 平线+尖刺）③ Shift+F3 饼图**最占时区块** | 卡整数 ⇒ **同步/节流（pacing）**，不是算力；均匀 ~33–50ms ⇒ 真实每帧成本 | 无 |
| **T1** | 绘制/几何受限 vs 固定成本 | 渲染距离拉到最小（2 chunk），同场景同窗口对比 FPS | 暴涨 ⇒ 绘制数受限（GPU 或提交侧）；**不动 ⇒ 固定每帧成本** | 无 |
| **T2** | CPU 侧 vs GPU 侧 | 「渲染 env」填 `MEOW_VK_DROP_DRAW=1` | FPS →60+ ⇒ GPU/绘制侧；**仍 20–30 ⇒ CPU 侧固定成本**（翻译层/JVM/present） | 画像无绘制；可能不稳 |
| **T3** | F72 是不是那笔固定成本 | 「渲染 env」填 `MEOW_VK_DROP_PUSH_DESCRIPTOR=1` | FPS 明显跳升 ⇒ F72 确诊 | 画像错 |
| **T4** | **每帧串行化等待**（头号嫌疑） | 「渲染 env」填 `MEOW_VK_WAIT_VIA_QUEUE_IDLE=0`（该项默认 ON，注释：`vkWaitSemaphores times out`） | FPS 跳升 ⇒ 确认是**每帧等队列空闲**把 CPU↔GPU 流水掐断；若超时/丢器件 ⇒ 记录后回退 | **可能崩/丢器件**（默认 ON 有原因） |
| **T5** | 交叉确认 | 超小窗 + 最小渲染距离 + T2/T3 任意组合 | 三重叠加仍 ~20 ⇒ 铁证"固定每帧成本" | 无 |

---

## 3. 廉价代码修复（不改语义，E5 用）

| 优先 | 改动 | 位置 | 风险 |
|---|---|---|---|
| 1 | `wd_note` 加早退（未 armed 直接 return；名字格式化只在 armed 时做，或改用 `wd_touch`） | `meowvulkan.c:979-984` | 极低（仅影响看门狗诊断） |
| 2 | `meow_vk_drop_push()` / `meow_f72_on()` 结果缓存为 static（与 `g_hooks` 同口径，`init_once` 后不变） | `:871`、`:884`–`886` | 低（env 改为"首用生效"，与其它开关一致） |
| 3 | 缓存各 wrapper 解析出的真实函数指针（按命令名一次解析；device 变更时失效） | 各 wrapper 体内 `g_gdpa` 调用点 | 中（须处理 `g_dev_seen` 变更） |
| 4 | F72 三个解析指针 + `getenv` 上提；O(256) 线性查表换哈希或**缓存上一次 layout→镜像映射**（push 常重复同一 set） | `:1782`、`:1828`、`:1861` | 中 |
| 5 | F72 去 `malloc`/`memcpy`（按提交区间的 arena / 线程局部复用） | `:2185`、`:2190` | 中 |
| 6 | F72 合并"同 set 且中间无 draw 的连续 push"（仅最后一次有效） | `meow_f72_emulate_push` | 中（须证语义等价） |

---

## 4. 未定性 / 待补

- **F72 每次 push 的真实纳秒成本**、`g_gdpa` 单次成本、F69 等待每帧轮询次数 —— 均需实机计数，本轮未测。
- **F66 合并提交是否让 MC 的帧变成串行**（本机 ICD 只收 1 entry 是既有事实，代价口径未知）。
- **B4 的变换执行者**：本桥无旋转代码，WSI shim / 官方 loader / 合成器三者谁是执行者未定。
- **Acquire/Present 同步原语与 image 数**（PB 指出不在其 5 文件内，未证）。
- **`renderScale` 是否真降游戏内部渲染分辨率**已在代码层证实（组件 1/S 布局 + `.scale(S)`），但**实际像素收益尚未测量**。
- **PE 提到的 "renderpearl"** 未见证据支撑 ⇒ 不采信、不入档。
- GL 档 60–70 的**测量版本/场景/glthread 口径**未记录（PD、PE 双路指出）⇒ 顺带补记。

---

## 5. 实机记录与推论（2026-09-19 起：仅 FPS 读数；**2026-09-20 起**改用「反编译源码 + shim 仪表 + 用户导出的 `.logs`」）

**记录 1（结案 B0）**：**纯原版**（无 Fabric/Sodium）同场景 —— **GL 50–60 FPS ｜ Vulkan 20–30 FPS**
⇒ 差距**与 Sodium 无关**，是我链 / ICD / MC-Vulkan 路径的真实差距。

**记录 2（★关键判别）**：同一场景，Vulkan 档 **全屏 ≈20+ FPS，超小窗口也 ≈20+ FPS**（随窗口尺寸/渲染分辨率几乎不变）。

**推论（由记录 2）**
- **排除"像素/填充率受限"** ⇒ ① **B4（旋转每帧全屏 blit）显著削弱** ✗（该类代价会随像素数缩放）② **E1（显示缩放矩阵）失去价值** ⇒ 不必做 ✗。
- **指向"每帧固定成本"**（对应 33–50 ms/帧）⇒ 强化 **B1（F72）/B2（`wd_note`）/B3（逐调用解析）**；并新增头号嫌疑
  **每帧串行化等待**：`MEOW_VK_WAIT_VIA_QUEUE_IDLE` 默认 ON（`meowvulkan.c:43`）⇒ 每帧 `vkQueueWaitIdle` 会**掐断 CPU↔GPU 流水**，是**与分辨率无关**的固定墙钟成本 ✓。
- **仍未区分**：固定成本在 **CPU 侧（我们的翻译层/JVM）** 还是 **GPU 侧"绘制数/几何"受限**（后者同样与分辨率无关）⇒ 用 §2.1 的 T1/T2 判定。
- **旁证（已弱化）**：20–30 恰在 60/3 ～ 60/2 区间原被读作 pacing 线索；但用户读数**非整数、帧时间波动大** ⇒ **pacing 假设不成立** ✗（改用记录 3 的解释）。

---

**记录 3（2026-09-19，用户实测）**：① 降低渲染距离后 FPS **涨到 50–60** ② **同一场景下只有"面对世界某个特定位置"才跌到 20–30**；
面对其他方向 **60 FPS，与 GL 几乎无差异** ③ 在该掉帧场景下 **GL 帧率依旧很高**（读数非整数、帧时间波动大）。

**推论 2（由记录 3；★推翻"固定每帧成本"）**
- **"每帧固定成本"假设被推翻** ✗：真有 33–50 ms 固定成本的话，**所有视角都该慢**；实测多数视角 60 FPS
  ⇒ **成本与该视角的"绘制/状态调用量"成正比** ✓。
- ⇒ §2.1 **T4（每帧 `vkQueueWaitIdle` 串行化）降级**（与"只有特定视角慢"不符）✗；T0 的 pacing 分支同样作废 ✗。
- ★ **头号假设（新）**：**"每次调用的固定开销" × 该视角暴涨的调用量**。论据链：
  1. 本机 GL 档是 **`libGLv4.so` → Zink → Vulkan**（`meowglguard` 转发链，90-archive/06 可证）⇒ **GL 与 Vulkan 共用同一 ICD、同一 GPU** ✓
  2. 同一场景 GL 能跑 60 ⇒ **GPU/ICD 有能力**吃下该内容 ✗
  3. PE 已证 GL guard **不包装热路径**（`glDraw*`/`glBufferData`/`glMapBuffer` 一律返回裸指针），而我们的 Vulkan shim **每个调用都包装**（且每次 push 3 次驱动调用）
  ⇒ **⇒ 差异最可能出在"提交层每次调用的固定开销"，被该视角的高调用量放大** ✓✓
- 与 §1 对应：**B1（F72）/ B2（`wd_note`）/ B3（逐调用解析）由"固定成本候选"升格为"高调用量视角的放大器"** ✓
  ⇒ §3 的廉价修复（缓存指针、`wd_note` 早退、F72 去 malloc/查表/env）**价值随之上升** ✓

**判定测试（新增；全部在"掉帧的那个视角"做）**

| # | 动作 | 判定阈值 |
|---|---|---|
| **T6** | Shift+F3 饼图，**VK 与 GL 在同一掉帧视角**对比（MC 饼图只计 CPU 侧） | VK 的 `render` 区块占比远大于 GL ⇒ **CPU/提交侧**（含我们的包装）✓；两者相近 ⇒ 不在调用侧 ✗ |
| **T7** | 「渲染 env」填 `MEOW_VK_DROP_PUSH_DESCRIPTOR=1` | FPS 恢复 ⇒ **F72 确诊** ✓✓ |
| **T8** | 「渲染 env」填 `MEOW_VK_DROP_DRAW=1` | FPS 恢复 ⇒ 绘制执行/GPU 侧 ✗；**仍 20–30 ⇒ CPU 提交侧** ✓（含我们的包装）|

**待补（用户可直接回答）**：那个掉帧位置**有什么内容**？（水 / 大量透明方块 / 红石 / 大量实体 / 告示牌 / 地图 / 下雨 / 信标 / 大量同屏区块交界）
—— 用户已答（2026-09-19）：**"视野里什么都有：大量建筑、实体（小动物）"** ⇒ 与"该视角调用量暴涨"一致 ✓。

---

**记录 4（2026-09-19，用户实测 + MC 崩溃报告）**
- `MEOW_VK_DROP_PUSH_DESCRIPTOR=1` ⇒ **MC 自己抛 Java 异常退出**（非驱动崩溃），报告在用户游戏目录
  `stuffs/test-fabric/versions/26.2-Fabric/crash-reports/crash-2026-09-19_12.43.41-client.txt`：
  `com.mojang.blaze3d.GpuDeviceLossException: VK_ERROR_DEVICE_LOST: Failed to wait for semaphore`
  @ `VulkanCommandEncoder.awaitSubmitCompletion(:564)` ← `submit(:213)` ← `Minecraft.renderFrame(:1397)`
  ⇒ **T7 作废**；`MEOW_VK_DROP_DRAW=1` 全黑无法导航 ⇒ **T8 作废**（两者设计目的是**帧级 bisect**，不是稳态 A/B）。
  ⇒ 仍可用：**T6（同视角 VK/GL 饼图对拍）** ✓。
- ★ 结构性事实：**MC 每帧在渲染线程上等一次"本帧提交完成"**（`awaitSubmitCompletion`）⇒ **1 帧深流水、CPU 与 GPU 串行**
  ⇒ 解释了"重场景更疼"（串行下帧时间 ≈ CPU + GPU，流水掩盖不掉）。本机一帧一条合并提交 ⇒ 该等待与"等本帧提交"等价 ⇒ 此处无免费收益。
- 会话环境（同日志）：`Window size 640x332`、`Surface acquired, MAILBOX, 640x332`、`Graphics Backend: Vulkan`、
  `Drivers 1.2.309 Maleoon 916`、**`Render Distance 12/12`**、`CPU 20x KirinX90`、Fabric 实例带 `sodium 0.9.2+mc26.2`。
- **F87 已落地**（2026-09-19，shim tag `.65 per-call-cost-fixes`）：`wd_note` 未 armed 早退 · 热命令解析指针缓存（30 个 `vkCmd*` + 提交 + F72 三个）
  · F72 两个 env 惰性一次 · F72 两处查表加"上次命中"缓存；**推迟**：每 push 的 `malloc/free`（需生命周期设计）。
  证据 `stuffs/research/vulkan/fixes/F87-per-call-cost-fixes.md`。

**记录 5（2026-09-19，用户实测 F87 收益）**
- 同一掉帧视角：**F87 前 20–30 FPS ⇒ F87 后 30+ FPS** ✓ ⇒ **"每次调用固定开销 × 该视角调用量"假设获实测支持** ✓✓
- T6 饼图：GL 与 VK 的 `frame` 区块占比**都是 ~82%** ⇒ **不具区分力** ✗（CPU 侧分块比例相同，只是总帧时间不同）⇒ 该路线收益有限，改由"帧数 A/B + 逐调用代码审计"推进 ✓。
- 剩余可打项：① F72 每 push 的 `malloc`/`free` + `memcpy`（F87 推迟）② **F72 每 push 一次 `vkAllocateDescriptorSets`**（改按帧复用环 ⇒ 每 push 驱动调用 3 → 2）③ **全热路径再审计**
  （`wd_note` 曾被漏掉 ⇒ 同类漏网需重扫；已派 `stuffs/research/vulkan/perf/PF-bridge-percall-audit.md`）。

**记录 6（2026-09-19，F72 复用一役的实况：F88 → F89 → F90）**
- **F88（tag `.66`）**：① R1（去每 push 的 `malloc`/`free`+`memcpy`，改文件级 scratch）**保留至今** ✓
  ② R2（按 layout 分桶复用描述符集）**上机即失败** ✗ —— 计数器签名：`reused` 冻结 46、`pools`/`grow` **每 256 次 push +1** ⇒ 池无界增长 ⇒ `VK_ERROR_DEVICE_LOST`。
- **F89（tag `.67`）**：把复用改挂"自由表 + 整池 reset" ⇒ **更糟** ✗ —— `emulated=5` 时已有 2 个池（约每 2 次 push 换池）⇒ 立刻丢器件。
- **F90（tag `.68`）**：**摘掉复用层** ✓ —— acquire 回到"每 push `vkAllocateDescriptorSets`"，**换池只在 `nsets>=MEOW_F72_MAXSETS` 或 `VK_ERROR_OUT_OF_POOL_MEMORY`**，reset 仍为 fence-signaled 整池回收 ✓；`MEOW_VK_F72_REUSE` 已删 ✓。用户实机确认可玩 ✓。
- **未做**：复用（每 push 省一次 Allocate）—— 收益存疑（F87 未碰 Allocate 即获实测收益；一次 push 的 3 个驱动调用里 Allocate 很可能最便宜）⇒ 登记为**带前置不变量 + 计数器门槛**的设计项 ✓。
- 证据：`stuffs/research/vulkan/fixes/F88-f72-perpush-cost.md`、`stuffs/research/vulkan/fixes/F89-f72-reuse-fixed.md`、`stuffs/research/vulkan/fixes/F90-f72-drop-reuse.md`。

**记录 7（2026-09-19，F87+R1+F90 三路独立对抗式复核）**
三路只读复核（A39 F87 正确性 / A40 F72 池生命周期 / A41 回归与文档）裁决**均为 PASS-WITH-FINDINGS、无 Critical** ✓。
- **H1 日志回归（必修）**：`totals` 的打印触发在 F90 后新增了 `resets`，而 `resets` **每帧 +1** ⇒ 稳态 **~1 行/帧**（30 FPS ⇒ ~5.4 万行/30min）✗，推翻 F86「静默」口径（A40 F-01、A41 F-01 双路独立命中）。
- **H2 池钉死（必修）**：`meow_f72_pool_free` 对 `pending && fence==0` 恒返 0，而 owned-fence 门受 `g_f72_owned_refs==0` 节流 ⇒ 该池**永久不可回收**、缓推 `MEOW_F72_NPOOLS=64` 上限；到顶后 `ensure_active` 会回退到**真实 `vkCmdPushDescriptorSet`**（历史丢器件路径）⇒ **是降级不是安全** ✗（A40 F-02）。
- **M1 两个竞态（仅在"多线程录制"下成立）**：`meow_cached_proc` 的 `*slot`/`*devSlot` 两次独立 store 可交错成"用 A device 调 B 的函数指针"；`meow_f72_lookup_dsl`/`dsl_find` 快路径可返回**另一个 layout 的 set**（A39 F1/F2）。shim 既有契约是"**假定单渲染线程**"（A10 §G5）⇒ 单线程下两者均安全 ✓ ⇒ 用一次 `gettid()` 观测闭合该前提。
- **M2 文档-代码矛盾**：本文件 `记录 6` 曾把 R2 记为"成功"、并提到已删的 `MEOW_VK_F72_REUSE=0` ⇒ 已在记录 6 更正（A41 F-02）。
- **未被波及** ✓：非 Vulkan 档完全未受影响、构建/导出符号面不变、无 F88/F89 死代码残留（仅 `reclaims`/`reuse_hits` 恒 0 的死字段）、开关语义与 Tier 表 / `运行时环境变量.md` 账实相符 ✓。
- 报告：`stuffs/research/vulkan/reviews/A39-f87-correctness.md`、`stuffs/research/vulkan/reviews/A40-f72-pool-lifecycle.md`、`stuffs/research/vulkan/reviews/A41-regressions-and-docs.md`。

**记录 8（2026-09-19，四路深挖：「复杂场景差在哪」的根因结论）**
方法：四路只读深挖（G1 官方文档与平台路径 / G2 MC 用法 vs 理想实现 / G3 定量归因 / G4 GL·Zink 反向推理），
以马良官方准则 `stuffs/research/vulkan/docs-maleoon-gpu-best-practices.md` 作为「标准理想实现」基准。
报告：`stuffs/research/vulkan/perf/G1-official-docs-and-paths.md`、`stuffs/research/vulkan/perf/G2-mc-vs-ideal-vulkan.md`、
`stuffs/research/vulkan/perf/G3-quantitative-attribution.md`、`stuffs/research/vulkan/perf/G4-gl-zink-vs-native-vulkan.md`。

**★ 根因（机制级，按证据强度排序）**
1. **CPU 与 GPU 不重叠 + 每帧同步合流**（最强）：Vulkan 档由 **MC 渲染线程同步逐调用**走 shim→ICD，且**每帧等本帧提交完成**
   （MC 的 `awaitSubmitCompletion`；我方 **F69 阻塞式 `vkWaitForFences(UINT64_MAX)`**，`meowvulkan.c` 约 `:2485`）
   ⇒ 帧时间 ≈ CPU + GPU ⇒ **命令越多越痛**。
   对照 **GL 档**：Mesa **glthread**（`GALLIUM_THREAD=1`）把 GL 调用**入队交独立线程执行**，且末端只有 `eglSwapBuffers`（`swapInterval=0`）**无每帧完成等待** ⇒ CPU 与 GPU 重叠 ✓。
   **可证伪预言（$0、零重编）**：GL 档设 **`GALLIUM_THREAD=0`** ⇒ 重视角应显著降至接近 Vulkan 档；若仍 50–60 ⇒「线程化 + 不等待」这一主因被证伪。
2. **每次调用的固定开销被命令数放大**（已有实测）：F87 削减 per-call 成本后同视角 **20–30 → 30+ FPS** ⇒ 该项可观 ✓；
   其中 **F72 把每次 push 放大成 3 次驱动调用**（实测 ≈**220 push/帧** ⇒ ≈660 驱动调用/帧 + ≈220 个新 descriptor set/帧 + ≈1 次整池 reset/帧）。
   GL 档恰好**不逐调用付费**（glthread 入队），且 **Zink 用常规描述符集天然绕开本机 ICD 的 push 缺陷** ✓。
3. **MC 侧的用法不动点**（我们改不了）：每 draw 前 push descriptor、无 set 复用/bindless；本意 2-in-flight 但每帧 submit + 等完成。

**★ 可行路径（排序）**
- **P0 诊断（$0，最优先）**：GL 档 `GALLIUM_THREAD=0` 对照（见上预言）；并：同视角 GL/VK 读 Shift+F3 饼图 **`frame` 的绝对 ms**
  （此前只读占比 82% ✗ 无区分力）⇒ `frame_VK − frame_GL ≳10ms` ⇒ CPU（含 shim）为主；`≲3ms` 而 FPS 差 ≥50% ⇒ GPU/等待为主。
- **P1 我们这层（收益最高、风险最高）**：**F72 正确的按帧环复用**（3→2 驱动调用 + 去每帧 ≈220 次 set 分配 + 去每帧整池 reset）
  —— 已两次失败（`.66`/`.67`）⇒ **必须带前置不变量 + 计数器门**（条件已在 F90 §5 登记）。
- **P2 恢复并发**：**收窄 F69 的阻塞等待**（不再无限期 `vkWaitForFences`）—— 需正确性 A/B。
- **P3 收尾**：复核 F66 合并是否过度保守；清残余的每次调用重解析（F69 fence 辅助 / `vkBeginCommandBuffer` / DebugUtilsLabel）。
- **P4 平台（低优先）**：**XEngine** 的头文件 / `libxengine.so`（stub）/ syscap 均在 SDK 中 ✓，但**自适应 VRS 才是真 FPS 杠杆、需深度/重投影矩阵/render pass 注入 ⇒ shim 极难**；
  空间超分只提画质不提帧率 ⇒ **只值一次便宜的能力探测**，不值得立项。
- **官方口径**：文档称 SDK 支持 **Vulkan v1.4.309**（只列 FUNC 符号、不列扩展/feature），设备实测只按 **1.2.309** 上报 ⇒ 该差距正是 shim 存在的原因；**未找到**驱动升级或例外渠道。

**记录 9（2026-09-19，P0 判别实验：主因确证）**
- **GL 档 `GALLIUM_THREAD=0`（关掉线程化渲染）⇒ GL 也只剩 20–30 FPS，且「视角转到哪里都没用」** ✓（用户实测）
  ⇒ **主因确证**：GL 之所以快，靠的正是 **Mesa glthread 把 GL 调用入队、交独立线程执行**；关掉它，GL 立刻退化到与 Vulkan 档同一量级 ✓✓
  ⇒ 且**无视角依赖**（各方向都同样低）= **恒定的每次调用成本**；而 Vulkan 档只在重视角掉帧 = 同一病因被"命令数"放大 ✓
- **⇒ 战线确定（按此开工）**：
  ① **恢复 CPU/GPU 重叠**：收窄 F69 的阻塞等待（**硬约束：宁多等不可少等** ✓，绝不可读到未完成的帧 ✗）
  ② **继续压低每次调用成本**：清残余每次调用重解析 + 对付 F72 的"每 push 3 次驱动调用"
  ③ F72 复用一类高风险项：**改为默认关的 opt-in 开关**，计数器可自证；**默认路径绝不受影响** ✓（保证再也不会"开不开都崩"）

**记录 10（2026-09-19，F92 落地：并发恢复 + opt-in 环复用）**
- **A 清残余每次调用重解析** ✓：F69 四个 fence 辅助（其中 `getFenceStatus` 原为**每帧每池**一次 ✗）、`vkBeginCommandBuffer`、`vkAllocateCommandBuffers`、
  DebugUtilsLabel×3、等待类入口（`vkWaitSemaphores`/`vkGetSemaphoreCounterValue`/`vkDeviceWaitIdle`/`vkQueueWaitIdle`）、`vkResetDescriptorPool`、
  `vkAcquireNextImageKHR`/`vkQueuePresentKHR`、`meow_vk_drop_draw` 的每 draw `getenv` ⇒ **热路径裸 `g_gdpa(` 重解析 = 0** ✓
- **B 不多等、不少等**（硬不变量 I1：**宁多等不可少等**）：给 F69/F72 记账加**一次性 signaled 位**（只由真实 `VK_SUCCESS` 置位、随 fence 生命周期清除）⇒
  **已确证完成则跳过阻塞等待** ✓，未命中则**原样** `vkWaitForFences` ✓（不伪造成功、不少等 ✓）
- **C F72 环复用改为 opt-in（默认关）** ✓：`MEOW_VK_F72_RING=1` 才启用（Tier B）；不变量
  **I2**（自由表空 ⇒ 仍在**当前池** Allocate；只在容量耗尽或 `OUT_OF_POOL_MEMORY` 才换池 ✓ —— 即修掉 `.67` 的病）、
  **I3**（只在该池 reset 边界回收）、**I4**（同帧不得发同一个 set 两次）；计数器 `ring_hits`/`ring_misses` 加在**现有** totals 行 ✓（不新增打印点 ✓）
- 逃生：**去掉该 env 即回到默认安全路径**（无需重建 ✓）⇒ 把"两次崩"的教训制度化 ✓
- 实机标签：`.70 concurrency-and-c-percall`；证据 `stuffs/research/vulkan/fixes/F92-concurrency-and-percall.md`
- 待用户核对：① 默认路径体感与 `gapMs`（等待段应缩短）② `MEOW_VK_F72_RING=1` 时 `ring_hits↑`、`allocs≪emulated`、`pools/grow` 有界、`forwarded=0`、不崩 ✓
- **PF bridge 逐调用审计**（`stuffs/research/vulkan/perf/PF-bridge-percall-audit.md`）：**Vulkan 逐帧循环内未发现同类漏网** ✓。
  另列同类漏网（但不在 Vulkan 帧循环）：`meow_bt_install_once` 每帧 `getenv`（GL 档，由 `meowSwapBuffers` 触发）、`meow_rate_tick` 每输入事件 `clock_gettime`、
  `glfwGetInstanceProcAddress` 每次 `dlsym`+`strcmp`（仅 proc 查询期）、`meow_gl_info_once`（GL 档）、NAPI `MeowGetInputRate` 每次 `dlsym`（频率待证）。

**记录 11（2026-09-19，F93：`.70` 默认路径池回收冻结的真因与修复）**
- 真因（代码可证）：F92-B 新增的 `MeowF69Map.signaled` 位**未在写入处初始化**，`MEOW_F69_MAX_ENTRIES=64` 淘汰槽复用时继承上一轮陈旧“已完成”位 ⇒ **伪造完成/少等**
  （`completion_proven` / 合并提交 timeline WAIT / `WaitSemaphores` 的 `allProven` / `signaled_value` 四处消费）⇒ 池完成 fence 读不到 SIGNALED ⇒ 回收冻结、`grow` 无界 ⇒ 卡死 SIGABRT。
  任务初判的两条（`p->fence==0`、`getFenceStatus` 缓存坏）均**证伪**。
- 修：`meow_f69_add_entry` 写入处清 0；`grow_streak>=2` 早阀；`reclaim_fail_nofence/_noquery/_notsignaled` 三计数（并入现有 `F72b push totals` 行，无新打印点）。
- tag `.71 fix-pool-reclaim`；证据 工作区根 `stuffs/research/vulkan/fixes/F93-fix-pool-reclaim.md`。

**记录 12（2026-09-19，F94：回收改用 F60 已证 queue-idle 边界）**
- 逐条证伪三条候选（MC 销毁我们记录的 fence / fence 挂在被合并掉的提交上 / `signaled` 与池回收耦合）；③「只判 `==VK_SUCCESS`，无法区分 `VK_NOT_READY` 与错误码」是**观测缺口**
  ⇒ 补 `reclaim_status_notready/_error/_proven` 与 `bind_pools`（并入现有 `F72b push totals` 行）。
- 真因：回收**过度依赖单个 fence**，且扫描会把 reset 未成功的满池**直接复用**（`nsets≈256` ⇒ 每 256 push 白长一池）。修：新增 `meow_f72_reclaim_pending_now`，
  在 F60 `vkQueueWaitIdle==VK_SUCCESS`（整队列完成证明）后回收 pending 池；扫描禁止复用未 reset 的 pending 池；`bind_submit` 写入新 fence 处清 `fenceSignaled`。
- tag `.72 pool-fence-fix`；证据 工作区根 `stuffs/research/vulkan/fixes/F94-pool-fence-fix.md`。

**记录 13（2026-09-19，F95：无 35 容量表 ⇒ 定性“成功 bind 停摆”）**
- 穷举文件内 14 张定长表/容量：**不存在容量为 35 的表**；35 只是三个计数（`resets` / `bind_pools` / `reclaim_status_proven`）同时停摆的**时点计数**。
  三者同停是必然（成功 bind 停 ⇒ 无池转 pending ⇒ `pool_free`/reset 不再触发）。真凶是一条“成功 bind 停摆”事件（W1 提交失败 / W2 bind 未被调用），**不是某张 35 容量的表**。
- 修：`meow_f72_quiesce_and_reclaim` 的回收对象从“仅 pending”扩为“所有 `!used` 且 `nsets>0`”的池（搁浅池）；
  新增判别计数 `bind_fail/fence0_bind/dead_full_skip/stranded_reset/borrow_full/f69_evict`（并入现有行、无新打印点）。
- tag `.73 fix-cap-saturation`；证据 工作区根 `stuffs/research/vulkan/fixes/F95-fix-cap-saturation.md`。

**记录 14（2026-09-19，F96：证伪 `count==1` 跳过 bind + 补齐“真实提交未登记”路径）**
- 证伪：MC 只用 sync2 提交（`vkQueueSubmit2KHR`），经 F66 合并分支**本无条件 bind** ⇒「一帧 2 entry 导致 `count==1` 守卫跳过 bind」对默认路径**不成立**。
- 但三条**真实执行却没登记**的路径存在：① v1 `vkQueueSubmit` 多 entry（旧 `count==1` 守卫）② F49 split 分支 ③ sync2 直通分支。
  修：`count>=1`（Vulkan 规定单个 `VkFence` 覆盖整批 `pSubmits`）；为 split / 直通按需建 shim tracking fence 并各补一次 `meow_f72_bind_submit`；F66 合并分支保持原样。
- tag `.74 bind-merged-submit`；证据 工作区根 `stuffs/research/vulkan/fixes/F96-bind-merged-submit.md`。

**记录 15（2026-09-19，F97：残余 per-call / 每帧成本清理 A1–A3）**
- A1 `meow_f69_signaled_value` 的**逐 fence** `vkGetFenceStatus` 查询 → 改由**整队列 idle 证明**（新增 `meow_f69_mark_queue_idle`，在 F60 与 `quiesce_and_reclaim` 的 idle 成功边界置位**同队列**条目；被覆盖的值集合不变、报值语义不变）。
- A2 4 处 per-call `getenv`（`sync2_to_v1` / `wait_via_queue_idle` / `sync2v1_merge` / `f69`）改进程内读一次（判定逻辑与全部 `why` 字符串逐字不变）。
- A3 提交/barrier 翻译改**文件级 scratch**（去每帧 `calloc`/`free` 风暴），超容量回落原 `calloc` 路径、不截断。
- tag `.75 residual-percall-2`；证据 工作区根 `stuffs/research/vulkan/fixes/F97-residual-percall-2.md`。

**记录 16（2026-09-19，F98：池平台期可观测（opt-in）+ 实机核对通过）**
- 新增 **opt-in** env `MEOW_VK_TOTALS_SEC=<秒>`（默认关）：池到平台期也每 N 秒打印一次**既有** `F72b push totals` 行（不新增打印点、默认路径与 `.75` 逐字相同）。
  目的 = 把 F95 验收「三计数持续增长」由“对拍推断”变“直接观测”。
- **实机核对（2026-09-19，用户实测；shim `.76`，`MEOW_VK_TOTALS_SEC=10`）**：日志 = 主仓 `.logs/` 内导出的 hilog（`This PC-1789808108-hilog.txt`，807 行），会话正常退出（`JLI_Launch returned 0`），
  无 DEVICE_LOST / SIGABRT / F72b warn / no-free-pool。**1,245,696 次 push 全程 `pools = grow = 35`（有界）**；`resets` / `bind_pools` / `reclaim_status_proven` 单调增（35 → 7626 / 7628 / 7626）；
  判别计数 `bind_fail/fence0_bind/dead_full_skip/stranded_reset/borrow_full` 恒 0；`forwarded=0`、`reclaim_status_error=0`；
  `reclaim_fail_notsignaled == reclaim_status_notready`（同值增长）⇒ 未命中都是 `VK_NOT_READY`（下一轮即 proven），非错误句柄；FPS ≈30（= F87 档）。
- tag `.76 steady-state-totals`；证据 工作区根 `stuffs/research/vulkan/fixes/F98-steady-state-totals.md`。

**记录 17（2026-09-19，F99+F100：环复用升默认开 → 实机崩 → 定量根因 → 回退默认关）**
- **F99（tag `.77 ring-coverage-gate`）**：依 W2 取证（MC 26.2 每次 push 覆盖 set=0 全 layout）新增**运行时覆盖门** `meow_f72_push_covers`
  （不变量 **I5**：只有被证明"覆盖了该 layout 全部 binding"的 set 才允许复用，**无法验证的 layout 永不复用**），并把**环复用升为默认开**，
  新增 `ring_gate_reject` 计数。证据 工作区根 `stuffs/research/vulkan/fixes/F99-ring-coverage-gate.md`。
- **实机结果（2026-09-19，用户实测；`.77` 默认开）**：进世界 ⇒ **满屏闪 + 帧数极低**；设 `MEOW_VK_F72_RING=0` 立刻恢复。
  日志（用户导出）：坏 = 主仓 `.logs/` 的 `This PC-1789809113-hilog.txt`；对照（`=0`）= 主仓 `.logs/` 的 `This PC-1789809216-hilog.txt`。
- **★根因（定量，代码 + 实机双证）—— 环复用不可救活**：环复用用「自由表」**替代**了 `vkResetDescriptorPool`，
  而池的 `maxSets` 是**两次 reset 之间的累计分配预算**（`MEOW_F72_MAXSETS=256`/池 × `MEOW_F72_NPOOLS=64`）⇒ 不 reset ⇒ **描述符内存永不归还**。
  铁证：`allocs=13634 ≈ pools(54) × maxSets(256)=13824` ⇒ 预算打满 ⇒ `vkAllocateDescriptorSets` 恒返 `VK_ERROR_OUT_OF_POOL_MEMORY(-1000069000)`
  ⇒ 该 push **转发给坏的原生 `vkCmdPushDescriptorSet`** ⇒ `vkQueueSubmit2 rc=-4` **VK_ERROR_DEVICE_LOST** ⇒ 满屏闪 + 帧数极低。
  计数器签名（ring ON）：`forwarded=2458`、`pools=54`、`grow=54`、`dead_full_skip=121914`、`bind_fail=11`、`resets=0`；
  对照（`=0`）：`forwarded=0`、`allocs == emulated`、`dead_full_skip=0`、`pools=35` ⇒ 健康。
  不可救活的理由：归还描述符内存必须 `vkResetDescriptorPool`，而一次池 reset 会让池内**所有** set 失效（正是要复用的那些）⇒ 自由表失去意义；
  两条出路分别不可接受：① 池开到覆盖整场会话 ⇒ 无界显存；② "reset 后重新分配" ⇒ 复用收益归零。
  ⇒ **覆盖门（内容正确性）必要但不充分，真正的墙是容量生命周期**；收益仅推算 **0.1–1 ms/帧** ⇒ 不再尝试。
- **F100（tag `.78 ring-optin-revert`）**：把环复用**改回默认关**（`MEOW_VK_F72_RING=1` 仅研究用），**保留** F99 的覆盖门与 `ring_gate_reject` 计数。
  证据 工作区根 `stuffs/research/vulkan/fixes/F100-ring-optin-revert.md`。
- **F100 实机核验（2026-09-19，用户实测；默认档 + `MEOW_VK_TOTALS_SEC=10`）**：日志 = 主仓 `.logs/` 的 `This PC-1789809771-hilog.txt`。
  **2,499,328 次 push 全程 `pools = grow = 36`（有界）**；`allocs == emulated`；`ring_hits = ring_misses = ring_gate_reject = 0`；`forwarded=0`；
  判别计数 `bind_fail/fence0_bind/dead_full_skip/stranded_reset/borrow_full` 恒 0；`resets` 单调增（29 → 15158）；`reclaim_status_error=0`；
  **0 次 DEVICE_LOST**、**正常退出**（`JLI_Launch returned 0`）；用户确认画面正常。

**记录 17 附：同期两路只读取证的去路**
- **W1（F69 重叠可行性）**：结论 —— F69 的等待**已是最窄形式**（只对 MC 请求值的最小映射 fence 真等），
  "少等 / 挪线程 / 延后"**无法证明安全 ⇒ 不做**（MC 在 `awaitSubmitCompletion` 后紧接 `vkResetCommandPool`，少等即 UB）；
  **建议先加一次性等待计数**（每帧等待次数 / F69 命中 vs F60 整队列 drain 次数 / 等待墙钟），再决定是否动 F60。
  证据 工作区根 `stuffs/research/vulkan/perf/W1-f69-overlap-feasibility.md`。
- **W2（F72 环绑定覆盖率）**：覆盖率证明成立（MC 26.2 每次 push 覆盖 set=0 全 layout），但被 F100 否掉（内容正确性 ≠ 容量生命周期成立）；
  报告对 `mcrev/flows/*.txt` 的引用是**字节码偏移**（非行号），顶部已加口径更正横幅。证据 工作区根 `stuffs/research/vulkan/perf/W2-f72-ring-binding-coverage.md`。

### 5.1 F95 §6 判据更正（2026-09-19）

- F95 报告 §6 的判据「三计数冻结 + `bind_fail=0` ⇒ W2（bind 未调用）」**会误报健康 warm-up**：实测健康基线 `.68`（用户确认可玩）与 `.75` 在
  **同一 `emulated≈9000`** 处逐字段相同（`pools=36 grow=36 resets≈23/24`）⇒ 爬升期 `resets` 停滞是**正常现象**（池尚未陆续进入 pending），不是“bind 未调用”。
- **正确判据 = 与健康基线在同工作量点对拍，或看 `grow` 是否越过 36。**（记录 16 的 `.76` 实机读数即按此判据：1.246M push 全程 `pools=grow=35`、`resets` 单调增至 7626。）

**记录 18（2026-09-19，F101 等待计数 + F102 计时撤回：性能主线收官总账）**
- **F101（tag `.79 wait-counters`，纯诊断计数、零行为变化、不新增 env；唯一改动文件 `meowvulkan.c`）**：量化帧循环等待面。
  `.79` 默认档 + `MEOW_VK_TOTALS_SEC=10` 实机日志（2026-09-19 用户实测；日志 = 主仓 `.logs/` 的 `This PC-1789810491-hilog.txt`）末行为
  `emulated=834560 forwarded=0 pools=35 resets=5390 allocs=834560 grow=35 ring_*=0 bind_pools=5392` +
  `wait_calls=4454 wait_f69=4454 wait_drain=0 wait_fwd=0 wait_fence_ms=127 wait_drain_ms=0 gscv=0`；无 DEVICE_LOST。判读：
  1. **F60 整队列 drain 从未触发**（`wait_drain=0`）⇒ W1（记录 17 附）的「F60 每帧 drain」假设**被证伪** ⇒ W1 的 P1（消除同帧 F69+F60 双等待）**无靶子** ✗。
  2. **100% 的等待由 F69 服务**（`wait_f69 == wait_calls = 4454`）⇒ 翻译层已在最优路径上 ✓。
  3. 等待墙钟 **≈0.02 ms/帧**（口径：**下界**；单次耗时取整到 ms ⇒ 真值 ≤ `127+4454` ms，即最坏 ≤0.8 ms/帧）—— 相对 ~30 ms 帧时**可忽略** ⇒ **等待不是瓶颈** ✗。
  4. **`gscv=0`** ⇒ MC **从不调用** `vkGetSemaphoreCounterValue` ⇒ W1 #8「per-fence 查询税」在本 MC 上为零；同时了结 A8 与 F69 注释的分歧 —— **A8 对**（MC 不轮询时间线值）✓。
  5. `wait_fwd=0` ⇒ 从未落到坏的真 `vkWaitSemaphores` ✓；`pools=35`、`allocs == emulated`、无 DEVICE_LOST ⇒ 链路健康 ✓。
  证据 工作区根 `stuffs/research/vulkan/fixes/F101-wait-counters.md`（§6）。
- **F102（tag `.80 shim-time`）—— 已撤回（tag `.81 revert-shim-time`）**：opt-in 给 F72 push 路径计时（纯计时诊断、默认关、不改语义）。
  实机（2026-09-19 用户实测）进世界后 **14 次 `vkQueueSubmit2 returned rc=-4`（`VK_ERROR_DEVICE_LOST`）连续发生**、`maxGapMs=2201`、`bind_fail=7`，体感 ~1 FPS；
  **但计时自身读出 push 路径仅 0.22 ms/帧**（`t_push_ms=262` / 1201 帧；`t_push_upd_ms=66`、`t_push_bind_ms=9`），且日志 `gapMs` 分布 13–75 ms（无 >100 ms）
  ⇒ **无法确证因果**，按最小化原则**撤回**。撤后 `.81`（无任何 env）实机：**0 DEVICE_LOST**、`forwarded=0`、`pools=grow=36`（有界）、`allocs==emulated`、
  判别计数全 0、正常退出（`JLI_Launch returned 0`）⇒ 用户确认"没毛病了"。**F102 唯一有效产出**：**push 路径 ≈0.22 ms/帧 ⇒ 我方这层不是瓶颈**
  （与 V1/G3 的"每次调用类 ~1–2 ms"方向一致）。证据 工作区根 `stuffs/research/vulkan/fixes/F102-shim-time.md`（顶部横幅 + §6）。
- **收官总账（2026-09-19）**：**等待面 ≈0（F101）+ push 路径 0.22 ms/帧（F102）+ 环复用不可行（F100）⇒ 我方这一层（shim）的结构性收益已尽**；
  剩余 ~16 ms 差距（Vulkan ~30 vs GL 50–60）在 MC 自身 / 驱动 / GPU 侧。现状登记见 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §D/§C6。

**记录 19（2026-09-20，反编译源码级测绘 + 仪表实测 + 间接合批证否 + GPU 侧候选）**
- **资料与方法**：用户用社区工具把 MC 去混淆源码（Mojang 已取消混淆）反编译到 工作区根 `stuffs/research/vineflower/{26.2,26.3}/`；
  本轮**只研究 Vulkan、只看 26.3**（技术路线在 26.3 定形），派 11 个只读子 agent 分工测绘；综合报告 = 工作区根 `stuffs/research/vineflower/findings/00-synthesis.md`，MC 侧素材 = 同目录 `a1–a8`、GPU 侧 = 同目录 `c1–c3`、已撤回的实现记录 = 同目录 `b1`（均位于工作区根 `stuffs/research/vineflower/findings/`）。
- **行为全貌（26.3 `renderpearl.backend.vulkan`，代码可证）**：
  ① 每帧**恰好 1 次 `vkQueueSubmit2`**（2 条 `VkSubmitInfo2` entry，entry 数 = stages）；
  ② 同步 = **时间线 `vkWaitSemaphores`，在 `submit()` 内等 `currentSubmitIndex-2`**（`MAX_SUBMITS_IN_FLIGHT=2` 硬编码，超时 5s，**不用 VkFence**）；
  ③ 描述符 = **push descriptor，每"脏"draw 一次**（`anyDescriptorDirty` 门控），**全包无描述符池/set**；
  ④ present：`minImageCount=max(3,caps.min)`、`presentMode` 由用户配置直驱、acquire/present 用二进制信号量；
  ⑤ transient = 512KB 块×4 分配器按提交 rotate 复用（非每帧新建 buffer）；⑥ 每个 pipeline 建 2 条 graphics pipeline，**`pipelineCache` 传 0 ⇒ 无管线缓存/无落盘**；
  ⑦ 环 `MappableRingBuffer` 3 缓冲，每帧 rotate+createFence+await；⑧ **OIT（26.3 新增）把 TRANSLUCENT 地形重画 3 遍**（≥9 pass / ≥12 次整屏 draw-blit）；⑨ 每帧 1 次 main→swapchain **整屏 blit**；⑩ **每帧有重复 clear**（`GameRenderer:475` vs `LevelRenderer:254` 的 main color+depth ×2；`503` vs `686` 的 depth ×2）。
  ⑪ **能力门控**：地形"间接合批"门控 = `limits.maxDrawIndirectDrawCount>0 ∧ features.nonZeroFirstInstance ∧ !hints.multiDrawIndirectHasKnownIssues`，而 MC 在后端把后两者**硬编码为 true/false** ⇒ **唯一真实输入是 `VkPhysicalDeviceLimits.maxDrawIndirectCount`**；⑫ 身份黑名单 58 条 `(driverID=14,vendorID=32902=Intel,deviceID…)` 两代逐条相同（与本机无关）。
- **仪表实测（26.3 复杂场景；`.82 f103-instrumentation`，用户实测 + 导出 `.logs`）**：**每帧 1 次提交（2 entry）**、≈90 push / ≈320 draw / ≈540 bind / **≈36 barrier**、F72 池路径 `vkQueueWaitIdle` **0 次**；
  **60–64% 墙钟阻塞在 `vkWaitSemaphores`**（每帧 13.5–17.2 ms 等待 / 22–27 ms 帧时）⇒ **帧时由 GPU 吞吐主导，我方 shim 的 CPU 开销不是瓶颈**（与记录 18 的 F101/F102 结论一致）。
  ICD 真值：`maxDrawIndirectCount=4294967295`、`multiDrawIndirect=1`、`drawIndirectFirstInstance=1`、**`shaderDrawParameters=0`（而我们在 features2 里说谎它为 1）**、无 `VK_EXT_multi_draw`。
- **已证否（不必再做实验）**：
  ① **`maxDrawIndirectCount` 上报开关**：门控原本就开（ICD 报 0xFFFFFFFF）⇒ 三次可比运行 **37.6 / 44.6 / 41.8 FPS**，其中 **37.6 那次是游戏内下雨**（用户判明）⇒ **该开关对帧率无可测效应**；**F103 仪表与该 env 已用 `git checkout -- meowvulkan.c` 整体撤回**（设备重装回 `.81`），`MEOW_VK_ADVERTISE_INDIRECT` **现不存在**。
  ② **图像布局转换**：普通纹理全程 `GENERAL`，**每帧 0 次**转换（`VulkanGpuTexture.java:62-76`）。
  ③ **提高 imageCount（3→4–6）**：MC 硬编码 in-flight=2、阻塞点是等 GPU 提交完成，acquire 等待实测仅 0.2–1 ms/帧 ⇒ 无收益。
- **GPU 侧候选（排序 = 收益 × 安全度；均「只改 shim」）**：
  1. **诊断丢弃"全量 mem barrier"量上限** —— 唯一模板 `VulkanCommandEncoder.java:251-260`（双向 `ALL_COMMANDS`+`MEM_RW`、无 ranges），主体 `VulkanCommandEncoder.java:409 submitRenderPass` **每 render pass 一条 ≈36/帧**；丢弃本身**不合法** ⇒ 只作默认关诊断、测完撤回。
  2. 收窄该 catch-all mask（按 CB 内上一条命令类型；须为真实 hazard 的超集，漏 `SHADER_WRITE`/COMPUTE 会闪帧）。
  3. 相邻同模板 barrier 去重（安全、小）。 4. **去重 clear**（同附件、中间无绘制）。 5. 合并同附件连续 pass（clear→sky→main）。 6. presentMode `FIFO→FIFO_RELAXED`（预期小：acquire 等待本就小）。
- **不可影响（仅记录）**：**OIT 3× 重画 TRANSLUCENT 地形**（GPU 吞吐头号嫌疑，纯 MC 侧，shim 无从下手）；每帧 1 次 main→swapchain 整屏 blit（main 非 swapchain image ⇒ 无 0-copy 空间）。
- 证据：综合见 工作区根 `stuffs/research/vineflower/findings/00-synthesis.md`（§1–§7）；GPU 侧依据分别见 工作区根 `stuffs/research/vineflower/findings/c1-barriers-and-layouts.md`、工作区根 `stuffs/research/vineflower/findings/c2-passes-clears-blit.md`、工作区根 `stuffs/research/vineflower/findings/c3-swapchain-memory.md`；本记录实测读数口径见 工作区根 `stuffs/research/vineflower/findings/b1-shim-instrumentation-impl.md`（**顶部已标"已撤回"**）。
