> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../20-design/render/渲染链-结论.md`](../../20-design/render/渲染链-结论.md)。

# 01 - 当前渲染链测绘（子 agent 原始情报）

> 来源：explore 子 agent 返回，主会话未改动内容（仅加本行说明）。
> Root prefix（下文省略）：`<workspace>/Meowcraft`

# Meowcraft Rendering Chain — Evidence-Backed Map

## 0. Headline findings (cross-check these first)

- **The native code uses ZERO `OH_NativeXComponent_*` symbols.** XComponent is used only as an ArkTS surface-id producer. Native obtains the window via `OH_NativeWindow_CreateNativeWindowFromSurfaceId(sid)`. (`grep OH_NativeXComponent` → no files)
- **`OH_NativeVSync` / `DisplaySync` are absent from all source.** Commit `edf1556` explicitly removed "DisplaySync90, window NativeVSync90 … XComponent node 90 (401), … setXcRate, … vsync-off trials".
- **`eglSwapInterval` is forced to `0` in two places** and `pojavSwapInterval()` ignores its argument.
- **No `setXComponentSurfaceRect`, `getXComponentSurfaceId`, `setExpectedFrameRateRange`, `setWindowLayoutFullScreen`, `setPreferredOrientation`, `setWindowKeepScreenOn`, `setWindowBackgroundColor`** anywhere in `entry/src/main/ets`.
- The GL context is owned by the **JVM render thread**; there is **no native render thread** in `meowcraftbridge` (no `pthread_create`/`std::thread` there).
- `libmeowcraftbridge.so` is built by `meowcraftlib` (HAR) and **merged into the `meowjre25` HSP libs**; Java loads it as `System.loadLibrary("meowcraftbridge")` (patched from `pojavexec`).

---

## 1. Layered diagram (text)

```
┌─ ArkTS UI ─────────────────────────────────────────────────────────────────┐
│ GameAbility (2nd UIAbility, process ":game")                                │
│   GameAbility.ets:48-65  onWindowStageCreate → setWindowRectAutoSave(true)  │
│                          → loadContent('pages/GameWindow')                  │
│ GameWindow.ets                                                              │
│   GameXComponentController : XComponentController  (:49-76)                 │
│     onSurfaceCreated(surfaceId) → onSurfaceReady(sid,0,0)                   │
│     onSurfaceChanged(sid,rect)  → onSurfaceReady(sid,rect.w,rect.h)         │
│     onSurfaceDestroyed()        → onSurfaceGone()                           │
│   XComponent({type: SURFACE, controller})  (:1060-1089)                     │
│     .id('game-xc') .focusable .defaultFocus                                 │
│     .onKeyEvent .onFocus .onBlur .onMouse .onAxisEvent                      │
│   Invisible TextInput IME overlay (:1097-1115) id('ime-input')             │
│   injectAndLaunch (:903-940): parseInt(surfaceId) → setGameSurface/         │
│                              resizeGameSurface; then startJvm               │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ import('meowjre25') → 'meowcraftlib'
┌─ NAPI bridge (libmeowjrebridge.so, in meowjre25 HSP) ──────────────────────┐
│ meowjrebridge.cpp                                                           │
│   setGameSurface → dlsym("pojavSetSurfaceId")                               │
│   resizeGameSurface → dlsym("meowResizeSurface")                            │
│   meowSendKey/MouseButton/CursorPos/Scroll/Char → dlsym("critical_send_*")  │
│   meowGetGrabbing, lockCursor, unlockCursor, mouseFilterStart/Stop          │
│   launchJvm → std::thread → dlopen(libjli.so) JLI_Launch (blocks forever)   │
│   PojavLib() → dlopen("libmeowcraftbridge.so", RTLD_GLOBAL)                   │
│              + critical_set_stackqueue(1)                                   │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ dlopen + dlsym
┌─ libmeowcraftbridge.so (self-built, in meowjre25 HSP libs) ─────────────────┐
│ egl_gl.c:  pojavSetSurfaceId → OH_NativeWindow_CreateNativeWindowFromSurfaceId│
│            env->window (env+0x000); SET_SOURCE_TYPE=OH_SURFACE_SOURCE_GAME  │
│            SET_BUFFER_GEOMETRY; pojavMakeCurrent → eglMakeCurrent           │
│            pojavSwapBuffers → eglSwapBuffers; eglSwapInterval(0)            │
│ input_bridge.c: event ring (SPSC) + pump + GLFW JNI callbacks + resize upcall│
│ pojav_environ.c: 0x27228-byte process-wide env block via POJAV_ENVIRON       │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ env->window consumed by EGL; GL resolved separately
┌─ LWJGL / GLFW Java stub (lwjgl.jar, patched) ─────────────────────────────┐
│ GLFW.class: System.loadLibrary("meowcraftbridge"); internalWindowSizeChanged  │
│ GLFW$Functions.class dlsym: pojavInit/Terminate/CreateContext/MakeCurrent/  │
│   GetCurrentContext/SwapBuffers/SwapInterval/SetWindowHint/                 │
│   StartPumping/PumpEvents/StopPumping                                       │
│ GL from libGLv4.so (preloaded RTLD_GLOBAL; -Dorg.lwjgl.opengl.libname=...)  │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ eglSwapBuffers
┌─ GPU / compositor ────────────────────────────────────────────────────────┐
│ EGL window surface bound to OHNativeWindow (ArkUI surface id)              │
│ eglSwapInterval(0) → immediate present; no native VSync / DisplaySync      │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Layer table (layer / file:line / API / what it does)

### 2.1 ArkTS window & ability

| Layer | file:line | API | What it does |
|---|---|---|---|
| Ability | `entry/src/main/ets/entryability/GameAbility.ets` [52-55] | `windowStage.setWindowRectAutoSave(true)` | remembers/restores game window rect |
| Ability | `entry/src/main/ets/entryability/GameAbility.ets` [57] | `windowStage.loadContent('pages/GameWindow')` | loads render page |
| Ability cfg | `entry/src/main/module.json5` [52-62] | `"process": ":game"` | game runs in separate process |
| Ability cfg | `entry/src/main/module.json5` [20-28] | `ohos.permission.LOCK_WINDOW_CURSOR` | cursor lock permission |
| Ability cfg | `entry/src/main/module.json5` [36-39, 57-59] | `startWindowBackground` | start-window bg only (no runtime bg API) |
| Window launch | `entry/src/main/ets/common/state/WindowHolder.ets` [52-62] | `startAbility(..., {displayId:0, windowLeft/Top/Width/Height, supportWindowModes:[FLOATING,FULL_SCREEN]})` | opens 2nd UIAbility as free window; no explicit `windowMode` |
| Entry | `entry/src/main/ets/entryability/EntryAbility.ets` [60] | `setWindowRectAutoSave(true)` | main window rect autosave |

Absent (verified): `setWindowLayoutFullScreen`, `setPreferredOrientation`, `setWindowKeepScreenOn`, `setWindowBackgroundColor`, `setWindowSystemBarEnable`, `windowMode`, `setExpectedFrameRateRange`.

### 2.2 ArkTS XComponent

| Layer | file:line | API | What it does |
|---|---|---|---|
| Decl | `entry/src/main/ets/pages/GameWindow.ets` [1060-1063] | `XComponent({ type: XComponentType.SURFACE, controller: this.xController })` | options contain only `type` + `controller`; **no `id`, no `libraryname`, no `key`** |
| Attr | `GameWindow.ets` [1064-1066] | `.width('100%') .height('100%') .backgroundColor(Color.Black)` | full-bleed black surface |
| Attr | `GameWindow.ets` [1070-1072] | `.id('game-xc') .focusable(true) .defaultFocus(true)` | focus id used by IME focus controller |
| Event | `GameWindow.ets` [1073-1089] | `.onKeyEvent / .onFocus / .onBlur / .onMouse / .onAxisEvent` | all input forwarded to native (no `.onTouch`, no `.onHover`) |
| Controller | `GameWindow.ets` [49-76] | `GameXComponentController extends XComponentController` | `onSurfaceCreated(sid)`, `onSurfaceChanged(sid,rect)`, `onSurfaceDestroyed()` |
| Controller | `GameWindow.ets` [66-70] | `rect.surfaceWidth/surfaceHeight` | px size source for `frameW/frameH` |
| Handler wiring | `GameWindow.ets` [185-200] | `setSurfaceReadyHandler` / `setSurfaceGoneHandler` | caches size, injects surface, cleanup+close on gone |

`XComponentController` callbacks are used; the **modifier** `.onSurfaceCreated/.onSurfaceChanged/.onSurfaceDestroyed` are NOT used. `SurfaceRect` is the only size source.

### 2.3 Surface-id → native plumbing

| Layer | file:line | API | What it does |
|---|---|---|---|
| ArkTS | `GameWindow.ets` [916] | `const sid = parseInt(surfaceId, 10)` | string→int surface id |
| ArkTS | `GameWindow.ets` [923] | `jrelib.resizeGameSurface?.(sid, fw, fh)` | resize path (w,h>0) |
| ArkTS | `GameWindow.ets` [928] | `jrelib.setGameSurface?.(sid, fw, fh)` | first-ready path (w,h==0) |
| NAPI | `libs/meowcraftlib/src/main/cpp/meowjrebridge/meowjrebridge.cpp` [312-348] | `SetGameSurface` → `dlsym(pojavSetSurfaceId)` | NAPI `setGameSurface` |
| NAPI | `meowjrebridge.cpp` [353-387] | `ResizeGameSurface` → `dlsym(meowResizeSurface)` | NAPI `resizeGameSurface` |
| Native | `libs/meowcraftlib/src/main/cpp/meowcraftbridge/egl_gl.c` [355-398] | `pojavSetSurfaceId(sid,w,h)` | creates `OHNativeWindow`, writes `env->window` (env+0x000) |
| Native | `egl_gl.c` [373] | `OH_NativeWindow_CreateNativeWindowFromSurfaceId((uint64_t)sid,&win)` | **surface id → native window** (not `OH_NativeXComponent_GetNativeWindow`) |
| Native | `egl_gl.c` [409-427] | `meowResizeSurface(sid,w,h)` | same-sid: only marks `env->width/height`; sid change → `pojavSetSurfaceId` |

### 2.4 Input & IME (ArkTS → native)

| Layer | file:line | API | What it does |
|---|---|---|---|
| Keyboard | `GameWindow.ets` [589-653] | `handleKey` → `sendKey/sendKeyMods` | maps KeyCode→GLFW via `toGlfwKey`, self-maintained `pressed` set & mods |
| IME key | `GameWindow.ets` [662-731] | `handleImeKey` | editing/plain-text key routing while IME focused |
| Mouse | `GameWindow.ets` [756-800] | `handleMouse` | grab: rawDelta virtual cursor; !grab: absolute `sendAbsCursor` |
| Wheel | `GameWindow.ets` [802-814] | `handleAxis` → `sendScroll` | vertical/horizontal axis |
| Char | `GameWindow.ets` [627-631] | `sendChar(uni)` | printable char when !grab and no Ctrl/Alt/Super |
| IME overlay | `GameWindow.ets` [1097-1115] | `TextInput({text:this.imeText,placeholder:''})` + `.opacity(0).hitTestBehavior(HitTestMode.None).enterKeyType(EnterKeyType.Send)` | 1×1 transparent focus sink; `onChange→syncImeText`, `onSubmit`, `onKeyEvent→handleImeKey` |
| Focus | `GameWindow.ets` [401, 431, 823] | `getFocusController().requestFocus('ime-input' / 'game-xc')` | programmatic focus swap |
| NAPI | `meowjrebridge.cpp` [482-607] | `MeowSendKey/MouseButton/CursorPos/Scroll/Char/GetGrabbing` | arg parse → `critical_send_*` |
| Native | `input_bridge.c` [156-273] | `critical_set_stackqueue`, `critical_send_char/char_mods/cursor_pos/key/mouse_button/scroll` | ring producer (stackqueue=1) |
| Native pump | `input_bridge.c` [277-388] | `pojavStartPumping/pojavPumpEvents/pojavStopPumping` | drains ring → Java GLFW callbacks on render thread |
| Grab poll | `GameWindow.ets` [515-533] | `pollGrabbing` (120 ms) → `meowGetGrabbing` | native `env->grabbing` |
| Cursor lock | `meowjrebridge.cpp` [609-646] | `OH_WindowManager_LockCursor/UnlockCursor` | OS cursor lock |
| Mouse filter | `GameWindow.ets` [110-150], `input_bridge.c` [671-722] | `mouseFilterStart/Stop`, `OH_NativeWindowManager_RegisterMouseEventFilter` | non-grab display-px direct feed |

### 2.5 Native EGL/GL setup & present

| Layer | file:line | API | What it does |
|---|---|---|---|
| EGL display | `egl_gl.c` [48-67] | `eglGetDisplay(EGL_DEFAULT_DISPLAY)` + `eglInitialize` | lazy display init |
| EGL config | `egl_gl.c` [69-89] | `eglChooseConfig` (RGBA8888, depth24, WINDOW|PBUFFER) | picks config |
| EGL context | `egl_gl.c` [91-134] | `eglBindAPI(EGL_OPENGL_API)` + `eglCreateContext` 3.2; fallback `EGL_OPENGL_ES_API` 2 | desktop GL preferred |
| EGL surface | `egl_gl.c` [137-168] | `OH_NativeWindow_NativeWindowHandleOpt(SET_BUFFER_GEOMETRY)` + `eglCreateWindowSurface`; `eglSwapInterval(display,0)`; fallback `eglCreatePbufferSurface(1x1)` | window surface from `env->window` |
| Make current | `egl_gl.c` [171-193] | `eglMakeCurrent` | recreates surface if `env->window` changed |
| Resize apply | `egl_gl.c` [209-235] | `pojav_egl_apply_resize` | detach+destroy+recreate surface on render thread |
| Swap | `egl_gl.c` [308-335] | `pojavSwapBuffers` → `eglSwapBuffers`; on `EGL_BAD_SURFACE/NATIVE_WINDOW` rebuild+retry | present + self-heal |
| Swap interval | `egl_gl.c` [337-342] | `pojavSwapInterval` | **ignores arg, forces `eglSwapInterval(...,0)`** |
| Teardown | `egl_gl.c` [259-278] | `pojavTerminate` | destroy surface/context/display (JVM exit only) |
| Context handle | `egl_gl.c` [284-298] | `pojavCreateContext/pojavMakeCurrent/pojavGetCurrentContext` | stable fake GLFW window pointer |
| Window handle | `egl_gl.c` [242-247] | `pojav_current_window_handle` | `env->showingWindow` or `&g_fakeWindowAddress` |

### 2.6 Resize/DPI propagation

| Layer | file:line | API | What it does |
|---|---|---|---|
| ArkTS | `GameWindow.ets` [168-172] | `frameW/frameH`, `xcVpW/xcVpH` | px frame size + vp component size |
| ArkTS | `GameWindow.ets` [189-192] | `this.frameW=w; this.frameH=h; px2vp(w/h)` | from `onSurfaceChanged` rect |
| ArkTS | `GameWindow.ets` [120-123] | `sx=frameW/xcVpW`, `ox=(displayX-x)*sx` | px-per-vp conversion for filter origin |
| ArkTS | `GameWindow.ets` [738-754] | `sendAbsCursor` | `round((local/xcVp)*frame px)` |
| Native UI thread | `egl_gl.c` [421-424] | `env->savedWidth/Height/width/height = w/h` | only marks size, never touches EGL |
| Native render thread | `input_bridge.c` [301-325] | `internalWindowSizeChanged` upcall + `pojav_egl_apply_resize` | 50 ms throttled; Java reframe then EGL rebuild |
| Native render thread | `egl_gl.c` [312-315] | swap-time diff self-heal | applies missed resize |
| Java | `MinecraftLauncher.ets` [204-210] | `-Dglfwstub.windowWidth/Height=1280/720`, `-Dcacio.managed.screensize=1280x720` | initial MC window size |
| ArkTS | `GameWindow.ets` [972-973] | `width:1280, height:720` | argv build defaults |

---

## 3. Symbol inventory

### 3.1 `OH_NativeXComponent_*`
**NONE.** No header, no symbol, no `native_interface_xcomponent.h` anywhere in the repo. (Verified by content grep across all `*.c/*.cpp/*.h/*.hpp/*.cc` and `*.ets`.)

### 3.2 `OH_NativeWindow_*` / `OH_NativeBuffer` / `OH_NativeImage`

| Symbol | file:line | Purpose |
|---|---|---|
| `OH_NativeWindow_CreateNativeWindowFromSurfaceId` | `egl_gl.c` [373] | ArkUI surface id → `OHNativeWindow*` |
| `OH_NativeWindow_NativeWindowHandleOpt(SET_BUFFER_GEOMETRY)` | `egl_gl.c` [145], [389] | producer buffer geometry = MC-expected px |
| `OH_NativeWindow_NativeWindowHandleOpt(SET_SOURCE_TYPE, OH_SURFACE_SOURCE_GAME)` | `egl_gl.c` [383] | mark surface as game source |
| header `<native_window/external_window.h>` | `egl_gl.c` [17] | declarations |
| `OH_NativeBuffer` / `OH_NativeImage` | — | **not used** |
| transform / scaling-mode / metadata APIs | — | **not used** |

### 3.3 `OH_WindowManager_*` / window-manager NDK

| Symbol | file:line | Purpose |
|---|---|---|
| `OH_WindowManager_LockCursor` | `meowjrebridge.cpp` [624] | OS cursor lock |
| `OH_WindowManager_UnlockCursor` | `meowjrebridge.cpp` [642] | OS cursor unlock |
| `OH_NativeWindowManager_RegisterMouseEventFilter` | `input_bridge.c` [704] | window-level mouse filter |
| `OH_NativeWindowManager_UnregisterMouseEventFilter` | `input_bridge.c` [717] | remove filter |
| `OH_Input_GetMouseEventAction/DisplayX/DisplayY` | `input_bridge.c` [676, 686-687] | filter event decode |

### 3.4 EGL symbols (all in `egl_gl.c`)

`eglGetDisplay`[52], `eglInitialize`[58], `eglChooseConfig`[81,85], `eglBindAPI`[102,122], `eglCreateContext`[107,126], `eglCreateWindowSurface`[148], `eglCreatePbufferSurface`[160], `eglMakeCurrent`[178,188,222,263,326], `eglDestroySurface`[179,223,264,327], `eglDestroyContext`[268], `eglTerminate`[60,271], `eglSwapBuffers`[321,331], `eglSwapInterval`[153,340], `eglGetError` (multiple).

**`eglGetCurrentSurface`: not present.**

### 3.5 `libmeowcraftbridge.so` exported symbols (from `nm -D` on the built artifact)

`pojavInit`, `pojavTerminate`, `pojavCreateContext`, `pojavMakeCurrent`, `pojavGetCurrentContext`, `pojavSetWindowHint`, `pojavSwapBuffers`, `pojavSwapInterval`, `pojavStartPumping`, `pojavPumpEvents`, `pojavStopPumping`, `pojavSetSurfaceId`, `pojav_egl_apply_resize`, `pojav_current_window_handle`, `pojav_environ`, `meowResizeSurface`, `meowGlfwRequestClose`, `meowGetGrabbing`, `meowMouseFilterStart`, `meowMouseFilterStop`, `critical_set_stackqueue`, `critical_send_char`, `critical_send_char_mods`, `critical_send_cursor_pos`, `critical_send_key`, `critical_send_mouse_button`, `critical_send_scroll`, `critical_send_screen_size`, `JNI_OnLoad`, `JNI_OnLoadGLFW`, `Java_org_lwjgl_glfw_GLFW_*`, `Java_org_lwjgl_glfw_CallbackBridge_*`.

### 3.6 Java → native dlsym surface (from `lwjgl.jar` in `meowcraft_extras.tar.gz`)

| Java class | String | Meaning |
|---|---|---|
| `org/lwjgl/glfw/GLFW.class` | `meowcraftbridge`, `libmeowcraftbridge.so` | `System.loadLibrary` name (patched by `tools/patch_pojav_libname.py` [38-41]；**该工具已删除**) |
| `org/lwjgl/glfw/GLFW.class` | `internalWindowSizeChanged`, `glfwSetWindowShouldClose`, `nativeSetInputReady`, `nativeSetGrabbing`, `nativeClipboard` | native upcalls implemented in `input_bridge.c` |
| `org/lwjgl/glfw/GLFW$Functions.class` | `pojavInit`, `pojavTerminate`, `pojavCreateContext`, `pojavMakeCurrent`, `pojavGetCurrentContext`, `pojavSwapBuffers`, `pojavSwapInterval`, `pojavSetWindowHint`, `pojavStartPumping`, `pojavPumpEvents`, `pojavStopPumping` | dlsym targets from `libmeowcraftbridge.so` |

`pojavSetSurfaceId` / `meowResizeSurface` are **not** in the Java dlsym set — they are NAPI-only (`libmeowjrebridge` → `dlopen`).

### 3.7 Renderer backend constants

| Item | file:line | Value |
|---|---|---|
| `kRendererSo` | `meowjrebridge.cpp` [36] | `"libGLv4.so"` |
| `kRendererEnv` | `meowjrebridge.cpp` [37] | `"openglv4"` |
| `POJAV_RENDERER_LIB` | `MinecraftLauncher.ets` [82] | `'libGLv4.so'` |
| `-Dorg.lwjgl.opengl.libname` | `MinecraftLauncher.ets` [192] | `libGLv4.so` |
| pre-dlopen RTLD_GLOBAL | `meowjrebridge.cpp` [177] | GL symbols visible to pojavexec |
| `-Dglfwstub.initEgl=false` | `MinecraftLauncher.ets` [203] | EGL is owned by pojavexec, not the stub |

---

## 4. XComponent-specific dependencies (would break if XComponent were replaced)

1. **`XComponentController` subclass contract** — `GameXComponentController extends XComponentController` overriding `onSurfaceCreated/onSurfaceChanged/onSurfaceDestroyed` (`GameWindow.ets` [49-76]). Any replacement must supply an equivalent surface lifecycle with a string/int surface id and `surfaceWidth/surfaceHeight`.
2. **`XComponent({type: XComponentType.SURFACE, controller})` + `.id('game-xc')`** — the focus target for IME deactivation (`GameWindow.ets` [431], [1070-1072]). Without an XComponent node, `requestFocus('game-xc')` has no target.
3. **Generic keyboard/mouse/axis event handlers on the XComponent node** — `.onKeyEvent/.onMouse/.onAxisEvent/.onFocus/.onBlur` (`GameWindow.ets` [1073-1089]); these depend on the node being focusable and non-`libraryname`. Replacement must expose equivalent focusable input events.
4. **`surfaceId` string from `onSurfaceCreated/Changed`** — `parseInt(surfaceId,10)` (`GameWindow.ets` [916]) is the sole handle passed to `setGameSurface`; the id must be convertible to a `uint64` accepted by `OH_NativeWindow_CreateNativeWindowFromSurfaceId` (`egl_gl.c` [373]).
5. **`SurfaceRect.surfaceWidth/surfaceHeight`** — sole source of `frameW/frameH/xcVpW/xcVpH` (`GameWindow.ets` [66-70], [189-192]) used for all cursor px↔vp math.
6. **`onSurfaceDestroyed` → `requestGameWindowClose`** (`GameWindow.ets` [72-75], [196-200], [888-900]) — drives graceful MC exit.
7. **`px2vp` on the XComponent's UIContext** (`GameWindow.ets` [191-192]) — DPI normalization uses the ArkUI context of this component.
8. **`.backgroundColor(Color.Black)` on the XComponent** (`GameWindow.ets` [1066]) — the only explicit render-area background.
9. **NAPI surface API names are XComponent-flavored in docs only** — `setGameSurface`/`resizeGameSurface` (`Index.d.ts` [15-33]) document "XComponent surfaceId"; native itself is surface-id-agnostic.

## 5. Surface-API-agnostic parts (survive an XComponent replacement unchanged)

1. **`pojav_environ` ABI block** (`pojav_environ.h` [65-108], `pojav_environ.c` [64-90]) — a plain 0x27228-byte allocation; `env->window` is just a `void*`.
2. **EGL/GL layer** (`egl_gl.c` entirely) — operates on `env->window` (`OHNativeWindow*`); it never sees an XComponent. Any producer that yields an `OHNativeWindow*` works.
3. **`OH_NativeWindow_*` usage** — `CreateNativeWindowFromSurfaceId`/`SET_BUFFER_GEOMETRY`/`SET_SOURCE_TYPE` are surface APIs, not XComponent APIs.
4. **Event ring + pump + GLFW JNI surface** (`input_bridge.c` [136-415]) — pure ring/JNI; independent of how the window was obtained.
5. **Input senders / mouse filter / cursor lock** (`input_bridge.c` [156-273], [671-722]; `meowjrebridge.cpp` [482-698]) — GLFW/NAPI semantics only.
6. **JVM launch + renderer env setup** (`meowjrebridge.cpp` [124-281]) — only needs `filesDir`/argv, not a surface.
7. **LWJGL/GLFW Java stub `pojav*` dlsym contract** — surface-agnostic; `pojavMakeCurrent` reads `env->window` at call time.
8. **Build/packaging graph** (`meowcraftlib` → `meowjre25` HSP merge) — unchanged.

---

## 6. Build / packaging evidence

| Item | file:line | Detail |
|---|---|---|
| meowjrebridge target | `libs/meowcraftlib/src/main/cpp/CMakeLists.txt` [5-13] | `add_library(meowjrebridge SHARED meowjrebridge/meowjrebridge.cpp)`; links `libhilog_ndk.z.so libace_napi.z.so libnative_window_manager.so` |
| meowcraftbridge target | `.../CMakeLists.txt` [19-28] | `add_library(meowcraftbridge SHARED egl_gl.c input_bridge.c pojav_environ.c)`; links `libhilog_ndk.z.so libnative_window.so libnative_window_manager.so libohinput.so libEGL.so` |
| meowassets target | `entry/src/main/cpp/CMakeLists.txt` [11-24] | links `libace_napi.z.so libhilog_ndk.z.so librawfile.z.so libz.so` (no window/EGL/xcomponent) |
| actual `DT_NEEDED` (pojavexec) | built `.so` | `libdeviceinfo_ndk.z.so libhilog_ndk.z.so libnative_window.so libnative_window_manager.so libohinput.so libEGL.so`; `SONAME libmeowcraftbridge.so` |
| actual `DT_NEEDED` (jrebridge) | built `.so` | `libdeviceinfo_ndk.z.so libhilog_ndk.z.so libace_napi.z.so libnative_window_manager.so libc++_shared.so`; `SONAME libmeowjrebridge.so` |
| HAR deps | `libs/meowjre25/oh-package.json5` [8-11] | `meowcraftlib`, `meowlwjgl3` |
| HSP re-export | `libs/meowjre25/Index.ets` [6] | `export * from 'meowcraftlib';` |
| NAPI exports | `libs/meowcraftlib/Index.ets` [8-26] | bridge exports incl. `setGameSurface`, `resizeGameSurface`, `meowSend*`, `lockCursor` |
| HSP type | `libs/meowjre25/src/main/module.json5` [4-5] | `"type": "shared", "libIsolation": true` |
| libs merge output | `libs/meowjre25/build/default/cache/default/shared_har/libs/arm64-v8a/` | contains `libmeowcraftbridge.so`, `libmeowjrebridge.so`, `libjli.so`, `libjvm.so`, `liblwjgl*.so`, `libopenal.so`, `libjnidispatch.so`, `libfreetype.so`, `libc++_shared.so` |
| LWJGL component HAR | `libs/meowlwjgl3/libs/arm64-v8a/` | `liblwjgl.so`, `liblwjgl_opengl.so`, `liblwjgl_stb.so`, `libopenal.so`, `libjnidispatch.so`, `libfreetype.so` |
| runtime lib path | `GameWindow.ets` [966-967] | `${ctx.bundleCodeDir}/meowjre25/libs/arm64` (nativeLibsDir + craftLibsDir) |
| JVM launch | `JvmLauncher.ets` [50-55] | `import('meowjre25')` → `launchJvm(filesDir, argv, filesDir/meow-jres/meow_jre25, bundleCodeDir/meowjre25/libs/arm64)` |
| lib rename patch | `tools/patch_pojav_libname.py` [38-41]（**该工具已删除**） | `"pojavexec"→"meowcraftbridge"`, `"libpojavexec.so"→"libmeowcraftbridge.so"` in `GLFW.class` |

---

## 7. Present / VSync / threading (precise)

- **Swap site:** `pojavSwapBuffers` → `eglSwapBuffers` (`egl_gl.c` [321], retry [331]). Called from Java `GLFW$Functions.pojavSwapBuffers` on the render thread.
- **Swap interval:** `eglSwapInterval(g_egl.display, 0)` at `egl_make_surface` [153] and `pojavSwapInterval` [340]; the latter discards MC's requested value (`(void)interval;` [338]).
- **VSync / DisplaySync:** none. `OH_NativeVSync` and `DisplaySync` appear only in git commit `edf1556` as removed experiments.
- **Thread owning GL context:** created lazily on first `pojav*` call, i.e. the **JVM render thread** (`egl_gl.c` header comment [6-8]: "all calls are expected on the JVM render thread"). No `pthread_create`/`std::thread` in `meowcraftbridge`.
- **Pump thread:** `pojavPumpEvents` runs on the render thread (comment `input_bridge.c` [301-303]) and performs both the Java `internalWindowSizeChanged` upcall and `pojav_egl_apply_resize`.
- **Cross-thread surface updates:** UI thread writes `env->width/height` via `meowResizeSurface` [421-424]; render thread reads and applies via diff [306-325] and swap self-heal [312-315]. Event ring uses `atomic_size_t eventCounter` (`pojav_environ.h` [71]) with acquire/release (`input_bridge.c` [151], [282], [385]).
- **JVM launch thread:** `meowjrebridge.cpp` [124-281] detached `std::thread`; plus two detached pipe-reader threads [226-227]. None own GL.
- **Surface destroy teardown:** `onSurfaceDestroyed` → `cleanupInput` + `requestCloseGame` → `meowGlfwRequestClose` (`input_bridge.c` [96-132]); **no EGL surface destroy on XComponent destroy** — EGL teardown only in `pojavTerminate` (`egl_gl.c` [259-278]).

---

## 8. Unknowns / not found

- **Window background color at runtime:** no `setWindowBackgroundColor`; only start-window resource `#FFFFFF` (`entry/src/main/resources/base/element/color.json`) and XComponent `.backgroundColor(Color.Black)`.
- **Orientation:** no `setPreferredOrientation` and no `orientation` field in `module.json5`; device is `2in1` only.
- **Frame-rate APIs:** none in source (removed by `edf1556`).
- **`setXComponentSurfaceRect` / `getXComponentSurfaceId`:** not called; size comes only from `SurfaceRect`.
- **Surface transform / scaling-mode / metadata:** no `OH_NativeWindow` transform or metadata calls found.
- **`eglGetCurrentSurface`:** not used anywhere.
- **GL function resolution internals inside `libGLv4.so`/LWJGL:** beyond `-Dorg.lwjgl.opengl.libname=libGLv4.so` and RTLD_GLOBAL pre-dlopen, the exact LWJGL proc-address path is in the prebuilt `lwjgl.jar` (not source in this repo) — "unknown" at source level.
