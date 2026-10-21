# Step1 打通记录：JVM(JLI_Launch) 在 app 进程内启动

日期：2026-09-07
状态：✅ 已跑通（JVM 25 aarch64 完整启动，属性/模块系统验证通过）

> ⚠️ **历史记录**（写于改名之前）：文中 `jrelib` = 现 `meowjre`/`meowcraftlib`（`meowjre25` 为更早的历史名），
> `libjrebridge.so` = 现 `libmeowjrebridge.so`，`jre_bridge.cpp` = 现 `meowjrebridge.cpp`，
> `libs/jrelib/...` = 现 `libs/meowcraftlib/...`。**当前命名/状态见 [`../00-current/现状基线.md`](../00-current/现状基线.md)。**

## 目标

Meowcraft 要在鸿蒙 PC（ARM Kirin）的 app 进程内直接启动内嵌 JRE（无子进程/exec）。
Step1 验证目标：`dlopen(libjli.so)` → `JLI_Launch` 能跑起来并打印属性/版本。

## 为什么打不通：三层叠加的平台限制

### 1. 数据区禁执行（el2 filesDir）
- 现象：JRE 放 filesDir 后 `dlopen(libjli.so)` 一律 `Invalid argument`(EINVAL)。
- 排除过程：ACL `ALLOW_WRITABLE_CODE_MEMORY` + 正式签名后依旧 EINVAL → 与权限/ACL 无关。
- 结论：el2 数据分区为分区级禁 exec（类 W^X）。任何可执行代码都不能放 filesDir。

### 2. musl namespace 隔离（entry 看不到 HSP 的库）
- 现象：entry `dlopen(/data/storage/el1/bundle/jrelib/libs/arm64/libjli.so)` 报
  `MUSL-LDSO: namespace=moduleNs_default ... check ns accessible failed`。
- 文件存在（access=true），纯 namespace 拒绝；`libIsolation:false` 也无效。
- 结论：HSP 模块 native libs 属独立 musl namespace，entry 无法跨 namespace dlopen。

### 3. JLI 的 java.home 标准布局依赖
- 现象：进入 JLI_Launch 后报 `could not open `'`（jvm.cfg 路径空）/
  `could not find libjava.so`。
- 原理：标准 JLI 用 `dladdr(libjli.so)` 反推 java.home，要求 libjli 位于
  `<java.home>/lib/...` 标准布局。JRE .so 平铺在 `libs/arm64-v8a/` → 推断必然错/空。

## 破解路径与关键决策

### 决策 A：数据/代码分离，照抄 HOML 的 HSP 结构
- 依据：`bm dump` 实证 HOML = entry + jre17.hsp + jre25.hsp，
  `nativeLibraryPath: jre25/libs/arm64`（.so 全在 HSP 的 el1 native libs 区）。
- 落地：建 `jrelib` HSP 承载 31 个 JRE .so（libs/arm64-v8a）+ 数据 tar（resfile）。
- filesDir 只放只读数据（modules/conf），可执行 .so 全在 el1 区。

### 决策 B：启动桥编进 HSP，与 JRE 同 namespace
- 依据：HOML 的 launcher（launcher.har 反汇编 `launchJVM@0xcb24` = getenv("jli_path")
  →dlopen→dlsym JLI_Launch）是嵌在 jre25.hsp 内部的，不是 entry 去 dlopen。
- 落地：native 桥（NAPI `libjrebridge.so`，导 `launchJvm`）编译进 jrelib；
  entry 只 `await import('jrelib')`，桥在**自己 namespace** 内 dlopen 同目录 libjli.so。
- 验证：`JreBridge: JLI_Launch begin` —— 前两层障碍同时击穿。

### 决策 C：反汇编华为移植版 libjli，用官方环境变量覆盖布局
- 依据：`strings` + `objdump` 反汇编 libjli.so，发现 OpenHarmony 移植补丁专用变量：
  - `OHOS_JAVA_HOME`（getenv @ 0x94bc）：java.home 覆盖
  - `OHOS_DL_DIR`（getenv @ 0x9558）：JVM .so dlopen 目录覆盖
- 落地：JLI_Launch 前 setenv：
  - `OHOS_JAVA_HOME = <filesDir>/jre25`（数据/modules 的家）
  - `OHOS_DL_DIR = <libsDir>`（平铺 .so 的家，HSP namespace 内）
  - `LD_LIBRARY_PATH = libsDir:javaHome/lib`
- 验证（决定性）：
  - `sun.boot.library.path = el1/bundle/jrelib/libs/arm64`（JVM 库从 HSP el1 加载）
  - `java.home = el2 filesDir/jre25`（108MB modules 从 filesDir 加载）
  - `-XshowSettings:properties` 全量属性、`--list-modules` 完整模块集、`JLI_Launch returned 0`

## 为什么 JRE 数据仍要解压到 filesDir（设计理由，勿随意改动）

JVM 要求 java.home 是一个**真实文件系统目录**：启动时会用普通文件 API
open/mmap 数百个具体路径（`lib/modules` 镜像、`lib/jvm.cfg`、`conf/`、
`lib/security/cacerts`、`release` 等）。鸿蒙沙箱约束：

- rawfile（随包资源）只能走 `OH_ResourceManager` 流式 API，**没有文件路径**，
  JVM 无法 open/mmap → 不能当 java.home。
- HSP libs 区（el1）只允许 .so 供 dlopen，**无法自定义目录树**。
- 能提供"真实目录 + 逐文件路径 + 100MB+ 空间"的只有 filesDir（el2）。

与"el2 禁 exec"不冲突——**刻意数据/代码分离**：

| 内容 | 位置 | 原因 |
|---|---|---|
| 31 个可执行 .so | el1 HSP libs（OHOS_DL_DIR） | 需 dlopen/执行 |
| modules/conf/bin/release（纯数据） | filesDir/jre25（OHOS_JAVA_HOME） | 只 open/mmap 读，无需 exec |

HOML 同样整份解压到 filesDir（当时镜像 `ref/org.xbstudio.homl.pro/haps/entry/files/jre25`，**已删**，见 [`homl-sandbox-mirror.md`](homl-sandbox-mirror.md)）。

## 打通后的工程化修复

- app 启动即崩 SIGABRT：局部 `std::thread` joinable 析构 → terminate；
  修复 = 全链路 detach 线程，shared_ptr 传停止信号。
- 进 app 自动跑 JVM：aboutToAppear 触发 → 收敛为按钮触发（用户约定：默认静默）。
- JVM 日志落盘：freopen 写文件再轮询 → 改 pipe→hilog 零落盘。
- hilog 输出前缀混乱：按 read 块上抛 → 行缓冲逐行上抛，每行统一 `[jre_stderr]` 前缀。
- 更新安装一律 `bm install -r`（用户约定：禁卸载，保 filesDir 数据）。

## 待办 / 遗留

- **[已解决] 真实 javac 产物 main 执行验证（2026-09-07）**：用 Maven 编译的
  com.example.App（javac, major 52）打进 jre25.tar.gz 根，`-cp <filesDir>/jre25
  com.example.App` 启动 → 真机输出 `Hello World!` 等 33 行，JLI_Launch returned 0，
  零异常。**手工 python Hello.class 的 ClassFormatError 悬案正式关闭**（证实是我
  手写字节码 bug，JVM 加载/执行链路完全正常）。测试类源自 stuffs/java_test_target。
- **[记录] JRE 数据瘦身优化（暂不动，待后续评估）**：filesDir/jre25 解压 127MB 中
  有 ~20MB 是 lib/*.so 冗余副本——JVM 实际加载走 el1（sun.boot.library.path 指向
  HSP libs），filesDir 内 .so 仅为"完整布局"附带品。可做瘦身版数据 tar（去 lib/.so
  只留 modules/conf/bin/release，127MB→~107MB）。HOML 未瘦身，保持同构亦可。
- 定位 JRE25 上游 git（release 内 `78770bfaefd2+`），锁定正式来源。
- [已清理] 测试期 App 验证已还原：GLPreviewView 测试按钮恢复 -XshowSettings -version；
  rawfile tar 已移除 com/example 测试类。

## 参考

- libjli.so 全量反汇编存档：`stuffs/research/misc/jli.asm`
- 桥实现：`libs/jrelib/src/main/cpp/jre_bridge.cpp`
- 测试入口：entry GLPreviewView「启动 JRE」按钮
