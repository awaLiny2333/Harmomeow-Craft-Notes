# 20-design / render — 渲染后端

本目录放**渲染后端**：GLFW 净室桥、SDL3（26.3+）、Vulkan、legacy gl4es 与 26.x 渲染栈差异。

- [GLFW净室桥-设计.md](GLFW净室桥-设计.md) — 净室重写 lwjgl GLFW stub + `libmeowcraftbridge.so`，去 Pojav/LGPL 与 `android/util`。
- [SDL3桥接-设计.md](SDL3桥接-设计.md) — 真 SDL3 fork（pin `release-3.4.14` + 自写 ohos 驱动）解锁 MC 26.3+ 的方案与证据。
- [SDL3适配-复盘.md](SDL3适配-复盘.md) — 26.3（SDL）适配全过程复盘（问题→根因→解）以及与 GLFW 那次的对照。
- [MC26.x渲染栈-差异分析.md](MC26.x渲染栈-差异分析.md) — 26.x 相对 ≤1.21 的渲染栈重写（多后端/帧图/Vulkan），解释 glthread 崩溃为何更易触发。
- [Vulkan后端-实现与原理.md](Vulkan后端-实现与原理.md) — **权威机制 / 原理**：本机 ICD 实为 1.4 能力、仅按 1.2 档位裁剪**上报面**；五处机制（门控修面 / F66 / F69 / F72 / F73）+ 为什么必须 + 边界与未解。
- [Vulkan后端-取证存档.md](Vulkan后端-取证存档.md) — **取证方法 / 设备事实 / 逐项读数**（功能自证 A/B/C、描述符/分块/传输阶段裁决、WSI 全链、踩坑与仪器链）；旧结案档（判 BLOCKED）[已归档](../../90-archive/Vulkan后端-跟进与结案.md)。
- [legacy渲染-gl4es-落地方案.md](legacy渲染-gl4es-落地方案.md) — ≤1.16 改用原生 GLES + 自编 gl4es v1.1.7 实现正确渲染（2026-09-11 实测 1.16.5 正常）。
- [1.21.1-崩溃-两条链与随包规避.md](1.21.1-崩溃-两条链与随包规避.md) — 1.21.1 + Create/Flywheel 的**两条独立链**（厂商 GPU 着色器编译器 NULL deref / JVM C 堆被光照越界写坏）+ 随包规避、判据与取证配方（2026-09-16）。
- [GL33到GLES32-后端-方案.md](GL33到GLES32-后端-方案.md) — **一份 `libgl4es.so` 通吃 MC 1.6.x–1.21.x**：≤1.16/legacy 走 FPE，1.17–1.21.x 新增"GL 3.2/3.3 core → 原生 GLES 3.2"后端（无系统桌面 GL 的出路）；含入口映射、着色器翻译、名字表、里程碑与风险（2026-09-22 立项）。
- [gl4es固定管线雾-取证与修复.md](gl4es固定管线雾-取证与修复.md) — **1.7.10 + OptiFine「Fog: Fast」⇒ 世界全透明/零碎面片**的取证与修复：雾 uniform **只在立即模式上传、显示列表回放从不上传**（⇒ 只被区块用到的变体雾 uniform 恒为 GL 零值 ⇒ 全世界刷成雾色）；已修管线，**真凶（雾数学/取值空间）另计**；含 `[fogtrace]` 追踪开关、三版教训（含"写未绑定程序会毁别人 uniform"）与用户侧可用解（Fog: Fancy/Off）。

上级索引见 [`../README.md`](../README.md)。
