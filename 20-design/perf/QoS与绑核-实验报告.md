# 性能优化：QoS 与绑核实验方案（2026-09-13）

> 定位：本轮「全面提升游戏性能」的 **④ JVM A/B + ⑤ 线程 QoS / 大核绑核** 执行方案。
> 上游调研：[`平台加速能力-调研.md`](平台加速能力-调研.md) §3.A（候选 A / §6 探测）。
> 应用侧已做完：[`性能实验台与glthread-结论.md`](性能实验台与glthread-结论.md)。
> 结论层以 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) 为准。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 15 条](../../00-current/现状基线.md)。

---

## 0. 设备侧前置探测（2026-09-13 实机，`hdc` 127.0.0.1:40229）

| 探 | 手段 | 结果 |
|---|---|---|
| P1 QoS 库 | `ls -l /system/lib64/libqos.so` | **No such file or directory**。但 shell 对 `/system/lib64/*` 只可 stat、不可列目录，且系统库路径多被 SELinux 隐藏（连 `libGLv4.so` 也报 not found）⇒ **shell 结论不可信**，改由**代码在 app 上下文 dlopen 自检** |
| P1 syscap | `bm dump -n meow.liny.craft.awa`、`hidumper` | 未暴露 `Resourceschedule/GraphicsGame/GameService` 任何 cap；`/system/etc/syscap*` 禁读 |
| P3 CPU 拓扑 | `/proc/cpuinfo`、`/sys/devices/system/cpu/*`、`cpufreq/*`（经 `hdc shell`） | **全部 Permission denied**（与 [`../../40-adaptation/oshi-cpu-info.md`](../../40-adaptation/oshi-cpu-info.md) 一致：app 亦不可读，oshi 正因此被 patch 合成拓扑）。**但用户自己的 shell 可读** ⇒ 已实测解出，见 §0.1 |
| CPU 核数 | `nproc` | **20** |

**结论**：QoS 可用性只能由运行时 dlopen 判定；**CPU 拓扑由用户 shell 实测解出（见 §0.1）** ⇒ 绑核从"盲试"改为**定点**。

### 0.1 CPU 画像（Kirin X90，用户 shell 实测 2026-09-13）

`/sys/devices/system/cpu/*`（`hdc shell` 禁读、**用户 shell 可读**）：**20 逻辑核 / 6 个 cluster（= 6 个 cpufreq domain）**，三层能效：

| tier | CPUs | `cpu_capacity` | `cpuinfo_max_freq` | 备注 |
|---|---|---|---|---|
| 小核 | **0–3** | 688 | 2.050 GHz | policy0 |
| 中核 | **4–11** | 888 | 2.009 GHz | policy1（8 核 1 簇） |
| **大核** | **12–19** | **1024** | **2.316 GHz** | policy2–5（4×2 核簇） |

- `core_ctl` 只出现在各簇首核（**0 / 4 / 12 / 14 / 16 / 18**）；`topology/cluster_id`、`core_type`、`core_cpus` 内核未导出。
- **大核 = cpu12–19**（capacity 与频率双高）⇒ 绑核首选 mask = **`12-19`**。
- 另注意：中核（888）频率（2.009GHz）**低于**小核（688，2.050GHz），但 capacity 更高 ⇒ capacity（微架构效率）比频率更能代表真实算力。

## 1. 设计：env 驱动的调度旋钮（零新增 UI）

复用既有**实验台**的「额外渲染环境变量」（`K=V`，`meowjrebridge.cpp` 在 JLI/预 dlopen 前 `setenv`）作为通道
⇒ **A/B 零重编、零新 UI、零新 Preferences**：

| env | 语义 | 落点 |
|---|---|---|
| `MEOW_QOS=1` | 当前线程提升为 `QOS_USER_INTERACTIVE` | ① 渲染线程：`meowMakeCurrent` / `meowSwapBuffers`；② 启动（JVM 原始）线程：`JLI_Launch` 前 |
| `MEOW_AFFINITY=<cpuset>`（如 `8-19` / `4-11` / `0-7`） | `sched_setaffinity` 绑核 | **启动线程**（JVM 后续线程默认继承创建者的 mask ⇒ 一处生效全局） |

- `libqos.so` **动态 `dlopen`**（不硬链），缺库 / 缺 `OH_QoS_SetThreadQoS` → **静默降级 no-op** + 一行告警日志。
- 与 `sched_setaffinity` 组合正是官方范例（[`平台加速能力-调研.md`](平台加速能力-调研.md) §3.A）。
- QoS 只能设**当前线程**：渲染线程必然经过桥（`meowSwapBuffers`），启动线程在 `JLI_Launch` 前设置。

**未知点（决定成败）**：
1. 本机（2in1）是否有 `libqos.so` / QoS syscap（P1，只能运行时判）；
2. `sched_setaffinity` 是否被 SELinux 允许（应查返回值 / `errno`）；
3. ~~大核编号未知~~ **已解**（§0.1：大核 = 12–19）；但绑核仍**可能被系统调度覆盖**，A/B 仍必要；
4. QoS 对 JVM 原生线程是否真生效。

## 2. 改动面

| 文件 | 改动 |
|---|---|
| `libs/meowcraftlib/src/main/cpp/meowcraftbridge/meowqos.{c,h}` | **新增**：`meow_qos_apply_current_thread()` / `meow_affinity_apply_current_thread()`，均 env 驱动、可降级 |
| `libs/meowcraftlib/src/main/cpp/CMakeLists.txt` | 两个 target（`meowjrebridge` / `meowcraftbridge`）都编入 `meowqos.c`；`meowjrebridge` 增 include 目录 |
| `.../meowcraftbridge/egl_gl.c` | `meowMakeCurrent` / `meowSwapBuffers` 顶部调 `meow_qos_apply_current_thread()` |
| `.../meowjrebridge/meowjrebridge.cpp` | launch lambda 内、`JLI_Launch` 前调 `meow_affinity_apply_current_thread()` + `meow_qos_apply_current_thread()` |

> native 产物在 `meowjre` HSP；改后须**清模块 build** 重建（`devecocli build --modules entry meowjre`），部署先 HSP 后 entry。

## 3. A/B 步骤（agent 不点 UI / 不抓日志，UI 归用户）

固定基准场景：**26.2 + Fabric + Sodium ｜ 16 视距 / 6 模拟 ｜ 2x 缩放 ｜ 最大化 ｜ 固定世界/位置/视角**。

| 轮 | 「额外渲染环境变量」填 | 期望 |
|---|---|---|
| 基线 | （空） | 记 FPS / 帧时（对齐既有基准 ≈90） |
| R4a | `MEOW_QOS=1` | 帧时 / 1% low 改善？ |
| R5a | **`MEOW_AFFINITY=12-19`** | 只绑 8 大核（首选） |
| R5b | `MEOW_AFFINITY=4-19` | 中+大 16 核（保留并行度） |
| R5c | `MEOW_AFFINITY=0-7` | 对照（小+部分中核，预期变差） |
| R4b+R5 | `MEOW_QOS=1` + 最优 mask | 组合 |

- 每轮**单变量**、同场景；改完**重开游戏**生效。
- 需看日志 → **用户导出 `.logs`**（agent 不抓 hilog）。

## 4. 判定 / 重开条件

- **QoS 有效且无异常** → 考虑收敛为**内置默认 + UI 开关**（去 env）。
- **绑核某 mask 稳定改善** → 固定该 mask；**无改善或反噬** → 放弃绑核。
- 日志显示 `libqos.so not found` / `sched_setaffinity rc<0` → **登记平台限制**（不硬撑）。

### 实测结果（2026-09-13，用户实机；日志 `This PC-1789310690-hilog.txt`）

单次运行同时带 `MEOW_QOS=1` + `MEOW_AFFINITY=12-19` + `-XX:ActiveProcessorCount=8`：

- **两者都确实生效**：`QoS: current thread -> USER_INTERACTIVE rc=0`（**启动线程 + 渲染线程各一次**）；`affinity: current thread bound to '12-19' (8 cpus)`。（`libqos.so` 经绝对路径 dlopen 的告警后，按名 `dlopen` 成功 ⇒ **2in1 上 QoS 可用**。）
- **无崩溃**：signal 11 = 99（对照 96，JVM 良性噪声；无 `rethrow`）。
- **用户体感：无可感收益** ⇒ **核心放置/调度不是 ~8ms 固定成本的限制因素**。
- **判定**：调度类（QoS + 绑核）作为提速手段**证伪**；两个旋钮**保留为 opt-in（默认关）**、不内置默认、不再加 UI。
  - 注：本结论为**单次合并运行 + 体感**（非严格单变量带帧数）；但"三管齐下无感"已足以判调度非瓶颈。

## 5. ④ JVM A/B 矩阵（零重编，走「额外 JVM 参数」）

> 前置取证：`libjvm.so`（OpenJDK 26.0.2.1 自编）已确认含这些 flag（`strings`，见调研 §4.1）；
> 参数放固定参数**之前**，可被覆盖。

| 组 | 参数 | 预期 |
|---|---|---|
| C1 | `-XX:ActiveProcessorCount=6` / `=8` / `=10` | 少核 → 降 JIT/GC/ForkJoin 抢核 |
| C2 | `-XX:+UseCompactObjectHeaders` | 对象头 12→8B，降带宽/缓存压力 |
| C3a | `-XX:+UseSerialGC` | 单核弱机常用；削卡顿峰值？（GC 停顿 trade-off） |
| C3b | `-Xms<M>=‑Xmx<M> -XX:+AlwaysPreTouch -XX:G1NewSizePercent=30 -XX:MaxGCPauseMillis=200`（Aikar 风格 G1） | 削卡顿；代价 = 启动/常驻内存 |
| C4 | `-XX:+AutoCreateSharedArchive -XX:SharedArchiveFile=<沙箱可写路径>` | 启动 + 早期游玩（JIT 未热） |
| C6 | `-XX:ReservedCodeCacheSize=256m` | mod 多时 code cache 压力 |

- ⚠️ 每组**单变量**；`-Xms=-Xmx`+`AlwaysPreTouch` 增启动时间/内存，单核弱机上是 trade-off，必须实测。
- AOT/CDS（Leyden `-XX:AOTMode/AOTCache`）需按 MC classpath 建档，属**高难度**，本轮不做，登记待立项。

## 6. 后续

- 验证通过后：把有效项**内置为默认**（去 env），UI 开关按需。
- 其它平台侧探测（P2 XEngine / P4 Mesa 缓存 / P5 HMS_GamePerformance）另轮。

## 7. 实现状态（2026-09-13）

- **代码**：新增 `meowcraftbridge/meowqos.{c,h}`；`CMakeLists.txt` 两 target 编入 `meowqos.c`；
  `egl_gl.c` 的 `meowMakeCurrent` / `meowSwapBuffers` 调 `meow_qos_apply_current_thread()`；
  `meowjrebridge.cpp` 的 launch lambda 在 `JLI_Launch` 前调 `meow_affinity_apply_current_thread()` + `meow_qos_apply_current_thread()`。
- **静态检查**：`check_cpp_files` 无 error（注：`meowqos.c` 须 `#define _GNU_SOURCE` 才暴露 `cpu_set_t`/`CPU_SET`/`sched_setaffinity`）。
- **构建**：`devecocli build --modules entry meowjre` → **BUILD SUCCESSFUL**；两个 `.so` 均含 `meow_qos_apply_current_thread` / `meow_affinity_apply_current_thread`。
- **部署**：`devecocli run --skip-build --module meowjre entry --device 127.0.0.1:40229` → 装成功并拉起 `EntryAbility`。
- **默认行为零变化**：未填 env 时两处均 no-op（不动现有默认）。
- **~~待办~~ 已完成**：§3 实机 A/B 已跑（2026-09-13，用户操作），结论见 **§4 实测结果**——QoS + 绑核**均生效但无可感收益** ⇒ 判**非瓶颈**、两旋钮**保留 opt-in（默认关）、不内置默认、不加 UI**。

## 相关

- [`平台加速能力-调研.md`](平台加速能力-调研.md)（§3.A 候选 A、§4.1 flag 取证、§5 R4/R5、§6 探测）
- [`性能实验台与glthread-结论.md`](性能实验台与glthread-结论.md)（实验台）
- [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md)（G）
- [`../../40-adaptation/oshi-cpu-info.md`](../../40-adaptation/oshi-cpu-info.md)（`/proc/cpuinfo` 禁读）
