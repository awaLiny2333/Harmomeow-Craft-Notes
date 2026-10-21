# Pojav 桥启动打通记录（MC 1.21.10 真机跑通）

> 本文记录从 commit `59e7c4c`（JRE 测试按钮 revert）之后，把 Minecraft 1.21.10 通过
> **Pojav 桥（HOML 同款 launcher.jar + pojavexec 系 native）** 在 Meowcraft 内真正跑通
> （画面显示 + BGM）的全过程：踩过的坑、反编译发现、参数对照、目录/黑箱 so 情报。
>
> 状态：✅ MC 主菜单画面已在独立游戏窗口显示、BGM 正常。遗留：关窗退出、实时 resize（见文末）。
>
> ⚠️ 渲染后端定案更新（2026-09-07 晚）：当前生效后端为**系统桌面 GL `libGLv4.so`
> （`openglv4`）**，非下文早期步骤使用的 mobileglues。本文第 3/4/5 节涉及
> mobileglues 的步骤是打通历史；当前代码见 [`清理杂项-2026-09-07.md`](清理杂项-2026-09-07.md)（历史档，非现状）第 1 节。
>
> ⚠️ **历史记录**（写于改名之前）：文中 `jrelib` = 现 `meowjre`/`meowcraftlib`（`meowjre25` 为更早的历史名），
> `libjrebridge` = 现 `libmeowjrebridge`，`jre_bridge.cpp` = 现 `meowjrebridge.cpp`；
> 第 5/6 节的黑箱 `libpojavexec.so`/`libhoml_bridge.so` **已于 Stage B/C 退役**。
> **当前命名/状态见 [`../00-current/现状基线.md`](../00-current/现状基线.md)。**

---

## 1. 战果时间线（59e7c4c → 画面显示）

| 阶段 | 关键动作 | 结果 |
|------|---------|------|
| 起点 | 上 commit：vanilla 直启已到 GLFW init，撞 glibc liblwjgl/musl 死结 | 需换 Pojav 桥路线 |
| 1 | 确认 HOML launcher.jar 反编译：`PojavLauncher.main` → `launchMinecraft` → `Tools.launchMinecraft` 反射 MC main | 确定桥入口语义 |
| 2 | 修复 `cacio.managed.screensize` 缺失 → 越过 line54 NPE | JVM 进入 MC 类加载 |
| 3 | 账户文件改 filesDir 沙箱自立门户 → 越过 `MinecraftAccount.load` | 进入 Tools 反射 |
| 4 | 补 `-DServer_Ip=` → 越过 getMinecraftArgs:147 NPE | 反射启动 MC main |
| 5 | 清残留官方 LWJGL jar（prune）→ 消除类冲突 | 定制 lwjgl.jar 生效 |
| 6 | el1 natives 全面替换为 HOML musl 集（52 so）→ 消除 glibc 加载死结 | LWJGL 可 dlopen |
| 7 | **发现双 native 启动链 bug**：env 全加在未生效的 libmeowassets | 崩溃原因核心 |
| 8 | HOML env + 预 dlopen mobileglues 补到**实际生效的 libjrebridge** | LWJGL 全家加载成功 |
| 9 | 独立 GameWindow 弹窗 + homl_bridge.surfaceChanged 注入 surfaceId | **画面显示 + BGM** |

---

## 2. 架构：两条 native 启动链（本战役最大坑）

Meowcraft 工程里有 **两条** native 启动链，曾导致修复全部无效：

| 链路 | 源文件 | 产物 | 是否真启动链 |
|------|--------|------|------------|
| entry 直启 | `entry/src/main/cpp/jre_launcher.cpp` | `libmeowassets.so` | ❌ 否（仅 GL 预览/installJre/probe 用） |
| **jrelib HSP 桥** | `libs/jrelib/src/main/cpp/jre_bridge.cpp` | `libjrebridge.so` | ✅ **是**（崩溃栈证据） |

- 崩溃日志栈帧明确是 `libjrebridge.so`（不是 libmeowassets.so）；hilog 的 `[jre_stdout]/[jre_stderr]`
  前缀来自 `jre_bridge.cpp` 的 pipe reader。
- **教训：改 native 启动逻辑前，先确认崩溃栈里实际跑的是哪个 .so。**
- `jre_bridge.cpp` 的关键实现：dlopen `<self-dir>/libjli.so` → JLI_Launch；stdout/stderr 走 pipe
  reader 逐行上抛 hilog（tag JreBridge）。JLI 阻塞，必须在 detach 线程跑（joinable 析构 = SIGABRT）。

### jre_bridge.cpp 现设的 env（JLI 前，HOML initEnv 等价）
```
LD_LIBRARY_PATH  = <libsDir>:<filesDir>/jre25/lib
OHOS_JAVA_HOME   = <filesDir>/jre25
OHOS_DL_DIR      = <libsDir>          // el1 平铺 .so 区
HOME             = <filesDir>
POJAV_RENDERER   = opengles_mobileglues
POJAV_NATIVEDIR  = <libsDir>
NGG_DIR_PATH     = <cacheDir>/
DLOPEN           = libspirv-cross-c-shared.so
LIBGL_USE_MC_COLOR=1  LIBGL_GL=31  LIBGL_ES=3
LIBGL_NORMALIZE=1  LIBGL_NOINTOVLHACK=1  LIBGL_NOERROR=0
ALSOFT_LOGLEVEL=0
```
随后 **预 dlopen `<libsDir>/libmobileglues.so`（RTLD_NOW|RTLD_GLOBAL）**，再 dlopen libjli。
HOML 原版顺序：homl_bridge.set_env 全量 → bridge.dl_open(renderer) → jvm_Launcher(args)。
渲染器预加载失败 HOML 是**硬失败**（不发 JVM）。

---

## 3. 逐关踩坑记录（含修复）

### 3.1 PojavLauncher.java:54 NPE —— `cacio.managed.screensize` 缺失
- 现象：`System.setProperty` NPE（栈：CHM putVal ← Properties ← System.setProperty ← PojavLauncher:54）。
- 反编译 launcher.jar 的 `PojavLauncher.launchMinecraft` 字节码 + 行号表还原：
  ```java
  // line 53: String s = System.getProperty("cacio.managed.screensize");
  // line 54: System.setProperty("glfw.windowSize", s);  // s==null → NPE
  // line 55: s.split("x");
  ```
- 根因：launcher.jar 期望 JVM 参数带 `-Dcacio.managed.screensize=WxH`（HOML JVMLauncher L160 传了），
  我们漏传 → getProperty null。
- 修复：pojav 分支加 `-Dcacio.managed.screensize=${w}x${h}`。

### 3.2 账户文件 —— filesDir 沙箱自立门户
- `Tools.<clinit>` 目录推导（反编译）：
  ```
  DIR_BUNDLE=getProperty("BUNDLE_PATH")  DIR_GAME_HOME/DIR_APP_DATA=getProperty("POJAV_HOME")
  DIR_ACCOUNT_NEW=POJAV_HOME+"/accounts"  DIR_GAME_NEW=POJAV_GAME_DIR
  DIR_HOME_VERSION=DIR_GAME_NEW+"/versions"  DIR_HOME_LIBRARY=DIR_GAME_NEW+"/libraries"
  ASSETS_PATH=DIR_GAME_NEW+"/assets"  DIR_GAME_PROFILE=getProperty("user.dir")
  ```
- `MinecraftAccount.load(name)` = `Tools.read(DIR_ACCOUNT_NEW+"/"+name+".json")`，无 try/catch，
  文件缺失直接崩。
- 尝试写 `.minecraft` 父目录 `stuffs/accounts/` → `13900001` 权限拒（picker 授权仅覆盖 .minecraft 子树）。
- **决策：账户自立门户**，放 filesDir 沙箱：`<filesDir>/pojav-home/accounts/Player.json`，
  并把 `POJAV_HOME` 指向它。json 字段对齐 HOML：
  ```json
  {"accessToken":"0","clientToken":"0","profileId":"00000000-0000-0000-0000-000000000000","username":"Player","xuid":"0"}
  ```
  （HOML 真机 `<account>.json`：clientToken 用 `${clientId}`、xuid 空串，本实现用 "0" 兼容。）
- **经验：POJAV_HOME 只驱动 DIR_ACCOUNT_NEW**（DIR_GAME_HOME/DIR_APP_DATA 无其它消费），
  可安全指向任意沙箱目录。

### 3.3 Tools.getMinecraftArgs:147 NPE —— `-DServer_Ip=`
- 反编译：`getProperty("Server_Ip").isBlank()`；缺属性 → null → NPE。
- HOML JVMLauncher L100 恒传 `-DServer_Ip=${serverIp}`。修复：传 `-DServer_Ip=`（空串走跳过分支）。

### 3.4 残留官方 LWJGL jar 类冲突
- Tools.launchMinecraft 把 `java.class.path` 每项 + `generateLaunchClassPath` 全部
  `addURL` 到 PojavClassLoader，再反射 MC main。classpath 里同时有官方 lwjgl-3.3.3.jar 与
  定制 lwjgl.jar 时，官方 `org.lwjgl.glfw.GLFW` 先加载 → 找官方 libglfw.so（glibc）→ 死。
- 修复：staging 目录**只增不删**导致旧 jar 残留。新增 `pruneStaleJars`：白名单 = 当前
   collectJarSources 文件名 + meowcraft_extras 固定 jar（lwjgl/launcher/gson-2.13.1/jsr305/patchjna_agent），
  删除其它 `.jar`。日志 `prune ... removed 8 stale jars`。

### 3.5 el1 natives：官方 glibc → HOML musl 集
- 我们 el1 里原有官方（Maven Central linux-arm64）liblwjgl.so/libglfw.so/libopenal.so/libjemalloc.so：
  NEEDED 全是 `libc.so.6/ld-linux-aarch64.so.1` → musl 加载必失败（早期 vanilla 已实锤
  `Error loading shared library ld-linux-aarch64.so.1`）。
- 从 HOML 真机安装包 `HOML-prod-signed.app`（本地 `HO_DATA_EXT_MISC/Download/`）解出
  `entry-default.hap` → `libs/arm64-v8a/` 全套 musl so，替换/新增到
  `libs/jrelib/libs/arm64-v8a/`（构建后 HSP 落到设备 el1 `/data/storage/el1/bundle/jrelib/libs/arm64`）。
- **删除**：libglfw.so / libjemalloc.so / liblwjgl_freetype.so（glibc 残留、Pojav 不用）。
- **替换**：liblwjgl.so(liblwjgl 447424) / liblwjgl_opengl / liblwjgl_stb / liblwjgl_tinyfd /
  libopenal / libjnidispatch（HOML musl，NEEDED 仅 libc.so）。
- **新增**：见 §6 黑箱 so 清单。
- 注意：libfreetype.so 与 jre 自带一致（SAME 大小 701912），不用改名覆盖，删掉
  `-Dorg.lwjgl.freetype.libname=liblwjgl_freetype`（此前为避免同名冲突的 hack）。

### 3.6 Render thread SIGSEGV（NULL+0xc）真凶 = env 没生效
- 崩溃模式：`[LWJGL] Loading JNI library: lwjgl` → Render thread 立崩，JIT 栈 + libjvm 底，
  无 Java 异常。反复多轮。
- 三个子 Agent 并行深挖（exlpore）结论：
  1. 定制 lwjgl.jar `Library.loadSystem("lwjgl")`：优先 `org.lwjgl.librarypath` 目录
     `System.load(绝对路径)`；其次 java.library.path。liblwjgl.so 导出 1605 个
     `Java_org_lwjgl_system_JNI_*` 与定制 jar 完全匹配（无符号缺失）。
  2. **实际生效的 libjrebridge 一条 env 都没设**（POJAV_RENDERER/LIBGL_*/DLOPEN 全缺）→
     pojavexec `pojavInitOpenGL` 读不到 renderer → 空函数表 → NULL 调用崩。
  3. pojavexec JNI_OnLoad 顺序：hookExec → installLwjglDlopenHook（覆盖
     `DynamicLinkLoader.ndlopen`）→ EMUI 缓解 → 按 `POJAV_SKIP_JNI_GLFW` 决定是否注册 GLFW JNI。
- **修复：把 HOML env + 预 dlopen mobileglues 加到 `jre_bridge.cpp`（而非 jre_launcher.cpp）**。
- 验证：hilog 出现 `JreBridge v2 (HOML env init)` + `env set` + `pre-dlopen mobileglues ok`。

### 3.7 HSP 更新不生效的坑
- `devecocli run --module entry` 只装 entry，**不重装 dynamicDependencies 的 jrelib HSP**。
- **安装顺序铁律（用户 2026-09-07 强调）：先装 HAR/HSP 再装主 hap**，保证资源包最新；
  曾因顺序不对（主模块先装 / HSP 未更新）在迭代中吃大亏。
- 改 jrelib native 后必须 `devecocli run --module jrelib` 单独部署 HSP；
  稳妥做法：`devecocli run --device <serial> --module entry jrelib` 一次部署；
  或手动 `hdc install -r <jrelib.hsp>` 先行、再 `-r <entry.hap>`。
- 用版本横幅（`JreBridge v2`）区分新旧 HSP 是否生效。

### 3.8 jna tmpdir 不可写（非致命）
- `-Djna.tmpdir` 被 version json 的 `${natives_directory}` 覆盖成 el1（只读）→
  JNA Warning `not writable`。但 JNA 从 `jna.boot.library.path` 直接 load jnidispatch，
  不落盘 → 非致命，仅告警。natives_directory 宏现指向 el1（为了 java.library.path 能找到
  liblwjgl.so）——el1 只读但对 load 无碍。

### 3.9 跨 UIAbility 传参（黑屏真凶）
- 现象：窗口黑屏 + `inject abort: missing launch params`；日志 `GameAbility onCreate
  params={...}` 只有系统参数、无我们的 gameRoot。
- **根因：模块级单例不跨 UIAbility 共享**（各 Ability 独立 JS 运行时/模块实例）。
- 修复：改回 **want.parameters** 传参：
  ```ts
  const want: Want = { bundleName, abilityName: 'GameAbility',
    parameters: { gameRoot, jsonPath, versionId } };  // ArkTS 允许 Want 上下文内联字面量
  ```
  GameAbility.onCreate 读 want → setGameLaunchParams 写**同 Ability 内**单例 → GameWindow 页读取。
- **ArkTS 坑**：`const p: Record<string,Object> = {}` 再逐字段赋值 → `arkts-limited-stdlib`
  （Object.create 禁）或 `arkts-no-untyped-obj-literals`；**Want 字面量内联 parameters 子对象
  有类型上下文反而合法**。

---

## 4. 我们 CMD 与 HOML JVMLauncher 的关键对齐（最终形态）

JVM 参数（buildLaunchArgv pojav 分支，MinecraftLauncher.ets）全量对齐 HOML
`JVMLauncher.ets overridableArguments`，关键项：
```
-Djava.system.class.loader=net.kdt.pojavlaunch.PojavClassLoader
-Dorg.lwjgl.opengl.libname=libmobileglues.so     ← HOML 1.21.10 真机配置
-Dorg.lwjgl.glfw.checkThread0=false
-Dorg.lwjgl.vulkan.libname=libvulkan.so
-Dglfwstub.initEgl=false  -Dglfwstub.windowWidth/Height=1280x720
-Dcacio.managed.screensize=1280x720
-Dpojav.path.minecraft=<gameRoot>
-Dpojav.path.private.account=<filesDir>/pojav-home/accounts
-DPOJAV_HOME=<filesDir>/pojav-home   -DPOJAV_GAME_DIR=<gameRoot>
-Djna.nosys=false  -Doshi.disable.*=true  -XX:ActiveProcessorCount=8
-Duser.language=zh -Duser.country=CN -Duser.timezone=Asia/Shanghai
-Dlog4j2.formatMsgNoLookups=true  -DServer_Ip=
-Dorg.lwjgl.util.Debug=true -Dorg.lwjgl.util.DebugLoader=true -Dorg.lwjgl.opengl.Debug=true
-DDEBUG=true -Dcpu.name=harmonyos -Dnet.minecraft.clientmodname=Meowcraft
-Dfml.earlyprogresswindow=false -Dloader.disable_forked_guis=true
-Dsodium.checks.issue2561=false -Djdk.lang.Process.launchMechanism=FORK
```
version json 的 `${natives_directory}` 宏 → **el1**（nativeLibsDir），使最终
java.library.path=/data/storage/el1/bundle/jrelib/libs/arm64（LWJGL System.load 命中 musl so）。

工具类（launcher.jar）反编译确认的运行时行为：
- `Tools.launchMinecraft`：getMinecraftArgs(account,version) → generateLaunchClassPath →
  把 java.class.path 每项 `appendToClassPathForInstrumentation` + cp 每项 `addURL` 到
  PojavClassLoader → `loadClass(version.mainClass)` 反射 `main(String[])`。
- `getMinecraftArgs` 宏表：auth_session/access_token/player_name/uuid/xuid/assets_root/
  assets_index_name/clientid/game_assets/game_directory(user.dir)/user_properties/user_type/
  version_name/version_type/natives_directory(=java.library.path)；Server_Ip 解析走
  `org.jackhuang.hmcl.util.ServerAddress`（hmcl 移植类，在 launcher.jar 内）。
- launcher.jar 内嵌：Pojav 全套 Tools/MCOptionUtils/MinecraftAccount/PojavClassLoader +
  android.util stub + com.mojang.text2speech.Narrator + hmcl ServerAddress（57 类）。
- lwjgl.jar 是 Pojav 定制合并版（4346 类，LWJGL 3.3.3-snapshot）：GLFW 类 <clinit>
  loadLibrary("pojavexec") → Library.loadNative(... libpojavexec.so)；核心 org.lwjgl.system.JNI
  由 liblwjgl.so 提供。

---

## 5. homl_bridge / pojavexec 机制（画面显示关键）

### homl_bridge（libhoml_bridge.so，NAPI 模块名 homl_bridge）
- UND：`pojav_environ`（pojavexec 全局）+ `OH_NativeWindow_CreateNativeWindowFromSurfaceId/
  GetSurfaceId/DestroyNativeWindow` —— 把 ArkUI XComponent surfaceId 转 OHNativeWindow 注入
  pojavexec 环境。
- NAPI 函数（完整，Index.d.ts 已复制到 `libs/jrelib/src/main/cpp/types/libhoml_bridge/`）：
  jvm_Launcher / surfaceChanged(id,w,h) / send_mouse_button / send_cursor_pos / send_screen_size /
  send_key / send_char_mods / send_char / send_scroll / set_env / dl_open / on_cursor_enabled /
  on_crash_message / on_log_message / on_nominal_exit / accessClipboard。
- jrelib Index.ets re-export：`export const homl_bridge = homlBridge`（import 'libhoml_bridge.so'）。
- **未引入 launcher HAR**：homl_har 仅是 .so + types 声明；ArkTS 侧只需给 jrelib 加
  types 依赖 + re-export，无需整个 HAR。libhoml_bridge.so 放 jrelib libs（数据），同时 NAPI
  可被 ArkTS import（同模块命名空间）。

### pojavexec（libpojavexec.so，HOML 鸿蒙定制）
- 依赖系统库：libdriver_helper.so / libace_napi.z.so / libhilog_ndk.z.so /
  libnative_window.so / libability_*.so。UND 无 OH_/napi 调用符号（BIND_NOW 仅重定位）。
- JNI_OnLoad（0x9314）顺序：GetEnv 存全局 → hookExec(ProcessImpl.forkAndExec hook) →
  installLwjglDlopenHook(RegisterNatives 覆盖 DynamicLinkLoader.ndlopen) →
  EMUI iterator 缓解（需 env POJAV_EMUI_ITERATOR_MITIGATE）→ 未设 POJAV_SKIP_JNI_GLFW 则
  注册 GLFW JNI → 返回 JNI_VERSION_1_4。
- JNI_OnLoadGLFW：FindClass org/lwjgl/glfw/GLFW → 缓存静态方法/字段 ID + mouseDownBuffer
  等 DirectByteBuffer 地址。
- GL 导出：pojavInit（只调 pojavInitOpenGL 返回 1，不碰 window）/ pojavCreateContext /
  pojavMakeCurrent / pojavSwapBuffers / pojavSwapInterval / pojavTerminate / pojavPumpEvents /
  pojavStartPumping / pojavStopPumping / pojavSetWindowHint / pojav_environ(8B 全局指针)。
- pojavInitOpenGL 按 POJAV_RENDERER 选后端：opengles*/openglv4→装 gl/osm 桥表；
  virgl/zink 走 dlopen 驱动。**env 缺失 = 空函数表 = NULL 调用崩**。
- GLFW$Functions 取址：pojavInit/pojavCreateContext/...（apiGetFunctionAddress）。
- **GLFW 键盘/鼠标回调实现**：pojavexec 处理 nglfwSetKeyCallback 等（input_bridge_v3 思路），
  消费 pojav_environ 环形缓冲（Android input_bridge_v3.c 同源思路）。

### HOML 启动时序（Game.ets 参照）
```
XComponent(TEXTURE, "java-game").onLoad → setTimeout 1s → launch()
onSurfaceCreated(surfaceId) → homl_bridge.surfaceChanged(parseInt(surfaceId),0,0)
onSurfaceChanged → surfaceChanged(id,800,800)   ← HOML 写死 800×800（resize 是已知短板）
```
我们实现用 SURFACE 类型 XComponent + onSurfaceCreated/Changed 传真实 rect 尺寸。

---

## 6. 黑箱 so 清单（受制于无源码，反编译/经验驱动）

以下 .so 从 HOML 真机安装包提取，**无源码**（除 Amethyst-Android jni 目录的 Android 版
同源 C 可参考），只能靠 readelf/objdump/strings 逆向 + 行为实验：

| .so | 角色 | 受制程度 | 备注 |
|-----|------|---------|------|
| **libpojavexec.so** | GLFW JNI 桥 + GL 桥核心（pojavInit/glfw 回调/EGL） | 🔴 最高 | GLFW 语义由它定；`nglfwWindowShouldClose` 等未实现 → MC 无法感知关窗；48KB BIND_NOW |
| **libhoml_bridge.so** | ArkUI↔JVM：surfaceId→OHNativeWindow 注入 + 输入转发 NAPI | 🔴 高 | 窗口注入唯一通道；无退出 API；NAPI 需 ArkTS import |
| **libmobileglues.so** | 渲染后端（GLES→Vulkan，内部 zink） | 🔴 高 | 渲到注入的 surface；resize 语义未知；3MB；NEEDED spirv/c++_shared |
| libdriver_helper.so | pojavexec/homl_bridge 依赖 | 🟡 中 | 仅符号依赖 |
| libxb_components.so | homl_bridge 附带 | 🟡 低 | 未见关键消费 |
| liblwjgl.so + 模块(ogl/stb/tinyfd/nanovg/vma/opengles) | musl 定制 LWJGL native | 🟡 中 | JNI 符号已验与定制 jar 全匹配 |
| libopenal.so | OpenAL 音频（BGM 来源） | 🟢 低 | 正常工作 |
| libpojavexec_awt.so / libawt_xawt.so | AWT 桥（cacio 备胎） | 🟢 低 | 当前未用 |
| libng_gl4es.so / libshaderc.so / libspirv-cross-c-shared.so | 备选渲染器/依赖 | 🟢 低 | ng_gl4es 是 HOML 备选 renderer |

**结论**：真正卡脖子的黑箱是 **libpojavexec.so + libhoml_bridge.so + libmobileglues.so**
三件套。它们决定 GLFW 语义（关窗/resize）、surface 注入方式、渲染后端行为。若要彻底解决
"关窗退出 / 实时 resize / 输入全通"，路径有：
- 继续黑箱实验：摸清 mobileglues resize 触发条件、pojavexec 是否有窗口尺寸更新通道；
- 换开源实现：Amethyst-Android `app_pojavlauncher/src/main/jni/` 有 pojavexec **Android 版源码**
  （input_bridge_v3.c/egl_bridge.c/ctxbridges/gl_bridge.c 等，Android.mk LOCAL_MODULE:=pojavexec），
  可作移植鸿蒙的参考（工作量：平台调用层适配，数天级）；
- HOML 同款 GLFW 语义缺失项（nglfwWindowShouldClose 等）只能靠 hook 或改 jar 补。

---

## 7. 遗留问题（已立项）

### 7.1 关窗游戏不退出
- 现象：关 GameWindow（点 X）后 BGM 继续——JVM/MC 未终止。
- 根因：MC 渲染循环每帧查 `glfwWindowShouldClose()`，而 pojavexec 未实现该 GLFW 语义
  （其导出无 nglfwWindowShouldClose/nglfwSetWindowShouldClose；定制 jar 里方法有 Java 实现
  读 window 内部字段，但无 native 支撑翻转）。
- **落地约束（重要）**：EntryAbility 与 GameAbility 同 module(entry) → **同进程**
  （鸿蒙 PC 只有"不同 module"的 UIAbility 才天然不同进程，见 faqs-ability-34）。
  单例不跨 ability 共享是 **JS 运行时隔离**所致，不是进程隔离。故"同进程内只终止 JVM 且不
  影响宿主主窗"不可行（JVM 线程受 libjvm 管理，无外部安全中止 API；DestroyJavaVM 会等待
  非 daemon 线程=MC main 自行退出，死等）。
- **可选落地**：
  a) **接受整 app 退出**：关游戏窗 → 进程 exit()，主窗一起退（主窗当前只是启动器，可接受？）。
  b) **拆独立 module**（架构正解）：把 GameAbility/GameWindow 放单独 module，PC 上独立进程，
     关窗杀该进程即停游戏，主 module 不受影响。工程量中等。
  c) 维持现状：用户在游戏内 ESC→保存并退出（对齐 HOML 单窗交互）。
- 2026-09-07 决定：暂记，待用户选 a/b/c。

### 7.2 实时 resize 未响应
- 现象：拖拽窗口大小，画面不跟随。
- 根因：XComponent rect 变了（onSurfaceChanged 有触发、surfaceChanged 已带真实尺寸），但
  mobileglues 渲染 surface 未重建/未重设 → 画面停留在初始尺寸。
- 目标：窗口拖拽实时跟随。需摸清 mobileglues 对 nativeWindow 尺寸变化的响应机制
  （可能要 OH_NativeWindow_NativeWindowHandleOpt 设宽高 + 重建 EGL surface）。
- HOML 自身 onSurfaceChanged 写死 800×800 → HOML 的 resize 也是短板，无可直接照搬。

### 7.3 输入未验证
- homl_bridge 有 send_mouse_button/send_cursor_pos/send_key/... 全套，ArkTS 侧转发已就位
  （GameWindow 可接入），但**尚未接鼠标/键盘事件**。点按钮/进游戏还需输入桥。
- NativeInput 方向参照 HOML core/NativeInput.ets + FCLKeycode/LWJGLKeycode 映射。

---

## 8. 环境与工具情报（可复用）

- **hdc**：`$HOME/devecow/deveco_tools/sdk/default/openharmony/toolchains/hdc`
  （`hdc` 裸命令不可用；用绝对路径）。本机 2in1 无线调试，**开发机 = 运行机**（当前 shell 所在
  即 hdc 连上的那台鸿蒙 PC）。⚠️ **hdc 端口重启后会变，勿写死**，用 `devecocli device list`
  或 `./hdc list targets` 现查。
  **部署约定（2026-09-07 更新）**：agent 可用 `devecocli` 签名/build/run 与 hdc；
  但**日志抓取仍由用户负责**（需要时请用户导出，勿自行开 hilog 监听）。
  ⚠️ **本条已被取代（2026-09-28）**：agent **不再构建 app 包、不再运行/部署**（`devecocli build` / IDE / `hvigorw`、
  `devecocli run`、一切 `hdc` 均归项目拥有者）；现行边界见 [`../00-current/工程与规范.md`](../00-current/工程与规范.md) §二.3。
  安装顺序铁律：**先 hsp/har（jrelib）再主 hap（entry）**（保证资源包最新，见 §3.7）。
- 本机 JVM/javap 被禁（PaX 拒 mprotect）→ 反编译用自写 python class 解析器
  （`stuffs/research/pojav/pojav_decomp/disasm.py`，支持常量池 + 字节码 + 行号表）。
- el1 natives 区：`/data/storage/el1/bundle/jrelib/libs/arm64`（应用沙箱不可 shell ls，权限拒）。
- HOML 真机镜像（ref 资产）：
  - 安装包：`HO_DATA_EXT_MISC/Download/HOML-prod-signed.app`（entry-default.hap 内 libs/arm64-v8a 全套 so）
  - 运行数据：镜像 `ref/org.xbstudio.homl.pro/haps/entry/files/`（含 HOML/.minecraft、jre25、accounts/<account>.json、persistent_storage 的 VersionSetting 配置）——**已删**（2026-09-09），结构与配置快照见 [`homl-sandbox-mirror.md`](homl-sandbox-mirror.md)
  - 配置情报：VersionSetting_1.21.10 renderer=libmobileglues.so、jre25；isolation 走 global(true)。
- HOML 桥 HAR 拆分版：`stuffs/research/homl/homl_har/package/`（libhoml_bridge NAPI types/Index.d.ts + 全套 so）。
- 设备上已装 HOML：`org.xbstudio.homl.pro`（但 bundle public 不可读，无法直接 dump so）。

---

## 9. 代码/产物位置速查

| 内容 | 路径 |
|------|------|
| JVM argv 组装 | `Meowcraft/entry/src/main/ets/common/data/MinecraftLauncher.ets`（buildLaunchArgv + gameRootParent/offlineAccountJson） |
| 实际 native 启动 | `Meowcraft/libs/jrelib/src/main/cpp/jre_bridge.cpp`（env + 预 dlopen + JLI） |
| (未生效) entry native | `Meowcraft/entry/src/main/cpp/jre_launcher.cpp` |
| 游戏窗口页 | `Meowcraft/entry/src/main/ets/pages/GameWindow.ets` |
| 窗口 Ability | `Meowcraft/entry/src/main/ets/entryability/GameAbility.ets`（加载 GameWindow） |
| 参数通道 | `Meowcraft/entry/src/main/ets/common/state/GameLaunchParams.ets` |
| 开窗 | `Meowcraft/entry/src/main/ets/common/state/WindowHolder.ets` |
| el1 so 源目录 | `Meowcraft/libs/jrelib/libs/arm64-v8a/`（构建进 HSP → el1） |
| homl_bridge NAPI 声明 | `Meowcraft/libs/jrelib/src/main/cpp/types/libhoml_bridge/Index.d.ts` |
| 反编译产物 | `stuffs/research/pojav/pojav_decomp/{disasm.py, allcls/, lwjglcls/}` |
