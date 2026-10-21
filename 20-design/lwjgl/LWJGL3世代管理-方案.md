# LWJGL 世代管理方案（现役：现代单代 3.4.3）

> 状态（现行口径，2026-09-14 起）：现代 LWJGL 已由「两代并存」**收敛为单代 3.4.3** ——
> MC **1.13–1.21.x 与 ≥1.22 / 26.x 均走 `lwjgl-3.4.3.jar`**；旧 `lwjgl-3.3.3.jar` 与 `_333` 三 so
> **已于 2026-09-14 退役移除**，1.13.2–1.21.11 的缺失成员（共 5 个）由 **overlay-3.4.3 的 3.4.x 兼容 shim** 补齐，
> 工具新增成员级校验器 `tools/lwjgl/mc_lwjgl_compat_check.py`；HAR 模块 `meowlwjgl3` **已改名 `meowlwjgls`**。
> 事实源：[`../../00-current/现状基线.md`](../../00-current/现状基线.md) §1 / §5 关键定论第 9 条。**2026-09-10 的"两代并存"设计已降为历史**，见 §6；
> 当初的两代→单代收敛依据（成员级判据 + 未知点清零 + 全链 review）已并入本文 §3，原始档 [`../../90-archive/LWJGL3单代收敛-决策依据.md`](../../90-archive/LWJGL3单代收敛-决策依据.md)。
>
> 边界：本文只覆盖**现代 LWJGL3 单代**。随包另有 **legacy LWJGL2 `liblwjgl.so`**（无后缀，服务 MC 1.6.x–1.12.2，
> 见 [`LWJGL2自编-方案.md`](LWJGL2自编-方案.md)）与 **SDL3 `libSDL3.so`**（无后缀，tag `common`，服务 ≥26.3，
> 见 [`SDL3桥接-设计.md`](../render/SDL3桥接-设计.md)）——与 `liblwjgl_343{,_opengl,_stb}.so` 命名正交。
> 总支持窗口 **1.6.x–26.3**（[`../../00-current/版本支持边界.md`](../../00-current/版本支持边界.md)）。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 9 条](../../00-current/现状基线.md)。

## 0. 现役：单代 3.4.3（关键事实）

| 项 | 现行值 |
|---|---|
| 世代 | **仅 `3.4.3`**（服务 1.13–1.21.x 与 ≥1.22 / 26.x） |
| jar | **`lwjgl-3.4.3.jar` 单 jar**（`lwjgl-3.3.3.jar` 已移除） |
| 世代表 | `LWJGL_GEN_TABLE` **单行**（就近归并，不再硬失败） |
| jar 表 | `LWJGL_GEN_JARS` **单 jar**；`LWJGL_GEN_333` 已删除 |
| 令牌 | `EXTRAS_VERSION`（换 tar 内容必递增，见 §4） |
| natives | **世代号紧跟基名**：`liblwjgl_343{,_opengl,_stb}.so`（同处扁平目录） |
| 兼容面 | overlay-3.4.3 的 **5 个 3.4.x 兼容 shim**（§3） |
| 工具 | `tools/lwjgl/`：`build_lwjgl_jar.sh` / `build_lwjgl_natives.sh` / `gen_glcap.py` / `build_libffi.sh` / `install_natives.sh` / `pack_extras.py` / `mc_lwjgl_compat_check.py` |

- **不再"按版本选代"**：`MinecraftLauncher.lwjglGeneration(jsonPath)` 仍解析版本 json 的
  `org.lwjgl:lwjgl:<ver>`，但 `LWJGL_GEN_TABLE` 只剩一行 → 所有现代版本**就近归并到 3.4.3**。
- `ClasspathStager` 平铺版本 jar 到 `cacheDir/mc-cp/<key>-<id>/`；**现行单代：不用选代、也不用删另一代 jar**。

## 1. 单代机制

### 1.1 三个天然挂点
1. **jar 选择**：`ClasspathStager` 本就把运行 jar 平铺到**每版本一个目录** `cacheDir/mc-cp/<key>-<id>/`，
   `-cp "<dir>/*"` 只吃这一个目录 → 天然按版本隔离。现行该目录里只有一份 `lwjgl-3.4.3.jar`。
2. **native 选择**：⛔ 初版设想（tar 解到数据区 + `org.lwjgl.librarypath` 多目录）**不可行**——
   平台禁止 dlopen 运行时写入数据区的文件（无 fs-verity 签名）；且 hvigor 只打包 `libs/<abi>/` 顶层 `.so`（子目录丢弃）。
   **改为同目录世代号紧跟基名 + LWJGL 官方 `bundledLibrary.nameMapper` 钩子**：所有世代都用
   `liblwjgl_<gen>{,_opengl,_stb}.so`（现仅 `_343`），同处随包（已签名）目录，启动时按世代改名加载。
3. **兼容面收敛（取代"版本→代映射"）**：`mc_lwjgl_compat_check.py` 对每个现代 MC 版做**成员级（含继承解析）**
   校验——以 3.3.3 为对照，3.4.3 相对 1.13.2–1.21.11 **只缺 5 个成员**（§3），补齐即等价 → 单代无需旧代，
   未来新版本也**免改代码**（缺什么补什么，校验器定位）。

### 1.2 改动清单
| 层 | 现行改动 |
|---|---|
| 随包 bundle（`meowcraft_extras.tar.gz`） | **单 jar** `lwjgl-3.4.3.jar` + 单套 natives `liblwjgl_343{,_opengl,_stb}.so`；`pack_extras.py` 丢弃 base tar 里所有 `lwjgl*.jar`（防退役世代残留） |
| `ClasspathStager.ets` | 平铺 jars + natives；**单代无需选代**（旧双代时才删另一代） |
| `MinecraftLauncher.ets` | `-Dorg.lwjgl.librarypath=<...>/natives:<el1>`（多目录）；`-Djava.library.path` 同步含前者；启动设 nameMapper + `-Dmeow.lwjgl.gen=<tag>` |
| 常量 | `LWJGL_GEN_TABLE` 单行、`LWJGL_GEN_JARS` 单 jar、`LWJGL_NAME_MAPPER`；`LWJGL_GEN_333` 已删；`EXPECTED_EXTRA_JARS` 白名单 |
| GLFW overlay | 公共净室 `deltas/overlay/` + 版本相关 `deltas/overlay-3.4.3/`（`opengl/GLCapabilities.java` + `glfw/GLFW.java` + 5 个 shim） |
| GL 桥（`libmeowcraftbridge.so`） | **单份**，满足 3.4.x GLFW stub 的 native 契约（含 IME/preedit 三方法 Java-only 实现，桥零改动） |
| 构建工具 | `tools/lwjgl/`（参数化 `--version`/`--overlay`，产 `lwjgl-<ver>.jar`；`mc_lwjgl_compat_check.py` 做成员级兼容校验） |

### 1.3 overlay 分层
- 公共净室 overlay `deltas/overlay/`（13 个版本无关文件：`glfw/{CallbackBridge,Callbacks,GLFWWindowProperties,GLFWNative*}`、
  `opengl/RendererInit`、`system/MeowBundledNameMapper`）+ 版本相关 `deltas/overlay-3.4.3/`
  （`opengl/GLCapabilities.java` + `glfw/GLFW.java` + 上述 5 个 3.4.x 兼容 shim）。历史曾有 `overlay-3.3.3/`，已移除。
- `build_lwjgl_jar.sh` 支持重复 `--overlay`，且**若 `deltas/overlay-<VERSION>` 存在却未传则报错**（防漏传导致 jar 缺版本钉死文件）。
- `GLCapabilities` **由 `tools/lwjgl/gen_glcap.py` 生成**（官方文件 → 注入 `RendererInit.onCreateCapabilities` /
  删版本守卫 / 去短路 / `reportMissing`→false）。槽位数必须与 natives 同版本（C 侧 `tlsGetFunction(index)`）。
- `GLFW.java`(3.4.3) = 公共版 + 3.4.x 独有 **IME/preedit** 三方法（MC≥1.22 的 `InputConstants`/`TextInputManager` 用到）；
  Java-only 实现，桥零改动。
- **libffi 3.8.0**：LWJGL≥3.4.x 链 `ffi_call_plan_*`，3.4.4 不兼容；`tools/lwjgl/build_libffi.sh`（OHOS 交叉编）。

### 1.4 native 命名（世代号紧跟基名）与**两处锁步**
- 命名 = `liblwjgl_<gen>{,_opengl,_stb}.so`（现仅 `_343`），同处 `meowlwjgls/libs/arm64-v8a/`（hvigor 只打包顶层 .so，故必须扁平）。
- 目录由 `tools/lwjgl/install_natives.sh` 治理（+ `natives.manifest`，**铺名**）；
  overlay 净室类 `org/lwjgl/system/MeowBundledNameMapper.java`（**查名**）——命名由此两处**锁步**决定，改一处必同步另一处。
- 启动对**所有世代**设 `-Dorg.lwjgl.system.bundledLibrary.nameMapper=org.lwjgl.system.MeowBundledNameMapper` + `-Dmeow.lwjgl.gen=<tag>`。
- 无 SONAME、NEEDED 仅 `libc.so` → 同 run 无冲突。
- **legacy LWJGL2 `liblwjgl.so` 无后缀**（`org.lwjgl.Sys.loadLibrary("lwjgl")` 只找该名，不经 mapper）；
  **SDL3 `libSDL3.so` 亦无后缀**（`MeowBundledNameMapper` 对 `SDL3` 透传，tag `common`）。
  二者与 `liblwjgl_343{,_opengl,_stb}.so` 命名正交，同处扁平目录互不冲突。

### 1.5 ArkTS 消费面
- `MinecraftLauncher.lwjglGeneration(jsonPath)` 解析 `org.lwjgl:lwjgl:<ver>`（`LWJGL_GEN_TABLE` 单行 → 归并 3.4.3）；
  `buildLaunchArgv` 设 mapper 属性；`ClasspathStager` 平铺 + `lwjglClasspathOk`（含"杂散 `lwjgl-<数字>*` jar"检查）；
  常量 `LWJGL_GEN_TABLE` / `LWJGL_GEN_JARS` / `LWJGL_NAME_MAPPER`；`EXTRAS_VERSION` 递增。
- `extractRawTar` **子目录支持已实测**（`type=='5'` 建目录 + 文件前 `MakeDirs`）——本方案不需要，但留档。

## 2. 约束 / 坑（必须处理）
1. **natives 必须随包**：平台在安装时对每个随包 native 打 fs-verity 签名；运行时写入 el1/el2 数据区的文件
   **无签名 → dlopen EINVAL**（[`bisheng-hnp-trial.md`](../../30-supply-chain/bisheng-hnp-trial.md) 实证）。故 native 都放随包目录
   （`meowlwjgls/libs/arm64-v8a/`，经 meowjre 隔离空间），靠**世代号紧跟基名 + nameMapper** 区分；⛔ 不可放 extras tar。
2. **classpath 只能有一份 lwjgl jar**：`-cp "<dir>/*"` 会把目录内所有 jar 都上路径 → 必须保证 staging 后该目录只留一份
   （单代下 `lwjgl-3.3.3.jar` 根本不在包内；`lwjglClasspathOk` 兜底检出杂散 jar）。
3. 存储：+~11.6MB(3.4.3 jar) + ~1.2MB(3.4.3 natives)，tar/安装包变大，可接受。
4. 桥 ABI：3.4.x stub 新增的 IME/preedit 三个方法用 Java-only 实现（镜像 `glfwSetDropCallback`），**桥本身零改动**。
5. `libmeowcraftbridge.so` 的 `System.loadLibrary("meowcraftbridge")` 名单代一致。

## 3. 5 个 3.4.x 兼容 shim（overlay-3.4.3）

**判据（为什么"直接丢 3.3.3"安全）**：`tools/lwjgl/mc_lwjgl_compat_check.py` 读 MC 客户端 jar 里**每一个** `org/lwjgl` 引用
（解析常量池 `Methodref/Fieldref/InterfaceMethodref` → `owner.name:desc`），再在 LWJGL jar 里**沿父类/接口链**解析该成员是否被声明。
以 3.3.3 为对照跑 1.16.5/1.19.4/1.21.10 → **0 缺失**（校验器可靠）；对照 3.4.3 → **缺失类 0 个、缺失成员恰好 5 个**（即下表）。
> 只看"文件级/类级"会误判：`limit()/free()/position()` 之类是**继承**来的，必须走父类链（第一版校验器就栽在这）。

| 缺失成员（3.4.x 删/改） | 使用它的 MC 版本 | 性质 |
|---|---|---|
| `glfw.GLFWImage.mallocStack(int, MemoryStack)` | 1.13.2–1.18.2 | 3.4 生成器删掉的便利静态（一行 `malloc(...)`） |
| `stb.STBIIOCallbacks.mallocStack(MemoryStack)` | 1.13.2–1.18.2 | 同上（stb_image 内存加载） |
| `stb.STBVorbisInfo.mallocStack(MemoryStack)` | 1.14.4–1.19.4 | 同上（OGG/Vorbis 音频） |
| `stb.STBImageResize.nstbir_resize_uint8(JIIIJIIII)I` | **1.13.2–1.21.11（全部现代版）** | resize→**resize2** 换名；新 `nstbir_resize_uint8_linear(...)J` 形参同形 |
| `util.tinyfd.TinyFileDialogs.tinyfd_messageBox(CS,CS,CS,CS,Z)Z` | 1.16.5–1.21.11 | 3.4 把末参 `Z`→`I`、返回也从 `Z`→`I` |

- 3 个 struct 补回 `mallocStack()/callocStack()` 全族（委托现存 `malloc/calloc`，即 3.3.x 原实现）；
  `STBImageResize` 补回 `nstbir_resize_uint8(...)I`（委托新 `..._linear(...)J`，结果 `!=0L → 1/0`；旧 `num_channels` 1/2/3/4 映射为 resize2 的**无 alpha** layout）+ 公开 `stbir_resize_uint8(ByteBuffer…)Z`；
  `TinyFileDialogs` 补回 boolean 重载（CharSequence 版 + ByteBuffer 版，`aDefaultButton?1:0` 进、`!=0` 出）——与 3.3.x 生成代码同语义。
- 其它 3.4.0 破坏性项（`mallocStack/callocStack` 全族、`NonnullDefault` 注解类被删、`MemoryUtil`→`MemoryUtilFFM`、
  Unsafe accessor 改包级、stb `stbir_*` 全族换名）经全量核对，**MC 都不用**。
- **未知点清零**：唯一真未知 = "MC 到底调不调被删的 API"，已被上表锁死；余下只有 shim 的**语义保真**与**实机回归**。
  独立复核结论：5 个 shim 与官方 3.4.3/3.3.3 源**逐行比对 = 纯新增、语义等价**（详见 [`../../90-archive/LWJGL3单代收敛-决策依据.md`](../../90-archive/LWJGL3单代收敛-决策依据.md) §8）。
- **副产（可复用工具）**：`mc_lwjgl_compat_check.py` 已收入 `tools/lwjgl/`；同源 `jar_class_dump.py` / `mc_lwjgl_ref_scan.py` / `mc_lwjgl_api_scan.py` 留 `stuffs/research/`。
  **方法论** = *改代际 / 换依赖前，先做成员级全量核对* —— 比"跑一把看看"便宜，且能直接定位"缺哪几个成员"。

## 4. `EXTRAS_VERSION`（换 tar 内容必递增）
- tar 内容变（换 jar / native / 改名）**必须显式递增**：staging 缓存按"每版本 done 标记"判定，令牌不变会继续用旧
  `cacheDir/mc-cp/<key>-<id>/` 里的旧 jar → 旧 nameMapper 找旧 so 名 → `UnsatisfiedLinkError`。
- 实机教训与规范见 [`../launch/决策与不变量.md`](../launch/决策与不变量.md) §10.6
  （**该文撰写时** `EXTRAS_VERSION=20260915-lwjgl-tagname`；**现役值**见 [`assets-digests.txt`](../../30-supply-chain/assets-digests.txt)——2026-09-16（v26）升为 `20260916-script-rebuild`）。

## 5. 实机验证（2026-09-10～2026-09-14）
- **26.1.2（gen=3.4.3）完全可玩**：加载 `lwjgl_343`/`lwjgl_343_opengl`/`lwjgl_343_stb`；GL 起在
  `zink Vulkan 1.2 / GL 4.2 (Core Profile)`；**音频正常、输入法正常**。
- **1.13.2 / 1.14.4 / 1.16.5 / 1.17.1 / 1.18.2 / 1.19.4 / 1.21.10 / 1.21.11 + 26.x**：收敛后用户确认"都能跑"
  （1.21.10 亦走 3.4.3：`_343` 三件 + 3.4.x 兼容 shim）。
  > 历史：2026-09-10 时 1.21.10 曾用 gen=3.3.3、natives 为后缀式 `liblwjgl{,_opengl,_stb}_333.so`；整套命名于
  > 2026-09-14 改为世代号紧跟基名，旧 `_333` 代同日移除。
- 现行 `meowlwjgls/libs/arm64-v8a/` 共 **11 so**：LWJGL 现代单代 **3**（`_343`）+ **legacy `liblwjgl.so`** + tinyfd
  + **SDL3 `libSDL3.so`** + `libshaderc.so` + `libspirv-cross.so` + **gl4es** + openal + freetype；
  `natives.manifest` **11 项**（tag 仅 `3.4.3` 与 `common`）；无 SONAME 冲突。
  （历史 2026-09-10～09-13：现代两代 6 + 其余 = **14 so**，manifest **12 项**。）
- **legacy LWJGL2（2026-09-11）**：`liblwjgl.so` 走 `Sys.loadLibrary("lwjgl")`，服务 MC 1.6.x–1.12.2；
  1.6.4 / 1.7.10 / 1.8.9 / 1.12.2 实机进主界面/进世界/键鼠/聊天/全屏全通过（[`LWJGL2-legacy适配-复盘.md`](LWJGL2-legacy适配-复盘.md) §1）。
- **SDL3（2026-09-11）**：`libSDL3.so`（无后缀，tag `common`）服务 ≥26.3；26.3-rc-1 实机可玩
  （[`SDL3适配-复盘.md`](../render/SDL3适配-复盘.md) §五/§六）。
- **可复现性已实跑核实（2026-09-10）**：`lwjgl-3.4.3.jar` 2 次同路径重建 `cmp` 一致；3.4.3 natives 3 次同路径一致
  （⚠️ native 内嵌绝对输出路径 → 仅同路径逐字节可复现）。见 `tools/lwjgl/README.md` §4。
- 提交：`52f3eba`（LWJGL 两代并存）、`e70da30`（OpenAL 1.24.3）、`2f5a5a1`/`ae49c21`（后缀式命名 + 对称 overlay，
  2026-09-14 改为世代号紧跟基名）、`8659c09`（SDL3 26.3）、`3299abe`（≤1.16 gl4es）、`c3b8806`（legacy LWJGL2）。

## 6. 历史沿革（2026-09-10 两代并存 → 2026-09-14 收敛单代）
- **2026-09-10：曾落地"两代并存"** —— `3.3.3`（服务 1.17–1.21.x）与 `3.4.3`（服务 ≥1.22；选 3.4.3 而非 3.4.1：同为 3.4.x、
  向后兼容且 API 更全）。`ClasspathStager` 按版本 json 的 `org.lwjgl:lwjgl:<ver>` **选代**（并删另一代 jar）；
  natives 一度用后缀式 `liblwjgl{,_opengl,_stb}_333.so`。原设计（§0–§6 旧版）认为跨代 3.3→3.4 不兼容、必须并存。
- **2026-09-14：收敛为单代 3.4.3** —— `mc_lwjgl_compat_check.py`（成员级、含继承解析）证明 3.4.3 相对全部现代版
  **只缺 5 个成员**，于是：补 5 个 shim、删 `lwjgl-3.3.3.jar` / `overlay-3.3.3/` / 3 个 `_333.so` + manifest 行 /
  `LWJGL_GEN_333`；natives 改名"世代号紧跟基名"；模块 `meowlwjgl3`→`meowlwjgls`；
  `pack_extras.py` 改为丢弃 base tar 里所有 `lwjgl*.jar`。
  ⇒ **双代并非必要**：原设计的主要成本 = 3.4.x 的 GLFW overlay/`GLCapabilities`，与"多版本选择"无关。
- 历史结论（现行单代同样成立，已并入上文）：**natives 必须随包**（fs-verity）、**classpath 只能有一份 lwjgl jar**。
  两代并存的完整历史设计与"为什么可行（三个天然挂点）"的原始推导，另见阶段1 快照
  [`../../90-archive/LWJGL3自编-阶段1历史.md`](../../90-archive/LWJGL3自编-阶段1历史.md)。
- 收敛依据全文（shim 修法、未知点清零、全链 review）：[`../../90-archive/LWJGL3单代收敛-决策依据.md`](../../90-archive/LWJGL3单代收敛-决策依据.md)。

## 7. 指针
- 供应链：[`provenance-master.md`](../../30-supply-chain/provenance-master.md)；收敛依据：[`../../90-archive/LWJGL3单代收敛-决策依据.md`](../../90-archive/LWJGL3单代收敛-决策依据.md)；
  阶段1 方案/快照：[`../../90-archive/LWJGL3自编-阶段1历史.md`](../../90-archive/LWJGL3自编-阶段1历史.md)；
- overlay/桥净室：[`../render/GLFW净室桥-设计.md`](../render/GLFW净室桥-设计.md)；版本边界：[`../../00-current/版本支持边界.md`](../../00-current/版本支持边界.md)。
- 构建工具：`tools/lwjgl/{build_lwjgl_jar.sh,build_lwjgl_natives.sh,gen_glcap.py,build_libffi.sh,install_natives.sh,pack_extras.py,mc_lwjgl_compat_check.py}`（末项为成员级、含继承解析的兼容校验器）。
