# HOML el2 沙箱镜像（ref/org.xbstudio.homl.pro）—— 已删除，留档

> 状态：**已删除**（2026-09-09，释放 1.7G）。本页保留其**关键事实 + 完整结构快照**。
> 结构快照：`homl-sandbox-tree.txt`（758 dirs / 9350 files 全量相对路径）——**未随公开版发布**。
> 来源：`HOML-prod-signed.app` 的 el2 沙箱（HOML 运行时数据 + 内置 JRE）。

## 1. 这是什么

HOML 真机 el2 沙箱（`/data/storage/el2/base/haps/entry/`）的镜像，共 1.7G：

| 路径 | 体积 | 内容 |
|---|---|---|
| `haps/entry/files/HOML/.minecraft` | 1.5 G | HOML 游戏目录：`PCL.ini`、`assets`、`config`、`libraries`、`versions`、`launcher_profiles.json`；`versions/` = **1.16.5 / 1.19.4 / 1.21.10 / 26.1.2** |
| `haps/entry/files/jre25` | 129 M | HOML 内置 JRE 25 |
| `haps/entry/files/jre17` | 119 M | HOML 内置 JRE 17 |
| `haps/entry/files/controllers/` | — | 手柄配置：`00000000 / 4bf3d919 / 91a8c076 / 9329f2ce / Moonlight / xb_defalut.json` |
| `haps/entry/files/persistent_storage` | — | HOML Preferences（XML，见 §2.1） |
| `haps/entry/files/HOML/accounts/` | — | `<account>.json`（见 §2.2） |
| `cache/ files/ Dictionaries/ preferences/ .backup/` | 小 | 系统杂项（hiappevent 日志等） |

## 2. 关键事实（情报）

### 2.1 `persistent_storage`（HOML Preferences，XML）
键：`GameProfile` / `VersionSetting_global` / `UISettings` / `VersionSetting_{1.19.4,1.16.5,1.21.10,26.1.2}` / `MenuState`。

- `VersionSetting_global`：`global:true, isolation:true, maxMemory:2048, minMemory:1024, renderer:"libng_gl4es.so", controller:"00000000", jreVersion:"jre25"`。
- `VersionSetting_1.21.10`：`renderer:"libmobileglues.so", jreVersion:"jre25", isolation:false`。
- `VersionSetting_1.19.4 / 1.16.5 / 26.1.2`：`renderer:"libGLv4.so", jreVersion:"jre25"`。
- `GameProfile`：`lastVersion:1.21.10, lastAccount:<account>, homeType:0`。
- `MenuState`：`cursorSize:30, menuSize:50, mouseSensitivity:2.7, screenWidth:2002, screenHeight:1335, lockMouse:true, hideAllViews:true, …`。
- `UISettings`：`DarkMode:0, ThemeColor:green, HomeBackground:pure, FirstStart:false`。

> 对 Meowcraft 的意义：印证 HOML 的"**每版本渲染器 / jreVersion**"配置模型（我们已定案自己的 `libGLv4`/`openglv4`，见 [`../00-current/现状基线.md`](../00-current/现状基线.md) §5.2）。

### 2.2 离线账户格式（`HOML/accounts/<account>.json`）
```json
{"accessToken":"0","clientToken":"${clientId}","profileId":"00000000-0000-0000-0000-000000000000","username":"<account>","xuid":""}
```
→ 与 Meowcraft `OfflineAccount` 的契约一致（字段：accessToken / clientToken / profileId / username / xuid）。

### 2.3 内置 JRE release 元数据
- `jre25/release`：`JAVA_VERSION=25.0.1`、`JAVA_RUNTIME_VERSION=25.0.1-internal-adhoc.root.openjdk-25`、`LIBC=musl`、`OS_ARCH=aarch64`、`OS_NAME=Linux`、`SOURCE=".:git:78770bfaefd2+"`。
- `jre17/release`：`JAVA_VERSION=17.0.18`、`LIBC=musl`、`OS_ARCH=aarch64`、`SOURCE=".:git:a8784a04081a+"`。

（印证 [`../00-current/版本支持边界.md`](../00-current/版本支持边界.md) 的 JRE 家族结论：OHOS OpenJDK aarch64-musl 移植。）

## 3. 为何删除 / 如何还原

- 纯参考资料（**代码 / 工具 / 构建脚本 0 依赖**）；占 1.7 G → 2026-09-09 删除。
- 还原：从 `HOML-prod-signed.app`（安装包，`~/HO_DATA_EXT_MISC/Download/`）重新拆包；或设备上已装的 HOML（但 bundle public 不可读，无法直接 dump）。

## 相关
- 结构快照：`homl-sandbox-tree.txt`（未随公开版发布）
- 溯源：[`../30-supply-chain/provenance-master.md`](../30-supply-chain/provenance-master.md) §3/§5
- 历史：[`pojav桥启动.md`](pojav桥启动.md)、[`jvm-step1.md`](jvm-step1.md)
