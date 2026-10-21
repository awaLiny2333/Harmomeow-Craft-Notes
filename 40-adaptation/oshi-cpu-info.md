# oshi CPU 信息鸿蒙适配（魔改 oshi-core）

> 日期：2026-09-09 ｜ 状态：**已实机验证**（MC 1.21.10 → F3 显示 `20x KirinX90`）
> 相关：[`../90-archive/supply-chain-retired/patchjna-agent.md`](../90-archive/supply-chain-retired/patchjna-agent.md)（历史：patchjna 曾做同类
> oshi/JNA 适配，已退役）、[`../00-current/已知限制与待解.md`](../00-current/已知限制与待解.md)
> 补丁/脚本：主仓库 `Harmomeow-Craft-Launcher/tools/oshi/README.md`（含工具集 README）
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 13 条](../00-current/现状基线.md)。

## 0. 一句话

鸿蒙沙箱禁读 `/proc/cpuinfo`、`/sys/devices/system/cpu`，导致 MC 的 F3 CPU 行显示 `<unknown>`。
我们用**自编 patched `oshi-core-6.6.5.jar`** 替换 MC 的库（**不改用户 `.minecraft`**），让 oshi 认
ArkTS `deviceInfo.chipType` + JVM 核数，F3 显示 `20x KirinX90`。

## 1. 现象与根因

**现象**：F3 屏 `CPU: <unknown>`。

**根因链**（反汇编 MC 的 `com/mojang/blaze3d/platform/GLX._getCpuInfo()` 得到）：

```
GLX._getCpuInfo()  →  getProcessorIdentifier()      （oshi 惰性 supplier: cpuid.get()）
                         ↑ 但 AbstractCentralProcessor 构造先调 initProcessorCounts()
```

- `initProcessorCounts()` 在 OHOS 上读 sysfs / udev / cpuinfo → 全部 `Permission denied` → 抛异常。
- 异常使 `LinuxCentralProcessor` **构造失败** → `_getCpuInfo()` 的 catch → 保留默认 `<unknown>`。
- 因此 `queryProcessorId()`（真正取名的地方）**从未被调用**。

`GLX._getCpuInfo()` 反汇编要点：默认写 `<unknown>`，`try { String.format("%dx %s",
getLogicalProcessorCount(), getProcessorIdentifier().getName().replaceAll("\\s+"," ")) } catch { 保持
<unknown> }`，结果缓存到静态字段 `cpuInfo`。

**关键实测（设备）**：
- `hdc shell cat /proc/cpuinfo` → **Permission denied**；`hdc shell ls /sys/devices/system/cpu/` 同。
- 官方"如何获取设备的 CPU 信息" = `hdc shell param get const.product.cpu.abilist`（**ABI 列表，非型号**）。
- ArkTS `@ohos.deviceInfo.chipType`（**API 21+**）= 当前设备 CPU 芯片型号（本机 `KirinX90`）；
  C/NAPI `deviceinfo.h`（27 个 `OH_Get*`）**无** chipType → 仅 ArkTS 侧可取。

## 2. 补丁（`tools/oshi/patch_oshi.py`，结构感知，跨版本）

源码位置跨版本一致：`oshi-core/src/main/java/oshi/hardware/platform/linux/LinuxCentralProcessor.java`。
但两处补丁的**锚点行随版本变化**，所以用 **Python 结构感知补丁器**（按方法名 + 花括号配对注入），
而不是行级 `.patch`。两处改动：

1. **`queryProcessorId()`**：在 `return new ProcessorIdentifier(cpuVendor, cpuName, ...)`（跨版本稳定锚点）
   之前注入：`-Dmeow.cpu.chip` 非空时用它作 `cpuName`。
2. **`initProcessorCounts()`**：**整体替换为合成拓扑**——用
   `Runtime.getRuntime().availableProcessors()`（尊重 `-XX:ActiveProcessorCount`）构造 N 个 `LogicalProcessor(i,i,0)`。
   OHOS 沙箱里 sysfs/udev/cpuinfo 全不可读，故**无条件合成**；这样结果**不依赖 JNA/libudev 是否存在**
   （2026-09-09 摘除 `libjnidispatch.so` 后仍稳，F3 仍 `20x`）。**返回类型跨版本有 4 种**，合成生成器自动识别并生成对应合成：

   | 版本段 | `initProcessorCounts` 返回类型 |
   |---|---|
   | 5.7.x / 5.8.x | `List<LogicalProcessor>` |
   | 6.2.2 | `Pair<List<LogicalProcessor>, List<PhysicalProcessor>>` |
   | 6.4.5 / 6.4.10 | `Triplet<…, List<ProcessorCache>>` |
   | 6.6.5 / 6.9.0 | `Quartet<…, List<String>>` |

> `libjnidispatch.so` 已于 2026-09-09 摘除（JNA 不再随包）；该合成拓扑不依赖 JNA。

> 为什么锁 6.6.5 起步：MC 1.21.10 的版本 json 依赖 `com.github.oshi:oshi-core:6.6.5`。

## 3. 数据流（端到端）

```
ArkTS deviceInfo.chipType = "KirinX90"        [GameLauncher.readCpuChip()，:game 进程]
  → argv -Dmeow.cpu.chip=KirinX90              [MinecraftLauncher]
  → oshi 补丁读该属性                            [LinuxCentralProcessor.queryProcessorId()]
  → GLX._getCpuInfo() = "%dx %s"               [getLogicalProcessorCount() x getName()]
  → F3: 20x KirinX90
```

- 核数来自 `Runtime.availableProcessors()`（= `sysconf(_SC_NPROCESSORS_ONLN)`，本机 20），
  与高级选项的 CPU 线程数**同步**（因为 `-XX:ActiveProcessorCount` 会影响它）。
- `-Dmeow.cpu.chip` 由 `:game` 进程的 ArkTS 侧读取（`GameAbility` 配 `"process": ":game"`，是 ArkTS 进程）。

## 4. 分发（不改用户 `.minecraft`）

- 自编 jar 随包：`entry/src/main/resources/rawfile/oshi-overrides/`（各版本 `oshi-core-<v>-meow.jar`
  + `manifest.txt`，每行 `<staged jar>=<覆盖件 jar>`）。
- `ClasspathStager.stageClasspathDir()` 平铺完成后调 `applyOshiOverrides()`：读 `manifest.txt`，
  逐行用 `resourceManager.getRawFileContentSync()` 读出覆盖件并**覆盖** `cacheDir/mc-cp/<key>-<id>/<staged jar>`。
  → **版本无关**：新增版本 = 多放一个 jar + 一行 manifest，ArkTS 代码不动。
- 用户 `.minecraft` 零改动；构建脚本只**只读**用户库里的 `jna`/`slf4j` 当编译 classpath。
- 覆盖写入只写 `Uint8Array` 有效区间（`buffer.slice(byteOffset, byteOffset+byteLength)`）——
  直接写 `.buffer` 可能因缓冲区更大而写出损坏 jar（曾踩坑）。
- 构建：`tools/oshi/rebuild_for_meowcraft.sh <oshi-version>...`（纯 `javac`，无 Maven / 无联网；需 JDK 9+）。
  通用脚本 `tools/oshi/build_oshi_meow.sh` 路径全从参数来（`--oshi-repo/--minecraft/--cache/--out`），
  可独立复用；每个版本 `git worktree add <tag>` → `patch_oshi.py` → `javac` → `jar` → 落 out + 追加 manifest。

## 5. 版本范围（1.17 及以后全部 release，实测 BMCLAPI）

oshi 版本 ∝ MC 版本。**1.17 起 33 个 release 只对应 9 个 oshi 版本**（2026-09-09 实测，数据源
`https://bmclapi2.bangbang93.com/mc/game/version_manifest_v2.json` + `/version/<v>/json`）：

| oshi | MC release |
|---|---|
| **6.9.0** | 26.2, 26.1.2, 26.1.1, 26.1, 1.21.11 |
| **6.6.5** | 1.21.10, 1.21.9, 1.21.8, 1.21.7, 1.21.6, 1.21.5, 1.21.4 |
| **6.4.10** | 1.21.3, 1.21.2, 1.21.1, 1.21, 1.20.6, 1.20.5 |
| **6.4.5** | 1.20.4, 1.20.3, 1.20.2 |
| **6.2.2** | 1.20.1, 1.20, 1.19.4, 1.19.3 |
| **5.8.5** | 1.19.2, 1.19.1, 1.19, 1.18.2 |
| **5.8.2** | 1.18.1, 1.18 |
| **5.7.5** | 1.17.1 |
| **5.7.4** | 1.17 |

- 1.16.5 及更早**不依赖 oshi**（无此问题）。
- `ref/oshi` 是**完整 git 仓库（208 个 tag）**，9 个版本源码都在 → 逐版本编译**脚本化**（见 §4）。
- 无覆盖件的版本**优雅降级**为 `<unknown>`（回到上游行为，不崩）。
- **备选（未采纳）**：
  - 自写 `-javaagent` 运行时改字节码（零新增产物，但 oshi 内部结构一变就得改 transformer，维护成本更高）；
  - app 内用 JRE 自带 `jdk.compiler` 运行时编译（`lib/modules` 含该模块），同样要按版本取源码。

## 6. GPU（同类问题的另一半）

| 位置 | 来源 | OHOS 现状 |
|---|---|---|
| F3 `GPU:` 行 | **OpenGL 字符串**（`GlStateManager._getString`，**非 oshi**） | ✅ 正确（Mesa Zink → Vulkan → Maleoon 916） |
| 崩溃报告 `Graphics Card #N` | **oshi** `getGraphicsCards()` → `lspci -vnnm` / `lshw` | ❌ 空（OHOS 无 lspci/lshw） |

- MC 的 `SystemReport`（`ae.class`）用 `oshi.hardware.GraphicsCard`。
- oshi Linux 实现：`LinuxGraphicsCard.getGraphicsCards()` 跑 `lspci`，空则 `lshw`。
- 若要修（**优先级低于 CPU**，仅崩溃报告可见）：同套路 `-Dmeow.gpu.*` +
  patch `LinuxGraphicsCard.getGraphicsCards()`。**当前不做**，记录备查。

## 7. 环境事实（编译能力，供后续适配参考）

- **本机 shell 跑不了 JVM**：`Failed to mark memory page as executable`（mmap-exec/seccomp 受限，
  `-Xint` 同样失败）→ agent 侧无法 `javac`。
- **用户 shell 可跑** BiSheng JDK 17.0.13（`javac`/`jar` 可用）→ **Java 编译由用户执行，agent 出脚本/命令**。
- **C/C++ agent 可自编**：`clang` 15.0.4（target 已是 `aarch64-unknown-linux-ohos`）+ `cmake` 4.1.2 +
  `ninja` 1.13.1 + OHOS SDK `native/llvm/bin` + `sysroot` → native 自编无需用户。
- app 自带 JRE **无** `bin/javac`，但 `lib/modules`（jimage）含 `jdk.compiler`。
- 本地无 `mvn`/`gradle`/`ant`；有 `python3`/`unzip`/`zip`/`curl`。

## 8. 复现步骤

```sh
# 1) 编译全部 9 个版本（用户在可跑 JVM 的 shell 执行；脚本内部 worktree+patch+javac+jar）
sh Harmomeow-Craft-Launcher/tools/oshi/rebuild_for_meowcraft.sh 5.7.4 5.7.5 5.8.2 5.8.5 6.2.2 6.4.5 6.4.10 6.6.5 6.9.0
# → Harmomeow-Craft-Launcher/entry/src/main/resources/rawfile/oshi-overrides/oshi-core-<v>-meow.jar + manifest.txt
# （通用脚本 tools/oshi/build_oshi_meow.sh 需显式传 --oshi-repo/--minecraft/--cache/--out）

# 2) 部署
devecocli run --module entry
```

## 相关

- 溯源：`../30-supply-chain/provenance-master.md`、`../90-archive/supply-chain-retired/patchjna-agent.md`
- 待解：`../00-current/已知限制与待解.md`
- 脚本/补丁：主仓库 `tools/oshi/patch_oshi.py`、`tools/oshi/build_oshi_meow.sh`

## legacy：oshi 1.1（MC 1.16.x，2026-09-11 补）

- MC **1.16.x** 用 `oshi-project:oshi-core:1.1`（2015 年，**老 API**：`HardwareAbstractionLayer.getProcessors()`（复数）→ `Processor.getName()`），
  与本工程先前覆盖的**现代 oshi（5.7.4–6.9.0）不兼容**（现代是 `getProcessor()` 单数 + `oshi/hardware/platform/linux/LinuxCentralProcessor`；
  直接替换 → MC `NoSuchMethodError`）。
- aarch64 的 `/proc/cpuinfo` **没有 `model name` 行** → 老 oshi 的 `getName()` 恒为 `null`（F3 显示 `<n>x null`）。
- 修法（`tools/oshi/patch_oshi_legacy.py`）：`CentralProcessor.getName()` 返回 `-Dmeow.cpu.chip`；
  `LinuxHardwareAbstractionLayer.getProcessors()` 核数回落 `Runtime.availableProcessors()`（修掉 `<n>x`）。
- 1.1 **无 tag / Maven Central 也无该版** → 源码用 git commit `4047d5be65`（2015-01-08，1.1 版 jar 构建日前最近提交）；依赖 JNA **3.4.0**。
- 构建：`sh tools/oshi/rebuild_legacy_for_meowcraft.sh`（**javac 由人跑**）；manifest **就地追加** `oshi-core-1.1.jar=oshi-core-1.1-meow.jar`
  （现代脚本已改为合并、不再清空 manifest）。
- 结果：1.16.5 F3 = **`20x KirinX90`**。工具说明见 `tools/oshi/README.md` §2.6。
