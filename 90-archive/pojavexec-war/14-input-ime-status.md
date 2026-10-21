> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../20-design/input/输入-总览.md`](../../20-design/input/输入-总览.md) 与 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)。

# 14 · 输入透传 + 隐形 IME：实现与已知限制（2026-09-08 实机定稿）

> 覆盖 Step A 键鼠透传、grab 光标锁、隐形 IME（聊天+菜单），及删除语义的最终形态。
> 规格前情：12-input-forwarding-spec.md（Step A）、13-ime-native-spec.md（IME v2）。

## 已实装清单
### 键鼠透传（全自研，homl_bridge 仅 Step B 待摘）
- ArkTS → jrelib(meowjrebridge) `meowSendKey/MouseButton/CursorPos/Scroll/Char` → meowcraftbridge `critical_send_*` → ring → pump → MC。
- 键盘：XComponent onKeyEvent（focusable），KeyType.Down/Up；自维护 pressed 集合：
  - 同键 Down 已在集合 → GLFW_REPEAT；mods 由 pressed 实时推导（SHIFT/CTRL/ALT/SUPER 位）。
  - char 仅在 !grab、可打印、无 Ctrl/Alt/Super 组合时发（Ctrl+A 等不被覆盖）。
- 鼠标：onMouse（组件本地 x/y 换算 framebuffer 像素，round 消除 floor 半像素偏移——修复 56px 标题栏导致的 Y 漂移）；grab 用 rawDeltaX/Y × 灵敏度 喂虚拟光标。
- 滚轮：onAxisEvent 垂直/水平取反。
- grab：轮询 meowGetGrabbing → OH_WindowManager_LockCursor(winId,false)+pointer.setPointerVisible(false)；失焦/清理自动恢复。
- 关窗退出/独立进程/防重复启动：见 11-m3-done.md（已提交）。

### 隐形 IME（中文输入，native 手感）
- 隐形 TextInput（1×1/opacity0/**hitTestBehavior(None)**：不显示 I 光标、不拦截点击、焦点仅代码控制）。
- 激活：非 grab（菜单/聊天等 MC 文本态）自动激活（poll 驱动、120ms 延迟、600ms 去激活冷却防抢焦点环）；聊天经 T// 也覆盖。
- XComponent 无 focusOnTouch（避免点击抢焦点），焦点全由 requestFocus('ime-input'/'game-xc') 管理；鼠标点击后 refocus IME。
- **删除语义（最终形态 = 本地缓冲镜像 + 尾差）**：
  - 输入/IME 上屏 → 尾差逐码点注入 MC（UTF-32 处理代理对）；
  - 删新输入：本地 TextInput 删除 → onChange 尾差 → BACKSPACE 给 MC（`imeLocalDeleted` 防交界双删）；
  - 删 MC 预置文字（镜像空）：Backspace Down 常被吞只来 Up → Up 合成一次（每次按键删一个）。
- Enter 提交（发 ENTER 给 MC）、Esc 取消（发 ESC 给 MC）后去激活；期间不注入 char。

## 已知限制（用户选 1：接受并记录）
1. **←/→ 光标移动与 Shift+选区在 MC 里不显示**：编辑发生在隐形框，MC 渲染不跟随光标/选区（操作有效）。要真显示需切 MC 原生直通=丢中文 IME，未做。
2. **组字中按 Backspace 会连带删一个 MC 字符**：无 API 区分"删拼音候选 vs 删上屏字"；启发式曾修复但误伤普通删除，已回滚为确定性删除，接受此取舍。
3. 菜单文本仅尾部编辑语义（无 MC 光标同步）；Home/End/←→ 不转发。
4. rawDelta 灵敏度常量默认 1.0（手感可调 CURSOR_SENS）。

## 日志指纹
- 输入：`INP key ...` / grab→；IME：`IME activate/deactivate`；鼠标修复探针 `ABS-CURSOR`（已留，可删）。
