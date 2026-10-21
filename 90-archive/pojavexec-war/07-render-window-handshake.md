> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../20-design/render/渲染链-结论.md`](../../20-design/render/渲染链-结论.md) 与 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)。

# 07 · HOML 渲染窗口握手真相（谁写 env+0x000）

> 来源：子 agent 三线取证（HOML ArkTS 源码 / launcher.jar Java 反编译 / 两个 so 静态反汇编全量扫描）。

## 先导结论（决定性）
`pojav_environ` 是 8B BSS **指针变量**（本 so 0xe620），由 pojavexec 构造器 `env_init`(0x8fc4) `calloc(1,0x27228)` 建结构体并 `setenv("POJAV_ENVIRON",hex)` 发布。
**本批次两个 so 内都不存在对 `env+0x000` 的写入方**；而 pojavexec 唯一的 EGL 建窗点 `gl_swap_surface`(0x7eac) 以 `[env+0x000]` 为 `eglCreateWindowSurface` 的 nativeWindow。

## 三线证据摘要
### A. HOML ArkTS（ref/HomoLauncher）
- Game.ets onSurfaceCreated→`surfaceChanged(parseInt(sid),0,0)`；onSurfaceChanged→`surfaceChanged(sid,800,800)`（写死，忽略 rect）；onLoad 延迟 1s → launch。
- 唯一 surface/window 入口 = `homl_bridge.surfaceChanged`；ArkTS 无任何把 sid/window 传 Java 或其它 native 的旁路。
- JVM 参数 `glfwstub.windowWidth/Height` 来自菜单（默认 900）；渲染器默认 libmobileglues。

### B. Java（launcher.jar 反编译）
- ArkUIKit `<clinit>` 只 `System.loadLibrary("homl_bridge")`，**从不加载 pojavexec**。
- 全 jar 无 surface/window→native 的传递；GLFW stub 是纯 Java 假窗口（尺寸=系统属性 glfwstub.*）。
- Java 层完全不在窗口链路上。

### C. pojavexec/homl_bridge 静态真相
- homl_bridge 对 env 仅 3 处访问：surfaceChanged 读 `[env+0]`（比对/销毁旧窗）→ `OH_NativeWindow_CreateNativeWindowFromSurfaceId(sid)`（PLT 0x247c0，@0x1fcd4）**返回值被丢弃** → 只把 w/h 写 `env+0x271d4/d8`；on_cursor_enabled/on_nominal_exit 写 thunk 槽 `0x27180/88`。
- pojavexec：UND **无任何 OH_NativeWindow_*/egl*/OH_ArkUI 导入**（EGL 全走 dlsym→`egl*_p` BSS 指针表）；`gl_swap_surface`(0x7eac) 唯一 `eglCreateWindowSurface_p` 调用点，nativeWindow=`[env+0]`；无窗回退 1×1 pbuffer。全 5222 条指令扫描：**本 so 从不写 [env+0]**。
- `JNI_OnLoad/OnLoadGLFW`(0x9314/0x9108) 只写 env+0x271b8(JavaVM) 与 0x27170-0x271c8 的 JNI class/method 缓存，不碰低区窗口槽。

## 推理：原设计的缺环
homl_bridge 造窗却从不写回 `[env+0]`；pojavexec 只读不写 → **原设计意图是"渲染驱动（mobileglues/GLv4 之类，dlopen 时）或更新版桥负责把 OH_NativeWindow 写入 env+0x000"**，homl_bridge.surfaceChanged 只做"按 sid 换窗保活 + 刷 w/h"。
> 对我们：现役自研替换件若要渲染，**必须自己补上"写 env+0"这一环**（我们手头两 so 无人写；依赖不存在于随包里的第三方驱动不可控）。这也是 drop-in 唯一必须新增的能力，其余全部贴近 HOMO。

## drop-in 自研 so 需要承担（复刻清单）
1. 构造器 env_init：alloc 0x27228 + 写 BSS 全局 + setenv POJAV_ENVIRON（同 HOML）。
2. 读共享槽渲染：`[env+0]` 作 EGL nativeWindow（gl_swap_surface 语义）；EGL 显示句柄自持。
3. **补齐缺失写槽**：自行从 surfaceId 创建 OH_NativeWindow 并写回 `[env+0]`（需拿到 sid）。
4. w/h 写 env+0x271d4/d8；让 homl_bridge 的 GetSurfaceId 对比在换窗时能正确销毁旧窗。
5. env+0x10 作 renderer 模式字段；pojav*/Java_* 导出面按 02 表补齐。

## 拿 sid 的可选通道（M1 决策）
- (a) **自研 so 注册 NAPI**（如 `setSurface(sid)`，jrelib Index import 并 re-export，GameWindow 在 homl_bridge.surfaceChanged 同点顺带调用）——极小改动、全归我们控制、语义其它全贴近 HOMO。**推荐**。
- (b) 黑箱探测现役 GLv4+zink 链是否已由某隐藏方写 env+0（用最小 instrumented so 在 JNI_OnLoad/pojavCreateContext 打印 `[env+0]`）——若已写则可能无需 (a)；但静态证据强烈表明无写入方，收益低。

## 关键地址速查（hex）
pojavexec：env_init=0x8fc4；pojav_environ BSS=0xe620；JNI_OnLoad=0x9314；JNI_OnLoadGLFW=0x9108；gl_swap_surface=0x7eac（唯一 eglCreateWindowSurface 调用点）；struct size=0x27228；w/h=env+0x271d4/d8；JavaVM=env+0x271b8。
homl_bridge：GOT pojav_environ=0x26550；surfaceChanged 处理器=0x1fbc0；CreateNativeWindowFromSurfaceId 调用=0x1fcd4（结果丢弃）。
