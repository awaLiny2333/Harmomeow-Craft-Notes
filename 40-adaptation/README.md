# 鸿蒙环境适配与魔改（OHOS Adaptation & Patches）

> 定位：**为了在鸿蒙沙箱 / 系统限制下跑通 MC，对第三方依赖或自身代码所做的适配与魔改**。
> 与 [`../30-supply-chain/`](../30-supply-chain)（溯源 / SBOM / 是否可控）互补：这里只讲
> **现象 → 根因 → 补丁 → 数据流 → 分发 → 版本范围 → 复现**。
> 结论/现状以 [`../00-current/现状基线.md`](../00-current/现状基线.md) 为准。

## 索引

| 主题 | 文档 | 状态 |
|---|---|---|
| oshi CPU 型号（F3 `<unknown>` → `20x KirinX90`） | [`oshi-cpu-info.md`](oshi-cpu-info.md) | 2026-09-09 实测通过（MC 1.21.10） |
| OpenAL Soft 自编（`libopenal.so` 源码级收编） | [`openal-ohos.md`](openal-ohos.md) | 2026-09-09 实测通过（MC 1.21.10 音频） |
| OpenAL OHAudio 后端（OpenSL→OHAudio 迁移，默认后端） | [`ohaudio-backend.md`](ohaudio-backend.md) | 2026-09-09 实测通过（MC 1.21.10 音频） |
| FreeType 自编（`libfreetype.so` 源码级收编） | [`freetype-ohos.md`](freetype-ohos.md) | 2026-09-09 实测通过（MC 字体） |

已归档的 `launcher.jar` 自编重建（Pojav 派生版）在 [`../90-archive/launcher-rebuild.md`](../90-archive/launcher-rebuild.md)。

## 约定

1. 每个适配一篇文档，固定小标题：现象 / 根因 / 补丁 / 数据流 / 分发 / 版本范围 / 复现 / 相关。
2. 补丁（`.patch`）与构建脚本放主仓库 `tools/`；notes 只记录设计与结论，不复制大段代码。
3. 用户 `.minecraft` / 用户数据 **零改动**是硬约束；覆盖走 app 自己的 staging 缓存或随包 rawfile。
4. 失败的尝试 / 历史探索进 [`../90-archive/`](../90-archive)。
5. 无补丁的版本必须**优雅降级**（回到原状，不崩）。
