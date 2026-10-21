# 触屏输入（触屏当鼠标 + 虚拟按键）— 专题归档

> 已归档（2026-09-22）：本目录是「触屏输入」这一轮的**结论 + 证据索引**，属**历史档、非现状**。
> 现行结论见 [`../../20-design/input/输入-总览.md`](../../20-design/input/输入-总览.md) §2.3/§2.4/§2.5，
> 落地与提交态见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 25 条。
> 未删的原始报告在工作区根 `stuffs/research/touch-controls`。

> 本项目惯例：`90-archive/` 放**结论 + 证据**（正文涉活状态一律写**指针**或**带日期记录**），
> `stuffs/` 留**原始件**；两者用**工作区根相对路径**互指。本目录只摘录 / 收敛结论，原件保持原地不改。

## 必读

- 原始件 `stuffs/research/touch-controls/CORRECTIONS.md` —— **必读**：本目录的结论与其冲突时，**以原始件与当前代码为准**。
  理由：多轮子 agent 在**不同时刻**写报告，其间代码经多轮编辑、一次**批量回归**与一次**整体撤销**；该文件是过期断言（含失效行号）的**唯一汇总**。
- 引用约定：本目录与原件一律**不写行号**（改后失效），只写**符号名 / 文件名**。

## 本专题文档

| 文档 | 讲什么 |
|---|---|
| [01-触屏当鼠标-链路与手势.md](01-触屏当鼠标-链路与手势.md) | 窗口级 touch filter 的链路、手势语义表、与既有 mouse filter 的关系、两条渲染链的差别 |
| [02-虚拟按键-布局与手势.md](02-虚拟按键-布局与手势.md) | 覆盖层布局（左下 8 向 / 右下 3×3 缺两格 / 顶部）、几何与尺寸来源、方向判定四条、高亮、多指 |
| [03-排除区与native桥.md](03-排除区与native桥.md) | 按钮矩形排除机制（数据驱动 / display px / 双缓冲发布 / finger 级跳过）、native 函数清单、六处接线 |
| [04-设置与存储拆分.md](04-设置与存储拆分.md) | 8 个设置项（键名 / 默认 / 钳制）、独立文件形态与容错、生效时机 |
| [05-MC默认键位-26.3-SDL-vs-26.2-GLFW.md](05-MC默认键位-26.3-SDL-vs-26.2-GLFW.md) | 默认键位表（SDL scancode vs GLFW 码对照）与「26.3 走 SDL、26.2 走 GLFW」前提 |
| [06-两轮独立复核与修复复盘.md](06-两轮独立复核与修复复盘.md) | 两轮复核的组织方式、抓到的缺陷类别、**那次回归的成因与治本**、四类坑、更正清单指针 |

## 原始件映射表（哪份结论 → `stuffs/research/touch-controls/` 下哪几个文件）

> 下表路径均为**工作区根相对**（`../../../stuffs/research/touch-controls/`）。「主要」= 本专题文档的直接取证来源；「辅助」= 同域参考，未逐字通读。

| 本专题文档 | 主要原始件 | 辅助 / 同域原始件 |
|---|---|---|
| 01 | `stuffs/research/touch-controls/review-A-native.md`、`stuffs/research/touch-controls/review2-A-native.md` | `stuffs/research/touch-controls/fixes-2-native.md`（含**事后更正**块）、`stuffs/research/touch-controls/fixes-3-arkts.md`、`stuffs/research/touch-controls/review-B-arkts.md`、`stuffs/research/touch-controls/review2-B-arkts.md` |
| 02 | `stuffs/research/touch-controls/ui-report.md`（布局 / 几何细节最全） | `stuffs/research/touch-controls/fixes-1-ui.md`、`stuffs/research/touch-controls/review-C-ui.md`、`stuffs/research/touch-controls/review2-C-ui.md` |
| 03 | `stuffs/research/touch-controls/exclude-report.md`、`stuffs/research/touch-controls/fixes-2-native.md` | `stuffs/research/touch-controls/review-A-native.md`、`stuffs/research/touch-controls/review2-A-native.md`、`stuffs/research/touch-controls/review-E-blast.md`（接线表） |
| 04 | `stuffs/research/touch-controls/touch-settings-file.md` | `stuffs/research/touch-controls/fixes-4-settings.md`、`stuffs/research/touch-controls/review-D-settings.md`、`stuffs/research/touch-controls/review2-D-settings.md` |
| 05 | `stuffs/research/touch-controls/mc-keybindings.md` | —— |
| 06 | `stuffs/research/touch-controls/review-E-blast.md`、`stuffs/research/touch-controls/review2-E-blast.md`、`stuffs/research/touch-controls/CORRECTIONS.md` | `stuffs/research/touch-controls/fixes-1-ui.md`、`stuffs/research/touch-controls/fixes-2-native.md`、`stuffs/research/touch-controls/fixes-3-arkts.md`、`stuffs/research/touch-controls/fixes-4-settings.md`、`review-*` / `review2-*` 全部 |

### 原始件清单（全部在 `stuffs/research/touch-controls/`）

| 阶段 | 文件 |
|---|---|
| 索引 | `stuffs/research/touch-controls/README.md`、`stuffs/research/touch-controls/CORRECTIONS.md`(**必读**) |
| 调研 / 实现 | `stuffs/research/touch-controls/mc-keybindings.md`、`stuffs/research/touch-controls/ui-report.md`、`stuffs/research/touch-controls/exclude-report.md`、`stuffs/research/touch-controls/touch-settings-file.md` |
| 第 1 轮复核 | `stuffs/research/touch-controls/review-A-native.md`、`stuffs/research/touch-controls/review-B-arkts.md`、`stuffs/research/touch-controls/review-C-ui.md`、`stuffs/research/touch-controls/review-D-settings.md`、`stuffs/research/touch-controls/review-E-blast.md` |
| 修复 | `stuffs/research/touch-controls/fixes-1-ui.md`、`stuffs/research/touch-controls/fixes-2-native.md`、`stuffs/research/touch-controls/fixes-3-arkts.md`、`stuffs/research/touch-controls/fixes-4-settings.md` |
| 第 2 轮复核 | `stuffs/research/touch-controls/review2-A-native.md`、`stuffs/research/touch-controls/review2-B-arkts.md`、`stuffs/research/touch-controls/review2-C-ui.md`、`stuffs/research/touch-controls/review2-D-settings.md`、`stuffs/research/touch-controls/review2-E-blast.md` |
| 收尾 | `stuffs/research/touch-controls/notes-sync.md`（notes 同步记录） |

## 产物

- **未涉及任何预编随包件重建**：`libSDL3.so` **逐字节复现原值** `db255b25…`，与主仓 `tools/README.md` 记录一致。

## 指针（不在此复述）

- 触屏点「回到游戏」后视角朝点击侧瞬移：机制 + 三条已试无效修法 + 「别再试」结论 → [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) **§G2**。
- 触控设置文件的缓存不失效 / 不做旧值迁移：定案 → [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) **§B6**。
