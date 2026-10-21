# 参考项目研究与方法论（HomoLauncher / Amethyst / HMCL + 本工程排查套路）

> 本目录是对 `ref/` 下参考**启动器**项目的深度研究报告（**外部参考**，非本项目自身实现；`ref/` 另含 lwjgl3 / lwjgl / openal-soft / freetype / oshi / SDL / shaderc 等作为**构建输入**的源码 clone，不在本目录范围）。
> 多数文档以"一个 ref 项目一篇"组织；《启动器目录模型与版本隔离》与《pojav系-启动渲染对照》**两篇**为跨启动器专题（前者含 `stuffs/.minecraft` 磁盘实证）。
> 写于改名之前，出现旧模块名按 [`../00-current/现状基线.md`](../00-current/现状基线.md) §3 换算。
> **现状**：Pojav / Amethyst / HOML 血统已全部清除；上述参照仓仅作**外部学习参考**（不随包）。

| 文件 | 内容 |
|---|---|
| [`原生崩溃排查-方法论与复盘.md`](原生崩溃排查-方法论与复盘.md) | ★**本工程自己的排查套路**（非外部项目）：拿到崩溃的速查顺序 / 平台与工具链事实 / 物证判读（含**三类良性噪声**）/ A/B 纪律 / 规避工程 / 交付 review / 战役坑清单与反面清单（2026-09-16） |
| [`homolauncher.md`](homolauncher.md) | HomoLauncher（鸿蒙版 Pojav）深度分析 —— 最直接参考 |
| [`amethyst.md`](amethyst.md) | Amethyst-Android 深度分析（含行级源码定位）：模块 / JNI 原生层 / 双 VM / JVM 启动 / GLFW stub / EGL / 输入 / 驱动家族 |
| [`hmcl-存储模型.md`](hmcl-存储模型.md) | HMCL 参考：**架构总览**（模块 / 平台抽象 / 参数生成 / 下载 / 账户 / 游戏模型 / UI）+ **持久化模型**（配置文件 / 已添加文件夹 / 账户 / 每实例参数 / 隔离落盘 / 迁移）—— 源码级 |
| [`启动器目录模型与版本隔离.md`](启动器目录模型与版本隔离.md) | **`.minecraft` 目录模型 / 版本隔离 / 安装流程**（HMCL 新版源码级 + PCL 磁盘实证 + 官方基线与各家横向对照） |
| [`pojav系-启动渲染对照.md`](pojav系-启动渲染对照.md) | **Pojav 系跨项目**：Amethyst × HomoLauncher 启动链 + 渲染/surface + 驱动映射 + HOML 资产清单 |
| [`../90-archive/三项目对比-早期快照.md`](../90-archive/三项目对比-早期快照.md) | 三项目横向对比 + 迁移路线建议（已归档，2026-09-15） |
| [`../90-archive/鸿蒙OpenGL渲染-早期研究.md`](../90-archive/鸿蒙OpenGL渲染-早期研究.md) | 鸿蒙 PC OpenGL ES 渲染梳理（已归档，2026-09-15） |

## 三者关系

```
Boardwalk (JVM 在 Android 启动的思路)
   └── PojavLauncher ──(
                        ├── Amethyst (其前身/同源重写，Android + iOS)
                        └── HomoLauncher (鸿蒙 NEXT 的 Pojav 实现)
                        )

HMCL (独立的多平台启动器，架构最成熟，可借鉴其 Core 层设计)
```

**关键结论**：HomoLauncher = 鸿蒙版 Pojav（`master` 分支才是真正资产）；Amethyst 与 HomoLauncher 共享同一套 Pojav 血统（caciocavallo AWT、`net.kdt.pojavlaunch` 包名、GLFW stub、gl4es/mobileglues）；HMCL 在启动器"上层"（版本解析/依赖下载/账户/参数拼接）最完善。
