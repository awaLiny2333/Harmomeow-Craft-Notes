# OpenAL OHAudio 后端（OpenSL ES → OHAudio 迁移）

> 日期：2026-09-09 ｜ 状态：**已实机验证**（MC 1.21.10 音频/BGM 正常，默认走 OHAudio）
> 相关：[`openal-ohos.md`](openal-ohos.md)（OpenSL 后端移植，本迁移的前置）、
> 溯源 [`../30-supply-chain/provenance-master.md`](../30-supply-chain/provenance-master.md)；
> 工具 `Harmomeow-Craft-Launcher/tools/openal/README.md`
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 12 条](../00-current/现状基线.md)。

## 0. 一句话

OpenSL ES 在 OHOS 上已被官方标记「不再推荐」；OHAudio（OH_Audio）是推荐替代。上游 OpenAL Soft
**没有 OHAudio 后端**，我们在自编 `libopenal.so` 里**新写了一个**（`alc/backends/ohaudio.cpp`），
并把它注册为**默认后端**（OpenSL 保留作回退）。

## 1. 背景与目标

- 现状（迁移前）：自编 OpenAL Soft 走 **OpenSL 后端**（HOML 同源），当时已实机验证音频正常。
- 官方态度：文档树已改名 `OpenSL_ES开发指导_不再推荐`；`API参考/OpenSL_ES` 明确
  「**不再推荐**…请开发者从 OpenSL ES 切换到 OHAudio」。
- 目标：在不破坏现有可用路径的前提下，新增 OHAudio 后端并切换为默认，拿到官方推荐路径 +
  低时延 FAST 通路 + 时钟/时间戳能力。

## 2. 可行性结论（3 路 agent 调研，2026-09-09）

- **可用**：设备 `/system/lib64/ndk/libohaudio.so`（410KB）存在；syscap `SystemCapability.Multimedia.Audio.Core`
  在设备 syscap 与 SDK 配置中均在；SDK(API23) 的 157 个 OH_Audio 符号是设备 204 个的子集。
- **API 面**：全部所需 ≤ API 23（`SetRendererWriteDataCallback`@12、`GetAudioTimestampInfo`@15、`GetLatency`@23）。
- **零先例**：OpenAL Soft 上游 / HOML / Amethyst / HMCL 均无 OHAudio 用法 → 首个实现。
- **风险**：FAST 在 2in1 上未证实（需运行时 `GetFastStatus()`）；渲染回调为**拉取式**且要求快速返回。

## 3. 实现（`tools/openal/ohaudio/`）

| 项 | 选择 | 理由 |
|---|---|---|
| 播放混音模型 | **直渲**：`OnWriteData` 回调里 `mDevice->renderSamples()` | 与 Oboe/CoreAudio 同构；无额外线程/ring/拷贝，延迟最低 |
| 捕获模型 | `OnReadData` 推入 ring buffer，`captureSamples` 从 ring 读 | 拉/推解耦（同 Oboe 捕获） |
| 回调 | `OH_AudioRenderer_OnWriteDataCallback` / `OH_AudioCapturer_OnReadDataCallback` | 现代分离式回调（API 12/20） |
| 配置 | `USAGE_GAME` + `ENCODING_TYPE_RAW` + 请求 `LATENCY_MODE_FAST` + 10ms 帧 | 游戏用途；FAST 失败系统自动降级 NORMAL |
| 格式 | U8/S16LE/S32LE/F32LE；生成后 `GetSampleFormat/GetChannelCount/GetSamplingRate` 回查 | OHAudio 不做格式转换 |
| 注册 | `BackendList` 中 `ohaudio` 在 `opensl` **之前** | 默认 OHAudio；OpenSL 保留可回退 |
| 错误 | 错误回调 → `mDevice->handleDisconnect` | 设备断开/系统错误 |

## 4. 数据流

```
JVM org.lwjgl.openal → System.loadLibrary("openal") → meowjre/libs/arm64/libopenal.so
  → OpenAL 选中 ohaudio 后端（BackendList 首个可用）
  → OH_AudioStreamBuilder_Create(RENDERER) → Set* → GenerateRenderer
  → OH_AudioRenderer_Start → 系统回调 OnWriteData(buffer,len)
      → mDevice->renderSamples(buffer, len/frameSize, channels)
```

## 5. 分发与部署

产物与部署同 [`openal-ohos.md`](openal-ohos.md) §5（同一个 `libopenal.so`）。
- A/B 与回退：`ALSOFT_DRIVERS=opensl`（强制 OpenSL）/ `=ohaudio`（强制 OHAudio）；
  或 `git checkout -- libs/meowlwjgls/libs/arm64-v8a/libopenal.so` 回到上一版。

## 6. 版本范围

基线版本与升级动机见 [`openal-ohos.md`](openal-ohos.md) §6（OpenAL Soft 1.24.3）。
OHAudio 头/库来自 OHOS SDK（本项目 API 23；设备 API 26），后端源已按 1.24 API 改写
（`open(std::string_view)`、`enumerate`、fmt、`DeviceBase` 的 `m*` 成员）。
- ⚠️ 1.24.x 的导出受 `-Wl,--version-script=libopenal.version`（`local: *`）与 `ALC_API` 双重控制：
  `alcEventIsSupportedSOFT`/`alcEventControlSOFT`/`alcEventCallbackSOFT` 上游**两处都缺** → 默认被裁，
  但我们需导出给 MC（LWJGL dlsym）。故新增第三个补丁器
  `Harmomeow-Craft-Launcher/tools/openal/patch_openal_events_export.py` 补 `ALC_API` +
  在 `libopenal.version` 列名。

## 7. 复现

构建脚本同 [`openal-ohos.md`](openal-ohos.md) §7（`rebuild_for_meowcraft.sh` 自动做 OpenSL 移植 + OHAudio 后端 + 构建）。
- 产物 sha256（strip 后）：`fececaeea7f785c8f47a9b4f804421b3922524f0c2df87419d21256a680b2d6c`（OpenAL Soft **1.24.3**，
  33 `alc*` + 176 `al*` 导出，含 `ALC_SOFT_system_events`）；同 tag + SDK + 构建路径下可复现。
  （历史：1.23.1 版 sha `e56a5b88…` / `9c2ae446…`，已退役。）

## 8. 踩坑与经验

- **拉取式回调**：`OnWriteData` 必须填满 `audioDataSize` 字节；填不满要给静音/返回 INVALID。
- **实时约束**：回调线程内禁阻塞/加锁/日志/控制 API；`handleDisconnect` 只能在错误回调里调。
- **单位混用**：回调长度=**字节**、`GetFrameSizeInCallback`=**帧**、`GetTimestamp`=**帧+ns**、
  `GetLatency`=**ms**。`renderSamples` 的 `frameStep` = 声道数。
- **FAST 是尽力而为**：需 48kHz + 支持设备 + 帧 5/10/15/20ms，否则静默降级；本机 2in1 未逐项实测 FAST 状态。
- **复用既有链路**：`tools/openal/` 的「参数化脚本 + wrapper + 导出断言 + 可复现」全部沿用；
  新增一个安装器 `patch_openal_ohaudio.py`（拷贝源码 + 锚定改 CMake/config/alc.cpp）。
- **验证**：`config.h` 有 `HAVE_OHAUDIO`、`BackendList` 顺序、`DT_NEEDED libohaudio.so` 三者
  共同证明后端已启用；OpenAL 后端**无运行时回退**，故「无崩溃 + 音频正常」即证明 OHAudio 真在跑。

## 9. 遗留 / 待办

- **FAST 状态（已实测，2026-09-09）**：`fast=1`（**已开**），48kHz / S16LE / 10ms 回调 / 20ms OpenAL 缓冲；
  `GetLatency()` 路由延迟 ≈ **25ms**（HAL/硬件路径，应用层无杠杆）。**5ms 回调实验**：`fast=1`、应用侧缓冲
  20ms→10ms，但 25ms 路由延迟不变、听感无差异 → 回退 10ms（余量更大）。结论：应用侧已近最优。
- **`getClockLatency` 精化**：当前用基类估计；可改用 `GetAudioTimestampInfo` 提升 A/V 同步精度。
- **`ALC_SOFT_reopen_device` 告警**（与 OHAudio 无关，OpenSL 版日志亦有）：上游 `alext.h` 的
  `alcReopenDeviceSOFT` 未加 `ALC_API` → 不导出 → LWJGL dlsym 失败告警；如要消除需给该符号加导出。
- **诊断探针**：`ohaudio.cpp` 保留一条一次性 hilog probe（tag `MeowOHAudio`，打印采样率/格式/回调帧/
  FAST/延迟）。注意 bridge 设了 `ALSOFT_LOGLEVEL=0` 禁用 OpenAL 自身日志，故探针走 hilog 直出。
- **1.24.3 实机（2026-09-10）**：**1.21.10 与 26.1.2 音频均正常**；26.x 的 `CallbackDeviceTracker` 因
  `ALC_SOFT_system_events`（已导出）不再 NPE。输入法亦正常。

## 相关

- OpenSL 移植：[`openal-ohos.md`](openal-ohos.md)
- 工具：`Harmomeow-Craft-Launcher/tools/openal/README.md`
- 官方文档：OHAudio 播放 `…/using-ohaudio-for-playback`、低时延 `audio-fast-playback`、
  切换指南 `replace-opensles-by-ohaudio`
