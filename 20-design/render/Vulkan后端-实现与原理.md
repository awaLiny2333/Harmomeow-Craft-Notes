# MC 原生 Vulkan 后端在本机跑通的原理

> **定位**：本文是 Vulkan loader shim 的**权威机制 / 原理**表述 —— 只讲**为什么需要 shim**、**每一级墙的真因与解法为什么成立**、
> **哪些是必需内置行为 / 哪些是诊断开关**、**边界与未解**。
> **不复述现状**：可用性、性能差距、未决项一律走指针 —— 见 [`现状基线.md`](../../00-current/现状基线.md) §5 第 24 条与
> [`已知限制与待解.md`](../../00-current/已知限制与待解.md) §H。
> **取证 / 读数 / 设备事实 / 过程记录**见 [`Vulkan后端-取证存档.md`](Vulkan后端-取证存档.md)；旧结案档（判 BLOCKED、结论已被推翻）在
> [`../../90-archive/Vulkan后端-跟进与结案.md`](../../90-archive/Vulkan后端-跟进与结案.md)。
> **本机** = 鸿蒙 PC（Maleoon 916 / OpenHarmony 7.0.0.105，API 26）；**主仓** = `<工作区根>/Harmomeow-Craft-Launcher`。
> **行号基准**：主仓 `libs/meowcraftlib/src/main/cpp/meowcraftbridge/meowvulkan.c`（下文 `<shim>.c`）；
> 符号名稳定、行号随重构失效；引用真 API 一律以**调用方生成头** `ref/lwjgl3/.../vulkan/vulkan_core.h` 为准。

---

## 1. 起点：为什么必须有一个 shim

### 1.1 这个 ICD 做的事：只裁"广告面"，不裁"能力"

本机唯一 ICD（`/vendor/lib64/passthrough/vulkan.hvgr_v210.so`）是一个 **1.4 时代实现**，却对外报
**`apiVersion = 1.2.309`**、device 扩展 69 个（[`Vulkan后端-取证存档.md`](Vulkan后端-取证存档.md) §2）。
`<shim>.c:3-7` 把这件事概括成一句话并作为整个文件的存在理由：

> KHR 后缀名被门控、post-1.2 的 feature 位被清 0，而**无后缀的 core 名不受门控、且是真实现**。

三条裁剪行为都有单变量复现（取证存档 §2、§3）：

| 行为 | 观测 | 证据 |
|---|---|---|
| **KHR 后缀名门控** | `vkGetDeviceProcAddr(dev,"vkCmdPipelineBarrier2KHR")` 未 enable 时 NULL；把该扩展 enable 进 `vkCreateDevice` 后**变非 NULL** | 取证存档 §3.1 |
| **feature 位按上报版本截断** | `VkPhysicalDeviceVulkan13Features.dynamicRendering` 读到 0，同 ICD 的 core 命令实际可用 | 取证存档 §3.2 |
| **无后缀 core 名是真实现** | `vkCmdBeginRendering`/`vkCmdEndRendering`/`vkCmdPushDescriptorSet` 等不经 enable 即可解析，指针落在 ICD 的 `r-xp` 段（`/proc/self/maps` 归属） | 取证存档 §3.1 |

**推论（本工程一切判断的前提）**：不能用"字符串里有没有"判断实现（ICD 串含 125 个 `VK_*`，比实际多 30 个），
也不能用"KHR 名是否为 NULL"判断实现 —— **必须用归属判定 + 功能自证**。

### 1.2 MC 的硬门控 + 由此推出的两类修正

MC 26.2/26.3 在 `VulkanBackend.<clinit>` / `VulkanFeatureSets` 里**硬要求** 5 个扩展 + 9 个 feature，**无"可选/条件"语义**
（§4.1）；本机**缺 3 个扩展名 + 1 个 feature**（`dynamic_rendering` / `push_descriptor` / `vertex_attribute_divisor`
+ `vertexAttributeInstanceRateDivisor`）。`<shim>.c:6-7` 记的就是这条。

于是 shim 必须同时做两类事：

1. **修"广告面"**（门控层）——补扩展名、补 feature 位、`vkCreateDevice` 前从**副本**剔名、`KHR→core` 名字映射（§2.1）；
2. **翻译"实现缺陷"**——ICD 真正执行不了的少数调用（提交、时间线、push 描述符、WSI 朝向）在本机栈里的替代路径（§2.5–§2.7）。

### 1.3 LWJGL 侧（决定 shim 的**最小**形状）

1. **LWJGL 自身不做任何 device 扩展/feature 必需集校验**。`VK.create()` 只加载库 + 强校验 3 个 1.0 函数存在。
2. **能力布尔来自"应用 enable 了哪些名字"**，**不是**来自 `vkEnumerateDeviceExtensionProperties`
   （`VkDevice.getDeviceCapabilities` 用 `VK.getEnabledExtensionSet(apiVersion, ci.ppEnabledExtensionNames())`）。
   ⇒ **只做枚举钩子骗不到 LWJGL**；反过来，只要名字真被 enable 进 `ppEnabledExtensionNames`，LWJGL 就把能力布尔置真。
   ⇒ shim 必须**同时**做**枚举钩子**与 **createDevice 放行**，且**不能改调用方原结构体**（否则会把 LWJGL 派生出的能力布尔抹掉，`<shim>.c:15-17`）。
3. **函数指针另有一道闸**：`KHRDynamicRendering.vkCmdBeginRenderingKHR` / `KHRPushDescriptor.vkCmdPushDescriptorSetKHR`
   的指针**只由 `vkGetDeviceProcAddr` 填充**，返回 NULL 则布尔置假并 `reportMissing`
   ⇒ shim 的 `vkGetDeviceProcAddr` **必须给出非空实现** —— 这就是 `KHR→core` 映射必须存在的原因。
4. 未上报的扩展名 **LWJGL 不拦**，原样透传给驱动（`VkDeviceCreateInfo.validate` 只查指针非空）。
5. 可配置键只有两个：`org.lwjgl.vulkan.libname`、`org.lwjgl.vulkan.explicitInit`；**没有 caps/扩展覆盖键**，也没有静默降级开关。
6. `VK_EXT_vertex_attribute_divisor`（无函数）的能力布尔**纯由名字决定** ⇒ 它最"好骗"。

---

## 2. 逐级攻墙：症状 → 误判 → 真因 → 解法 → 为什么成立

### 2.1 门控层（四钩子）

**症状**：MC 直接抛 `VULKAN_MISSING_EXTENSION` / `VULKAN_MISSING_FEATURE`，拒绝建 Vulkan 后端（§4.1）。

**误判**：早期 `probe_mc_verdict.py` 因 **sType 常量写错**（`VkPhysicalDeviceFeatures2 = 1000059000` 被写成 `1000056000`）
把"必需 feature 缺失"报成假阴性，一度得出"BLOCKED 不可行"的结论（[`../../90-archive/Vulkan后端-跟进与结案.md`](../../90-archive/Vulkan后端-跟进与结案.md)、取证存档 §4）。

**真因**：§1.1 的上报面裁剪；且 ICD 字符串含 `dynamic_rendering` / `push_descriptor` / `vertex_attribute_divisor`
等 **30 个"知而不报"**的条目，说明是**能力档位裁剪而非硬件缺失**。

**解法**（`<shim>.c:117-123`、`:5257-5292`、`:5401-5429`、`:5432-5471`、`:5221-5246`）：

| 钩子 | 作用 | 代码 |
|---|---|---|
| ① 补枚举 | 在 `vkEnumerateDeviceExtensionProperties` 结果里追加被门控名（两段式 `pProps==NULL`/非 NULL 都处理） | `:5257-5292` |
| ② 补 feature 位 | 按 pNext 链的 sType 命中就置 `dynamicRendering=1`（Vulkan13 与 DynamicRendering 两个结构体）与 `vertexAttributeInstanceRateDivisor=1` | `:5401-5429` |
| ③ createDevice 剔名 | 拷贝一份 `VkDeviceCreateInfo`，去掉 ICD 拒收的名字后转发；**不动调用方原结构体** | `:5432-5471` |
| ④ KHR→core 映射 | `map_name()` 折叠 `…KHR` 到 ICD 暴露的 core 名（渲染、push、sync2、event/timestamp、queue-family properties 等） | `:5221-5246` |

**名单口径（回代码核实）**：`kGatedNames[]` 实为 **4 个**（`:117-123`）——MC 硬需的 3 个
（`VK_KHR_dynamic_rendering` / `VK_KHR_push_descriptor` / `VK_EXT_vertex_attribute_divisor`）**再加**
`VK_KHR_get_physical_device_properties2`。第 4 个不是 MC 的硬门控，而是为 LWJGL/VMA 解析 KHR 拼写而补（见 §2.4）。
`<shim>.c:13` 的概述仍写"the three gated names"，是指 MC 硬需的三个；完整名单以数组为准。

**为什么成立**：无后缀 core 名是真实现（§1.1），所以"补名 → 让 MC 通过校验 → createDevice 剔名 → 调用被映射到 core 名"
是一条**不改 MC、不造能力**的纯翻译链；且 dynamic_rendering / push_descriptor 有**像素/状态级自证**，
只有 divisor 是"谎"（§2.4、§4.4）。门控层被攻下后，MC 不再报 `Failed to create backend Vulkan`，也未回退 GL（取证存档 §3.5）。

### 2.2 `@0xc` 漂移崩溃：shim 自己包装函数的参数表错位

**症状**：`SIGSEGV(SEGV_MAPERR)@0x8 或 @0xc`，pc 落在**当时正在跑的 JIT'd Java**（`HashMap.computeIfAbsent`、
`datafixers…`、`StackMapGenerator$Frame.pushStack`…），**崩点会漂移**，只在 Vulkan 档出现，safepoint 堆校验干净。

**误判（两次）**：先判为"项目原本就有的 Java 侧空读"（读平台寄存器得到 `@0xc` + JDK classfile 栈帧）；
更早还判为"`vkCmdCopyBufferToImage` 这条命令会死在调用内部"。两者都被推翻。

**真因**：**shim 自己的** `vkCmdCopyBufferToImage` 包装**声明成 7 个参数**（多插了一个**不存在**的 `srcLayout`；
真 API 是 **6 个**）⇒ **每一位参数错位一个寄存器** ⇒ 驱动把 `pRegions` 当成"真正的 regionCount"（一个指针低半字），
把野指针当 ~30 亿个 `VkBufferImageCopy` 的数组读 ⇒ **延时的野内存踩踏**（`<shim>.c:793-806`）。

**当前代码事实（回代码核实）**：现在包装原型是 **6 参**
`typedef void (*PFN_cmdCopyBufferToImage)(void*, void*, void*, uint32_t, uint32_t, const void*);`
（`<shim>.c:809`），包装体 `:813-846`，转发用同一张实参表 `:840`。**这是全文件唯一的参数表错误**——
独立复核 `stuffs/research/vulkan/reviews/A5-wrapper-abi-audit.md`（24 wrapper + 19 PFN typedef 全对）。
物证 = 旧版曾打印荒谬的 `regions=3068047000`（那是指针低 32 位，不是个数）。

**解法**：原型改回真 6 参、转发用同一张实参表，tag 升 `shim build … .7`（`<shim>.c:807-809`）。

**为什么解释得了全部症状**：崩点在 JIT'd Java 里到处漂移、safepoint 干净、只在 Vulkan 档；关掉 shim 不崩其实是因为
MC 在 `findPhysicalDevice` 抛 `BackendCreationException`、Vulkan 后端根本没初始化。

> ✅ **已物理对齐（实机 A/B）**：取证存档 §3.6 的「不经 shim 的原生探针 `SIGSEGV`」不可复现 —— 原始 ICD 指针与 shim 包装在同一最小 copy 用例下均 `rc=0`，坐实本条结论（见 §5 结案条目）。

### 2.3 `memset(NULL, 0, 0x8000)`：musl 对 `alignment < 8` 返 EINVAL

**症状**：native `SIGSEGV(SEGV_MAPERR)@0x0`，`pc` 落在 **musl `memset`**，寄存器 `x0=x1=0`、`x2=0x8000`；
`-Xint`（无 JIT）仍崩、形态回到这一处 ⇒ **证明它是 native 崩溃，不是 Java 层 NPE**。

**真因**：LWJGL core 的 `__aligned_alloc` 在 OHOS 上退化为 `posix_memalign`；**musl 对 `alignment < sizeof(void*)`
返回 `EINVAL`**；VMA 以 `VMA_ALIGN_OF(RegionInfo)=2` 调用它、为 32 MiB 块的页表（`8192*4 = 0x8000`）分配 ⇒ 返回 NULL
⇒ `memset(NULL, 0, 0x8000)`（与 `x2=0x8000` 逐位吻合）。根因链见 `stuffs/research/vulkan/fixes/F2-lwjgl-aligned-alloc-musl.md`。

**解法**：把对齐 clamp 到 `>= sizeof(void*)`（**只抬下界、语义不变**），在**工作区内的源码副本**上重编 LWJGL core；
**食谱** = 主仓 `tools/lwjgl/build_lwjgl_core_aligned_alloc_fix.sh`（头注释 `:2-27` 写明根因、musl 反汇编、生成器模板也一并改）。

**为什么成立**：这是**只放宽下界的等价修补**；修后 shim 轨迹跨过原来的首块 `vkBindBufferMemory`。

### 2.4 VMA 函数表里的 KHR 格为 NULL

**症状**：开断言时 VMA `Assertion failed: … != nullptr`（`vk_mem_alloc.h:13825`）⇒ abort；`-DNDEBUG` 随包时**直呼 NULL**
⇒ 低地址野读（与 §2.3 表象相同）。

**真因**：**LWJGL 关掉了 VMA 的两条自导入路径**（预处理器实测 `VMA_STATIC_VULKAN_FUNCTIONS` 与
`VMA_DYNAMIC_VULKAN_FUNCTIONS` 皆为 0）⇒ 整张 `VmaVulkanFunctions` 必须由 Java 填满；而本机 ICD 是 **1.2-core**，
**LWJGL 合法地不解析 KHR 拼写** ⇒ `vkGetPhysicalDeviceProperties2KHR` / `…MemoryProperties2KHR` 为 **NULL**。

**解法**：**补广告** `VK_KHR_get_physical_device_properties2`（`kGatedNames` 第 4 个，`<shim>.c:109-122`），
让 LWJGL 解析 KHR 名；再用 `KHR→core` 映射落到 ICD 的 core 实现（`<shim>.c:5561-5565`）。

**"随包"与"诊断"的区别（回代码核实）**：

- **随包是纯净版**：`tools/lwjgl/build_lwjgl_vma.sh` 的 `MODE=release`（默认）**不 patch 源码**，
  是上游原样构建；随包文件 sha256 `479a619f99d0f740…`（脚本 `:6-8`）。VMA 只需应用提供的 Vulkan 函数指针，
  补上第 4 个扩展名后 KHR 格不再为 NULL ⇒ **运行时不需要 patch**。
- **patch 版仅诊断**：收窄断言 + 打印 NULL 清单 + `memset` 监视，配方在 `stuffs/research/vulkan/build_vma_patched.sh`；
  脚本 `:11-16` 明写 **NEVER ship**，随包件不含 `[vma]` 诊断串。

### 2.5 提交侧的两道墙：F66 合并提交 + F69 时间线→真实 fence

**⑤a 症状**：一次提交里放多条 `VkSubmitInfo2` entry 时，**第二条**就死（`rcSeq=0,-1`，驱动报
"Command buffer has error and cannot be executed"）；拆成 N 次调用也失败（只是把"第二次 entry"换成"第二次 call"）。

**真因**：**本机 ICD 每次提交只接受 1 条 entry**。

**解法 = F66 合并**：把一帧的多条 entry（各自的 wait / command buffer / signal）**按原顺序合并进一条 v1 `VkSubmitInfo`**，
并链一条 `VkTimelineSemaphoreSubmitInfo`（`<shim>.c:1454-1468`）。合并后的 wait 集合是各 entry 的**超集**（更保守）、
单队列内提交顺序保持 ⇒ 是**忠实翻译**（`:1463-1468`）。`MEOW_VK_SYNC2_TO_V1_MERGE=0` 回到 N 次拆分作 A/B。
另：**两个 sync2 入口同时用会在首次提交即死**（v1 barrier+submit2 OK，sync2 barrier+submit2 FAIL），
故 `vkQueueSubmit2`/`vkCmdPipelineBarrier2` 统一翻译为 v1（`<shim>.c:1198-1213`）。

**⑤b 症状**：合并提交被接受（`rc=0`）后，MC 等自己的时间线信号量仍吃 `-4`（DEVICE_LOST）/ `rc=2`（TIMEOUT）。

**真因**：**ICD 从不从 GPU 侧推进时间线计数**（物证 `stuffs/research/vulkan/fixes/F50-host-timeline-signal.md:18`）。

**解法 = F69 翻译，不是伪造**：在合并后的提交上 ①把**时间线 signal** 从 `pSignalSemaphores` 剔除（二值信号量保留）；
②创建真实 `VkFence` 挂到该次 `vkQueueSubmit`；③`rc=0` 后登记 `(时间线信号量, 值N) -> fence`；
④`vkWaitSemaphores` / `vkGetSemaphoreCounterValue` 从该 fence 回答；⑤提交内的时间线 wait 先主机 `vkWaitForFences` 再剔除
（`<shim>.c:1486-1508`、decide `:1520-1532`、有界表 64×64）。

**为什么不能伪造**：F50 的**主机侧 `vkSignalSemaphore`** 已被证死 —— 主机提前推进让 **MC 以为 GPU 已完成而重置命令池**，
CPU/GPU 竞争 ⇒ **present 信号量永不完成**（~940 ms acquire，`<shim>.c:1489-1503`；物证 `stuffs/research/vulkan/fixes/F50-host-timeline-signal.md`）。
**真实 fence 只在 GPU 真正完成时才 signal**，所以它是"顺序正确、不被主机偷跑"的唯一解。

### 2.6 描述符侧：F72 / F72b / F72c —— "材质/贴图显示不出来"的真解

**症状**：门控攻下后画面出现但**材质/贴图显示不出来**；把 push 描述符消费进真实管线会**器件丢失**。

**真因（实机 A/B 收窄）**：`vkCmdPushDescriptorSet` 记录/提交都不报错，**在"简单用法"下原始 push 可用** —— 最小 A/B 顶点着色器真读 `set0/binding0` 的 UBO 并经 `gl_Position` 消费、真 `vkCmdDraw(3)`，A/B 两臂均 `rc=0`；但**在 MC 的真实用法下不可用** —— 关掉模拟（`MEOW_VK_PUSH_AS_SET=0`）跑 MC 实测：首帧提交 `rc=0` 被接受，随后 `vkWaitSemaphores→vkWaitForFences` 返回 `-4`（器件丢失）、MC 抛 `GpuDeviceLoss`；
而**普通描述符集全链可用**（pool → set → `vkUpdateDescriptorSets` → `vkCmdBindDescriptorSets` → 消费，
storage image 写入落地）。**MC 唯一的描述符写入路径恰是 push**（§4.3 全 jar 无 `vkCmdBindDescriptorSets`）。

**解法 = F72 用普通描述符集模拟**（`<shim>.c:1717-1740`）：
`vkCreatePipelineLayout` 被捕获使 `(layout,set)→setLayout` 可知（`:1791-1838`）；一次 push 变成
`vkAllocateDescriptorSets(pool)` + 把 writes 的 `dstSet` 改写 + `vkUpdateDescriptorSets` + `vkCmdBindDescriptorSets`。
任何失败（layout 未捕获 / 无空闲池 / 分配失败 / 无法解析真函数）都**降级为转发原 push 并限流告警**——不猜测、不静默丢弃（`:1738-1739`）。

**F72b 镜像 set layout（必须）**：MC 的 set layout 带 `PUSH_DESCRIPTOR_BIT_KHR`，而**按规范这种 layout 不能用于
`vkAllocateDescriptorSets`** ⇒ shim 另建"**绑定完全相同、去掉 push 位**"的镜像 layout 来分配，并用**原 pipeline layout**绑定
（push 位不参与 set-layout 兼容性判定）（`<shim>.c:1840-1928`，镜像创建 `:1914-1920`）。

**F72c 池健壮化**（`<shim>.c:2060-2102`）：顺序是 ①**回收**已 signal 的 pending 池（reset 后可复用）→
②挑一个本帧未用的空闲池 → ③都不行就**按需增开一个池**（硬上限 `MEOW_F72_NPOOLS=64`）→ 只有增开失败才转发原 push。
池复位前必须等其上次提交的 fence 真的 signal（`:2041-2050`），**没有 fence 的 pending 池刻意不复用**（无法证明 GPU 已完成）。

**默认值（回代码核实）**：`MEOW_VK_PUSH_AS_SET` 跟随 hooks ⇒ **被加载即默认开**（`<shim>.c:1747-1759`）。
真机自证行 `F72b push totals: emulated=1688000 forwarded=0 pools=26 grow=26 resets=8180`。

> **F72 必需性（实机复核，保留）**：原始 push **在简单用法下可用、在 MC 真实用法下不可用**（关掉 `MEOW_VK_PUSH_AS_SET` 跑真实业务 ⇒ 首帧 `rc=0` 被接受、随后等待 `-4` 器件丢失、`GpuDeviceLoss`）⇒ **F72 模拟是必需的**。
> **覆盖边界**：最小 A/B 未覆盖 MC 的多样性（每帧大量 push / 多 set / 组合图像采样器 / push 之后仍有主机侧写入）；**若将来要收窄成因，就须逐项变化这些维度**（非当前优先）。

> **两条独立修复，勿混为一谈**（[`已知限制与待解.md`](../../00-current/已知限制与待解.md) §F）：
> **① 材质/描述符**：`vkCmdPushDescriptorSet` 被 MC 真实用法消费会丢器件，由 **F72/F72c** 解决；**F72 经实机复核为必需**。
> **② 图像上传**（image transfer）本役走**原始 `vkCmdCopyBufferToImage` 直转发**，**F53 重定向默认关**
> （`<shim>.c:239-255`，F61 起与 hooks 无关；其"必崩"再改判为 §2.2 的包装参数表错位）；**实机 A/B 结案**：走 shim 与直调 ICD 原始指针（日志自证 `shim!=real`）均 `rc=0` ⇒ **ICD 无罪、F53 不需**；覆盖边界 = 最小基础路径（单 region / LINEAR / 小图），**未**覆盖多 region / OPTIMAL / 大上传。

### 2.7 WSI 朝向：F73/F74 默认强制 `preTransform=IDENTITY`

**症状**：F72 后画面出现，但**逆时针转 90° 且拉伸**（"躺着、瘦长"）。

**真因**：本机 surface 报 `currentTransform = 0x2`（`ROTATE_90_BIT_KHR`，`supportedTransforms=0x1ff`），
且 **WSI 真的照做旋转**；MC 请求 `imageExtent=640x332` + `preTransform=0x2` ⇒ 横向内容被转 90° 后再塞回原比例。
证据：`<shim>.c:4794-4802`、`stuffs/research/vulkan/fixes/F73-pretransform-identity-m1.md` §0。

**解法**：`meow_swapchain_mut()` 里把 `preTransform` 覆写为 `IDENTITY(0x1)`，且 **F74 起为默认开**
（未设/空/`identity` ⇒ 强制；`=requested`/`0` 保留调用方原值作 A/B 逃生）（`<shim>.c:4755-4815`、`:4762-4777`）。
`MEOW_VK_FIX_EXTENT=current` 仍是 opt-in。收据行带 `source=default/identity/requested`，避免"沉默"歧义。

**为什么成立**：`supportedTransforms` 含 IDENTITY，WSI 不再旋转；F73 文档记录了"覆写之所以必须无条件可达"的实现教训
（`.51` 版把覆写藏在只在其它开关触发时才调用的分支里 ⇒ 静默不生效）。

---

## 3. 机制总表（口径 = 按默认值一刀切）

**规则**：**A 级 = 功能必需 / 默认开**（用户不设置也生效）· **B 级 = 诊断 / 默认关**（只在排障时手动打开）。
权威清单 = `<shim>.c:31-58` 头注释；notes 投影见 [`运行时环境变量.md`](../../00-current/运行时环境变量.md) §1。两处已逐条核对一致。

### 3.1 A 级：功能必需 / 默认开

| 开关 | 默认 | 机制 / 为什么必需 | 代码 |
|---|---|---|---|
| `MEOW_VK_SHIM=0`（逃生） | 被加载即挂钩（`g_hooks=1`） | 选 Vulkan 由**库名** `-Dorg.lwjgl.vulkan.libname=libmeowvulkan.so` 承载；`=0`/空 = 纯透传逃生 | `<shim>.c:5176-5179` |
| **F66 合并提交**（无 env） | 编译期默认开 | 本机 ICD 只接受 1 条 entry | `<shim>.c:1454-1468` |
| `MEOW_VK_SYNC2_TO_V1` | 跟随 hooks（开） | 两个 sync2 入口同用会首提交即死 | `<shim>.c:1261-1275` |
| `MEOW_VK_SYNC2_TO_V1_MERGE` | 跟随 hooks（开） | F66 的单 entry 约束 | `<shim>.c:1470-1483` |
| `MEOW_VK_WAIT_VIA_QUEUE_IDLE` | 开 | `vkWaitSemaphores` 恒超时；用真实 `vkQueueWaitIdle` 满足等待 | `<shim>.c:1293-1305` |
| `MEOW_VK_TIMELINE_AS_FENCE` | 跟随 hooks（开） | 时间线计数不从 GPU 推进，翻成真 `VkFence`（F69） | `<shim>.c:1520-1532` |
| `MEOW_VK_PUSH_AS_SET` | 跟随 hooks（开） | push 是 MC 唯一描述符路径，须模拟成普通 set（F72） | `<shim>.c:1747-1759` |
| `MEOW_VK_FIX_SURFACE_TRANSFORM` | identity（默认） | WSI 真旋转 90°（F73/F74） | `<shim>.c:4762-4777` |
| `MEOW_VK_STRIP_UNSUPPORTED_FEATURES` | 跟随 hooks（开） | createDevice 前从副本剔掉 ICD 不支持的 feature 位（F36） | `<shim>.c:5327-5333` |

### 3.2 B 级：诊断 / 默认关

| 开关 | 默认 | 用途 | 代码 |
|---|---|---|---|
| `MEOW_VK_VERBOSE` | 关 | 放开逐次调用 / 细节日志（高音量、扰时序） | `<shim>.c:5483-5490` |
| `MEOW_VK_WD` | 关 | 卡死看门狗：无 Vulkan 活动超时 ⇒ `SIGQUIT` 线程转储 | `<shim>.c`（F60/M1） |
| `MEOW_VK_FIX_EXTENT=current` | 关 | 强制 `imageExtent=caps.currentExtent`（本机当前等价） | `<shim>.c:4816-4828` |
| `MEOW_VK_FIX_COPY_BUFFER_TO_IMAGE=1` | 关（F61，与 hooks 无关） | F53 把上传重写为 GPU 别名路线，留作 A/B | `<shim>.c:239-255` |
| `MEOW_VK_NO_DIVISOR_FEATURE` | 关 | **别用**：不谎报 divisor ⇒ MC 直接拒绝建后端 | `<shim>.c:5301-5308` |
| `MEOW_VK_DROP_DRAW` / `MEOW_VK_DROP_PUSH_DESCRIPTOR` | 关 | 二分定位用：丢弃全部 draw / push | `<shim>.c:873`、`:891` |

**已被删除的档**：16 个 `MEOW_VK_PROBE_*` + `meowvkprobe.c` + UI 宿主（F79）；`MEOW_VK_SHIM` 的三个旧总开关语义、
`MEOW_VK_KEEP_SYNC2` 等（F75）。**注意**：`meow_resolve_device_fn` / `MEOW_FORWARD_3OUT` 是从探针改名而来的**通用解析/转发机制**，
与已删探针无关、勿删（`<shim>.c:2893` NAMING NOTE）。

> **高频探针默认静默（tag `2026-09-23.83 quiet-f72b-totals`）**：`F71 divisor summary` / `F72 pipelineLayout captured` / `F72b push totals`
> 三类**高频探针默认关闭**（此前默认逐条打印 / 池平台期也打；一场正常游玩约 2600 行日志 ⇒ **默认关闭后降到个位数**）。
> **临时开启**（二选一）：`MEOW_VK_VERBOSE=1`（逐条，见上表）或 `MEOW_VK_TOTALS_SEC=<秒>`（聚合行**低速率心跳**）。
> 落点 `主仓 libs/meowcraftlib/src/main/cpp/meowcraftbridge/meowvulkan.c`；投影见 [`运行时环境变量.md`](../../00-current/运行时环境变量.md) §1。

### 3.3 与旧文档 / 代码注释的两处口径（以代码为准）

1. **"补 3 个扩展名"**：`kGatedNames[]` 实为 **4 个**（`<shim>.c:117-123`）——MC 硬需 3 个 + `VK_KHR_get_physical_device_properties2`（为 VMA/LWJGL 补，§2.4）。
2. **F74 报告称"启动器自动注入 `MEOW_VK_SHIM=1`"已被 F75 取代**：当前 `GameLauncher.ets` **不再注入**该 env
   （`GameLauncher.ets:115-116`、`:213-214`），改由 `MinecraftLauncher.ets:265-267` 按**库名**选 shim / 占位库 ⇒ **零必配 env**。

---

## 4. MC 侧需求（决定 shim 形状，且说明为什么没有退路）

> 方法：python 解析 `26.2.jar` / `26.3-rc-3.jar` 的常量池 + 自写字节码解码器（本机 `javap` 起不来：
> `Failed to mark memory page as executable`）。类落点：`com.mojang.blaze3d.vulkan.*`（26.2）、
> `com.mojang.renderpearl.backend.vulkan.*`（26.3）。取值方法（strings 解构）见 [`Vulkan后端-取证存档.md`](Vulkan后端-取证存档.md) §1。

### 4.1 硬门控在哪

- **26.2**：集中在 `VulkanBackend.<clinit>`
  - `REQUIRED_DEVICE_EXTENSIONS` = { `VK_KHR_dynamic_rendering`, `VK_KHR_push_descriptor`,
    `VK_KHR_synchronization2`, `VK_EXT_vertex_attribute_divisor`, `VK_KHR_swapchain` }
  - `REQUIRED_DEVICE_FEATURES` = { multiDrawIndirect, fillModeNonSolid, samplerAnisotropy, shaderDrawParameters,
    timelineSemaphore, hostQueryReset, synchronization2, dynamicRendering, vertexAttributeInstanceRateDivisor }
  - 判定 = `VulkanPhysicalDevice.getMissingExtensions(required)`（**只是字符串集合差集**）+ 逐 feature 查 →
    `BackendCreationException(VULKAN_MISSING_EXTENSION / VULKAN_MISSING_FEATURE)`。**无"可选/条件"语义**。
- **26.3**：集中在 `VulkanFeatureSets`
  - `requiredFeatureSets()` = `REQUIRED_FEATURESET`（名 `"Minecraft base required"`），ext/feature 同上，
    但 **`fillModeNonSolid` 降为可选（Wireframe）**、**新增 `drawIndirectFirstInstance`**。
  - `requiredIfExtensionsAvailableFeatureSets()` = 仅 `VK_KHR_portability_subset`(+`triangleFans`)；
    `optionalFeatureSets()` = calibrated_timestamps / NV/AMD checkpoint / multi_draw（**都不挡启动**）。
- 其它门槛：`VK_API_VERSION_1_2`、graphics queue。

### 4.2 是"真用"不是"只列清单"（逐个有调用点）

| 扩展 | 调用点 |
|---|---|
| `dynamic_rendering` | `VulkanCommandEncoder` → `KHRDynamicRendering.vkCmdBeginRenderingKHR/EndRenderingKHR`；`VulkanRenderPipeline#compile` 挂 `VkPipelineRenderingCreateInfoKHR` |
| `push_descriptor` | `VulkanRenderPass#pushDescriptors` → `KHRPushDescriptor.vkCmdPushDescriptorSetKHR` |
| `vertex_attribute_divisor` | `VulkanRenderPipeline#compile`：`VkVertexInputBindingDivisorDescriptionEXT` → `VkPipelineVertexInputDivisorStateCreateInfoEXT` → 挂 `vertexInputState.pNext` |
| `synchronization2` | `VulkanCommandEncoder` → `vkCmdPipelineBarrier2KHR`/`vkCmdWriteTimestamp2KHR`；`VulkanQueue$Submission` 用 `VkSubmitInfo2` |
| `swapchain` | `VulkanGpuSurface` → `vkCreateSwapchainKHR`/`AcquireNextImageKHR`/`QueuePresentKHR` |

### 4.3 无退路（决定 shim 必须覆盖这些面）

- 全 jar **没有** `vkCmdBeginRenderPass` / `vkCreateRenderPass` / `VkRenderPassCreateInfo` / `VkFramebufferCreateInfo` /
  `VkRenderPassBeginInfo` / `vkCreateFramebuffer` ⇒ **纯 dynamic rendering，没有经典 render pass 备选**。
- **push_descriptor 是唯一的描述符写入路径**：全 jar 无 `vkCmdBindDescriptorSets` / `vkUpdateDescriptorSets` /
  `vkAllocateDescriptorSets` / `vkCreateDescriptorPool`（只建 `vkCreateDescriptorSetLayout`）。
  ⇒ "关掉 push"等于重写整个描述符上传，**不是清单问题** ⇒ 这是 **F72 存在的理由**。

### 4.4 divisor 的 vanilla 用法（**确证**：伪造安全）

- 26.2：`VertexFormat.builder(I)` 的调用者**只有** `DefaultVertexFormat.<clinit>`，14 处**全部 `iconst_0`**
  ⇒ 所有格式 stepRate=0 ⇒ `vertexBindingDivisorCount()` 恒 0 ⇒ **从不挂 divisor state**。
- 26.3：16 处里 **15×0 + 1×1**；那 1 个 = `CHUNK_DATA_INSTANCED`（terrain-multidraw 系列用），
  **stepRate 恰好 = 1**，且这些 pipeline 是 required、reload 必编译。
- **divisor=1 正是"扩展未启用"时的隐式默认值** ⇒ 即使驱动完全忽略那个 pNext，**顶点步进结果一致**。
- MC **从不查询** `maxVertexAttribDivisor`/divisor properties（全 jar 无引用）。
⇒ **结论**：伪造 `vertexAttributeInstanceRateDivisor=true` 对 **vanilla 安全**（判据强度：穷举调用点，确证）；
**mod 若用 divisor>1 会超出本机上限 1**。

### 4.5 MC 有内建后端回退（"失败代价低"的机制依据）

`PreferredGraphicsApi{DEFAULT,OPENGL,VULKAN}`；`getBackendsToTry()` 返回候选列表：
```
VULKAN          → { VulkanBackend, GlBackend }
DEFAULT|OPENGL  → { GlBackend, VulkanBackend }
```
`Minecraft.<init>` 的循环 `try { … } catch (BackendCreationException e) { LOGGER.error("Failed to create backend {}", …); 记录; 继续下一个 }`，
**两个都失败才 `Window$WindowInitFailed`**。⇒ 开启 Vulkan 后即使初始化失败，**只是日志报错 + 回退 OpenGL**。
（另有：上次异常退出时若偏好为 VULKAN → 重置 DEFAULT；DEFAULT 崩过 → 强制 OPENGL。CLI `--graphicsBackend` 可强制。）

---

## 5. 边界与未解（只给指针 + 一句本质）

**已知边界**

- **压缩纹理**：`vkCmdCopyBufferToImage` 系的 LINEAR 中转对压缩格式（BC*/ETC2/EAC/ASTC，11 个）非法、且这些格式全无 STORAGE
  ⇒ 两条补实现路线都覆盖不到（vanilla 以未压缩 RGBA8/SRGB 为主）。取证存档 §3.7。
- **divisor 谎言的边界**：vanilla 安全、mod 用 divisor>1 会超出本机上限 1（§4.4）。
- **F72 覆盖边界**：最小 A/B 未覆盖 MC 真实用法维度（§2.6）。

**未解 / 未验项**

1. **divisor 特性为何是硬门控**：MC **必须**有 `VK_EXT_vertex_attribute_divisor` 特性才肯建后端，但实测**从不使用 divisor 状态**
   ⇒ 为什么它要这个特性（未解）。证据：`stuffs/research/vulkan/fixes/F71-divisor-refuted.md`（`withDivisorState=0`）、§4.4。
2. **本机 ICD 为什么报 1.2 / 清位**：是"1.4 实现被主动按 1.2 档位裁剪广告面"，还是另有原因（未解）。见取证存档 §2。
3. **GL 档偶发闪**：沿用观察，F78 已摘除 GL 路径上的窗口 usage 写操作但用户仍见偶发闪；线索"Sodium 下无"不能作因果断言。指针：[`已知限制与待解.md`](../../00-current/已知限制与待解.md) §H1。
4. **Vulkan 世界 ≈22 FPS vs GL 60–70**：存在真实差距，已排除项与候选见 [`已知限制与待解.md`](../../00-current/已知限制与待解.md) §H2/§D。
5. **MC 26.3 上的 Vulkan 档**：缺口在 SDL `ohos` 视频驱动未提供 Vulkan vtable（已补 5 hook）；机制见 [`SDL3适配-复盘.md`](SDL3适配-复盘.md) §七，状态见 [`现状基线.md`](../../00-current/现状基线.md) §5 第 24 条。

> ✅ **已结案（原「原生探针不可复现」）**：本机 ICD 的**原始 `vkCmdCopyBufferToImage` 可用** ⇒ 历史「绕过 shim 亦崩」在本测例下**不可复现** ⇒ ICD 缺陷判定**不成立**，那批 `@0xc` 漂移 / 图像传输族崩溃确系 shim 的 **7 参 vs 6 参包装错位**（`.7` 已修）⇒ 贴图路径**不需要 F53 重定向兜底**（§2.2）。
> **判据（实机 A/B，游戏进程内）**：`SELFTEST begin real=0x6c21600a90 shim=0x5ceac11fe4 shim!=real=1`；`A(shim) rc=0`；`B(raw) rc=0`（直调 `gdpa` 原始指针，日志明写 NOT in the call path）；`result=A_OK_B_OK`。
> **边界**：最小用例（64 B buffer → 4×4 **LINEAR** 图 → **1 region** → **单 entry** 提交 → `vkQueueWaitIdle`），且运行于游戏进程（= MC 真实环境）⇒ 只证**基础路径健康**；**未**覆盖 MC 真实规模（多 region / OPTIMAL / 大上传）。

---

## 6. 方法学（可复用）

1. **同形单变量纪律**：怀疑"与 Vulkan 路径绑定"时，只改渲染后端做 GL/auto 对照，其余变量全不动。
2. **丢弃式测试是单侧证据**：把嫌疑调用丢掉不等于排除它 —— F68 丢掉 push 后 draw 在**无描述符**下执行，换来另一种错，不能给 push 免罪（`<shim>.c:1720-1723`）。
3. **hilog 行号 ≠ 因果**（多进程交织）：由日志先后推断"崩在贴图上传"被寄存器复核直接推翻。
4. **不能用"日志里没有"推断"没发生"**：采集侧会截断/挤掉；未收到只能记"未观测到"。见 [`原生崩溃排查-方法论与复盘.md`](../../10-research/原生崩溃排查-方法论与复盘.md) §9。
5. **hot 路径日志必须限流**：F71 前后同一批事件从 30,145 行降到 14 行；`<shim>.c:1762-1780` 是标准限流写法（前 4 条具名 + 每 4000 一条累计）。
6. **对齐对象 = 调用方头文件 + 真机实测，不是文档头**：参数表以 `ref/lwjgl3/.../vulkan_core.h:4587`（调用方生成头）为准；
   "驱动缺陷"级结论必须原生 C 复验 —— ctypes 临时对象 `addressof()` 曾造成两条假阳性，一度把整条 Vulkan 线判死。
7. **最小 A/B 会过度泛化，不能代证"能否退役绕行"**：凡"能否退役某绕行"的结论，必须由"关掉它跑真实业务"来定；用最小测例下结论**必须同时写明覆盖范围与未覆盖的真实用法维度**。
8. **判定"ICD 缺陷 vs 我们的 bug"的常规手段**：在游戏进程内、同形两臂（经我们的包装 vs 直调 ICD 原始指针）、**自证指针**（打印 `shim!=real`），在最小用例下比返回码。

---

**相关**：[`Vulkan后端-取证存档.md`](Vulkan后端-取证存档.md)（取证方法 / 设备事实 / 逐项读数）、
[`../../90-archive/Vulkan后端-跟进与结案.md`](../../90-archive/Vulkan后端-跟进与结案.md)（上一版，BLOCKED 结论已归档）、
[`MC26.x渲染栈-差异分析.md`](MC26.x渲染栈-差异分析.md)（26.x 为何重写渲染栈 / Vulkan 后端的由来）、
[`../lwjgl/LWJGL3世代管理-方案.md`](../lwjgl/LWJGL3世代管理-方案.md)（随包 native 自编与世代管理）、
[`渲染链-结论.md`](渲染链-结论.md) §2.2（两条渲染链的活架构）、
[`../../00-current/运行时环境变量.md`](../../00-current/运行时环境变量.md)（env 开关总表）。
