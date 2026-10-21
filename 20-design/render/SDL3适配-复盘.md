# 26.3(SDL) 适配全过程复盘 + 与 GLFW 那次对照

> 日期：2026-09-11 ｜ 状态：**26.3-rc-1 实机可玩**（画面/键鼠/转视角/文本）
> 定位：**复盘与对照**。机制/方案细节见 [`SDL3桥接-设计.md`](SDL3桥接-设计.md)（§6 进展、§7 输入、§8 结论）；
> 当年 GLFW 侧净室桥见 [`GLFW净室桥-设计.md`](GLFW净室桥-设计.md)；状态以 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) 为准。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 8 条](../../00-current/现状基线.md)。

---

## 一、26.3 适配时间线（问题 → 根因 → 解）

| # | 现象 | 根因 | 解 |
|---|---|---|---|
| 1 | 启动即崩 `NoClassDefFoundError: org/lwjgl/sdl/SDL` | MC 26.3 **弃 GLFW 改 SDL3**（版本 json 无 `lwjgl-glfw`、增 `lwjgl-sdl:3.4.3`；新后端层 `renderpearl`） | 立项走**真 SDL3 fork** |
| 2 | 选哪版 SDL | ABI 必须与 LWJGL 的 `libSDL3.so` 同源 | **钉 `release-3.4.14`**（读官方 natives 的 `libSDL3.so.git` = `147a8ee3…`） |
| 3 | SDL3 在 OHOS 编不动 | OHOS 工具链 `CMAKE_SYSTEM_NAME=OHOS` → CMake `UNIX` 假（落 unknown）；`pthread_setcanceltype` OHOS 动态 libc 未导出 | **OHOS→Linux 伪装工具链** + `!defined(__OHOS__)` 守卫 + `SDL_UNIX_CONSOLE_BUILD=ON` |
| 4 | 视频后端 | 只有 dummy/offscreen | 自写 **`src/video/ohos`**（外部 `OHNativeWindow` + SDL EGL 路径，`Video drivers: dummy offscreen ohos`） |
| 5 | GL 被否 `glGetError mismatch` | MC `GlBackend.loadLibrary` 要求 **`SDL_GL_GetProcAddress` == `GL.getFunctionProvider()`**（指针同一性） | 驱动 `SDL_GL_GetProcAddress` 改 **`dlopen(path)+dlsym`**（与 LWJGL 一致），EGL 只管 context/surface/swap |
| 6 | `NoClassDefFoundError …shaderc` | renderpearl 用 `lwjgl-{shaderc,spvc,vma}`（26.2 前判"死件"已剔除） | jar 3.4.x **补回三模块** |
| 7 | `UnsatisfiedLinkError: libshaderc.so` | LWJGL 直连真 `libshaderc.so` | **自编 shaderc**（glslang/SPIRV-Tools）+ `libspirv-cross.so`（均按官方 natives `.git` 钉版） |
| 8 | 黑屏（有 BGM） | 多窗共用同一 `OHNativeWindow` 各自建面 + 窗口销毁毁面 | 单一**共享 EGL surface**（不随窗口销毁） |
| 9 | 卡加载 | `SyncSurfaceSize` 把"重建面"写在"尺寸变化"判断之外 → **每帧重建** | 仅**尺寸真变**才重建（后演进为不重建、只重设 geometry） |
| 10 | 键鼠无反应 | `input_bridge.c` 生产者以 **GLFW thunk 为门**（无 thunk 即丢弃）；26.3 无 GLFW stub | 无 thunk 时**回落输入环**；SDL 驱动 `PumpEvents` drain 环 → `SDL_Send*` |
| 11 | 鼠标**垂直偏移**（含点击，越往下越大） | MC `getScaledYPos = y×guiScaledHeight/**getScreenHeight()**`；`Window.height` 取**启动参数 `--height`**（我们硬编码 720），真实客户区 **664**（顶栏 56）；GLFW 路径靠 stub `internalWindowSizeChanged(664)` 刷正 | ① **启动参数用真实客户区尺寸**（等首个 `onSurfaceChanged` 再启动）；② 驱动**按序**发 `SDL_EVENT_WINDOW_RESIZED` |
| 12 | resize 偏移/失效 | `SyncSurfaceSize` 先改 `window->w` 再发事件，SDL 遇"尺寸相等"**丢弃** RESIZED | 改**先发事件再改** `window->w`（+`PIXEL_SIZE_CHANGED`） |
| 13 | 文本乱码 `a<?>][`（重复） | `SDL_UCS4ToUTF8` **不写 NUL**（读栈垃圾）+ `MeowSendChar` 同时发 `char_mods`+`char`（都入环→**两次** `TEXT_INPUT`） | 字符 **NUL 终止** + SDL 泵**折叠 CHAR_MODS/CHAR 对** |
| 14 | 光标**不锁定**（grab 失效） | MC 用 `SDL_WarpMouseInWindow`+`SDL_SetWindowRelativeMouseMode`；驱动**未挂 `SDL_Mouse` 相对模式钩子** → `Unsupported` → `env->grabbing` 不置位 | 新增 **`SDL_ohosmouse.c`**（`SetRelativeMouseMode`→`env->grabbing`；`WarpMouse`→置虚拟光标）+ 泵在 grab 时发**相对位移** |
| 15 | 采样率恒 0 | 排偏移时**误关 native mouse filter**（`meow_rate_tick` 只在 filter/grab overlay tick） | 恢复 filter（偏移真因与 filter 无关） |

**弯路（勿重蹈）**：给 y 加常量 56 / 换 hover 源 / 关 filter / 砍窗口顶栏——**全是表面**；真因在 MC 的屏幕高取值与 SDL 事件推送。

---

## 二、与 GLFW 那次的对照

| 维度 | **GLFW 那次**（≤26.2，见 [`GLFW净室桥-设计.md`](GLFW净室桥-设计.md)） | **SDL 这次**（26.3，本档 §一） |
|---|---|---|
| **触发** | 要把上游 **Pojav/LGPL** 血统清成净室自研；顺带甩 `android/util` | MC 换代：**弃 GLFW 改 SDL3** + 新 `renderpearl` 后端 |
| **性质** | **净化/替换**（换来许可干净 + 自研可控） | **移植/引入**（跑通一条全新平台绑定） |
| **边界做法** | **替换 Java GLFW 绑定**（`org.lwjgl.glfw.*` overlay）+ 自有 native **`libmeowcraftbridge.so` 提供全部 `glfw*`**；**不引入真 GLFW** | **编译整包真 SDL3**（fork tag 3.4.14）+ 新增 **`ohos` video/mouse 驱动**接入**同一套**桥（`meow_environ`/OHNativeWindow/输入环） |
| **方向** | **去库**（Remove） | **引库**（Add，zlib/MIT 正规上游：SDL / shaderc / SPIRV-Cross） |
| **Java 侧改动** | 14 文件 overlay（GLFW/CallbackBridge/Callbacks/… + `RendererInit`/`GLCapabilities`），`javac` 由人跑 | **无 overlay**；jar 增 `org.lwjgl.sdl` 等**原样模块** |
| **native 侧改动** | 重写桥（头文件 + `input_bridge`/`egl_gl`），导出 13 GLFW + 9 CallbackBridge + 11 `meow*` 符号 | 新写 SDL 驱动 5 文件（video/window/gl/events/mouse），导出 SDL 符号；桥**复用**，仅**生产者门控**放宽 |
| **版本钉定** | LWJGL 3.4.3（Maven release + sha1；现代单代，`_333` 已移除） | SDL `release-3.4.14`（官方 natives `.git`）；shaderc/SPIRV-Cross 亦按官方 `.git` 钉 |
| **构建技术** | overlay 合并 fat jar（确定性 pack）+ CMake 桥 | **OHOS→Linux 伪装工具链**编整包 SDL/glslang/SPIRV-Tools；`--require`/`--verify` 断言 |
| **窗口/尺寸** | GLFW stub 的 **`internalWindowSizeChanged`** 主动推真实尺寸（MC 用它算 GUI/鼠标） | SDL **无此回调** → 靠**启动尺寸 = 真实客户区** + **`SDL_EVENT_WINDOW_RESIZED`** |
| **GL proc-address** | 由 LWJGL 自带加载（`glfwGetProcAddress` 抛 Unimplemented，GL 从 `-Dorg.lwjgl.opengl.libname` 载） | MC 要求 **SDL 与 LWJGL 指针同一性** → 驱动 `dlsym` 对齐 |
| **grab/转视角** | `glfwSetInputMode(CURSOR_DISABLED)` → `CallbackBridge.nativeSetGrabbing` → `env->grabbing` | `SDL_SetWindowRelativeMouseMode` → **需挂 `SDL_Mouse` vtable** → `env->grabbing`；相对位移由泵差分 |
| **文本** | GLFW **char 回调**（直接码点，`invokeChar`） | SDL **`TEXT_INPUT`**（枚举/生命周期 + 我们的 NUL/双发 bug） |
| **新增原生** | 无（自研桥） | `libSDL3.so` + `libshaderc.so` + `libspirv-cross.so`（+ jar `lwjgl-sdl/vma/spvc/shaderc`） |
| **问题类型** | 许可/血统/契约独立实现；首次平台桥（EGL/输入环/尺寸 upcall） | 整包库移植；**平台行为取证**（screenHeight、事件顺序、指针同一性） |
| **验证** | 实机 1.21.10 画面/输入/resize/关窗回归；digest + 供应链 | 同（26.3-rc-1 逐项实机）；另加**反汇编**定位 + **两点测量**定映射 |
| **副作用教训** | `GLCapabilities` 全量加载 → 启动期 200+ "entry point missing"（无害） | 关 filter → **采样率 0**（副作用） |

---

## 三、异同总结

**相同**
1. **同一架构哲学**：无论 GLFW 还是 SDL，都把窗口/GL/输入**桥接到我们自己的 `meow_environ` + OHNativeWindow/EGL + SPSC 输入环**——平台绑定是可替换的外壳，内部链不变。
2. **精确钉版 + 构建期断言 + 实机回归**：两代都靠"钉上游修订（Maven/`.git`）+ 符号/DT_NEEDED 断言 + 逐项实机"。
3. **平台边界自研可控**：GLFW 用净室 overlay+桥；SDL 用自研 `ohos` 驱动——两者都是"我们拥有的边界层"。
4. **平台怪癖反复出现**：窗口**顶栏高度**、F 行媒体键、尺寸空间……名字不同、本质同类。

**不同**
1. **去库 vs 引库**：GLFW 那次是**替换/清除**上游绑定（许可与血统驱动）；SDL 这次是**新引入**整包上游（功能换代驱动）。
2. **边界实现相反**：GLFW **不引真 GLFW**（我们提供 `glfw*`）；SDL **引真 SDL3**（我们只加一个驱动）。
3. **尺寸/坐标来源**：GLFW 有 `internalWindowSizeChanged` 主动推；SDL 没有，只能靠**启动尺寸 + 事件**——这正是 26.3 鼠标偏移的根。
4. **工作量形状**：GLFW ≈ 供给链净室 + 首次平台桥；SDL ≈ **整包移植 + 新后端 + 大量行为取证**（反汇编/实测）。

---

## 四、方法论教训（与项目铁律呼应）

1. **禁"解决不了就解决环境"**：我一度提议**砍掉窗口顶栏**，被明确纠正——顶栏/窗口模式必须保留；真因在 **MC 的 screenHeight 取值**，不在窗口形态。
2. **先取证再动手**（`meowcraft_measure_before_hack_fix`）：两数据点（+20@y260 / +40@y455）把"常量 or 缩放"**定死**；反汇编 `GlBackend`/`Window`/`MouseHandler` 定位 `getScaledYPos/getScreenHeight`。
3. **表面修复会被识破**：常量 56 / 改 hover 源 / 关 filter 都治标，且**副作用**（采样率 0）暴露了它。
4. **静态可查的先查，实机的后验**：ABI/符号/反汇编先行；设备不可得时（用户离开）只做**理论研究**（3 份报告）。

---

## 五、现状与产物

- **版本支持窗口**：**MC 1.6.x – 26.3**（2026-09-11 实测 26.3 可玩；下界经 legacy LWJGL2 + gl4es 下延，见 [`../lwjgl/LWJGL2-legacy适配-复盘.md`](../lwjgl/LWJGL2-legacy适配-复盘.md)）。见 [`../../00-current/版本支持边界.md`](../../00-current/版本支持边界.md)。
- **新增随包**：`libSDL3.so`（fork 3.4.14）、`libshaderc.so`、`libspirv-cross.so`（`libs/meowlwjgls/libs/arm64-v8a/`，manifest tag `common`）；jar 增 `org.lwjgl.sdl`（+ `lwjgl-vma/spvc/shaderc`）。
- **工具**：`tools/sdl/`（伪装工具链 + 补丁器 + 构建脚本 + `src/video/ohos` 驱动）、`tools/shaderc/`；`tools/lwjgl/install_natives.sh --sdl/--native`。
- **研究报告**：`stuffs/research/sdl/reports/{text-input-mc263,mouse-grab-mc263,sdl-ohos-driver-contract,vulkan-mc263}.md`。
- **记忆**：`meowcraft_mc_26_3_sdl_switch`、`meowcraft_26_3_input_producer_gate`、`meowcraft_26_3_input_coords_solved`、`meowcraft_26_3_text_grab_rootcause`。

## 六、回归审查（2026-09-11，子 agent 全面 code review）

针对本次 26.3 全部改动做了一次全面 review（报告 `stuffs/research/code-review-26.3.md`），重点排查**对旧架构（GLFW ≤26.2）与其他部分的兼容**。

### 已修（确定性安全项）
- **启动兜底**：`GameWindow` 等首个 `onSurfaceChanged` 拿真实客户区尺寸再启动；新增 **1.5s 超时兜底**（`LAUNCH_FALLBACK_MS`）避免回调不来时"永不启动"。
- **ABI 断言**：`meowcraftbridge_environ.c` 为新 `fs*` 字段补 `offsetof` 断言（size 断言已有）。
- **清理**：删死代码（`GameInputController.sendChar/sendCharMods`、未用 import、`GameWindow.fsActive`）；SDL 驱动临时 `fprintf` 探针全清；SDL README 摘要同步。

### 甄别为"非本次回归 / 需实机回归"
- **既有（26.2 已验，不动）**：`-Dorg.lwjgl.vulkan.libname=…no-vulkan`、`JLI_Launch` 后 `_exit()`、滚轮归一化。
- **潜在**：`lwjgl-vma` 类随包但无 `liblwjgl_vma.so`（仅 VMA/Vulkan 路径触及；GL 路径不碰）。
- **实机已可用、可后续加固**：全屏读-清竞态 / 多窗共享请求通道。
- **文本单源（已收敛）**：为修 26.3 双发而删 `handleKey` 的 char → 文本改为"**仅 IME onChange**"单源；
  后续 legacy 战役（[`../lwjgl/LWJGL2自编-方案.md`](../lwjgl/LWJGL2自编-方案.md) §6.2）确认整链契约为"物理键只发 KEY + 字符只经隐形 IME"，
  ≤26.2 / legacy 聊天打字正常；若仍有个案，按"版本/路径条件化"处理（仅 SDL 路径抑制）。

### 结论
- **SDL 26.3**：✅ 兼容（实机验证：画面 / 键鼠 / 转视角 / 文本 / **全屏**）。
- **GLFW ≤26.2**：✅ 实机可玩（2026-09-11 实测：1.16.5 / 1.21.10 / 26.2 全通过；启动 / 聊天 / 全屏 / 滚轮 / 关窗，见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 关键定论第 8 条）。

---

## 七、Vulkan 接通（2026-09-19）

**结论**：MC 26.3 的「渲染后端 = Vulkan」**已实机可用**（**2026-09-19** 用户实测进世界成功，默认地形 **70–80 FPS**）。缺口**不在** loader shim（一直生效），而在**我方 SDL `ohos` 驱动的 Vulkan vtable**。

| 项 | 内容 |
|---|---|
| 现象 | MC 抛 `BackendCreationException: Vulkan is not supported: No dynamic Vulkan support in current SDL video driver (ohos)`（`renderpearl.backend.vulkan.VulkanBackend.loadLibrary`），随后**内部回退 GL**（日志转出现 Zink 告警） |
| 根因 | `ref/SDL-3.4.14/src/video/SDL_video.c:6261`：`SDL_Vulkan_LoadLibrary()` 见 `_this->Vulkan_LoadLibrary == NULL` ⇒ `SDL_DllNotSupported("Vulkan")`，其文案与观测**逐字一致**。构建侧无问题（`SDL_VULKAN=ON`、8 个 `SDL_Vulkan_*` 早已导出）—— 与 §一#5/§一#14 同属"驱动没挂 vtable ⇒ MC 侧报不支持" |
| 解 | 新增 `tools/sdl/src/video/ohos/SDL_ohosvulkan.{c,h}`（`Vulkan_LoadLibrary/UnloadLibrary/GetInstanceExtensions/CreateSurface/DestroySurface`）+ `SDL_ohosvideo.c` 的 `OHOS_CreateDevice()` 内 `#ifdef SDL_VIDEO_VULKAN` 挂载；OHOS WSI **本地声明**（`VK_OHOS_surface` / sType `1000685000` —— 与上游后加的 `vulkan_ohos.h`、桥 `egl_gl.c` 既有硬编码**三处同值**） |
| loader | 顺序 = 调用方 `path` → `SDL_HINT_VULKAN_LIBRARY`（`SDL_GetHint` 会**回落环境变量** ⇒ `SDL_VULKAN_LIBRARY=libmeowvulkan.so` 可零重编切 shim）→ 系统 loader。**实测 MC 传的是 shim 的绝对路径**（`…/meowjre/libs/arm64/libmeowvulkan.so`，`source=application`）⇒ 与 GL 同一套"**指针同一性**"约定，系统 loader 分支实为兜底 |
| hook 取舍 | `SDL_Vulkan_GetVkGetInstanceProcAddr` **无 vtable 入口**（返回驱动存进 `vulkan_config` 的指针）；`Vulkan_GetPresentationSupport` **有意不挂** ⇒ SDL 报"恒支持"（与 GLFW 桥 `glfwGetPhysicalDevicePresentationSupport` 恒 1 同简化） |
| 窗口策略 | **已定案（2026-09-19）：SDL 路径不调桥**（驱动自足）—— 原设计在建面前调桥的 `meowVkPrepareSurfaceWindow()`（几何 pin + usage/format），**实测该调用因裸名 `dlopen` 解析不到而静默跳过、功能照常**（1 次 swapchain、70–80 FPS），且桥/ArkTS 已在发布 surface id 时设好几何与 format ⇒ 不再引入跨库耦合（也消除一个"静默降级"点）；桥侧函数随之收为**本地 static helper**（仅 GLFW 路径使用） |
| 产物契约 | `libSDL3.so` 2,050,560 B（**sha 见表** [`../../30-supply-chain/assets-digests.txt`](../../30-supply-chain/assets-digests.txt)）；**同一源码状态下 3× 从头重建逐字节一致**（本役共 3 轮 9 次；每轮重取 pristine worktree + 清 build 目录，patcher 每轮真跑）；1270 个 `SDL_*` 动态符号；`DT_NEEDED` 仅 `libnative_window.so libc.so` |
| 性能口径 | **跨版本观察**（26.3 `renderpearl` vs 26.2 旧栈），**非受控 A/B** ⇒ **不改写** 26.2 的根因结论（[`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) §D、F87–F102 收官结论不受本役影响） |

**两条平台适配事实（本役踩出，写死）**
1. **`SDL_Log*` 在本平台不可见**：SDL 核心与我方驱动**连 `WARN` 都进不了 hilog**、游戏目录也无落盘日志（应用侧把 SDL 日志截住）⇒ 我方驱动自证**以 stderr 为主**（启动器转发游戏进程 stderr ⇒ 导出 `.logs` 里表现为 `[jre_stderr] MeowSDL: …`，且**无缓冲不会丢**）、**hilog 为尽力副本**（`dlopen("libhilog_ndk.z.so")` 运行时解析；**不链接** —— 链接会加 `DT_NEEDED` 并触发通用构建脚本 `build_sdl_meow.sh` 的依赖白名单守卫）。组串用普通 printf、递 hilog 用 `"%{public}s"`，否则字段会被抹成 `<private>`。
2. **`patch_sdl_ohos.py` 是 check-then-insert（只增不删）**：撤销其中某项改动**无效**（已打过的树里仍在，patcher 下次只说"already present"）；正确做法 = `git -C ref/SDL-3.4.14 checkout -- .` 重置后让 patcher 重打。

**装包注意**：HSP 里是 hvigor **剥符号后**的副本 ⇒ sha 必与产物不同；判据 = 包内**仍含新代码字符串**（本次核对通过）。

**证据**：工作区根 `stuffs/research/sdl/reports/vulkan-mc263.md`；上游官方 OHOS 端口（**只在 `main`、未进任何 3.4.x 发布** ⇒ 只能看/择取，不能整体换版）存 `stuffs/research/sdl/upstream-openharmony/`。
