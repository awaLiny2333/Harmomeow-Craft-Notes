> 已归档（2026-09-15）：本文为早期平台专题研究，其"需 gl4es/mobileglues 翻译层"的假设已被推翻（现走系统桌面 GL `libGLv4.so`）；现行结论见 [`../20-design/`](../20-design/) 与 [`../20-design/render/渲染链-结论.md`](../20-design/render/渲染链-结论.md)。

# 鸿蒙 PC 上的 OpenGL ES 渲染技术梳理

> 这是"在 ARM 麒麟芯片鸿蒙 PC 上跑 Minecraft"最关键的一环。
>
> ⚠️ **早期研究（2026-09-07 前）**：当时假设需 gl4es/mobileglues 翻译层、mobileglues 为默认。
> **已推翻**：实测走**系统桌面 GL `libGLv4.so`**（底层 Mesa Zink over Vulkan），应用侧无需翻译层。
> 当前渲染链与定论见 `../00-current/渲染链与迁移结论.md` 与 `../00-current/现状基线.md` §5。

## 1. 为什么需要转换层

Minecraft 通过 LWJGL 调用 **桌面 OpenGL（Desktop GL / Core Profile）** 渲染。
但鸿蒙 PC / 移动设备的原生图形 API 是 **OpenGL ES（GLES 2.0/3.x）**（底层由 GPU 驱动提供，
可能还涉及 Vulkan）。两者 API 有差异（函数集、着色器方言 GLSL vs ESSL、扩展机制），
所以需要一个"翻译层"把桌面 GL 调用转成 GLES 调用。

## 2. 三种渲染驱动（来自 HomoLauncher `RENDERER_LIB`）

| .so 文件 | POJAV_RENDERER 值 | 底层技术 | 适用 |
|----------|-------------------|----------|------|
| `libng_gl4es.so` | `opengles3` | NG-GL4ES（Krypton Wrapper）+ GL4ES | 老牌方案，兼容性好 |
| `libmobileglues.so` | `opengles_mobileglues` | **MobileGlues** | **默认**，HomoLauncher 首推 |
| `libGLv4.so` | `openglv4` | 原生 GL v4 驱动 | **仅鸿蒙 PC 或平板** |

**关键证据**（`JVMLauncher.initEnv()` 注释 + toast）：

```ts
let ret = this.bridge.dl_open(glibName);
if(!ret){
  if(glibName == RENDERER_LIB.RENDERER_NAME_GLV4){
    toast("当前图形驱动仅鸿蒙pc或平板可用")
  } else {
    toast("图形驱动加载失败")
  }
}
```

即：在鸿蒙 PC/平板上，可以加载 `libGLv4.so`（原生 GL 4 驱动），效果最接近桌面；
在手机/嵌入式上则回退到 mobileglues/gl4es。

## 3. 转换层组件家族（对照 Amethyst README）

| 组件 | 功能 | 备注 |
|------|------|------|
| **GL4ES** | OpenGL 1.x~2.x → GLES 2.0 翻译 | 最常用，支持大量扩展 |
| **MobileGlues** | 统一 GLES 入口 + 驱动选择 | HomoLauncher 默认 |
| **NG-GL4ES / Krypton Wrapper** | gl4es 的现代包装 | |
| **ANGLE** | 把 GLES 转 Vulkan/D3D/Metal | 更"近原生"，性能好 |
| **Mesa 3D** | 完整软件/硬件 GL 实现 | llvmpipe 软件渲染兜底 |
| **virglrenderer** | 虚拟 GPU（宿主 GPU 转发） | 虚拟机场景 |
| **LWJGL3** | Java → 原生 GL 绑定 | `liblwjgl*.so` |
| **LWJGLX** | LWJGL2 API 兼容层 | 兼容老版本 MC |
| **libepoxy** | GL 函数指针动态解析 | 驱动加载 |
| **GLX shim (glxshim)** | 桌面 GLX 调用伪装 | Amethyst driver_helper |

## 4. 渲染链工作流（结合 HomoLauncher + Amethyst 推演）

```
Minecraft (Java) 
   → LWJGL 3 (liblwjgl_opengl.so / liblwjgl_opengles.so)
   → dl_open 选择的驱动 .so (mobileglues / gl4es / GLv4)
   → [翻译层] 把 Desktop GL → GLES
   → EGL (egl_bridge / libegl)
   → 鸿蒙 surface (XComponent TEXTURE 的 surfaceId)
   → GPU / 麒麟芯片图形驱动
```

## 5. 环境变量（HomoLauncher `initEnv` 设置项解读）

```c
setenv("POJAV_RENDERER", "opengles_mobileglues"); // 指定渲染后端
setenv("LIBGL_USE_MC_COLOR", "1");  // MC 颜色修正
setenv("LIBGL_GL", "31");           // 目标 GL 版本 3.1
setenv("LIBGL_ES", "3");            // 目标 GLES 3
setenv("NGG_DIR_PATH", cacheDir+"/"); // NG-GL4ES 工作目录
setenv("DLOPEN", "libspirv-cross-c-shared.so"); // SPIRV-Cross（着色器交叉编译）
setenv("LIBGL_NORMALIZE", "1");     // 规范化
setenv("LIBGL_NOINTOVLHACK", "1");
setenv("LIBGL_NOERROR", "0");
setenv("ALSOFT_LOGLEVEL", "0");     // OpenAL 静默
```

`DLOPEN=libspirv-cross-c-shared.so` 是关键 —— 用 SPIRV-Cross 做着色器交叉编译
（把 GLSL 编译成 SPIR-V 再交叉成 GLES 可用的 ESSL），这是现代转换链的核心组件。

## 6. LWJGL 相关 JVM 参数（HomoLauncher）

```c
-Dorg.lwjgl.opengl.libname=${renderer}      // ★指定渲染 .so 名
-Dorg.lwjgl.glfw.checkThread0=false         // 关线程检查
-Dorg.lwjgl.system.allocator=system
-Dorg.lwjgl.vulkan.libname=libvulkan.so     // Vulkan 路径（备用）
-Dglfwstub.windowWidth=${w} / windowHeight=${h}
-Dglfwstub.initEgl=false                    // GLFW stub 不自己初始化 EGL
// LWJGL DEBUG flags（调试时开启）
-Dorg.lwjgl.opengl.Debug=true ...
```

## 7. 鸿蒙侧的关键点

1. **XComponent TYPE=TEXTURE**：作为 GPU 渲染载体，`onSurfaceCreated` 拿到的 `surfaceId`
   通过 `bridge.surfaceChanged(surfaceId,w,h)` 传给原生 EGL 上下文绑定。
2. **`dl_open(renderer)`**：运行时 `dlopen` 指定的渲染 .so，而非编译期链接 —— 这是能动态切换
   渲染后端的关键。
3. **JRE 里的 OpenGL**：JRE 的 `awt`/`fontmanager` 等模块也含图形相关，需 caciocavallo 移植 AWT。
4. **麒麟芯片 GPU**：华为/麒麟 GPU 的 EGL/GLES 驱动由系统提供，转换层最终落到系统 GLES 栈。

## 8. 小结

在鸿蒙 PC（ARM 麒麟）上跑 MC 的渲染路径**已被 HomoLauncher 验证可行**：
- 首选 `libGLv4.so`（原生 GL4 驱动，最接近桌面，仅 PC/平板）；
- 备选 `libmobileglues.so`（默认通用）；
- 兜底 `libng_gl4es.so`。
核心机制是 `dl_open` + `POJAV_RENDERER` 环境变量 + SPIRV-Cross 着色器交叉编译 + EGL 绑定鸿蒙 surface。
