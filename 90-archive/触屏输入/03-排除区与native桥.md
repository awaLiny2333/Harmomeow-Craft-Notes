# 03 - 排除区与 native 桥

> 已归档（2026-09-22）：历史档、非现状。现行结论见 [`../../20-design/input/输入-总览.md`](../../20-design/input/输入-总览.md) §2.4；
> 原始件：主 `stuffs/research/touch-controls/exclude-report.md` 与
> `stuffs/research/touch-controls/fixes-2-native.md`（含**事后更正**块）。不写行号，只写符号名。

## 0. 目标

虚拟按键覆盖层上的**按钮矩形**不能同时驱动 MC 光标 / 点击：按在按钮上的那根手指**只按按钮**，
其它手指照常驱动「触屏当鼠标」。

## 1. 机制（数据驱动 · display px · 双缓冲发布 · finger 级跳过）

1. **ArkTS 采集**：`TouchControlsView.ets` 维护 `regions[]`（左下方向网格 / 右下动作区 / 顶部 ESC / 顶部输入 / 顶部 TAB），
   每个容器挂 `.onAreaChange → onRegionArea(index, …)`，`buildCsv()` 遍历所有 `valid` 矩形生成
   `"x,y,w,h;..."`，**去重 + 防抖 50ms** 后调 `GameInputController.setTouchExcludeRects(csv)`。
   - **数据驱动**：矩形随布局 / 缩放 / 边距**自动跟随**，不手写矩形。
   - `EXCLUDE_REGION_COUNT` 与 `regions` 条数一致（随布局收敛由 5 → 4）。
2. **桥**：`setTouchExcludeRects` → `libs/meowcraftlib/Index.ets` 导出的 `touchSetExcludeRects`
   → `meowjrebridge.cpp` NAPI `TouchSetExcludeRects`（字符串两段式：先长度后内容）→ `dlsym` 到
   native `meowTouchSetExcludeRects`。
3. **native 存储**：`meowTouchSetExcludeRects(const char *csv)` 解析 CSV（`sscanf` 逐段，非 4 字段或
   宽 / 高非正跳过；**上限 24 段**超出即停；空串 / NULL 清空），写入**双缓冲槽位**。
4. **touch filter 命中**：`meow_touch_filter` 算出 `dx,dy` 后先判 `meow_touch_in_exclude(dx,dy)`；
   命中 ⇒ 记下该 finger id、必要时补发左键释放、**整段手势 `return false`**（不进入 `g_tFingers` 计数）。
   ⇒ 多指之间**不串**（只有起手落在矩形内的那根手指被跳过）。

### 为什么用 display px（而不是 local）

- 原生 filter 的 `dx,dy = OH_Input_GetTouchEventDisplayX/Y` 本就是**屏幕物理 px**，排除矩形用同一空间，
  原生命中判断**无需换算**，也不依赖 `g_filterOriginX/scale` 的标定状态
  （纯触屏、只在按键上操作、XComponent 从未收到触摸时 origin 仍是哨兵值）。
- ArkTS 侧换算：`TouchObject.displayX/Y` = 相对屏幕的 vp，`windowX/Y` = 相对窗口的 vp
  ⇒ 窗口原点偏移 `winOff = display − window`（自由浮窗非 0）；按钮 display px
  = `(globalPosition_vp + winOff) × vp2px(1)`。`winOff` 在**首次触摸**时标定并缓存。

## 2. 双缓冲 + 原子发布（防半更新 / 瞬时清零）

- 写方 `meowTouchSetExcludeRects` 只写「**非当前**」槽，连条数一起写完，再 `atomic_store(release)` 切槽。
- 读方 `meow_touch_in_exclude` 先 `atomic_load(acquire)` 取槽，只读该槽的内容与条数。
- ⇒ 读方拿到的永远是**整份写完的快照**：不会读到写一半的矩形，也不会出现 count 瞬时为 0；空串清空同样走发布路径。
- 残留窗口（自认）：写方在一次 filter 回调未跑完时连发两次更新、且正好回写到读方手里那份才可能撞上；
  两次更新之间隔着一次完整 NAPI 调用，实际不构成问题。

## 3. finger 表维护（回归治本的关键）

- 排除区 finger 表（`g_tExclFingers` / `g_tExclFingerCount`）**只由 filter 线程**在
  **`UP` / `CANCEL`** 与**会话边界**维护。
- **重设排除区快照时【不清】finger 表**（这一点是关键）：ArkTS 会在**手势进行中**重推排除区
  （首触标定、IME / 旋转 / resize）⇒ 若随快照清表，按住中的手指会被中途「解封」。
  第 1 轮复核曾把「清表」当补强，实为回归成因（见 [06](06-两轮独立复核与修复复盘.md) 坑 2）。

## 4. native 侧函数清单

| 符号 | 职责 |
|---|---|
| `meowTouchSetExcludeRects` | 解析 CSV 并**发布**排除矩形快照（双缓冲 + 原子） |
| `meow_touch_in_exclude` | 命中判断（读 acquire 槽） |
| `meow_touch_excl_finger_has` / `_add` / `_remove` | 排除区 finger 表增删查 |
| `meowTouchFilterStart` / `meowTouchFilterStop` | filter 注册 / 注销；参数（enable / 原点 / 缩放 / 灵敏度）由 ArkTS 传入 |
| `meow_touch_filter` | 触摸回调：命中排除区 ⇒ 整段跳过；否则按 grab / 非 grab 分流 |
| `meow_touch_grab_delta` | grab 下转视角增量（系数 `g_touchSens × g_grabSensitivity`，**两因子都要留**） |
| `meow_touch_reset_gesture` | 手势状态复位，**只在会话边界**调用（不在 `meowTouchFilterStart` 开头） |

> 源码位置：`libs/meowcraftlib/src/main/cpp/meowcraftbridge/input_bridge.c` 与
> `libs/meowcraftlib/src/main/cpp/meowjrebridge/meowjrebridge.cpp`；类型声明在
> `libs/meowcraftlib/src/main/cpp/types/libmeowjrebridge/Index.d.ts`。

## 5. 桥方法的六处接线（新增桥方法必须齐）

| # | 落点 | 文件 |
|---|---|---|
| ① | native 实现 | `input_bridge.c` |
| ② | NAPI 包装 + `desc[]` 注册属性名 | `meowjrebridge.cpp` |
| ③ | TypeScript 声明 | `types/libmeowjrebridge/Index.d.ts` |
| ④ | ArkTS 导出 | `libs/meowcraftlib/Index.ets` |
| ⑤ | 类型接口 | `entry/src/main/ets/common/state/JvmLauncher.ets`（`JreLibModule`） |
| ⑥ | 调用点 | 如 `GameInputController.setTouchExcludeRects` / `TouchControlsView` 上报与清空 |

- 本轮的三个新桥方法：`touchFilterStart` / `touchFilterStop` / `touchSetExcludeRects`。
- **最容易漏 = ④**：漏 `Index.ets` 导出 ⇒ 运行期 `?.` **静默失效**（现象是「日志里一条都没有」），
  极易误判成「底层机制不生效」。
- 第 2 轮复核核对结果：**3 方法 × 6 处 = 18/18 齐全**（第 1 轮 `touchFilterStop` 曾缺第⑥处调用点）。

## 6. 不确定 / 未实测（原件自认）

- 排除矩形命中是否成立，依赖 `Area.globalPosition` 单位（vp vs px）。
- 首触 `winOff` 未知导致的一次漏排除。
- 覆盖层 `hitTestBehavior` 是否让「按在按键上的手指」在按钮区**同时**触发虚拟键与 touch-as-mouse。
- 「手指先在区外按下、后拖入按键区」不改变手势语义（按 DOWN 时点分类）——有意取舍。
