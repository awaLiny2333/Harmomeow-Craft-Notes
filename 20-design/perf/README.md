# 20-design / perf — 性能

本目录放**性能**：平台加速能力调研、实验台与 glthread 结论、QoS 绑核、glthread 崩溃与 GL guard 方案。

- [平台加速能力-调研.md](平台加速能力-调研.md) — 华为平台加速能力（QoS/绑核/超帧/ABR/OpenGTX/XEngine）可用性判定、马良 GLES 反模式与待探测项。
- [性能实验台与glthread-结论.md](性能实验台与glthread-结论.md) — 用户基准 + 常驻实验台（渲染 env / 额外 JVM 参数）+ glthread 结论与指针、剩余候选。
- [QoS与绑核-实验报告.md](QoS与绑核-实验报告.md) — JVM A/B + 线程 QoS / 大核绑核执行方案（含 Kirin X90 CPU 拓扑实测）。
- [glthread崩溃-Bug报告.md](glthread崩溃-Bug报告.md) — 可提交华为 / Mesa 上游的 glthread×Zink×Maleoon UAF 随机 SIGSEGV 报告。
- [glthread-GL-guard-方案.md](glthread-GL-guard-方案.md) — B 方案：GL guard 转发层（应用侧拦 `glXGetProcAddress` 修 glthread UAF，让 26.x 不崩）。
- [Vulkan后端-性能瓶颈清单与实验计划.md](Vulkan后端-性能瓶颈清单与实验计划.md) — Vulkan 档性能差距的五路审计瓶颈清单（B0–B10）+ 决定性实验 E0–E5 + 廉价修复清单（2026-09-19）。

上级索引见 [`../README.md`](../README.md)。
