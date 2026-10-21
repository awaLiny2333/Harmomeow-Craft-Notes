> 已归档（2026-09-15）：本文是 LWJGL 单代 jar+3 so 的**阶段1历史快照**；现行见 `20-design/lwjgl/LWJGL3世代管理-方案.md`。

# lwjgl.jar + LWJGL 原生三件套 自编方案

> 状态：**阶段1 ✅ 完成**（2026-09-10，实机 1.21.10 出画面）——工具已建、native/jar 自编、drop-in 成功。四路 agent 回执：
> `stuffs/research/lwjgl/REPRODUCE_CONTRACT_lwjgl_jar.md`（jar 契约）、
> `stuffs/research/lwjgl/LWJGL_NATIVES_OHOS_FEASIBILITY.md`（so 可行性）。
> 目标：把 Java 侧最后一个半黑箱 `lwjgl.jar` 及伴生 3 so 收编为源码级，并升到 LWJGL 3.4.1（解锁 MC ≥1.22）。

> ⚠️ **阶段史（2026-09-10 之后）**：本文记录 **阶段1（LWJGL 单代 3.3.3）** 的调研、方案与产物快照。
> 后续曾落地 **两代并存（3.3.3 + 3.4.3）+ natives 统一后缀（`_333`/`_343`；当时后缀式，2026-09-14 改为世代号紧跟基名）**；**2026-09-14 又收敛为现代单代 3.4.3**
> （`lwjgl-3.3.3.jar` 与 `_333` 三 so 移除，1.13.2–1.21.11 缺失成员由 overlay-3.4.3 的 5 个兼容 shim 补齐），
> 且 HAR 模块 `meowlwjgl3` **已改名 `meowlwjgls`**。故本文中
> `liblwjgl{,_opengl,_stb}.so`（无后缀）/"3 个 native"/单 `lwjgl.jar`/"4075 类"/digest v14 等命名与数字
> **均为阶段1 历史值**。现行方案见 [`../20-design/lwjgl/LWJGL3世代管理-方案.md`](../20-design/lwjgl/LWJGL3世代管理-方案.md) §7；
> 现行资产值见 [`../30-supply-chain/assets-digests.txt`](../30-supply-chain/assets-digests.txt)（v25）。

## 0. 速览

1. **"三个 so"** = `liblwjgl.so`(core) + `liblwjgl_opengl.so` + `liblwjgl_stb.so`；**GLFW native 不存在也无需**——`nglfwXXX` 全由自研 `libmeowcraftbridge.so` 覆盖。
2. **jar**：上游 **stock 预编译 jar（默认 Maven release 3.3.3）** + **自研净室 overlay** 覆盖 19 个改写类 → 确定性合并，**与 launcher.jar 同款路线**（javac 只编 overlay，无需 Gradle/kotlinc）。**stock 类我们没编**，详见 §9。早期曾以 Amethyst 打包的 `3.3.3-snapshot` 作 base/overlay 参照，现无该依赖。
3. **so**：`ref/lwjgl3` 的 `modules/{core,opengl,stb}` 用 OHOS clang 交叉编译（上游无 CMake，是 Ant+GCC，照搬其命令）。core 需先交叉编 `libffi.a`。
4. **双版本并存（阶段1 时设想）**：3.3.3（MC 1.17–1.21.x）与 3.4.1（MC ≥1.22）各一套，按 MC 版本选（此思路早期参考 Amethyst）。**后续实际收敛为现代单代 3.4.3**（见文首阶段史）。

## 1. 坐标

| 对象 | 位置 |
|---|---|
| 随包 jar | `Harmomeow-Craft-Launcher/entry/.../rawfile/meowcraft_extras.tar.gz` → `lwjgl.jar`（4075 类 fat 合并，基 Maven 3.3.3） |
| 三个 so | `Harmomeow-Craft-Launcher/libs/meowlwjgls/libs/arm64-v8a/`（伴已自编 `libopenal.so`/`libfreetype.so`） |
| 上游源码 | `ref/lwjgl3`（⚠ HEAD=`3.4.3-12`=3.5.0 dev；要 3.4.1 须 `git checkout 3.4.1`） |
| Android overlay 早期参照 | `ref/Amethyst-Android/jre_lwjgl3glfw/{lwjgl-3.3.3,lwjgl-3.4.1}/src/main/java`（仅工作区外部参照，不入仓库、不随包） |
| iOS javac 早期模板 | `ref/PojavLauncher_iOS/JavaApp/{Makefile,src/lwjgl}`（仅工作区外部参照，不入仓库、不随包） |
| 官方 java jar（本地） | `stuffs/.minecraft/libraries/org/lwjgl/*/{3.3.3,3.4.1}/` |
| lib 名补丁 | `Harmomeow-Craft-Launcher/tools/patch_pojav_libname.py` — **已删除**（净室 overlay 直接写死 `libmeowcraftbridge.so`，无需二进制补丁） |

## 2. 关键发现

### 2.1 上游构建真相
- **Gradle 不产 jar**（只 publish）；真构建是 **Ant**。生成的 Java(6548)/C(19) **已入库** → 生成器/kotlinc **可绕过** → **javac-only 成立**（无注解处理）。
- ⚠ 版本陷阱：当前 checkout 是开发版（GLFW 绑定 3.5.1），必须 checkout tag `3.4.1`。

### 2.2 覆盖式配方（早期参照 Pojav 系）
- `libs/` 放**未改**官方 jar，`src/` 只放 ~18–20 个**改写文件**（现为自研净室 overlay），打包时 merge 覆盖。
- 改写集：`glfw/GLFW.java`（整文件重写，native 面改 `meow*` 函数表）、`glfw/{CallbackBridge,Callbacks,GLFWWindowProperties}.java`、`opengl/GLCapabilities.java`（插 `RendererInit.onCreateCapabilities`）、`opengl/RendererInit.java`、`glfw/GLFWNative*.java`（打桩抛异常）、`android/util/*`（AOSP 纯 Java vendor 5 个，现改用 `java.util.HashMap` 后已甩掉）。
- iOS `Makefile` 曾被用作最干净的 javac 打包模板：extract 官方 jar → 覆盖编译类 → 删 `META-INF` → rejar。
- ⚠ **GLCapabilities 版本雷**：早期 Amethyst 件用 **3.3.0 时代**文件，缺 3.3.2/3.4.1 新增 12 个扩展函数 → 我们应取**目标版本官方**该文件再只打 2 处编辑（插 hook + 可选非短路 `&`）。
- ⚠ **SDL**：3.4.1 overlay 引入 `org.lwjgl.sdl.*`，需 `libSDL3.so`（OHOS 无）；除非目标 MC 走 SDL 后端，否则丢弃/打桩。

### 2.3 收编前现装 jar 契约（历史实证）
- 版本 **3.3.3**（Manifest 无 `Implementation-Version` → 运行时报 `3.3.3-snapshot`，属重打包假象）。
- **4346 类**全 `org/lwjgl/**` fat 合并：core + vulkan(2754) + opengl(519) + util(406) + system(322) + glfw(106) + openal/stb/nanovg + **LWJGLX(LWJGL2)**。
- 其中 **12 个 Java17(major 61)** = Pojav patch 集。与 pristine HOML 件（历史外部件）只差 `GLFW.class`（我们的 lib 名补丁）。
- HOML-only delta（历史）：`org.lwjgl.opengl.RendererInit`（=早期 Amethyst `PojavRendererInit` 改名，gl4es 检测）。
- **契约**：12 GLFW natives + 7 CallbackBridge natives + 11 `meow*` + 12 Java17 类。

### 2.4 三个 so（实证）
| so | 大小 | sha256 | 映射 | 导出 | NEEDED |
|---|---|---|---|---|---|
| liblwjgl.so | 447424 | `541092c3…` | core | 1961 `Java_org_lwjgl_*`+`JNI_OnLoad` | libc.so |
| liblwjgl_opengl.so | 289768 | `28d29507…` | opengl | 2228 | libc.so |
| liblwjgl_stb.so | 323504 | `44466573…` | stb | 215 | libc.so |

- 三者都必须重建（官方 glibc 与 Android bionic 均不可加载）；**不要**建 `liblwjgl_glfw.so`。
- 源：`ref/lwjgl3` `modules/{core,opengl,stb}`；opengl/stb 无后端依赖（易）；core 需 `libffi.a`+`jni.h`+Linux syscall 移植。
- 配方：复用 OHOS native clang/sysroot，`-D__MUSL__ -DLWJGL_LINUX -DLWJGL_arm64`，`-Wl,--no-undefined -Wl,--version-script,config/linux/version.script`；显式 version script 无 OpenAL 零导出 bug，但保留导出数断言。

## 3. 推荐方案（分阶段）

**阶段 1 — 3.3.3 复现（先证管线，零版本风险）**
- 用官方 3.3.3 jar + Amethyst 3.3.3 overlay 走通 overlay 合并/patch/确定性打包 → 产出 jar，**与现装 jar 逐字节对齐验证**（同 launcher.jar 方法论）。
- 同步重建 3 个 so（3.3.3 源），drop-in 替换现装件 → 实机回归 1.21.10。

**阶段 2 — 升 3.4.1（解锁 ≥1.22）**
- jar：官方 3.4.1 jar + Amethyst 3.4.1 overlay（注意 GLCapabilities 取官方 3.4.1 重打、SDL 取舍）。
- so：`ref/lwjgl3` checkout `3.4.1` 重建 core/opengl/stb。
- 双版本：按 MC 版本在启动期选 3.3.3/3.4.1 一套（classpath + native 目录）。

**工具落点 `tools/lwjgl/`**（仿 `tools/launcher/`、`tools/openal/`、`tools/freetype/`）：
- `build_lwjgl_jar.sh`：extract 官方 jar + overlay + javac（**用户跑**）+ 确定性 pack（`patch_pojav_libname.py` **已删除**——净室 overlay 直接写死 `libmeowcraftbridge.so`，无需 libname 补丁）。
- `build_lwjgl_natives.sh`：OHOS clang 编 core/opengl/stb（+ 先编 `libffi.a`）。
- `deltas/`：overlay 源 + 补丁；[`README.md`](README.md)。

## 4. 不可协商契约（重建后必须满足）

- jar：`org/lwjgl/glfw/GLFW` 的 12 native 符号名（`nglfwSet{Char,CharMods,CursorEnter,CursorPos,Key,MouseButton,Scroll}Callback`、`nglfwSetShowingWindow`、`nglfwGetCursorPos(A)`、`nativeInitializeGLFWNativeBridge`、`internalGetGamepadDataPointer`）+ 7 `CallbackBridge` natives + 11 dlsym `meow*` + 12 Java17 类。
- loadLibrary：`meowcraftbridge` / `libmeowcraftbridge.so`（净室 overlay 源码写死；`patch_pojav_libname.py` **已删除**）。
- `libmeowcraftbridge.so` 必须仍在同 ABI 下导出上述 `Java_org_lwjgl_*` 符号。

## 5. 风险 / 开放问题

1. **GLCapabilities 版本来源**（按目标版本官方重打 vs 沿用 Amethyst 3.3.0 子集）——影响扩展/模组兼容。
2. **SDL 后端**：目标 MC 是否走 SDL 窗口路径？是则 `libSDL3.so` 进关键路径。
3. **libffi 交叉编译**（core 硬依赖）：本机首次为 OHOS 编 `libffi.a`。
4. **core 的 Linux-only 调用**在 OHOS musl 覆盖度（syscall/affinity/madvise 等）。
5. **`RendererInit`（原 `PojavRendererInit`）gl4es 谓词**（`endsWith("libng_gl4es.so")`）对 OHOS 渲染器（`libGLv4.so`）需改判。
6. **无 JVM**：agent 不能跑 javac/验证；编译与实机回归由用户执行。

## 6. 验收标准

- 阶段 1：自编 jar 与现装 `lwjgl.jar` 逐字节一致（或差异仅可解释）；3 个 so drop-in 后 1.21.10 正常。
- 阶段 2：产物在 MC 1.22+ 正常启动渲染；供应链把 jar+3so 从"半可控"升**源码级**并入 digest。

## 7. 参考

- `../40-adaptation/launcher-rebuild.md`（同款管线先例）
- `stuffs/research/lwjgl/REPRODUCE_CONTRACT_lwjgl_jar.md`、`LWJGL_NATIVES_OHOS_FEASIBILITY.md`
- `../30-supply-chain/provenance-master.md`、`../00-current/收编自研路线与交接.md`

## 8. 实现进度（阶段1）

- [x] 工具集 `Harmomeow-Craft-Launcher/tools/lwjgl/`（commit `fd8934b`）：`build_lwjgl_jar.sh` / `finalize_for_meowcraft.sh` / `build_lwjgl_natives.sh` / `rebuild_for_meowcraft.sh` + README。
- [x] **native 三件已建成**（`stuffs/research/lwjgl_natives/out/`，导出面与现装件精确一致）：

| so | 现装 sha | 自编 sha | 导出 | NEEDED |
|---|---|---|---|---|
| liblwjgl.so(core) | `541092c3…` | `0b1dc8ae…` | 1961 | libc.so |
| liblwjgl_opengl.so | `28d29507…` | `4541eeb3…` | 2228 | libc.so |
| liblwjgl_stb.so | `44466573…` | `a8d2392d…` | 215 | libc.so |

  尺寸差 1–5%（上游用 LTO，我们未开）。libffi：`ref/lwjgl3` 只带头文件，实取自 `stuffs/research/jna/jna_src/native/libffi`（3.4.4）直编 aarch64 8 个 TU。
- [x] jar 管线**干跑到 javac 前通过**：staging 正确（19 overlay 源 / 13 CP jar；`PojavRendererInit`→`RendererInit` 改名生效）；本机 shell 无可用 JVM → 优雅 `exit 3`。
- [x] 用户跑 javac 产 `lwjgl.jar`（`6aec4f87…`）→ **对账 pristine 类集：我方 ⊇ 旧 HOML 件（历史外部件）的 4346 类（仅多 1 个无害 `GLFWVulkan$Functions`）**。
- [x] drop-in 换 jar+3so → **实机 1.21.10 出画面**。
- [x] digest v12 入库 + 供应链升级（jar+3so → 源码级）。

### 8.1 暴露的 HOML↔Amethyst 契约差（本次踩坑，后人必读）

早期我们的 `libmeowcraftbridge.so` 是按 **HOML jar 的 GLFW stub 契约**实现的，而当时自编 jar 用的是**原版 Amethyst stub**（均历史外部参照，现桥与 overlay 已净室重写）——两者在多处接口不同，逐一暴露并修好：

1. **缺 native → 静默死在 GLFW 初始化**（无 Java 异常、无 cppcrash，日志停在 `Loaded …libmeowcraftbridge.so`）。
   Amethyst stub 的 `glfwInit()` 会调 `GLFW.internalGetGamepadDataPointer()` + `CallbackBridge.nativeCreateGamepad{Axis,Button}Buffer()`，桥里没有 → 启动即失败。
   **修**：桥补 7 个 gamepad/DPI/notify native（`input_bridge.c`，40B 静态 `gamepadState` 缓冲）。
2. **`AMETHYST_RENDERER` 未设 → `glfwCreateWindow` NPE**（`"<local13>".equals(...)`）。
   Amethyst stub 读 `System.getenv("AMETHYST_RENDERER")` 后直接 `.equals`；我们只设了 `MEOWCRAFT_RENDERER`。
   **修**：`meowjrebridge.cpp` 并列 `setenv("AMETHYST_RENDERER", rendererEnv)`。
3. **`internalWindowSizeChanged` 签名不符 → 黑屏**（音频正常）。
   桥缓存 `(JII)V`（HOML），Amethyst 是 `(J)V` → 缓存失败 → surface resize 不通知 MC → framebuffer 尺寸不更新。
   **修**：桥双签名兼容（回退 `(J)V` 时先把尺寸写进 stub 的 `public static int mGLFWWindowWidth/Height`）。

> 结论：**自编 jar 的 Java stub 与自研桥是"配套对"**，换 stub 必须同步核对 native 面 + 方法签名 + env 约定。判据：`m3:`/`JNI`/`GetStaticMethodID` 类日志 + 真崩溃（无 cppcrash）。

## 9. 自编边界：stock base / overlay / native（2026-09-10 补）

`lwjgl.jar` **并非"全部从源码编译"**，而是三层拼装：

| 层 | 谁做的 | 说明 |
|---|---|---|
| **stock base** = 12 个模块 jar（`--official`，早期默认 `ref/Amethyst-Android/jre_lwjgl3glfw/lwjgl-3.3.3/libs/lwjgl-3.3.3`；现默认 Maven release 3.3.3，见下） | **上游 LWJGL 预编译件（非我们）** | manifest = `Specification-Version: 3.3.3-snapshot`（Ant 1.10.14 / Adoptium JDK 21）；早期用 `3.3.3-snapshot` 而非 Maven release `3.3.3`，与 `.minecraft` 的 release jar **不逐字节相同**。我们只解包+重打包。 |
| **overlay** = 19 个改写源（现为自研净室 `tools/lwjgl/deltas/overlay`；早期取自 Amethyst `.../lwjgl-3.3.3/src/main/java`） | **我们 javac 编译** | GLFW stub/`RendererInit` 等净室重写；合并时同名覆盖 stock。 |
| **合并 / 确定性打包** | 我们 | `pack_jar.py`（`patch_pojav_libname.py` **已删除**：净室 overlay 直接写死 `libmeowcraftbridge.so`）。 |
| **3 个 native** `liblwjgl{,_opengl,_stb}.so` | **我们从源码编** | `build_lwjgl_natives.sh`，源 `ref/lwjgl3@3.3.3`。 |

- 所以"源码级" = **overlay + 合并管线 + native**；jar 内绝大多数 stock 类是**上游预编译件**。
- 这也是游戏运行时报 `3.3.3-snapshot+SNAPSHOT` 的原因（嵌入的 MANIFEST 取自 stock core jar）。
- **已实现"缺则下载"**（2026-09-10，同 `tools/meow-launcher`/`tools/oshi` 模式）：`build_lwjgl_jar.sh` 默认从 **Maven Central 拉 release 3.3.3** 的 11 个模块（`.sha1` 校验）作 stock base。**`lwjgl-lwjglx` 默认剔除**（164 类 LWJGL2 兼容层，非 Maven 件）：扫 MC 1.21.10 + 全部 MC 库 + launcher.jar/gson **259 个 jar** + overlay 源，对其独有 **163 类的引用 = 0** → MC≥1.17 死代码。`--with-lwjglx` 可回退包含。`--offline --official <dir>` = 纯本地/snapshot 构建。
- **已完成（2026-09-10，实机出画面）**：**8 模块** jar（Maven release 3.3.3 base；**剔 lwjglx + nanovg/vma/shaderc**；4075 类）已替换入 tar；digest **v14**，tar `67548a7e…`，jar（补丁后）`30f36f25…`；游戏版本串 `3.3.3`。
- **可再瘦（唯余）**：`vulkan`（2755 类/6MB，最大块）——仅 8 处引用（core 配置串 + `GLFWVulkan` 链接），vanilla 不调；剔除风险小但非零。

**复现契约关键点**：消费的 `lwjgl.jar` = Maven release 3.3.3 的 8 模块（早期为 12 模块快照）fat 合并 + **自研净室 overlay**；`android/util` 不再随附；overlay 唯一 OHOS 改动 = `PojavRendererInit`→`RendererInit`（对齐自研桥 `input_bridge.c` 的 JNI 符号名）。

## 10. overlay 机制速览（2026-09-10；完整版见 `Harmomeow-Craft-Launcher/tools/lwjgl/README.md` §1）

> 一句话：jar = 官方 Maven 模块 class + **我们的 overlay class 覆盖同名官方类**。为什么要覆盖——官方
> `org.lwjgl.glfw.GLFW` 是薄 JNI 绑定，会去加载**真正的原生 GLFW**；我们没有原生 GLFW，只有自研桥
> `libmeowcraftbridge.so`（GLFW 语义用鸿蒙 API 实现）。故 GLFW 相关类**整类替换**；`GLCapabilities`/`RendererInit`
> 也让 GL 上下文/函数槽位装载走我们的路径。其余 `org.lwjgl.*` 直接用官方件。

**流水线（5 步，两条规则）**

```
① stage   --overlay 目录按顺序 cp 进 scratch overlay/     ← 规则A：后者覆盖前者（公共 → 代）
② javac   编译 scratch overlay/*.java（cp = 官方 8 模块 + jsr305 + jspecify）
③ merge   官方模块 class 解压进 merge/，再把 overlay 的 **org/** class 最后拷入 ← 规则B：overlay 胜出
          （并删 META-INF / net/java/openjdk/cacio / android）
④ pack    确定性打包（固定 mtime + 排序）→ lwjgl-<ver>.jar
⑤ sanity  必备类在 / 无 android/util / GLFW 载库名 == meowcraftbridge
```

**两层（判据：该文件是否与 LWJGL 版本钉死）**

| 层 | 目录 | n | 内容 | 为何 |
|---|---|---|---|---|
| 公共 | `deltas/overlay/` | 13 | `glfw/{CallbackBridge,Callbacks,GLFWWindowProperties,GLFWNative*}`、`opengl/RendererInit`、`system/MeowBundledNameMapper` | 版本无关（转发桥 / 反射 / 平台桩）→ 每代共用 |
| 每代 | `deltas/overlay-3.3.3/`、`deltas/overlay-3.4.3/` | 各 2 | `opengl/GLCapabilities.java`（C 侧 `tlsGetFunction(index)` **槽位契约**：3.3.3=2228 / 3.4.3=2270，由 `gen_glcap.py` 生成）、`glfw/GLFW.java`（MC 链接的 GLFW 公共 API 面） | 版本钉死 |

- **构建期守卫**：`--version <v>` 而 `deltas/overlay-<v>` 存在却没传 → `build_lwjgl_jar.sh` **报错**（防漏传/串代）。
- **加一代**：见 README §1.4 —— `deltas/overlay-<newver>/` 放那两个文件（caps 用 `gen_glcap.py` 生成）
  + 构建传两次 `--overlay` + `rebuild_for_meowcraft.sh <newver>`（natives）+ `pack_extras.py --jar/--require`
  + ArkTS `LWJGL_GEN_TABLE` 加一行（门槛 = 该代 lwjgl 版本）。
