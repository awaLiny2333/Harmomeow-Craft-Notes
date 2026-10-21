# 15 · Stage B：摘除 libhoml_bridge.so + libdriver_helper.so（2026-09-08）

> 原生侧最后一个 HOML 黑箱摘除。至此应用层原生依赖全部自研/开源，黑箱清零。
> 前置：Step A 输入透传（12/14）、M3 关窗/resize（10/11）已把 homl 职责逐一替代。

## 侦查结论（两子 agent：引用测绘 + 语义覆盖审计）
- ArkTS 运行时实际只调 homl 两个函数：`surfaceChanged`（首次 surface）与
  `send_screen_size`（resize），都在 `GameWindow.injectAndLaunch` 一处；
  且我们的 `setGameSurface`/`resizeGameSurface` 调用**嵌套在 bridge 守卫 else 内**
  （桥缺失会连带跳过注入 = 潜在 bug，本次重写顺带修复）。
- 依赖图（readelf）：仅 `libhoml_bridge.so` DT_NEEDED `libdriver_helper.so`+`libpojavexec.so`；
  自研 `libpojavexec.so`/`libmeowjrebridge.so` 均不依赖两者 → 删两 so 不破坏加载。
- 职责覆盖：surface 注入/宽高镜像/关窗/grab/输入 send 已全在 meow 侧；
  homl 其余声明（set_env/dl_open/on_*/jvm_Launcher/accessClipboard 等）无调用方。
- **ring 模式开关依赖**：`send_screen_size` 是当前唯一触发 `critical_set_stackqueue(1)`
  （事件走 ring+pump 由 pump 线程派发）的路径 → 删除后需 meow 侧等价补位。

## 改动清单
### ArkTS
- `entry/.../pages/GameWindow.ets`：`injectAndLaunch` 重写——删 homl_bridge 守卫与
  两个调用，`setGameSurface`/`resizeGameSurface` 提升为无条件（首 surface vs resize 分支保留）；
  注释同步（不再提 homl 时序/冻结理由，更新为"同 sid 只标尺寸"语义）。
- `entry/.../common/state/JvmLauncher.ets`：删 `HomlBridgeApi` 接口与 `homl_bridge?` 字段。
- `libs/jrelib/Index.ets`：删 `import homlBridge` 与 `export homl_bridge`。
- 包声明：`libs/jrelib/oh-package.json5`、两处 `oh-package-lock.json5` 移除 `libhoml_bridge.so` 依赖。

### C
- `meow_jre_bridge.cpp`：`PojavLib()` dlopen 成功后 `dlsym("critical_set_stackqueue")` 并置 1
  —— 取代 homl send_screen_size 的 ring 模式开关（时序提前到 JVM 启动前，与旧运行时
  "首个 resize 后即 ring"的支配态一致）。
- 注释卫生：pojav_environ.h/.c、egl_gl.c、input_bridge.c、entry cpp/CMakeLists、
  libmeowassets Index.d.ts——把"homl_bridge 读写 X"改为历史态/自持描述。

### 删除
- `libs/jrelib/libs/arm64-v8a/libhoml_bridge.so`（152KB）、`libdriver_helper.so`（6KB）
- `libs/jrelib/src/main/cpp/types/libhoml_bridge/`（Index.d.ts + oh-package.json5）
- 悬空 oh_modules symlink

## 构建/产物验证
- `devecocli build clean` → `devecocli run --module entry jrelib`（assembleHsp+HAP 成功）。
- stripped native 集与 `.hsp` 内：**无 homl/driver**；含 libmeowjrebridge.so + libpojavexec.so。
- HAP 内仅剩 rawfile `meowcraft_extras.tar.gz`（Java jar 载体，非 native）。

## 剩余风险（实机验证项）
1. **Java 侧 launcher.jar ArkUIKit**：类常量池含 `System.loadLibrary("homl_bridge")`；
   是否在 MC 1.21.10 路径执行无法静态判定 → 跑游戏 grep `UnsatisfiedLinkError`。
   若触发：需对 launcher.jar 做字节码摘除/替换（下策：补同名空 stub，不推荐）。
2. ring 模式提前启用 → 实机确认输入/IME/滚轮语义与之前一致。
3. resize/关窗/渲染回归。
4. 已知取舍（沿用，非回归）：pojavSetSurfaceId 在真正 sid 变更时泄漏旧 OH_NativeWindow
   （正常流 sid 恒定，与 Stage B 前行为一致）。

## 验证日志指纹
- 启动正常：`set surface sid=... WxH`（首帧）→ `resize surface sid=... WxH`
- 错误即败：`UnsatisfiedLinkError` / `homl_bridge`
- 输入：`INP key`/grab；IME `IME activate/deactivate`；关窗 `meow request close`
