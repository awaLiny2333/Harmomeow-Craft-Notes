> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../20-design/render/渲染链-结论.md`](../../20-design/render/渲染链-结论.md) 与 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) A4/A6。

# 05 - OpenGTX 可行性实证：2in1 设备确定不支持（零代码结案）

> 日期：2026-09-09
> 方式：**零代码实证**——只在设备本机查 syscap 清单与系统库，未改任何代码。
> 前置：[`../../20-design/render/渲染链-结论.md`](../../20-design/render/渲染链-结论.md) §5 backlog 第 4 条（"真正的 90Hz 出路"）。
> 关联：[`02-surfaceholder-docs.md`](02-surfaceholder-docs.md)（帧率 API 能力）、[`03-sdk-header-facts.md`](03-sdk-header-facts.md)（`external_window.h` 无帧率 API）。

---

## 1. 结论

**OpenGTX（Graphics Accelerate Kit / 游戏渲染加速服务）在本机（MateBook 2in1）不可用，路径关闭。**

两条独立证据同时为否：

| 检查 | 结果 |
|---|---|
| 设备 syscap 是否含 `SystemCapability.GraphicsGame.RenderAccelerate` | **否**（该字符串在 `/system/etc/syscap.json` 中出现 **0** 次） |
| 系统是否随包 `libopengtx.so` | **否**（`/system/lib64`、`/vendor/lib64` 均无，`gtx|accelerat` 模糊匹配也为空） |

与 SDK 元数据预测完全一致：`hms/ets/api/device-define/syscap-version.json:1100` 中 RenderAccelerate 的 deviceTypes = phone 5.0.0(12) / tablet 5.0.0(12) / tv 6.1.0(23)，**不含 2in1**；`2in1-hmos.json:94` 只有 `SystemCapability.GraphicsGame.LaunchAcceleration`。

---

## 2. 实证记录（原样）

开发机 = 运行机，直接在设备 shell 执行（裸 `hdc` 不可用；本机可直接查文件系统）。

```sh
$ param get const.product.devicetype
2in1

$ ls -l /system/lib64/libopengtx.so
ls: /system/lib64/libopengtx.so: No such file or directory

$ grep -o '"SystemCapability\.GraphicsGame[^"]*"' /system/etc/syscap.json | sort -u
"SystemCapability.GraphicsGame.AssetAcceleration"
"SystemCapability.GraphicsGame.LaunchAcceleration"

$ grep -c "RenderAccelerate" /system/etc/syscap.json
0

$ ls /system/lib64/ | grep -i opengtx        # 空
$ ls /vendor/lib64/ | grep -i opengtx        # 空
$ ls /system/lib64/ | grep -iE "gtx|accelerat"   # 空
```

syscap 清单结构确认（该文件是设备能力清单，非应用清单）：

```json
// /system/etc/syscap.json:935-939
{
  "component": "graphics_game_sdk",
  "syscap": [
    "SystemCapability.GraphicsGame.LaunchAcceleration"
  ]
}
```

> 即：设备只下发了 `graphics_game_sdk` 的 **LaunchAcceleration**（游戏启动加速），没有 **RenderAccelerate**（渲染加速/OpenGTX）。

---

## 3. 复验命令（一行，未来换设备/升级后可再跑）

```sh
grep -o '"SystemCapability\.GraphicsGame[^"]*"' /system/etc/syscap.json | sort -u; ls /system/lib64/ | grep -i opengtx
```

判定：输出含 `SystemCapability.GraphicsGame.RenderAccelerate` 且存在 `libopengtx.so` → 才值得进入 Probe-1（见 §5）。

---

## 4. 为什么"即便支持也未必解决诉求"（文档层结论，来自侦查A）

- OpenGTX 是**自适应 LTPO/SOC/DDR 治理**（`SCENE_MODE` / `TOUCH_MODE` / `ADAPTIVE_MODE`，`targetFPS∈[30,144]`），**不是"强制 90Hz"开关**。
- 文档对"已经 60fps、想上 90Hz"**无任何延迟收益声明**；`bpta-ltpo-description` 反而警告锁高帧会增加负载/功耗、可能把延迟转移到别处。
- 需每帧喂 `DispatchFrameRenderInfo`（相机位置 + yaw/pitch/roll）+ 场景切换喂 `DispatchGameSceneInfo`，集成成本中等但收益存疑。
- 无 ArkTS API，仅 C/C++；无 AGC/游戏分类/权限门槛（仅 `module.json5` metadata `GraphicsAccelerateKit_LTPO: true`）；不支持设备时 `HMS_OpenGTX_CreateContext` 返回 **nullptr**（不崩）。

---

## 5. 未来触发条件（何时重开这条路径）

满足**任一**才值得再评估：

1. 换到 **Phone / Tablet / TV** 设备类（OpenGTX 文档支持面）；或
2. 平台把 `SystemCapability.GraphicsGame.RenderAccelerate` 加进 **2in1** syscap 并随包 `libopengtx.so`（用 §3 一行复验）；或
3. 诉求从"上 90Hz"变为"动态稳帧/降功耗"（OpenGTX 的本职），且设备支持。

否则维持现状：**60Hz 基线 + 输入延迟优化**（已定案，见 `../输入延迟调查证据.md`）。

---

## 6. 未执行的可选项（留档，不需要）

若将来 §5 条件满足，最小探针为：

- CMake：`target_link_directories(<target> PRIVATE ${HMOS_SDK_NATIVE}/sysroot/usr/lib/${OHOS_TOOLCHAIN_NAME})` + `target_link_libraries(<target> PUBLIC opengtx)`（裸 `-lopengtx` 会找不到库，头文件已全局可见）。
- `module.json5`：`"metadata": [{"name": "GraphicsAccelerateKit_LTPO", "value": "true"}]`。
- native 一次性调用：`CreateContext → SetConfiguration(mode/targetFPS/packageName/engineType=OTHERS_ENGINE/…) → Activate → DispatchGameSceneInfo(PLAYING, recommendFPS=90)`，逐调用打返回码；`CreateContext==nullptr` 即设备不支持。
