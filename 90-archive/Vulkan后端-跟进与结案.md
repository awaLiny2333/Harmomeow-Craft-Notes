# MC 26.2+ Vulkan 图形后端跟进（可复现取证 + 结论）

> 已归档（2026-10-02；判 **BLOCKED** 的结论已被推翻 —— 真相是**上报面被裁剪**（ICD 实现存在、只是不对外上报）；
> 现役机制见 [`Vulkan后端-实现与原理.md`](../20-design/render/Vulkan后端-实现与原理.md)、取证与读数见 [`Vulkan后端-取证存档.md`](../20-design/render/Vulkan后端-取证存档.md)）。
> 日期：2026-09-11 ｜ 当时结论：**调研完成，结论 BLOCKED（当前系统/驱动不可行）**。
> 本文余下内容仍可作**取证方法 / 设备事实 / WSI 与 native 适配蓝图**参考；判错错因 = 本文所用脚本的 sType 常量写错
> ⇒ "必需 feature 缺失"一栏是**假阴性**。
> 相关：[`已知限制与待解.md`](../00-current/已知限制与待解.md) §A6、[`SDL3桥接-设计.md`](../20-design/render/SDL3桥接-设计.md)、[`LWJGL3世代管理-方案.md`](../20-design/lwjgl/LWJGL3世代管理-方案.md)、`../40-adaptation/ohos-vulkan-api`（见 `30-supply-chain`/记忆）
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 24 条](../00-current/现状基线.md) 与 [已知限制与待解.md §A6](../00-current/已知限制与待解.md)（**该条现已改为"可用"**，2026-09-18）。

---

## 0. 结论（TL;DR）

**MC 26.2/26.3 的原生 Vulkan 后端在本机（Maleoon 916 / OpenHarmony 7.0.0.105）当前驱动下无法初始化。**

- MC **硬性要求** 5 个 device 扩展 + 1 个 device feature：
  `VK_KHR_dynamic_rendering`、`VK_KHR_push_descriptor`、`VK_KHR_synchronization2`、`VK_EXT_vertex_attribute_divisor`、`VK_KHR_swapchain` / `vertexAttributeInstanceRateDivisor`。
- 本机唯一 Vulkan 驱动 **只上报其中 2 个**（`synchronization2`、`swapchain`），**缺 3 个扩展 + 该 feature** → MC 直接抛
  `VULKAN_MISSING_EXTENSION`（"Device [{}] does not support required extensions, missing: {}"）。
- 驱动二进制里**其实含这些扩展的代码/字符串**（说明驱动有能力但**主动不上报**，即被 `apiVersion 1.2` 能力档位卡住），
  但我们无任何可用开关去解锁：无第二 ICD、无 layer 注入、API 版本/进程名均不影响上报集合。
- **重开条件**：系统/驱动升级到上报 `VK_KHR_dynamic_rendering`（通常随 Vulkan 1.3 能力）**且** 暴露
  `VK_KHR_push_descriptor` + `VK_EXT_vertex_attribute_divisor`（+ divisor feature）。

适配蓝图（GLFW/SDL WSI、natives、启用开关）已备好，见 §7；解锁后按 §8 执行。

---

## 1. 取证方法（全部可复现）

| 步骤 | 命令/位置 | 说明 |
|---|---|---|
| 设备 Vulkan 枚举 | `stuffs/research/vulkan/probe_vulkan.py` | ctypes dlopen `/system/lib64/libvulkan.so`，枚举 loader/device 扩展 |
| MC 式判定 | `stuffs/research/vulkan/probe_mc_verdict.py` | 对 MC 的 required 集逐项 PASS/MISS + 从 `/proc/self/maps` 定位 ICD |
| API 版本门控测试 | `stuffs/research/vulkan/probe_apiver.py` | 以 1.0/1.1/1.2/1.3 各建实例，对比上报集合（无差异） |
| MC 需求解构 | `strings` 抽 `com/mojang/blaze3d/vulkan/*`（26.2）、`com/mojang/renderpearl/backend/vulkan/*`（26.3） | 沙箱 JVM 不可跑（`Failed to mark memory page as executable`），故用 strings 读常量池 |
| 驱动内部 | `strings /vendor/lib64/passthrough/vulkan.hvgr_v210.so` | 6.3MB，含 125 个 `VK_*` 串 |

---

## 2. 设备侧实测（权威事实）

- **loader**：`/system/lib64/libvulkan.so`，`vkEnumerateInstanceVersion` = **1.3.275**；无 `libvulkan.so.1`。
- **ICD（唯一）**：`/vendor/lib64/passthrough/vulkan.hvgr_v210.so`（+ 核心 `libhvgr_v210.so`、编译器 `libbishenggpucompiler_v210.so.15`）。经 `/proc/self/maps` 确证。
- **物理设备**：`Maleoon 916`，**apiVersion 1.2.309**，INTEGRATED_GPU，**device 扩展 69 个**。
- **instance 扩展 13 个**，含 `VK_KHR_surface`、**`VK_OHOS_surface`**、`VK_KHR_portability_enumeration`、`VK_EXT_debug_utils`、`VK_LUNARG_direct_driver_loading`。
- **Implicit layers**（均不注入缺失扩展）：`VK_LAYER_HUAWEI_iGraphics`、`VK_LAYER_HUAWEI_GameAware`、`VK_LAYER_TRACE3D_Loader`、`VK_LAYER_OHOS_surface`（`libvulkan_swapchain.so`）。
- **驱动「知而不报」**：ICD 字符串含 125 个 `VK_*`，比实际上报多 30 个，含
  `VK_KHR_dynamic_rendering`、`VK_KHR_dynamic_rendering_local_read`、`VK_KHR_push_descriptor`、
  `VK_EXT_vertex_attribute_divisor`、`VK_KHR_maintenance4/5/6`、`VK_KHR_copy_commands2`、
  `VK_EXT_descriptor_buffer`、`VK_EXT_extended_dynamic_state(2)`、`VK_EXT_line_rasterization` 等
  → 典型「Vulkan 1.2 能力档位」裁剪（**非硬件缺失**）。

### 2.1 应用内探针实测（2026-09-11，确认 app 上下文 = shell）

在启动器首页加「Vulkan 能力探测」按钮（native `probeVulkan()`，`entry` 模块，dlopen libvulkan.so）
**——临时探针，取证完成后已回退、不保留**。应用进程内实测**与 shell 完全一致**：

```
loader: libvulkan.so loaded
loader apiVersion: 1.3.275
instance ext: 13 [VK_OHOS_surface=YES]
device: Maleoon 916  api 1.2.309
device ext: 69
MISS VK_KHR_dynamic_rendering
MISS VK_KHR_push_descriptor
OK   VK_KHR_synchronization2
MISS VK_EXT_vertex_attribute_divisor
OK   VK_KHR_swapchain
MISS vertexAttributeInstanceRateDivisor
VERDICT: BLOCKED (missing 3/5 +feature)
```

→ **彻底排除「app 进程可能比 shell 宽松」的残余假设**。

同一日志还暴露华为 iGraphics / GameAware 层的门控（`/system/etc/vulkan/implicit_layer.d/VkLayer_{iGraphics,GameAware}.json`）：
```
IsGameInBlackList(169): load local config xml fail!
GetPlatformProduct(100): load local config xml fail!
DisableReasonLog(159): meow.liny.craft.awa is GT Disable by not support
CheckGameVersion(350): not config gameversion
GetGameName(100): No iGraphicsCore opt is enabled. Disable hook.
```
即：iGraphics 需一份本机缺失的**游戏配置 XML**（`/sys_prod/etc/graphics_game/config/igraphics_config_cust.xml`）才生效；
我们（非白名单游戏）走不到该优化路径。**注意：该层不含缺失扩展的字符串，即使启用也无法补出 Vulkan 扩展**——
故「GT/game 白名单」不是解锁 Vulkan 的途径，仅解释 iGraphics 优化为何未生效。

---

## 3. MC 后端需求解构

### 3.1 MC 26.2（`com.mojang.blaze3d.vulkan`，WSI = **GLFW**）

- `VulkanBackend` 静态常量 **`REQUIRED_DEVICE_EXTENSIONS`**（常量池顺序）：
  ```
  VK_KHR_dynamic_rendering
  VK_KHR_push_descriptor
  VK_KHR_synchronization2
  VK_EXT_vertex_attribute_divisor
  VK_KHR_swapchain
  ```
  经 `VulkanPhysicalDevice.getMissingExtensions(required)` 校验 → 缺则
  `BackendCreationException(VULKAN_MISSING_EXTENSION)`（"Device [{}] does not support required extensions, missing: {}"）。
- **必需 feature**：`vertexAttributeInstanceRateDivisor`（"Device [{}] does not have required feature [{}]"）。
- 其它门槛：Vulkan **1.2**（"Device [{}] does not support Vulkan 1.2"）、graphics queue。
- 可选：`VK_KHR_portability_subset`、`VK_NV_device_diagnostic_checkpoints`、`VK_AMD_buffer_marker`、`VK_EXT_multi_draw`（可选 FeatureSet）。
- WSI 调用：`glfwWindowHint`、`glfwVulkanSupported`、`glfwGetRequiredInstanceExtensions`、`glfwCreateWindowSurface`、`glfwGetPhysicalDevicePresentationSupport`。
- **架构证据**：常量池**没有** `VkRenderPassCreateInfo`/`VkFramebufferCreateInfo`/`vkCmdBeginRenderPass`；
  只有 `VkRenderingInfo`/`VkPipelineRenderingCreateInfoKHR`/`vkCmdBeginRendering` → **纯 dynamic rendering，无退路**。
- 后端选择：`net.minecraft.client.PreferredGraphicsApi{DEFAULT,OPENGL,VULKAN}`（`Options` 内 `graphicsApi`，有 `OptionsForceDefaultGraphicsApiFix` datafix）；`getBackendsToTry()` 返回 `GpuBackend[]`。

### 3.2 MC 26.3（`com.mojang.renderpearl`，WSI = **SDL3**）

- `VulkanFeatureSets`：`REQUIRED_FEATURESET`（名 "Minecraft base required"）= VK10/VK11/VK12 features +
  `KHRPushDescriptor` + `KHRDynamicRendering` + `KHRSynchronization2` + `EXTVertexAttributeDivisor`(+`vertexAttributeInstanceRateDivisor`)；
  另有 optional/conditional：`MULTI_DRAW`、`AMD_BUFFER_MARKER`、`NV_DIAGNOSTIC_CHECKPOINT`、`CALIBRATED_TIMESTAMP`、`PORTABILITY_SUBSET`、`Wireframe`、`requiredIfExtensionsAvailableFeatureSets`。
- WSI 调用（LWJGL `org.lwjgl.sdl`）：`SDL_Vulkan_LoadLibrary`、`SDL_Vulkan_GetVkGetInstanceProcAddr`、`SDL_CreateWindow`、`SDL_Vulkan_*`。
- **核心必需集与 26.2 相同** → 同一 blocker。

---

## 4. 我方现状（解构结果）

### 4.1 ArkTS 启用开关（唯一注入点）
- `entry/.../common/constants/LaunchDefaults.ets`
  - `RENDERER_LIB='libGLv4.so'`、`RENDERER_ENV='openglv4'`
  - `VULKAN_LIB='libvulkan.so'`（**死常量，无引用**）
  - `VULKAN_LIB_DISABLED='libmeow-no-vulkan.so'`（注释：26.2 的 `NativeLibrariesBootstrap` 一旦探到 loader 就 eager 强载 shaderc/spvc/vma）
- `entry/.../common/data/MinecraftLauncher.ets`
  - `[227]` `-Dorg.lwjgl.vulkan.libname=${VULKAN_LIB_DISABLED}` ← **禁用落点**
  - `[219]` `-Dorg.lwjgl.opengl.libname=libGLv4.so`；`[222-224]` lwjgl 世代选名；`[386-408]` classpath 排除 json 的 `org/lwjgl/**`

### 4.2 Java 侧（**已就绪，零缺失**）
- 随包 `lwjgl-3.4.3.jar` **已含** `org/lwjgl/vulkan/`（4071 类）、`org/lwjgl/util/vma/`（48）、`org/lwjgl/util/shaderc/`（65）、`org/lwjgl/util/spvc/`（43）。
- `tools/lwjgl/build_lwjgl_jar.sh[117:125]`：`lwjgl-vulkan` 恒含；`3.4.*` 自动追加 `lwjgl-sdl lwjgl-vma lwjgl-spvc lwjgl-shaderc`。
- **loader 名解析**：`VK.java` Linux 分支 `Library.loadNative(..., Configuration.VULKAN_LIBRARY_NAME, "libvulkan.so.1")`；
  可覆盖键 `-Dorg.lwjgl.vulkan.libname`。**OHOS 无 `.so.1`，启用时必须写 `libvulkan.so`。**

### 4.3 Native 侧（**缺 1 件**）
- 已随包：`liblwjgl_343{,_opengl,_stb}`（现代单代；旧 `_333` 已移除）、`liblwjgl_tinyfd`、`libshaderc.so`、`libspirv-cross.so`、`libSDL3.so`、`libfreetype.so`、`libopenal.so`。
- **缺 `liblwjgl_vma.so`**（`lwjgl-vma` 的 JNI 原生库；`LibVma` 名字写死 `liblwjgl_vma.so`，无覆盖键）。
  - 素材齐：`ref/lwjgl3/modules/lwjgl/vma/src/main/c/vk_mem_alloc.h` + `src/generated/c/org_lwjgl_util_vma_*.cpp`；
    上游配方 `config/linux/build.xml`（C++，`-I vma/src/main/c -I vulkan/src/main/c -latomic`）。
  - `tools/lwjgl/build_lwjgl_natives.sh` 现只编 C（core/opengl/stb/tinyfd），**需加 C++ vma 目标**。
  - 参考件（非自编、勿直接采用）：`ref/HomoLauncher/libs/lwjgl3/libs/arm64-v8a/liblwjgl_vma.so`。

### 4.4 窗口 WSI（**26.2 与 26.3 均缺**）
- **GLFW 桥**（26.2）：`libs/meowcraftlib/src/main/cpp/meowcraftbridge/`
  - `egl_gl.c`：仅 EGL/GL；`meowSetWindowHint` 是 no-op（`GLFW_NO_API` 被忽略）；OHNativeWindow 已在
    `meowSetSurfaceId()`→`meow_environ->window[0x000]` 可取。
  - `input_bridge.c`：`Java_org_lwjgl_vulkan_VK_getVulkanDriverHandle` **返回 0**（"no Vulkan loader"）；无任何 surface。
  - **GLFW.java overlay**（`tools/lwjgl/deltas/overlay-3.4.3/org/lwjgl/glfw/GLFW.java`）**缺**：
    `glfwVulkanSupported`、`glfwGetRequiredInstanceExtensions`、`glfwCreateWindowSurface`、
    `glfwGetInstanceProcAddress`、`glfwGetPhysicalDevicePresentationSupport`、`glfwInitVulkanLoader`。
- **SDL 桥**（26.3）：`tools/sdl/src/video/ohos/` 无任何 `VK_/SDLK_VULKAN/SDL_Vulkan_*`；
  `SDL_ohosvideo.c[151-162]` 只挂 `GL_*`，无 `Vulkan_*` 回调。
- 构建：两份 CMakeLists 均未链 `libvulkan`；`module.json5` 无 syscap。
- 新增 native 函数须同步：`libs/meowcraftlib/Index.ets` re-export + `meowjrebridge.cpp` NAPI 表。

---

## 5. 缺口 → 需求矩阵

| MC 需要 | 设备是否具备 | 我方是否就绪 |
|---|---|---|
| `VK_KHR_synchronization2` | ✅ | — |
| `VK_KHR_swapchain` | ✅ | — |
| **`VK_KHR_dynamic_rendering`** | ❌ **缺** | — |
| **`VK_KHR_push_descriptor`** | ❌ **缺** | — |
| **`VK_EXT_vertex_attribute_divisor` + feature** | ❌ **缺** | — |
| `VK_OHOS_surface`（平台 WSI） | ✅ | ❌ 未接入（桥/SDL） |
| `lwjgl-vulkan`（Java） | — | ✅ jar 已含 |
| `liblwjgl_vma.so`（native） | — | ❌ 未自编 |
| `libshaderc/libspirv-cross` | — | ✅ 已自编随包（按 3.4.3 钉版） |
| loader 名 `libvulkan.so` | ✅ | ❌ 当前被禁用 |

**致命项**：驱动缺 3 个必需扩展 + 1 feature → **即使我方全部补齐，MC 也无法通过能力校验**。

---

## 6. 重开条件（何时再来）

满足全部：
1. 系统/驱动升级后 `probe_mc_verdict.py` 的 **5/5 扩展 + feature 全 OK**；
2. 具体为驱动上报 `VK_KHR_dynamic_rendering`（含 `dynamicRendering` feature）、`VK_KHR_push_descriptor`、
   `VK_EXT_vertex_attribute_divisor`（含 `vertexAttributeInstanceRateDivisor`）；
3. 触发方式：系统 OTA / GPU 驱动更新 / 换机。

本轮已排除：API 版本门控、implicit layer 过滤、第二 ICD、软件 ICD、**app vs shell 上下文差异（应用内探针实测一致）**。
残余：无（结论已两次独立取证确认）。

---

## 7. 适配蓝图（解锁后执行）

### 7.1 启用开关（ArkTS）
1. `LaunchDefaults.ets`：保留 `VULKAN_LIB`；新增渲染后端开关（按版本/用户选项），支持 `VULKAN`。
2. `MinecraftLauncher.ets[227]`：Vulkan 模式改为 `-Dorg.lwjgl.vulkan.libname=libvulkan.so`（**非 `.so.1`**）；
   可选 `-Dorg.lwjgl.vulkan.explicitInit`。
3. 后端选择：写 `Options.graphicsApi`（`PreferredGraphicsApi`）或经 launcher 注入；否则默认仍走 GL。

### 7.2 26.2 —— GLFW Vulkan WSI（`meowcraftbridge`）
1. **Java overlay** `GLFW.java`（现现代单代 `overlay-3.4.3/`；历史曾有 `overlay-3.3.3/`，2026-09-14 移除）新增：
   - `glfwVulkanSupported()` → 探测 loader（dlopen `libvulkan.so`）成功即 true；
   - `glfwGetRequiredInstanceExtensions()` → 返回 `{VK_KHR_surface, VK_OHOS_surface}`（+ 若请求 portability 则附 `VK_KHR_portability_enumeration`）；
   - `glfwCreateWindowSurface(instance, window, alloc, pSurface)` → 走 native；
   - `glfwGetInstanceProcAddress(instance, name)` → `vkGetInstanceProcAddr`；
   - `glfwGetPhysicalDevicePresentationSupport(...)` → 恒 true（OHOS WSI 由 swapchain layer 支持）；
   - `glfwInitVulkanLoader`（若被调用）。
2. **native**：`meowcraftbridge` 加 `dlopen("libvulkan.so")` + 从 `meow_environ->window` 取 `OHNativeWindow*`
   → `vkCreateSurfaceOHOS(instance, &VkSurfaceCreateInfoOHOS{window}, NULL, &surface)`（`vulkan_ohos.h`）。
   - CMake 链 `libvulkan.so`；`glfwGetVulkanDriverHandle` 由返回 0 改为真 handle。
3. 新增 NAPI → 同步 `Index.ets` + `meowjrebridge.cpp`。

### 7.3 26.3 —— SDL Vulkan（`tools/sdl/src/video/ohos/`）
1. `SDL_ohosvideo.c` 挂 `Vulkan_LoadLibrary`/`Vulkan_GetInstanceExtensions`/`Vulkan_CreateSurface`/`Vulkan_GetVkGetInstanceProcAddr`/`Vulkan_UnloadLibrary` 回调。
2. `SDL_ohoswindow.c` 用 `OHNativeWindow` → `vkCreateSurfaceOHOS`（同 7.2）。
3. 参考：SDL3 自身 `SDL_vulkan.h` + Android/Linux 后端实现（`ref/SDL`）。

### 7.4 natives
1. `tools/lwjgl/build_lwjgl_natives.sh` 加 **C++** vma 目标（`-I vma/src/main/c -I vulkan/src/main/c -latomic`）→ `liblwjgl_vma.so`。
2. `install_natives.sh --native liblwjgl_vma.so=<out>`（manifest tag `common`）；`--verify` 纳入校验。
3. 清模块 build + `devecocli build --modules entry meowjre` 后部署。

### 7.5 验证
- 启动加 `-Dorg.lwjgl.util.Debug=true`/Vulkan 校验层；确认 `gen=3.4.x`、Vulkan 1.3、`renderpearl.backend.vulkan` 命中。

---

## 8. 建议的当前行动

> **2026-09-18 更新**：本节"不落地 Vulkan 运行路径"的建议**已废** —— Vulkan 档已落地可用（界面选 Vulkan 即用、零必配 env），
> 见 [`../20-design/render/Vulkan后端-取证存档.md`](../20-design/render/Vulkan后端-取证存档.md) §13 与 [`现状基线.md`](../00-current/现状基线.md) §5 第 24 条；下文作为 2026-09-11 的历史记录保留。

1. **不落地**任何 Vulkan 运行路径（避免死代码/回不来的适配）；`VULKAN_LIB_DISABLED` 维持。
2. **保留取证工具**：`stuffs/research/vulkan/{probe_vulkan.py,probe_mc_verdict.py,probe_apiver.py}` + 本文件为「复检入口」。
   （应用内探针为一次性取证，已回退，不再保留代码。）
3. **复检时机**：每次系统/驱动 OTA 后跑 `python3 stuffs/research/vulkan/probe_mc_verdict.py`，看是否 5/5 + feature OK。
4. 可选（无害预置，非必需）：先把 `liblwjgl_vma.so` 自编出来放 `stuffs/`（不入包），缩短将来解锁后的落地时间。
5. 长期：向平台反馈「2in1 需 Vulkan 1.3 / dynamic_rendering / push_descriptor / vertex_attribute_divisor」。

---

## 9. 附：本机证据速查

```
loader:  /system/lib64/libvulkan.so  (1.3.275)
ICD:     /vendor/lib64/passthrough/vulkan.hvgr_v210.so  (唯一)
device:  Maleoon 916  apiVersion 1.2.309  deviceType=INTEGRATED  device_ext=69
required(miss): VK_KHR_dynamic_rendering, VK_KHR_push_descriptor, VK_EXT_vertex_attribute_divisor
required(ok):   VK_KHR_synchronization2, VK_KHR_swapchain
feature(miss):  vertexAttributeInstanceRateDivisor
instance_ext ok: VK_KHR_surface, VK_OHOS_surface, VK_KHR_portability_enumeration, VK_EXT_debug_utils
verdict: BLOCKED (3/5 required extensions missing)
```
