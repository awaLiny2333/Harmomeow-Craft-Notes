# 公开版阅读说明

本仓是 **Harmomeow Craft Launcher** 的工程笔记：记录在鸿蒙 PC（2in1）上原生运行
Minecraft Java 版的**设计、取证、约束与踩坑**。它不是构建产物，也不包含启动器源码。

## 代码在哪

启动器源码在**另一个仓库**（`Harmomeow-Craft-Launcher`，同一 GitHub 账号下）。
本仓只放文档；所有以 `common/…`、`entry/…`、`libs/…`、`tools/…` 开头的路径都指那个仓库。

## 哪些东西没有随本仓发布

| 目录 | 是什么 | 说明 |
|---|---|---|
| `stuffs/` | 本地工作区：调研产物、构建输出、测试用游戏目录 | 体积大、含本机状态，不发布 |
| `ref/` | 上游源码树（JRE / LWJGL / SDL / gl4es 等） | 构建输入，按各自许可另行获取 |
| `.logs/` | 维护者从设备导出的日志 | 不含在本仓 |
| 预编译件（`.so` / `.jar` / JRE tar） | 随包件 | 配方见启动器仓的 `tools/` |

因此文档里出现的 `stuffs/…`、`ref/…`、`.logs/…` 引用，请理解为
**"本地工作区路径，未随公开版发布"**，不是坏链。

## 建议阅读顺序

1. [`00-current/`](00-current/README.md) —— 现役结论层。唯一事实源是
   [`现状基线.md`](00-current/现状基线.md)；与它冲突时以它为准。
2. [`20-design/`](20-design/README.md) —— 按域的设计档：启动 / 安装 / 环境 / 渲染 / LWJGL / 性能 / 输入。
3. [`30-supply-chain/`](30-supply-chain/README.md)、[`40-adaptation/`](40-adaptation/README.md) —— 依赖溯源与平台适配。
4. [`90-archive/`](90-archive/README.md) —— 历史与证据。**结论可能已被推翻**，只作考古。
5. [`10-research/`](10-research/README.md) —— 其它启动器的对照研究（只读参考）。

## 术语对照

| 文档里的说法 | 指的是 |
|---|---|
| 拥有者 / 用户裁决 / 用户实测 | 项目维护者本人 |
| agent / 子 agent | 开发期使用的 AI 编程助手 |
| 主仓 | 启动器源码仓库（`Harmomeow-Craft-Launcher`） |
| 现状基线 | `00-current/现状基线.md`，唯一事实源 |
| 归档 / 已归档 | 历史材料，非现状 |

文档以中文为主，专有名词保留英文原文（组件名、API 名、路径）。

## 许可

- 文档：**CC BY 4.0**（见 [`LICENSE`](LICENSE)）
- `notes-tools/` 下的脚本：**MIT**（见 [`LICENSE-MIT`](LICENSE-MIT)）

## 更正

欢迎 issue / PR。改结论时请**先改 `00-current/现状基线.md`**，再回写对应文档；
历史与过程写进 `90-archive/`。
