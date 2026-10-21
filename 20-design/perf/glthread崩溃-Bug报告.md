# Bug 报告：`GALLIUM_THREAD=1`（Mesa glthread）× Zink × 华为 Maleoon 驱动 → 访问未映射内存随机 SIGSEGV

> 日期：2026-09-13 ｜ 状态：**可直接提交**（华为 GPU/驱动 或 Mesa / Zink 上游）
> 证据与实现：[`性能实验台与glthread-结论.md`](性能实验台与glthread-结论.md)、[`../../00-current/运行时环境变量.md`](../../00-current/运行时环境变量.md)（`MEOW_BT`）
> 复现载体：Harmomeow Craft Launcher（HarmonyOS 上跑 Minecraft Java 的启动器，未改 MC 本体）
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 16 条](../../00-current/现状基线.md)。

## 摘要（中文）

在 HarmonyOS 2in1（MateBook Fold / Kirin X90 / Maleoon 916 / Mesa 25.0.1 Zink-over-Vulkan）上，
开启 Mesa 的 threaded context（`GALLIUM_THREAD=1`）后，进程**随机（约 50%）**在加载屏或游玩中
**SIGSEGV（SEGV_ACCERR）** 崩于访问**未映射内存 / guard 页**。崩溃指令位置不稳定——开 JIT 时落在
**JVM JIT 代码缓存**，`-Xint` 时落在 **`libgallium-25.0.1.so` 调用 `memcpy` 读野指针**——说明
**JIT 不是崩因**，根因是 **`libgallium`/Zink 在 glthread 下访问已释放/未映射内存**（内存安全 bug）。
关闭 `GALLIUM_THREAD`（=0）则从不崩。应用侧（桥/EGL 生命周期/JVM 参数/着色器缓存）已逐条排除。

---

# Bug report (English)

## Summary

With Mesa's threaded context enabled (`GALLIUM_THREAD=1`), a Vulkan-backed OpenGL app (Minecraft Java
via the Harmomeow Craft launcher) **intermittently (~50%) crashes with SIGSEGV (SEGV_ACCERR)** while accessing
**unmapped memory / guard pages**, during shader/pipeline compilation (loading screen) or mid-game.
The faulting instruction is **not stable** — it lands in JVM JIT code when the JIT is on, and in
**`libgallium-25.0.1.so` → `memcpy`** when running `-Xint` — so **JIT is not the cause**. Root cause is a
**memory-safety bug (use-after-free / wild pointer) inside `libgallium`/Zink under glthread**.
With `GALLIUM_THREAD=0` the app never crashes.

## Environment

| | |
|---|---|
| Device | HUAWEI MateBook Fold (2-in-1), Kirin X90, **Maleoon 916** GPU |
| OS | HarmonyOS **7.0.0.105** (`apiversion=26`) |
| GL stack | system `libGLv4.so` → `libEGL_mesa.so` → **`libgallium-25.0.1.so`** (**Mesa 25.0.1**, Zink/kopper over Vulkan) |
| Vulkan | `libvulkan.so`; ICD `/vendor/lib64/passthrough/vulkan.hvgr_v210.so` (reports Vulkan 1.2) |
| App runtime | bundled **OpenJDK 26.0.2.1** (self-built `libjvm`), **LWJGL 3.4.3** |
| Content | Minecraft **26.2** + Fabric + Sodium (also reproduced on vanilla). **MC-version-dependent for the fatal crash**: on 1.18.2 / 1.20.6 / 1.21.10 only *benign* faults appear (a constant 4 KB `---p` page, likely the HotSpot safepoint polling page; recovered, process survives), while the **fatal, variable-address fault (`libgallium`→`memcpy` on unmapped memory) is observed on 26.x only** |
| Renderer | EGL window surface created by the app; `eglSwapInterval(0)`; `vblank_mode=0` |

## Steps to reproduce

1. Launch the app with env **`GALLIUM_THREAD=1`** (and keep the rest default: `vblank_mode=0`, `GALLIUM_THREAD` otherwise `0`).
2. Start Minecraft (26.2 + Fabric + Sodium or vanilla).
3. Observe: crash within the loading screen or shortly after entering a world, **~50% of runs** (observed 3/8, then 1/2, 1/2, 1/3 across sessions; 4 consecutive clean runs also seen).
   - `GALLIUM_THREAD=0` → 0 crashes over many runs.

## Expected vs Actual

- **Expected**: glthread offloads GL calls to a driver thread; app stays stable (as on desktop Mesa).
- **Actual**: random SIGSEGV `SEGV_ACCERR` on **unmapped / PROT_NONE pages**.

## Evidence

### A) With JIT (default) — fault pc in **JVM JIT code cache**

```
W  [nodict]<HM_GPU> #  Create pipeline cache          ← Huawei driver
W  [nodict]<HM_GPU> #  Get pipeline cache data
W  signal_chain_handler ... signal: 11                ← SIGSEGV
I  DFX_SignalHandler :: signo(11), si_code(2), pid(...), tid(...)   ← si_code 2 = SEGV_ACCERR
```
Our in-process dumper (`MEOW_BT=1`) captured, in one run, **multiple distinct faults**:

```
FAULT#1 sig=11 code=2 addr=0x5a07cbd000 pc=0x5b8c8a2860
FAULT#2 sig=11 code=2 addr=0x5a07cbd000 pc=0x5b8c8a2860
FAULT#3 sig=11 code=2 addr=0x5a07cbd000 pc=0x5b8549dd70
FAULT#4 sig=11 code=2 addr=0x5a32f46000 pc=0x5980977dec
  addr->=0x5a07cbd000  <anon>  [---p size=0x1000]        ← 4 KB PROT_NONE guard page
  pc  ->=0x5b8c8a2860  <anon-exec>+0xe4860 [rwxp size=0x270000]   ← JVM code cache
  addr->=0x5a32f46000  [anon:guard:19595]                ← thread guard page
  pc  ->=0x5980977dec  ld-musl-aarch64.so.1 (memcpy)
  lr  ->=0x5bbce26cc4  libgallium-25.0.1.so
```
anon-exec regions (rwxp) totalled **~23 MB across two clusters** (blocks of 64 KB–7 MB).

### B) `-Xint` control — JIT code cache disappears, **still crashes**

```
extra JVM args: -Xint
addr=0x5ba641d000  <UNMAPPED>
pc  ->=0x5980977dec  ld-musl-aarch64.so.1            (memcpy)
lr  ->=0x5ba3e26cc4  libgallium-25.0.1.so
x0=0x70d3da3000 (dst)  x1=0x5ba641cfc0 (src)  x2=0x370 (880 bytes)
```
- rwxp anon-exec shrank from **~23 MB / 2 clusters → a single 2.5 MB block** ⇒ the earlier `<anon-exec>` pcs were indeed JVM JIT code (not libffi), yet the crash **persisted** elsewhere.
- The faulting frame is a **`memcpy` called from `libgallium`**: it reads `src = 0x5ba641cfc0` and faults at `src + 0x40` (**unmapped page** `0x5ba641d000`).
  ⇒ **`libgallium` passed a wild/unmapped pointer to `memcpy`**.

### Common signature

- Fault addresses are always **unmapped pages or guard/PROT_NONE pages** (e.g. `[---p] 0x1000`, `[anon:guard:<tid>]`), **not** ordinary buffer contents.
- Multiple faults at the same bad address from different code paths ⇒ **process-wide memory corruption**, not a single bad call site.

### C) Fatal frame symbolized (module bases + Mesa `.gnu_debugdata`)

`MEOW_BT` logs key module bases, so the fatal (variable-address) fault resolves:

```
thr=Render thread
addr=0x5b82577000  pc=ld-musl memcpy   lr=libgallium-25.0.1.so (base 0x5b99200000) + 0xE26CC4
x0(dst)=0x70d2c3e000   x1(src)=0x5b82576fc0   x2(n)=0x4DF0
```
⇒ `memcpy(dst, src=0x5b82576fc0, n=19952)`; the fault is at `src + 0x40` (page boundary) — the **source pointer
is freed/unmapped** (the destination mapping is fine).

`libgallium-25.0.1.so` is stripped, but it **keeps a `.gnu_debugdata` section** (a compressed mini-ELF holding a
full `.symtab`, ~18.8k symbols). Extracting it yields authoritative names:

```
libgallium+0xE26C44  zink_buffer_subdata   ← the crashing routine (Zink pipe_context::buffer_subdata)
libgallium+0xE261CC  zink_buffer_map       (called first to obtain dst)
libgallium+0xE2515C  transfer_unmap        (called after the memcpy)
libgallium+0xE26BC0  zink_buffer_unmap
```

`zink_buffer_subdata` disassembles as:

```
e26cb0  bl   zink_buffer_map     ; dst = mapped GPU buffer (host-visible BO, else u_upload_alloc staging)
e26cb8  mov  w2, w21             ; n   = argument (w4) = 0x4DF0
e26cbc  mov  x1, x20             ; src = argument (x5) = 0x5b82576fc0
e26cc0  bl   memcpy@plt          ; <-- fault (read from a freed/unmapped caller pointer)
e26cd8  bl   transfer_unmap      ; flush + release
```

**Interpretation**: MC (through Mesa's state tracker) issued a `glBufferSubData`-equivalent with a **source
pointer that had already been freed/unmapped** (~20 KB transfer). It is a caller-side use-after-free that only
manifests with glthread's asynchronous lifetime management. (The exact caller is reached via the
`pipe_context` function-pointer table, so it cannot be identified statically.)

### D) Full call chain (frame-pointer walk, also symbolized)

A bounded frame-pointer walk from the faulting context gives the caller chain (all names from `.gnu_debugdata`):

```
bt#0  tc_texture_subdata+0x3B0     ← Mesa glthread threaded-context wrapper   <-- the caller
bt#1  st_TexSubImage+0x40C         (state tracker)
bt#2  texture_sub_image+0x1D4
bt#3  texsubimage_err+0x1C8
bt#4  _mesa_TexSubImage2D+0x84     (GL entry: glTexSubImage2D)
```

⇒ **`glTexSubImage2D` (MC/LWJGL, Render thread) → `_mesa_TexSubImage2D` → `st_TexSubImage` →
`tc_texture_subdata` (glthread) → `zink_buffer_subdata` → `memcpy(dst, <freed src>, 0x5DF0)`** — i.e. a
**texture upload** (~24 KB) whose source pointer was freed before the threaded-context path consumed it.
This matches "crashes mostly late in loading" (texture-atlas upload peak).

## Analysis & exclusions (all A/B on-device)

| Hypothesis | Experiment | Result |
|---|---|---|
| JVM JIT | `-Xint` | ❌ still crashes (fault moves to `libgallium`→`memcpy`) |
| JRE/JVM version | swap the bundled JRE to a different self-built OpenJDK build (26 ↔ 25; identical 29-library set) | ❌ **both crash** — JRE family excluded |
| C2 | `-XX:TieredStopAtLevel=1` | ❌ |
| Implicit null checks | `-XX:+UnlockDiagnosticVMOptions -XX:-ImplicitNullChecks` | ❌ |
| SVE / oversubscription | `-XX:UseSVE=0 -XX:ActiveProcessorCount=4` | ❌ |
| Mesa changes signal state at load | compare `sigaction`/`sigaltstack`/`pthread_sigmask` pre/post pre-dlopen | ❌ identical |
| App's own EGL surface lifecycle | add `glFinish` drain before surface destroy/recreate (Mesa contract) | ❌ still crashes |
| Zink descriptor churn | `ZINK_DESCRIPTORS=lazy` | ❌ |
| Disk shader/pipeline cache | `MESA_SHADER_CACHE_DISABLE=true` / `MESA_SHADER_CACHE_DIR=<writable>` / `SHOW_STATS=1` | ❌ still ~50% flaky; **disabling the cache does not stop the driver's `Get pipeline cache data`** |
| CPU scheduling | thread QoS (`QOS_USER_INTERACTIVE`) + `sched_setaffinity` to big cores | applied, no effect (not the crash factor) |
| GL extension-gated paths | `MESA_EXTENSION_OVERRIDE` verified working (ext count 211→210, extension flips to `no`) | hiding `GL_ARB_buffer_storage` makes **MC abort at renderer init** (`Failed to map buffer`; unrelated to glthread); hiding `GL_ARB_direct_state_access` (MC runs via its emulated path) → **glthread crash persists** ⇒ neither path is the trigger |

## Suspected component

`libgallium`/Zink's **glthread (`GALLIUM_THREAD=1`) path, interacting with the Huawei Vulkan driver's
pipeline-cache code** (`<HM_GPU> Create pipeline cache` / `Get pipeline cache data`), yields **accesses to
unmapped/freed memory**. Since `-Xint` isolates it to `libgallium`→`memcpy`, the corruption originates in
the Mesa/Zink/driver stack, not in the app.

## Requested

Fix the memory-safety issue in **Mesa glthread × Zink** and/or the **Huawei Vulkan driver's pipeline-cache
path** (Maleoon 916), so `GALLIUM_THREAD=1` is stable.

## Workaround

An **application-side workaround is implemented and shipped** (2026-09-14), pending an upstream fix:

- The launcher loads a small **GL guard** library as LWJGL's OpenGL library
  (`-Dorg.lwjgl.opengl.libname`). It forwards every GL name to the real
  `libGLv4.so`, except `glTexSubImage2D`: after the real call it performs a
  `glFlush()` (default) — or `glFinish()` — so the threaded-context queue
  consumes the caller's pointer while it is still valid.
- Enabled by default (advanced option "threaded render", modern render path only;
  the gl4es/legacy path is unaffected). Verified on device: 0 fatal crashes over
  many runs, plus a large FPS gain.
- Alternatively, keep `GALLIUM_THREAD=0` (opt out via the same option).

This is a *compensation* for the Mesa-side defect; the correct place to fix it is
`tc_texture_subdata` (copy the client data synchronously). See
[`glthread-GL-guard-方案.md`](glthread-GL-guard-方案.md).

## Attachments / references

- Capture tool: in-process `SIGSEGV` dumper (`MEOW_BT=1`) — prints ucontext registers + `/proc/self/maps`-resolved
  `pc/lr/addr`, then chains to the JVM handler. Source: `libs/meowcraftlib/src/main/cpp/meowcraftbridge/meowbt.c`.
- Full logs available on request (hilog exports with `[meowbt]` lines).
- Related: [`性能实验台与glthread-结论.md`](性能实验台与glthread-结论.md)（§2 #2.1/#2.2）、[`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) A7。
