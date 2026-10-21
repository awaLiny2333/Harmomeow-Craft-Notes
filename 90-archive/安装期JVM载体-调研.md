# 安装期「无感」JVM 载体调研 —— JVM 到底绑什么 / native 子进程 vs 无窗 UIAbility（证据存档）

> 已归档（2026-10-01；因为其载体结论（无窗 :neoinstall UIAbility）已并入现役档（环境与载体 §4）；现役口径见 [`环境与载体.md`](../20-design/launch/环境与载体.md)）。

> 日期：2026-09-15 ｜ 定位：**证据存档 / 调研结论**，**不复述现状**（能力现状见 [`../../00-current/现状基线.md`](../00-current/现状基线.md)）。
> 触发：安装 NeoForge 需**反复起 JVM**（1.20.2–1.21.x 每次 6 个 processor；26.x 1 个），要尽可能「无感」（不闪窗、不占任务栏、不打扰主 UI）。
> 方法：三路子 agent（平台进程/Ability 模型 + native 子进程专项 + 我方代码耦合测绘）。证据 = 官方文档 documentId / 本地 SDK 头文件:行 / 本仓代码:行。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 22 条](../00-current/现状基线.md)。

---

## 0. 结论速览

1. **JVM 硬绑「进程」，不绑窗口、不绑 ability 实例**：HotSpot 一进程一 JVM（二次 `JLI_Launch` 必败）；而「进程 ↔ ability」是 OS 规则——进程随其内**第一个 ability 启动**而创建、随其内**所有 ability 退出**才销毁；进程名由 `module.json5` 的 `process` 字段**静态**决定。
2. **现在「JVM 跑在 `:game`（带 `GameWindow` 的 UIAbility 进程）」纯属实现选择**：`launchJvm` 本体**零窗口依赖**（surface 走另一条 `setGameSurface` 通路）。
3. 真正挡路的只有三处**实现约束**（不是平台硬绑定）：① `rendererSo`/`rendererEnv` 为空即 `abort`；② 无条件预 `dlopen` 渲染器 + 注入 GL/Mesa env；③ ArkTS 侧 `jvmStarted` 单例守卫 + native `_exit` 语义 ⇒ **安装 JVM 必须放独立进程**。
4. **两条官方正规的「无感」路**：
   - **A. Native 子进程**（`OH_Ability_StartNativeChildProcess`）：系统明示**不支持 UI 界面、不支持 Context 接口** ⇒ 物理无窗、无任务栏、无 ability 生命周期。**最无感**；唯一命门是「新进程能否 `dlopen` 我们 HSP 里的 JRE `.so`」（2026-09-15 登记，尚待 POC）。
   - **B. 独立进程 UIAbility + `startupVisibility=STARTUP_HIDE`**（2in1/Tablet 专属）：文档明示「窗口不显示、dock 无图标、`onForeground` 不回调」。**最稳**（完整复用现有 `import('meowjre')` + HSP 内 `dlopen` 链路）；未知是「是否真零闪帧」。
5. 排除/不宜：主进程内起 JVM（会冻 UI、`exit` 杀主进程）；`startAbilityByCall` 真无窗（**三方不可用**，仅系统内）；`ServiceExtensionAbility`（三方不可用）；`AppServiceExtensionAbility`（需 ACL，仅企业）；`WorkSchedulerExtensionAbility`（单次 ≤2min，系统调度）；`TaskPool`/`Worker`（同进程，无法隔离 `exit`）。

---

## 1. 绑定关系（证据）

| 绑定 | 性质 | 证据 |
|---|---|---|
| JVM ↔ 进程 | **硬**（一进程一 JVM） | 现有代码已按此设守卫：`JvmLauncher.ets:56,67-71`「进程内只能起一次」；`JLI_Launch` 结束后桥 `_exit`（`meowjrebridge.cpp:450-458`） |
| 进程 ↔ ability | **OS 规则**：进程内所有 ability 退出后进程才销毁；进程名由 `module.json5` 的 `process` 静态决定 | 文档 `process-model-stage`；本仓 `module.json5:65` `"process": ":game"` |
| JVM ↔ 窗口/surface | **无绑定** | `launchJvm` 全程不碰 surface（surface 由 `setGameSurface`/`resizeGameSurface` 单独注入，`meowjrebridge.cpp:490,531`） |
| 多进程支持面 | 2in1/PC 与 Tablet 支持多进程/子进程；**手机不允许三方应用多进程甚至 fork** | FAQ `faqs-ability-34`/`faqs-ability-29`/`faqs-ability-112` |

**我方真正的耦合点**（去掉窗口后挡路的）：`rendererSo/rendererEnv` 必填（`meowjrebridge.cpp:166-177`）、预 dlopen 渲染器（`:298`）、GL env 注入（`:229-284`）、`startJvm` 形参是 `UIAbilityContext`（实际只用 `filesDir`/`bundleCodeDir`，`JvmLauncher.ets:74-75`）、`jvmStarted` 单例（`:56`）。`-Dorg.lwjgl.opengl.libname` 自检（`:416-428`）只在 argv 含该 flag 时触发 ⇒ processor 主类天然绕过。

---

## 2. 候选 A：Native 子进程（最无感）

**API**（头文件 `native/sysroot/usr/include/AbilityKit/native_child_process.h`，库 `libchild_process.so`）：

| 接口 | @since | 头文件行 |
|---|---|---|
| `OH_Ability_CreateNativeChildProcess(libName, cb)` | 12 | :278-280 |
| `OH_Ability_StartNativeChildProcess(entry, args, options, &pid)` | 13 | :411-414 |
| `OH_Ability_GetCurrentChildProcessArgs()` | 17 | :458-459 |
| `OH_Ability_RegisterNativeChildProcessExitCallback(cb)` | 20 | :481-483 |
| `OH_Ability_KillChildProcess(pid)` | 22 | :517-518 |

- **入口形态 = 共享库 + 导出函数**（不是独立 ELF）：`entry = "libX.so:Main"`，子进程 `dlopen(libName)` 后 `dlsym("Main")` → `Main(NativeChildProcess_Args)`，**函数返回即子进程退出**。ArkTS 侧等价入口：`childProcessManager.startNativeChildProcess(...)`（@since 13）。
- **参数**：`entryParams` ≤ **150 KB**（超长 classpath 需走 fd/文件）；`fdList` ≤ **16** 个 fd（可传 pipe 回收 stdout/stderr）；`isolationMode` 必须 **`NORMAL`**（共享沙箱与网络）才能读 `filesDir`。
- **能力边界**：**不支持 UI**；**不支持 Context 接口**（⇒ JRE 解压/资源读取必须在父进程做，子进程只收路径）；子进程内**不能再建子进程**（`NCP_ERR_ALREADY_IN_CHILD`）；**随父进程退出**。
- **设备/数量**：仅 **PC/2in1 + Tablet**（API14+；phone 返回 `801`/`16000061`）；单进程 ≤50（API15+），与 `childProcessManager` 合计 ≤512。
- **保活**：`OH_BackgroundProcessManager_SetProcessPriority(pid, PROCESS_INACTIVE)`（@since 17）**仅对 native 子进程生效**，是「声明我在干活」的口子；默认冻结策略文档未给。
- **命门（2026-09-15 登记，尚待 POC）**：子进程是 AppSpawn 拉起的**全新进程**，只按 `libName` 解析；**能否跨 namespace `dlopen` `meowjre` HSP 里的 29 个 JRE `.so` 未获文档保证**（对照：`架构决策与踩坑.md` §8.5 记过 entry 跨 namespace dlopen HSP so 会 `MUSL-LDSO: ns accessible failed`）。**绕法**：把 JRE 的 `.so` 平铺进 **entry HAP 的 `libs/arm64-v8a/`**（hvigor 只打顶层 `.so`）。

## 3. 候选 B：独立进程 UIAbility + `STARTUP_HIDE`（最稳）

- **开关**（`@ohos.app.ability.startoptions` / `contextConstant`，均 @since 12，**仅 2in1/Tablet**、**`processMode` 与 `startupVisibility` 必须同时设置**、仅 `UIAbilityContext.startAbility` 生效）：
  - `processMode = NEW_PROCESS_ATTACH_TO_PARENT`（进程随父进程退出；`NEW_PROCESS_ATTACH_TO_STATUS_BAR_ITEM` 另一档）；
  - `startupVisibility = STARTUP_HIDE` ⇒ 文档原文：**窗口不显示在前台、dock 栏无图标、`onForeground` 不回调**；
  - 进一步抑启动页/动画：`hideStartWindow`（@since 20，2in1/自由多窗 Tablet）、`withAnimation=false`（@since 11；HarmonyOS 6.1.0 起支持）、`removeMissionAfterTerminate=true`。
- **注意**：`onWindowStageCreate` 里**不调 `loadContent` 不会得到「无窗」**（窗口照建、白屏）；真正的无窗后台启动 `startAbilityByCall` **对三方关闭**（仅分布式迁移场景开放）。
- **优点**：完整复用现有链路（`import('meowjre')` → HSP 内 `dlopen` JRE → `JLI_Launch`），零 lib 解析风险。
- **未知**：`STARTUP_HIDE` 是否做到**零帧闪窗**、是否真的无任务栏条目——文档未保证，**需实测**。

## 4. 候选 C 与排除项

| 方案 | 判定 | 依据 |
|---|---|---|
| 现有 `:installer` UIAbility **带窗** + 隐藏/最小化 | 兜底（最可能闪窗） | `uiability-usage`：不 `loadContent` 即白屏；`FAQ faqs-ability-65`：UIAbility 在任务列表会显示任务视图 |
| **主进程内**起 JVM | ❌ 排除 | 会冻 UI；且 `_exit`/`JLI` 会带走主进程；`jvmStarted` 单例拒二次 |
| `startAbilityByCall` 后台（真无窗） | ❌ 三方不可用 | `uiability-cross-device-interaction` §约束限制 |
| `ServiceExtensionAbility` | ❌ 三方不可用 | FAQ `faqs-background-tasks-1`；SDK 无公开 d.ts |
| `AppServiceExtensionAbility` | ❌/受限 | @since 20，仅 2in1，需 ACL `ohos.permission.SUPPORT_APP_SERVICE_EXTENSION`（企业应用） |
| `WorkSchedulerExtensionAbility` | ❌ 不适合 | 单次回调 ≤2min、系统条件调度 |
| `TaskPool` / `Worker` | ❌ 不隔离 | 同进程线程 ⇒ `exit` 会带走宿主 |

## 5. 保活/冻结兜底

- **短时任务**（`OH_BackgroundTaskManager_RequestSuspendDelay`，@since 13，权限 `ohos.permission.KEEP_BACKGROUND_RUNNING`）：退后台延迟挂起，单次 ≤3min、连续申请不可超 3 次 ⇒ **不够一次完整安装**。
- **长时任务**（`continuous-task`）：能「直到取消才不挂起」，但**会弹通知栏通知**；**有利条款**：一个 UIAbility 申请后**整个应用所有进程都不被挂起** ⇒ 可作 A/B 的保活兜底（代价 = 一条通知）。
- 后台配额参照：后台内存 2GB / IO 1GB；后台单核占用超阈值会被结束（FAQ `faqs-background-tasks-6`）。

## 6. 我方最小改造面

**方案甲（无窗 UIAbility）必须改**：`module.json5` 加 `InstallAbility` + `process: ":install"`；新增 `InstallAbility.ets`（**不 `loadContent`**）；新增 headless 编排（跳过账户/渲染设置，只做 classpath 与 argv）；`JvmLauncher.startJvm` 形参放宽为 `common.Context`；`meowjrebridge.cpp` 增 **headless 入参**（置空即跳过 `rendererSo/Env` 必填、跳过预 dlopen 与 glthread guard，保留 env/pipe/JLI）；**新增结果回传**（现状 native 只有 hilog + `_exit`，**无跨进程退出码通道**）。
**可直接复用**：native `launchJvm` 主体（env/pipe/`JLI_Launch`）、`startJvm` 单例与 `import('meowjre')`、`jre::Install`（解压与就绪标记）、`Want.parameters` 传参模式。

**方案乙（native 子进程）可复用**：主进程侧编排（JRE 解压、classpath staging、argv 组装的 ArkTS 部分）+ 路径函数；**需确认**：HSP so 可达性（命门）、`NEED_OPENGL=1`（app 级 `appEnvironments`）是否被继承并强制 GL 初始化、stdout/stderr 与退出码回报（可 `waitpid`/fd）。

## 7. POC 计划（最小验证集）

**POC-1（定命门，最高优先）**：在 2in1 上从主进程 `startNativeChildProcess("libmeowprobe.so:Main")`，子进程内：`dlopen` JRE 的 `libjli.so` → `JLI_Launch` 跑一个最小 main（打印 `java.home`/`-version`）→ 通过传入 fd 回收 stdout 并回传退出码。
- **判据**：① 子进程被拉起（pid 非空、退出回调触发）；② `dlopen` 成功（若失败 → 记录 `MUSL-LDSO` 类错误，改走「JRE so 平铺进 entry libs」再试）；③ 打印出的 `java.home` 与 el2 数据目录一致；④ 全程**无新窗口/无任务栏条目**。

**POC-2（备选路 B 验证）**：`InstallAbility` + `processMode=NEW_PROCESS_ATTACH_TO_PARENT` + `startupVisibility=STARTUP_HIDE`（+ `hideStartWindow`/`withAnimation=false`），起 JVM 跑最小 main。
- **判据**：无可见窗口/无 dock 图标/无启动页闪帧（需人工观察，2026-09-15 登记待验），进程能跑完并被主进程感知。

**POC-3（顺带）**：`el1` 文件能否 `execve`（决定「直接 exec `bin/java`」这条是否彻底关闭）。

## 8. 实测结论（2026-09-15 POC 完成；探针已清理）

### 8.1 loader namespace 定论（三轮探针 + 一次打包试验，实证）

> **一个进程能 `dlopen` 的范围 = 它自己模块的 libs + 它已加载的 HSP 的 libs + 系统库。**

- **native 子进程**（AppSpawn 起的新进程，只带自己模块 = entry）：
  - ✅ 能 `dlopen("<入口 libs>/libmeowprobe.so")`（绝对路径、自己的 el1 目录）；
  - ❌ **不能** `dlopen` HSP(`meowjre`) 目录里的任何库（`libjli.so` / `libc6.so` 都失败），
    而同一进程里 `access()=1`、`stat()` 正常、`opendir` 能列全 44 个条目 ⇒ **文件可见但不许加载**；
  - 报错码会漂移：同一路径曾报 `No such file or directory`，也报过 `Invalid argument` ⇒ **不能靠 errno 判因**。
- **`:game` 进程**（`import('meowjre')` 加载了 HSP）⇒ 桥在 HSP 内 `dlopen` HSP 的 JRE 一直可用。
- **推论**：把 JRE 的 29 个 `.so` 放进**入口 HAP 的 `libs/arm64-v8a/`** 后，子进程侧 `s0` 策略立即成功。

### 8.2 路线 A（native 子进程）实测

打包试验（仅把 JRE `.so` 临时复制进入口 HAP）+ 同一条探针 ⇒
`[s0] dlopen(.../libs/arm64/libjli.so) -> OK`、`dlsym(JLI_Launch) -> OK`、
`java.home=/data/…/el2/…/meow-jres/meow_jre`（正确）、`os.name=HarmonyOS`、`JLI_RETURNED code=0`，
**全程无窗口**。

⇒ **A 技术上成立**，代价是 **JRE `.so` 必须落到入口 HAP**（要么双份 ≈ +33MB，要么迁移并回归游戏路径）；
**未采用**（见 8.3 更省）。

### 8.3 路线 B（无窗 UIAbility）实测 —— **采用**

做法：静态 `process: ":neoinstall"` 的 UIAbility（不 `loadContent`）+ 父进程
`StartOptions{processMode: NEW_PROCESS_ATTACH_TO_PARENT, startupVisibility: STARTUP_HIDE}`
（SDK 原文要求二者成对；均 @since 12，仅 2in1/Tablet 生效）。

实测（2026-09-15，用户观察 + 产物文件双证）：
- **完全没有窗口弹出、没有 dock 条目、主 UI 无干扰**（用户原话："无缝"）；
- 该进程内走 **HSP 的 JRE 链路**跑通 JVM：`JLI_BEGIN args=3` → `JLI_RETURNED code=0`；
- **零打包改动**（JRE 仍只在 HSP）；进程隔离成立（JVM 的 `_exit` 只结束 `:neoinstall`）。

⇒ **B = 安装期载体**。附带好处：与 `:game` 同一套已验证机制，`NeoForge` 的 processor 工具 JVM 可逐次复用它。

### 8.4 桥的沉淀（保留，通用能力）

- **headless 模式**：`launchJvm` 的 `rendererLib` 传空 ⇒ 跳过渲染器预 dlopen、渲染相关 env、glthread 失效安全；
- **退出码文件通道**：headless 时把 `JLI_BEGIN` / `JLI_RETURNED code=N` 追加到
  `<filesDir>/meow-neo-jvm-result.txt`（补上「native 只有 hilog、主进程拿不到退出码」的洞，安装编排必需）。
- 回归确认：改动后 **MC 26.2 Fabric 实机无问题**（用户 2026-09-15 确认）。

### 8.5 探针清理（2026-09-15）

native 探针（`meowneoprobe`）、探针数据层（`NeoInstallProbe.ets`）、无窗 ability 与 UI 入口/文案
**全部删除**（结论已落本文档；证据仅存 `.logs/`，非持久凭据）。T3 实现安装编排时按本文 §8.3 的做法重新加回
（`module.json5` 需给 UIAbility 声明 `startWindowIcon`/`startWindowBackground`，否则 schema 校验失败）。

## 9. 证据台账

- 文档 documentId（摘）：`开发指南/Ability_Kit_程序框架服务/应用模型/进程模型/process-model-stage`；`.../Native子进程开发指导/创建_终止Native子进程_C_C/capi-nativechildprocess-development-guideline`；`API参考/.../C_API/头文件/native_child_process_h/capi-native-child-process-h`；`.../C_API/模块/ChildProcess/capi-childprocess`；`API参考/.../Stage模型能力的接口/ohos_app_ability_childProcessManager_子进程管理_/js-apis-app-ability-childprocessmanager`；`API参考/.../ohos_app_ability_startOptions/...`；`FAQ/程序框架/程序框架_Ability/*`（34/29/112/65/4）。
- 头文件：`$HOME/devecow/deveco_tools/sdk/default/openharmony/native/sysroot/usr/include/{AbilityKit/native_child_process.h, background_process_manager/background_process_manager.h, transient_task/transient_task_api.h}`；d.ts：`ets/api/@ohos.app.ability.{childProcessManager,ChildProcessOptions,contextConstant}.d.ts`、`.../StartOptions.d.ts`。
- 本仓：`module.json5:65`、`JvmLauncher.ets:56,67-78`、`GameLauncher.ets:24-125`、`meowjrebridge.cpp:116-458`、`jre_launcher.cpp:239-289`、`GameProcessScanner.ets:13-17`。

## 10. 2026-09-27 复核：phone 侧无解（仅「进程内单 VM」一条路）

> 本节为**带日期的记录**（当次复核的实测与源码证据），不改前文历史结论。触发：让 phone 也能装 NeoForge。

**失败现象**：手机装 NeoForge ⇒ 第一个 processor 的 JVM 返回 `JLI_Launch returned 0` 后，**整个启动器退出**。
**根因**：桥在 JVM 返回后**无条件 `_exit`**（主仓 `libs/meowcraftlib/src/main/cpp/meowjrebridge/meowjrebridge.cpp:588-592`），而其前提「独立进程」在 phone 上**不成立**。

**实测（phone = HUAWEI Mate XT，API 26 / OHOS 7.0.0）**：
- `module.json5` 的静态 `process: ":game"` / `":neoinstall"` **在 phone 被忽略** ⇒ 所有 ability 同进程；`ps` 只见单进程 `meow.liny.craft.awa`；用户确认「手机上玩完 MC 后整个 App 也退出」（同一根因）。
- 方案乙（`:neoinstall` 改**可见进度页**）**UI 部分跑通**（进度页显示、processor 返回 0），但无进程隔离 ⇒ `_exit` 杀 App ⇒ **失败**。该试验（对 2in1/Tablet 无影响）已**回滚**，代码回到 §8.3 的 B 路线。

**phone 侧机制穷尽**：

| 机制 | phone | 依据 |
|---|---|---|
| `startupVisibility=STARTUP_HIDE`（+`processMode`） | ❌ 仅 2in1/Tablet | 本文 §3；phone 传该字段启动失败 |
| UIAbility 静态 `process:` | ❌ phone 忽略 | 本次实测（FAQ `faqs-ability-34`） |
| native 子进程 / `childProcessManager` | ❌ 仅 2in1/Tablet（801/16000061） | 本文 §2 |
| ExtensionAbility 作宿主 | ❌ 三方×按需×长时×独立进程**四者不可兼得**（`WorkScheduler` 单次 ≤2min 且系统调度；`RemoteNotification` <10s；`Service`/`AppService` 三方不可用） | 本次复核 |
| Worker / TaskPool | ❌ **同进程线程**（非进程） | 本次复核（d.ts「isolated from the host thread」） |
| **进程内** | ✅ 唯一剩余 | — |

**HotSpot 侧硬约束（源码，工作区 `ref/jdk26u`）**：**一进程只能成功创建一个 VM；销毁后也不能再建** —— `src/hotspot/share/prims/jni.cpp:3586-3607`（注释原话「only possible to have one Java VM, since some of the runtime state is in global variables」；`safe_to_recreate_vm` 初值 1、成功创建后置 0 且**永不回 1**，仅"创建失败可重试"才复位 `:3686`；`DestroyJavaVM` 只复位 `vm_created` `:3775`）。⇒ 一个 App 进程生命周期内**最多一个 JVM 会话**（与 `JvmLauncher.ets` 的 `jvmStarted` 单例一致）。

**唯一可行路径（本记录为 2026-09-27 复核时的提议）**：phone 端「**进程内、单 VM** 跑完所有 processor」——桥 headless 不 `_exit`；同一 VM 内用一个 driver 顺序调用各 processor 的 `main`；**装完后 phone 端须重启启动器**才能起游戏 JVM。待验：某 processor 是否 `System.exit()`；单 VM 跑多 main 的稳定性。

**新增候选（2026-09-28 补记，见 [`NeoForge无JVM安装-可行性与取证.md`](../20-design/launch/NeoForge无JVM安装-可行性与取证.md)）**：上述讨论都假定"安装期**必须**有 JVM"。该项重新逐 processor 核对后，**26.x 形态不成立** —— 它 client 侧只有 1 个 processor 且**不做字节码重命名**（profile 无 `--input-mappings`）⇒ 只需「解 bundle + LZMA/GDIFF 补丁 + 抽库 + 写确定性 zip」，可纯 native 重实现 ⇒ **phone 装 NeoForge 26.x 存在一条完全不跑 JVM 的路径**（1.20.1 / 1.20.2–1.21.x 仍卡在 FART / ART 各 1 个 remapper，故本文结论对这两形态继续有效）。"下载已构建产物代替"经联网核实**不成立**。

**产物**：复核报告见 工作区根 `stuffs/research/neoforge-phone-install/`（四份：平台机制 / 代码测绘 / 扩展宿主 / Worker）。

---

相关：[`NeoForge支持-改动方案.md`](NeoForge支持-改动方案.md)（§2.4 前置 / T0）、[`Fabric支持-调研.md`](../20-design/launch/Fabric支持-调研.md)、[`../README.md`](../README.md)。
