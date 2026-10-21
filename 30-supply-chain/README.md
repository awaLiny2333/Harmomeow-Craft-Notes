# 依赖与 .so 溯源（Supply Chain）

> 更新：2026-09-13（对齐**该文撰写时**代码基线 `6ba4ee6`；支持窗口 **MC 1.6.x – 26.3**）｜ **命名/状态以 [`../00-current/现状基线.md`](../00-current/现状基线.md) 为准。**
> 本目录分工（**只放现状**）：
> - [`provenance-master.md`](provenance-master.md)：资产总表 + 来源/可控分级 + 收编路线（**权威**）
> - [`per-so-catalog.md`](per-so-catalog.md)：逐 so 名录
> - [`assets-digests.txt`](assets-digests.txt)：校验和（SBOM 基线）
> - [`bisheng-hnp-trial.md`](bisheng-hnp-trial.md)：BiSheng hnp 嵌入试验（结论：**不可嵌入**，含平台 exec/隔离事实）
>
> 已退役/已剔除档案（**非现状**）：[`../90-archive/supply-chain-retired/`](../90-archive/supply-chain-retired)（patchjna_agent、JNA/libjnidispatch）。

## 0. 结论先行（当前）

| 类别 | 资产 | 可控性 |
|---|---|---|
| **自研（源码级）** | `libmeowassets.so` / `libmeowjrebridge.so` / `libmeowcraftbridge.so` / `libopenal.so` / `libfreetype.so` / LWJGL 现代单代 natives（`liblwjgl_343{,_opengl,_stb}.so`；旧 `_333` 已于 2026-09-14 移除）/ legacy LWJGL2（`liblwjgl.so`）/ `liblwjgl_tinyfd.so` / `libgl4es.so` / SDL3（`libSDL3.so`）/ `libshaderc.so` / `libspirv-cross.so` / `lwjgl-3.4.3.jar`（tools 自编）+ 全部 ArkTS + `tools/` | 🟢 本仓库/工具链可复现编译 |
| **可控（来源已核实）** | **随包 ASM 9.9.1 ×5**（Maven Central 官方件，逐件下官方 `.sha1` 校验相等；见 [`provenance-master.md`](provenance-master.md) §4.2）、`libc++_shared.so`（NDK 工具链件） | 🟢 能证明与上游一致 |
| **自研/可控（JRE，已收编 2026-09-12，2026-09-13 精确对齐源）** | `meowjre`（官方 OpenJDK 26.0.2.1 glibc 件原地改 `.dynstr` + 自编 `libc6.so`/`libjli`/`libjvm`；自编件源 = 官方发布同一 commit：`openjdk/jdk26u` `jdk-26.0.2.1-ga`） | 🟢 零黑箱（见 [`provenance-master.md`](provenance-master.md) §3/§4.1/§5） |
| **已退役 jar** | `patchjna_agent.jar` / `jsr305.jar`（已退役）；`android/util` 已甩掉 | ⚪ git/档案留证 |
| **平台依赖** | `libGLv4`/`libEGL`（Mesa Zink over Vulkan → Maleoon 916）等系统库 | ⚪ 系统能力，非应用资产 |

- **Pojav/Amethyst/HOML 代码零残留**：`libpojavexec.so`/`libhoml_bridge.so`/`libdriver_helper.so` 已退役（Stage B/C，git 可还原）；launcher/GLFW overlay/桥已净室重写。
- **支持窗口 = MC 1.6.x – 26.3**（2026-09-11 实测定案）：1.6.x–1.12.2 → 自编 legacy LWJGL2（`liblwjgl.so`）+ gl4es；≤1.16 → 自编 `libgl4es.so`（GLES）；1.17–1.21.x 与 ≥1.22 → **现代单代 LWJGL 3.4.3**（1.13–1.21.x 靠 5 个 3.4.x 兼容 shim）；≥26.3 → 自编 SDL3（`libSDL3.so`）+ `libshaderc.so`/`libspirv-cross.so`。
- JRE 收编已完成（2026-09-12，零黑箱）：官方 OpenJDK 26.0.2.1（glibc）件原地改 `.dynstr` + 自编 `libc6.so`/`libjli`/`libjvm` → 供应链**全自主/可控**（见 [`provenance-master.md`](provenance-master.md) §3/§4.1/§5）。自编件源已与官方 26.0.2.1 发布精确对齐（`openjdk/jdk26u`，tag `jdk-26.0.2.1-ga` @ `d55edf1cba61…`）。
- 随包 jar 载体：`entry/src/main/resources/rawfile/meowcraft_extras.tar.gz`（**1 jar（LWJGL）+ 随包 ASM ×5**：`lwjgl-3.4.3.jar`〔现代单代，服务 1.13–1.21.x 与 ≥1.22；旧 `lwjgl-3.3.3.jar` 已移除〕+ `asm9/{asm,asm-analysis,asm-commons,asm-tree,asm-util}-9.9.1.jar`〔**v45 2026-09-30**：落 `asm9/` 子目录，启动期覆盖实例声明的旧 ASM〕；`EXTRAS_VERSION` 令牌控 staging 缓存〔现 `20261001-drop-meow-launcher`〕；**`launcher.jar` / `gson-for-launcher.jar` 已于 2026-10-01 随 MeowLauncher 退役一并移除**；`jsr305.jar` 已移除）。
- JRE 数据：`entry/src/main/resources/rawfile/meow_jre.tar.gz` → `filesDir/meow-jres/meow_jre`。

> 历史 v2 裁剪（2026-09-07，51→40 so 等）与旧命名（`jrelib`）已归档于 git 历史与本文档旧版；
> 当前布局见 [`per-so-catalog.md`](per-so-catalog.md) 与 [`assets-digests.txt`](assets-digests.txt)。
