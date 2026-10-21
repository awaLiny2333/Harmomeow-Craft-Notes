# GL 能力屏蔽：接口与操作规范

> 定位：**通用**（不限于 compute）。目标 = 让"某个 GL 能力在本进程 / 本设备上不可用"这件事
> **可配置、可验证、可撤销**，而不是散落的特例补丁。
> 实现面（为什么必须两层、代码落在哪）见 [`1.21.1-崩溃-两条链与随包规避.md`](1.21.1-崩溃-两条链与随包规避.md) §1(2)；
> 旋钮清单见 [`../../00-current/运行时环境变量.md`](../../00-current/运行时环境变量.md)。
> 状态（是否默认开、哪些芯片命中）以 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 23 条为准。

## 1. 四条硬规则

1. **先问"消费者从哪拿这个信息"，再选层** —— 屏蔽点必须落在**它真正读的那份数据**上。本机实测反例：
   过滤 `glGetStringi` ✗（LWJGL 不吃我们的 GL 包装）、只改扩展表 ✗（**函数槽型**探测如
   `check_ARB_compute_shader` 不含 `ext.contains`，够不着）、`MESA_EXTENSION_OVERRIDE` 单独用 ✗（改不了标志）。
2. **"能力"与"版本组"是两种东西，真值来源不同**：
   - **能力**（`GL_ARB_*`/`GL_EXT_*`）= "驱动**公布** + 入口**可解析**"（上游语义）；
   - **版本组**（`OpenGL11..OpenGL46`）= 上下文自报的 **`GL_VERSION`**
     （LWJGL 自己只塞**当前版本**那一个名字，所以低版本组必须靠版本号补 ✓）。
3. **至少落两个执行点，它们互补**：
   - ① **LWJGL 能力标志**（`MEOW_MASK_EXTENSIONS` → `RendererInit.isMasked`）⇒ 让**经 LWJGL 读能力**的模组
     走它自己设计好的降级路径（**不依赖它捕获异常** ✓）；
   - ② **Mesa 扩展表**（`MESA_EXTENSION_OVERRIDE`，启动器从**同一清单**派生、只取 `GL_*`）⇒ 让**绕过
     LWJGL** 的消费者也只会拿到**干净的 GL 错误**，而不是驱动崩溃 ✓。
4. **只做"真→假"**：伪造（假→真）需要驱动真能解析入口 ⇒ 不保证 ⇒ **不做** ✗。

## 2. 操作步骤（照做即可）

1. **选清单**：能力名写 `GL_ARB_x`；要压版本组写 `OpenGLxy`（如 `OpenGL46`）。
2. **下发**（都是**数据**、免重编，任选）：
   - 临时/排障：在「**额外渲染环境变量**」写 `MEOW_MASK_EXTENSIONS=GL_ARB_x,OpenGL46`
     （启动器自动派生 `MESA_EXTENSION_OVERRIDE=-GL_ARB_x` ⇒ **两层都生效** ✓）。
     ⚠️ **它是"整体替换"而不是追加** ✗：想"再补一个能力"必须**把默认那条一起写上**
     （本机默认 = `GL_ARB_compute_shader`），否则 compute 屏蔽会**两层同时消失**、Kirin 上崩溃回来 ✗。
     想**关掉**屏蔽则写**显式空**：`MEOW_MASK_EXTENSIONS=`（两层都不发 ✓）。
   - 长期默认：改 `GameLauncher.ets` 的 `defaultMask`（本机现为 Kirin + 现代路径 ⇒ `GL_ARB_compute_shader`）。
   - **面向用户的开关**：「编辑版本 → **屏蔽 GL_ARB_compute_shader**」（**逐实例**，**默认开 = 屏蔽** ——
     与 `MEOW_MASK_EXTENSIONS` 的"设/不设"语义一致 ✓）。**关掉它 = 不屏蔽**该能力、两层都不下发 ⇒
     模组可用 compute，但本机驱动不稳**可能直接崩** ⇒ 知情承担 ✓。它只影响 `defaultMask` 的取值，
     **优先级仍低于**显式 `MEOW_MASK_EXTENSIONS` ✓；落在
     `versions/<id>/.hmmcraft/instance-settings.json` 的 `hmmcraftComputeShaderMasked`，
     **仅显式 false 才写键**（稀疏文件 ✓，与 glthread 同构），启动自证行打
     `computeShader=on(default)/off(user)` ✓。
     **⚠️ 关掉它不会让用户在「额外渲染环境变量」里设的其它屏蔽失效** ✓：那份 `MEOW_MASK_EXTENSIONS` 会
     **整份覆盖**默认清单（`capMask = maskOverride === null ? defaultMask : maskOverride`）⇒ 此时开关
     **根本不参与** ✓；用户直接写的 `MESA_EXTENSION_OVERRIDE` 也因"后写覆盖"而仍然生效 ✓。

**实现位置（排查用；覆盖关系契约表在 [`../../00-current/运行时环境变量.md`](../../00-current/运行时环境变量.md) §1.2）**：
`meowjrebridge.cpp` 的 setenv 顺序 —— ① 桥内默认 `229–304` · ②③ 启动器拼行 + 用户文本 `308–333`（每行打
`extra render env: K=V` 日志）· ④ GL guard 失效安全 `376–379`（同时打 WARN）；启动器拼行在 `GameLauncher.ets`
的 `renderEnv`（顺序：`GALLIUM_THREAD` → `MEOW_GUARD_SYNC` → 屏蔽行 → 用户文本）✓。
   ⚠️ **两种入口影响的层数不同**：**env = 两层总闸**（启动器从它派生 Mesa 那半 ✓）；
   `-Dmeow.maskExtensions`（走「额外 JVM 参数」）**只驱动 ①**（与 env **并集**、只加不减；Mesa 那半看不到
   JVM 属性 ✗）⇒ 想两层都生效就写 env ✓。

3. **验证四判据**（缺一不可）：
   - **自证行**：`RendererInit: capability mask armed: […]` + 启动器 `capMask=on(…)`；
   - **行为判据**：该能力**不再被尝试**（本例：`Compiled culling/` ×0、`GL_INVALID_VALUE` **0**）；
   - **反例判据**：别信"没崩"——要看它走的是不是**设计好的降级路径**（本例 `pipeline/instancing` ×26 ✓）；
   - **不失真**：`groups …` 与 `GL_VERSION` 自证行一致（4.2 就报 4.2 ✓），别让屏蔽连带把版本组压坏 ✗。
4. **记录**：SBOM（[`../../30-supply-chain/assets-digests.txt`](../../30-supply-chain/assets-digests.txt)）写清单 + 产物摘要；
   notes 写机制与判据；代码里留**自证行**。
5. **可逆**：写 `MEOW_MASK_EXTENSIONS=`（**显式空** = 关掉屏蔽）✓；驱动修好后**应当撤销**（按芯片门控是**启发式** ✗）。

## 3. 禁止清单（全是**实测**或**结构性**反例）

| ✗ 别做 | 为什么 |
|---|---|
| 在 **GL 层**包装 `glGetStringi`/`GL_NUM_EXTENSIONS` | 到不了 LWJGL 的能力集（实测**零影响** ✗）|
| 只改**扩展表**（Mesa 或自建包装） | **函数槽型**探测（如 `check_ARB_compute_shader`）不含 `ext.contains` ⇒ 够不着（实测 ✗）|
| 去藏**必需**扩展（`SSBO`/`GL_ARB_shader_image_load_store` 等） | 会直接关掉依赖它的路径，**比降级更糟** ✗ —— 只藏那一个出问题的能力 |
| 用**版本号钝器**（`MESA_GL_VERSION_OVERRIDE` / `MESA_EXTENSION_MAX_YEAR`） | 会连带藏掉一片必需扩展 ✗（本机 Mesa 侧也没有 `MESA_VK_*` 之类可夹版本；负结论见 [`1.21.1-崩溃-两条链与随包规避.md`](1.21.1-崩溃-两条链与随包规避.md) §1）|
| **伪造**能力（假→真） | 需要驱动真能解析入口 ⇒ 不保证 ⇒ 不做 ✗ |
| 把"屏蔽"当成**修复** | 它把"驱动崩"换成"能力不可用"（性能代价）⇒ **真解在上游驱动**，要并行上报 ✓ |

## 4. 边界（诚实：通用 ≠ 万能）

- 只覆盖**能力标志**，**不动函数槽** ⇒ "忽略标志硬调该函数"的模组不会被拦住（由 **Mesa 层**兜成干净 GL 错误 ✓）。
- 只屏蔽**经 LWJGL** 的视图；模组若自带 JNI 直接查 GL ⇒ 只有 Mesa 层兜底 ✓。
- 键名 = LWJGL 字段名（= 扩展名；版本组 = `OpenGLxy`）；**换 LWJGL 世代要重生成** overlay
  （`gen_glcap.py` 带**硬失败**守卫：形状变了会报错，而不是静默生成**未经校验**的文件 ✓）。
- **实机范围的记录（2026-09-16）**：当时只在 NeoForge 1.21.1 + Create/Flywheel 上跑过；原版 / Fabric /
  1.20.2 / 26.x / gl4es 只核了**代码可达性**。⚠️ **当前状态一律以
  [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 23 条为准**（本文件只记机制与规范，
  不承担状态声明 ✓）。

## 相关

[`1.21.1-崩溃-两条链与随包规避.md`](1.21.1-崩溃-两条链与随包规避.md)（案例与取证）·
[`../../00-current/运行时环境变量.md`](../../00-current/运行时环境变量.md)（`MEOW_MASK_EXTENSIONS` / 覆盖关系）·
[`../../10-research/原生崩溃排查-方法论与复盘.md`](../../10-research/原生崩溃排查-方法论与复盘.md)（通用排查套路）·
[`../perf/glthread-GL-guard-方案.md`](../perf/glthread-GL-guard-方案.md)（另一条应用侧规避平台缺陷的先例）·
`tools/jre26/README.md`（JRE 构建与 digest）、工作区根 `stuffs/research/1.21.1-crash-2026-09-16/`（物证）
