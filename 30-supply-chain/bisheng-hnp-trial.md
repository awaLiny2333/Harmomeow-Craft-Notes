# BiSheng(毕昇) JDK hnp 嵌入试验记录（2026-09-08，结论：不可嵌入，已回滚）

> 目标：评估华为生态社区 hnp 包的 BiSheng JDK（ref/bishengjdk17_0_13_06.hnp、8u432_b11.hnp）
> 能否替换/补充 OpenJDK25 作为本项目内置 JRE。结论见文末。试验已完整回滚，
> 当前线上=OpenJDK26（meow_jre）分体方案，可玩。

## 来源与形态（证据）
- ref 下两个目录即解包态：`jdk-17.0.13` / `jdk-8u432`。
- `release`：IMPLEMENTOR=BiSheng、`LIBC=musl`、OS_ARCH=aarch64、SOURCE 含
  `ohos_build/libs/*` 与 `ohos_build/sdk/third_party_musl` → **OpenHarmony 生态官方构建**。
- 布局标准：`lib/libjli.so`、`lib/server/libjvm.so`、`lib/modules`、`jvm.cfg`、`conf/`；
  多出 jsound/j2pcsc/saproc（vs OpenJDK25 组）。

## 可行性检查（通过项）
- ELF64/AArch64/DYN；NEEDED libc.so(musl 无 .so.6) + libc++_shared —— 与我们的加载环境匹配。

## 阻塞链（判定不可嵌入）
1. **libjli 不支持分体启动**：strings 对比 —— OpenJDK25 libjli 含 `OHOS_DL_DIR`/`OHOS_JAVA_HOME`
   （支持"so 平铺 el1 + java.home 指 el2 数据"），BiSheng17 libjli 只有 `/lib/libjava` 标准路径
   （按 argv0 推导 java.home，绝对路径加载 `<home>/lib/libjava.so` 等）→ 数据目录 .so 又被 C2 抽走 → `could not find libjava.so`。
2. **整树无法落 el1**（平台打包限制，探针实证）：
   - hvigor 只把 `libs/arm64-v8a/` **顶层 *.so** 物化进 HSP/el1；**子目录与非 .so 全部丢弃**
     （`jre/bin|conf|release|lib/modules` 计数=0）；
   - filesDir/el2 **禁 dlopen**；resources/rawfile 非真实目录，当不了 java.home。
   - ⇒ "完整 java.home 树于可执行区"无任何承载位。BiSheng 属"整树自运行"型 JDK，不适配嵌入式启动器。

## 次要坑（已绕过）
- BiSheng `libsyslookup.so` 安装期 fs-verity 拒绝（`9568393`/ret `-768` "Key was rejected by service"）：
  摘除该文件即可安装（FFM 专用，MC 不用）。其 `.note.ohos.ident`（namesz=5/type=0）与可装库
  （namesz=12/type=1）不同，未证为根因。
- 期间执行了 `devecocli signature generate --force`（build-profile 新密钥），与结果无关。

## 结论 / 后续路线
- **继续 OpenJDK（OHOS 官方移植）家族**：其 libjli 支持 `OHOS_DL_DIR` 分体启动，与当前
  el1-flat + filesDir 数据架构契合。
- 将来要 17/21：优先找 **OpenHarmony 官方 OpenJDK 17/21 移植**（25 同源老版本），装前先
  strings 验证其 libjli 含 `OHOS_DL_DIR`；无则同此结论不可嵌入。
- 毕昇 hnp（8/17）留档 `ref/`，不采用。多版本并存（meow-jres 已备好）留待官方移植版就绪。

## 平台 exec 门槛定论（2026-09-08 补充：为何"写进 el1"也不行）
- **挂载层无 noexec**：el1/base、el2/base、bundle 均为 `rw,nosuid,nodev,...`（实证 mount 输出）。
- **真正机制 = 文件级 fs-verity + code-sign**：安装时 `installs/CODE_SIGN` 对**每个随包 native**
  执行 `EnableCodeSignForFile → Fs-verity has been enabled`（9568393 排障日志实证）。
  ⇒ 可执行性的唯一来源 = "随包安装、installer 打上 fs-verity 签名"。
- 推论（三面全堵）：
  1. 运行时写入 el1/base 或 el2/base 的文件**无该签名 → dlopen 一律 EINVAL**（与 filesDir 探针同源）；
  2. el1/bundle 代码区只读，写不进；
  3. 打包侧只物化 libs 顶层 .so（hvigor 限制）。
  ⇒ **凡 libjli 不带 OHOS_DL_DIR/OHOS_JAVA_HOME 的整树自定位 JDK 不可嵌入**（无 root/无系统签名前提）。
  系统库（libGLv4）可 dlopen 系系统预签，不矛盾。

## 模块拆分平台事实（2026-09-08，df08e5a/fa76734/e41d2b6 实证）
- **fs-verity/code-sign 对所有随包 native 授予**（无论模块有无 native 构建）。曾加过"native 身份 stub"，
  但 **e41d2b6 实测去掉 stub 游戏照跑** → stub 多余。此前 EINVAL 根因纯是**跨模块 namespace**（见下），
  与 fs-verity/模块构建身份无关。
- **libIsolation:true = 每 HSP 独立 namespace/子目录**：跨模块绝对路径 dlopen
  （meowcraftlib 桥 → meowjre libjli）在本设备 **EINVAL**。HOML 参考（host entry→隔离 jre HSP）
  在其环境可行，本机不成立。
- **libIsolation:false = 各 HSP native 全拍平进宿主合并目录**
  `/data/storage/el1/bundle/libs/arm64` → 同 namespace、同目录 dlopen（= 拆分前语义）。
  采用此模型：项目/打包层两模块（meowcraftlib、meowjre）职责清晰，执行层合一。
  未来若系统支持 host→isolated，把 JRE 模块切回 libIsolation:true 即可（代码已解耦，launchJvm 收 jreHome/jreLibsDir 参数）。
- 注意：两模块均非隔离时勿各自带 libc++_shared.so（同名冲突）——已删 meowjre 副本，由 craft 供一份。

### ⚠️ 终版更正（fa76734，两个子 agent 反推 HOML 后定案）
- **HOML 从不做宿主→隔离跨模块 dlopen**：launcher.har 的桥 native 静态并入**每个**隔离 jre HSP，
  libjli 的 dlopen 是"模块内自加载"。我们此前多次 EINVAL 全是**跨模块**（craft→meowjre）所致。
- **最终拓扑（=HOML 模型，当时实机验证）**：每个 JRE 一个 **libIsolation:true 自足 HSP**
  （JRE .so + 组件 + 经 **meowcraftlib(HAR)** 静态并入的桥/c++），Index re-export 桥；
  entry 只 `import('<jreVer>')` 并按其模块目录配 OHOS_DL_DIR/jli 路径 → 版本共存/切换 = 多份自足 HSP + 换 import。
- 教训：**dlopen 方必须与被 dlopen 目标同模块同目录**；想"模块分离"就用 HAR 并入（复制成本换 namespace 正确性）。
