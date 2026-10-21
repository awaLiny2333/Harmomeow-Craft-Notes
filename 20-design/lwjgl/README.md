# 20-design / lwjgl — LWJGL 自编与世代管理

本目录放 **LWJGL 的源码级自编与世代管理**（现代 LWJGL3 + legacy LWJGL2）。

- [LWJGL3世代管理-方案.md](LWJGL3世代管理-方案.md) — **现代单代 3.4.3**：为什么由"两代并存"收敛为单代、5 个 3.4.x 兼容 shim 的成员级判据与修法、native 命名与锁步、`EXTRAS_VERSION`。
- [LWJGL2自编-方案.md](LWJGL2自编-方案.md) — 自编 native `liblwjgl.so` 服务 MC 1.6.x–1.12.2 的设计、最小集与风险。
- [LWJGL2-legacy适配-复盘.md](LWJGL2-legacy适配-复盘.md) — legacy LWJGL2 OHOS 适配全过程复盘（上游/构建/魔改/验收）。

上级索引见 [`../README.md`](../README.md)。
