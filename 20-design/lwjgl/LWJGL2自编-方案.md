# LWJGL2 OHOS 自编方案（MC 1.6.x–1.12.2 legacy）

> 问题：MC ≤1.12.2 用 **LWJGL 2**（`org.lwjgl.*`：`Display`/`Keyboard`/`Mouse`/`GL11…`）；随包只有 LWJGL3 → 老版本撞
> `UnsatisfiedLinkError: liblwjgl.so`（`org.lwjgl.Sys.<clinit>`）。用户决定：**自编 native LWJGL2**（不走 LWJGL2-API-shim）。
> 源码：`ref/lwjgl`（官方 legacy，`lwjgl2.9.3+19-g2df01dd7`，2016）。相关：[`../../00-current/版本支持边界.md`](../../00-current/版本支持边界.md)、记忆 `meowcraft_legacy_lwjgl2_campaign`。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 9 条](../../00-current/现状基线.md)。

## 0. 目标与关键事实

- 产 **`liblwjgl.so`**（aarch64 上 `Sys.loadLibrary` 只找 `liblwjgl.so`，**不找 `liblwjgl64.so`**）；**只编 native**。
- **JNI_VERSION=19** 跨 2.9.0–2.9.4（含 nightly）一致；JNI 符号名跨代稳定 → **一份 native 同时服务 MC 1.6.x–1.12.2**（1.6.x/1.7.10 = 2.9.0/2.9.1；1.8.9/1.12.2 = 2.9.2/2.9.4）。
- **生成代码不在库**（`src/generated`、`src/native/generated` 被 gitignore）→ 构建前必须**先跑 generator** 产出
  `src/native/generated/opengl/*.c`（`Java_org_lwjgl_opengl_GL1x_*`）与 JNI 头。

## 1. 构建（现成 ant 不能直接用）

- 官方：`build.xml` → `platform_build/linux_ant/build.xml`；依赖 **JDK8 + Ant + javah**（JDK10+ 无 javah，需 `javac -h`）。
- **aarch64 会踩坑**：`linux_ant/build.xml:42-57` 的 `uname -m` 判定在 aarch64 落到"32 位"分支，且链接 `-lX11 -lXcursor -lXrandr -lXxf86vm -ljawt` → 必挂。
- **结论：自写最小构建**（CMake/Make），只编下面 fileset，链接 OHOS 的 `-lEGL -lGLESv3 -lnative_window -lc -lm`；去掉 `lwjgl.map`（无 version-script，避 lld 兼容问题，多导出无妨）。

## 2. native 源码：复用 vs 重写（最小集）

| 组 | 文件 | 处置 |
|---|---|---|
| 通用 JNI | `src/native/common/*.c`（`common_tools.c`、`org_lwjgl_BufferUtils.c`、`org_lwjgl_openal_AL/ALC10/ALC11.c`、`extal.c`） | **复用**（可裁 OpenCL/AWT） |
| GL 通用 | `src/native/common/opengl/*.c`（`extgl.c`、`org_lwjgl_opengl_GLContext.c`） | **复用** |
| **生成 GL JNI** | `src/native/generated/opengl/*.c` | **生成**（generator） |
| GL 平台 | `src/native/linux/opengl/{extgl_glx.c, org_lwjgl_opengl_Display.c, org_lwjgl_opengl_LinuxContextImplementation.c, display.c, context.{c,h}, GLX.c}` | **重写** → EGL + OHNativeWindow |
| 输入 | `src/native/linux/{org_lwjgl_opengl_LinuxEvent.c, LinuxKeyboard.c, LinuxMouse.c, org_lwjgl_input_Cursor.c, LinuxPeerInfo.c}` | **重写** → 复用现有输入环（`meow_environ`） |
| Sys | `getJNIVersion`(19)/`getPointerSize`/`setDebug` | 保留（在 Display.c / common_tools.c） |
| OpenAL | `linux_al.c` + `common/org_lwjgl_openal_*` | 复用（dlopen 我们的 `libopenal.so`） |

> 关键接缝：① GL 取址 `GLContext.ngetFunctionAddress` → `extgl_GetProcAddress`：**改 `extgl_glx.c` 为 `eglGetProcAddress` + `dlsym`（指向 gl4es `libgl4es.so`）**；② 窗口：把 `X11PeerInfo{Display*,screen,drawable}` 换成 OHNativeWindow 句柄；③ 输入：X11 事件 → 我们的 SPSC 输入环。

## 3. Java 侧（不可忽略）

- **`LinuxSysImplementation` 静态块**（`LinuxSysImplementation.java:48-64`）：`java.awt.Toolkit.getDefaultToolkit()`（无 X11 → `AWTError`）+ `System.loadLibrary("jawt")`（已 try/catch 吞）。
  → 对策（择一）：**(a)** `-Djava.awt.headless=true`（若 JRE 含 `java.desktop`，headless 可过）；**(b)** 用惯用 **overlay 影子类**：在自研 jar 里提供一个不打 AWT 的 `org.lwjgl.LinuxSysImplementation`（classpath 优先）——更稳、可脱 AWT。
- `LinuxDisplay`/`LinuxKeyboard`… 若走"改 jar"路线，则须与 MC 的 `lwjgl.jar` 分叉；**首选不改 jar**：native 内部伪造 `XEvent` 布局让现有 `LinuxEvent/Keyboard/Mouse` 的 `nGet*` 能读（脆弱），或影子这几个类。

## 4. 实施阶段

1. **生成**（人跑，JDK）：跑 generator → `src/native/generated/opengl/*.c` + `org_lwjgl_*.h`（OpenGL 一路；弃 OpenCL/AWT）。
2. **移植平台 native**：写 OHOS 版 `extgl`（→gl4es）/`Display`/`Context`（EGL+OHNativeWindow）/输入（输入环）。
3. **自写构建**：`tools/lwjgl2/` 编译 → `liblwjgl.so`；`install_natives.sh` 治理 + manifest（tag `common`）；随包。
4. **ArkTS**：legacy 版本 classpath 用 MC 的 `lwjgl-2.9.x.jar` + 我们的 `liblwjgl.so`（natives 走 `libs/arm64`）；形态断言更新（legacy：MC lwjgl2 jar + 我方 liblwjgl.so）。
5. **实机**：先 1.12.2（最接近），再 1.7.10。

## 5. Top 风险
1. **generator 需 JDK8/Ant**（source 1.5/1.6；javah 已废）——需 `-source 8` 改写 + `javac -h`。
2. **AWT/headless**（见 §3）——不解决 → `Sys.<clinit>` 仍炸。
3. **X11 头/`jawt` 链接**——必须切断。
4. **X 事件布局**（若不改 jar）——脆弱，可能需要影子类。
5. `--version-script` 在 lld——去掉即可。
6. `Sys.loadLibrary` 先于 `createImplementation`（`Sys.java:112` 先载 native）→ **native 必须最先可用**。

## 6. 实施结果与实机决策（2026-09-11，已跑通 1.6.x–1.12.2；1.7.10 / 1.8.9 / 1.12.2 实机）

**产物**：`tools/lwjgl2/`（`generate_sources.sh` 零 error → 25 JNI 头；`build_lwjgl2_meow.sh --with-display`
→ 178 TU / 导出 2287 / `DT_NEEDED=libc.so` / 321 KB，`liblwjgl.so` 随包 tag `common`）；
`tools/lwjgl2/src-ohos/`（`meow_port.h` + `meow_{extgl,sys,display,context,input,cursor}.c`）；
补丁 `patches/0001-generator-filer-bypass.patch`。生成器/构建细节见 `tools/lwjgl2/README.md`。

**实机踩坑（都是实测定案，改之前先读 `tools/lwjgl2/README.md` 的"实机踩坑"1–8 条）**：
`org.lwjgl.util.Debug` 对 legacy 必须 false（否则 1282 崩溃）；JNI `GetDirectBufferCapacity` 是**元素数**；
鼠标 Y 不要在 native 翻转（`LinuxMouse.transformY` 已翻）；`nReleaseCurrentContext` 必须让 `nIsCurrent` 变 false；
不要写共享块的 `width/height` 镜像（会触发桥重建 surface → 闪）；`utf8LookupString` 参数序是
**`(xic, event_ptr, …)`**（写反 = 按键即崩）。

### 6.1 GL 错误上报：legacy **默认静默**，可一键恢复（重要）

- **现象**：MC 1.6.x–1.12.2 **每帧**调用 `glGetError()`（自身日志 `########## GL ERROR ########## / @ Post render /
  1282: Invalid operation`），而 gl4es 的 `glGetError` 会**转发底层 GLES 错误**（`ref/gl4es/src/gl/getter.c`），
  于是 gl4es 内部调用遗留的错误被 MC 每帧刷屏。
- **决策**：legacy 默认设 **`LIBGL_NOERROR=1`**（gl4es 文档化开关：`if (globals4es.noerror) return GL_NO_ERROR;`）→ 刷屏消失。
  - **实现位置**：`tools/lwjgl2/src-ohos/meow_context.c` 的 `nMakeCurrent` **首次调用时** `setenv("LIBGL_NOERROR","1",1)`。
    这样做的原因：gl4es 只在 `initialize_gl4es()` 里读一次该开关，而桥是在 `meowMakeCurrent()` 内才调用它 →
    我们在其之前设置即可生效；且只影响 legacy（`liblwjgl.so` 只服务 1.6.x–1.12.2），**不需要改共享桥**
    （`meowjrebridge.cpp:212` 仍统一设 `LIBGL_NOERROR=0` 供 LWJGL3/26.x 用）。
  - **恢复上报（深挖 gl4es 具体错误时用）**：在游戏进程环境里设 **`MEOW_LWJGL2_GLERRORS=1`** → 我们跳过上面的设置，
    MC 的 `########## GL ERROR ##########` 会重新出现（用它定位是哪个 GL 调用让 gl4es 置错）。
- **代价**：`LIBGL_NOERROR=1` 会连带隐藏**真正**由 `glGetError` 上报的错误 → 仅在 legacy 生效，并保留上面的逃生口。

### 6.2 已结案（2026-09-11 实机确认）

- **文本输入"双份" → 已修**：根因在**共享桥的生产契约**——`meowjrebridge.cpp` 的 `MeowSendChar` 对一个字符同时推
  `MEOW_EV_CHAR_MODS`（`charMods`）与 `MEOW_EV_CHAR`（`ch`），该"成对推送 + mods 在前"是给 **GLFW/SDL 的 Java
  回调路径**的约定；走**输入环**（LWJGL2）时两条都进环 → 翻译层若两种都当字符，MC 就收到两遍。
  **修法**（`tools/lwjgl2/src-ohos/meow_input.c`）：字符事件入翻译时把紧邻的"另一种、同码点"一条一并消费
  （真重复按键之间必隔 KEY 按下/释放，不会误吞）。**未改共享桥/SDL 路径**。
- **Esc 无效 → 已修**：`GameInputController.handleImeKey` 的 Esc 分支原只在 IME 激活时经 `cancelImeByEsc` 转发，
  而后者 `!imeActive` 即早退 → "IME 未激活但隐形 TextInput 仍持焦"时 Esc 被吞。**修法**：Esc 分支无条件
  `sendImeKey(GLFW_KEY_ESCAPE)`；`cancelImeByEsc` 收敛为只去激活。
- **文本输入整链**：物理键只发 KEY（`preImeKey`，供按键绑定）＋字符只经隐形 IME `onChange → sendImeChars`（单源）；
  **不要**在可打印键路径再补发字符（会与 IME 路径双发）。排查用翻译层临时 `fprintf(stderr,…)` 打事件流，并对照
  桥/jrebridge 生产侧日志（`D char cp=…`/`D meowSendKey k=…`）判归属。

### 6.3 仍待解决

- **闪烁**：仅 1.7.10 主菜单、局部、偶发一帧（用户判定可暂缓）。
- **AWT**：`LinuxSysImplementation` 静态块的 `Toolkit.getDefaultToolkit()` 风险未实际触发（1.7.10/1.8.9/1.12.2 均无
  `AWTError`），保留对策（见 §3）。
- **gl4es 内部那个 1282**：现被 `LIBGL_NOERROR=1` 静默（见 §6.1）；要深挖时设 `MEOW_LWJGL2_GLERRORS=1` 复现。

