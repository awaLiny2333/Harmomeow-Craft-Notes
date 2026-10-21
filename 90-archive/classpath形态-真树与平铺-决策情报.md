# classpath 形态：真 maven 树 vs 平铺 — 决策情报（2026-09-30）

> 已归档（2026-10-01；因为其三态 classpath 的判据与定案已并入现役档（启动链-总览 §0 / 决策与不变量 §0.3）；现役口径见 [`启动链-总览.md`](../20-design/launch/启动链-总览.md)）。

> **本文是带日期的决策情报记录（2026-09-30），不是活状态。**
> 支持面现状以 [`../../00-current/现状基线.md`](../00-current/现状基线.md) §5 第 28 条与
> [`../../00-current/版本支持边界.md`](../00-current/版本支持边界.md) 为准；限制级重开条件见
> [`../../00-current/已知限制与待解.md`](../00-current/已知限制与待解.md) §E。
> **本文只回答一件事**：什么版本 / 什么加载器走哪种 classpath 形态、机制上**为什么**、代价是什么、为什么暂不统一。
> 此前这条线只有零散段落（[`Forge-1.13及以上-调研与方案.md`](../20-design/launch/Forge-1.13及以上-调研与方案.md) §5.3/§5.5、
> 明细档 `stuffs/research/forge-support/review-2026-09-30.md`），本文把它们收拢到一处。
> **代码路径相对 `Harmomeow-Craft-Launcher/`；只引符号名（文件名 / 函数 / 常量），不写行号。**

## 0. 一句话

同一份「解析出的库清单」有两种落地形态：**平铺**（把库复制进一个平面目录、`-cp "<dir>/*"`）与
**真 maven 树**（不复制、按清单顺序逐条写 `<gameRoot>/libraries/**` 的绝对路径 + 实例 jar）。
用哪种不是偏好，而是由**启动形态主类**决定的机制问题 —— 其中 Forge 1.13–1.16.5 那一代，平铺**必然失败**。

## 1. 两种形态是什么

| 形态 | 做什么 | `-cp` 长什么样 | 实现落点 |
|---|---|---|---|
| **平铺（flat）** | 把解析出的库**复制**进一个平面目录（`cacheDir/mc-cp/<实例>/`） | 只写通配串 `<cache>/mc-cp/<实例>/*` | `common/data/ClasspathStager.ets`（落盘）；调用侧 `common/data/GameLauncher.ets` 传 `${cpDir}/*` |
| **真树（real-tree）** | **不复制**；按清单顺序把 `<gameRoot>/libraries/**` 的**绝对路径**逐条写出，末尾加实例 jar | 一长串绝对路径（对齐 HMCL 的 `${classpath}`） | `common/data/MinecraftLauncher.ets` 的 `assembleRealTreeClasspath` |

**判据 = 启动形态主类**（`common/constants/LaunchContract.ets` 的 `REAL_CLASSPATH_MAIN_CLASSES`），
另有 `loader === neoforge` 兜底；判定函数 = `common/data/MinecraftLauncher.ets` 的 `needsRealClasspath`。
它按**主类（形态）**判，不按 loader 名或 MC 版本号字符串比较（这族实例可能是薄 `inheritsFrom`、
`detectLoader` 认不出，而主类始终稳定）。

形态自证（稳定英文诊断串，设备复测时读数用）：`classpath mode=real-tree (entries=N)` / `classpath mode=flat`；
真树下另打一行 `classpath real-tree: asm=<path> (in-libraries=yes|no)`（ASM 提供者、及其是否落在
`<gameRoot>/libraries/org/ow2/asm/…` —— 即 FML 反推 maven 根所依赖的那条不变量）。

## 2. 判定矩阵（核心：什么版本、什么 loader、走什么方案、为什么）

| 版本段 / loader | 形态 | 为什么（机制，不是偏好） |
|---|---|---|
| vanilla（1.6.x–26.3，`net.minecraft.client.main.Main`） | **平铺** | 既不做"按自身位置反推"，也不做 classpath 模块化 ⇒ 真树对它**零功能收益**，却要吃长度与顺序责任 |
| Fabric / Legacy Fabric（`KnotClient`） | **平铺** | 同上；Fabric 的 loader 自行处理 classpath |
| Forge ≤1.12.2（launchwrapper `net.minecraft.launchwrapper.Launch`） | **ordered（显式有序绝对路径）** | 2026-10-01 方案 A（`MeowLauncher` 退役）后的口径：**不再有自研 system class loader**，「启动器族」（launchwrapper / FML 本体 / OptiFine）**就在 classpath 上**（不再摘出）；`-cp` 走**清单顺序逐条绝对路径 + 实例 jar**（OptiFine 置末、丢 `optifine:launchwrapper-of`）。**为什么不用通配**（2026-10-01 事故定案）：平铺 `<dir>/*` 的展开顺序 = 文件系统 `readdir`（JDK 8 无排序语义）⇒ OptiFine jar 里那份 920 B 的 `TRSRTransformation` 空壳可能先于 Forge 本体命中 ⇒ `NoSuchMethodError`。**legacy 已并入「显式列表家族」**（与 Forge ≥1.13 的 `real-tree` 同族，差别只在不补随包 LWJGL3、改用 MC 的 LWJGL2）。**（历史，方案 A 之前；2026-10-01 起作废）** 旧实现设 `-Djava.system.class.loader=meow.launcher.MeowClassLoader`、要求「平铺 `-cp` 自足」并把启动器族摘出 —— 该论证随 MeowLauncher 退役作废 |
| **Forge 1.13–1.16.5（`cpw.mods.modlauncher.Launcher`）** | **真树（充要）** | FML 的 `LibraryFinder.findLibsPath()` 取 `ClassLoader.getResource("org/objectweb/asm/Opcodes.class")` 得到 **ASM jar 路径**后连续 `getParent()` **×6** 当作 `libraries` 根，再拼 `net/minecraftforge/forge/<ver>/forge-<ver>-universal.jar` 只做 `Files.exists` 校验（`FMLCommonLaunchHandler.validatePaths`）。平铺目录里 ASM 落在任意深度 ⇒ 上溯 6 级落到**别的目录**（2026-09-30 实测为应用数据根）⇒ fatal `Missing forge!`（文件其实在盘上）。FML **不读任何 `-D`**、也不扫 `java.class.path` ⇒ **换任何深度的平铺只会错成另一个值**。2026-09-30 实机（用户设备）：真树后 1.16.5 进游戏 |
| **Forge 1.17.1–1.20.1（`cpw.mods.bootstraplauncher.BootstrapLauncher`）** | **真树** | `-p`（module path）由 json 给且经 `${library_directory}` 展开为真路径；`-DignoreList` / `-DmergeModules` 按**条目 / 文件名**消费 classpath ⇒ 需要可信、稳定、有序的条目集合；顺序确定（同一包谁赢不再随机）。2026-09-30 实机（用户设备）：1.20.1 进世界（平铺下也曾成功，但真树才让这些开关真正生效） |
| **NeoForge（同上主类；新世代 `net.neoforged.fml.startup.Client`）** | **真树** | 同上；2026-09-30 实机（用户设备）：1.20.2 / 1.21.1 / 26.x 均通过。注意 NeoForge 一直**直启加载器主类** ⇒ 其 classpath 从**不含**我们的 launcher / gson 桩件（**两件已于 2026-10-01 退役**；现所有形态亦同）—— 这也是它天然免疫 text2speech 撞包的原因 |
| Forge ≥1.20.2（③ 代 `net.minecraftforge.bootstrap.ForgeBootstrap`） | （真树）但**支持面外** | 撞包问题（模块解析 + 两个 jar 导出同一包）已登记在 [`../../00-current/已知限制与待解.md`](../00-current/已知限制与待解.md)（§E 条目）；用户 **2026-09-30 决定** Forge 支持面**截至 1.20.1** |

> **更正记录（2026-09-30 复核）**：`MinecraftLauncher.ets` 的 classpath 形态注释**曾**写成「legacy 还必须让 launchwrapper
> 留在平铺里」—— 与同文件实现（`collectJarSources` 的 filter）**相反**，系本次改动新加时**写反了**，已随本轮修正
> （当时口径 = 「启动器族必须摘出平铺，改由 `MeowClassLoader` 从真 maven 树加载」）。
> **★ 再更正（2026-10-01，方案 A：`MeowLauncher` 退役）**：上一条的「摘族 + 自研 `MeowClassLoader` + 平铺自足」
> **整套已随退役作废** —— 现 legacy 与 Forge ≥1.13 同走**显式绝对路径列表**（legacy = `ordered`、Forge ≥1.13 =
> `real-tree`），「启动器族」就在 classpath 上。`LaunchContract.ets` 不再有 `LAUNCHWRAPPER_MAIN_CLASS` 常量
> （launchwrapper 形态判据 = `MinecraftLauncher.ets` 导出的 `isLaunchWrapperMain`）。⇒ 上表 legacy 行已按此改写。

## 3. 真树的机制收益（"为什么"）

1. **位置即信息（决定性）**：加载器按**自身 jar 的物理位置**反推库根（见 §2 第 4 行）。
2. **顺序确定**：平铺通配 `<dir>/*` 的展开顺序 JVM **不承诺** ⇒ 同名类遮蔽靠运气。历史事故：随包 `gson`
   静默遮蔽 MC 声明的 `gson`，**165 个类**全从我们的 jar 加载，后靠把包 shade 成 `meow.gson` 才消除。
   真树 = **清单顺序**，与 HMCL / 官方一致。
3. **条目携带坐标**：报错与自证日志可定位到 group / artifact / version —— 新增的自证即 `classpath mode=`
   与 `classpath real-tree: asm=… (in-libraries=yes)`。

## 4. 真树的代价与缺陷（完整）

1. **没有省掉平铺的开销**：随包 `lwjgl-3.4.3.jar` 与 oshi 补丁件
   都**不在 maven 树里**，仍要从平铺目录按绝对路径取 ⇒ 真树形态是「**既复制又变长**」，两份成本都付
   （除非把 staging 改造成只物化这 2 个件，而那会动到已落地的 LWJGL / natives 握手与 oshi 覆盖）。
   （历史：`launcher.jar` / `gson-for-launcher.jar` 曾是随包件，2026-10-01 已随 MeowLauncher 退役移除。）
2. **顺序 / 去重 / 存在性的责任转到我们代码**：生成列表的一方要对顺序（同名遮蔽）、去重（基座 jar + 叶子 jar、
   清单同坐标两条如 1.16.5 的 text2speech 普通 + natives）、存在性（缺件静默跳过，现已补 warn）负责
   ⇒ 更多可错的代码面。
3. **依赖树完整且布局规范**：要求 `<gameRoot>/libraries/<group 路径>/<artifact>/<version>/<file>` 布局成立；
   异形布局（自定义 `libraries/`、手工整理过的实例）会让路径算不出来 ⇒ 静默丢库。好处是失败信号通常更清晰
   （`Missing forge!` 而非莫名 `NoClassDefFoundError`）。
4. **诊断体验**：`-cp` 变长后日志里的 `CMD:` 必然被截断（现用 `CMD_TAIL:` 续行）⇒ 事后手工核对整条命令
   不可行，只能靠自证日志。
5. **legacy 现也走真树式列表**：见 §2 第 3 行（`ordered` 显式有序绝对路径；**不再**依赖平铺 —— 「system classloader
   依赖平铺」那条旧论随 `MeowLauncher` 退役作废，legacy 已并入「显式列表家族」）。
6. **不替用户归一版本**：真树保留坐标与版本（比平铺"同名压成一份、靠运气遮蔽"更正确），但"当前在加载哪个
   版本"变成**需要读懂**的信息。

## 5. 为什么不统一（2026-09-30 决定：暂不统一）

- vanilla / Fabric **零功能收益**（不需要布局信息）；
- legacy **也走显式列表**（`ordered`；不复是「会坏」的那一类 —— 该旧论随 `MeowLauncher` 退役作废）；
- **不改 staging 就没有收益、只有成本**；
- 需要**全窗口**（1.6.x–26.3 × vanilla / Fabric / legacy / 各 loader）**设备回归矩阵**；
- ① 代在平铺下**必然失败** ⇒ **长度兜底只能对「平铺也够用」的形态启用**，不能拿平铺当 ① 代的兜底
  （那只是把一种失败换成更难诊断的一种）。

## 6. 未决与待办（如实写）

1. **`-cp` 长度上限未知**：已知 **9.7 KB / 53 条（1.16.5）** 与 **≈13 KB / 71 条（1.20.1）** 均于 **2026-09-30 记录**
   实机可用；本仓注释里「超长 `-cp` 在本 JLI 移植会失效」一直没有实测边界。**建议的最小下一步**：真树组装后
   再打一条**实际字节数**自证（`bytes=N`；现在只有 `entries=N`，且它按 `:` 切分计数）—— 是否做，用户 2026-09-30 未决。
2. **将来的统一路线（若要）**：① 加字节数自证 → ② 摸到上限 → ③ 改造 staging 只物化随包 / 补丁件 →
   ④ ~~处理 legacy 的 system classloader 依赖~~（**已随 `MeowLauncher` 退役消解**：legacy 已并入显式列表家族）→ ⑤ 全矩阵回归。
3. **一处未定论（必须如实标，不是结论）**：早先评审断言「平铺时 `-DignoreList` / `-DmergeModules` 等于**死参数**
   （`java.class.path` 只有一条通配串）」，但 1.21.1 平铺失败的取证（2026-09-30）显示 `ForgeBootstrap` 推出的模块名
   来自**文件名**（`text2speech` / `launcher`）⇒ 说明本 JLI 移植下 `java.class.path` 里的通配**已被展开成真实条目**
   ⇒ 这两个开关在平铺下究竟生效到什么程度**未定论**（可能只是"恰好不需要"）。**不要把它写成结论。**

## 7. 指针

**设计 / 调研**
- [`../20-design/launch/启动链-总览.md`](../20-design/launch/启动链-总览.md) —— 四大类型 × 逐世代的启动总表（本文 §2 的"什么版本走哪种形态"在其中与主类 / system CL / JRE 档并成一张表）。
- [`Forge-1.13及以上-调研与方案.md`](../20-design/launch/Forge-1.13及以上-调研与方案.md) —— §5.2（A/B/C 三样本实测，含 ① 代 `Missing forge!` 字节码定案）、
  §5.3（阶段 1 首改：判据收敛到启动形态主类 + `assembleRealTreeClasspath`）、§5.4（桩包来历与 text2speech 实际提供者）、§5.5（全面评审）。
- [`Forge支持-改动方案.md`](Forge支持-改动方案.md) —— §4.2「启动：classpath 形态判据从 loader 名改为形态」的历史建议；§4.3 classpath 形态与 `-p`/ignoreList 冲突。
- [`NeoForge支持-改动方案.md`](NeoForge支持-改动方案.md) —— §4.3「真 maven 树 + 按序（弃平铺）」（NeoForge 侧最早的形态裁决）。
- [`NeoForge支持-调研.md`](../20-design/launch/NeoForge支持-调研.md) —— `assembleRealTreeClasspath` 改名前的「按绝对路径去重保序」取证。
- [`桌面标准启动链路-对照.md`](桌面标准启动链路-对照.md) —— 桌面 `${classpath}` 基线（真树要对齐的参照）。

**活状态（本档不复制，只指）**
- [`../../00-current/现状基线.md`](../00-current/现状基线.md) §5 第 28 条（Forge 支持面 + 真树首改）。
- [`../../00-current/版本支持边界.md`](../00-current/版本支持边界.md)（legacy `-cp` 自补）。
- [`../../00-current/已知限制与待解.md`](../00-current/已知限制与待解.md) §E（模块化 classpath 撞包的重开条件）。

**明细档**
- `stuffs/research/forge-support/review-2026-09-30.md` —— 四路只读对抗性评审逐条（启动侧 classpath / argv 组装一路）。
