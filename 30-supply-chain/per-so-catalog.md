# el1 逐 so 名录（per-so catalog）

> 对象：**66 个随包 so** = **29** 自编现代 JRE（`meowjre`，已收编 2026-09-12；口径 = `libs/meowjre/libs/arm64-v8a/` 实际 `.so` 数 = 26 官方 OpenJDK 26.0.2.1（glibc）件原地 patch + 3 自编 `libc6.so`/`libjli.so`/`libjvm.so`，**含** `libc6`/`libjli`） + **25** 第二套 JRE（`meowjrelegacy` = **Java 8 / legacy**；`libs/meowjrelegacy/libs/arm64-v8a/`；Eclipse Adoptium Temurin 8 数据件 + 自编 musl `libjvm.so` 与 `libc6`/`libjli` 等桥接件，配方 = 主仓 `tools/jre8/`） + **12** 自编组件：**现代单代 LWJGL 3.4.3 ×3** / legacy LWJGL2 `liblwjgl.so` / `liblwjgl_tinyfd.so` / **VMA `liblwjgl_vma.so`** / `libgl4es.so` / SDL3 `libSDL3.so` / `libshaderc.so` / `libspirv-cross.so` / `libopenal.so` / `libfreetype.so`，运行时部署于两套 JRE HSP 的 el1 `/data/storage/el1/bundle/{meowjre,meowjrelegacy}/libs/arm64`
> （各 HAR 的 native 静态并入对应 HSP 目录）：
> - **meowjre JRE 29**：`libs/meowjre/libs/arm64-v8a/`
> - **meowjrelegacy JRE 25**：`libs/meowjrelegacy/libs/arm64-v8a/`
> - **组件 12**：`libs/meowlwjgls/libs/arm64-v8a/`
>
> `libc++_shared.so` **不在仓库源树**，由 NDK/构建期注入（工具链运行时组件，性质同 `libc.so`，**无需自持**；服务 libopenal 与我们的 libmeowjrebridge）。
>
> 加载机制三合一：① JVM 自 dlopen（`OHOS_DL_DIR`）② Java `System.loadLibrary`（java.library.path）
> ③ LWJGL/JNA loader（org.lwjgl.librarypath / jna.boot.library.path）。
> 来源：JRE 组 29 = **自编/魔改（官方 OpenJDK 26.0.2.1 glibc 件原地改 `.dynstr` + 自编 `libc6.so`/`libjli.so`/`libjvm.so`）**；自编 `libjli`/`libjvm` 源 = 官方 26.0.2.1 发布同一 commit（更新仓 `openjdk/jdk26u` `jdk-26.0.2.1-ga` @ `d55edf1cba61…`）；
> 组件组 12（现代单代 LWJGL 3.4.3 `_343`×3 / legacy LWJGL2 `liblwjgl.so` / `liblwjgl_tinyfd.so` / VMA `liblwjgl_vma.so` / `libgl4es.so` / `libSDL3.so` / `libshaderc.so` / `libspirv-cross.so` / `libopenal.so` / `libfreetype.so`；旧 `_333` 三件已于 2026-09-14 移除）均为**自编**（见 [`provenance-master.md`](provenance-master.md) §3）；LWJGL 早期随包的旧件已被自编件替换。
> 溯源见 [`provenance-master.md`](provenance-master.md) §3-§4。

## A. JRE 组（meowjre，29 个 = 26 官方 OpenJDK 26.0.2.1 glibc 件原地 patch + 3 自编 `libc6`/`libjli`/`libjvm`；自编件对齐官方源 `jdk26u` `jdk-26.0.2.1-ga`）
使用者 = JVM 自己（启动链 libjli→libjvm→java.base 按需 dlopen）。

### A1 启动/常驻核心（9）
| so | 职责 | 加载时机 |
|---|---|---|
| libjli.so | launcher 引导库 | 每次（我们的 libmeowjrebridge 经 JLI_Launch 调它） |
| libjvm.so | HotSpot VM 本体（17MB） | 每次 |
| libjava.so | java.base 核心 native | 每次 |
| libzip.so | zip/jar 读取 | 类加载/资源 |
| libjimage.so | jimage 模块镜像 | 模块系统 |
| libverify.so | 字节码校验 | 类加载 |
| libnet.so / libnio.so | 网络栈 / NIO | 联网/IO |
| libjsig.so | 信号链（libjsig 前置） | 用 -Xrs/信号链时 |

> 另含自编兼容层 **`libc6.so`**（glibc→musl shim，**无版本**导出；随 JRE 组一并计入）：9(A1) + 13(A2) + 6(A3) + `libc6` = **29**。

### A2 按特性惰性加载（13 随包）
| so | 职责 | 何时 |
|---|---|---|
| libinstrument.so | javaagent 支撑 | 有 `-javaagent` 时才载（patchjna 已退役，默认不挂） |
| libextnet.so | unix domain socket 等扩展网络 | 极少 |
| libsyslookup.so | FFM SystemLookup 符号查询 | 极少 |
| libjdwp.so + libdt_socket.so | 调试器 | 仅调试挂 agentlib |
| libmanagement{,_agent,_ext}.so | JMX | 不显式开 JMX 不用 |
| ~~libj2pkcs11.so~~ | PKCS#11 加密 | **未随包**（实际 `libs/meowjre/libs/arm64-v8a/` 无此件） |
| libj2gss.so | GSS/Kerberos | 认证场景 |
| libjaas.so | JAAS 登录 | 极少 |
| libprefs.so | java.util.prefs | 用到才载 |
| librmi.so / libsctp.so | RMI / SCTP | 不用 |

### A3 AWT/Java2D 备胎组（6 随包；原版 MC 不碰）
libawt.so / libawt_headless.so（AWT toolkit）、libfontmanager.so（Java2D 字体）、
libjavajpeg.so（JPEG codec）、libmlib_image.so（图像加速）、liblcms.so（色彩管理）；
~~libjawt.so~~（AWT JNI 桥；**未随包**，实际 `libs/meowjre/libs/arm64-v8a/` 无此件）。
> 加载条件：只有触发 java.awt/javax.imageio 才 dlopen；vanilla 路径基本是压舱物。

## A′. 第二套 JRE 组（meowjrelegacy，25 个 = Java 8 / legacy）
> 服务**需要 Java 8 的实例**（Forge ≤1.12.2 走 LaunchWrapper：需 `java.util.jar.Pack200`（JDK 14 删）与可用的 `SecurityManager`（JDK 24 禁）⇒ 上限 8；选择逻辑见 [`../20-design/launch/环境与载体.md`](../20-design/launch/环境与载体.md)）。
> 口径 = `libs/meowjrelegacy/libs/arm64-v8a/` 实际 `.so` 数 = **25**。
> 来源：数据件 = **Eclipse Adoptium Temurin 8**（`jdk8u504-b01`, linux/**aarch64**, **glibc**, `image_type=jdk`；release 溯源 sha256 `57b7ed8af9d48542bb49ff7894448040b17bea0a48b41677d11ecaec6129768d`）；**我方自编/改造** = `libjvm.so`（musl，源码 `ref/jdk8u` / OpenJDK 8u504，HotSpot 打了 OHOS 分体补丁）+ `libc6.so`/`libjli.so` 等桥接件；数据 tar = `rawfile/meow_jre_legacy.tar.gz`（**32,333,885 B**，data token `1.8.0_504-b01-r1`）。完整配方 / digests：主仓 `tools/jre8/README.md`。

| 组 | 件 |
|---|---|
| 启动/常驻核心（8） | `libjli` `libjvm` `libjava` `libzip` `libverify` `libnet` `libnio` `libjsig` |
| 按特性惰性（9） | `libinstrument` `libjdwp` `libdt_socket` `libmanagement` `libj2gss` `libjaas_unix` `libsctp` `libunpack` `libsunec` |
| AWT/Java2D（6） | `libawt` `libawt_headless` `libfontmanager` `libjpeg` `libmlib_image` `liblcms` |
| 兼容层 / 其它（2） | `libc6`（glibc→musl shim）、`libfreetype`（与 meowlwjgls 的 `libfreetype.so` **同哈希**） |

> ⚠️ **与 meowjre 组的同名件**：本组与 meowjre 组有多个**同名但 `.dynstr`/哈希不同**的件（是 Java 8 那套的对应件；两套件各自在自己 HSP 里）⇒ **勿跨套混装**；组件类件（gl4es / lwjgl 等）在**两个 HSP 各有一份副本**，换件时**两个 HSP 都要同步**（见主仓 `工程与规范.md` §二 3.1）。

## B. 组件组（meowlwjgls，12 个；MC 运行时外围，Java 动态加载）
> 现代 LWJGL **单代 3.4.3**（服务 1.13–1.21.x 与 ≥1.22；旧的 3.3.3 代已于 **2026-09-14 移除**，缺失成员由 overlay-3.4.3 的 5 个 3.4.x shim 补齐）；另有 legacy LWJGL2 `liblwjgl.so`（1.6.x–1.12.2）与 gen-agnostic 件（`tinyfd`/`vma`/`gl4es`/`SDL3`/`shaderc`/`spirv-cross`，manifest tag `common`）。
> 同处**扁平目录**（hvigor 只打包 `libs/<abi>/*.so` 顶层），靠**世代号紧跟基名**（现仅 `_343`，即 `liblwjgl_343{,_opengl,_stb}.so`）+ 官方 `bundledLibrary.nameMapper` 在启动期选名（命名由 `install_natives.sh` 铺名 / `MeowBundledNameMapper` 查名两处锁步，见
> [`../20-design/lwjgl/LWJGL3世代管理-方案.md`](../20-design/lwjgl/LWJGL3世代管理-方案.md) §7）。

| so | 身份 | 加载者 | 作用 |
|---|---|---|---|
| ~~liblwjgl_333.so~~ | LWJGL core native @3.3.3；**已于 2026-09-14 移除**（历史 sha `0b1dc8ae…`，导出 1961） | — | — |
| ~~liblwjgl_opengl_333.so~~ | LWJGL GL 绑定 @3.3.3；**已于 2026-09-14 移除**（历史 sha `4541eeb3…`，导出 2228） | — | — |
| ~~liblwjgl_stb_333.so~~ | stb 图像解码 @3.3.3；**已于 2026-09-14 移除**（历史 sha `a8d2392d…`，导出 215） | — | — |
| liblwjgl_343.so | LWJGL core native @3.4.3（链 libffi 3.8.0）；**自编 2026-09-10；2026-09-17 F2 对齐 clamp 重编**（现 sha `2a6fcf99…`，导出 2207；pre-F2 `16298280…`，备份 `stuffs/research/vulkan/fixes/liblwjgl_343.so.pre-f2`） | LWJGL `System.loadLibrary`（现代单代；1.13–1.21.x 与 ≥1.22） | 内存/loader，一切 LWJGL 地基，必载 |
| liblwjgl_343_opengl.so | LWJGL GL 绑定 @3.4.3；**自编**（sha `e1f1413b…`，导出 2270） | 同上 | 同上（槽位 2270） |
| liblwjgl_343_stb.so | stb 图像解码 @3.4.3；**自编**（sha `8eb4a1b8…`，导出 224） | 同上 | 同上 |
| liblwjgl.so | **legacy LWJGL2 native（自编；**当前随包件 sha `73ac4aa8…`**〔2026-09-29 契约订正（共享上下文 + `nCreate` 形参）后，再对齐整族 JNI 形参口径（`nReleaseCurrentContext` 等）后重编，323,336 B；supersedes `b6f9106c…`〔2026-09-29 契约订正后单次重编, 323,368 B〕 / `df886466…`〔2026-09-11, 322,600 B〕 / `93931548…`〔契约订正前单次构建, 323,368 B〕〕，导出 2287〔Stage 2 `--with-display`〕；JNI_VERSION=19，`DT_NEEDED=libc.so` 仅）** | MC 1.7–1.12 的 `org.lwjgl.*` | LWJGL2 窗口/输入/上下文；GL 取址→gl4es；服务 MC 1.6.x–1.12.2（aarch64 只认此名，无 `64`） |
| liblwjgl_tinyfd.so | **tinyfd（自编；tag `common`；sha `f2b126ca…`；gen-agnostic 无后缀）** | LWJGL `NativeLibrariesBootstrap`（≥1.22 eager load） | 原生文件对话框；`MeowBundledNameMapper` 原样透传 |
| liblwjgl_vma.so | **VMA 内存分配器（自编；tag `common`；`--release` 纯净件；sha `479a619f…`；`DT_NEEDED` 仅 libc，libc++ 静态链入）** | `org.lwjgl.util.vma`（LWJGL ≥3.4.x；MC 的**所有** Vulkan 分配） | Vulkan 显存分配（`vmaCreateAllocator`/`vmaCreateBuffer`/…）；LibVma 无 override key ⇒ 缺件硬失败 "Failed to create VMA allocator"。配方 `tools/lwjgl/build_lwjgl_vma.sh`（默认 release；诊断版不随包） |
| libgl4es.so | **gl4es v1.1.7（自编；tag `common`；**当前随包件 sha `60f57b38…`**（自证 tag `2026-10-21-fog-identity-state`，1,297,272 B；把 EXP/EXP2 + `density==0` 的「恒等雾」归一化成 fog-off 变体，并让生成器消费归一化状态 ⇒ 修 1.16.5 主菜单文字全黑；实机验收 2026-10-21 通过。上一版 = `993672d9…`〔双 GL 上下文「显示列表 id 撞号」根因修复版 + 收尾加固（`glGenLists()` 占位检测由看值改看键 + 新增 `gl4es_glListReserved` ⇒ 修"两个 EGL 上下文发出同一批 display list id"，FML splash 第二上下文 + 主上下文撞号/顶替；另硬化 `list.c` `mode_inits` 深拷贝 + OOM 分支 `mode_init_cap = 0`、`gl4es.c` `glGenLists()` 扫描+插入套 `glgenlists_lock`、`drawing.c` `GL_QUADS` 立即路径索引缓存三处加锁〔含补的第三处 `glMultiDrawArrays`〕），自证 tag `2026-10-01-ctxlistid2`，1,292,568 B；**实机验收已通过（2026-10-01；含 `shared ctx created` 病态条件 + 四症状正常）**；supersedes `444bc805…`〔v47「显示列表 id 撞号」修复版（无本轮收尾加固），自证 tag `2026-10-01-ctxlistid`，2026-10-01, 1,292,568 B〕、`35a81e4c…`〔每 EGL 上下文隔离 glstate 版（tls3：+ M-2 可观测化 warn，共享语义不变），自证 tag `2026-09-30-ctxiso-tls3`，2026-09-30, 1,292,568 B〕、`ea15f779…`〔每 EGL 上下文隔离 glstate 版（tls2），自证 tag `2026-09-29-ctxiso-tls2`，2026-09-29, 1,292,568 B〕、`f5c2d61f…`〔每 EGL 上下文隔离 glstate 版（tls），自证 tag `2026-09-29-ctxiso-tls`，2026-09-29, 1,292,568 B〕、`5c01567d…`〔雾兜底版，自证 tag `2026-09-29-fogfix-reentrant`，2026-09-29, 1,259,800 B〕、`87fc358b…`〔自证 tag `2026-09-29-cleanup`，2026-09-29, 1,260,408 B〕与 `f96d54a5…`〔r16 = 雾改动前历史基准，2026-09-27, 1,255,704 B〕〕；`SONAME=libGL.so.1`，`DT_NEEDED` 仅 libc）** | 桥（gl4es 后端 / **GL3 core 后端**）/ LWJGL2 `extgl` 取址 | 桌面 GL 1.x/2.x → 原生 GLES 翻译层（FPE；服务 ≤1.16 含 legacy）**＋ GL 3.2/3.3 core → 原生 GLES 3.2（1.17–1.21.x，env `MEOW_GL3`；着色器经 shaderc/SPIRV-Cross 翻译，见 `运行时环境变量.md`）** |
| libSDL3.so | **SDL3 fork `release-3.4.14` + 自研 `ohos` 驱动（自编；tag `common`；sha `5fe4d5d4…`）** | `org.lwjgl.sdl`（LWJGL ≥3.4.x） | MC 26.3 视频/输入后端（含 Vulkan WSI、焦点事件、剪贴板写、打开网址）；`DT_NEEDED` libnative_window/libc（EGL/GL/pasteboard 运行时 dlopen） |
| libshaderc.so | **shaderc @2c8cae7（自编；tag `common`；sha `0cff3465…`）** | `org.lwjgl.util.shaderc.Shaderc` | MC 26.3 `renderpearl` 着色器编译；glslang/SPIRV-Tools 静态并入 |
| libspirv-cross.so | **SPIRV-Cross @6c09849（自编；tag `common`；sha `93ad9907…`）** | `org.lwjgl.util.spvc.Spvc` | MC 26.3 `renderpearl` SPIR-V 转换 |
| libopenal.so | **OpenAL Soft 1.24.3（自编；sha `fececaee…`；默认 OHAudio 后端，见 [`../40-adaptation/ohaudio-backend.md`](../40-adaptation/ohaudio-backend.md)）** | org.lwjgl.openal | MC 音频；DT_NEEDED libohaudio/libOpenSLES/libc++_shared |
| libfreetype.so | **FreeType 2.13.3（自编；[`../40-adaptation/freetype-ohos.md`](../40-adaptation/freetype-ohos.md)）** | LWJGL freetype 绑定 | MC 字体光栅化 |

> 目录由 `tools/lwjgl/install_natives.sh` 治理（`libs/meowlwjgls/libs/natives.manifest`：tag → 文件名 + sha256）；**勿手工增删/改名**。

> `libjnidispatch.so` 已于 2026-09-09 **摘除**（JNA 不再随包；仅 oshi 用、且 oshi 已改为合成拓扑。见 [`jna-analysis.md`](../90-archive/supply-chain-retired/jna-analysis.md)）。

## 备注
- **口径与复算**：A 段（现代 JRE）= `主仓/libs/meowjre/libs/arm64-v8a/*.so`（29）；A′ 段（第二套 JRE / Java 8）= `主仓/libs/meowjrelegacy/libs/arm64-v8a/*.so`（25）；B 段（组件）= `主仓/libs/meowlwjgls/libs/arm64-v8a/*.so`（12）。复算并逐行核对：`sha256sum 主仓/libs/*/libs/arm64-v8a/*.so`（三目录合计 66）。
- strip 无 .comment；个别带 GNU build-id 可作比对锚：libopenal=f4be7661…、
  libc++_shared=e6d9b144…（libc++_shared 为构建期注入）。
- 自研 so（libmeowjrebridge / libmeowcraftbridge / libmeowassets）不在本清单（CMake 产物，见 [`provenance-master.md`](provenance-master.md)）。
- **随包 jar（entry rawfile 的 extras）不在本名录**（本表只列 `.so`）：`meowcraft_extras.tar.gz` 的 jar 成员（`lwjgl-3.4.3.jar` / **`asm9/{asm,asm-analysis,asm-commons,asm-tree,asm-util}-9.9.1.jar`〔v45 2026-09-30 新增，启动期覆盖实例声明的旧 ASM〕**；`launcher.jar` / `gson-for-launcher.jar` 已于 2026-10-01 随 MeowLauncher 退役移除）见 [`assets-digests.txt`](assets-digests.txt) 的「meowcraft_extras jars」段与 [`provenance-master.md`](provenance-master.md) §2/§3/§4。
