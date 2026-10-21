> 已归档（2026-09-15）：已被 `00-current/渲染链与迁移结论.md` 取代。

# 关键发现：鸿蒙系统原生提供桌面 OpenGL（路线重大更新）

> 日期：2026-09-07。来源：官方文档「API参考/OpenGL/opengl」+ XComponent NDK 指南。
> 结论先行：**鸿蒙 PC 提供桌面 OpenGL 3.0/4.2（系统 libGLv4.so），无需 gl4es/mobileglues
> 翻译层**。渲染链可做到与桌面几乎一致，这是本设计最大的简化点。

## 1. 官方文档实证

- **OpenGL 支持能力**：API 20 起 OpenGL 3.0，API 22 起 **OpenGL 4.2**。
- **支持设备**：API 20 起 PC；API 22 起部分 Tablet（用 `OH_Graphics_QueryGL` 判断）。
- **查询接口**：`eglGetProcAddress("OH_Graphics_QueryGL")`——存在且返回 1 → 用 GL；
  返回 0 → 用 GLES；函数不存在 → GLES。
- **所需动态库**：`libGLv4.so`、`libEGL.so`（另 `libace_ndk.z.so`、`libace_napi.z.so`）。
- **头文件**：`GL/gl.h`、`GL/glcorearb.h`（core profile 桌面 GL）、`EGL/egl*.h`。
- **必须配置 app.json5**：
  ```json5
  "appEnvironments": [{ "name": "NEED_OPENGL", "value": "1" }]
  ```
- **OpenGL ES**（另一篇）：ES 3.2 原生导出，需 `libGLESv3.so`/`libEGL.so`（移动/平板用）。

## 2. 对 Meowcraft 的意义（渲染链简化）

### 之前（HomoLauncher 思路）
```
MC (LWJGL-opengl)
  → 翻译层 gl4es/mobileglues（桌面GL → GLES）
  → EGL + GLES context
  → GPU
```
翻译层是最大黑盒/兼容性风险源。

### 现在（利用系统 OpenGL）
```
MC (LWJGL-opengl)  ——  1.21.10 恰好声明 LWJGL 3.3.3，桌面 GL 调用
  → liblwjgl_opengl.so (JNI)
  → 系统 libGLv4.so（桌面 OpenGL 3.2 core+）
  → GPU
```
即：**LWJGL 拿到的是桌面 OpenGL API**，应用侧不再需要 gl4es/mobileglues。
> ⚠️ **但不等于"与桌面原生 GL 无差别"**：`libGLv4.so` 底层是 **Mesa Zink（GL→Vulkan 翻译层）→ Maleoon 916**（见 §7），
> 存在偶发 20–70ms 尖刺。应用侧无翻译层，但系统层仍是翻译链。
- 渲染器选择：不再需要 mobileglues/gl4es；渲染器标识近似 `opengles3_desktopgl` 的"真桌面 GL"路
  （对应 Amethyst 的 Zink/Kopper 路线，但这里由系统直接给）。
- 需要 EGL 创建**桌面 GL context**：`eglBindAPI(EGL_OPENGL_API)`（对应 Amethyst gl_bridge 里
  仅 desktopgl 渲染器才走的路径，这次是主路径）。
- `OH_Graphics_QueryGL` 在运行时确认设备能力；PC 上预期返回 1。

## 3. XComponent surface → EGL 链路（官方范式）

官方「自定义渲染 XComponent」NDK 指南给出标准做法：
- ArkTS：`XComponent({ type: XComponentType.TEXTURE })` + `XComponentController`
  （onSurfaceCreated/onSurfaceChanged/onSurfaceDestroyed 回调，拿 surfaceId）。
- NDK：`OH_ArkUI_SurfaceHolder_AddSurfaceCallback` 注册生命周期回调；
  在 OnSurfaceCreatedNative 里创建 `EGLRender`（EGLDisplay → EGLSurface → 上下文），
  OnSurfaceChanged 更新尺寸。
- 即：surfaceId → native 侧 EGL/OpenGL 渲染 → 上屏，官方原生支持。
- HomoLauncher 的 `surfaceChanged(parseInt(surfaceId), w, h)` 就是这条路（把 string surfaceId
  转 number 交给 native）——但按官方 NDK 应走 `OH_ArkUI_SurfaceHolder` API 更规范。

## 4. 更新后的推荐架构

```
ArkTS UI (目录/版本/启动)
  XComponent(TEXTURE) + controller 回调
  ArkTS 键鼠事件 → 输入桥

Native (C/NDK, 鸿蒙新写；早期参考 Amethyst 结构，现净室自研)
  OH_ArkUI_SurfaceHolder 生命周期 → EGLRender
  EGL: eglBindAPI(EGL_OPENGL_API)   ← 桌面 GL，非 ES
  dlopen libGLv4.so (+ libEGL.so)   ← 系统库
  meow_environ 事件缓冲（早期移植 Amethyst input_bridge 思路，现净室重写；输入源=ArkTS）
  dlopen libjli.so → JLI_Launch（JVM 拉起，复用 HomoLauncher jre25 思路）

OpenJDK (arm64, Java21+) — 复用 jre25 HSP 产物
  Java 侧：LWJGL 官方 Java 包 + 自研净室 Java GLFW stub（早期参照 Amethyst 源码）→ net.minecraft.client.main.Main
```

## 5. 待核实/风险（更新）

| 项 | 状态 |
|----|------|
| libGLv4.so 的系统性 | ✅ 官方文档证实（PC 系统库），不再是"未知/厂商库" |
| 是否需 NEED_OPENGL | ✅ 必须配 app.json5 appEnvironments，否则可能拿不到 GL 环境 |
| GL 版本满足 1.21.10 | 待实测：1.21.10 需 OpenGL 3.2 core+；系统给 4.2，预期满足 |
| context 创建路径 | EGL_OPENGL_API + eglCreateContext（与 GLES 不同分支）需实测 |
| OH_Graphics_QueryGL 返回值 | PC 预期 1；应用仍需做回退（1/0/缺失三态） |
| LWJGL 3.3.3 native jar 里 liblwjgl_opengl.so 能否直接 dlopen 系统 GL | 预期可（它就是标准 dlopen libGL） |
| 输入（grab/光标锁） | 鸿蒙 LOCK_WINDOW_CURSOR 权限已确认存在 |

## 6. 一句话结论

**在鸿蒙 PC 上跑原版 1.21.10 的渲染问题被官方 OpenGL 支持大幅简化**：**应用侧**渲染驱动层可以
从方案里删掉（不再需要 gl4es/mobileglues 这类翻译层），走"系统 libGLv4 + 桌面 GL context"。
> 注意：系统 `libGLv4.so` 自身即 **Mesa Zink（GL→Vulkan）**，故性能**不完全等价**桌面原生 GL。
剩下的硬骨头只有三块：JRE 打包、GLFW/输入 stub、XComponent↔EGL surface。

## 7. 实测确认（2026-09-07，Step0 已出图）

- **XComponent + EGL + 桌面 GL 全链路跑通**：`OH_Graphics_QueryGL=1` →
  `CreateNativeWindowFromSurfaceId` → `eglBindAPI(EGL_OPENGL_API)` 3.2 context → 清出蓝色块。
- **libGLv4 底层 = Mesa Zink（桌面 GL over Vulkan）**：日志出现大量
  `ZINK: SSBO is readonly in vertex stage!` 与 vk instance/device 创建信息，EGL 1.5。
  说明系统桌面 GL 由 Vulkan 后端支撑（对 1.21.10 而言透明，无需关心）。
- **踩坑记录（对应 `../00-current/架构决策与踩坑.md`）**：
  surface 就绪必须用 XComponentController.onSurfaceCreated（onAttach 太早）；
  surfaceId 是 64 位句柄，NAPI 必须 int64 读（uint32 会截断）；
  InitSurface 需幂等（onSurfaceChanged 会重复触发，重复 eglCreateWindowSurface 报
  EGL_BAD_NATIVE_WINDOW=12291）。
