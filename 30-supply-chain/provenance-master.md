# 技术资产溯源总表（Master Provenance）

> 本表 = 随包件与自编件的来源 / 分级 / 收编路线（2026-09-10 全量重写；2026-09-18 补 F2/VMA）：
> 支持窗口 **MC 1.6.x – 26.3**（2026-09-11 实测定案）。新增自编件：legacy LWJGL2（`liblwjgl.so`，1.6.x–1.12.2）、
> `libgl4es.so`（≤1.16）、`libSDL3.so` + `libshaderc.so` + `libspirv-cross.so`（≥26.3）、`liblwjgl_tinyfd.so`、legacy oshi 1.1。
> LWJGL 现代**单代 3.4.3**（2026-09-14 由「两代并存 3.3.3 + 3.4.3」收敛；服务 1.13–1.21.x 与 ≥1.22，缺失成员靠 5 个 3.4.x 兼容 shim）+ OpenAL Soft **1.24.3**（`ALC_SOFT_system_events`）+ LWJGL core 链 **libffi 3.8.0**。
> **范围**：除用户游戏文件夹（stuffs/.minecraft）外的全部随包/自研资产。
> **2026-09-30 补 §4.2**：把**从网络下载的产物**（随包 ASM 9.9.1 ×5 / 重建的 extras tar / 取证的 6 份 Forge installer）逐条记 **URL + 日期 + 官方 sha1 + 实测 sha256 + 落盘 + 是否随包 + 校验方式**（照 URL 可重下逐字节复核）。
> 依据：本目录 digest（**v45**）/ 逐 so 名录、`../20-design/`、`../40-adaptation/`、历次实机验证日志。口径见 §1。
> **血统声明**：Pojav / Amethyst / HOML-HomoLauncher **血统已全部清除**；`ref/PojavLauncher_iOS`、`ref/Amethyst-Android` 仅作**工作区外部参照**，不入仓库、不随包。

## 1. 分级口径
| 级 | 定义 |
|---|---|
| **完全自主（源码级）** | 源码在本仓库，且由我们的工具链**本地编译** |
| **可控·来源已核实** | 官方发布物/工具链件，能证明与上游一致（逐字节核对 / 官方坐标 + `.sha1`） |
| **外部历史件** | 外部预编译包转手（本机未复现），信任仅到"归因"；**不排除魔改** |
| **平台依赖** | 系统能力，非应用资产 |
| **已退役** | git / notes 锚点留证可还原 |

## 2. 总览金字塔
```
① 完全自主（源码在仓库，我们编译/构建）
   ArkTS 全量（entry 入口/游戏窗/启动器 UI/状态/扫描器/输入转发/IME）
   libmeowassets.so        ← entry native：installJre / extractRawTar
   libmeowjrebridge.so     ← meowcraftlib：NAPI launchJvm + env + 预 dlopen + surface 注入 + meowSend* + 光标锁
   libmeowcraftbridge.so   ← meowcraftlib：GLFW/GL 桥本体（JNI 挂载 / 事件 ring+pump / EGL / resize / 关窗 / grab）；净室自研
   lwjgl-3.4.3.jar ← tools/lwjgl：官方 8 模块（Maven 下载）+ 自研净室 overlay（现代单代，服务 1.13–1.21.x 与 ≥1.22；≥3.4.x 另补 sdl/vma/spvc/shaderc；旧 3.3.3 jar 已于 2026-09-14 移除）
   liblwjgl_343{,_opengl,_stb}.so ← tools/lwjgl：ref/lwjgl3 @3.4.3 交叉编译（世代号紧跟基名；core 链 libffi 3.8.0 + F2 对齐 clamp；旧 `_333` 三件已于 2026-09-14 移除）
   liblwjgl_vma.so         ← tools/lwjgl/build_lwjgl_vma.sh：VMA 自编（release 默认 = 随包纯净件；`--diagnostic` 不随包；gen-agnostic，tag common）
   liblwjgl.so             ← tools/lwjgl2：legacy LWJGL2 native 净室重编（JNI_VERSION=19，服务 MC 1.6.x–1.12.2；GL→gl4es）
   liblwjgl_tinyfd.so      ← tools/lwjgl：LWJGL tinyfd（gen-agnostic，tag common；MC ≥1.22 启动期 eager load）
   libgl4es.so             ← tools/gl4es：gl4es v1.1.7 OHOS 自编（桌面 GL 1.x/2.x → 原生 GLES；服务 ≤1.16 及 legacy）
   libSDL3.so              ← tools/sdl：SDL3 fork release-3.4.14 + 自研 ohos 驱动（服务 ≥26.3）
   libshaderc.so / libspirv-cross.so ← tools/shaderc：shaderc + SPIRV-Cross 自编（≥26.3 renderpearl）
   libffi.a                ← tools/lwjgl/build_libffi.sh：上游 libffi 3.8.0 OHOS 交叉编译（LWJGL ≥3.4 依赖）
   libopenal.so            ← tools/openal：OpenAL Soft 1.24.3 OHOS 移植（默认 OHAudio 后端）
   libfreetype.so          ← tools/freetype：FreeType 2.13.3 自编（zlib only）
   oshi-overrides ×10      ← tools/oshi：上游 oshi jar（现代 9 + legacy 1.1）+ CPU 拓扑合成补丁
   tools/                  ← 构建/打包/补丁脚本（relocate_gson.py / pack_jar.py / jre26/ …）

② 可控·来源已核实随包
   asm9/{asm,asm-analysis,asm-commons,asm-tree,asm-util}-9.9.1.jar（Maven Central 官方 5 件，逐件 `.sha1` 校验、与本机树逐字节 `cmp` 一致；落在 extras tar 的 `asm9/` 子目录，启动期覆盖实例声明的旧 ASM）
   libc++_shared.so（OHOS NDK 工具链件；装机件 == NDK 官方件）

③ 原「外部历史件」JRE —— **已收编并精确对齐（2026-09-12，零黑箱）**
   随包 JRE 现全自持：官方 OpenJDK 26.0.2.1(glibc) **26 lib** 原地改 `.dynstr` + 自编 `libc6.so`/`libjli.so`/`libjvm.so` + 官方 26.0.2.1 数据
   来源：官方 tar `https://jdk.java.net/archive/` ；源码 **更新仓 `https://github.com/openjdk/jdk26u`**（tag **`jdk-26.0.2.1-ga`** → commit **`d55edf1cba61…`**；26.0.x **不在**主线 `openjdk/jdk`）；配方 `tools/jre26/`

④ 平台依赖（系统，非随包）
   libGLv4/libEGL（桌面 GL = Mesa Zink over Vulkan → Maleoon 916 驱动）
   libhilog_ndk / libace_napi / librawfile / libz / libnative_window* 等 SDK 库

⑤ 已退役（git/锚点留档）
   旧 libpojavexec/libhoml_bridge/libdriver_helper（原生三件套）、libjnidispatch(JNA)、
   mobileglues / NG-GL4ES 黑盒系（已由自编 gl4es 取代）、
   launcher.jar / gson-for-launcher.jar（净室 meow.launcher + 其 shade 后的 gson；2026-10-01 随方案 A「MeowLauncher 退役」整体移除）、
   patchjna_agent.jar、jsr305.jar、tools/patch_pojav_libname.py、tools/repack_*_extras.py
```

## 3. 生产流程（我们编译/魔改/构建的每一项）

| 产物 | 工具（入口） | 生产流程（关键步骤） | 输入（上游/来源） |
|---|---|---|---|
| **launcher.jar**（**已退役 2026-10-01**，历史留档） | `tools/meow-launcher/build_meow_launcher.sh`（javac 用户跑）+ `finalize_for_meowcraft.sh` | 编译 `src/meow/launcher/*`（12 源）+ clean-room `com.mojang.text2speech` 桩 → 确定性 `pack_jar.py` → finalize：组装 pre-shade tar（`lwjgl.jar` 不变 + 新 `launcher.jar` + 官方 gson）→ `relocate_gson.py`（`com.google.gson`→`meow.gson`）→ 换 rawfile tar | 自研源码；编译期依赖 Maven 官方 **gson 2.13.1**（Apache-2.0） |
| **lwjgl-3.4.3.jar** | `tools/lwjgl/build_lwjgl_jar.sh`（javac 用户跑）+ `pack_extras.py` | 官方 **8 模块**从 Maven Central 下载（`.sha1` 校验）→ javac 编 **自研净室 overlay**（公共 `deltas/overlay` + `deltas/overlay-3.4.3`〔含 5 个 3.4.x 兼容 shim〕）→ merge（overlay 覆盖）→ strip META-INF/cacio → 确定性 pack → `pack_extras.py` 组包 | 上游 **LWJGL release 3.4.3**（BSD-3；现代单代，旧 3.3.3 已移除）；`GLCapabilities` 由 `gen_glcap.py` 从对应 tag generated 生成 |
| **liblwjgl_343{,_opengl,_stb}.so** | `tools/lwjgl/build_lwjgl_natives.sh` + `install_natives.sh`（core 另见 `build_lwjgl_core_aligned_alloc_fix.sh` F2） | `git archive ref/lwjgl3@3.4.3` → OHOS clang 交叉编译 core/opengl/stb（复刻上游 Ant+GCC flag；`--version-script` 圈导出；core 需 libffi.a；core 含 **F2 `__aligned_alloc` 对齐 clamp**）→ `llvm-strip` + 去元数据段 → 断言导出面/NEEDED；**世代号紧跟基名**命名（`install_natives.sh` 铺名 / `MeowBundledNameMapper` 查名**两处锁步**）后由 `install_natives.sh` 摆入扁平目录并维护 `natives.manifest` | 上游 **LWJGL 3.4.3** 源码（BSD-3；现代单代）；**libffi 3.8.0**（MIT）；OHOS clang/sysroot |
| **liblwjgl_vma.so** | `tools/lwjgl/build_lwjgl_vma.sh`（`--release` 默认 / `--diagnostic`） | `ref/lwjgl3@3.4.3` 的 `modules/lwjgl/vma` 交叉编（不动 `ref/`；release 为纯净件，`libc++_static` 静态链入 ⇒ `DT_NEEDED` 仅 `libc.so`）→ `llvm-strip` → 断言导出/NEEDED → `install_natives.sh` 摆入扁平目录 + `natives.manifest`（tag `common`）。`--diagnostic` 版带 `[vma]` 诊断串，**不随包**（仅存 `stuffs/`） | 上游 **LWJGL 3.4.3** VMA 模块（BSD-3）；OHOS clang/sysroot；libc++_static（NDK） |
| **libffi.a** | `tools/lwjgl/build_libffi.sh` | 上游 libffi 3.8.0 源码 → `include/ffi.h`（sed 占位符）+ 手写 `fficonfig.h` + 手工 TU 直编 aarch64-linux-ohos（autotools 在沙箱受阻）→ `llvm-ar` → 断言 11 个入口 | 上游 **libffi 3.8.0**（MIT）；OHOS clang/sysroot |
| **libopenal.so** | `tools/openal/build_openal_meow.sh`（`patch_openal_ohos.py` + `patch_openal_ohaudio.py` + `patch_openal_events_export.py`） | 上游源码 + OHOS 移植补丁（新增 **OHAudio** 后端，默认；保留 OpenSL 回退）+ 导出 `ALC_SOFT_system_events` 三函数 → OHOS clang/CMake 编 → 产物入 meowlwjgls | 上游 **OpenAL Soft 1.24.3**（LGPL-2.0-or-later）；OHOS OHAudio C API |
| **libfreetype.so** | `tools/freetype/build_freetype_meow.sh` | 上游源码 → OHOS clang/CMake（`zlib only`）→ strip + 去 OHOS 元数据段 → 与随包旧件 `.text/.rodata` 逐字节一致 | 上游 **FreeType 2.13.3**（FTL / GPLv2） |
| **liblwjgl.so**（legacy LWJGL2） | `tools/lwjgl2/generate_sources.sh` + `build_lwjgl2_meow.sh` + `verify_reproducible.sh` | JDK 驱动注解处理器复刻上游 Ant `generate-all`（8 处理器）产 Java/C + `javac -h` 头 → `src-ohos/` 平台层（extgl→gl4es、EGL+OHNativeWindow 窗口/上下文、输入环、光标）OHOS clang 直编 → 断言导出面/`DT_NEEDED` | 上游 **LWJGL 2.9.3**（`ref/lwjgl` @ `2df01dd7`，BSD-3） |
| **liblwjgl_tinyfd.so** | `tools/lwjgl/build_lwjgl_natives.sh`（gen-agnostic 段） | LWJGL `modules/lwjgl/tinyfd` 的 `tinyfiledialogs.c` + 生成 JNI → OHOS 交叉编（无后缀，tag `common`） | 上游 **LWJGL 3.4.3**（BSD-3）内置 tinyfiledialogs（Zlib） |
| **libgl4es.so** | `tools/gl4es/build_gl4es_meow.sh` + `gl4es_ohos.toolchain.cmake` | 上游 v1.1.7 → OHOS 交叉编（`NOX11/NOEGL/NO_INIT_CONSTRUCTOR`；`libGL.so.1`→`libgl4es.so`）→ 断言固定管线与 dlsym 导出、`DT_NEEDED` 仅 libc | 上游 **ptitSeb/gl4es v1.1.7**（MIT） |
| **libSDL3.so** | `tools/sdl/build_sdl_meow.sh` + `patch_sdl_ohos.py` | SDL fork `release-3.4.14` + 自研 `ohos` 视频/鼠标驱动（接入桥共享状态块）OHOS clang/CMake → 断言驱动/导出 | 上游 **libsdl-org/SDL release-3.4.14**（Zlib） |
| **libshaderc.so / libspirv-cross.so** | `tools/shaderc/build_shaderc_meow.sh` | 钉修订的 shaderc/glslang/SPIRV-Tools/SPIRV-Headers/SPIRV-Cross → OHOS clang/CMake（依赖静态并入）→ strip | 上游 **google/shaderc @2c8cae7**、**KhronosGroup/SPIRV-Cross @6c09849**（Apache-2.0） |
| **oshi-overrides ×10** | `tools/oshi/patch_oshi.py` / `patch_oshi_legacy.py` + `build_oshi_meow.sh` / `build_oshi_legacy_meow.sh` | 对 9 个现代 oshi 版本 + **legacy oshi 1.1** 打"CPU 拓扑合成"补丁（规避 `/proc/cpuinfo` 在沙箱不可读）→ 确定性 pack → 入 rawfile `oshi-overrides/`；运行时按版本覆盖 MC 自带 oshi | 上游 **oshi**（MIT）5.7.4 / 5.7.5 / 5.8.2 / 5.8.5 / 6.2.2 / 6.4.5 / 6.4.10 / 6.6.5 / 6.9.0 + legacy **1.1**（commit `4047d5be65`） |
| **gson-for-launcher.jar**（**已退役 2026-10-01**，历史留档） | `tools/relocate_gson.py` | 取官方 gson jar → 重定位 `com.google.gson`→`meow.gson`（类条目 + 常量池引用）→ 改名成员 | 上游 **gson 2.13.1**（Apache-2.0；Maven 官方坐标，sha1 `853ce06c…`）；HOML 转手副本与其**逐字节相同** |
| **asm9/*.jar（随包 ASM 9.9.1 ×5）** | Maven Central 官方下载（逐件 `.sha1` 校验）+ `tools/lwjgl/pack_extras.py` | 从 `https://repo1.maven.org/maven2/org/ow2/asm/<artifact>/9.9.1/<artifact>-9.9.1.jar` 取 5 件（`asm`/`asm-analysis`/`asm-commons`/`asm-tree`/`asm-util`），逐件下 `.sha1` 校验并与本机树 `stuffs/test-forge/libraries/org/ow2/asm/9.9.1/*` `cmp` 逐字节一致 → `pack_extras.py --jar asm9/<name>=<path>` 组进 extras tar（**`asm9/` 子目录**，不落平铺面） | 上游 **ASM 9.9.1**（BSD-3；module 名 `org.objectweb.asm{,.tree,.tree.analysis,.commons,.util}`，与 9.7.1 一致）；用途见 `MinecraftLauncher.needsAsmOverride` |
| **meow_jre.tar.gz（JRE 数据瘦身）** | `tools/jre26/linux_slim_jre.sh` + `linux_build_zipfs_patch.sh` + `pack_jre_data.py` | 用官方 JDK26 的 `jlink` 按原 HOML 模块集裁 `lib/modules`（剔除 `jdk.crypto.cryptoki` + `jdk.jsobject` → **43 模块**）+ 裁 `bin/` 到 5 件 + 容器编 `jdk.zipfs` 补丁类（`linux_build_zipfs_patch.sh`，36 个 → `home/lib/patch/jdk.zipfs/`）→ `pack_jre_data.py` **确定性**打包（排序 / mtime=0 / uid=gid=0）→ **41,233,017 B / 71 文件**（令牌 r2） | 官方 OpenJDK **26.0.2.1** 数据；自编补丁 `tools/jre26/patches/zipfs_chmod_best_effort.py`；配方 `tools/jre26/`（见 §3③） |
| **确定性打包器** | `tools/oshi/pack_jar.py` | `pack_jar.py <classes> <manifest> <out.jar>`：固定时间戳 + 排序 → 逐字节可复现（launcher/lwjgl/oshi 共用） | — |
| **ArkTS / 3 个自研 so** | hvigor 内置 CMake/Ninja（无独立 tools 入口） | `entry/src/main/cpp/meowassets`、`libs/meowcraftlib/src/main/cpp/{meowjrebridge,meowcraftbridge}` 由 hvigor 构建并静态并入 `meowjre` HSP；jni.h/jni_md.h 为 OpenJDK( GPL+CE) 拷贝 | 自研源码 \| vendored `jni.h` |

## 4. 外部来源（从大基建/网上下载的东西：上游 + 出处）

| 资产 | 上游/作者 | 许可 | 获取方式 | 我们做了什么 |
|---|---|---|---|---|
| LWJGL 8 模块 jar | **LWJGL**（GitHub LWJGL/lwjgl3） | BSD-3 | Maven Central `org.lwjgl:<mod>:3.4.3`（含 `.sha1` 校验；旧 `:3.3.3` 已不再随包）；本地缓存 `stuffs/research/lwjgl_build-3.4.3/m2/` | 原样打底，被自研 overlay 覆盖关键类 |
| LWJGL native 源码 | 同上 | BSD-3 | `ref/lwjgl3`（git clone；tag `3.4.3`，worktree `ref/lwjgl3-3.4.3`；旧 `3.3.3` 已不再随包） | 交叉编译现代**单代** 3 so；**零源码改动**（仅 OHOS 编译配置） |
| LWJGL2 native 源码 | **LWJGL**（GitHub LWJGL/lwjgl） | BSD-3 | `ref/lwjgl`（独立 clone @ `2df01dd7` = `lwjgl2.9.3-19`） | 净室重编 aarch64 `liblwjgl.so`（JNI_VERSION=19；仅一份本地补丁 `JavacFiler` 绕行） |
| gl4es | ptitSeb/gl4es | MIT | `ref/gl4es`（v1.1.7） | OHOS 交叉编（`NOX11/NOEGL/NO_INIT_CONSTRUCTOR`）+ 改名 `libgl4es.so` |
| SDL3 | libsdl-org/SDL | Zlib | `ref/SDL` worktree `ref/SDL-3.4.14`（tag `release-3.4.14`，与官方 `libSDL3.so.git` 一致） | 自研 `ohos` 视频/鼠标驱动 + 补丁 |
| shaderc / SPIRV-Cross | google/shaderc、KhronosGroup/* | Apache-2.0 | `ref/{shaderc,glslang,SPIRV-Tools,SPIRV-Headers,spirv-cross}`（按官方 natives `.git` 钉修订） | OHOS 交叉编（依赖静态并入；`SOURCE_DATE_EPOCH` 保证可复现） |
| libffi | libffi 项目 | MIT | `stuffs/research/libffi/libffi-3.8.0`（GitHub release tarball） | OHOS 交叉编译为 LWJGL core 的静态 lib |
| gson | Google gson | Apache-2.0 | Maven Central `com.google.code.gson:gson:2.13.1` | ~~shade 到 `meow.gson`（仅 launcher 用）~~ launcher 已于 2026-10-01 退役 ⇒ **gson 不再随包**（仅作 MC/Fabric/Forge 清单声明的依赖） |
| ASM（随包 9.9.1 ×5） | **OW2 ASM**（gitlab.ow2.org/asm / Maven Central） | BSD-3-Clause | Maven Central `org.ow2.asm:{asm,asm-analysis,asm-commons,asm-tree,asm-util}:9.9.1`（逐件 `.sha1` 校验；本地树对照 `stuffs/test-forge/libraries/org/ow2/asm/9.9.1/`） | **原样随包**（extras tar 的 `asm9/` 子目录）；启动期为「ModLauncher ≥10 且声明的 ASM 读不懂当前 JRE 类文件」的实例（如 Forge 1.19.4）把 ASM 指向这 5 件 |
| OpenAL Soft | kcat/openal-soft | LGPL-2.0-or-later | `ref/openal-soft`（源码；tag **1.24.3**） | OHOS 移植 + 新增 OHAudio 后端 + 导出 `ALC_SOFT_system_events` |
| FreeType | FreeType 项目 | FTL（本项目采用；双许可 FTL/GPLv2） | `ref/freetype`（源码，VER-2-13-3） | OHOS 交叉编译（zlib only） |
| oshi | oshi/oshi | MIT | `ref/oshi`（现代各版本）+ legacy 1.1（commit `4047d5be65`） | CPU 拓扑合成补丁 ×10（现代 9 + legacy 1） |
| **JRE**（自编） | **OpenJDK**（jdk.java.net 官方件 + openjdk/jdk26u 源码） | GPL-2.0-only WITH Classpath-exception-2.0 | 官方 **26.0.2.1** tar（`https://jdk.java.net/archive/`，sha256 `b96b265a…`）+ 源码 `jdk-26.0.2.1-ga`（更新仓 `https://github.com/openjdk/jdk26u` @ `d55edf1cba61…`） | **源码级自编/魔改**：`tools/jre26/`（26 lib 原地改 `.dynstr` + 自编 `libc6.so`/`libjli`/`libjvm`）；容器 openEuler 编 `libjvm`；见 `tools/jre26/README.md` |
| libc++_shared.so | LLVM libc++（OHOS NDK） | Apache-2.0 WITH LLVM-exception | OHOS NDK 工具链（构建期注入） | 无（工具链件） |
| jni.h / jni_md.h | OpenJDK | GPL+CE | 拷贝进 `meowcraftbridge/`（OHOS NDK 无 jni.h） | 原样 |
| `com.mojang.text2speech` 接口面 | Mojang（MC 客户端调用契约） | — | **我们按 MC 调用契约独立实现**（`Narrator`+`NarratorDummy` 桩） | 净室桩，无上游代码 |
| `android/util/*` | AOSP | Apache-2.0 | 早期 vendored | **已移除**（GLFW stub 改用 `java.util`） |
| 平台 GL/系统库 | Mesa(Zink)/OHOS SDK | — | 系统 | 无（平台依赖） |

### 4.1 JRE 精确对齐官方源（2026-09-13）

自编 `libjli`/`libjvm` 的源 = **官方 OpenJDK 26.0.2.1 发布所用的同一 commit**（`release` 内嵌 `SOURCE=".:git:d55edf1cba61"`）：

- **源**：更新仓 `https://github.com/openjdk/jdk26u`，tag **`jdk-26.0.2.1-ga`** → commit **`d55edf1cba61219d17565da51cd13a4d425f7c59`**（引用 commit 用 `^{commit}`，注解 tag 对象哈希不同）。26.0.x **不在**主线 `openjdk/jdk`（主线止于 26.0.0 GA）。
- **落位**：clone `ref/jdk26u`（容器自包含用）；宿主 worktree `stuffs/research/jdk26/jdk26u-src`（供 `--jdk-src` 编 `libjli`；其 `.git` 指宿主绝对路径，**不可**进容器）。
- **可复现**：`SOURCE_DATE_EPOCH=1784133400` + 固定构建目录 `$HOME/meow-jvm26`；`linux_verify_jvm_repro.sh` 2× `cmp` 一致（默认 2，`MEOW_REPRO_N` 可调高）。
- **对齐只改自编件（2026-09-13）**：该次仅自编 `libjvm`/`libjli` 变化；官方 26 lib、`libc6.so`、`modules.slim`、数据 tar 均不变 → 数据令牌当时仍 `26.0.2.1+1-7-r1`（现网用户无需重新解压数据）。
- **2026-09-27（数据 tar 变了 → 令牌升 r2）**：新增 `lib/patch/jdk.zipfs/**`（36 个 `jdk.zipfs` best-effort-chmod 类，源码级自编：`tools/jre26/{patches/zipfs_chmod_best_effort.py,linux_build_zipfs_patch.sh}`）⇒ 随包数据 tar 变为 `f17974a5…`（41,233,017 B / 71 文件），**数据令牌升 `26.0.2.1+1-7-r2`**（老 r1 用户端「须升级」重解压）。动机 = 手机用户存储（FUSE/hmdfs）拒 chmod、致 Fabric 首次 remap 崩；投放射 `--patch-module jdk.zipfs=`。

| 对象 | sha256 |
|---|---|
| 官方 JDK tar | `b96b265a4a1a36c02454148891aa58ca63303cbc2d1b7979c33b4fe99e09117b` |
| 自编 glibc `libjvm.so`（未魔改 + `MEOW_MALLOC_SLACK`，27,707,752 B） | `03ff9334767e644cf307e5a1c3f4bc2f2ab48054d0134c46bcd947b4e3f3f4b1` |
| 随包 `libjvm.so`（魔改后） | `8d8a7eeef43507d6cb66b0d6c0bc748adc06b2a60f4ca750db94808be8048464` |

> ⚠️ 以上（及 `assets-digests.txt` 全部条目）是**仓库/配方产物**的 digests；**HSP 打包时会 strip native 库**
> ⇒ `.hsp` 内副本的尺寸/哈希与之不同（预期，非篡改；实测 `libjvm` 27,707,752 → 22,264,392 B、符号 64681 → 0）。
| 随包 `libc6.so`（**不变**） | `c8b06fadd6f074b8bab3069bddb537bf503ac815575b46021b6ef05121a5a723` |
| 随包 `libjli.so` | `bedc743c54d0d9acd37a5d841963b87e79659063f5d5e4222a8433cad637d089` |
| `modules.slim`（jlink 产物，43 模块；**不变**） | `d7486973d16eccc577ac86a96531089184c69c6be284b5c712d30d7da1d8f0c0`（42,748,043 B） |
| 随包数据 tar | `f17974a51a53bbdaeecdedf0230046375664137cfdb36653425864491a877fb3`（41,233,017 B / 71 文件 = 35 基础 + 36 个 `lib/patch/jdk.zipfs/**` 补丁类；**令牌 r2**）；2026-09-13 对齐时曾为 `4f9c2b87…`（41,158,374 B / 35 文件） |
| HAP（本次 debug 签名） | `69e2ebd33b8288d41798fcb1c962a8d19dc1e2fb53db369583ceb11b3f278bda` |
| HSP（本次 debug 签名） | `e415480b03b7257bf0ea887b10194ed646fca2dba43192b79245d330e02c9e47` |

> HAP/HSP 含签名材料 → 随签名变化；其余件与签名无关。逐条实机/符号校验见 `tools/jre26/README.md`。

## 4.2 网络下载产物来源总表（2026-09-30 补）

> 目的：本会话（含 2026-09-28 起最近几轮）**所有从网络下载的产物**都能**照 URL 重下 + 逐字节复核**。
> 口径：**官方 sha1** 一律从**同一仓库同等 URL + `.sha1`**取得（`https://…/<file>.sha1`，非我们自算）；**实测 sha256/大小**用 `sha256sum` / `stat -c %s`。

| 构件（坐标 / 文件名） | 版本 | 来源 URL（完整） | 下载日期 | 官方 sha1 | 实测 sha256 | 大小 | 落盘路径 | 随包? | 校验方式 |
|---|---|---|---|---|---|---|---|---|---|
| `org.ow2.asm:asm` / `asm-9.9.1.jar` | 9.9.1 | `https://repo1.maven.org/maven2/org/ow2/asm/asm/9.9.1/asm-9.9.1.jar` | 2026-09-30 | `2ceea6ab43bcae1979b2a6d85fc0ca429877e5ab` | `6f3828a215c920059a5efa2fb55c233d6c54ec5cadca99ce1b1bdd10077c7ddd` | 126,252 B | `stuffs/research/asm-9.9.1/asm-9.9.1.jar` → extras tar `asm9/asm-9.9.1.jar` | **随包**（extras tar `asm9/` 子目录） | 下官方 `.sha1` 比对（相等）+ 与树内副本 `stuffs/test-forge/libraries/org/ow2/asm/9.9.1/*.jar` `cmp` 逐字节一致 |
| `org.ow2.asm:asm-analysis` / `asm-analysis-9.9.1.jar` | 9.9.1 | `https://repo1.maven.org/maven2/org/ow2/asm/asm-analysis/9.9.1/asm-analysis-9.9.1.jar` | 2026-09-30 | `1ab8d9316ef7a67240087919a708246c37ed1660` | `6260bffc8ec008dd1b713702c7994e2c94d188a3da5bef9e87278a16df6a7522` | 35,170 B | 同上（`asm9/`） | **随包** | 同上 |
| `org.ow2.asm:asm-commons` / `asm-commons-9.9.1.jar` | 9.9.1 | `https://repo1.maven.org/maven2/org/ow2/asm/asm-commons/9.9.1/asm-commons-9.9.1.jar` | 2026-09-30 | `ab35de4c537184a09339069f1a3b3aacf2289149` | `c2319e014ce7199f2b7f7d56d6bb991863168c3f4b6cd6c9f542a4937ef7ef88` | 75,010 B | 同上（`asm9/`） | **随包** | 同上 |
| `org.ow2.asm:asm-tree` / `asm-tree-9.9.1.jar` | 9.9.1 | `https://repo1.maven.org/maven2/org/ow2/asm/asm-tree/9.9.1/asm-tree-9.9.1.jar` | 2026-09-30 | `b6b1b3366296163b4b1f540731aad0a2baa484d8` | `0f3555096b720b820bbacab0b515589bee0200bee099bda14c561738ae837ba1` | 51,963 B | 同上（`asm9/`） | **随包** | 同上 |
| `org.ow2.asm:asm-util` / `asm-util-9.9.1.jar` | 9.9.1 | `https://repo1.maven.org/maven2/org/ow2/asm/asm-util/9.9.1/asm-util-9.9.1.jar` | 2026-09-30 | `e51f5b0ae0b0c1960687ae970a2a3434d39d8abb` | `c5ebbbeaf68126af094b42fa4800f59bc4413abd02d95b9aefad722cd257e207` | 94,643 B | 同上（`asm9/`） | **随包** | 同上 |
| Forge installer `forge-1.14.4-28.2.26-installer.jar` | 28.2.26 | `https://maven.minecraftforge.net/net/minecraftforge/forge/1.14.4-28.2.26/forge-1.14.4-28.2.26-installer.jar` | 2026-09-30 | `ffbeba315833c324e8c71091b76d8c655e778c41` | `e68a0e2d589b2954c5d109a04b80747ac8c061acabe074db1607f9c2fd7d2ce1` | 6,579,712 B | `stuffs/research/forge-support/evidence/1.14.4-28.2.26/installer.jar` | **仅取证**（不随包） | 下官方 `.sha1` 比对（相等）+ 解包内嵌两份 JSON 落盘 |
| Forge installer `forge-1.15.2-31.2.57-installer.jar` | 31.2.57 | `https://maven.minecraftforge.net/net/minecraftforge/forge/1.15.2-31.2.57/forge-1.15.2-31.2.57-installer.jar` | 2026-09-30 | `85408fff4e9fdcedc417f378618a8a6870268913` | `84fd49a743978421b26f62ac78222289fe892a46f996cf11cb5e05b7441a7773` | 6,690,572 B | `stuffs/research/forge-support/evidence/1.15.2-31.2.57/installer.jar` | **仅取证** | 同上 |
| Forge installer `forge-1.19.4-45.4.1-installer.jar` | 45.4.1 | `https://maven.minecraftforge.net/net/minecraftforge/forge/1.19.4-45.4.1/forge-1.19.4-45.4.1-installer.jar` | 2026-09-30 | `1b1ab1afdbc8b508de9374e63031c7a80f4ca7dd` | `9cc81da8f5ee2640c125a2ff3fd99ad59cd6d6f0047488f69f9443c5853be42c` | 7,252,756 B | `stuffs/research/forge-support/evidence/1.19.4-45.4.1/installer.jar` | **仅取证** | 同上 |
| Forge installer `forge-1.20.4-49.2.0-installer.jar` | 49.2.0 | `https://maven.minecraftforge.net/net/minecraftforge/forge/1.20.4-49.2.0/forge-1.20.4-49.2.0-installer.jar` | 2026-09-30 | `01615b3e329bf23b1207de18b4c6f14cd897fde5` | `3a0fc9007762da3dc01e4bad13f88b480a53ac4dd306f342064d2b92e7497fb3` | 5,535,650 B | `stuffs/research/forge-support/evidence/1.20.4-49.2.0/installer.jar` | **仅取证** | 同上 |
| Forge installer `forge-1.20.2-48.1.0-installer.jar`（额外取样 · ②/③ 切点） | 48.1.0 | `https://maven.minecraftforge.net/net/minecraftforge/forge/1.20.2-48.1.0/forge-1.20.2-48.1.0-installer.jar` | 2026-09-30 | `e15577724cc665f8f7691333c3deb73f317103d8` | `10c3f124c8c6b9c2550e0003ebf014c8d24f8ef6b4b9d76fd4619cdc6013eef6` | 5,466,576 B | `stuffs/research/forge-support/evidence/1.20.2-48.1.0/installer.jar` | **仅取证** | 同上 |
| Forge installer `forge-1.20.3-49.0.2-installer.jar`（额外取样 · ②/③ 切点） | 49.0.2 | `https://maven.minecraftforge.net/net/minecraftforge/forge/1.20.3-49.0.2/forge-1.20.3-49.0.2-installer.jar` | 2026-09-30 | `652287f19aed44ad920631c6a62a9a3ffe62fb87` | `8c6e5fcb9181259d0354bc555a13e09b212df0a5f33b2c06eb73a4cad74e6d9f` | 5,491,620 B | `stuffs/research/forge-support/evidence/1.20.3-49.0.2/installer.jar` | **仅取证** | 同上 |

> **ASM 5 件许可（实物核实，2026-10-01）**：`[license BSD-3-Clause; copyright "Copyright (c) 2000-2011 INRIA, France Telecom / All rights reserved."; jar `META-INF/MANIFEST.MF` → `Bundle-License: BSD-3-Clause;link=https://asm.ow2.io/LICENSE.txt`; Maven POM `<licenses>` → `<name>BSD-3-Clause</name><url>https://asm.ow2.io/license.html</url>`; 5 件**原样随包** ⇒ 再分发须保留版权 + 许可声明，不得用其名背书]`。许可全文（`Harmomeow-Craft-Launcher/entry/src/main/resources/rawfile/licenses/ASM-BSD-3-Clause.txt`，含 INRIA/France Telecom 版权行）与再分发义务登记于 `Harmomeow-Craft-Launcher/THIRD-PARTY-NOTICES.md` §1 表（**注意**：ASM 的 BSD-3 文本与 LWJGL 的 BSD-3 文本版权行不同，故各自独立成档）。

> 6 份 Forge installer 的来源列（逐版本完整 URL / 官方 sha1 / 实测 sha256 / 大小）**同表**；其**逐版本真件字段**（内嵌 `maven/`、`libraries`、`data` 键等）见
> `stuffs/research/forge-support/install-1.13-1.20.1/A-sample-requirements.md`（其附件表给 sha1/字节；URL/sha256 以本表为准）。

**重建的随包 extras tar（派生件；输入 = 上一版 tar 的 lwjgl jar + 5 件随包 ASM）**

- 产物（**当前随包件，2026-10-01**）：`Harmomeow-Craft-Launcher/entry/src/main/resources/rawfile/meowcraft_extras.tar.gz` —— **6 members** / **12,403,320 B** / sha256 `7c8aa392…`（全文见 [`assets-digests.txt`](assets-digests.txt)）；**`EXTRAS_VERSION` = `20261001-drop-meow-launcher`**。6 成员 = `lwjgl-3.4.3.jar`（`970dbec8…`）+ `asm9/{asm,asm-analysis,asm-commons,asm-tree,asm-util}-9.9.1.jar`（**`launcher.jar` / `gson-for-launcher.jar` 已摘除** —— 随方案 A「MeowLauncher 退役」）。
- 入参：`--base-tar`（须已不含 `launcher.jar`/`gson-for-launcher.jar`；旧件用 `--drop-prefix launcher` + `--drop-prefix gson-for-launcher` 摘除）+ `--jar lwjgl-3.4.3.jar=<built>` + 上表 5 件 ASM（`stuffs/research/asm-9.9.1/*.jar`）+ `--require lwjgl-3.4.3.jar`。
- 命令（`Harmomeow-Craft-Launcher/` 下）：
  ```
  python3 tools/lwjgl/pack_extras.py --base-tar <上一版 extras tar> --drop-prefix asm9 \
    --drop-prefix launcher --drop-prefix gson-for-launcher \
    --jar lwjgl-3.4.3.jar=stuffs/research/asm-9.9.1/base/lwjgl-3.4.3.jar \
    --jar asm9/asm-9.9.1.jar=stuffs/research/asm-9.9.1/asm-9.9.1.jar \
    --jar asm9/asm-analysis-9.9.1.jar=stuffs/research/asm-9.9.1/asm-analysis-9.9.1.jar \
    --jar asm9/asm-commons-9.9.1.jar=stuffs/research/asm-9.9.1/asm-commons-9.9.1.jar \
    --jar asm9/asm-tree-9.9.1.jar=stuffs/research/asm-9.9.1/asm-tree-9.9.1.jar \
    --jar asm9/asm-util-9.9.1.jar=stuffs/research/asm-9.9.1/asm-util-9.9.1.jar \
    --require lwjgl-3.4.3.jar --out entry/src/main/resources/rawfile/meowcraft_extras.tar.gz
  ```
- 校验方法：tar 成员数 6（`tar -tzf`），逐成员 `tar -xOf ./<member> | sha256sum` 与 `assets-digests.txt` 一致；组包器为**确定性**（gzip mtime=0 / tar mtime=0 / 成员排序），故换绝对路径不影响字节。

> **历史（v45，2026-09-30，已被上面 6 成员版取代）**：产物 = 8 members / **12,674,361 B** / sha256 `cb0c0918977b68d99e557eb0eb54bce7a8c8fd3331d7c8a37638c861025c09bd`；入参 = 上一版 tar（含 `launcher.jar` = `2c50c03b…` + 已 shade 的 `gson-for-launcher.jar` = `efedc694…`）+ `lwjgl-3.4.3.jar` + 5 件 ASM；同入参 2× 重建 `cmp` 一致。`launcher.jar` 生产链见 §3（**已退役**）。

## 5. 自主可控程度（结论）
- **Java 侧 + 原生桥 100% 自主**：ArkTS、lwjgl.jar（官方模块 + 自研 overlay）、GLFW/GL 桥、jrebridge、assets、openal、freetype、legacy LWJGL2、gl4es、SDL3、shaderc/spirv-cross、tinyfd、oshi 补丁 —— 全部**源码在仓库、本地构建**。
- **正规第三方（非血统债）**：上游 LWJGL(BSD-3) / gl4es(MIT) / SDL3(Zlib) / shaderc·SPIRV-Cross(Apache-2.0) / **ASM 9.9.1(BSD-3，随包 ×5)** / libc++_shared(NDK) —— 均为可核验官方件（gson 仍属清单依赖，但**已不随包**）。
- ~~**唯一外部历史件**：JRE~~ **已收编（2026-09-12，零黑箱）**：随包 JRE 现为「官方 OpenJDK 件 + 自编/魔改」→ **供应链可宣称全自主/可控**（见 `tools/jre26/README.md`）。
- **平台依赖**：GPU 驱动（Maleoon 916）/ SDK 库，无解、也无需自持。

## 6. 剩余风险 / 收编路线（backlog）
1. ~~**JRE 收编**（最高优先）~~ **已完成**（2026-09-12，零黑箱）：官方 26.0.2.1 件魔改 + 自编 `libc6.so`/`libjli`/`libjvm` → 供应链**全自主/可控**（见 `tools/jre26/README.md`）。
2. ~~**LWJGL 升级**~~ **已完成**（2026-09-10；2026-09-14 收敛为现代**单代 3.4.3** + 3.4.x 兼容 shim）+ OpenAL 1.24.3，**MC ≥1.22（26.1.2）实机可玩**（见 [`../20-design/lwjgl/LWJGL3世代管理-方案.md`](../20-design/lwjgl/LWJGL3世代管理-方案.md) §7）。
2b. ~~**下界 + 26.3**~~ **已完成**（2026-09-11）：≤1.16 自编 **gl4es**（GLES）、1.6.x–1.12.2 自编 **legacy LWJGL2**（`liblwjgl.so`）、26.3 自编 **SDL3** + shaderc/spirv-cross → 支持窗口 **1.6.x – 26.3** 实机可玩。
3. （可选）`vulkan` 模块再瘦（2755 类/6MB，仅 `GLFWVulkan` 链接，vanilla 不调）。
4. （可选）`GLCapabilities` 启动期 ~200 行 missing-function 日志收敛。
5. 每项完成标准：自编产物 digest 入库 + 实机回归（渲染/输入/IME/关窗）。

## 7. 指针与运行布局
- **网络下载产物来源（URL/日期/官方 sha1/实测 sha256/落盘/是否随包）**：见 §4.2。
- 逐 so 名录：[`per-so-catalog.md`](per-so-catalog.md)；SBOM/校验和：[`assets-digests.txt`](assets-digests.txt)（**v45**）。
- 运行资产：el1 `meowjre/libs/arm64/`（JRE **29**〔口径见 [`../00-current/现状基线.md`](../00-current/现状基线.md) §1：含 `libc6`/`libjli`〕 + 自研桥/jrebridge）；`meowlwjgls/libs/arm64-v8a/`（**12 so**：现代 LWJGL 单代 3（`_343`）+ legacy `liblwjgl.so` + `liblwjgl_tinyfd.so` + VMA `liblwjgl_vma.so` + SDL3 + shaderc + spirv-cross + gl4es + openal + freetype；`natives.manifest` **12 项**，tag 仅 `3.4.3` 与 `common`；旧 `_333` 三件已于 2026-09-14 移除）；
  rawfile（entry）：`meowcraft_extras.tar.gz`（**1 jar（LWJGL）+ 随包 ASM 9.9.1 ×5**：`lwjgl-3.4.3.jar`〔现代单代〕+ `asm9/{asm,asm-analysis,asm-commons,asm-tree,asm-util}-9.9.1.jar`〔子目录，启动期覆盖实例声明的旧 ASM〕；`lwjgl-3.3.3.jar` 已于 2026-09-14 退役；`launcher.jar`/`gson-for-launcher.jar` 已于 **2026-10-01** 随 MeowLauncher 退役移除；tarball **6 members，12,403,320 B，sha256 `7c8aa392…`**）+ `meow_jre.tar.gz`（JRE 数据）+ `oshi-overrides/`（**10**）。
- 设计/流程档：[`launcher净室-设计.md`](../90-archive/launcher净室-设计.md)、[`GLFW净室桥-设计.md`](../20-design/render/GLFW净室桥-设计.md)、[`LWJGL3自编-阶段1历史.md`](../90-archive/LWJGL3自编-阶段1历史.md)、`../40-adaptation/*`。
