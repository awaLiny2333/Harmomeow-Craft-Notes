# patchjna_agent.jar 解剖 + 自研可行性

> 📦 **已归档（2026-09-09）**：`patchjna_agent.jar` 已从随包剔除，本文为历史档案（非现状）。
> 现状见 [`../../30-supply-chain/provenance-master.md`](../../30-supply-chain/provenance-master.md)。

> ⚠️ **已退役（2026-09-09，commit `012a530`）**：A/B 实测**摘掉后游戏正常运行**（无致命错误），
> 且 oshi CPU 信息本就是 `<unknown>`、不影响 `-XX:ActiveProcessorCount`/性能 → 已从
> `meowcraft_extras.tar.gz`、staging 白名单、启动参数中**全部移除**。本文保留为解剖档案。

> 日期：2026-09-09 ｜ 对象：随包 `meowcraft_extras.tar.gz` 内的 `patchjna_agent.jar`（16,693B）
> 关联：`provenance-master.md` §3/§4.3、`../00-current/已知限制与待解.md` §D

## 0. 结论先行

- 它是一个 **`-javaagent` 类替换器**（`ClassFileTransformer`），**不提供任何 .so**。
- 机制极简：命中两个类名 → 返回内嵌的"替换类字节"，其余原样放行。
- **自研 agent 外壳：完全可行、几十行、drop-in**（同样 `-javaagent:` 挂载）。
- **"完全自主可控"的关键不在外壳，而在两份补丁类字节**——要么自持编译版，要么重建 JNA/oshi。

## 1. 解剖（实测）

```
META-INF/MANIFEST.MF            Premain-Class / Agent-Class = net.kdt.patchjna.PatchJNAAgent
net/kdt/patchjna/PatchJNAAgent.class   2116B  agent 本体
com/sun/jna/Platform.class.patch       6903B  替换字节（重编译的 Platform.java）
oshi/hardware/platform/linux/LinuxCentralProcessor.class.patch  21738B  替换字节
```

`PatchJNAAgent` 行为（常量池证据）：
- `premain(args, inst)`：打印 `PatchJNAAgent: premain called` → `inst.addTransformer(t)`。
- `transform(loader, className, ...)`：
  - `className == "com/sun/jna/Platform"` → 打印 `Replacing Platform.class` → 返回 `com/sun/jna/Platform.class.patch` 的字节；
  - `className == "oshi/hardware/platform/linux/LinuxCentralProcessor"` → 同理返回对应 patch；
  - 其它 → `null`（不改）。

两份补丁类：
- **JNA `Platform`**：改 `osType`/`ARCH`/`isAndroid`(dalvik)/`jna.prefix`/`getNativeLibraryResourcePrefix` 等平台检测（鸿蒙 musl 适配）。
- **oshi `LinuxCentralProcessor`**：改 `/proc/cpuinfo` 解析、`/sys/devices/system/cpu/` 拓扑、udev 枚举、CPU 频率/缓存识别（鸿蒙 CPU 识别适配）。

## 2. 为什么需要它

`launcher.jar` 用 **oshi**（系统信息）→ 依赖 **JNA**（本地调用）。鸿蒙上 JNA 的平台检测 / oshi 的 CPU 解析会误判或失败；patchjna 在类加载期把这两类换成适配版。已启用（对齐 HOML，日志三连证生效）。

## 3. 「JNA 重建课题」是什么

- 现状：`libjnidispatch.so` = HOML 转手的 **JNA 6.1.6**（musl），jar 期望 **7.0.2** → Narrator 报 `Expected 7.0.2 / Found 6.1.6`（**仅噪音，非致命**）。
- 课题：**从 JNA 上游源码按 OHOS aarch64-musl 自编** `libjnidispatch.so`（版本对齐 7.0.2）。
- 收益：① 消版本噪音；② 有机会淘汰 `patchjna_agent.jar`；③ `libjnidispatch.so` 从"归因级"升到"源码级"。
- 难点：JNA 构建链（ant + 交叉 sysroot + musl）。
- ⚠️ 注意：patchjna 改的是 **JNA/oshi 的 Java 类**；重建 **native** 不一定自动消掉它——需确认重建后的 **Java 侧**也不再误判鸿蒙。

## 4. 自研可行性（回答"能不能自己实现一个直接接上就用"）

**能，但要分清两层：**

| 层 | 能否自研 | 说明 |
|---|---|---|
| **agent 外壳** | ✅ 很容易 | 自写 `Premain-Class` + `ClassFileTransformer`，按类名返回内嵌字节；挂载方式不变（`-javaagent:`）。**drop-in。** |
| **两份补丁类字节** | ⚠️ 需要自持 | 直接用 HOML 的 `.patch` = 仍非自主。要自主须：fork 上游 `Platform.java` + `LinuxCentralProcessor.java`，落鸿蒙适配改动，**自己编译**。 |

**要自主，先得知道改了什么**：把 HOML 的两份 `.patch` 反编译，与上游 JNA/oshi 同版本源码 **diff**，把差异重写进我们的 fork（或用 `disasm.py` 逐方法比对）。这是真正的工作量。

**替代方案（可能更省）**：
- **classpath 覆盖**：把自编的 `com/sun/jna/Platform.class` + `oshi/.../LinuxCentralProcessor.class` 放进一个**排在前面的 jar**，让 JVM 优先加载 → 连 agent 都不需要。代价：受 `PojavClassLoader`/classpath 顺序约束，需实测。
- **重建 JNA/oshi**（§3）：从源码修鸿蒙适配，最彻底。

**前置验证（建议先做）**：A/B 摘掉 `patchjna_agent.jar` 跑一局，看 JNA/oshi 是否真的会崩或误报——若不影响原版 1.21.10，可能**根本不需要**这个补丁。

## 5. 后续（2026-09-09）：JNA tmpdir 只读警告已修

退役 patchjna 后，oshi 走 Udev → 加载 JNA → 会触发 `JNA temporary directory ... is not writable`
（MC 版本 json 的 `-Djna.tmpdir=${natives_directory}` 指向只读 el1，覆盖了我们设的可写目录）。
修法（commit `a5d9296`）：在版本 json 参数**之后**再补 `-Djna.tmpdir=<runDir/natives>`（JVM 后者胜出），
`java.library.path` 仍保持 el1。实测警告归零。
> 残留：`WARNING: java.lang.System::load ... unnamed module`（JDK 原生访问提示，JNA 引起，修复前后都有，非致命）。

## 6. 补记（2026-09-09）：oshi 的 CPU 型号数据源其实存在（ArkTS）

前文"oshi CPU 信息本就是 `<unknown>`"只说明**现状**，不代表**无解**：鸿蒙 ArkTS 侧
`@ohos.deviceInfo` 的 **`chipType`（API 21+）= 当前设备 CPU 芯片型号**（C/NAPI `deviceinfo.h` 无此函数，仅 ArkTS）。
`GameAbility` 配 `"process": ":game"` → 游戏进程是 ArkTS 进程，可直接读该值。

要接进 MC 仍差两步：① ArkTS 读 `chipType` → 以 `-D...` 传入 JVM（argv 由 `MinecraftLauncher` 组装）；
② 注入 oshi（它不认自定义属性）：替换/覆盖 `oshi-core-6.6.5.jar`（用自编 OHOS 适配版）或自研 agent。
收益仍主要是 F3 屏 / crash report 观感；附带 `performanceClass`（API 19+）可用于自适应默认。

**已完成（Step 1-3）**：`GameLauncher.readCpuChip()` 在 `:game` 进程读 `deviceInfo.chipType` →
`-Dmeow.cpu.chip=<值>` → 自编 patched `oshi-core-6.6.5.jar` 随包覆盖 staged jar。实机验证：
MC 1.21.10 F3 显示 **`20x KirinX90`**。完整设计见 [`../40-adaptation/oshi-cpu-info.md`](../../40-adaptation/oshi-cpu-info.md)。

## 7. 相关

- 依赖分级：`provenance-master.md` §4（patchjna = 半可控；libjnidispatch = 归因）
- 待解清单：`../00-current/已知限制与待解.md` §D
- 反编译工具：`stuffs/research/pojav/pojav_decomp/disasm.py`
