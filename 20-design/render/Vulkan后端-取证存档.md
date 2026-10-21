# Vulkan 后端取证存档（设备事实 · 方法 · 读数）

> **性质**：本文是 Vulkan 后端的**可复现取证方法与设备事实**，以及逐项读数 / 自证 / 过程记录。
> **机制 / 原理**的权威表述见 [`Vulkan后端-实现与原理.md`](Vulkan后端-实现与原理.md)（本文不重复"为什么这么设计"）；
> **现役可用性 / 未决项**见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 24 条与 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §H。
> **本文取代**旧结案档（判 BLOCKED、结论被推翻，归档于 [`../../90-archive/Vulkan后端-跟进与结案.md`](../../90-archive/Vulkan后端-跟进与结案.md)）与旧"绕过可行性"档（其机制面已并入 [`Vulkan后端-实现与原理.md`](Vulkan后端-实现与原理.md)）。
> **原始证据 / 逐项修复**在**工作区根** `stuffs/research/vulkan/`：`probe_*.py`（探针）、`fixes/F1…F79`（逐项修复）、`reviews/A1…A25`（独立复核）、`vk-m1-evidence/`、`vk-faultlog-archive/`。
> **本机** = 鸿蒙 PC（Maleoon 916 / OpenHarmony 7.0.0.105，同一台 2in1，开发机 = 运行机）；「工作区根」 = 含 `notes/`、`stuffs/`、`ref/` 的目录。

---

## 1. 取证方法（可复现）

**前提**：设备端有 `python3`（`/data/service/hnp/bin/python3`），脚本**直接在设备上跑**，用 `ctypes` `dlopen` 系统 loader 实测。

| 脚本（工作区根 `stuffs/research/vulkan/` 下）| 作用 |
|---|---|
| `probe_vulkan.py` / `probe_apiver.py` | 枚举全表 / apiVersion 门控测试（结论：无差异）|
| `probe_mc_verdict.py` | "复检入口"——⚠️ **其 sType 常量是错的，会假报 feature MISS**，修法见 §4 第 1 条 |
| `probe_bypass.py` | 第 1 轮：Q1 入口点 / Q2 带对照的 feature / Q3 createDevice 拒收 / Q4 loader env 注入面 |
| `probe_bypass2.py` | 第 2 轮：**指针归属判定**（`/proc/self/maps`）+ 修正对照 + `enable` 前后对比 + `createInstance(1.3)` 对照 |
| `probe_bypass3.py` | 第 3 轮：push-descriptor **layout 标志位**是否被接受 + divisor 属性（EXT 与 1.4-core 两版）+ **功能自证 D**（push→submit）|
| `probe_bypass4.py` / `probe_bypass5.py` | 第 4/5 轮：**barrier / layout 排查**（结论：不是 barrier 的问题）+ **功能自证 C**（真实附件渲染读回）|
| `probe_bypass6.py` | 第 6 轮：`vkCmdFillBuffer` —— 证明**命令执行链路本身没问题** |
| `probe_bypass7.py` | 第 7 轮：图像配置扫描（LINEAR vs OPTIMAL × usage × 内存类型）⇒ 定位"OPTIMAL 不能线性判读" |
| `probe_bypass8.py` | 第 8 轮：**LINEAR 图像**验证 clear 与**真实附件渲染**（PART1/PART2 PASS）+ 拷贝隔离 |
| `probe_bypass9.py` | 第 9 轮：两个拷贝方向（D1 正确尺寸缓冲仍不生效；D2 崩在脚手架）|
| `probe_u2bisect.py` / `probe_u2_workaround.py` / `probe_u2_hunt.py` | 镜像传输族逐个变体切开（每变体独立子进程）|
| `probe_u2_alternative.py` / `probe_u2_alt_localise.py` / `probe_spv_version.py` | compute / SPIR-V 备选路线（含 `OpEntryPoint` 字面串的坑，§4）|
| `probe_cpu_upload.py` / `probe_linear_chain.py` / `probe_sample_linear.py` / `probe_desc_path.py` / `probe_dispatch_triage.py` | CPU 上传 / LINEAR 链 / 采样 / 描述符普查（原生 C 复核用的能力表）|
| `probe_tiling_routes.py` | 能力面查询（哪些格式可 LINEAR / 可 storage，§3 硬边界）|
| `probe_wsi_surface.py` / `meowvkwsi.c` / `meowvktiling.c` | WSI / 分块传输的原生 C 仪器 |
| 主仓 `libs/meowcraftlib/src/main/cpp/meowcraftbridge/meowvkprobe.c`（**已删**）| 应用内自检探针（§6），产编译产物物证 |

**复现命令（任意一轮）**：`python3 stuffs/research/vulkan/probe_bypass8.py`（在设备上直接跑）。
> `stuffs/` 在**工作区根**（`<workspace>/stuffs/...`），不在主仓内。

**MC 需求解构（strings 法）**：沙箱 JVM 起不来（`Failed to mark memory page as executable`，`javap` 同样），
故用 `strings` 抽 `com/mojang/blaze3d/vulkan/*`（26.2）、`com/mojang/renderpearl/backend/vulkan/*`（26.3）
的常量池，读必需扩展 / feature 名与调用点。结果（必需集、无退路、divisor 用法）见 [`Vulkan后端-实现与原理.md`](Vulkan后端-实现与原理.md) §4。

---

## 2. 设备侧事实（loader / ICD / device）

- **loader**：`/system/lib64/libvulkan.so`，`vkEnumerateInstanceVersion` = **1.3.275**；无 `libvulkan.so.1`。
- **ICD（唯一）**：`/vendor/lib64/passthrough/vulkan.hvgr_v210.so`（+ 核心 `libhvgr_v210.so`、编译器 `libbishenggpucompiler_v210.so.15`），经 `/proc/self/maps` 确证。
- **物理设备**：`Maleoon 916`，**apiVersion 1.2.309**，INTEGRATED_GPU，**device 扩展 69 个**。
- **instance 扩展 13 个**，含 `VK_KHR_surface`、**`VK_OHOS_surface`**、`VK_KHR_portability_enumeration`、`VK_EXT_debug_utils`、`VK_LUNARG_direct_driver_loading`。
- **Implicit layers（均不注入缺失扩展）**：`VK_LAYER_HUAWEI_iGraphics`、`VK_LAYER_HUAWEI_GameAware`、`VK_LAYER_TRACE3D_Loader`、`VK_LAYER_OHOS_surface`（`libvulkan_swapchain.so`）。
- **驱动「知而不报」**：ICD 字符串含 125 个 `VK_*`，比实际上报多 30 个，含
  `VK_KHR_dynamic_rendering`、`VK_KHR_push_descriptor`、`VK_EXT_vertex_attribute_divisor`、
  `VK_KHR_maintenance4/5/6`、`VK_EXT_descriptor_buffer`、`VK_EXT_extended_dynamic_state(2)` 等
  → 典型「Vulkan 1.2 能力档位」裁剪（**非硬件缺失**）。
- **内存**：type0 `flags=0x7` DEVICE_LOCAL|HOST_VISIBLE|HOST_COHERENT（UMA ⇒ 显存可直接 map 判读）。
- **swapchain 提供者**：`/system/lib64/libvulkan_swapchain.so`（implicit layer `VK_LAYER_OHOS_surface`）；未 enable `VK_KHR_swapchain` 时 `vkCreateSwapchainKHR` = NULL。

### 2.1 应用内探针实测（确认 app 上下文 = shell）

在启动器首页加「Vulkan 能力探测」按钮（native `probeVulkan()`，`entry` 模块，dlopen libvulkan.so）——
**临时探针，取证完成后已回退、不保留**。应用进程内实测**与 shell 完全一致**：
```
loader: libvulkan.so loaded ; apiVersion: 1.3.275
instance ext: 13 [VK_OHOS_surface=YES] ; device: Maleoon 916 api 1.2.309 ; device ext: 69
MISS VK_KHR_dynamic_rendering / VK_KHR_push_descriptor / VK_EXT_vertex_attribute_divisor (+feature)
OK   VK_KHR_synchronization2 / VK_KHR_swapchain
```
⇒ **彻底排除「app 进程可能比 shell 宽松」的残余假设**（门控与裁剪是**进程无关的栈行为**）。

同一日志还暴露华为 iGraphics / GameAware 层的门控（`/system/etc/vulkan/implicit_layer.d/VkLayer_{iGraphics,GameAware}.json`）：
```
DisableReasonLog: … is GT Disable by not support
```
即：iGraphics 需一份本机缺失的**游戏配置 XML**（`/sys_prod/etc/graphics_game/config/igraphics_config_cust.xml`）才生效。
**注意：该层不含缺失扩展的字符串，即使启用也无法补出 Vulkan 扩展** —— 故「GT/game 白名单」不是解锁 Vulkan 的途径。

---

## 3. 关键读数（能力面 / 自证 / 裁决）

### 3.1 Q1 隐藏入口点 + **归属判定**（翻案的关键）

用 `/proc/self/maps` 把 `vkGetDeviceProcAddr` 返回的指针**归属到具体 so 的段**（必须**在 ICD 被 dlopen 之后**采样，见 §4）：
```
vkCmdBindPipeline                    → ICD r-xp   [对照]
vkCmdPipelineBarrier2 / vkCmdBeginRendering / vkCmdEndRendering → ICD r-xp   ★
vkCmdPushDescriptorSet（无后缀）/ …WithTemplate → ICD r-xp   ★
vkCmdBeginRenderingKHR / …PushDescriptorSetKHR / …KHR → NULL
vkCreateSwapchainKHR → 未 enable 时 NULL；enable 后 → libvulkan_swapchain.so r-xp   [layer 提供]
```
ICD 的 `.dynsym` **只有两个符号**（`vk_icdGetInstanceProcAddr` / `vk_icdNegotiateLoaderICDInterfaceVersion`）
⇒ 入口点全靠**它内部名字表**，这也解释了"字符串里有 ≠ 能解析"。loader `libvulkan.so` 的 `.dynsym` 含一批 `Cmd…KHR`（trampoline），**与 ICD 无关**。

### 3.2 Q2 feature 真值（带自校验对照）

对照必须全 OK，否则该行无意义（第一版就是被自己写错的 sType 骗了，§4）：
```
core1.0 : multiDrawIndirect=1 drawIndirectFirstInstance=1 fillModeNonSolid=1 samplerAnisotropy=1
vk11(ctl): multiview=1 variablePointers=1 shaderDrawParameters=1
vk12(ctl): descriptorIndexing=1 … timelineSemaphore=1 hostQueryReset=1
tfEXT(ctl): transformFeedback=1   ← 证明"链式查询 + EXT 结构体"都是通的
vk13    : synchronization2(ctl)=1 **dynamicRendering=0**
divisorEXT: **vertexAttributeInstanceRateDivisor=0** ; props: EXT(1000190000) max=1 ; 1.4-core(1000525000) max=1
```

### 3.3 Q3 `vkCreateDevice` 拒收未上报扩展名

```
(对照) 无扩展 / VK_KHR_synchronization2 → rc=0
隐藏三件 / 单独任一件                   → rc=-7 (VK_ERROR_EXTENSION_NOT_PRESENT)
createInstance(apiVersion=1.3) 后重试    → 仍 rc=-7，扩展表仍 69 个
```
⇒ **必须"剔名后再转发"**；反过来，**enable 成功 = KHR 名可解析**。

### 3.4 Q4 loader 注入面 —— **全死**

`VK_LAYER_PATH` / `VK_INSTANCE_LAYERS` / `VK_LOADER_LAYERS_ENABLE=*` / `VK_ICD_FILENAMES=<不存在>` /
`VK_DRIVER_FILES=<不存在>` / `VK_LOADER_DEBUG=all` —— **六项全部无效**：layer 列表恒为 4 项、物理设备恒为 1、无任何 debug 输出。
⇒ 这是**被裁剪过的 loader**，**env 注入路线作废**。

### 3.5 功能自证（像素级）

```
自证 A  vkCmdBeginRendering（0 附件）: begin → end → submit → wait 全 rc=0
自证 B  vkCmdPushDescriptorSet: layout(flags=PUSH_DESCRIPTOR_BIT_KHR) rc=0 → push(1 write) → submit → wait 全 rc=0
自证 C★ 带真实 color attachment 的 dynamic rendering:
        LINEAR 图 → beginRendering(1 attachment, LOAD_OP_CLEAR=(0.25,0.5,0.75,1.0)) → end → submit → wait
        → **map 图像显存**判读：4096/4096 texel = (64,128,191,255)，与请求逐值一致 ✓
        控制项：vkCmdClearColorImage 亦 4096/4096；vkCmdFillBuffer 写满 1024/1024 字 ✓
```
⇒ "dynamic rendering + 真实附件 + 光栅化"这条链在本机成立，是本轮最硬的证据。
（附带观察：日志出现 `CompilerShaderInfoReport: … bisheng_graphic_pipeline_compilation_… compile costs …`
⇒ **管线创建走厂商 Bisheng 着色器编译器**，与 [`1.21.1-崩溃-两条链与随包规避.md`](1.21.1-崩溃-两条链与随包规避.md) 的"链 A"同一个编译器。）

### 3.6 分阶段裁决（原生 C / 真 shaderc）

```
stage 4 建管线 : vkCreateGraphicsPipelines(renderPass=NULL, pNext=PipelineRenderingCreateInfo) rc=0
                 → beginRendering + bindPipeline + draw(3) 读回 **magenta=4096 / black=0**（像素正确）
stage 5 描述符 : 5a 普通描述符集 pool→set→vkUpdateDescriptorSets→vkCmdBindDescriptorSets→消费 全通（storage image 落地）= PASS
                 5b push 描述符被消费 ⇒ **VK_ERROR_DEVICE_LOST**、写入未落地 = FAIL（真实的缺口）
stage 6 compute: 6a SSBO 读 → storage image 写：shaderc status=0、管线 rc=0、texel 4096/4096 落地 = PASS
                 6b UBO：allocateDescriptorSets rc=-1000069000（= OUT_OF_POOL_MEMORY，我的池尺寸问题，未追）
stage 7 采样   : CPU 填 LINEAR 图 (200,100,50,255) → GPU 采样管线 rc=0 → 目标图首个非黑 texel 逐值一致 = PASS
```
**镜像传输族**：`vkCmdCopyBufferToImage` 11/11 参数组合全 `SIGSEGV`；同族 `vkCmdCopyImageToBuffer` / `vkCmdBlitImage` / `…2` 为空操作
（**事后改判**：`vkCmdCopyBufferToImage` 的"崩"实为 shim 自身 7 参 vs 6 参包装错位，见 §4 与 [`Vulkan后端-实现与原理.md`](Vulkan后端-实现与原理.md) §2.2）
⇒ 收敛出的补实现（当时设计）= **CPU 写 → LINEAR 中转图 → `vkCmdCopyImage` → 目标图（保持 OPTIMAL）**；
**正式落地改 GPU 别名路线、F53 默认关**（图像上传走原始 `vkCmdCopyBufferToImage` 直转发）。

### 3.7 硬边界：压缩纹理

`probe_tiling_routes.py` 能力面查询（只读、无渲染）：
| 路线 | 合法格式 |
|---|---|
| compute 写 storage image | 8/23 |
| 强制 LINEAR | 12/23 |
| 压缩格式（BC*/ETC2/EAC/ASTC，11 个） | **两条都非法**（LINEAR 非法 + 全无 STORAGE）★ **硬边界** |

⇒ 对 vanilla（未压缩 RGBA8/SRGB 为主）两条都合法；**压缩纹理是死角**（旁证：本机 `BC4/5/7` 连 SAMPLED 都没有）。
另注：本机 **LINEAR 图同时支持 SAMPLED + STORAGE + COLOR_ATTACHMENT + BLIT**（比一般驱动宽松）。

### 3.8 WSI 全链（原生 C + 真窗口）

临时挂 ArkUI `XComponent` 取 surfaceId → `OH_NativeWindow_CreateNativeWindowFromSurfaceId`（rc=0）→
**`vkCreateSurfaceOHOS` rc=0** → `vkGetPhysicalDeviceSurfaceSupportKHR` supported=1 → `vkCreateDevice`（带 swapchain，rc=0）
→ **`vkCreateSwapchainKHR` rc=0** + **`vkGetSwapchainImagesKHR` = 3 张图** ⇒ **可上屏**。
实测参数（实现时照抄）：`imageCount=[3,64]`、`currentExtent` 随窗口、`min/max extent=1x1/4096x4096`、
`currentTransform=IDENTITY`、**`supportedCompositeAlpha=0x8`（仅 `INHERIT`）**、`supportedUsageFlags=0x9f`、
formats 9 个、**presentModes = MAILBOX + FIFO（无 IMMEDIATE）**。
⚠️ 我传的 `compositeAlpha=OPAQUE(0x1)` caps 里并不支持却仍 rc=0 —— 又一处"驱动不校验"；实现按 caps 传 `INHERIT`。
⚠️ `vkCreateSurfaceOHOS(instance, {window=NULL}, …)` **直接 SIGSEGV**（真实现、无 NULL 校验）⇒ 必须传活着的 `OHNativeWindow*`。
⚠️ 入口进程 UIAbility.onCreate 里做这类 native 调用会直接崩 ⇒ 必须走**组件内**的 `await import('meowjre')`。

---

## 4. 我踩过的坑（后人别再踩）

1. **sType 常量写错 ⇒ 假阴性**（这就是上一版判错的原因）。已核对（主仓 `ref/lwjgl3` 生成源）：
   `VkPhysicalDeviceFeatures2 = 1000059000`（旧脚本写成 `1000056000` ⇒ 错的）；
   `VkPhysicalDeviceVulkan1_1/1_2/1_3_FEATURES = 49/51/53`（不是 `1000096xxx`）；
   `PhysicalDeviceDynamicRenderingFEATURES = 1000044003`；`VertexAttributeDivisorFEATURES_EXT = 1000190002`。
   **教训**：feature 查询必须带**已知为真的对照**，否则读到的 0 可能只是"结构体没被认"。
2. **OPTIMAL（tiled）图像的显存不能按线性扫描判读** —— 重排后字节里找不到连续颜色模式，曾据此误判"OPTIMAL 不支持渲染"。**凡要看像素，用 `VK_IMAGE_TILING_LINEAR`**（本机 UMA，显存可直接 map）。
3. **看 image 内容前先确认 usage 齐**：漏 `TRANSFER_DST` 会让对照 `vkCmdClearColorImage` 本身非法（静默丢弃）。
4. **`/proc/self/maps` 必须在 ICD 被 dlopen 之后采样**，否则归属判定全落到 `UNKNOWN`。
5. **同一块 `VkDeviceMemory` 不能重复 map**（第二次返回 `-5 VK_ERROR_MEMORY_MAP_FAILED`），用完先 unmap。
6. **判"实现"不能只看名字/字符串**：icd_strings 有 125 个 `VK_*` 但只上报 69；KHR 名为 NULL 也可能只是被门控。
7. ★★ **ctypes：绝不要把临时对象的 `addressof()` 传给 Vulkan**（本轮最贵的坑）。写成 `WDS(…, C.addressof(DII(None, view, 1)), …)` —— `DII(...)` 是**临时对象**，表达式一结束即被 GC，驱动拿到**悬垂指针** ⇒ 表现为 `vkUpdateDescriptorSets` **SIGSEGV**、push 描述符**设备丢失**。**两个"驱动缺陷级"假阳性由此而来，一度把整条 Vulkan 线判死**；原生 C 复验后全部推翻。规矩：**传给 Vulkan 的 struct 一律先绑定到变量**；且**"驱动缺陷"级结论必须用原生 C 复验**。
8. **手写 SPIR-V 的 `OpEntryPoint` 入口名必须 NUL 终止并补齐到整字** —— `"main"` 恰好 4 字节，必须占 **2 个字**（`0x6e69616d` + `0x00000000`）；只写 1 个字时解析器把后续操作数吞进名字里 ⇒ 厂商前端报 `SPV01: Could not find an entrypoint …`。修好后厂商前端接受手写模块 ⇒ **SPIR-V 迭代可完全在设备上做**。

---

## 5. 临时探针与物证归档

**应用内探针**（`meowvkprobe.c` + UI 宿主 + 16 个 `MEOW_VK_PROBE_*`）：**已整体删除**（F79）。
探针分档（当时 6 个按钮）：运行（能力面 + feature + shaderc 编译）/ 管线（建管线 + dynamic rendering + 读回）/
拷贝（两个坏拷贝，故意看它怎么崩）/ 描述符（普通集 vs push 同形对比）/ SSBO（复验 compute UBO/SSBO）/
采样（CPU 填 LINEAR 图 + 采样读回）。判读一律 LINEAR 附件 + map 显存，逐行 `fflush` 到 `<filesDir>/vulkan-probe.txt` 并 hilog 镜像。

**源码误删事故**：归档时 `cp` 因 cwd 漂移**静默失败**、紧随的 `rm` 删掉了未纳入版本控制的 `meowvkprobe.c`（约 1610 行）。
**幸存物证 = 编译产物**（`stuffs/research/vulkan/probe_archive/`：`meowvkprobe.c.o` 逐字节原物、`.strings.txt` 757 条字面量、
`.lines.txt` DWARF 行表、`probe-integration.diff`、`reprobe` 主仓 `libmeowvulkan.so` shim）—— 查报文字面量 / 结构体布局 / 函数边界行号一律以 `.o` 及其派生物为准。
**教训**：① 归档要**先确认复制成功、再删原物**；② 跨目录操作**不要依赖 cwd**（一律绝对路径）；③ **未纳入版本控制的临时件**在回退动作里最脆弱，回退这类文件应当**最后**做、且**先备份**。

**仪器链**（本役最值钱的产出）：`resolve_pc.py`（pc/lr → Java 方法，消费 `-XX:+LogCompilation`）；
`MEOW_VK_WD`（shim 看门狗，超时打 hilog + `SIGQUIT` 自触线程转储）；自有 shell 直读 `/data/log/faultlog/faultlogger/`（写全路径、会滚动清理 ⇒ 读到即归档）；
`-DNDEBUG` 移除让第三方库（VMA）自报 `文件:行号`；产物自报版本（`shim build <tag>`）；VM 参数先自教（JVM 会明确报 `Unrecognized`）。
详见 [`../../10-research/原生崩溃排查-仪器手册.md`](../../10-research/原生崩溃排查-仪器手册.md)。

**死路清单（不要重走）**：等 `hs_err`；用我们的 dumper 抓 `MAPERR`（同样被 DFX 挡前）；`sigaction` 抢在 DFX 前（sigchain 定序）；
`MEOW_BT_LOW=1`；**劫持 SIGSEGV**（会把 JVM 弄死）；用 faultlog 的"有无"做历史/范围推断（会被清理）；
**凭记忆写 VM 参数 / 结构体字段序**；**信 `lr`**（可能是脏值）。

---

## 6. 本机事实速查

```
loader : /system/lib64/libvulkan.so   1.3.275（但 env 被裁剪，见 §3.4）
ICD    : /vendor/lib64/passthrough/vulkan.hvgr_v210.so   （唯一）
         核心 /vendor/lib64/libhvgr_v210.so ；编译器 libbishenggpucompiler_v210.so.15
swapchain 提供者: /system/lib64/libvulkan_swapchain.so  （implicit layer VK_LAYER_OHOS_surface）
device : Maleoon 916  apiVersion 1.2.309  device_ext 69
instance_ext: VK_KHR_surface / VK_OHOS_surface / VK_KHR_portability_enumeration / VK_LUNARG_direct_driver_loading …
内存   : type0 flags=0x7 DEVICE_LOCAL|HOST_VISIBLE|HOST_COHERENT（UMA ⇒ 显存可直接 map 判读）
required(miss): VK_KHR_dynamic_rendering / VK_KHR_push_descriptor / VK_EXT_vertex_attribute_divisor (+feature)
required(ok)  : VK_KHR_synchronization2 / VK_KHR_swapchain
复检入口: python3 stuffs/research/vulkan/probe_mc_verdict.py   （⚠️ 先按 §4 第 1 条修 sType）
          + python3 stuffs/research/vulkan/probe_bypass2.py    （归属判定 + 带对照的 feature）
```

> **重开 / 复检条件**：系统 / 驱动升级后 `probe_mc_verdict.py` 的 **5/5 扩展 + feature 全 OK**（通常随 Vulkan 1.3 能力）——
> 触发方式 = 系统 OTA / GPU 驱动更新 / 换机。本轮已排除：API 版本门控、implicit layer 过滤、第二 ICD、软件 ICD、app vs shell 上下文差异。
> 长期可向平台反馈两件事：① 别裁剪 Vulkan 的**上报面**（KHR 名 / feature 位）；② 修 `vkCmdCopyBufferToImage` 系的**崩溃 / 空操作**。

---

**相关**：[`Vulkan后端-实现与原理.md`](Vulkan后端-实现与原理.md)（权威机制 / 原理）、
[`../../90-archive/Vulkan后端-跟进与结案.md`](../../90-archive/Vulkan后端-跟进与结案.md)（旧结案档，BLOCKED 结论已归档）、
[`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 24 条、[`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §H、
[`../../00-current/运行时环境变量.md`](../../00-current/运行时环境变量.md)（env 开关总表）、
[`MC26.x渲染栈-差异分析.md`](MC26.x渲染栈-差异分析.md)、[`SDL3适配-复盘.md`](SDL3适配-复盘.md) §七、
[`../../10-research/原生崩溃排查-仪器手册.md`](../../10-research/原生崩溃排查-仪器手册.md)。
