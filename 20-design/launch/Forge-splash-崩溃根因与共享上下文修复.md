# Forge splash 崩溃根因与共享上下文修复（2026-09-29）

> 定位：**1.7.10-Forge-OptiFine 进游戏即 SIGSEGV** 的根因取证与修复记录。
> 现象层在日志、语义层在 LWJGL2、修复落在**我们自己的两处**（桥 `egl_gl.c` + LWJGL2 shim `meow_context.c`），
> **不写游戏目录、不动 Forge/HMCL 的文件**（符合 [`../../00-current/工程与规范.md`](../../00-current/工程与规范.md) 的兼容铁律）。
> 本页只放**取证与实现细节**；"当前进展口径"以 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) 的 **C11** 条为准（本页不重复声明口径）。

## 1. 结论

FML 的控制台 splash（`cpw.mods.fml.client.SplashProgress`）在自己的线程上要求**一个与主上下文共享对象的第二个 GL 上下文**（LWJGL2
`SharedDrawable`）。桌面靠 GLX 天然满足；我们这侧原来**把共享参数丢掉**、直接把唯一那个 EGL 上下文再绑一次 ⇒
`eglMakeCurrent` 必然 `EGL_BAD_ACCESS(3002)`（上下文还 current 在渲染线程上）⇒ 失败又被 `void` 返回吞掉、shim 还**无条件**
把"上下文 current"标记为真 ⇒ splash 线程在**没有 current 上下文**的情况下跑 gl4es ⇒ 原生线程 SIGSEGV，进程亡。

修法：把 LWJGL2 真正需要的语义补上 —— **真建一个共享 EGL 上下文**（每上下文自己的 surface），并让**失败能传出来**。

## 2. 现象：日志证据（`Harmomeow-Craft-Launcher/.logs/This PC-1790615609-hilog.txt`）

```
973  [jre_stdout] [Client thread/INFO]: Attempting early MinecraftForge initialization
974  [jre_stdout] [Client thread/INFO]: MinecraftForge v10.13.4.1614 Initialized
975  E   eglMakeCurrent failed: 3002                     ← EGL_BAD_ACCESS
976  W   meowMakeCurrent: no GL context/surface available ← 桥的守卫：没东西可绑
977  W   signal_chain_handler call 0 rd sigchain action for signal: 11 …
979  I   DFX_SignalHandler :: signo(11), si_code(1), pid(17100), tid(19780).   ← SEGV_MAPERR
…（976 之后 Java 仍在跑：981 Replaced 183 ore recipies、998 early init 完成、1059 OptiFine E7）
1073 I   Current process(17100) rethrow signo(11).        ← 没人接手 ⇒ 进程亡
1078 W   pid(17100) rethrow sig(11) success.
1079 I   [jre_stdout] LIBGL: FPE Vertex shader compile failed: <乱码>   ← stdout 块缓冲，死亡时才刷出
```

判读要点（都已交叉验证）：

- **致死的 SIGSEGV 在 tid 19780**（唯一被 `rethrow` 的那条），`si_code=1`（访未映射地址）；
- **没有 hs_err**：崩溃线程**不是 JVM 线程**（HotSpot 的链式处理器"放过"了它 ⇒ 平台 DFX 直接 rethrow）。
  进一步查证：实例的 `.hmmcraft/logs/` 为空、`stuffs/` 下只有别的实例的旧 hs_err ⇒ **本次确无 HotSpot 报告**；
- **`LIBGL: FPE Vertex shader compile failed: <乱码>`** 出现在**同一处**的两个不同跑次（`…5448` 与 `…5609` 均止于此行）⇒ 稳定复现点；
- **1.6.4 香草那次（`…4807`）完全没有这两条 GL 报错**（`eglMakeCurrent`/`FPE` 计数 = 0）⇒ 与"有没有 FML splash"强相关。

## 3. 机制：为什么"没上下文"，以及为什么打印是乱码

1. **gl4es 这条打印的含义**：`ref/gl4es/src/gl/fpe.c:408`
   ```c
   printf("LIBGL: FPE Vertex shader compile failed: %s\n", buff);   /* buff = 着色器 InfoLog */
   ```
   打印的是 `glGetShaderInfoLog` 的缓冲区。**在当前线程没有 current 上下文时，这个缓冲区内容无效** ⇒ 打出乱码。
   即：乱码本身就是"**GL 调用在无 current 上下文下发生**"的判据，不是着色器本身的问题。

2. **RIP 落到 gl4es 之后**：无上下文 ⇒ gl4es 内部状态/`glstate` 与驱动侧对象不一致 ⇒ 空/野指针 ⇒ 原生线程 SIGSEGV。

3. **为什么这个线程没有上下文**（三层，逐层有据）：
   - FML splash 用 `SharedDrawable`：`ref/lwjgl/src/java/org/lwjgl/opengl/SharedDrawable.java:50`
     `this.context = (ContextGL)((DrawableLWJGL)drawable).createSharedContext();`
     ⇒ `DrawableGL.java:74-79` `new ContextGL(peer_info, attribs, context)` —— **要一个共享对象的第二上下文**（桌面 GLX 的能力）；
   - 我们旧实现**丢掉共享**：`tools/lwjgl2/src-ohos/meow_context.c` 改前 `nCreate` 里
     `(void)shared_context_handle;`（只发一个不透明句柄）、`nMakeCurrent` 里 `(void)context_handle;`（转手交给桥）；
     桥侧只有**唯一** EGL 上下文（`egl_gl.c` 的 `g_egl.context`），而它此刻还 current 在渲染线程上；
   - **失败被吞**：桥的 `meowMakeCurrent()` 返回 `void`（失败只打日志），shim 随后**无条件** `t_context_current = 1`
     ⇒ LWJGL 认为"已 current" ⇒ splash 线程继续发 GL 调用 ⇒ 上面的结果。

4. **splash 为什么会启动**：`SplashProgress` 的开关只有一处 —— `config/splash.properties` 的 `enabled`
   （`getBool("enabled", true)`，即**文件不存在时默认开**），外加一个"检测到 OptiFine 就关"的分支，判据是
   `Launch.blackboard["optifine.ForgeSplashCompatible"]`（常量池解出：`#209 = optifine.ForgeSplashCompatible`、
   `#58 = enabled`、`#160 = config/splash.properties`、`#461 = false`）。
   崩的那几次**没有这个配置文件** ⇒ 走默认值 **开** ⇒ splash 起来 ⇒ 走上面的路径。
   > **实测**：修好之后 FML 自己写出了 `config/splash.properties`，内容是 **`enabled=false`**
   > （文件头 `#Splash screen properties` + 时间戳 = FML 写的）⇒ **后续跑次的 splash 被跳过**。
   > 也就是说：单看"哪个分支写了 false"，与 §3.4 的字节码解读（OptiFine 声明兼容就保留）并不一致，
   > **具体是 `hasOptifine()` 的判定时机还是该键的取值所致，尚未坐实** —— 这里只记录观测到的事实，
   > 不做机制断言（见 §9 的实测结论：本轮**共享上下文路径根本没被走到**）。

5. **与 HMCL 的一致性核对**：`ref/HMCL`（956 个 `.java`）中**没有任何地方触碰 `splash.properties`**（只有测试里出现过
   "splash" 字样）⇒ **HMCL 不靠写游戏目录来绕这个坑**，故我们也不应走那条路（写 `config/` 违背兼容铁律）。
   桌面 HMCL 能跑 splash，是因为桌面有共享上下文 —— 缺口在**我们的 shim**，不在 FML。

## 4. 1.6.4 香草为什么没事

香草 MC 没有 FML splash ⇒ 全进程只有**一次** make-current（渲染线程）⇒ 不会出现"第二个上下文抢 context" ⇒
本次崩点整条链都不存在（日志侧 `eglMakeCurrent`/`FPE` 计数 = 0）。

## 5. 修复（已实现）

### 5.1 桥：上下文注册表（`libs/meowcraftlib/src/main/cpp/meowcraftbridge/egl_gl.c`）

- 新增 `MeowCtxSlot g_ctxSlots[MEOW_MAX_CTX]`：**句柄 → {EGLContext, 自己的 EGLSurface, 是否主}**，句柄就是槽位地址；
- 每次 `eglCreateContext` 都经 `meow_create_context_with()`，顺带记下成功的属性表（`g_ctxAttrs`）⇒ 共享上下文与主上下文**同版本/同档位**；
- 次级上下文用**独立的 1×1 pbuffer**（`egl_build_secondary_surface()`）。原因：**EGL 规定一个 surface 同时只能被一个 context current**，
  所以次级上下文**不能**复用主上下文那个 window surface；而已知的唯一消费者（FML splash）**从不呈现**（见下条）；
- **新导出**：
  - `meowCreateSharedContext(share)` — `share == NULL` 只登记主槽位（不提前建上下文，保持原有懒创建时机）；
    否则 `eglCreateContext(display, config, parentCtx, g_ctxAttrs)` 建**真共享**上下文，返回新句柄，失败返回 NULL；
  - `meowMakeCurrentFor(window, handle)` — 按句柄绑定；`window == NULL` 仍为"在调用线程上解除"；**返回 1/0**；
  - `meowDestroySharedContext(handle)` — 销毁次级上下文（主上下文是 no-op，进程级不拆）。
- `meowMakeCurrent()` 保留为 `(void)meowMakeCurrentFor(window, NULL)`（LWJGL3/GLFW 路径不变）；
- `meowSwapBuffers()`：**在次级上下文上调 swap 直接忽略**（换主 surface 会 EGL 报错；splash 的输出按设计不呈现），首条记日志；
- `meowTerminate()` 先销毁所有次级槽位。

### 5.2 shim：把上下文问出来、把失败抛出去（`tools/lwjgl2/src-ohos/meow_context.c` + `meow_port.h`）

- `MeowContext` 增加 `void *bridge_ctx`（桥侧句柄）；`MeowBridge` 增加 `createContext/makeCurrentFor/destroyContext` 三个 dlsym 入口
  （缺任一 ⇒ 自动回退旧 `makeCurrent` 路径并打日志）；
- `nCreate`：把 `shared_context_handle` 的桥句柄转给 `createContext()`；**拿不到句柄就抛 `LWJGLException`**，绝不发给 LWJGL 一个绑不上的句柄；
- `nMakeCurrent`：走 `makeCurrentFor(window, ctx->bridge_ctx)`，**失败抛异常且不置"current"**；
- 每线程当前上下文改为**句柄**（`static __thread MeowContext *t_current_ctx`）：`nIsCurrent` 改为"问的是不是这个上下文"，
  `nReleaseCurrentContext` 顺带让桥解绑该线程；
- `nDestroy`：交给 `destroyContext()`（主上下文仍为 no-op）。

### 5.3 取舍与已知风险

- **为什么次级用 pbuffer 而不是第二个 window surface**：EGL 的"surface 只被一个 context current"约束下，第二个 window surface
  可用性依赖驱动实现；而 splash 本来就不呈现（我们也不再为它 swap）。**代价 = splash 画面不可见**（功能不受影响）；
  若将来要"可见的 splash"，需单独验证"同一 native window 建两个 EGLSurface"在该驱动上的行为。
- **gl4es 的 `glstate` 必须按 EGL 上下文隔离**：FML splash 线程与主线程在加载期**真的会并发驱动同一个进程级 `glstate`** ⇒ SIGSEGV/SIGTRAP（见 §9 与 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) C11）。**修法**：gl4es delta `tools/gl4es/deltas/glcore/src/gl/meowctx.c` 把 `glstate` 变 `__thread` 并按 EGL 上下文绑定（桥 `egl_gl.c` 每次成功 `eglMakeCurrent` 后经 `dlsym` 调 `meow_gl4es_bind`）。共享上下文现**默认允许**（策略见 [`../../00-current/运行时环境变量.md`](../../00-current/运行时环境变量.md) §1）。"两个上下文的**对象表**共享（EGL 语义）"不变；**共享对象表的并发加固仍未做**（残留风险，见该 delta 节末）。

### 5.4 共享对象表并发：暂不加固（决策记录，2026-09-30）

**前提**：每 EGL 上下文隔离只隔离了 `glstate` 的**事务面**（矩阵/enables/`glBegin` 事务/VAO/gleshard）；`NewGLState(parent)`（`ref/gl4es/src/gl/glstate.c:73-96`）让同组上下文仍**共享**这些 khash 表 —— `headlists`、`texture.list`、`buffers`、`glsl`（`shaders`/`programs`）、`fpe_cache`、`fbo.{framebufferlist,renderbufferlist}`、`samplers.samplerlist`、`queries.querylist`（`ref/gl4es/src/gl/glstate.h:19/41/78/83` 标 `//shared`）。

**谁真会跑两个上下文**：第二上下文只由 LWJGL2 `SharedDrawable.createSharedContext()` 发起 → LWJGL2 shim `nCreate` → 桥 `meowCreateSharedContext(share≠NULL)`（`tools/lwjgl2/src-ohos/meow_context.c:122,157-158`；`libs/meowcraftlib/.../meowcraftbridge/egl_gl.c:1014`）。⇒ **仅 Forge ≤1.12.2（LaunchWrapper + FML splash）在 gl4es(FPE) 上**存在"两线程两上下文、整加载期重叠"；原版 legacy / Fabric / 1.13+（走 LWJGL3+GLFW 桥，**从不调** `meowCreateSharedContext`）只有一个上下文 ⇒ 不同线程不会同时进 gl4es。

**竞争对（file:line；均为共享表上的非原子 get→put→del 序列）**：
- `headlists`：`gl4es_glNewList`（`gl4es.c:819-824`）/ `gl4es_glEndList`（`:837-850`：`free_renderlist(kh_value)` + 存新链）/ `gl4es_glCallList`（`:871-881` 取链后 `draw_renderlist` 遍历）/ `gl4es_glDeleteList`（`:931-944` kh_get+`free_renderlist`+kh_del）⇒ **释放 vs 遍历同一 `renderlist_t` = UAF**；并发 `kh_put` 触 rehash ⇒ 桶数组损坏（此前 `<HM_GPU> vertexSum: 22364413` 的垃圾 `len` 即此类）。
- `texture.list`：`gl4es_glGenTextures`（`texture_params.c:429-460`）/ `gl4es_getTexture`（`:139-151` kh_get→kh_put→malloc，**三步非原子**）/ `gl4es_glDeleteTextures`（`:368-427` kh_get+free+kh_del）。
- `buffers`：`gl4es_glGenBuffers`（`buffers.c:97-123`；`lastbuffer++` 是裸 static，`:107`）/ `gl4es_glBindBuffer`（`:125-164`）/ `gl4es_glDeleteBuffers`（`:332-378`）。
- `glsl`：`gl4es_glCreateProgram`（`program.c:111-115`）/ `deleteProgram`→kh_del（`:167`；裸 static `lastprogram` `:93`）/ `gl4es_glCreateShader`（`shader.c:47-50`）/ `gl4es_glDeleteShader`（`:70-74`）。
- `fpe_cache`：`fpe_GetCache`（`fpe_cache.c:79-88` kh_get→kh_put）。`fbo`：`gl4es_glGenFramebuffers`（`framebuffers.c:109`）/ `gl4es_glDeleteFramebuffers`（`:117-166`，kh_del `:166`）；renderbuffers 同形（`:818-958`）。

**不加固的风险**：加载期**概率性原生死**（SIGSEGV/SIGTRAP、**无 hs_err**，崩溃线程非 JVM 线程）或**静默错乱**（纹理/显示列表）。概率**低但非零**：隔离修复后**未再观测到**（见 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) C11）；窗口仅"Forge ≤1.12.2 + FML splash 开 + gl4es(FPE)"的加载期几秒。不可恢复但**显眼**（进程亡于加载中）。

**加固的副作用（逐项）**：① **每表叶锁** —— 挡不住上述复合序列（get-create-delete），单独做**不够**，还给热路径加锁开销；② **显示列表/程序引用计数** —— 才真覆盖 `glEndList`-free vs `glCallList`-traverse，但改动散落 `gl4es.c`/`list.c`/`listrl.c`/`program.c`/`shader.c`/`texture.c`/`texture_params.c`/`fpe_cache.c`/`framebuffers.c` 十余个**覆盖式 delta**（上游一改须手工合并），**引入新 bug 概率不低**；③ **表改每上下文** —— **破坏 EGL 共享语义**（FML splash 正依赖共享），不做；④ **会话级串行化** —— 与 FML 锁序**死锁**（已证），排除。

**零风险缓解（供拥有者裁决）**：① 安装时给 ≤1.12.2 Forge 实例预置 **FML 自己的** `config/splash.properties: enabled=false`（落**每实例**目录 = `GameDirs.profile`，**不是** `GameDirs.game`）⇒ 彻底消掉并发窗口；FML 自持文件、HMCL 兼容（HMCL 不碰 splash，桌面靠 GLX 天生共享）—— *拥有者此前选根因修复，此仍为零风险退路（见 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) C11）*。② **诊断**：在共享表 mutator 外加 env 门控的一次性计数/日志，或备好 faultlog 符号化配方 ⇒ 日后概率崩能直接判定是否落在这几张表。

**结论**：**暂不加固**（维持现状；每 EGL 上下文隔离**已消掉该崩溃**，状态以 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) C11 为准）。**重开条件** = 再观测加载期概率性原生死 ⇒ 取 `/data/log/faultlog/faultlogger/` 原生栈判定是否落在这几张表；届时优先"显示列表/程序引用计数 + 其余表叶锁"或直接采用缓解①。

## 6. 本轮已做的验证

| 项 | 结果 |
|---|---|
| 桥静态检查（`check_cpp_files`） | 无 error（仅既有 severity-2 噪声；期间发现并修掉一处**我引入**的前置声明缺失） |
| LWJGL2 shim 真实编译 | `sh tools/lwjgl2/build_lwjgl2_meow.sh --src ../ref/lwjgl --sdk-native <CLT SDK>/openharmony/native --out ../stuffs/research/lwjgl2/out --with-display` ⇒ **178 TU 通过、断言 OK**，产物 `stuffs/research/lwjgl2/out/liblwjgl.so`（323368 B，sha256 `93931548ac424bc57e1a28615d8ba613c3d3c714ca4e555955c87e26b28d6a8d`） |
| stage-2 全套 6 个源语法检查（`-Wall -Wunused -fsyntax-only`，OHOS clang） | 全部干净 |
| **3 次干净重建逐字节复现** | **未做**（按 `../../00-current/工程与规范.md` 的规则，不得声称可复现） |
| **实机** | **未做**（见 §7 判据） |

> 附：`tools/lwjgl2/README.md` 里记的 SDK 路径 `/data/service/hnp/ohos-sdk.org/ohos-sdk_26.0.0.18/ohos/native` **本机已不存在**；
> 当前在用的是 `/data/service/hnp/hmos-clt.org/hmos-clt_1.0.0/sdk/default/openharmony/native`（已在 README 里改为占位 + 注明）。

## 7. 下次实机要看什么（判据）

同一条 1.7.10-Forge-OptiFine 启动，检查 `Harmomeow-Craft-Launcher/.logs/`：

1. **成功路径**：出现
   - `ctx registry: primary slot 0x...`
   - `shared ctx created: share=0x... -> ctx=0x... slot=0x...`（**关键**：证明真建了第二上下文）
   - `swapBuffers on a shared context ignored (no presentation)`
   - 且**没有** `eglMakeCurrent failed: 3002`、**没有** `LIBGL: FPE Vertex shader compile failed`、**没有** `rethrow signo(11)`；
2. **驱动不支持共享上下文**（退路已内置）：出现
   - `shared ctx: eglCreateContext(share=...) failed: 0x30xx` + Java 侧 `LWJGL2 port: make-current failed`／`cannot create GL context`
   ⇒ splash 线程被"正当地"挡住（抛异常而不是跑飞）。此时看游戏是否继续（splash 被跳过）：
   继续 ⇒ 我们的目标已达成（splash 不可见而已）；不继续 ⇒ 再评估是否要"预置 `config/splash.properties`"
   （**需要用户裁决**，因为那是写游戏目录）；
3. **仍崩** ⇒ 取 `/data/log/faultlog/faultlogger/` 的原生栈（本次因无 hs_err、DFX 只给了 tid，需要它才能继续收敛）。

## 8. 相关文件

- 代码：`Harmomeow-Craft-Launcher/libs/meowcraftlib/src/main/cpp/meowcraftbridge/egl_gl.c`、
  `Harmomeow-Craft-Launcher/tools/lwjgl2/src-ohos/meow_context.c`、`.../meow_port.h`
- 上游语义：`ref/lwjgl/src/java/org/lwjgl/opengl/{SharedDrawable,DrawableGL,ContextGL}.java`
- gl4es 打印点：`ref/gl4es/src/gl/fpe.c:406-408`
- 同一实例的其它坑（"任何含 `ITweaker` 的 jar 都必须交给 MeowClassLoader"）：[`Forge支持-改动方案.md`](../../90-archive/Forge支持-改动方案.md)
- 多 JRE / Java 8：[`多JRE共存-方案.md`](../../90-archive/多JRE共存-方案.md)
- 运行期事实：`Harmomeow-Craft-Launcher/tools/lwjgl2/README.md`（§6 踩坑第 17 条）

## 9. 实测（2026-09-29 21:31–21:34，用户实机；`.logs/This PC-1790616*`）

装上新 shim + 桥后连跑四次（`1.7.10-Forge-OptiFine` ×3、`1.12.2-Forge-OptiFine` ×1）。**按证据说话**：

**9.1 好的部分**

- **SIGSEGV / FPE 乱码不再出现**：四次里 `FPE Vertex shader compile failed` 与 `eglMakeCurrent failed` 计数
  分别为 0/0/0/1 —— 唯一那条 3002 出现在 `1.12.2`（Forge 自己也有"第二上下文"式用法），
  **该次没有崩** ⇒ 「失败要能传出来/挡得住」这条改动**确实生效**（旧行为是跑飞）。
- `1.7.10-Forge-OptiFine` 进到世界并**干净退出**（实例 `logs/latest.log` 末行 `Stopping!`，
  `SoundSystem shutting down...`）。
- 退出时 hilog 里的 `signo(6)`（SIGABRT）**是正常现象**：紧前一行是
  `F [appspawn_server.c:69]Unexpected call: exit(0)` —— 应用已 `exit(0)`，SIGABRT 来自框架收尾的杀进程。
  （早前把一个启动阶段的 cppcrash 当证据的教训见 `tools/lwjgl2/README.md` §6 第 16 条。）

**9.2 必须说清的"不能归因"**

- 四次日志里**都没有 `shared ctx created`** ⇒ **共享上下文路径一次也没被走到**；同时
  `config/splash.properties` 里 `enabled=false`（FML 自己写的）⇒ **splash 被跳过**。
- ⇒ **"现在不崩"不能归功于 §5 的修复**：直接原因（至少在这一配置下）是 FML 关掉了 splash。
  §5 的修复**在本轮没有得到检验**（口径登记在 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) 的 C11）。
  要检验它需显式打开一次：把该文件的 `enabled` 置 `true`（或删掉文件再跑一次，
  注意这等于**写游戏目录里的 FML 配置** ⇒ 需用户裁决）。
- 另：`stuffs/test-forge/versions/1.7.10-Forge-OptiFine/config/splash.properties` 首次出现是 01:34（本次），
  而崩的 01:13 那次**没有**该文件 ⇒ "首次运行必崩、之后被 FML 自己关掉"这条路径本身也需要一次受控复现才能定论。

**9.3 新问题（未定位）：进世界后"画面全透明 + 实体渲染错误"**

已知条件（全部来自实例自带日志，非猜测）：

- `[Shaders] No shaderpack loaded.` ⇒ **不是着色器包问题**；
- OptiFine E7 **确实生效**（`OptiFine ClassTransformer`、`Forge ... detected optifine, enabling compatibility features`）；
- `[OptiFine] OpenGL Occlussion culling: Not available (GL_ARB_occlusion_query)`；
- 渲染 env：`MEOWCRAFT_RENDERER=gl4es`、`GALLIUM_THREAD=1`（glthread 开）、后端链 = gl4es FPE → GLES → zink → Maleoon；
- 日志里**没有** `########## GL ERROR`（MC 1.7.10 每帧的 GL 错误报告器没响）⇒ 是"渲染结果不对"而非"GL 报错"；
- 实例的 `options.txt`（**夹具自带，非本启动器所写**：只有 6 行，含 1.13+ 才有的 `simulationDistance`）
  `renderDistance:2`、`mipmapLevels:0`。

判别实验（按代价从低到高，均不涉及改代码）：

1. **回归对照**：跑 1.6.4 香草（已知基线）+ 1.7.10 香草 ⇒ 若都正常，排除"本 shim 改动引入回归"；
2. **关 glthread**（实例设置里的"线程化渲染"关掉）再进世界 ⇒ 排除 `GALLIUM_THREAD=1` × OF 的组合；
3. **游戏内把渲染距离拉到 8+** ⇒ 排除"只是视野 2 区块"的误读；
4. **无 OptiFine 对照**：已备好 `stuffs/test-forge/versions/1.7.10-Forge/`（同样 1.7.10 + Forge，
   `patches` 去掉 `optifine` 段、版本 jar 用纯 Forge universal、0 处 optifine 引用；**原实例未改动**）
   ⇒ 直接判定"是否 OptiFine 专属"。

**结论（2026-09-29 21:50，用户实机）**：换成隔壁 Linux 机器上**真正的无 OF 夹具**（版本 jar = MC 合并 jar，
`含 FMLTweaker: 0`；与 OF 实例同 gameRoot、同 `options.txt`、48 条库只差 optifine 一段）后
—— **渲染正常**；而 OF 实例仍是"全透明 + 实体错"。⇒ **归因 OptiFine**（1.7.10 的 OptiFine E7 渲染路径 × gl4es FPE），
不是 Forge、不是基础链路、也不是本 shim 改动（纯原版两次也正常）。

> 注：我最初用"纯 Forge universal 当版本 jar"构造的对照实例**启动即崩**（与渲染无关），根因见 §11；
> 换成真夹具后对照才成立。**该次崩溃不代表 Forge 有问题**。

**已定位到具体特征（2026-09-29，用户实机二分）**：**OptiFine 的「Fog: Fast」这一档 × gl4es 的固定管线雾**。

- 「Fog: Off」「Fog: Fancy」⇒ **画面正常**；「Fog: Fast」⇒ **全透明 + 实体渲染错误**；
- 与之无关的（都已试过、无效）：Connected Textures、Fast Render（本就 false）、Chunk Loading（本就默认）；
- **完整取证、两层根因、我们改了什么、三版教训、用户侧可用解与后续待办，全部移到专文**：
  [`../render/gl4es固定管线雾-取证与修复.md`](../render/gl4es固定管线雾-取证与修复.md)（本页不再重复）。
- 一句话口径：**管线缺陷（雾 uniform 只在立即模式上传、显示列表回放从不上传）已修并装机；真凶（雾数学/取值空间）未修**；
  用户侧可用解 = 把 Fog 改成 **Fancy/Off**（`ofFogType` 默认就是 Fast ⇒ 新装 OF 实例默认中招）。

## 10. 相关文件（续）

- 本节用到的对照实例：`stuffs/test-forge/versions/1.7.10-Forge/`（我造的，纯 Forge）

## 11. 附赠发现：族过滤漏了「版本 jar 本身就是 Forge jar」的情形（2026-09-29 实机）

**现象**：用"版本 jar = Forge universal"的实例（= HMCL `install + versionInfo` 形态，老 Forge 正是把 jar 拷进版本目录）
启动即死，`latest.log` **0 字节**、死在 early startup：

```
[LaunchWrapper]: Loading tweak class name cpw.mods.fml.common.launcher.FMLTweaker
Caused by: java.lang.NoClassDefFoundError: net/minecraft/launchwrapper/ITweaker
    at net.minecraft.launchwrapper.LaunchClassLoader.findClass(LaunchClassLoader.java:106)
    at net.minecraft.launchwrapper.Launch.launch(Launch.java:98)
```

**根因（已定位到行）**：`LOADER_FAMILY_PATH_SEGMENTS` 是**按路径**匹配的
（`/net/minecraft/launchwrapper/`、`/net/minecraftforge/forge/`、`/net/minecraftforge/fmlloader/`、`/optifine/`），
`MinecraftLauncher.ets::collectJarSources` 在"主类是 launchwrapper"时把族 jar 从**平铺 classpath**里摘掉、改由
`MeowClassLoader` 从真 maven 树加载。但**版本 jar 的路径**是 `versions/<id>/<id>.jar` —— 不在任何 segment 里：

| jar | 含 FML tweaker | 含 `ITweaker` | 路径命中族 segment | 结果 |
|---|---|---|---|---|
| `1.7.10-Forge-OptiFine.jar`（原实例版本 jar） | **否** | 否 | —（无需命中） | FML 只在被摘走的 forge 库里 ⇒ 同族同加载器 ⇒ **正常** |
| `versions/1.7.10-Forge/1.7.10-Forge.jar`（= Forge universal 副本） | **是** | 否 | **否** | FML 留在平铺目录被 **app CL** 定义，而 launchwrapper 已被摘走 ⇒ 同族被拆到两个加载器 ⇒ **CNFE** |
| `libraries/.../launchwrapper-1.12.jar` | 否 | **是** | 是 ⇒ 摘走 | |

**影响面**：**只有当「版本 jar 自身携带 FML/launchwrapper 实现」时才会踩**（例如把
`forge-<ver>-universal.jar` 直接当 `<id>.jar` 的形态，我最初就是这么构造的 ⇒ 必崩）。
**真实的 HMCL 夹具不是这个形态**：本机两份 1.7.10 夹具（含 OF 的那份）的版本 jar 都是 **MC 合并 jar**
（`含 FMLTweaker: 0`、含 MC 主类）⇒ FML 只在被摘走的 `libraries/net/minecraftforge/forge/…` 里，
与 launchwrapper 同族同加载器 ⇒ **不会踩**（实机已验证能进世界）。⇒ 本 bug 属**边界形态**，不是当前主线阻塞项。
**修法方向**（与 `collectJarSources` 注释里早已写下的口径一致：「任何含 `ITweaker` 实现的 jar 都必须交给 MeowClassLoader」）：
把族判定从**路径**改成**内容**（jar 内是否有 `net/minecraft/launchwrapper/ITweaker.class` / FML tweaker 实现），
**并把版本 jar 纳入判定**。注意这会改变 MC 类的加载来源（版本 jar 从 app CL 移到 `MeowClassLoader`），
属于类加载拓扑变更 ⇒ **必须实机验证后再定**。相关文件：`entry/.../data/MinecraftLauncher.ets:713-763`、
`entry/.../constants/LaunchContract.ets`（segment 表）、`tools/meow-launcher/src/meow/launcher/{LibraryResolver,VersionLoader,MeowClassLoader}.java`。

> 附：`VersionLoader` 只跟 `inheritsFrom`，**不处理 `patches`**；两个 1.7.10 夹具都是厚 json（无 `inheritsFrom`，
> 自带 48/49 条顶层 `libraries`），所以 `patches` 只影响 ArkTS 侧（族判定走的是 `resolveVersion`）。
