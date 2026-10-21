# 多 JRE 共存方案（草案 1）—— 第二套 el1 命名空间 + 按版本择 JRE

> 已归档（2026-10-01；因为其两套 JRE / 布局 / 选择逻辑的结论已并入现役档（环境与载体）；现役口径见 [`环境与载体.md`](../20-design/launch/环境与载体.md)）。

> 日期：2026-09-28 ｜ **修订 1 = 初稿；本轮只出方案、未动代码**。
> 触发：[`Forge支持-改动方案.md`](Forge支持-改动方案.md) §10 **R1** —— 三阶段真机取证证明 **Forge ≤1.12.2 在随包 JRE 26 上跑不了**（`ClassCastException`（launchwrapper 假设 JDK 8 的 `AppClassLoader extends URLClassLoader`）→ 修好后 `NoClassDefFoundError: ITweaker`（已修）→ 最终卡在 **`UnsupportedOperationException: Setting a Security Manager is not supported`**，即 **JEP 486（JDK 24+）永久禁用 SecurityManager，任何 flag 都无效**）。HMCL 对该段的答案正是**换 Java**（`MODDED_JAVA_8` = 1.7.10–1.16.999 要 Java 8）⇒ 本方案研究"我们怎么让多套 JRE 共存"。
> **第二轮（2026-09-28）定案**：把 `FMLTweaker` 里那一次 `setSecurityManager` 摘掉（3 字节字节码补丁，探针）后，
> 卡点推进到 coremod 注入阶段，换成 **`java.util.jar.Pack200` 缺失（JEP 367 / JDK 14 删除，`ClassPatchManager.setup` 必经）**
> ⇒ **能跑原样 Forge 1.12.2 客户端的 JDK 上限 = 13**（23/21/17/14 全部出局），而 Pack200 无法从 classpath 提供
> ⇒ **第二套 JRE 定案为 Java 8**（覆盖 ≤1.12.2 LaunchWrapper + 1.13–1.16 ModLauncher/Mixin）。
> 收编工序已落地在工作区根 `Harmomeow-Craft-Launcher/tools/jre8/`（其 README 含全部取证与实测体积）。
> 前置+原始报告（**工作区根**）：`stuffs/research/multi-jre/A-current-plumbing.md`（我方单 JRE 全链路 + 硬编码清单）、`stuffs/research/multi-jre/B-platform-constraints.md`（平台/hvigor 硬约束 + 布局候选）、`stuffs/research/multi-jre/C-hmcl-java-management.md`（HMCL 多 Java 语义 + 选择规则表）。
> 本文为**决策记录 / 方案存档**，**不复述现状**；当前状态见 [`../../00-current/现状基线.md`](../00-current/现状基线.md)。
> **不做多 JRE 的替代**：只支持 Forge 1.13+（把 ≤1.12.2 登记为"需 Java 8"）—— 见 [`Forge支持-改动方案.md`](Forge支持-改动方案.md) §10 的 D 路线。

## 0. 结论速览

1. **技术上可行，但物理上不能"合租"**：`libjli`/HotSpot 用 **`OHOS_DL_DIR` 这个扁平目录 + 裸名**（`$OHOS_DL_DIR/libjvm.so`）定位 JVM 组件，其余 JRE `.so` 靠 `LD_LIBRARY_PATH` **按文件名** dlopen ⇒ **同一个 el1 平铺目录里放两套同名 `.so` 必然互相污染**（静默命中一份）。⇒ 两套 JRE **必须各占一个 el1 目录 / 命名空间**。
2. **推荐布局 = 候选①：新增第二个 `type: shared` HSP**（如 `meowjrelegacy`），自带 `libIsolation:true` 命名空间与 `libs/arm64-v8a/`；`entry` 侧按"选中的 JRE"决定用哪个模块的 el1 目录（`hspLibsDir(<模块名>)` 已经是**按模块名寻址**，改变模块名即换目录）。**模块名必须版本中性**（`meowjre`/`meowjrelegacy`，**不要** `meowjre8`——那会被读成版本号，违反 [`现状基线.md`](../00-current/现状基线.md) §1 的命名约定）。
3. **改动面集中在我们自己的代码**（数据侧骨架已按 `id` 参数化，半就位）：**令牌单值 → 按 id 映射**、**el1 按 id 取目录**、**`PurgeStaleJreData` 会误删兄弟 id（危险，必改）**、**传参链只喂默认 id**、桥内回退字面量；native 侧**无需改 ABI**（`OHOS_DL_DIR`/`OHOS_JAVA_HOME` 本来就是参数化输入）。
4. **选择逻辑照搬 HMCL**：一张"MC 版本区间 × loader → Java 版本"的**数据驱动规则表** + "强制/建议"两档评分 + 用户覆盖（`AUTO/VERSION/DETECTED/CUSTOM`）；最低 Java 表：`≥1.13→8 / ≥1.17→16 / ≥1.18→17 / ≥1.20.5→21 / ≥26.1→25`，Forge `≤1.16.999→8`，`LAUNCH_WRAPPER ≤1.12.999→≤8`。
5. **代价量级**：每新增一套 JRE ≈ **el1 29 个 `.so`（≈32.6 MiB，HSP 打包会 strip）** + **数据 tar（≈39.3 MiB）** ≈ **单份 ~72 MiB**；构建多一个模块（`libs/**/*.so` 增删后 hvigor 不追踪 ⇒ 必须清模块 build）；部署 2 包 → 3 包；且**多出来的 HSP 由系统管理、app 删不掉**（弃用只能 `hdc shell bm uninstall -n <bundle> -m <module>`）。
   - **2026-09-28 实测修正（第二套 = JDK 8）**：官方 Temurin 8u504 的 `jre/lib/rt.jar` 里 19898 个条目**全是 STORED（未压缩）**
     ⇒ gzip 有 3.03× ⇒ **照搬**（不裁）的数据 tar = **30.8 MiB**，el1 25 件 = **20 MB** ⇒ 合计 **≈51 MiB**，
     **比 26 那一套还小**。故 §8 里"数据瘦身另做"一项**不需要**（细则见工作区根 `Harmomeow-Craft-Launcher/tools/jre8/README.md` §2.4）。
6. **Java 8 的具体门槛**（若第二套选 Java 8）：官方 OpenJDK 8 的 `libjli` 需要**移植我们那两个 patch**（`OHOS_DL_DIR`/`OHOS_JAVA_HOME`；8 的启动器源码位置与 9+ 不同），`libjvm` 侧同样要 patch；**关键待验前置 = 官方 8（glibc/aarch64）件能否按 `tools/jre26` 同法在 OHOS(musl) 上跑通**（`libc6.so` 兼容层可复用；`MEOW_MALLOC_SLACK` 那种为现代 MC 打的补丁不需要）。

## 1. 目标与范围

**目标**：让 app 内**同时携带并可选地使用多套 JRE**，由"MC 版本 + loader"选择其一，用于覆盖 **JRE 26 跑不了的段**（Forge ≤1.12.2 已证；≤1.16.999 的 `MODDED_JAVA_8` 段同理待验）。

**范围**：打包与落盘布局、令牌与升级、选择逻辑、启动期传参、UI/设置；**不含**"要不要做"的决策（那属 [`Forge支持-改动方案.md`](Forge支持-改动方案.md) §10 的 C/D 路线选择）。

## 2. 硬约束（"为什么不能合租"）

| # | 约束 | 证据 |
|---|---|---|
| C1 | **hvigor 只收 `<module>/libs/<abi>/` 顶层 `.so`**（子目录/非 `.so` 丢弃）⇒ native 必须扁平化 | `tools/lwjgl/install_natives.sh:5-10`、[`../20-design/launch/决策与不变量.md`](../20-design/launch/决策与不变量.md) §10.4 |
| C2 | **el1 路径按模块名寻址**：`<bundleCodeDir>/<moduleName>/libs/arm64/` | 主仓 `entry/.../constants/Paths.ets:118-120` |
| C3 | **`OHOS_DL_DIR` = 单一扁平目录 + 裸名**：`jvmpath = $OHOS_DL_DIR/libjvm.so`；其余 JRE 件（`libjava.so`/`libzip.so`/`libnio.so`/`libjimage.so`…）靠 `DT_NEEDED` **裸名** + `LD_LIBRARY_PATH` 命中 ⇒ **同名 .so 在搜索路径里必须唯一** | `tools/jre26/patches/libjli-ohos.patch:22-29`、`ref/jdk26u/src/java.base/unix/native/libjli/java_md.c:41`（`JVM_DLL="libjvm.so"`）、主仓 `libs/meowcraftlib/.../meowjrebridge.cpp:232-244` |
| C4 | **只有随包（el1）件能 `dlopen`**；el2/数据区件 `dlopen` 一律 `EINVAL`（fs-verity） | [`../20-design/launch/决策与不变量.md`](../20-design/launch/决策与不变量.md) §8 |
| C5 | **HSP 由系统管理，app 无法删除**（弃用一套只能 `bm uninstall -m`） | [`../20-design/launch/决策与不变量.md`](../20-design/launch/决策与不变量.md) §18、[`../../00-current/工程与规范.md`](../00-current/工程与规范.md) §二 3.1 |
| C6 | **hvigor 不追踪 `libs/<abi>/` 增删** ⇒ 增删 `.so` 后必须清模块 build 并显式 `build --modules` | [`../20-design/launch/决策与不变量.md`](../20-design/launch/决策与不变量.md) §10.4 |

⇒ **C3 是根因**：两套 JRE 的 `.so` 必须落在**两个互不重叠的搜索路径**里；C1+C2 给出的唯一自然落点就是**另一个模块的 el1 目录**。

## 3. 布局选型

| 方案 | 做法 | 改动面 | 风险 | 结论 |
|---|---|---|---|---|
| **① 多 HSP（推荐）** | 新建第二个 `type:"shared"`（+`libIsolation:true`）模块承载第二套 JRE 的 el1 `.so`；`entry/oh-package.json5` 的 `dynamicDependencies` 多加一行；`meowcraftlib`（桥）静态并入两个 HSP（各自 `SelfDir` ⇒ 各自的 `OHOS_DL_DIR`）；`hspLibsDir(<选中模块名>)` 取目录 | 新模块 4 个配置文件 + `libs/arm64-v8a/*.so`；根 `build-profile.json5` 加一行；`entry/oh-package.json5` 加一行；§4 的硬编码清单 | 模块名需版本中性；多一个常驻 HSP；部署 2→3 包 | **可行（推荐）** |
| ② 同模块 + 重命名 | 第二套 `.so` 改名（`libjvm_8.so`…）并逐个改 `.dynstr`（NEEDED+SONAME）+ 再 patch `libjli` 找新名 | 整套 JRE 配方 + 2 处额外 patch；名字长度受"新名 ≤ 旧名"约束 | JVM 内部按名加载点需穷举；最容易踩坑 | **理论可行、代价最高，不做** |
| ③ 同 HSP 放两套同名 | 两个 HAR 各带一组 `.so` 并入同一 HSP | — | **同名冲突**（构建报错/静默覆盖）+ C3 污染 | **平台不允许** |
| ④ 两 HAR → 两 HSP | 同 ①，第二套先用 HAR 承载 | 同 ① + 一层 HAR | 同 ①（无额外收益） | 等价于 ① |

**推荐 ①**，并且**模块名取语义名而非版本号**：`meowjre`（现代）+ `meowjrelegacy`（legacy 段）。⚠️ 注意与 [`现状基线.md`](../00-current/现状基线.md) §1 的"版本中性命名"约定**不冲突**——约定禁的是把**版本号**塞进模块名（`meowjre25`），不禁"按用途分模块"。

## 4. 我方"单 JRE 硬编码"清单 → 多 JRE 的逐处改法

> 来源：A 报告 §3（逐符号取证）。**数据侧骨架已按 `id` 参数化**（`Install(<id>)/scanJavaEnv 循环/JavaEnvView.install(<id>)`），所以主要工作是"把单值变成按 id 的映射/传参"。

> **实现定案（2026-09-29，已落地）——机制不是"把 id 撒满调用点"**：
>
> 1. **一套 JRE = 一个对象**：`common/data/JavaRuntime.ets` 的 `JavaRuntime` 把**必须彼此一致**的四项绑在一起
>    —— `id` / HSP 模块名 / **数据令牌** / **就绪标记**（= 数据布局事实：现代套 `lib/modules`、legacy 套 `lib/rt.jar`），
>    并自带 `home() / libsDir() / javaBin() / zipfsPatchDir() / readyPath() / tokenPath()`。
>    启动链只认"解析好的那一个" ⇒ **结构上不可能**出现"数据用 A、el1 用 B"。
> 2. **桥的模块选择只在一处**：`JvmLauncher.currentBridge()`。每个 HSP **各有一份**
>    `libmeowcraftbridge.so`（带着窗口环/surface/输入共享状态）⇒ 起 JVM 后**所有**桥调用都必须打到那个模块，
>    否则状态分家（窗口无响应/输入失效）。原先**6 处**写死的 `import('meowjre')` 已全部改走它；
>    `loadBridge()` 里那个小分支是**唯一**知道模块名的地方。
> 3. **选择策略 = 两张表的 join**：`common/data/JavaPolicy.ets` ——
>    表 A「段 → 约束（`min/max/preferred` + 依据）」× 表 B「可用 runtime（各带 `javaMajor`）」；
>    `AUTO` 交给策略，用户可覆盖（**与建议冲突只在理由里记录、不静默改**），
>    且**结果（选中的 JRE 主版本）进 UI 与启动日志（同源同一个 `resolveJavaRuntime`）** ⇒ 面板显示与日志一致；
>    **逐段 / 逐选择的理由不进 UI、只进日志**（`reasonDiag`，稳定英文诊断串）—— 面板副行是一条**静态**提示
>    `java_env_mismatch_caveat`（2026-09-29 `9a5697e` 起；原 `reasonRes` 展示层 plumbing 已删）。
>    约束**只写有证据的段**（Forge ≤1.12.2 强制上限 8）；其余一律"取最新" ⇒ **默认不改动单 JRE 时代的行为**。
> 4. **加第三套 JRE = 纯数据**：① tools 配方产出；② 新建版本中性 HSP；
>    ③ `JavaRuntime` 表加一行 + `Paths.ets` 加字符串 + native `jre_launcher.h::kJreSpecs` 加一行；
>    ④ rawfile 放 `<id>.tar.gz`；⑤（需要时）`JavaPolicy` 表加一行；⑥ `loadBridge()` 加一个分支。
>    —— **逻辑代码零改动**（UI 下拉的选项也由 `BUNDLED_RUNTIMES` 生成）。
> 5. **安装期工具 JVM 与启动路径同源解析（`JavaPolicy`）—— 不再写死现代套（2026-09-29 打通）**：
>    `:neoinstall` 的 processor **工具 JVM** 用哪套 JRE，改由主进程 `GameVersionsView.confirmInstall` 用
>    **与启动路径同一处**的 `JavaPolicy.resolveJavaRuntime` 按 **(MC 版本 × loader)** 解析出 `id`
>    （目标实例尚未创建 ⇒ 无实例覆盖、传 AUTO；`remote.id` + `LOADER_NEO_FORGE` 取自安装面板），
>    经 job（`NeoForgeProcessorJob.jreId`）传到 `NeoInstallAbility` 用**同一个 id** 起 `startJvm`；
>    就绪判据仍是同一处 `runtimeStatus`（未见第二事实源）。id 缺失（旧 job）/未知 ⇒ 回退现代套 + warn。
>    今天 NeoForge（≥1.20.2）命中表 A 的"无约束 ⇒ 取最新"分支 ⇒ 结果 **= 现代套**（行为不变）；本条的价值是
>    **打通"策略 → 安装器"这条链**：将来策略若把某段指向 legacy 套，安装器与游戏不会跑在两套 JRE 上。
>    指链：[`NeoForge支持-改动方案.md`](NeoForge支持-改动方案.md)、`entry/.../{components/GameVersionsView.ets,common/state/InstallerState.ets,common/data/VersionInstaller.ets,common/data/NeoForgeInstaller.ets,entryability/NeoInstallAbility.ets}`。
>    （遗留：legacy Forge 1.13–1.16 的 processor 工具是否也要 Java 8，属另一课题；机制现已在位。）
> 6. **桥就绪 = 显式事件，不是"读当前值"（2026-09-29 修订 2）**：第 2 条把 6 处 `import('meowjre')`
>    全改成 `currentBridge()` 后，暴露出同一类**静默跳过** —— `currentBridge()` 未选定即 `undefined`，
>    调用方若"读当前值再判空"，就会把启动早期发起的一次性注册/上报**默默丢掉**（`undefined` 表示
>    "还没选"，**不是**"失败"）。**真机事故**：`GameInputController` 的启动触屏 filter 注册
>    （`ensureTouchFilter`）被跳过 ⇒ 纯触屏设备上**鼠标不动即触屏全废**（该注册原本要等一次鼠标
>    `Move` 才被补上）。修法 = `JvmLauncher` 的**桥就绪契约**：`whenBridgeSelected()`（等"已选定"
>    事件；已选定立即兑现、选择失败 reject）+ `runWithBridge()`（未就绪则入队、`selectBridge`
>    成功后按 FIFO flush，**绝不静默丢弃**）。**契约定稿（同日评审后，含"可重臂"纠正）**：①
>    **可重臂**——就绪是"当前这一次"而非进程终态（`selectBridge` 可重试），失败**只拒当刻等待者**并
>    **立刻换一个新 promise** ⇒ 之后成功的重选仍能通知等待者；当刻无人等待时，之后任何一次
>    `whenBridgeSelected()` 由已落定的 `activeBridge` 立即兑现（否则一次失败会永久毒化契约、启动触屏
>    注册在重试路径上再次静默丢失）；② **队列有上界**（`MAX_PENDING_BRIDGE_ACTIONS=64`，满则丢最旧
>    并留痕），且**选择失败 / 启动中止时带条数丢弃**（绝不静默）——仅成功时 flush ⇒ 陈旧意图不跨会话
>    重放；③ **失败文案精确化**：`GameInputController.applyTouchFilter` 区分"桥未选定"（info，对齐
>    `bindOverlay`）与"HSP 未导出该入口 = 能力缺失"（对齐 `notifyWindowActive` 的 `?.`），不再把后者
>    误报为 "bridge unavailable"。**消费侧一律走这两者**，`currentBridge()` 降为
>    **生产侧低层读取**（`selectBridge` 之后紧邻读一次，如 surface 注入、`startJvm`）。同批修好的
>    静默点：`GameInputController.setTouchExcludeRects`（虚拟按键排除区，改走 `runWithBridge`）、
>    `JvmLauncher.notifyWindowActive`（窗口焦点，改走 `runWithBridge`）、`GameWindow.requestCloseGame`
>    （未选定桥时显式留痕而**不**入队，以免桥选定后误关刚起的游戏）、`GameInputController.bindOverlay`
>    （未选定桥时**留痕**，不再无声 `return false`）。事件源、两个入口与"读当前值
>    vs 等就绪"的判据见 `entry/src/main/ets/common/state/JvmLauncher.ets` 顶部注释。
>
> 下表为**历史清单**（逐条已实施或被上述机制吸收）：

| 优先级 | 现状（单 JRE） | 改成多 JRE |
|---|---|---|
| **P0 危险** | `jre_launcher.cpp:80-105 PurgeStaleJreData(jresRoot, keepId)` **删 `meow-jres/` 下所有 ≠keepId 的兄弟目录** | 改成**白名单**（只清"已知废弃 id"），否则装第二套会把第一套删掉 |
| **P0** | `Paths.ets:24 JRE_DATA_TOKEN`（单值）↔ `jre_launcher.h:30 kJreDataToken` ↔ `JavaEnvScanner.ets:60` 全局比较 | 令牌变 **`id → token` 映射**（三处同步；每 id 一个令牌文件 `<id>/meow_jre_data` 可沿用） |
| **P0** | `Paths.ets:119-121 hspLibsDir(bundleCodeDir)` **无 id 参数** ⇒ 所有 JRE 同一 el1 目录 | 带 **模块名/id** 参数（`hspLibsDir(bundleCodeDir, moduleName)`），由"选中的 JRE"决定 |
| **P1** | `JvmLauncher.ets:94-95`、`GameLauncher.ets:123/138/139/163`：`jreHome`/`jreLibsDir`/`zipfsPatchDir`/`bin/java` 全用**默认 id** | 一路带"本次选中的 JRE id"（接口本身够用，改的是"喂谁"） |
| **P1** | `JavaEnvScanner.ets:41 BUNDLED_JRE_IDS=[JRE_ID_MEOW]`（数组可扩，只列 1 个） | 加第二 id（扫描循环 `:49` 天然支持多 id） |
| **P1** | `meowjrebridge.cpp:230-231` 的 **javaHome/jreLibsDir 回退字面量** | 回退值与所选 id 一致（或直接去掉回退、强制传参） |
| **P2** | `Paths.ets:81 RAWFILE_MEOW_JRE='meow_jre.tar.gz'`（Install 内已按 `<id>.tar.gz` 派生） | 每个 id 自带 `<id>.tar.gz` |
| — | UI（`JavaEnvView` 的 `Repeat`、`install(env.id)`、状态/版本行） | **已通用**，多行天然支持（受 scanner 返回集限制） |

## 5. 选择逻辑（按 MC 版本 + loader 选 JRE）

**照搬 HMCL 的语义**（C 报告 §3/§7），做成**数据驱动规则表**放在我们这边（建议与 `RendererPolicy` 同层的集中策略模块，如 `common/data/JavaPolicy.ets`）：

| 规则（段 → 要求） | 依据 |
|---|---|
| 香草最低 Java：`≥1.13→8`、`≥1.17→16`、`≥1.18→17`、`≥1.20.5→21`、`≥26.1→25` | `ref/HMCL/.../game/GameJavaVersion.java:42-54` |
| **Forge**：`≤1.7.2→7`、**`1.7.10–1.16.999→8`**、`1.17→16`、`1.18–1.20.4→17`、`≥1.20.5→21` | `game/JavaVersionConstraint.java:68-107` |
| **`LAUNCH_WRAPPER`（≤1.12.999）→ `≤8`**（强制） | `:129-140` |
| `MODLAUNCHER_8`（1.16.3–1.17.1 + Forge）→ `≤17` | `:179-223` |
| 选择算法：架构过滤 → 逐条判"强制/建议" → `suggested ?: mandatory`；同档偏好"主版本最接近推荐、版本更高" | `HMCL/.../java/JavaManager.java:305-364` |
| 用户覆盖：`AUTO / VERSION / DETECTED / CUSTOM`（空值回退自动） | `setting/JavaVersionType.java:31-42`、`setting/GameSettings.java:932-993` |

**我们的落地差异**：HMCL 的 `argv[0] = java 可执行路径`，我们是**在进程内 `JLI_Launch`** ⇒ "选哪个 JRE" = "给 `JLI_Launch` 喂哪一组 `jreHome`/`jreLibsDir`（即哪套 el1 + 哪份数据）"，**参数按选定的 JRE 版本条件生成**（照搬它"按 Java 版本条件拼参数"的做法）。

## 6. 数据侧（多 id）

- 目录：`<filesDir>/meow-jres/<id>`（现状 `id = meow_jre`）——**骨架已按 id 参数化**，加 id 即可。
- **令牌**：每 id 一份（文件名 `<id>/meow_jre_data` 沿用），值形如 `<JDK 版本>+<配方版本>-rN`；**改数据必升令牌**（既有铁律）；**两个 id 各自独立**，勿共用（否则"新 el1 so + 旧数据"混合）。
- `release`：`JAVA_VERSION` 用于 UI 展示与**选择逻辑的版本判定**（`JavaInfo.parsedVersion` 同义）。
- `lib/patch/jdk.zipfs/**`：**第一套专有**（手机 FUSE 拒 chmod 的补丁），路径随 `jreHome` 传（`--patch-module jdk.zipfs=<jreHome>/lib/patch/jdk.zipfs`，存在性检查已在 `GameLauncher` 做）⇒ 换 JRE 自动跟随。
- **清理**：`PurgeStaleJreData` 改白名单（§4 P0）。

## 7. 启动链参数化

- **无需改 native ABI**：`launchJvm(filesDir, args, jreHome, jreLibsDir, …)` 已经是"喂一组路径"的形状（`JvmLauncher.ets:26-27`）；桥内 `setenv("OHOS_JAVA_HOME", javaHome)` / `setenv("OHOS_DL_DIR", jreLibsDir)` / `LD_LIBRARY_PATH = libsDir:jreLibsDir:javaHome/lib` 都是**参数化输入**（`meowjrebridge.cpp:232-244`）⇒ 多 JRE 只需**喂对的 id**。
- **注意 `LD_LIBRARY_PATH` 串味**：桥一次性把 `libsDir:jreLibsDir:javaHome/lib` 写进去 ⇒ **一次启动只应放"被选中那套"**（我们的 `:game` 是独立进程且一次只跑一个实例 ⇒ 天然满足）。
- `libc++_shared.so` 等**非 JRE** 的随包件与 JRE 的 29 个 `.so` 同目录（`meowjre/libs/arm64/`）：第二套 HSP 同样要带自己那份（或各自携带，避免跨模块依赖）。

## 8. 若第二套选 Java 8：额外工作

| 项 | 内容 | 状态 |
|---|---|---|
| 输入件 | 官方 OpenJDK **8**（aarch64/glibc）tar | 需获取（`jdk.java.net/archive` 之类；与 `tools/jre26` 同思路） |
| 收编 | 原地改 `.dynstr`（`patch_dynstr.py` 同法）+ **`libc6.so` 兼容层（可复用）** | 配方可复用；**官方 8 件能否在 OHOS(musl) 跑通未验** ← **关键前置** |
| 启动器 patch | **JDK 8 的 `libjli` 位于 `jre/lib/<arch>/jli/`**（JDK 7 起同构），源码在 8 的 `jdk/src/share/bin`（与 9+ 的 `src/java.base/unix/native/libjli` 不同）⇒ **`OHOS_DL_DIR`/`OHOS_JAVA_HOME` 两个 patch 需移植** | 待做；`JLI_Launch` 入口本身可复用（我们就是 `dlopen(libjli.so)` + `JLI_Launch`） |
| `libjvm` | 8 的 `os_linux` 需同样 patch（认 `OHOS_DL_DIR`/`OHOS_JAVA_HOME`）；若官方 8 件能直接跑则**可能不需要自编 libjvm**（`MEOW_MALLOC_SLACK` 那种为现代 MC 打的补丁在 legacy 段不需要） | 待验（能省一大块） |
| 数据 | jlink 瘦身（8 的模块系统与 9+ 不同；8 是 rt.jar + `jre/lib`，瘦身手法不同） + 数据令牌另起 | 待做 |
| 体积 | 8 的那套 ≈ 同上量级（el1 + 数据） | — |

## 9. 分期与验收

> **前置已就绪（2026-09-28）**：**JDK 8 这一套的收编本身已完成并自证**——工具链落地在工作区根
> `Harmomeow-Craft-Launcher/tools/jre8/`（shim + 自编 libjli + 容器自编 libjvm + 官方件改 dynstr + 数据打包），
> 正式产物 25 件 `.so` 全 PASS（重定位口径）、数据 tar **30.8 MiB**、el1 **21 MB**（比 26 那套更小）。
> ⇒ 下表 M0 里"官方 8 件能否在 OHOS 上跑通"这一条已由静态+符号面收敛，**真机 dlopen 仍待验**；
> M1–M4 是**应用侧**（多 id/多模块/选择逻辑）的活。

| 阶段 | 内容 | 出口判据 |
|---|---|---|
| **M0 前置验证（先做，最省）** | ① 官方 8（glibc/aarch64）件在 OHOS 上能否 `dlopen`/启动（用我们桥的 headless 路径 + 最小 class）；② 多 `dynamicDependencies`（两个 shared 模块）能否构建通过 | 两条都绿才继续；任一红则本方案按 §10 风险降级 |
| **M1 布局落地** | 新建第二 HSP（`meowjrelegacy`）+ §4 的 P0/P1 改动（令牌映射、el1 按 id、清理白名单、传参链） | 两套 JRE 可同时在设备上、各自 `release` 可读、互不干扰 |
| **M2 选择逻辑** | `JavaPolicy`（规则表 + 强制/建议 + 用户覆盖）接进启动链与 UI | 按实例自动选对 JRE（打日志自证："实例 X → JRE Y"） |
| **M3 Java 8 收编** | §8 的输入/收编/两个 patch/数据 + 令牌 | 1.12.2 Forge 进主菜单（**R1 的 B 档转正**） |
| **M4 UI/设置** | Java 环境区多实例 + 选择模式（自动/指定版本/指定路径）+ 启用禁用 | 用户可手动指定某 JRE |

**风险与降级**：R1（官方 8 跑不通 OHOS）⇒ 回到"≤1.12.2 不做"；R2（多 shared 模块的平台限制）⇒ 退到候选 ②（改名，代价高）；R3（体积/部署复杂度上升）⇒ 只在需要时**按需携带**第二套（例如仅当用户装 legacy 段实例时提示下载 —— 但那要求数据侧可下载而非随包，属另一方案）。

## 10. 证据台账

- 我方现状：[`../../00-current/现状基线.md`](../00-current/现状基线.md) §1/§2、[`../20-design/launch/决策与不变量.md`](../20-design/launch/决策与不变量.md) §8/§10.4/§18、主仓 `entry/.../{constants/Paths.ets,data/JavaEnvScanner.ets,state/JvmLauncher.ets,data/GameLauncher.ets,components/JavaEnvView.ets}`、`entry/src/main/cpp/meowassets/{jre_launcher.cpp,jre_launcher.h}`、`libs/meowcraftlib/.../meowjrebridge.cpp`、`libs/meowjre/*`、`tools/jre26/{README.md,rebuild_for_meowcraft.sh,pack_jre_data.py,patches/libjli-ohos.patch}`。
- 平台约束：`tools/jre26/patches/libjli-ohos.patch`、`ref/jdk26u/src/java.base/unix/native/libjli/java_md.c`、`tools/lwjgl/install_natives.sh`（同目录多代命名的既有先例）。
- HMCL 语义：`ref/HMCL/HMCLCore/.../java/{JavaInfo,JavaRepository,JavaRuntime}.java`、`game/{JavaVersionConstraint,GameJavaVersion}.java`、`ref/HMCL/HMCL/.../java/{JavaManager,JavaInstallTask,HMCLJavaRepository}.java`。
- 原始报告（**工作区根**）：`stuffs/research/multi-jre/A-current-plumbing.md`、`stuffs/research/multi-jre/B-platform-constraints.md`、`stuffs/research/multi-jre/C-hmcl-java-management.md`。

相关：[`安装期JVM载体-调研.md`](安装期JVM载体-调研.md)、[`Forge支持-改动方案.md`](Forge支持-改动方案.md)、[`NeoForge支持-改动方案.md`](NeoForge支持-改动方案.md)、[`../lwjgl/LWJGL3世代管理-方案.md`](../20-design/lwjgl/LWJGL3世代管理-方案.md)、[`../README.md`](../README.md)。
