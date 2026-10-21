> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../20-design/input/输入-总览.md`](../../20-design/input/输入-总览.md) 与 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)。

# 13 · 中文输入：隐形 IME（native 手感）规格

> 目标：聊天/文字输入用系统中文输入法，**视觉零新增**（无可见输入条/无快捷键），交互"点进聊天直接打中文"。
> 平台约束（API23 已核实）：IME 必须有一个获焦的文本输入客户端；三方无全局 IME 文本通道。→ 用**隐形 TextInput** 作客户端，仅在"MC 打开文本输入"时自动激活。

## 激活策略（防丢首字符，核心）
- **聊天/命令**（世界内）：grabNative=true 时用户按 `T` 或 `/`（GLFW_KEY_T=84、'/'=47）开聊天。做法：onKeyEvent 检测到 grabNative 且该键按下 → **正常转发给 MC**（开聊）→ 置 `chatOpening=true`，`setTimeout 250ms` 后若 `!grabNative && !imeActive` → `activateIme()`。
  → 首个拼音字母是在 IME 激活**之后**按的，天然不丢。
- **IME 激活后**：焦点给隐形 TextInput（系统输入法随焦点弹出；中文直接可打）。此后键不再到 XComponent。
- **退出**：a) Enter（无组字）提交：发 ENTER key 给 MC 提交聊天 → deactivate；b) Esc：发 ESC 给 MC 关聊天 → deactivate；c) grab 轮询发现 grabNative 回 true（MC 关了聊天/回游戏）→ deactivate。
- **菜单类文本域**（如新建世界名，grab 恒 false，无开聊信号）：无法可靠判"此处在打字"——本版**不做自动**（保持原直通英文输入）；如后续要支持，需另设计显式入口。文档记录该取舍。

## v2（2026-09-08 用户要求"其它输入框也支持 IME"）——非 grab 态 IME 常驻

> 取代上节"仅 T 开聊激活 + 菜单不自动"的取舍：把激活从"聊天信号"泛化为"**grab=false 即 MC 处于菜单/文本态**"。理由：菜单内唯一需要键盘打字的场景就是 MC 的文本框（世界名/种子/改名等），而 grab=false 正好覆盖这些态；首字符不再丢失（激活先于任何键入），菜单键盘导航靠"从 TextInput 转发非编辑键"保住。

### 激活/停用
- 轮询 pollGrabbing 得到 grabNative：
  - 变 false（进入菜单/聊天）且 `!imeActive && !imeCooldown` → 延迟 ~120ms 后 activateIme()（保留 timer/幂等；连续菜单层级无需重复激活）。
  - 变 true（回游戏）且 imeActive → deactivateIme()（焦点还 XComponent）。
- `deactivateIme` 后设 `imeCooldown` 600ms，防"Esc 关菜单→焦点回 XComponent 期间 grab 仍 false→立即再激活"的抢焦点环。
- 移除上版 T/Slash 开聊专用激活（不再需要；非 grab 即激活覆盖聊天与菜单）。Esc 菜单逐层关闭由"两条路径都转发 Esc"保证：
  - XComponent 直通路径（imeActive=false 时，如在 cooldown/焦点切换间隙）收到 Esc down → 也 `forwardKey(256,down)` 给 MC（不只 grab 解锁逻辑）。
  - TextInput onKeyEvent 收到 Esc → 转发 Esc 给 MC + deactivateIme()。

### TextInput 键转发（IME 激活期间）
- TextInput.onKeyEvent 收到**物理键**：统一调用与 XComponent 相同的"key→sendKey"处理（含 mods 由 pressed 推导、down/up），但：
  - **不注入 char**（文本统一走 onChange 尾差同步，避免双插）；
  - **抑制本地编辑键**的 key 转发：Backspace/Delete/Home/End/←/→（其效果由本地缓冲编辑 + 尾差同步映射成 MC 的 BACKSPACE/DELETE 或忽略）；否则双删。
  - Enter 不进 onKeyEvent（走 onSubmit）；Esc 见上；Space 作为普通字符由 onChange 处理，key 不转。
- 结果：菜单里英文字母/数字经 TextInput 缓冲→onChange 尾差→char 进 MC（等效直打）；中文经 IME 同上；Ctrl+A 等组合键经 key 转发（mods 含 CTRL）触发 MC 全选（TextInput 本地不产生文本变化→无 char→无覆盖）；F 键/其它功能键正常转发。

### 首字符/竞态
- 菜单打开即有 ~120ms 延迟激活；期间用户基本不会立即打字。若竞态发生（120ms 内已直通转发首个字符），由于该路径已带 key+char 且与后续 IME 文本连续，可接受；记录日志便于观察。
- 世界内按下 Esc 回菜单瞬间若立刻开始打字（<120ms）可能走直通而 IME 未就绪——cooldown 交互设计保证 120ms 后焦点给 IME；首字走直通最多丢一次 IME 合成机会，属可接受边缘（日志取证）。


## UI（隐形）
- Stack 顶层放：`TextInput({ text: this.imeText, placeholder: '' })`：
  `.width(1).height(1).opacity(0).focusable(true).id('ime-input')`（不可见、可获焦），位置默认即可。
- 不用可见提示条、无按钮、无 Ctrl+Space 处理（全部移除上版实现）。

## 状态与同步（聊天尾差模式）
- 字段：`imeActive:boolean`、`imeText:string`（@Local，绑定 TextInput）、`imeLast:string`。
- `activateIme()`：imeActive=true；imeText=''；requestFocus('ime-input')（FocusController，失败打日志）。
- `onChange(v)`：尾部 diff 同步到 MC（聊天光标在尾部，够用）：
  - `v.startsWith(imeLast)` → 追加段 = v.slice(imeLast.length) → 逐 UTF-32 codepoint `meowSendChar(cp,0)`；
  - `imeLast.startsWith(v)`（删除）→ 差值长度 n → 逐次 `meowSendKey(BACKSPACE=259,0,PRESS,0)`+`(…,RELEASE,0)`；
  - 其它替换（IME 组字中途翻屏等少见）→ 简化：diff 退化为 把 imeLast 与 v 的公共前缀剔除后，先按删除量发 BACKSPACE 再按追加量发字符（长度差法）；不追求完美，注释说明。
  - 更新 imeLast=v。
- TextInput `onKeyEvent`：Esc（KeyCode 2070, Down）→ `deactivateIme()` 并发 ESC 给 MC（sendKey 256）。Enter 不进 onKeyEvent（走 onSubmit）。
- `onSubmit`（IME 非组字期 Enter 触发）：先发 ENTER PRESS/RELEASE 给 MC → 清空并 deactivate。
- `deactivateIme()`：imeActive=false；imeText=''；imeLast=''；焦点还 XComponent（requestFocus('game-xc')）；若 grabNative 依 MC 定（不强制锁）。
- 每次 activate/deactivate/发字符打一行调试日志正文 `IME ...`（便于真机取证，别刷屏：只打 activate/deactivate/onSubmit）。

## 与 grab/其它逻辑配合
- grab 轮询 `pollGrabbing`：imeActive 期间不处理 grab 变化（跳过）；deactivate 后按 grabNative 恢复。
- onKeyEvent（XComponent）：imeActive 时不应收到键（焦点已移走），但保险地直接 return；chatOpening 逻辑只在 !imeActive 时跑。
- XComponent 生命周期兜底（关窗/disappear）：deactivate + 恢复鼠标可见 + 全键 UP（既有逻辑保留）。

## 参照
- 现有 GameWindow 已含：ime 覆盖层（上版可见版，待删除）、grab 轮询、onKeyEvent/onMouse/onAxisEvent、sendChar/meowSendChar、requestFocus 用法（'game-focus' 旧 id 若与 xc id 冲突，检查统一用 'game-xc' 或保留两个 id 方案）。
- meowSendChar/meowSendKey NAPI 已存在（meowjrebridge）。
