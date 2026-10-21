# 性能：实验台与基准（glthread 已应用侧修复）

> 定位：一次「全面提升游戏性能」调查的**结论层**留档 —— ①用户基准 ②**常驻实验台**（新增资产）
> ③glthread 的结论与指针 ④本次保留的改动 ⑤剩余候选（按优先级）。
> **glthread 的根因与修复**（GL guard 转发层）见 [`glthread-GL-guard-方案.md`](glthread-GL-guard-方案.md)；
> **可提交上游的崩溃证据**见 [`glthread崩溃-Bug报告.md`](glthread崩溃-Bug报告.md)。
> 本文为决策记录，**不复述现状**；当前状态见 [现状基线.md §5 第 16 条](../../00-current/现状基线.md)。

## 0. 基准（用户定义，2026-09-13）

**26.2 + Fabric + Sodium ｜ 16 视距 / 6 模拟距离 ｜ 2x 缩放 ｜ 窗口最大化 ｜ 固定世界/固定位置/固定视角**

FPS 随「显示缩放」N（渲染分辨率 = 窗口 / N）：

| N | 渲染像素 | 帧时 | FPS |
|---|---|---|---|
| 1x | 1.85 MP | 22.2 ms | ≈45 |
| 1.5x | 0.82 MP | 16.7 ms | ≈60 |
| 2x | 0.46 MP | 11.1 ms | ≈90 |
| 4x | 0.12 MP | 9.1 ms | ≈110+ |

拟合 `帧时 ≈ 8 ms(固定) + 7.5 ms/MP` → **固定每帧成本是大头**（4x 只渲染 0.12MP 仍要 9.1ms）。这也是当初去试 glthread 的原因。
（另：固定渲染分辨率、只变窗口大小 → FPS 近似，排除"合成器上采样成本"。）

## 1. 实验台（常驻资产，本次新增）

| 旋钮 | 位置 | 说明 |
|---|---|---|
| **额外渲染环境变量** | 高级选项 | `K=V`，换行或 `;` 分隔；**启动前 setenv**，可覆盖内置默认（`GALLIUM_THREAD`/`ZINK_*`/`MESA_*`…） |
| **额外 JVM 参数** | 高级选项 | 空格/换行分隔，原样追加到 argv（放固定参数之前，允许被覆盖） |

- 注入点：渲染 env = `meowjrebridge.cpp` setenv 块（**预 dlopen 渲染器之前**——Mesa 在 screen init 读 env）；JVM 参数 = `MinecraftLauncher.buildLaunchArgv`。
- 改完**下次开游戏生效**（落**应用级全局设置** `app-settings.json` 的 `global.runtime` 组，游戏进程启动时读）。
- 文件：`constants/Constants.ets`、`data/GlobalSettings.ets`、`data/SettingsTools.ets`、`data/MinecraftLauncher.ets`、`data/GameLauncher.ets`、`state/JvmLauncher.ets`、`components/AdvancedOptionsView.ets`、`resources/base/element/string.json`、`libs/meowcraftlib/src/main/cpp/{meowjrebridge/meowjrebridge.cpp,types/libmeowjrebridge/Index.d.ts}`。

## 2. glthread（结论 + 指针）

**收益**：开 `GALLIUM_THREAD=1` 帧数明显提升（用户：最高 >100%）。**代价**：glthread 本身增输入/present 延迟（当年关它的原因），需一起评估。

**根因**：Mesa **`tc_texture_subdata` 不做客户端数据同步拷贝**，把客户端像素指针原样转发给 `zink_buffer_subdata`，TC flush（在 Render 线程）时读**已释放**的客户端缓冲 ⇒ UAF（崩溃落在 `libgallium+0xE26CC4` 调 `memcpy` 读野指针）。详见 [`../render/MC26.x渲染栈-差异分析.md`](../render/MC26.x渲染栈-差异分析.md) §5。

**修复（应用侧）= GL guard 转发层**：native `libmeowglguard.so` 作 LWJGL 的 OpenGL 库（`-Dorg.lwjgl.opengl.libname`），对**贴图上传家族 8 个入口**做后置同步；`MEOW_GUARD_SYNC` **按 MC 版本自动**（**仅 ≤1.21.x 免同步**，其余每次 `flush`）；线程化渲染为**「编辑版本」里的逐版本 Toggle（默认开）**，**对桌面 GL 与 GL4ES 后端都生效**（GL4ES 的 GLES 后端也是 Mesa ⇒ Zink）。设计与实机证据见 [`glthread-GL-guard-方案.md`](glthread-GL-guard-方案.md)；上游修复建议见 [`glthread崩溃-Bug报告.md`](glthread崩溃-Bug报告.md)。

> 本文曾据"应用侧不可修"的判定登记平台限制 **A7**；该判定已被应用侧 GL guard 取代（A7 转为已修复）。当前口径见 [现状基线.md §5 第 16 条](../../00-current/现状基线.md)。

## 3. 本次保留的改动

| 改动 | 处置 |
|---|---|
| 实验台（渲染 env + 额外 JVM 参数） | **保留**（长期有用；A/B 零重编） |
| `egl_drop_surface()` 的 glthread drain（`glFinish`，仅 glthread 时触发） | **保留**（Mesa 契约；glthread 关时 no-op，零开销） |
| `GALLIUM_THREAD` 行的警示注释（含本次证据） | **保留** |
| 信号状态诊断（`LogSignalState`） | **已移除**（一次性排查用，结论已入档） |

## 4. 剩余性能候选（按优先级）

> 平台侧能力已单独立档 → [`平台加速能力-调研.md`](平台加速能力-调研.md)
> （QoS + 绑核、**超帧/ABR/OpenGTX/XEngine 的可用性判定**、马良 GLES 反模式、Mesa 着色器缓存、
> 随包 `libjvm.so` flag 静态取证、实验顺序 R1–R9、待探测清单 P1–P6）。

| 优先 | 项 | 预期 | 手段 / 备注 |
|---|---|---|---|
| **高** | **游戏侧 mod 组合**：Sodium 已在用；再叠 Lithium / FerriteCore / ImmediatelyFast / EntityCulling / ModernFix 等 | 常再涨 **20–60%** | 启动器引导或一键安装（Fabric 已支持） |
| **高** | **画质/视距预设**（`options.txt`：视距/图形=流畅/平滑光照/实体距离/粒子/mipmap/maxFps） | 直接（视距成本平方级） | 启动器随版本给预设 |
| 中 | JVM：GC 选择（G1 / Serial / ZGC）+ Aikar 风格 G1、`-Xms=-Xmx` + `AlwaysPreTouch`、`-XX:ActiveProcessorCount`（已有旋钮）、`-XX:+UseCompactObjectHeaders` | 削卡顿 / 削峰值 | **实验台零代码 A/B** |
| 中 | **AOT/CDS（JDK26 Leyden，`-XX:AOTCache`）**：目前**随包零 CDS/AOT 档** | 启动 + 早期游玩明显改善 | 需按 MC classpath 建档 |
| 中 | Mesa **磁盘着色器/管线缓存落地**（`MESA_SHADER_CACHE_DIR` 指向持久目录；先用 `MESA_SHADER_CACHE_SHOW_STATS=1` 验证是否在写） | 二次启动更快 + 首次卡顿减少 | 实验台 |
| 低 | present/延迟：`vblank_mode=0`（已有）、Zink present 模式 | 小幅 | 实验台 |
| 低 | 游戏独立进程 + 线程优先级/QoS（大核亲和） | 不确定（IPC 代价） | 需改架构 |
| 深水 | **Vulkan 后端解锁**（去掉 Zink 的 GL→Vulkan 二次翻译） | 潜在最大**结构性**收益 | **已达成**（界面选 Vulkan 即用；见 [已知限制与待解.md](../../00-current/已知限制与待解.md) A6 与 [现状基线.md §5 第 24 条](../../00-current/现状基线.md)）；其性能差距登记见 [`Vulkan后端-性能瓶颈清单与实验计划.md`](Vulkan后端-性能瓶颈清单与实验计划.md) |

## 相关

- [现状基线.md](../../00-current/现状基线.md) §5 第 16 条；[`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md)（A7 / G）；
  [`../render/渲染链-结论.md`](../render/渲染链-结论.md)；[`../../90-archive/输入延迟调查证据.md`](../../90-archive/输入延迟调查证据.md)
- 渲染后端/GL profile 决策：[`../launch/决策与不变量.md`](../launch/决策与不变量.md)
