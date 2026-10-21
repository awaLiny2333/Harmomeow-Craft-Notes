# 20-design — 启动 / 安装 / 环境 / 渲染 / 性能 / 输入

> 本区是**设计 / 机制层**：每篇写"某个机制是怎么设计的、为什么这么做"（现行事实与契约）。
> 其中 `launch/` 另放"启动链 / 安装链 / 环境与载体 / 决策与不变量"四篇**总览** + 各机制的**证据 / 调研档**。
> **现役真相**以 [`../00-current/现状基线.md`](../00-current/现状基线.md) 为准；历史与实验在 [`../90-archive/`](../90-archive/README.md)；
> 外部项目研究在 [`../10-research/`](../10-research/README.md)；上游索引见 [`../README.md`](../README.md)。
> 下表只给一句提要；**逐篇索引以各子目录的 `README.md` 为准**。

| 子目录 | 放什么 |
|---|---|
| [`launch/`](launch/README.md) | 启动链 / 安装链 / 环境与载体 / 决策与不变量 + 账户 / 设置存储 + Forge / NeoForge / Fabric 机制证据 |
| [`render/`](render/README.md) | 渲染后端与桥（GLFW 净室桥 / SDL3 / gl4es / MC 26.x 渲染栈 / Vulkan / 1.21.1 崩溃两条链）+ 渲染链结论 |
| [`lwjgl/`](lwjgl/README.md) | LWJGL jar/native 自编与世代管理（现代单代 3.4.3 + legacy LWJGL2） |
| [`perf/`](perf/README.md) | 性能（平台能力调研 / 实验台 / QoS与绑核 / glthread GL-guard / 崩溃 Bug 报告） |
| [`input/`](input/输入-总览.md) | 输入总览（鼠标 + 触屏） |

**命名约定**：`<主题>-<类别>.md`，类别只用 **方案 / 调研 / 复盘 / 报告 / 对照 / 总览 / 设计 / 结论**；目录已表主题，文件名不重复域前缀；专名保留官方大小写（`LWJGL2/3`、`SDL3`、`Vulkan`、`glthread`、`gl4es`、`Fabric`）。
