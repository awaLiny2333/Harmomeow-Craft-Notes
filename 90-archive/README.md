# 归档区（实验 / 历史）

> ⚠️ **历史归档 · 路径口径说明（2026-09-12）**
> 本区为**历史**记录（非现状）。文中出现的 `Meowcraft/...` 指**当时的旧开发目录**；工程已于 2026-09-12 迁移为 **`Harmomeow-Craft-Launcher/`**（品牌 **Harmomeow Craft Launcher**）。**历史原文不改**，阅读时请按“`Meowcraft/xxx` → `Harmomeow-Craft-Launcher/xxx`”换算。

> ⚠️ 本区是**只增不改的历史证据**，用于考古 / 复现，**不是当前真相**。
> 当前命名 / 状态 / 定论见 [`../00-current/现状基线.md`](../00-current/现状基线.md)。
> **现状补充**：Pojav/Amethyst/HOML 血统已全部清除；黑盒原生三件套与 mobileglues / NG-GL4ES 翻译层均已退役，现用净室自编件（`libmeowcraftbridge.so` / 自编 gl4es）。

## 目录

| 文件 / 目录 | 内容 | 被谁取代 |
|---|---|---|
| [`jvm-step1.md`](jvm-step1.md) | Step1：JLI_Launch 在 app 进程内起 JVM（三层平台限制破解） | 已被 `00-current/现状基线.md` 概括 |
| [`pojav桥启动.md`](pojav桥启动.md) | Pojav 桥把 MC 1.21.10 跑通到画面（双 native 链坑、黑箱 so 情报） | 已被 `pojavexec-war/` 与 `00-current/` 取代 |
| [`清理杂项-2026-09-07.md`](清理杂项-2026-09-07.md) | 2026-09-07 清理快照（孤儿代码/后端定案） | 已被 `00-current/现状基线.md` 取代 |
| [`输入延迟调查证据.md`](输入延迟调查证据.md) | 输入/帧率延迟逐条证据（§一~§七，含 hitrace） | 结论已收敛到 `../20-design/input/输入-总览.md` 与 `../20-design/render/渲染链-结论.md` |
| [`pojavexec-war/`](pojavexec-war) | pojavexec 大战全档案（01-16：源码测绘/契约/M0-M3/输入/IME/摘 homl/改名） | 功能已落地，见 `00-current/现状基线.md` |
| [`渲染迁移评估/`](渲染迁移评估) | SurfaceHolder 迁移评估原始情报（01 渲染链测绘 / 02 文档 / 03 SDK 头 / 04 阶段A备用 / 05 OpenGTX） | 结论已收敛到 `../20-design/render/渲染链-结论.md` |
| [`触屏输入/`](触屏输入) | 触屏输入专题（触屏当鼠标 / 虚拟按键 / 排除区与 native 桥 / 设置独立文件 / 键位 / 两轮复核与四类坑） | 结论已收敛到 `../20-design/input/输入-总览.md` §2.3/§2.4/§2.5 |
| [`架构决策与踩坑-历史章节.md`](架构决策与踩坑-历史章节.md) | 早期章节（Step0 native 骨架 / 独立窗口雏形 / JRE 内嵌与 JLI_Launch / glthread 负项） | 现役决策见 `../20-design/launch/决策与不变量.md` |
| [`自研收编-总览与交接.md`](自研收编-总览与交接.md) | 收编自研路线 + 交接（含 launcher.jar 战役） | 方案 A「`MeowLauncher` 退役」后整体作废 |
| [`launcher净室-设计.md`](launcher净室-设计.md) | 净室 `meow.launcher`（替换 Pojav 派生 `launcher.jar`） | `MeowLauncher`/`MeowClassLoader`/`launcher.jar` 已退役 |
| [`桌面标准启动链路-对照.md`](桌面标准启动链路-对照.md) | 桌面正常启动基线（1.21.10 实证） | 结论已并入 `../20-design/launch/启动链-总览.md` §0.4 |
| [`classpath形态-真树与平铺-决策情报.md`](classpath形态-真树与平铺-决策情报.md) | 三态 classpath 的机制决策情报 | 结论已并入 `../20-design/launch/启动链-总览.md` §0 与 `决策与不变量.md` §0.3 |
| [`多JRE共存-方案.md`](多JRE共存-方案.md) / [`安装期JVM载体-调研.md`](安装期JVM载体-调研.md) | 多 JRE 共存 / 安装期无窗 JVM 载体 | 结论已并入 `../20-design/launch/环境与载体.md` |
| [`原版安装-方案.md`](原版安装-方案.md) / [`Fabric安装-方案.md`](Fabric安装-方案.md) / [`Forge-1.13至1.20.1-安装实施方案.md`](Forge-1.13至1.20.1-安装实施方案.md) | 原版 / Fabric / Forge 安装实施记录 | 结论已并入 `../20-design/launch/安装链-总览.md` |
| [`Forge支持-改动方案.md`](Forge支持-改动方案.md) / [`Fabric支持-改动方案.md`](Fabric支持-改动方案.md) / [`NeoForge支持-改动方案.md`](NeoForge支持-改动方案.md) | 三家 loader 的落地设计草案 | 结论已并入 `../20-design/launch/`（启动链 / 安装链 / 决策与不变量） |
| [`Vulkan后端-跟进与结案.md`](Vulkan后端-跟进与结案.md) | MC 26.2+ 原生 Vulkan 后端取证（**当时结论 BLOCKED，已被推翻**） | 现役机制见 `../20-design/render/Vulkan后端-实现与原理.md`、取证见 `Vulkan后端-取证存档.md` |
| [`LWJGL3单代收敛-决策依据.md`](LWJGL3单代收敛-决策依据.md) | 现代 LWJGL 两代→单代的成员级判据与 5 个 shim | 已并入 `../20-design/lwjgl/LWJGL3世代管理-方案.md` §3 |
| [`hmcl.md`](hmcl.md) | HMCL 深度分析（旧类名体系 `Version`/`DefaultLauncher`） | 总览已并入 `../10-research/hmcl-存储模型.md` §12 |
| [`launcher-rebuild.md`](launcher-rebuild.md) | `launcher.jar` 自编重建（Pojav 派生） | `launcher.jar` 随方案 A 退役（净室 `meow.launcher` 亦退役） |
| [`notes重构-方案.md`](notes重构-方案.md) | notes 重构方案（临时方案档） | 方案 A/B/C 已全部执行，现役结构见各目录 README |
| [`homl-sandbox-mirror.md`](homl-sandbox-mirror.md) | HOML el2 沙箱镜像（`ref/org.xbstudio.homl.pro`，1.7G）已删除 + 关键事实 + 结构快照 | 纯参考资料，已删（2026-09-09）；结构快照未随公开版发布 |
| [`supply-chain-retired/`](supply-chain-retired) | 已退役供应链组件档案（patchjna_agent、JNA/`libjnidispatch.so`） | 已被自编件取代（见 `00-current/`、`../30-supply-chain/provenance-master.md` §2⑤） |

## 命名对照（历史文档 → 现在）

| 旧名 | 现名 |
|---|---|
| `jrelib`（HSP） | `meowjre`（HSP）+ `meowcraftlib`（HAR）（**`meowjre25` 为更早的历史名**） |
| `libjrebridge.so` | `libmeowjrebridge.so` |
| `jre_bridge.cpp` / `meow_jre_bridge.cpp` | `meowjrebridge.cpp` |
| 自研 `libpojavexec.so` | `libmeowcraftbridge.so` |
| `libs/jrelib/...` | `libs/meowcraftlib/...` / `libs/meowjre/...`（**`meowjre25` 为更早的历史名**） |
| HOML 黑箱 `libpojavexec.so`/`libhoml_bridge.so`/`libdriver_helper.so` | 已退役（Stage B/C） |
