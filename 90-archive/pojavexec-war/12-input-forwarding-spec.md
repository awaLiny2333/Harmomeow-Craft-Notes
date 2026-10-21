> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../20-design/input/输入-总览.md`](../../20-design/input/输入-总览.md) 与 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)。

# 12 · 输入透传（B：全自研链路 + 摘 homl_bridge）实现规格

> 调研定稿（R1 ArkUI/光标锁；R2 键码映射）。目标：ArkTS 事件 → meowjrebridge 的 meowSend* → meowcraftbridge critical_send_* → ring → pump → MC。全程无 homl_bridge。

## 0. 关键事实（必须遵守）
- XComponent **当前无 libraryname** → ArkTS 通用事件(onKeyEvent/onMouse/onAxisEvent)可用；**加了 libraryname 后这些事件全失效**（勿加）。
- 事件回调在 UI 线程；meowSend* 走 SPSC ring（20B/条）UI 线程单写安全，同步直调无禁忌。
- 滚轮：走 `onAxisEvent`（onMouse 不带滚轮）；ArkUI 正值=向后(下)，GLFW yoffset>0=向上 → 下发前取反（每格 ±1）。
- 鼠标：`onMouse`（windowX/Y 是 vp、rawDeltaX/Y 是硬件原始增量、pressedButtons API15+）；MouseButton 是位标志(Left=1/Right=2/Middle=4/Back=8/Forward=16)。
- 键盘：`onKeyEvent` 需要组件**获焦**：XComponent `.focusable(true)` + `.focusOnTouch(true)`；KeyType.Down=0/Up=1；无 REPEAT 类型（自维护 pressed 集合：Down 已在集合→action=2 REPEAT）；`unicode`(可打印时才非0，仅基本拉丁)。
- 修饰键 mods 自维护：SHIFT=0x1 CTRL=0x2 ALT=0x4 SUPER=0x8（左右都算，Super 看 metaKey/KEYCODE_META_*）。
- 光标锁：原生 `OH_WindowManager_LockCursor(windowId, false)`/`UnlockCursor(windowId)`（头 window_manager/oh_window.h，链 libnative_window_manager.so），需权限 `ohos.permission.LOCK_WINDOW_CURSOR`；隐藏光标 `pointer.setPointerVisible(false)`；**失焦自动解锁**。无 warp API → grab 用"虚拟光标=中心+ΣrawDelta×S"喂 send_cursor_pos。
- grab 状态机：MC 通过 `glfwSetInputMode(CURSOR_DISABLED)` → Java stub → 我们 meowcraftbridge 的 `Java_..._CallbackBridge_nativeSetGrabbing` 置位；ArkTS 侧**轮询** meowGetGrabbing()（100~150ms）感知进入/退出，再调 lockCursor/setPointerVisible。char 仅在 !grab 时发（防聊天/视角键串扰）。

## 1. C 改动
### meowcraftbridge（libs/jrelib/src/main/cpp/meowcraftbridge/）
- env 自由尾区(0x271e6+ reserved_tail)划出 `int grabbing`（放结构体新增字段并 _Static_assert 保持总尺寸/偏移不变；reserved 区足够）。
- `Java_..._CallbackBridge_nativeSetGrabbing(JNIEnv*,jclass,jboolean)`（input_bridge.c 已存在）里：写 env->grabbing = v。
- 新增导出 `int meowGetGrabbing(void)`：返回 env?env->grabbing:0（放 egl_gl.c 或 input_bridge.c 均可，注意不要破坏现有导出；meow 前缀）。

### meow_jre_bridge.cpp（meowjrebridge NAPI 面新增）
- 复用现有 PojavLib() dlopen 句柄 + dlsym 模式，新增 NAPI 导出（都先读 meowcraftbridge 里 critical_* 的真实签名再定参型）：
  - `meowSendKey(key:number, scancode:number, action:number, mods:number):boolean` → dlsym `critical_send_key`
  - `meowSendMouseButton(button:number, action:number, mods:number):boolean` → `critical_send_mouse_button`
  - `meowSendCursorPos(x:number, y:number):boolean` → `critical_send_cursor_pos`（注意签名可能是 float，转好）
  - `meowSendScroll(x:number, y:number):boolean` → `critical_send_scroll`
  - `meowSendChar(codepoint:number, mods:number):boolean` → 先 `critical_send_char_mods(cp,mods)` 再 `critical_send_char(cp)`（顺序重要）
  - `meowGetGrabbing():number` → `meowGetGrabbing`
  - `lockCursor(windowId:number, follow:boolean):number` → 调 OH_WindowManager_LockCursor（include window_manager/oh_window.h）
  - `unlockCursor(windowId:number):number` → OH_WindowManager_UnlockCursor
- CMake：meowjrebridge target 追加 `libnative_window_manager.so`。

## 2. 权限与类型
- entry/src/main/module.json5 requestPermissions 追加 `ohos.permission.LOCK_WINDOW_CURSOR`（reason 用 $string:reason_lock_cursor，usedScene abilities:["GameAbility"] when:"inuse"）；string.json 加 `reason_lock_cursor`。
- meowjrebridge types/libmeowjrebridge/Index.d.ts 追加上述 8 个声明；libs/jrelib/Index.ets re-export（const）。
- JvmLauncher.ets `JreLibModule` 补可选字段（meowSendKey/meowSendMouseButton/meowSendCursorPos/meowSendScroll/meowSendChar/meowGetGrabbing/lockCursor/unlockCursor）。

## 3. ArkTS：键码映射文件（新建 entry/src/main/ets/common/input/GlfwInput.ets）
- 常量：GLFW_MOD_SHIFT=0x1/CTRL=0x2/ALT=0x4/SUPER=0x8；GLFW 键码数值表（照 ref/HomoLauncher/.../LWJGLGLFWKeycode.ets 的数值；务必含 F1..F24、小键盘、编辑键、修饰左右）。
- `toGlfwKey(hm:number):number` 快路径：数字 2000..2009→hm-1952；A..Z 2017..2042→hm-1952；Space 2050→32；其余 switch 精确表（Del 2055→259 退格；ForwardDel 2071→261 删除；Ctrl_Left 2072→341 …；AT/PLUS/STAR/POUND 等→0）。未知→0（调用方丢弃 key，但仍可 char）。
- `glfwMouseButton(hmButton:number):number`：Left(1)→0、Right(2)→1、Middle(4)→2、Forward(16)→3、Back(8)→4；其它→-1。
- char 判定：可打印 unicode 0x21..0x7E。

## 4. GameWindow.ets 转发层
- XComponent 加 `id('game-xc')`、`.focusable(true)`、`.focusOnTouch(true)`、`onKeyEvent/onMouse/onAxisEvent`（事件里先判 source? 鼠标 source 仅 Mouse 时处理可选，先全量）。
- 状态（struct 私有，非 @Local 也行但需引用 this）：grabbing:boolean、pressed:Set<number>(KeyCode)、mods 位（自维护）、虚拟光标 vx/vy、winId、frameW/frameH（用 surface 尺寸变量已有 fw/fh? onSurfaceChanged 有；存最近一次）、jrelib 模块引用懒加载（首次事件时 import）。
- 键盘 handler：
  - down/up（KeyType），先同步修饰位（若键是 mod 键）后计算 glfwKey；down: pressed 已含→action=2 else 1 & add；up→0 & delete。
  - key!=0 → meowSendKey(glfwKey,0,action,mods)。down 且 unicode 可打印且 !grabbing → meowSendChar(unicode,mods)。
  - Esc down → setGrab(false)（菜单兜底，勿吞事件本身，仅当 grab 中）。
  - e.stopPropagation()。
- 鼠标 handler：
  - Press/Release（含 Cancel 按 Release）→ meowSendMouseButton(glfwBtn, down?1:0, mods)。Left press 且 !grabbing 且 cursor 在窗口 → 进入 grab？——**注意先不自动 grab**（菜单期点按钮不能立刻锁），由 MC grab 状态（轮询 meowGetGrabbing）决定锁；点按照常送按钮让 MC 处理。简化：仅当 grabbing 时才处理 raw 视角；MC 进世界会置 grab→轮询切锁。
  - Move：grabbing → vx+=rawDeltaX*S; vy+=rawDeltaY*S; meowSendCursorPos(vx,vy)。!grabbing → 绝对：rx=windowX/winVpW、ry=windowY/winVpH（vp 宽高缓存），meowSendCursorPos(rx*frameW, ry*frameH)（frame 尺寸缓存在 onSurfaceChanged/onSurfaceCreated 的 fw/fh）。
- 滚轮 handler：onAxisEvent UPDATE 期 getVerticalAxisValue 非0 → meowSendScroll(0, -v)（或 sign）；水平 getHorizontalAxisValue 非0 → meowSendScroll(-h? ,0)（负向左）。
- grab 轮询：aboutToAppear 起 setInterval(120ms) 调 meowGetGrabbing()；状态变化时触发 async setGrab(target)：target→ lockCursor(winId,false)+pointer.setPointerVisible(false)+vx/vy=frameW/H 中心；false→ unlockCursor+visible(true)。获取 winId 经 window.getLastWindow(context())。轮询与 UI 线程 ok；离开页面清 interval（已有 pollTimer 模式可复用/加第二个 timer）。
- 生命周期兜底：aboutToDisappear/onSurfaceDestroyed：unlock+visible true + 补发全部按键 UP（清 pressed 发 action0）防卡键。

## 5. 摘 homl_bridge（最后做，单独一步验证）
- GameWindow：首帧 surface 不再调 homl_bridge.surfaceChanged（只用 setGameSurface）；resize 不再调 send_screen_size（已用 resizeGameSurface）→ 移除 homl 相关 import/代码。
- libs/jrelib/Index.ets 移除 homlBridge import/export；JvmLauncher.ets 移除 HomlBridgeApi 类型与引用；GameWindow 类型引用清理。
- 删除 assets libhoml_bridge.so、libdriver_helper.so（git 可还原）；删除 types/libhoml_bridge 目录及 jrelib oh-package 中对应依赖；检查 entry 无残留 homl_bridge 引用（grep）。
- （libc++_shared 保留：libopenal 仍依赖。）

## 6. 日志指纹
- 新增日志 tags 用现有 JreBridge/MeowPojav 体系；关键正文：`meowSendKey k=.. a=..`、`grab->1/0`、`lockCursor rc=`、`char cp=..`（调试级，别刷屏；可只打按下+状态切换）。

## 7. 约束/风险
- 不做 libraryname；不动 homl 之外的 HOML 资产直到第 5 步验证通过；UI 极简、注释朴素。
- repeat 自己维护；DEL 退格 ≠ 删除别抄错；小键盘两套都要；mods 用自维护集合。
- rawDelta 校准系数常量（默认 1.0）留注释可调。
- 事件高频：move/axis 天然节流（按帧/事件即可，ring 够大）。
- ArkTS Set 允许；类型严格（number map 用 number 键）。
- 实施后必须本机 clang 0 error/0 warn + ets 检查无诊断（重启 arkts MCP 若报陈旧）。

## 8. 参照
- ref/HomoLauncher/.../LWJGLGLFWKeycode.ets（数值表）、NativeInput.ets（结构）
- ref/Amethyst-Android .../CallbackBridge.java（mods/char 语义）
- [`02-interface-contract.md`](02-interface-contract.md)（critical_send 语义）、meowcraftbridge input_bridge.c（真实签名）
