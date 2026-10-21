# LWJGL2 legacy（MC 1.6.x–1.12.2）OHOS 适配复盘

> 战役时间：2026-09-11。作者：项目维护者。目的是让后人**只看这一篇**就能接手：
> 上游来源 → 编译链 → 移植层设计 → 每一处魔改与根因证据 → 会话全部改动 → 未完成与难度。
> 配套：[`LWJGL2自编-方案.md`](LWJGL2自编-方案.md)（设计/风险，§6 为实施结果）、
> `Harmomeow-Craft-Launcher/tools/lwjgl2/README.md`（操作手册/踩坑 1–16）、[`../render/SDL3适配-复盘.md`](../render/SDL3适配-复盘.md)（姊妹战役）。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 9 条](../../00-current/现状基线.md)。

---

## 1. 结果（现状）

**MC 1.6.x–1.12.2（legacy LWJGL2）在 OHOS 2in1 上可玩**：进主界面、进世界、键鼠、聊天输入（含中文）、Esc 菜单、
退出、窗口 resize、鼠标锁定、全屏（进入/退出）、**多数情况下一切正常**。
（实机验证为 1.7.10 / 1.8.9 / 1.12.2；**1.6.x**（json 声明 LWJGL `2.9.0/2.9.1-nightly`）走**同一份** `liblwjgl.so`，见 §2。）

- 产物：`liblwjgl.so`（Stage 2：178 TU / 导出 **2287**（GL 2262 / OpenAL 20，`Linux*` 121 全导出）；
  `DT_NEEDED=libc.so`；`.note.ohos.ident` 在；strip 后 ~320 KB），随包 tag `common`。
**实机验收（2026-09-11，用户执行）**：A1–A9 全通过 + B 组回归（1.16.5 / 26.3 / 启动器 UI）全通过。
**A10（副屏全屏）未测**（手头无副屏）→ 代码已实现（按窗口所在显示器取尺寸），现状见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 20 条 caveat ①。

- 已知未完成：**全屏期间显示器尺寸变化无法动态跟随**（§9，含难度估摸）；多显示器 B/C 档；A10（现状见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 20 条 caveat ①）；1.7.10 主菜单偶发局部一帧闪。

## 2. 上游与来源（全部可重建）

| 件 | 版本/位置 | 说明 |
|---|---|---|
| LWJGL2 源码 | `ref/lwjgl`，`git describe` = **`lwjgl2.9.3-19-g2df01dd7`**，commit **`2df01dd7`** | `git clone https://github.com/LWJGL/lwjgl.git && git checkout 2df01dd7`。**独立 clone**（app 仓库之外） |
| 我们的 liblwjgl | `stuffs/research/lwjgl2/out/liblwjgl.so`（`tools/lwjgl2/build_lwjgl2_meow.sh --with-display`） | 随包到 `Harmomeow-Craft-Launcher/libs/meowlwjgls/libs/arm64-v8a/liblwjgl.so`（**与 LWJGL3 的 `liblwjgl_343.so` 不冲突**：`loadLibrary("lwjgl")` → `liblwjgl.so`；mapper 只给 3.x 名加世代号（紧跟基名）） |
| MC 侧 jar | `lwjgl-2.9.0/2.9.1.jar`（**1.6.x** / 1.7.10）/ `lwjgl-2.9.4-nightly-20150209.jar`（1.8.9/1.12.2） | **不改**；`isLegacyLwjgl()` 按 `org.lwjgl.lwjgl:` 前缀（**并遵守 rules**）识别 |
| JNI 头来源 | `ref/lwjgl/src/hdrs-meow/org_lwjgl_*.h`（`javac -h` 产出，25 个） | 权威 native 签名 |
| JInput | `ref/lwjgl/libs/jinput.jar`（官方） | 头生成时 `input.Display → Controllers` 需要 |
| GL 翻译层 | gl4es（自编，v1.1.7，`tools/gl4es/`）；运行时 `libgl4es.so` | 桌面 GL→GLES；`glXGetProcAddressARB` 返回**它自己的**每个 `gl*` 符号（已核实） |
| 平台 GL | Mesa 25.0.1 + **Zink**（GL→Vulkan，Maleoon 916）；原生 GLES `libGLESv3.so`（ES 3.2） | 实测 renderer = `GL4ES using zink Vulkan 1.2` |
| OHOS SDK | `/data/service/hnp/ohos-sdk.org/ohos-sdk_26.0.0.18/ohos/native` | clang wrapper = `aarch64-unknown-linux-ohos-clang`；**无** `llvm-strip`/`llvm-readelf` |
| 短命工具（研究用，未随包） | 当时为 `$HOME/deveco/mcdump/cfdump.py`（**现不在本机**） | 纯 Python class 解析器（`javap` 在本机 SIGSEGV）——用于读 MC 字节码，可重建；现存同类工具见工作区根 `stuffs/research/jar_class_dump.py`、`stuffs/research/mc_class_probe.py` |

**反汇编 MC 的方法**（后续查 MC 行为时复用）：`javap` 不可用 → 用纯 Python 解析 `.class`，读常量池/方法体；
三个版本的 `Minecraft` 混淆名：1.12.2 `bib`、1.8.9 `ave`、1.7.10 `bao`。

## 3. 交付物清单

```
Harmomeow-Craft-Launcher/tools/lwjgl2/
  generate_sources.sh              生成：8 处理器 + javac -h 头（零 error）
  build_lwjgl2_meow.sh             构建：直驱 OHOS clang + 断言（Stage1/Stage2）
  README.md                        操作手册 + 踩坑 1–16 + 环境开关 + 复现走查
  patches/0001-generator-filer-bypass.patch   vendored 补丁（唯一源码改动）
  patches/README.md                补丁说明 + 重生成方法
  src-ohos/meow_port.h             共享私有头（状态块/bridge/事件结构/KeySym 表）
  src-ohos/meow_extgl.c            GL 取址 → gl4es（+NV 桩）
  src-ohos/meow_sys.c              getJNIVersion=19
  src-ohos/meow_display.c          LinuxDisplay 55 + PeerInfo/DisplayPeerInfo/PbufferPeerInfo/Canvas
  src-ohos/meow_context.c          LinuxContextImplementation 9 + 每帧镜像（全屏/指针锁）
  src-ohos/meow_input.c            LinuxEvent 27 + Keyboard 16 + Mouse 6（+事件合成）
  src-ohos/meow_cursor.c           光标 6
ref/lwjgl/                        （打补丁 + .gitignore 加 bin-meow/、src/hdrs-meow/）
Harmomeow-Craft-Launcher/libs/meowlwjgls/libs/arm64-v8a/liblwjgl.so + natives.manifest（tag common）
```

## 4. 构建链（逐步骤、可复现）

### 4.1 生成（`generate_sources.sh`，人跑，只需 JDK）
1. `javac -proc:none` 编 generator 树 + helper（opengl/opengles/opencl 的辅助类）。
2. **必须复刻上游 `generate-all` 全 8 步**（原因=Java 侧互引闭包，见手册 §4 表）。
   注意：**不要**排除 `ARB_cl_event.java`（上游 opengl 模式含 `ARB*`；其参数引用 CL 类型，故 helper 要含 opencl 类）。
3. 头：`javac -h` + **固定类清单**（照 `build.xml:297-374`）+ `-sourcepath "$JAVA:$GENJ"` + `-cp …:libs/jinput.jar`
   + `-XDshould-stop.ifError=GENERATE`。
4. 实测：generated/opengl 157 / openal 3 / opengles 47 / opencl 15 C；Java 472；**头 25**。

### 4.2 构建（`build_lwjgl2_meow.sh`，agent 可跑）
- 源集 = 上游集 **减去** X11/GLX/AWT/OpenCL + `src-ohos/*`（手册 §5）。
- 编译：`-D__MUSL__ -O2 -fPIC -std=c99 -pthread -Wall -Wunused -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0
  -D_GNU_SOURCE -D_FILE_OFFSET_BITS=64` + include（jni/hdrs-meow/common/common-opengl/common-KHR/common-CL/meowcraftbridge）。
- 链接：`-shared -fuse-ld=lld -z noexecstack -O2 -pthread -Wl,--no-undefined -lml -lpthread`
  （**无** `-lEGL/-lGLESv3/-lnative_window`：那些经 `dlsym` 走桥；**去掉** GLX 形状 `lwjgl.map`）。
- 断言（都能真失败）：逐符号 `require_sym`（Sys/getJNIVersion/getPointerSize/setDebug、BufferUtils、`GLContext_ngetFunctionAddress`、
  `GL11_nglAccum`、`GL20_nglVertexAttribPointer`、`AL10_initNativeStubs`…、stage2 再要求 `LinuxDisplay_nCreateWindow` 等 15 项）
  + 计数下限（opengl ≥2000、openal ≥20=上游完整面）+ 禁 X11/jawt `DT_NEEDED` + `.note.ohos`。
- 加固（审计后）：缺生成物**明确报错**；拒含空格路径；`--build` 指向 `$SRC`/`/` 即拒绝；值选项缺值报错；
  不再有无用的 `--api`。

### 4.3 随包
`tools/lwjgl/install_natives.sh --native liblwjgl.so=<out>`（tag `common`）→ 清模块 build（hvigor 不追踪 libs 增删）
→ `devecocli build --modules entry meowjre` → `devecocli run --skip-build …`。

## 5. 平台/架构事实（移植层依赖的全部契约）

- **进程级状态块**（`meowcraftbridge_environ.h`，ABI 冻结 0x27228）：`OHNativeWindow*`(0x0)、宽高镜像(0x271d4..)、
  SPSC 输入环(0x20)+`atomic eventCounter`(0x18)、`cursorX/Y`(0x27140/48)、`cLastX/Y`(0x27150/58)、
  `grabbing`(0x271e8)、`fsRequest`(0x271ec)、`fsX..fsH`。经 `MEOWCRAFT_ENVIRON`(hex 指针) 采用；**不引用符号**（零 DT_NEEDED）。
- **bridge 入口**（`dlsym(RTLD_DEFAULT)`，`libmeowcraftbridge.so` 由 `meowjrebridge` 以 RTLD_GLOBAL 预载）：
  `meowMakeCurrent(void*)`、`meowSwapBuffers()`、`meowSwapInterval(int)`、`meowGetCurrentContext()`、
  `meowSetFullscreenRequest(want,x,y,w,h)`、`meowGetGrabbing()`。
- **EGL/gl4es 顺序**：桥的 `meowMakeCurrent` → `egl_bind`/`egl_ensure_context`（gl4es 模式走 GLES2 分支）→
  `eglMakeCurrent` → `meowSwapInterval(0)` → **最后** `gl4es_init_once()`（`set_getmainfbsize` 注册回调、
  `set_getprocaddress`、`initialize_gl4es()`）→ **任何 GL 调用必须在其后**（我们的 `nMakeCurrent` 正好在 `GLContext.useContext` 之前）。
- **输入环**：`liblwjgl.so` 是**唯一**消费者（**绝不** `meowStartPumping/PumpEvents/StopPumping`，那是 GLFW/SDL 泵）；
  键/钮/滚轮/字符进环(`MEOW_EV_*`)，指针走最新值槽；**桥的指针过滤在 `grabbing` 时抑制绝对坐标、改用增量**
  （`input_bridge.c:905/968`）——这是"锁鼠标后菜单点不动"的机制根源。

## 6. 移植层：与 LWJGL2 Java 侧的硬契约（改 native 前必读）

| 主题 | 契约（证据） |
|---|---|
| 事件布局 | 自定义 `MeowPortEvent`，**不必模仿 Xlib ABI**（Java 只经我们的 accessor 访问） |
| 坐标 | native 给**原始左上原点**；Java 自己翻（`LinuxMouse.transformY`，`:195`） |
| 事件泵 | `LinuxDisplay.processEvents`：一个事件先 `mouse.filterEvent`/`keyboard.filterEvent` 再 display switch；`close_requested` 只由 `ClientMessage`(format 32, data0==delete_atom) 置位 |
| 焦点 | `isActive() = focused \|\| isLegacyFullscreen()`（`:816`）；`focused` 只在 FocusIn 置 true（`checkInput` 对 `parent==null` 早退）→ **窗口每次重建后必须补发 FocusIn** |
| 全屏 | 尺寸来自 `createWindow` 的 `mode.getWidth()`；**全屏时 resize 通知被抑制**（`Display.java:652`）；`initial_mode` 是 `final`（冻结） |
| 抓取 | `updatePointerGrab()` 全屏也 grab；**隐藏光标只在 `shouldGrab()`（Mouse.isGrabbed）**（`:432-440`） |
| 上下文销毁 | `releaseContext()` 清 caps 后 `destroy()` 会 `glGetError()` → native 的 `nIsCurrent` 必须随之变 false |
| 尺寸镜像 | 共享块的 width/height 归桥所有；native **不要写**（写了会触发 surface 重建 → 闪） |
| 字符 | `utf8LookupString(xic, event_ptr, buffer, pos, size)`；`positionBuffer(pos+len)` |
| 键位 | GLFW→X11：可打印 ASCII 32..126 **直通**（X11 KeySym==ASCII）；F1..F24/KP/修饰键按表；**返回 0=KEY_NONE → 键到不了游戏**（空格跳不了就是这个） |

## 7. 逐条坑 → 根因 → 证据 → 修法

> 详细叙述见 `tools/lwjgl2/README.md` §6（1–16）；这里给"根因一句话 + 决定性证据"索引，方便按证据回查。

| # | 现象 | 根因（一句话） | 决定性证据 |
|---|---|---|---|
| 1 | 进世界首帧 `Invalid operation (1282)` 崩溃 | `org.lwjgl.util.Debug` 门控 `Display.swapBuffers` 的**交换前** `checkGLError`，而 gl4es 模拟留良性错误 | 栈 `Display.swapBuffers(Display.java:617)`（=交换前那次） |
| 2 | 鼠标hover上下颠倒 | native 多翻了一次 Y | `LinuxMouse.transformY`（`:195`） |
| 3 | 退出时 `No OpenGL context found` | `nReleaseCurrentContext` 没让 `isCurrent` 变 false | 栈 `ContextGL.forceDestroy→getCapabilities` |
| 4 | 画面闪烁 | `nSetWindowSize/nReshape` 写了桥的尺寸镜像 → 桥重建 surface | 桥 `meowSwapBuffers` 的尺寸自愈逻辑 |
| 5 | `Mouse.create()` 失败（首帧崩） | `GetDirectBufferCapacity` 返回**元素数**，被当字节比较 | `LinuxMouse.nQueryPointer`(Native) → `reset(:96)` |
| 6 | 潜在崩溃 | 漏 include → 函数指针被截 32 位 | `-Wall` 隐式声明警告 |
| 7 | **任何按键即崩** | `utf8LookupString` 参数序反了（假 XIC 当事件指针） | cppcrash `@0x4943004d`、`pc liblwjgl.so(...utf8LookupString+44)` |
| 8 | 聊天每字打两遍 | `MeowSendChar` 同时推 `CHAR_MODS`+`CHAR`，翻译层两种都当字符 | 翻译层探针 + 生产侧日志对照 |
| 9 | 游戏里 Esc 无效 | Esc 只在 `imeActive` 时转发（`cancelImeByEsc` 早退） | 代码路径分析 + 实测 |
| 10 | 一次 F11 进全屏却立刻被弹回 | 本机 F 行键**重复投递 Down** → MC toggle 两次 | 生产侧 `meowSendKey k=300 a=1` **两次** |
| 11 | GL ERROR 刷屏 | MC 每帧查错 + gl4es 转发底层 GLES 错误 | MC 自身 `@ Post render 1282` 日志 |
| 12 | 全屏往返后进世界**直接暂停且死局** | 全屏 destroy+create 把 `focused` 清 false，而我们只合成过一次 FocusIn | `LinuxDisplay.java:506`、`:816`、`:1017` |
| 13 | 全屏主菜单锁鼠标点不进世界 | 指针锁错绑"是否全屏"（应跟 `Mouse.isGrabbed()`） | `LinuxDisplay.java:432-440` + 桥抑制绝对坐标 |
| 14 | 全屏画面卡左下角 | 全屏尺寸来自 DisplayMode，而我们报的是窗口尺寸 | `Display.java:652`（全屏抑制 resize）+ 模式冻结 |
| 15 | 全屏期间尺寸变化不跟随 | `initial_mode` final + MC 自己的 fullscreen 标志跳过 resize 检查 | MC 字节码三重门（§9） |
| 16 | 误把"良性 cppcrash"当崩溃证据 | 平台每次启动固定产一个（JIT 段、无 liblwjgl） | 判据：真崩溃 pc 落在对应 so 的 r-x 段 |

## 8. 排查方法论（踩过的弯路也在内）

1. **读 `.logs/`**：`Harmomeow-Craft-Launcher/.logs/This PC-*-hilog.txt`（hilog 导出）——含 `[jre_stdout]/[jre_stderr]`（MC/JVM 输出）
   与 ArkTS/bridge 的 `D meowSendKey…/D char cp=…/GameInput/IME/apply resize` 行。**先读日志再猜**。
2. **cppcrash 判读**：`/data/log/faultlog/faultlogger/cppcrash-<bundle>-<uid>-<ts>.log`；看 `Reason:Signal:…@<addr>`
   （**故障地址经常直接指认 bug**，如假令牌）、fault thread 帧（**是否带模块名/函数名** = 真崩溃判据）、
   内嵌的设备日志（能还原崩溃前后时序）。`pc` 在 JIT rwx 匿名段 = Java/JIT 层（多为良性那个）。
3. **JVM 侧**：`-XX:ErrorFile=` 可写 hs_err（含 Java 栈）；`-Xlog:exceptions=info`、`-Xlog:library=debug`；
   **禁用** `-XX:-UseSignalChaining`（OHOS 预装 SIGSEGV handler → 启动即死）。
4. **native 探针**：翻译层 `fprintf(stderr, …)`（**`printfDebug` 会被 LWJGL2 的 debug 开关静音**，因为 legacy 关了它）；
   只打**状态翻转**，避免刷屏（用户铁律）。**用完必撤**。
5. **归因三方**：生产侧（ArkTS/bridge 日志）↔ 我的翻译层（探针）↔ LWJGL2/MC（字节码/源码）。三方对照能一刀切清。
6. **不要凭直觉"猜修"**：本战役每个结论都有上表证据；两次误判（把良性 cppcrash 当按键崩溃、把 1282 当 native 错）
   都是因为"先猜后验"。

## 9. 未完成：全屏期间尺寸变化（动态调整）+ 难度估摸（已调研）

**MC 的尺寸检测是三重门**（1.7.10 `bao`/1.8.9 `ave`/1.12.2 `bib` 字节码实证）：

```
Display.update() 之后：
  if (MC自己的fullscreen标志) return;     // bib.T / ave.T / bao.N ← 全屏时直接跳过
  if (!Display.wasResized()) return;      // 而该标志在全屏被 Display.java:652 强制 false
  if (宽高与 MC 缓存相同) return;
  resize(w,h);                            // a(II)V —— 唯一刷新 视口/ScaledResolution/GUI缩放/framebuffer 的地方
```

因此：**所有"LWJGL 层"手段单独都无效**（改 `current_mode`、翻 `window_resized`、ArkTS 再 maximize、`setDisplayMode` 都不行），
因为门①是 MC 自己的标志。**唯一有效杠杆 = JNI 直调 MC 的 `resize(II)`**（私有方法 JNI 可调；名字三版一致 `a(II)V`，
单例 getter 分别 `bib.z()` / `ave.A()` / `bao.B()`），并同时把 `Display.current_mode` 换成新尺寸的 fullscreen-capable
`DisplayMode`。**估摸：①②（检测/镜像 + 改 current_mode）≈1–2h 低风险；③（JNI 调 `resize`）≈3–5h 中风险；实机 2–4 轮。**
残留：`initial_mode` 是 `final` → 每次重新进全屏会先闪一帧旧尺寸（随后被逐帧修正）；依赖逐版本混淆名 → 必须写成
**显式版本表 + 缺版本即禁用**。

**多显示器**：A 档（按**窗口所在显示器**取尺寸，`WindowProperties.displayId` → `getDisplayByIdSync`，回退默认）**已实现**；
B（`win.on('displayIdChange')`/`display.on('change'/'add'/'remove')` 实时镜像，需动共享块 ABI 两个头）、
C（JNI 自愈 `current_mode`）未做。

## 10. 本次会话的全部改动（跨模块影响已审）

| 文件 | 改动 | gating |
|---|---|---|
| `tools/lwjgl2/**`（新） | 生成/构建脚本、src-ohos 移植层、补丁、README | 新增，纯工具 |
| `ref/lwjgl`（vendored） | `GeneratorVisitor` 绕 Filer + `.gitignore` 两项 | 仅生成期；不参与运行时 |
| `MinecraftLauncher.ets` | legacy: `util.Debug=false`、`-Dmeow.screen.w/h`（窗口所在显示器优先）；`-cp` 自补；保留 MC 的 LWJGL2 jar；`isLegacyLwjgl`（**已修：遵守 rules**）；新增 import/LOG 常量 | 均按 `isLegacyLwjgl(...)` 分支（`-cp` 自补为无害 no-op） |
| `ClasspathStager.ets` | `dropOtherLwjglJar` 改白名单精确名、`pruneStaleJars`、`lwjglClasspathOk` 形态断言 | legacy/现代分别分支；断言对两代都跑（失败即中止启动） |
| `GameInputController.ets`（**全渲染器共用**） | Esc 无条件转发；`cancelImeByEsc` 只去激活；**功能键重复 Down 丢弃**；**已删**每键 down 的 hilog | 无 gating（但已静态核对：Esc 计数不变、长按状态不受影响） |
| `GameWindow.ets`（共用） | 启动前查**窗口所在显示器**尺寸 → `setWindowDisplaySize`（**已修：仅 legacy 才查**） | 消费方在 legacy 分支 |
| `libs/meowlwjgls/libs/arm64-v8a/liblwjgl.so` +`natives.manifest` | 新增 legacy native（tag common） | 只被 legacy 的 `loadLibrary("lwjgl")` 命中 |
| `notes/**`（本仓库外） | 本篇 + 方案 §6 + README 等 | 文档 |

**共享 native/桥零改动**（`libs/meowcraftlib/src/main/cpp/**` 无 diff ✓）；legacy 只**读**状态块 + `dlsym` 既有导出；
它**写**的字段：`grabbing/isGrabbing`、`fsRequest/fsActive/fsX..fsH`、`cLastX/cLastY`、消费环时 `outEventIndex/eventCounter`、
以及仅在 ≤0 时补 `width/height/savedWidth/savedHeight`。**同进程同时只运行一个游戏**（`:game`），故不与 SDL 路径争用。

## 11. 复现清单（一键顺序）

见 `tools/lwjgl2/README.md` §1（四步：取源码 → 打补丁 → 生成 → 构建 → 随包 → 构建 app → 部署）。

**可复现性（已实测，非"应该"）**：规则见 `notes/00-current/工程与规范.md:126-127`（≥3 次干净重建 + `cmp`）。
一键校验脚本 `tools/lwjgl2/verify_reproducible.sh --src <lwjgl2 源码树> [--work <临时目录>] [--with-generator]`（A=native 3 次重建+cmp+无嵌路径断言；
B=重跑 generator 后 `diff -r`，需 JDK）。⚠️ **2026-09-29 起基础脚本已"环境无关化"**：`verify_reproducible.sh` 与
`generate_sources.sh` 的 `--src` 均为**必需参数**、`--work` 默认落到 `${TMPDIR:-/tmp}`（本机跑法见 `tools/lwjgl2/README.md` 的「本机配方」块）。
**实测（2026-09-11）**：`liblwjgl.so` 3 次干净重建**逐字节一致**（`cmp`），
sha256 `df8864669dfc1703598903ae29a9ab70a733f603e8a8600a715939209eb47b11`，322600 B；不嵌绝对路径/时间戳；
**同 tag + 同 SDK + 同源码路径**下可复现。（⚠️ 该哈希是**当时**的记录；随包件在 2026-09-29 已换为 `73ac4aa8…`（323,336 B，JNI 契约订正版），
故"与随包件同哈希"只对 2026-09-11 那一版成立。）**生成物（B 段）同样实测一致**：
`src/generated` 472 / `src/native/generated` 222 / `src/hdrs-meow` 25 文件 `diff -r` 全等 ⇒ **全链可复现**。
最短验证：`sh tools/lwjgl2/generate_sources.sh --src <lwjgl2 源码树>`（应零 error、25 头）→
`sh tools/lwjgl2/build_lwjgl2_meow.sh --src <lwjgl2 源码树> --sdk-native <sdk-native> --out <out-dir> --with-display`
（应 178 TU / 2287 导出 / `NEEDED: libc.so`）。

## 12. 关键 file:line 索引（回查用）

- LWJGL2：`Display.java` 77/130/493-517/523-526/616/652/1264/1317-1350；`LinuxDisplay.java` 347-358/366-369/415/419-430/
  432-440/443/483-495/506-507/613-626/729-755/816-817/869-872/938-968/1017/1026-1047/1108-1125/1167-1178；
  `LinuxMouse.java` 93-106/112-124/134-149/195-197；`Mouse.java` 348-381/442-475/561-593/647-673；
  `LinuxKeyboard.java` 180-262/290-335；`LinuxEvent.java` 59-104；`DisplayMode.java` 62-68。
- 上游 native：`src/native/linux/org_lwjgl_opengl_LinuxKeyboard.c` 122-153；
  `src/native/linux/opengl/{display.c,context.c,org_lwjgl_opengl_Display.c}`；`src/native/common/common_tools.c` 367-381（JNI_OnLoad）。
- 平台：`meowcraftbridge_environ.h` 88-137；`input_bridge.c` 260-283/693-709/897-920/956-975；
  `egl_gl.c` 141-187（gl4es init）/419-460（resize/swap）/503-557（makeCurrent/swap/interval）。
- 应用：`MinecraftLauncher.ets`（legacy 分支/`isLegacyLwjgl`）、`ClasspathStager.ets`、`GameInputController.ets`
  （Esc/F 键/IME）、`GameWindow.ets`（显示器查询/全屏/隐形 TextInput）。
