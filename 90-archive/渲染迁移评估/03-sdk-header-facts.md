> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../20-design/render/渲染链-结论.md`](../../20-design/render/渲染链-结论.md)。

# 03 - 本地 SDK 头文件实证（子 agent 原始情报）

> 来源：general 子 agent 返回，主会话未改动内容（仅加本行说明）。
> 只读扫描，未改动任何代码。

# Native SDK Surface-API Ground Truth

## (a) SDK paths + version

**SDK root:** `$HOME/devecow/deveco_tools/sdk/default/`

| Artifact | Path | Version |
|---|---|---|
| Package meta | `sdk-pkg.json` | `apiVersion=23`, `displayName="HarmonyOS 6.0.33"`, `platformVersion=6.1.0`, `releaseType=Release`, `version=6.1.0.105` |
| OpenHarmony native | `openharmony/native/oh-uni-package.json` | `apiVersion=23`, `version=6.1.0.105`, Release |
| OpenHarmony ets | `openharmony/ets/oh-uni-package.json` | `apiVersion=23`, `version=6.1.0.105` |
| HMS native | `hms/native/uni-package.json` | `apiVersion=23`, `platformVersion=6.1.0`, `version=6.1.0.105` |

**Native include root:** `.../openharmony/native/sysroot/usr/include/`

**Project declaration** (`Meowcraft/build-profile.json5:22-24`): `targetSdkVersion="6.1.0(23)"`, `compatibleSdkVersion="6.1.0(23)"`, `runtimeOS="HarmonyOS"`. No `compileSdkVersion` key present. All four `module.json5` files (`entry`, `libs/meowjre25`, `libs/meowcraftlib`, `libs/meowlwjgl3`) declare only `deviceTypes:["2in1"]` — **no API-level constraint**.

### Header existence facts (important)

| Requested header | Status |
|---|---|
| `arkui/native_interface_xcomponent.h` | **ABSENT** |
| `ace/xcomponent/native_interface_xcomponent.h` | **PRESENT** (1435 lines) — SurfaceHolder lives here |
| `ace/xcomponent/native_xcomponent_key_event.h` | PRESENT |
| `arkui/native_node.h` | PRESENT (12303 lines) |
| `arkui/native_type.h` | PRESENT (284036 B) |
| `arkui/native_interface.h` | PRESENT |
| `native_node_ffi.h` / any `*node_ffi*` | **ABSENT anywhere in SDK** |
| `native_window/external_window.h` | PRESENT |
| `OH_ArkUI_SurfaceHolder` under `arkui/` | **ABSENT** — only in `ace/xcomponent/` |
| Any HMS (`hms/native`) xcomponent/node header | ABSENT |

The SurfaceHolder API is **not** in an `arkui/` directory; it is declared in `ace/xcomponent/native_interface_xcomponent.h`.

---

## (b) Symbol inventory

### B1. `OH_ArkUI_SurfaceHolder_*` / `OH_ArkUI_SurfaceCallback_*` / `OH_ArkUI_XComponent_*`
All in `ace/xcomponent/native_interface_xcomponent.h`. All carry Clang availability `introduced=N.0.0`.

| Line | Symbol | Signature | @since / avail |
|---|---|---|---|
| 1072 | `OH_ArkUI_SurfaceHolder` | `typedef struct OH_ArkUI_SurfaceHolder OH_ArkUI_SurfaceHolder;` | 19 |
| 1081 | `OH_ArkUI_SurfaceHolder_Create` | `OH_ArkUI_SurfaceHolder* (ArkUI_NodeHandle node)` | 19 |
| 1090 | `OH_ArkUI_SurfaceHolder_Dispose` | `void (OH_ArkUI_SurfaceHolder*)` | 19 |
| 1104 | `OH_ArkUI_SurfaceHolder_SetUserData` | `int32_t (OH_ArkUI_SurfaceHolder*, void*)` | 19 |
| 1114 | `OH_ArkUI_SurfaceHolder_GetUserData` | `void* (OH_ArkUI_SurfaceHolder*)` | 19 |
| 1122 | `OH_ArkUI_SurfaceCallback` | `typedef struct OH_ArkUI_SurfaceCallback OH_ArkUI_SurfaceCallback;` (**opaque**) | 19 |
| 1130 | `OH_ArkUI_SurfaceCallback_Create` | `OH_ArkUI_SurfaceCallback* ()` | 19 |
| 1138 | `OH_ArkUI_SurfaceCallback_Dispose` | `void (OH_ArkUI_SurfaceCallback*)` | 19 |
| 1149 | `..._SetSurfaceCreatedEvent` | `void (OH_ArkUI_SurfaceCallback*, void(*onSurfaceCreated)(OH_ArkUI_SurfaceHolder*))` | 19 |
| 1162 | `..._SetSurfaceChangedEvent` | `void (OH_ArkUI_SurfaceCallback*, void(*onSurfaceChanged)(OH_ArkUI_SurfaceHolder*, uint64_t width, uint64_t height))` | 19 |
| 1175 | `..._SetSurfaceDestroyedEvent` | `void (OH_ArkUI_SurfaceCallback*, void(*onSurfaceDestroyed)(OH_ArkUI_SurfaceHolder*))` | 19 |
| 1190 | `OH_ArkUI_SurfaceHolder_AddSurfaceCallback` | `int32_t (OH_ArkUI_SurfaceHolder*, OH_ArkUI_SurfaceCallback*)` | 19 |
| 1206 | `OH_ArkUI_SurfaceHolder_RemoveSurfaceCallback` | `int32_t (OH_ArkUI_SurfaceHolder*, OH_ArkUI_SurfaceCallback*)` | 19 |
| 1216 | `OHNativeWindow` | `typedef struct NativeWindow OHNativeWindow;` | 19 |
| 1225 | `OH_ArkUI_XComponent_GetNativeWindow` | `OHNativeWindow* (OH_ArkUI_SurfaceHolder*)` | 19 |
| 1241 | `OH_ArkUI_XComponent_SetAutoInitialize` | `int32_t (ArkUI_NodeHandle, bool)` | 19 |
| 1254 | `OH_ArkUI_XComponent_Initialize` | `int32_t (ArkUI_NodeHandle)` | 19 |
| 1266 | `OH_ArkUI_XComponent_Finalize` | `int32_t (ArkUI_NodeHandle)` | 19 |
| 1278 | `OH_ArkUI_XComponent_IsInitialized` | `int32_t (ArkUI_NodeHandle, bool*)` | 19 |
| 1292 | `OH_ArkUI_XComponent_SetExpectedFrameRateRange` | `int32_t (ArkUI_NodeHandle, OH_NativeXComponent_ExpectedRateRange)` | 20 |
| 1307 | `OH_ArkUI_XComponent_RegisterOnFrameCallback` | `int32_t (ArkUI_NodeHandle, void(*)(ArkUI_NodeHandle, uint64_t timestamp, uint64_t targetTimestamp))` | 20 |
| 1321 | `OH_ArkUI_XComponent_UnregisterOnFrameCallback` | `int32_t (ArkUI_NodeHandle)` | 20 |
| 1334 | `OH_ArkUI_XComponent_SetNeedSoftKeyboard` | `int32_t (ArkUI_NodeHandle, bool)` | 20 |
| 1344 | `OH_ArkUI_AccessibilityProvider_Create` | `ArkUI_AccessibilityProvider* (ArkUI_NodeHandle)` | 20 |
| 1353 | `OH_ArkUI_AccessibilityProvider_Dispose` | `void (ArkUI_AccessibilityProvider*)` | 20 |
| 1363 | `..._SetSurfaceShowEvent` | `void (OH_ArkUI_SurfaceCallback*, void(*onSurfaceShow)(OH_ArkUI_SurfaceHolder*))` | 20 |
| 1375 | `..._SetSurfaceHideEvent` | `void (OH_ArkUI_SurfaceCallback*, void(*onSurfaceHide)(OH_ArkUI_SurfaceHolder*))` | 20 |
| 1385 | `ArkUI_XComponentSurfaceConfig` | `typedef struct ArkUI_XComponentSurfaceConfig ...;` | 22 |
| 1393 | `OH_ArkUI_XComponentSurfaceConfig_Create` | `ArkUI_XComponentSurfaceConfig* ()` | 22 |
| 1402 | `OH_ArkUI_XComponentSurfaceConfig_Dispose` | `void (ArkUI_XComponentSurfaceConfig*)` | 22 |
| 1414 | `..._SetIsOpaque` | `void (ArkUI_XComponentSurfaceConfig*, bool)` | 22 |
| 1427 | `OH_ArkUI_SurfaceHolder_SetSurfaceConfig` | `int32_t (OH_ArkUI_SurfaceHolder*, ArkUI_XComponentSurfaceConfig*)` | 22 |

**`OH_ArkUI_SurfaceCallback` fields — key correction:** it is an **opaque typedef with no public fields**. There is **no `OnSurfaceCreated`/`OnSurfaceChanged`/`OnSurfaceDestroyed`/`OnFrame` struct member** for this type. Events are registered through the `Set*Event` setter functions above. `OnFrame` is **not part of SurfaceCallback at all**; it is registered separately on the node via `OH_ArkUI_XComponent_RegisterOnFrameCallback` (line 1307, API 20) or the legacy `OH_NativeXComponent_RegisterOnFrameCallback` (line 859, API 11).

### B2. `OH_NativeXComponent_*` (legacy)
All in same header. None deprecated except two noted.

| Line | Symbol | @since | Deprecated |
|---|---|---|---|
| 413 | `GetXComponentId` | 8 | — |
| 427 | `GetXComponentSize` | 8 | — |
| 442 | `GetXComponentOffset` | 8 | — |
| 456 | `GetTouchEvent` | 8 | — |
| 470 | `GetTouchPointToolType` | 9 | — |
| 484 | `GetTouchPointTiltX` | 9 | — |
| 497 | `GetTouchPointTiltY` | 9 | — |
| 515/533/551/569 | `GetTouchPointWindowX/Y`, `DisplayX/Y` | 12 | — |
| 583 | `GetHistoricalPoints` | 10 | — |
| 597 | `GetMouseEvent` | 9 | — |
| 610 | `RegisterCallback` (touch + surface lifecycle) | 8 | — |
| 622 | `RegisterMouseEventCallback` | 9 | — |
| 646 | `GetExtraMouseEventInfo` | 20 | — |
| 662 | `GetMouseEventModifierKeyStates` | 20 | — |
| 675 | `RegisterFocusEventCallback` | 10 | — |
| 688 | `RegisterKeyEventCallback` | 10 | — |
| 701 | `RegisterBlurEventCallback` | 10 | — |
| 714–834 | `GetKeyEvent`, `GetKeyEventAction/Code/SourceType/DeviceId/Timestamp`, `GetKeyEventModifierKeyStates/NumLockState/CapsLockState/ScrollLockState` | 10 / 20 | — |
| 846 | `SetExpectedFrameRateRange` | 11 | — |
| 859 | `RegisterOnFrameCallback` | 11 | — |
| 871 | `UnregisterOnFrameCallback` | 11 | — |
| 887 | `AttachNativeRootNode` | 12 | **deprecated since 20** → `OH_ArkUI_NodeContent_AddNode` |
| 903 | `DetachNativeRootNode` | 12 | **deprecated since 20** → `OH_ArkUI_NodeContent_RemoveNode` |
| 915 | `RegisterSurfaceShowCallback` | 12 | — |
| 928 | `RegisterSurfaceHideCallback` | 12 | — |
| 944 | `RegisterUIInputEventCallback` | 12 | — (axis only) |
| 960 | `SetNeedSoftKeyboard` | 12 | — |
| 976 | `RegisterOnTouchInterceptCallback` | 12 | — |
| 992 | `GetTouchEventSourceType` | 12 | — |
| 1005 | `GetNativeXComponent(ArkUI_NodeHandle)` | 12 | — |
| 1018 | `GetNativeAccessibilityProvider` | 13 | — |
| 1033 | `RegisterKeyEventCallbackWithResult` | 14 | — |
| 1050/1064 | `OH_ArkUI_XComponent_StartImageAnalyzer` / `StopImageAnalyzer` | 18 | — |

Legacy types: `OH_NativeXComponent_Callback` (352, `@since 8`, fields `OnSurfaceCreated/OnSurfaceChanged/OnSurfaceDestroyed/DispatchTouchEvent`), `OH_NativeXComponent_MouseEvent_Callback` (369, `DispatchMouseEvent`/`DispatchHoverEvent`), `OH_NativeXComponent_KeyEvent` (383), `OH_NativeXComponent_ExpectedRateRange` (391, `{int32_t min,max,expected}`), `OH_NativeXComponent_ExtraMouseEventInfo` (633).

### B3. API-version gating

- **No `#ifdef`/`__API_VERSION__` preprocessor gating** in `native_interface_xcomponent.h`. Preprocessor conditionals are only include guards / `__cplusplus` (lines 38, 44, 54, 1431).
- Gating mechanism is Clang availability: `__attribute__((__availability__(ohos, introduced=19.0.0)))` plus `@since` tags.
- `info/application_target_sdk_version.h` defines `OH_CURRENT_API_VERSION = OH_API_VERSION_23` and `#define APIAVAILABLE(maj,min,patch) __INNER_APIAVAILABLE(...)` (macro itself `@since 22`).
- **Minimum API:** SurfaceHolder core = **19**; surface show/hide + node frame-rate + accessibility provider = **20**; `ArkUI_XComponentSurfaceConfig` / `SetSurfaceConfig` = **22**.

### B4. Declared relationship

- `OH_ArkUI_SurfaceHolder_Create(ArkUI_NodeHandle node)` — **YES, takes `ArkUI_NodeHandle`** (line 1081). `ArkUI_NodeHandle = typedef struct ArkUI_Node*` (`native_type.h:89`).
- `OH_ArkUI_XComponent_GetNativeWindow(OH_ArkUI_SurfaceHolder*)` returns `OHNativeWindow*` (line 1225) — the surface buffer comes through the SurfaceHolder, not `OH_NativeXComponent*`.
- **Nothing in the `OH_ArkUI_SurfaceHolder_*` family takes `OH_NativeXComponent*`.** All legacy `OH_NativeXComponent_*` functions take `OH_NativeXComponent*`.

---

## (c) SurfaceHolder usability at project API level

**YES — fully usable.** Project declares `compatibleSdkVersion`/`targetSdkVersion = 6.1.0(23)`. SurfaceHolder APIs require 19 (core), 20 (show/hide, node frame rate), 22 (surface config) — all ≤ 23. The SDK's own `OH_CURRENT_API_VERSION` is 23. No macro gating blocks compilation; the availability attributes only enforce `__builtin_available` runtime checks when the app's target is older than the introduced version, which is not the case here.

---

## (d) Input-event and frame-rate capability facts

### Input events — legacy XComponent (`OH_NativeXComponent*`)
| Capability | API | Line | Deprecated |
|---|---|---|---|
| Touch (down/up/move/cancel) | `RegisterCallback` + `DispatchTouchEvent`, `GetTouchEvent`, `GetHistoricalPoints` | 610/352/456/583 | No |
| Mouse + hover | `RegisterMouseEventCallback` (`DispatchMouseEvent`/`DispatchHoverEvent`), `GetMouseEvent` | 622/369/597 | No |
| Key | `RegisterKeyEventCallback` (10), `RegisterKeyEventCallbackWithResult` (14), `GetKeyEvent*` | 688/1033/714 | No |
| Focus/Blur | `RegisterFocusEventCallback`/`RegisterBlurEventCallback` | 675/701 | No |
| Axis | `RegisterUIInputEventCallback` — *"Currently, only axis events are supported"* | 944 | No |
| Touch intercept | `RegisterOnTouchInterceptCallback` | 976 | No |
| Mouse modifier keys | `GetExtraMouseEventInfo` + `GetMouseEventModifierKeyStates` | 646/662 | No |

### Input events — native node (`ArkUI_NodeHandle`, `arkui/native_node.h`)
- `registerNodeEvent(node, ArkUI_NodeEventType, targetId, userData)` — line 10776, `@since 12`
- `unregisterNodeEvent` — 10788
- `registerNodeEventReceiver(void(*)(ArkUI_NodeEvent*))` — 10803, `@since 12`; `unregisterNodeEventReceiver()` — 10810. **Note: there is no standalone `OH_ArkUI_RegisterNodeEventReceiver` symbol in this SDK** — these are function-pointer members of `ArkUI_NativeNodeAPI_1`.
- `addNodeEventReceiver(node, void(*)(ArkUI_NodeEvent*))` — 11018; `removeNodeEventReceiver` — 11030
- `ArkUI_NodeEvent` = `typedef struct ArkUI_NodeEvent ArkUI_NodeEvent;` (10135); getters `OH_ArkUI_NodeEvent_GetEventType` (10144), `GetInputEvent` (10177), `GetNodeHandle` (10167), `GetNumberValue` (10235) etc.
- `ARKUI_NODE_XCOMPONENT = 12` (native_node.h:92), `ARKUI_NODE_XCOMPONENT_TEXTURE` (110).

Input-related `ArkUI_NodeEventType` values (native_node.h):

| Line | Enum | Value | @since |
|---|---|---|---|
| 8394 | `NODE_TOUCH_EVENT` | 0 | — |
| 8455 | `NODE_ON_FOCUS` | auto | — |
| 8464 | `NODE_ON_BLUR` | auto | — |
| 8489 | `NODE_ON_CLICK` | auto | — |
| 8497 | `NODE_ON_TOUCH_INTERCEPT` | auto | — |
| 8525 | `NODE_ON_HOVER` | auto | — |
| 8534 | `NODE_ON_MOUSE` | auto | — |
| 8638 | `NODE_ON_KEY_EVENT` | 21 | 14 |
| 8652 | `NODE_ON_KEY_PRE_IME` | 22 | 14 |
| 8662 | `NODE_ON_FOCUS_AXIS` | 23 | 15 |
| 8674 | `NODE_DISPATCH_KEY_EVENT` | 24 | 15 |
| 8684 | `NODE_ON_AXIS` | 25 | 17 |
| 8694 | `NODE_ON_CLICK_EVENT` | 26 | 18 |
| 8705 | `NODE_ON_HOVER_EVENT` | 27 | 17 |
| 8735 | `NODE_ON_HOVER_MOVE` | 29 | 15 |
| 8766 | `NODE_ON_COASTING_AXIS_EVENT` | 31 | 22 |
| 8776 | `NODE_ON_CHILD_TOUCH_TEST` | 32 | — |

### Frame rate
| API | Header:line | Signature | @since |
|---|---|---|---|
| `OH_NativeXComponent_SetExpectedFrameRateRange` | xcomponent:846 | `(OH_NativeXComponent*, OH_NativeXComponent_ExpectedRateRange*)` | 11 |
| `OH_NativeXComponent_RegisterOnFrameCallback` | xcomponent:859 | `(OH_NativeXComponent*, void(*)(OH_NativeXComponent*, uint64_t, uint64_t))` | 11 |
| `OH_NativeXComponent_UnregisterOnFrameCallback` | xcomponent:871 | `(OH_NativeXComponent*)` | 11 |
| `OH_ArkUI_XComponent_SetExpectedFrameRateRange` | xcomponent:1292 | `(ArkUI_NodeHandle, OH_NativeXComponent_ExpectedRateRange)` (by value) | 20 |
| `OH_ArkUI_XComponent_RegisterOnFrameCallback` | xcomponent:1307 | `(ArkUI_NodeHandle, void(*)(ArkUI_NodeHandle, uint64_t, uint64_t))` | 20 |
| `OH_ArkUI_XComponent_UnregisterOnFrameCallback` | xcomponent:1321 | `(ArkUI_NodeHandle)` | 20 |
| `OH_NativeXComponent_ExpectedRateRange` | xcomponent:391 | `{int32_t min; int32_t max; int32_t expected;}` | 11 |
| `ArkUI_ExpectedFrameRateRange` | `arkui/native_animate.h:57` | `{uint32_t min,max,expected;}` — animation-only, **not** in `native_type.h`, **not** XComponent | 12 |
| `OH_NativeVSync_SetExpectedFrameRateRange` | `native_vsync/native_vsync.h:200` | `(OH_NativeVSync*, OH_NativeVSync_ExpectedRateRange*)` | — |

**`external_window.h` frame-rate facts:** there is **no frame-rate API**. It exposes `OHSurfaceSource` (lines 385-410: `OH_SURFACE_SOURCE_DEFAULT/UI/GAME/CAMERA/VIDEO`, `@since 12`) settable via `OH_NativeWindow_NativeWindowHandleOpt` codes `SET_SOURCE_TYPE`/`GET_SOURCE_TYPE` (lines 222-234), plus `OH_NativeWindow_SetMetadataValue`/`GetMetadataValue` (887/907). Frame-rate control for a native surface is only available through the XComponent / NativeVSync APIs above, not through `OHNativeWindow`.

---

## (e) Anything implying XComponent deprecation

- **No blanket XComponent deprecation** in any header.
- Only two functions are deprecated, both `@since 12 / @deprecated since 20`:
  - `OH_NativeXComponent_AttachNativeRootNode` (`native_interface_xcomponent.h:887`) → `@useinstead OH_ArkUI_NodeContent_AddNode` (declared `arkui/native_node.h:11342`)
  - `OH_NativeXComponent_DetachNativeRootNode` (`native_interface_xcomponent.h:903`) → `@useinstead OH_ArkUI_NodeContent_RemoveNode` (declared `arkui/native_node.h:11355`)
- The newer node-based path (`OH_ArkUI_XComponent_*` + `OH_ArkUI_SurfaceHolder_*`, API 19-22) supersedes the legacy `OH_NativeXComponent_*` pattern in practice, but the legacy input/frame-rate APIs carry **no `@deprecated` tag** in this SDK.
