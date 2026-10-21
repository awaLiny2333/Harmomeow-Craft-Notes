> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)。

# 05 · homl_bridge → pojav_environ ABI 取证（drop-in 二进制兼容红线）

> 来源：子 agent 反汇编取证（llvm-objdump/nm/readelf + Amethyst environ.h 对照）。

## 核心结论
**不能整份照抄 Amethyst `pojav_environ_s` 尾段**；前段 0x000–0x27160 字节级兼容 ✅。homl_bridge 全库只解引用 `pojav_environ` **3 处**（surfaceChanged / on_cursor_enabled / on_nominal_exit），硬约束集中在 4 个槽。

## homl_bridge 实测访问（struct 基址=0）
| 偏移 | 宽 | R/W | 所在 NAPI | 语义 |
|---|---|---|---|---|
| 0x000 | 8 | R | surfaceChanged | **OH_NativeWindow\*** 当前窗口指针：GetSurfaceId 与 JS 传入新 id 比对，不同则 Destroy + Create（新窗口**不写回** 0x000） |
| 0x27180 | 8 | W | on_cursor_enabled | JS 通知 thunk 指针（0/1），可空，调用形态 `((void(*)(int))slot)(v)` |
| 0x27188 | 8 | W | on_nominal_exit | JS 通知 thunk 指针（exit code），可空 |
| 0x271d4 | 4 | W | surfaceChanged | **savedWidth**（=HOML 原 critical_send_screen_size 同址） |
| 0x271d8 | 4 | W | surfaceChanged | **savedHeight** |

**红线**：0x000[8] 可读窗口指针；0x27180/0x27188 放可空回调；0x271d4/0x271d8 为 savedW/H；**0x271d4..0x271dc 禁止放 8B 指针**（Amethyst 此处是 glfwThreadVmEnv/dalvikJavaVMPtr，surfaceChanged 每次 stp w,w 会打坏它们——致命冲突）。
0x27180/0x27188 只能当 native thunk 槽，**不能**按 Amethyst 当 jmethodID Call*（会把代码地址当 methodID 崩）。

## 建议 drop-in 布局（5.1，前段=Amethyst 原样）
- 0x000 pojavWindow(OH_NativeWindow*/8) · 0x008 mainWindowBundle · 0x010 config_renderer(int) · 0x014 force_vsync · 0x018 eventCounter(atomic 8) · 0x020 events[8000]×20B · 0x27120 outEventIndex · 0x27128 outTargetIndex · 0x27130 inEventIndex · 0x27138 inEventCount · 0x27140-0x27158 cursorX/Y/cLastX/cLastY(4×double)
- 0x27160-0x27178 自用槽 · **0x27180 jsNotifyCursorEnabled · 0x27188 jsNotifyNominalExit** · 0x27190 自用
- 0x27198+ 自排（JavaVM*/JNIEnv*/keyDown/mouseDown/gamepad/invoke 表/bool…）
- 0x271d0-0x271d3 bool 簇 · **0x271d4 savedWidth · 0x271d8 savedHeight** · 0x271dc+ 自排尾部（建议总量 ≥ HOML 原 alloc 0x27228）

## 事件/ring 情报（producer/consumer 都在自研 so 内，须自洽实现）
- GLFWInputEvent={int type,i1,i2,i3,i4}（20B）；events[8000] 回绕；atomic eventCounter@0x018；inEventIndex@0x27130。
- type 常量（HOML 与 Amethyst 一致实测）：char=1000、char_mods=1001、cursor_enter=1002（cursor_pos 首入隐式）、key=1005、mouse_button=1006、scroll=1007；**cursor_pos 不入 ring**（直写 cursorX/Y double）；send_screen_size 只写 savedW/H（不投 HOML 那套 1004/1008 不一致降级）。
- homl_bridge NAPI → 我们 so 的符号调用：send_mouse_button(3×int) / send_cursor_pos(2×int→float) / send_screen_size(2×int) / send_key(4×int) / send_scroll(2×double) / send_char(int→bool) / send_char_mods(2×int)；send_screen_size 前先 critical_set_stackqueue(1)。

## surface 注入缺口（drop-in 设计必答）
homl_bridge 只**创建/销毁 native window 却不写回 0x000**。当前 HOML 画面能出的真正机制未完全查明。自研 so 若要渲染必须拿到 window：
- 方案 (a)（最小、推荐）：自研 so 追加一个小导出（如 `pojavSetSurfaceId(int64 sid)` 或写 window 槽），由 GameWindow（ArkTS，surfaceChanged 同点）顺带调用——改变量极小且归我们控制。
- 方案 (b)：继续黑箱试验确认 HOML 究竟如何把 window 写进 0x000。
> 决策待 M1 起点定（建议 (a)）。
