# 20-design / launch — 启动 / 安装 / 环境与载体

本目录放**启动器侧**设计：四篇**总览**（启动链 / 安装链 / 环境与载体 / 决策与不变量）+ 账户 / 设置存储 + 各机制的证据 / 调研档。

## 总览（先看这四篇）

- [术语与定义.md](术语与定义.md) — **本目录专业名词的唯一权威**：`classpath` 三态（`flat` / `real-tree` / `ordered`）/ `slim`、加载器与世代、启动参数机制、安装链（`processor` / `spec` / `outputs` 幂等 …）、渲染 / 环境术语；每词条按"定义 → 形式化 → 如何观测 → 为什么这样 → 易混点 → 落点"六段给出，另附**三态判据真值表**与**代号对照表**。
- [启动链-总览.md](启动链-总览.md) — **某个 MC 版本 + 加载器该走哪条路、为什么、判据落在哪个函数**：三条切轴（LWJGL 切 1.13 / GL 切 1.17 / 窗口层切 26.3）+ 三个分流问题（classpath 三态 `flat` / `real-tree` / `ordered` · 是否直启加载器主类 · JRE 档）；原版 / Forge 四代 / NeoForge / Fabric 逐代给主类、classpath、JRE、关键坑；含总表、判据落点索引、常见误判速查。
- [安装链-总览.md](安装链-总览.md) — **四类应用内安装**（原版 / Fabric / Forge / NeoForge）的入口 / 判型 / 产物形态 / 幂等 / 失败诊断；Forge 判型 = client processor 数。
- [环境与载体.md](环境与载体.md) — **两套 JRE + 选择规则 / 多 JRE 布局与令牌门 / 平台伪装 / 安装期工具 JVM 载体（无窗 `:neoinstall`）/ 随包 ASM 覆盖 / `jdk.zipfs` 类补丁 / 沙箱缓存与运行目录布局（`mc-cp` / `mc-run`，含缓存 / 运行目录 ASCII 树）**。
- [决策与不变量.md](决策与不变量.md) — **定案（含"为什么"）/ 机制不变量 / 被否决方案**；含 `.minecraft` 目录管理、窗口记忆、ArkTS 踩坑、共享状态、版本识别、LWJGL 单代、版本隔离、输入、全屏、主题、显示缩放、JRE 数据门、启动器功能、随包 jar MANIFEST、失焦暂停、剪贴板、grab / 指针不变量、**另起 JVM 必带平台伪装**。

## 账户 / 设置

- [账户系统-设计与进度.md](账户系统-设计与进度.md) — 离线账户 + 微软正版登录（`MSA Device Code → XBL → XSTS → login_with_xbox`）；`MS_CLIENT_ID` 需自填。
- [实例设置存储-方案.md](实例设置存储-方案.md) — 设置文件化：逐版本 `<gameRoot>/versions/<id>/.hmmcraft/instance-settings.json` + 应用级 `filesDir/meow-settings/app-settings.json` 的 `global` 段 / `accounts.json`；Preferences 已彻底移除。

## 下载 / 进度

- [下载器-可靠性方案.md](下载器-可靠性方案.md) — 下载原语的结算契约（恰好 settle 一次 / 零拷贝写盘 / 批量失败语义）与故障注入矩阵。
- [安装进度-聚合方案.md](安装进度-聚合方案.md) — 16 并发下的进度口径：已知/未知大小的算法、全局节流、进度条边界、测试矩阵。

## 机制证据 / 调研（不进总览，也不归档）

- [Forge支持-调研.md](Forge支持-调研.md) — HMCL 的 Forge 支持面 / 两个版本源与镜像 / 两条安装形态 / 盘上格式 / 与 NeoForge 的差异。
- [Forge-1.13及以上-调研与方案.md](Forge-1.13及以上-调研与方案.md) — Forge ≥1.13 的四世代机制、启动侧病根（判据按 loader 名）、安装侧三缺口与环境侧事实。
- [Forge-splash-崩溃根因与共享上下文修复.md](Forge-splash-崩溃根因与共享上下文修复.md) — 1.7.10+OptiFine 进游戏 SIGSEGV 的取证与修复（FML splash 要"共享对象的第二 GL 上下文"）。
- [NeoForge支持-调研.md](NeoForge支持-调研.md) — NeoForge 证据存档：HMCL 三链 + 真 installer 解剖 + 我方现状测绘。
- [NeoForge安装链-逐行取证.md](NeoForge安装链-逐行取证.md) — HMCL 装 NeoForge/Forge 的逐行取证（JVM 落在 processor 那一步）。
- [NeoForge无JVM安装-可行性与取证.md](NeoForge无JVM安装-可行性与取证.md) — "不跑 JVM 能否装成 NeoForge"的逐 processor 判定（26.x 可零 JVM）。
- [Fabric支持-调研.md](Fabric支持-调研.md) — Fabric 启动机制（`KnotClient` + 追加 loader 库）与 vanilla 差异、盘上两形态。

## 归档（考古，非现状）

净室 launcher / 桌面启动基线 / 原版·Fabric 安装方案 / Forge 与 NeoForge 改动方案 / classpath 形态 / 多 JRE 共存 / 安装期 JVM 载体 / Forge 1.13–1.20.1 安装实施方案 —— 见 [`../../90-archive/`](../../90-archive/README.md)，其中 `桌面标准启动链路-对照.md`、`原版安装-方案.md`、`Fabric安装-方案.md`、`Forge支持-改动方案.md`、`Fabric支持-改动方案.md`、`NeoForge支持-改动方案.md`、`classpath形态-真树与平铺-决策情报.md`、`多JRE共存-方案.md`、`安装期JVM载体-调研.md`、`Forge-1.13至1.20.1-安装实施方案.md`、`launcher净室-设计.md` 均已在顶部标注"已归档（日期 + 为什么 + 现役口径指向）"。

上级索引见 [`../README.md`](../README.md)。
