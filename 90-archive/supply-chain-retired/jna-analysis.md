# JNA / libjnidispatch 调研（自编 vs 摘除）

> 📦 **已归档（2026-09-09）**：JNA/libjnidispatch 已从随包剔除，本文为历史档案（非现状）。
> 现状见 [`../../30-supply-chain/provenance-master.md`](../../30-supply-chain/provenance-master.md)。

> 日期：2026-09-09 ｜ 状态：**已摘除**（自编可行但收益≈0；改摘除，2026-09-09 实机验证 F3 仍 `20x`）
> 相关：[`provenance-master.md`](../../30-supply-chain/provenance-master.md) §4.3、[`per-so-catalog.md`](../../30-supply-chain/per-so-catalog.md) §B、
> [`../40-adaptation/oshi-cpu-info.md`](../../40-adaptation/oshi-cpu-info.md)、`tools/oshi/patch_oshi.py`

## 0. 一句话

`libjnidispatch.so` 是 JNA 的 native FFI 库（实为 **JNA 5.13.0**，native ABI `6.1.6`）。
自编可行（配方已验证，~0.5–1 天）但**功能收益几乎为零**；**更优解是摘除 JNA**（前提：给 oshi 补丁加空拓扑兜底）。

## 1. 纠正三个误解

1. **"6.1.6" 是 native ABI 版本，不是 jar 版本**。该 `.so` = **JNA 5.13.0**（`build.xml: jni.major=6/minor=1/revision=6`，`jni.md5=147a998f…` 与二进制内 `getAPIChecksum` 完全一致）。
2. **`jna.jar` 不来自 HOML**，来自**用户 MC 的 libraries**（随 MC 版本走；`ClasspathStager` 平铺 `cacheDir/mc-cp/<id>/jna-<v>.jar`）。
3. **launcher 不用 oshi/JNA**（`launcher.jar` 0 引用）；真正使用者是 **MC 客户端的 oshi**（F3 CPU 行 / 崩溃报告）。`per-so-catalog.md` 旧文写的"launcher 的 oshi"是错的，已修。

## 2. 谁在用 JNA（bytecode 引用，非文件名）

| 消费方 | JNA 引用 | OHOS 上是否触发 |
|---|---|---|
| **oshi-core 6.6.5** | 237/575 类引用 `com/sun/jna.*` | **是**——`LinuxCentralProcessor.initProcessorCounts()` → `readTopologyFromUdev()` → `jna-platform` 的 `Udev` |
| MC 客户端 | `bfi`(Win)/`fsv`(mac) 两处，OS 守卫 | 否（OHOS 不进入） |
| text2speech Narrator | `FliteLibrary` 引用 JNA | 潜在（缺 `libflite.so`，未触发） |
| `launcher.jar` / `lwjgl.jar` / gson / jsr305 | **0** | 否 |

→ **OHOS 上 JNA 的唯一实际消费者是 oshi。**

## 3. 版本矩阵（决定"单文件能否覆盖"）

| MC | jna.jar | 期望 native ABI | vs 现有 6.1.6 |
|---|---|---|---|
| 1.17–1.18.1 | 5.8.0/5.9.0 | 6.1.1 | ✅ |
| 1.18.2–1.19.2 | 5.10.0 | 6.1.2 | ✅ |
| 1.19.3–1.20.1 | 5.12.1 | 6.1.4 | ✅ |
| 1.20.2–1.20.4 | 5.13.0 | **6.1.6** | ✅ 精确匹配 |
| 1.20.5–1.21.3 | 5.14.0 | 7.0.0 | ❌ |
| 1.21.4–1.21.10 | 5.15.0 | 7.0.2 | ❌ |
| 1.21.11 | 5.17.0 | 7.0.4 | ❌ |

JNA 兼容判定只看 **major 相同 + expectedMinor ≤ nativeMinor** → **一个 `.so` 覆盖不了 1.17–1.21.x**（6.x vs 7.x 两条 ABI 线）。

## 4. 现状问题（`.logs` 实证）

```
[MEOW-OSHI] initProcessorCounts failed: java.lang.Error:
There is an incompatible JNA native library installed on this system
Expected: 7.0.2 / Found: 6.1.6 (at …/meowjre25/libs/arm64/libjnidispatch.so).
```

- 1.21.10 的 `jna-5.15.0.jar` 期望 ABI 7.0.2，现有 6.1.6 → `Native` 静态初始化抛 `Error` → JNA 不可用。
- 但 patched oshi（`patch_oshi.py`）把 `initProcessorCounts()` 包在 `catch(Throwable)` 里 → 兜底 `availableProcessors()` → F3 显示 `20x KirinX90`，**游戏不崩**。
- 即：**当前 `20x` 来自异常兜底，不是真实 topology**；每启动打一堆 Error 噪音。

## 5. 自编条件（已跑通 PoC）

- 源码：`java-native-access/jna` tag **5.15.0**（native ABI 7.0.2，配 1.21.10）。
- 工具链：OHOS clang 15.0.4 + ninja/make；**无需 ant**（直接 clang）。
- JNI 头：仓库内 `Meowcraft/libs/meowcraftlib/src/main/cpp/meowcraftbridge/jni.h`（NDK sysroot 无 `jni.h`）。
- libffi：JNA 自带 3.4.4 源码，或用 HNP 预编译 `/data/service/hnp/libffi.org/libffi_3.4.4/lib/libffi.a`。
- **无需源码补丁**（JNA 不认 OHOS 但可用 `jna.boot.library.path`/`jna.nosys` 绕过）。
- PoC 断言：144 导出符号与现件一致、`getNativeVersion="7.0.2"`、`DT_NEEDED` 仅 `libc.so`、`isProtected=0`。

## 6. 自编的收益 / 解决不了什么

| ✅ 能解决 | ❌ 解决不了 |
|---|---|
| 消除版本不匹配报错（选定 ABI 线） | 全版本覆盖（需两条 ABI 线 + 按版本选择） |
| 让 JNA 在该线真正可用 | 沙箱禁 `/proc/cpuinfo`/`/sys`（F3 仍靠 `-Dmeow.cpu.chip`） |
| 自主化（去 HOML 中间人，源码级） | 缺 `libudev`/`libflite`（udev topology / Narrator 仍不可用） |
| 有升级路径 | JDK native-access 警告 |

> 关键：**即便自编成功，JNA 的 udev 路径仍会因缺 `libudev` 失败 → F3 核数依旧靠兜底**。自编**功能收益≈0**，主要是"自主化"意义。

## 7. 更优解：摘除 JNA

- 仅 oshi 用 JNA；`20x` 本就不靠它。
- **前提补丁**：`tools/oshi/patch_oshi.py` 让 `initProcessorCounts()` 在 **topology 为空时也**返回 `availableProcessors()` 兜底（现在只在异常时兜底）。
- **最小摘除**：删 `libs/meowlwjgl3/libs/arm64-v8a/libjnidispatch.so`（`jna.jar` 来自用户 `.minecraft`，不随包）→ 零功能损失。
- **彻底摘除**：再补两处 `com.sun.jna.Platform` 引用（`SystemInfo.<clinit>`、`AbstractCentralProcessor.createProcessorID`）+ 过滤 `jna*.jar`。

## 8. 结论

**不自编；先给 oshi 加空拓扑兜底，再摘除 `libjnidispatch.so`**（要更彻底再摘 `jna.jar`）。这样既去掉一个黑箱，又不引入新构建链。

## 相关

- 溯源：[`provenance-master.md`](../../30-supply-chain/provenance-master.md) §4.3、[`per-so-catalog.md`](../../30-supply-chain/per-so-catalog.md) §B
- oshi 适配：[`../40-adaptation/oshi-cpu-info.md`](../../40-adaptation/oshi-cpu-info.md)
- 补丁：`Meowcraft/tools/oshi/patch_oshi.py`
