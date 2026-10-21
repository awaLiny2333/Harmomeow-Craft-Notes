> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../20-design/render/渲染链-结论.md`](../../20-design/render/渲染链-结论.md)。

# 02 - OH_ArkUI_SurfaceHolder 官方文档调研（子 agent 原始情报）

> 来源：general 子 agent 返回，主会话未改动内容（仅加本行说明）。
> 方法：`devecocli docs search` + `devecocli docs read <documentId>`。

# HarmonyOS ArkUI SurfaceHolder Research Report

Method: `devecocli docs search` + `devecocli docs read`. All claims below cite doc title + documentId/header path. Where the docs are silent, marked **NO DOC FOUND**.

---

## (a) Verdict — what SurfaceHolder is & relation to XComponent

- `OH_ArkUI_SurfaceHolder` is an opaque handle that wraps an XComponent's Surface so native code can manage its lifecycle and obtain the `OHNativeWindow`. It is **not a new rendering component** — it is the recommended *native-side lifecycle manager for an XComponent node*.
  - Cite: `OH_ArkUI_SurfaceHolder` — `API参考/ArkUI_方舟UI框架/C_API/结构体/OH_ArkUI_SurfaceHolder/capi-oh-nativexcomponent-native-xcomponent-oh-arkui-surfaceholder` ("提供封装的OH_ArkUI_SurfaceHolder实例。起始版本：19")
  - Header: `native_interface_xcomponent.h`; Module: `OH_NativeXComponent Native XComponent`.
- XComponent itself supports three type values; only `SURFACE` (separate on-screen, DSS when black) and `TEXTURE` (GPU-composited, higher power) are current. `COMPONENT` deprecated v12, `NODE` deprecated v20.
  - Cite: `枚举说明` — `API参考/ArkUI_方舟UI框架/ArkTS组件/公共定义/枚举说明/ts-appendix-enums` (XComponentType).
- Relationship: an XComponent can be created either (1) ArkTS-declarative, (2) ArkTS custom-node (`typeNode`/`NodeController`), or (3) NDK native node. SurfaceHolder is created from that node's `ArkUI_NodeHandle`.
  - Cite: `自定义渲染 (XComponent)` — `开发指南/ArkUI_方舟UI框架/UI开发_ArkTS声明式开发范式/添加组件/自定义渲染_XComponent/napi-xcomponent-guidelines` §"XComponent的开发范式" (5 paradigms listed).
- **Is OH_NativeXComponent deprecated?** The header/API reference does **not** use the word 废弃 for `OH_NativeXComponent` itself. Instead the guide states a **recommendation to replace it** and cites two defects:
  1. `OH_NativeXComponent` instance lifetime is strongly tied to the XComponent; operating it after component destruction can cause stability/crash problems.
  2. Its interaction-event API is not rich — only basic touch/mouse/keyboard; high-level gestures (long-press, drag) require custom recognition.
  - Quote/cite: same guide, §"OH_NativeXComponent向OH_ArkUI_SurfaceHolder的迁移": "建议使用OH_ArkUI_SurfaceHolder相关接口代替OH_NativeXComponent相关接口".
- Formally deprecated items found (exact notes):
  - `OH_NativeXComponent_AttachNativeRootNode` / `OH_NativeXComponent_DetachNativeRootNode`: 起始版本 12, **废弃版本 20**, replacement `OH_ArkUI_NodeContent_AddNode` / `OH_ArkUI_NodeContent_RemoveNode`. Cite: `native_interface_xcomponent.h` header doc.
  - XComponent constructor `XComponent(value: {id, type: string, libraryname, controller})`: "从API version 12开始不再演进，推荐使用 XComponent(options: XComponentOptions)". Cite: `XComponent` — `API参考/ArkUI_方舟UI框架/ArkTS组件/渲染绘制/XComponent/ts-basic-components-xcomponent`.
  - `XComponent(value:{id,type,...})`: "该接口从API version 12开始不再演进" (same doc).
  - `XComponentType.COMPONENT` 废弃 v12; `XComponentType.NODE` 废弃 v20 (enum doc).

---

## (b) API inventory — OH_ArkUI_SurfaceHolder / SurfaceCallback / node-based XComponent

Header `native_interface_xcomponent.h` (all below, unless noted). Source: `native_interface_xcomponent.h` doc + `自定义渲染 (XComponent)` §接口说明.

| API | Signature | Version |
|---|---|---|
| `OH_ArkUI_SurfaceHolder_Create` | `OH_ArkUI_SurfaceHolder* (ArkUI_NodeHandle node)` | 19 |
| `OH_ArkUI_SurfaceHolder_Dispose` | `void (OH_ArkUI_SurfaceHolder*)` | 19 |
| `OH_ArkUI_SurfaceHolder_SetUserData` | `int32_t (OH_ArkUI_SurfaceHolder*, void* userData)` | 19 |
| `OH_ArkUI_SurfaceHolder_GetUserData` | `void* (OH_ArkUI_SurfaceHolder*)` | 19 |
| `OH_ArkUI_SurfaceCallback_Create` | `OH_ArkUI_SurfaceCallback* ()` | 19 |
| `OH_ArkUI_SurfaceCallback_Dispose` | `void (OH_ArkUI_SurfaceCallback*)` | 19 |
| `OH_ArkUI_SurfaceCallback_SetSurfaceCreatedEvent` | `void (cb*, void (*onSurfaceCreated)(OH_ArkUI_SurfaceHolder*))` | 19 |
| `OH_ArkUI_SurfaceCallback_SetSurfaceChangedEvent` | `void (cb*, void (*onSurfaceChanged)(OH_ArkUI_SurfaceHolder*, uint64_t width, uint64_t height))` width/height unit **vp** | 19 |
| `OH_ArkUI_SurfaceCallback_SetSurfaceDestroyedEvent` | `void (cb*, void (*onSurfaceDestroyed)(OH_ArkUI_SurfaceHolder*))` | 19 |
| `OH_ArkUI_SurfaceHolder_AddSurfaceCallback` | `int32_t (OH_ArkUI_SurfaceHolder*, OH_ArkUI_SurfaceCallback*)` | 19 |
| `OH_ArkUI_SurfaceHolder_RemoveSurfaceCallback` | `int32_t (OH_ArkUI_SurfaceHolder*, OH_ArkUI_SurfaceCallback*)` | 19 |
| `OH_ArkUI_XComponent_GetNativeWindow` | `OHNativeWindow* (OH_ArkUI_SurfaceHolder*)` | 19 |
| `OH_ArkUI_XComponent_SetAutoInitialize` | `int32_t (ArkUI_NodeHandle, bool)` default true | 19 |
| `OH_ArkUI_XComponent_Initialize` | `int32_t (ArkUI_NodeHandle)` | 19 |
| `OH_ArkUI_XComponent_Finalize` | `int32_t (ArkUI_NodeHandle)` | 19 |
| `OH_ArkUI_XComponent_IsInitialized` | `int32_t (ArkUI_NodeHandle, bool*)` | 19 |
| `OH_ArkUI_SurfaceCallback_SetSurfaceShowEvent` | `void (cb*, void (*onSurfaceShow)(OH_ArkUI_SurfaceHolder*))` | 20 |
| `OH_ArkUI_SurfaceCallback_SetSurfaceHideEvent` | `void (cb*, void (*onSurfaceHide)(OH_ArkUI_SurfaceHolder*))` | 20 |
| `OH_ArkUI_XComponent_SetExpectedFrameRateRange` | `int32_t (ArkUI_NodeHandle, OH_NativeXComponent_ExpectedRateRange)` | 20 |
| `OH_ArkUI_XComponent_RegisterOnFrameCallback` | `int32_t (ArkUI_NodeHandle, void(*)(ArkUI_NodeHandle, uint64_t ts, uint64_t targetTs))` | 20 |
| `OH_ArkUI_XComponent_UnregisterOnFrameCallback` | `int32_t (ArkUI_NodeHandle)` | 20 |
| `OH_ArkUI_XComponent_SetNeedSoftKeyboard` | `int32_t (ArkUI_NodeHandle, bool)` | 20 |
| `OH_ArkUI_AccessibilityProvider_Create` | `ArkUI_AccessibilityProvider* (ArkUI_NodeHandle)` | 20 |
| `OH_ArkUI_AccessibilityProvider_Dispose` | `void (ArkUI_AccessibilityProvider*)` | 20 |
| `OH_ArkUI_XComponentSurfaceConfig_Create` | `ArkUI_XComponentSurfaceConfig* ()` | 22 |
| `OH_ArkUI_XComponentSurfaceConfig_Dispose` | `void (ArkUI_XComponentSurfaceConfig*)` | 22 |
| `OH_ArkUI_XComponentSurfaceConfig_SetIsOpaque` | `void (config*, bool)` | 22 |
| `OH_ArkUI_SurfaceHolder_SetSurfaceConfig` | `int32_t (OH_ArkUI_SurfaceHolder*, ArkUI_XComponentSurfaceConfig*)` | 22 |

Notes / naming corrections:
- There is **no** `OH_ArkUI_SurfaceHolder_SetSurfaceCallback` and **no** `OH_ArkUI_SurfaceHolder_GetNativeWindow`. Correct names: `OH_ArkUI_SurfaceHolder_AddSurfaceCallback` and `OH_ArkUI_XComponent_GetNativeWindow`.
- There is **no** SurfaceHolder buffer-geometry set/get API. Surface geometry is read from `onSurfaceChanged(width,height)` (vp) or node attribute `NODE_XCOMPONENT_SURFACE_SIZE` (px, get-only) / set via `NODE_XCOMPONENT_SURFACE_RECT` (v18, set/get, px).
  - Cite: `ArkUI_NodeAttributeType（XComponent组件相关属性）` — `API参考/ArkUI_方舟UI框架/C_API/头文件/native_node_h/ArkUI_NodeAttributeType_XComponent组件相关属性/capi-native-node-h-nodeattributetype-xcomponent`.
- Old (non-holder) equivalents still exist on `OH_NativeXComponent`: `SetExpectedFrameRateRange` (v11), `RegisterOnFrameCallback`/`UnregisterOnFrameCallback` (v11), `RegisterMouseEventCallback` (v9), `RegisterKeyEventCallback` (v10), `RegisterUIInputEventCallback` (v12, **axis only**), `RegisterOnTouchInterceptCallback` (v12), `SetNeedSoftKeyboard` (v12). Cite: `native_interface_xcomponent.h` doc.
- `OH_NativeXComponent_ExpectedRateRange` (min/max/expected, fps) is v11. Cite: struct doc.

---

## (c) Input-event capability analysis (critical)

- **SurfaceHolder exposes no input callbacks of its own.** The `OH_ArkUI_SurfaceCallback` set contains only Created/Changed/Destroyed/Show/Hide — no touch/mouse/key/axis signature. (Cite: struct doc + header function list.)
- With SurfaceHolder the documented path is **ArkUI NDK node events** on the owning `ArkUI_NodeHandle`:
  - `nodeAPI->addNodeEventReceiver(handle, cb)` + `nodeAPI->registerNodeEvent(handle, <type>, 0, userData)`.
  - Enumerable events: `NODE_ON_CLICK_EVENT`, `NODE_TOUCH_EVENT`, `NODE_ON_MOUSE`, `NODE_ON_HOVER_EVENT`, `NODE_ON_AXIS`, `NODE_ON_KEY_EVENT`.
  - Cite: `绑定基础输入事件` — `开发指南/ArkUI_方舟UI框架/UI开发_基于NDK构建UI/添加事件响应/绑定基础输入事件/ndk-bind-input-events` (lists all six + accessor APIs for position/pressure/pointer count/touch area/mouse button/raw delta/axis values/key+modifier).
  - Migration guide uses exactly this for SurfaceHolder: `registerNodeEvent(handle, NODE_TOUCH_EVENT, ...)`. Cite: `自定义渲染 (XComponent)` §"监听交互事件".
- **Documented advantage of SurfaceHolder path:** "使用OH_ArkUI_SurfaceHolder相关的接口，除监听基础事件外还能监听长按、拖拽等高级手势" (same guide §"监听交互事件") — i.e. it inherits the full ArkUI NDK gesture system, unlike `OH_NativeXComponent` which only had basic events.
- `OH_NativeXComponent`-only input APIs (no SurfaceHolder equivalent needed because node events supersede them): `DispatchTouchEvent` in `OH_NativeXComponent_Callback`, `OH_NativeXComponent_RegisterMouseEventCallback`, `RegisterFocusEventCallback`/`RegisterKeyEventCallback`/`RegisterBlurEventCallback`, `RegisterUIInputEventCallback` (**仅支持轴事件**), `RegisterOnTouchInterceptCallback` (doc explicitly suggests migrating to `NODE_ON_TOUCH_INTERCEPT`).
  - Cite: `OH_NativeXComponent_Callback` struct doc; `native_interface_xcomponent.h` doc.
- **Gap / pitfall to flag:** the SurfaceHolder lifecycle callbacks give you no event object and no `window`; you must wire input separately through node events. Also, if an XComponent is created with the old `libraryname` param, ArkTS generic events (`onTouch`/`onClick`/…) "仅响应C-API侧事件接口" and will not fire — FAQ recommends the `XComponent(options: XComponentOptions)` form without `libraryname`.
  - Cite: `如何解决XComponent无法触发触摸事件问题` — `FAQ/UI框架/UI界面/如何解决XComponent无法触发触摸事件问题/faqs-arkui-909`.
- **No doc found** for any SurfaceHolder-specific mouse/key/axis convenience API; node events are the only documented path.

---

## (d) Frame-rate / present capability analysis

- No frame-rate API is attached to `OH_ArkUI_SurfaceHolder` itself. Use the **owning node**:
  - `OH_ArkUI_XComponent_SetExpectedFrameRateRange(ArkUI_NodeHandle, OH_NativeXComponent_ExpectedRateRange)` — v20.
  - `OH_ArkUI_XComponent_RegisterOnFrameCallback` / `UnregisterOnFrameCallback` — v20.
  - Cite: `native_interface_xcomponent.h` doc; usage example `native.setFrameRate` → `OH_ArkUI_XComponent_SetExpectedFrameRateRange(node, range)` in `自定义渲染 (XComponent)` §开发步骤.
- Struct `OH_NativeXComponent_ExpectedRateRange { int32_t min; int32_t max; int32_t expected; }` in fps — v11. Cite: struct doc.
- Old path equivalent: `OH_NativeXComponent_SetExpectedFrameRateRange` (v11) + `RegisterOnFrameCallback` (v11). Cite: `请求自绘制内容绘制帧率` — `开发指南/ArkGraphics_2D_方舟2D图形服务/使用可变帧率能力定制不同内容的绘制帧率/请求自绘制内容绘制帧率/displaysync-xcomponent`.
- Documented semantics/constraints:
  - The onFrame callback runs on the UI main thread; do not do heavy UI work inside it.
  - Must unregister when frame control no longer needed (memory/power).
  - API <18: callback kept firing while the XComponent instance existed; **from API 18 only while the XComponent is on-tree**.
  - Cite: same `displaysync-xcomponent` doc.
- **SurfaceHolder vs XComponent refresh-rate/performance benefit: NO DOC FOUND.** Frame rate is a property of the XComponent node, not of the holder. No 60 Hz cap claim, no "higher refresh rate with SurfaceHolder" claim in the docs reviewed.
- Composition-path difference that *is* documented (type-level, not holder-level): SURFACE renders separately and "背景色设置为黑色时走显示子系统（DSS）"; TEXTURE is frame-synced with ArkUI, unified with system animation, GPU-composited and **higher power than surface/DSS**.
  - Cite: `枚举说明` — XComponentType (ts-appendix-enums); `XComponent` component doc.

---

## (e) Constraints / pitfalls (documented)

- **Node requirement:** `OH_ArkUI_SurfaceHolder_Create` takes an `ArkUI_NodeHandle` of an **XComponent** node. The node can come from:
  - ArkTS declarative: `.onAttach()` → `getAttachedFrameNodeById(id)` → pass FrameNode to native → `OH_ArkUI_GetNodeHandleFromNapiValue`.
  - ArkTS custom node: `typeNode.createNode(uiContext,'XComponent',...)`.
  - NDK: `nodeAPI->createNode(ARKUI_NODE_XCOMPONENT)`.
  - Native-node-into-ArkTS: `NodeContent` + `ContentSlot` + `OH_ArkUI_NodeContent_AddNode`.
  - Cite: `自定义渲染 (XComponent)` §开发范式 + §开发示例; `NodeContent` doc; `ContentSlot` doc.
- **Attachment/lifecycle timing:** OnSurfaceCreated fires when the component goes on-tree **and** `autoInitialize=true` (default), or on `OH_ArkUI_XComponent_Initialize`; OnSurfaceDestroyed fires on off-tree with autoInitialize=true or on `OH_ArkUI_XComponent_Finalize`. Cite: `自定义渲染 (XComponent)` §管理Surface生命周期.
- **Native window ownership:** with the old API, the system holds a ref on the NativeWindow and decrements after OnSurfaceDestroyed. With SurfaceHolder you must call `OH_ArkUI_XComponent_GetNativeWindow(holder)` inside the Created callback. Cite: `OH_NativeXComponent_Callback` doc; guide §获取NativeWindow方式.
- **Teardown order (from official sample `UnbindNode`):** `OH_ArkUI_XComponent_UnregisterOnFrameCallback` → `OH_ArkUI_AccessibilityProvider_Dispose` → `OH_ArkUI_SurfaceHolder_RemoveSurfaceCallback` → `OH_ArkUI_SurfaceCallback_Dispose` → delete user data → `OH_ArkUI_SurfaceHolder_Dispose` → `nodeAPI->disposeNode(node)`. Cite: `自定义渲染 (XComponent)` §开发步骤 (UnbindNode).
- **Multi-surface:** multiple XComponents each get their own node/holder/callback (the frame-rate sample creates two XComponents each with its own callback). No special multi-surface API. Cite: `displaysync-xcomponent`; guide §开发范式 (two XComponent example).
- **Pixel format/opacity:** EGL sample config uses RGBA8888 (`EGL_RED/GREEN/BLUE/ALPHA_SIZE 8`). Surface opacity control via `ArkUI_XComponentSurfaceConfig_SetIsOpaque` / `OH_ArkUI_SurfaceHolder_SetSurfaceConfig` (v22) or ArkTS `setXComponentSurfaceConfig({isOpaque})` (v22). Cite: `自定义渲染 (XComponent)` EGLConst; header doc; `XComponent` component doc.
- **HDR / secure gaps:** `enableSecure` (v13) and `hdrBrightness` (v20/v24) are **NOT supported for XComponent created via ArkUI NDK interfaces**. Cite: `XComponent` component doc (属性).
- **Surface size limit:** `surfaceWidth`/`surfaceHeight` must not exceed **8192px**, else rendering anomalies. Cite: `XComponent` component doc (SurfaceRect).
- **Drawing conflict:** `lockCanvas`/`unlockCanvasAndPost` must not be used while also drawing through the NDK NativeWindow (buffer/context conflict). Cite: `XComponent` component doc (lockCanvas/unlockCanvasAndPost).
- **Single-parent rule:** a node cannot be mounted under two parents (double-mount → blank/abnormal UI). Cite: `识别和解决组件树中节点双挂问题` — `FAQ/UI框架/组件使用/识别和解决组件树中节点双挂问题/faqs-arkui-1067`.
- **UI-thread:** onFrame callback runs on UI main thread (doc). NDK node creation/event registration is via `ArkUI_NativeNodeAPI_1`, which is UI-thread bound; the docs do not contain a one-line "SurfaceHolder must be created on the UI thread" statement — **explicit statement NO DOC FOUND**, but thread-safety is implied by the UI-main-thread callback note and the NDK thread FAQ. Cite: `displaysync-xcomponent`; `NDK线程开发中的Env使用问题` — `FAQ/NDK开发/NDK开发/NDK线程开发中的Env使用问题/faqs-ndk-development-22`.
- **Density:** not provided by SurfaceHolder callbacks; `onSurfaceChanged` returns width/height in **vp** only. Density would have to be obtained separately. **NO DOC FOUND** for a density parameter in this API set.

---

## Minimal code path (per docs)

ArkTS (declarative, no `id`/`libraryname`):
```ts
XComponent({ type: XComponentType.SURFACE })
  .id('XComponentSurfaceHolder')
  .onAttach(() => {
    const node = this.getUIContext().getAttachedFrameNodeById('XComponentSurfaceHolder');
    native.bindNode('XComponentSurfaceHolder', node);   // cross-language
  })
  .onDetach(() => { native.unbindNode('XComponentSurfaceHolder'); });
```
Native:
```cpp
OH_ArkUI_GetNodeHandleFromNapiValue(env, args[1], &handle);
auto* holder = OH_ArkUI_SurfaceHolder_Create(handle);
auto* cb = OH_ArkUI_SurfaceCallback_Create();
OH_ArkUI_SurfaceHolder_SetUserData(holder, render);
OH_ArkUI_SurfaceCallback_SetSurfaceCreatedEvent(cb, OnSurfaceCreatedNative);
OH_ArkUI_SurfaceCallback_SetSurfaceChangedEvent(cb, OnSurfaceChangedNative);
OH_ArkUI_SurfaceCallback_SetSurfaceDestroyedEvent(cb, OnSurfaceDestroyedNative);
OH_ArkUI_SurfaceHolder_AddSurfaceCallback(holder, cb);
nodeAPI->addNodeEventReceiver(handle, onEvent);
nodeAPI->registerNodeEvent(handle, NODE_TOUCH_EVENT, 0, nullptr);
// Created callback:
void OnSurfaceCreatedNative(OH_ArkUI_SurfaceHolder* h){
  auto window = OH_ArkUI_XComponent_GetNativeWindow(h);  // OHNativeWindow*
  render->SetUpEGLContext(window);                        // eglCreateWindowSurface(..., (EGLNativeWindowType)window, ...)
}
```
- EGL direct use confirmed: the official sample casts the returned window to `EGLNativeWindowType` and calls `eglCreateWindowSurface`, `eglMakeCurrent`, `eglSwapBuffers`. Cite: `自定义渲染 (XComponent)` §开发示例 / EGLRender.cpp.
- Alternative native-node path uses `NodeContent` + `ContentSlot` + `OH_ArkUI_NodeContent_AddNode` (v12+). Cite: `NodeContent` doc; guide §"通过NDK接口来创建组件".

---

## Citations (doc title — documentId / header)

1. `OH_ArkUI_SurfaceHolder` — `API参考/ArkUI_方舟UI框架/C_API/结构体/OH_ArkUI_SurfaceHolder/capi-oh-nativexcomponent-native-xcomponent-oh-arkui-surfaceholder`
2. `OH_ArkUI_SurfaceCallback` — `API参考/ArkUI_方舟UI框架/C_API/结构体/OH_ArkUI_SurfaceCallback/capi-oh-nativexcomponent-native-xcomponent-oh-arkui-surfacecallback`
3. `native_interface_xcomponent.h` — `API参考/ArkUI_方舟UI框架/C_API/头文件/native_interface_xcomponent_h/capi-native-interface-xcomponent-h`
4. `OH_NativeXComponent Native XComponent` — `API参考/ArkUI_方舟UI框架/C_API/模块/OH_NativeXComponent_Native_XComponent/capi-oh-nativexcomponent-native-xcomponent`
5. `OH_NativeXComponent_Callback` — `API参考/ArkUI_方舟UI框架/C_API/结构体/OH_NativeXComponent_Callback/capi-oh-nativexcomponent-native-xcomponent-oh-nativexcomponent-callback`
6. `OH_NativeXComponent_ExpectedRateRange` — `API参考/ArkUI_方舟UI框架/C_API/结构体/OH_NativeXComponent_ExpectedRateRange/capi-oh-nativexcomponent-native-xcomponent-oh-nativexcomponent-expectedraterange`
7. `自定义渲染 (XComponent)` — `开发指南/ArkUI_方舟UI框架/UI开发_ArkTS声明式开发范式/添加组件/自定义渲染_XComponent/napi-xcomponent-guidelines`
8. `绑定基础输入事件` — `开发指南/ArkUI_方舟UI框架/UI开发_基于NDK构建UI/添加事件响应/绑定基础输入事件/ndk-bind-input-events`
9. `请求自绘制内容绘制帧率` — `开发指南/ArkGraphics_2D_方舟2D图形服务/使用可变帧率能力定制不同内容的绘制帧率/请求自绘制内容绘制帧率/displaysync-xcomponent`
10. `XComponent` — `API参考/ArkUI_方舟UI框架/ArkTS组件/渲染绘制/XComponent/ts-basic-components-xcomponent`
11. `枚举说明` (XComponentType) — `API参考/ArkUI_方舟UI框架/ArkTS组件/公共定义/枚举说明/ts-appendix-enums`
12. `ArkUI_NodeAttributeType（XComponent组件相关属性）` — `API参考/ArkUI_方舟UI框架/C_API/头文件/native_node_h/ArkUI_NodeAttributeType_XComponent组件相关属性/capi-native-node-h-nodeattributetype-xcomponent`
13. `NodeContent` — `API参考/ArkUI_方舟UI框架/ArkTS_API/UI界面/arkui/NodeContent/js-apis-arkui-nodecontent`
14. `ContentSlot` — `API参考/ArkUI_方舟UI框架/ArkTS组件/自定义占位组件/ContentSlot/ts-components-contentslot`
15. `如何解决XComponent无法触发触摸事件问题` — `FAQ/UI框架/UI界面/如何解决XComponent无法触发触摸事件问题/faqs-arkui-909`
16. `识别和解决组件树中节点双挂问题` — `FAQ/UI框架/组件使用/识别和解决组件树中节点双挂问题/faqs-arkui-1067`
17. `NDK线程开发中的Env使用问题` — `FAQ/NDK开发/NDK开发/NDK线程开发中的Env使用问题/faqs-ndk-development-22`

Key "NO DOC FOUND" items: (1) explicit formal deprecation label on `OH_NativeXComponent`; (2) any SurfaceHolder-specific input callback; (3) any SurfaceHolder vs XComponent performance/refresh-rate claim or 60 Hz cap; (4) density parameter in SurfaceHolder callbacks; (5) explicit "must create on UI thread" sentence.
