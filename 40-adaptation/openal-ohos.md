# OpenAL Soft 鸿蒙适配（自编 libopenal.so）

> 日期：2026-09-09 ｜ 状态：**已实机验证**（MC 1.21.10 音频/BGM 正常）
> 相关：溯源 [`../30-supply-chain/provenance-master.md`](../30-supply-chain/provenance-master.md) §4.3、
> 逐 so [`../30-supply-chain/per-so-catalog.md`](../30-supply-chain/per-so-catalog.md) §B；
> 补丁/脚本 `Harmomeow-Craft-Launcher/tools/openal/README.md`
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 12 条](../00-current/现状基线.md)。

## 0. 一句话

外部历史件的 `libopenal.so`（OpenAL Soft 1.23.1）是「归因未复现」的预编译件。我们用**上游 1.23.1
源码 + OHOS 移植补丁自编替换**（不改用户 `.minecraft`），把它升级为「**源码级**」，音频实测正常。

## 1. 现象与目标

- **现象**：非 bug，纯自主可控诉求——该 so 为外部历史件，无本地源码树/构建配方（见溯源 §4）。
- **目标**：从上游源码自编出 drop-in 的 `libopenal.so`（同 ABI/依赖），替换后 MC 音频行为不变。

## 2. 根因/难点：上游 OpenSL 后端是给 Android 写的

- 上游 `alc/backends/opensl.cpp` 包含 `<SLES/OpenSLES_Android.h>`、用 Android simple buffer queue IID
  （`SL_IID_ANDROIDSIMPLEBUFFERQUEUE` / `SL_DATALOCATOR_ANDROIDSIMPLEBUFFERQUEUE`），并（在 `#if 0` 里）用 JNI。
- OHOS **只有** `<SLES/OpenSLES_OpenHarmony.h>` + 自己的 `SL_IID_OH_BUFFERQUEUE` / `SLOHBufferQueueItf`；
  没有 Android 头、没有 `jni.h`（NDK sysroot 内不存在）。
- 所以不是「重编」，而是**后端移植**（早期也是打补丁才跑通）。

## 3. 补丁（`tools/openal/patch_openal_ohos.py`，锚定精确替换，`__OHOS__` 守卫）

1. `jni.h` 仅在非 OHOS 引入（唯一 JNI 用法本就在 `#if 0`）。
2. 头文件：OHOS 用 `OpenSLES.h` + `OpenSLES_OpenHarmony.h`。
3. 中性别名 `MeowBufferQueueItf` / `MeowBufferQueueState` / `MeowDataLocator_BufferQueue` +
   `MEOW_SL_IID_BUFFERQUEUE` / `MEOW_SL_DATALOCATOR_BUFFERQUEUE`，OHOS 映射到 OH buffer queue，
   其它平台映射回 Android。
4. OHOS 回调多一个 `size` 参数（`SlOHBufferQueueCallback`）。
5. OHOS 创建 player/recorder 时不请求可选接口，缓冲队列随后 `GetInterface` 取（对齐官方示例）。
6. Android 专有的 stream type / recording preset 配置块在 OHOS 下编译掉。

> 契约来源：官方文档 `devecocli docs read "…/使用OpenSL_ES开发音频播放功能_C_C/using-opensl-es-for-playback"`
> （`SL_DATALOCATOR_BUFFERQUEUE` + `SL_IID_OH_BUFFERQUEUE`）；旧二进制反汇编做交叉验证。

## 4. 数据流

```
JVM 里 org.lwjgl.openal 首次用 AL → System.loadLibrary("openal")
  → /data/storage/el1/bundle/meowjre/libs/arm64/libopenal.so（我们自编）
  → OpenSL 后端 slCreateEngine → CreateAudioPlayer(SL_DATALOCATOR_BUFFERQUEUE)
  → GetInterface(SL_IID_OH_BUFFERQUEUE) → Enqueue(ring buffer) → 系统音频
```

## 5. 分发与部署

- 产物直接替换 `libs/meowlwjgls/libs/arm64-v8a/libopenal.so`（该 HAR 静态并入 `meowjre` HSP）。
- 部署：`devecocli run --module entry meowjre`（改 HSP 内的 so，**必须带上 meowjre**）。
- 用户 `.minecraft` 零改动。

## 6. 版本范围

- OpenAL Soft **1.24.3**（2026-09-10 由 1.23.1 升级，动机见 [`ohaudio-backend.md`](ohaudio-backend.md) §6：MC ≥1.22 需
  `ALC_SOFT_system_events`）。`ref/openal-soft` 有完整 git（含 1.21–1.25 全 tag）。
- 补丁器已**版本容错**（同时认 1.23.x / 1.24.x 锚点）；`rebuild_for_meowcraft.sh [tag]` 指定版本。

## 7. 复现

```sh
sh Harmomeow-Craft-Launcher/tools/openal/rebuild_for_meowcraft.sh 1.24.3    # 默认 tag 1.24.3
# 或通用脚本（路径全参数化，可独立复用）：
sh Harmomeow-Craft-Launcher/tools/openal/build_openal_meow.sh --src <源码树> --sdk-native <SDK>/native --out <目录>
```

- 三个补丁器：`patch_openal_ohos.py`（OpenSL 移植）、`patch_openal_ohaudio.py`（OHAudio 后端安装）、
  `patch_openal_events_export.py`（`ALC_SOFT_system_events` 三个函数补 `ALC_API` + 列入 `libopenal.version`）。
- 产物 sha256（strip 后，1.24.3）：`fececaeea7f785c8f47a9b4f804421b3922524f0c2df87419d21256a680b2d6c`。
  可复现前提：同 tag + 同 SDK/工具链 + 同构建路径。（历史 1.23.1 版 sha `0d6ec75c…`。）
- **实机（2026-09-10）**：1.21.10 与 **26.1.2 音频均正常**（26.x 依赖的 `ALC_SOFT_system_events` 已导出）。

## 8. 踩坑清单（按阶段，含现象/根因/修法）

### A. 构建期

1. **CMake 4.x 移除 <3.5 兼容**：`Compatibility with CMake < 3.5 has been removed`。
   → `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`。
2. **`FindOpenSL` 强制要求 Android 头**：`Could NOT find OpenSL (missing: OPENSL_ANDROID_INCLUDE_DIR)`。
   OHOS 无 `SLES/OpenSLES_Android.h`。→ 显式传 `OPENSL_INCLUDE_DIR` / `OPENSL_ANDROID_INCLUDE_DIR`
   （都指 sysroot include，头不会被用到）/ `OPENSL_LIBRARY`，让 `find_package` 通过。
3. **worktree 的 `.git` 文件触发 git 版本见证报错**：
   `ninja: error: …/openal-soft/.git/worktrees/1.23.1/index missing`（OpenAL 的
   `version_witness.txt` 步骤把 worktree 当 submodule 处理、路径拼接出错）。
   → `-DALSOFT_UPDATE_BUILD_VERSION=OFF`（只影响构建元数据，不影响功能）。
4. **零导出符号（决定性，见 §9）**：运行崩 `A core ALC function is missing`。
   → `-DHAVE_GCC_PROTECTED_VISIBILITY=0 -DHAVE_GCC_DEFAULT_VISIBILITY=1` + 构建断言导出数 > 0。
5. **上游格式串警告**：`opensl.cpp` 的 `"…0x%08x", SLresult` 在 OHOS 下 `SLresult` 是
   `unsigned long`（64 位）→ `-Wformat` 警告。仅错误路径日志，未修（不阻断）。

### B. 移植期

- OHOS 缺 Android 头 + `jni.h` → 必须移植后端（见 §2/§3），不是纯重编。
- 用 **旧二进制做 oracle** 反推补丁：`strings` 得 `SL_IID_OH_BUFFERQUEUE`、
  `llvm-objdump` 得无 `movk #0x8000`（→ 用标准 `SL_DATALOCATOR_BUFFERQUEUE` 而非 Android 的
  `0x80000001`）、回调 mangled 名含 `SLOHBufferQueueItf`（→ 3 参回调）、无 `SL_IID_ANDROIDCONFIGURATION`
  串（→ 配置块被编译掉）。比盲试可靠得多。

### C. 部署 / 打包验证期

- **meowlwjgls(HAR) 的 so 并入 meowjre(HSP)**：改 so 后必须带 `meowjre` 一起部署。
- **hvigor `DoNativeStrip` 会 `--strip-all` 重 strip** → HSP 内件的哈希 ≠ 源码树件。
  验证打包的是自编件：本地对源件跑同款 `llvm-strip --strip-all`，与 HSP 内件 `sha256` 逐字节比对
  （本次 `631a004f…` 完全一致）。
- **替换铁证**：旧件 sha `15ad72b0…` vs 新件 sha `0d6ec75c…`；另有构建独有指纹串
  `MEOW_SL_IID_BUFFERQUEUE`（旧件为 `SL_IID_OH_BUFFERQUEUE`）。

### D. 断言之坑（方法论）

- 修复后的最终产物**只构建过一次**就宣称"可复现"——被用户当场质疑，补跑 3 次干净重建 + `cmp`
  才敢下结论。教训：**可复现/一致性断言必须自证，不能凭"应该"**（见 §10）。

## 9. 零导出符号（决定性坑，通用）

- **现象**：替换后 MC 启动即崩 `java.lang.RuntimeException: A core ALC function is missing`。
- **根因**：CMake 用 `check_c_source_compiles` 探测 `__attribute__((visibility("default")))`，
  **OHOS 交叉编译下该 try_compile 链接测试误判失败**（同款小程序用 OHOS clang 手编+链接能过）→
  `EXPORT_DECL` 为空 → `-DALC_API=`/`-DAL_API=` 为空；配合 CMakeLists 的
  `CMAKE_CXX_VISIBILITY_PRESET hidden` → **库零导出**（`llvm-nm -D` 查 `alc*` = 0，旧件 = 30）。
- **修法**：显式 `-DHAVE_GCC_PROTECTED_VISIBILITY=0 -DHAVE_GCC_DEFAULT_VISIBILITY=1`
  （`check_c_source_compiles` 见 cache 已定义即跳过探测），构建脚本并断言 `alc` 导出数 > 0。
- **诊断口诀**：OHOS 交叉编译 CMake 库「符号全丢 / 运行时报 function missing」→ 先查
  visibility/export cache 变量（`HAVE_GCC_*_VISIBILITY`、`ALC_API`/`AL_API`）。
- 详见记忆 `meowcraft_ohos_crosscompile_visibility_exports`。

## 10. 经验与方法（可复用）

1. **先文档后实验**：官方 OpenSL ES 示例定契约（datalocator/IID/回调），再动手。
2. **旧二进制当 oracle**：`strings` / `llvm-objdump` 反推旧件的补丁形状，避免盲试。
3. **工具参数化 + 断言**：构建脚本路径全从参数来、可独立复用；内置"导出符号数 > 0"断言，
   把这次的坑变成永久的防回归闸门。
4. **可复现必须自证**：声称逐字节一致前，自己跑 ≥3 次干净重建 + `cmp`（不能只比哈希）。
5. **打包链路要单独验**：hvigor 会二次 strip，源件哈希 ≠ 装机件哈希；用"同款 strip 复现比对"
   证明装的是自编件。

## 11. 总结

- **结果**：`libopenal.so` 从「归因（未复现）」升级为「**源码级**」；el1 预编译 so **36 → 35**。
  > **统计口径**：此处 36→35 = 当次审计把 el1 下**所有**预编译 so 一起计数（含 JRE 历史件与各组件）；
  > 与 [`现状基线.md`](../00-current/现状基线.md) §1 的 meowjre **29 so** 口径不同——后者只数 `meowjre`
  > 模块 `libs/arm64-v8a/` 实际 `.so`（26 官方件原地 patch + 3 自编 `libc6`/`libjli`/`libjvm`）。
- **提交**：主仓 `e1efb0a`（so + `tools/openal/`）、notes `3db4ae9`/`38e01a2`。
- **工具**：`tools/openal/`（补丁器 + 参数化构建脚本 + wrapper + README）可独立复用、可复现。
- **剩余外部历史件**：30 个 JRE 预编译 so（归因未复现）。`launcher.jar` / `lwjgl.jar` 已分别净室自编（见 [`launcher净室-设计.md`](../90-archive/launcher净室-设计.md)、[`GLFW净室桥-设计.md`](../20-design/render/GLFW净室桥-设计.md)）。

## 相关

- 溯源：[`../30-supply-chain/provenance-master.md`](../30-supply-chain/provenance-master.md)、
  [`../30-supply-chain/per-so-catalog.md`](../30-supply-chain/per-so-catalog.md)
- 工具：`Harmomeow-Craft-Launcher/tools/openal/README.md`
- 记忆：`meowcraft_ohos_crosscompile_visibility_exports`、`meowcraft_verify_before_claiming`
