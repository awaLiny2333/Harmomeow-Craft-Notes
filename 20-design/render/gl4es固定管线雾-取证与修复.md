# gl4es 固定管线雾：OptiFine「Fog: Fast」画面坏（2026-09-29，第二轮取证·**含对第一轮结论的推翻**）

> 定位：**MC 1.7.10 + OptiFine「Fog: Fast」⇒ 世界被刷成雾色/零碎面片** 的取证。
> **本页含两处自我更正**（第一轮的推断被第二轮证据推翻），请在引用前先读 §1。
> 口径见 [`../../00-current/已知限制与待解.md`](../../00-current/已知限制与待解.md) C12；应用侧原文见
> [`../launch/Forge-splash-崩溃根因与共享上下文修复.md`](../launch/Forge-splash-崩溃根因与共享上下文修复.md)。

## 1. 结论速览（含"已推翻"）

| 项 | 第一轮（**已推翻/已修正**） | 第二轮（当前） |
|---|---|---|
| ① 显示列表回放是否上传雾 uniform | **不上传**（认为 `listdraw.c` 只调裸 `gles_glDraw*`） | **上传**：`loader.h:205-211` 的 `LOAD_GLES_FPE` 在 **ES2** 下把 `gles_glDrawArrays/Elements` **直接指向 `fpe_glDrawArrays/Elements`** ⇒ `realize_glenv()` 照跑、雾 uniform **每次 draw 都上传**（另有反汇编实证，见 §5）。⇒ 我为此加的"雾变化时推送 uniform"**属冗余** |
| ② 哪一档用 RADIAL | 认为 **Fast 切到 `GL_EYE_RADIAL_NV`** | **反了**：**`Fancy` = RADIAL（0x855B）**、**`Fast` = `GL_EYE_PLANE_ABSOLUTE_NV`（0x855C）**（OF 字节码证据见 §4）⇒ 据此设计的 `MEOW_FOG_NO_NV_DISTANCE` **不是有效二分** |
| ③ 当前最佳假设 | —— | **H1：Fast 下 `fogdist` 在同一帧内来回跳（天空 pass 无条件 RADIAL / 地形 pass ABS）⇒ FPE 状态抖动 ⇒ 区块（显示列表）绘制用到的变体与当帧地形状态不匹配** ⇒ 这是目前**唯一能解释"只有 Fast 坏、Fancy/Off 都好"**的不对称 |
| ④ 另一条**独立真 bug**（在册） | —— | **H4：显示列表把非 `FOG_COLOR` 的雾操作当雾色回放**（`listrl.c:398-406` 只存一个 op + 4 float；`listdraw.c:417-419` 写死按 `GL_FOG_COLOR` 回放）⇒ 列表内录下的 `START/END/MODE/DENSITY` **永不生效**，且 `fog_val[1..3]` 可能未初始化 |
| ⑤ 用户侧可用解（不变） | Fog 改 **Fancy / Off** 即正常 | 同 |

### ★最终结论（2026-09-29 11:2x，已实机验证）

**根因定案：本栈上"平面（`GL_EYE_PLANE_ABSOLUTE_NV`）雾变体"渲染坏了 —— 表现为几何被撕成条；而径向（`GL_EYE_RADIAL_NV`）那条变体正常。**

- 排除法把 gl4es 侧逐环证清（状态 ✓ / 变体选择 ✓ / uniform 上传（GL **回读 600/600** 与期望一致）✓ / 生成 shader 的顶点源 `FogSrc = vertex.z`（眼空间）✓ 类型与赋值一致 ✓ / 片元公式与 `highp` ✓ / 列表内无雾调用 ✓）
  ⇒ ⇒ **雾的"计算链"没有问题，坏的是"平面那支变体本身"**（`MEOW_FOG_FORCE_RADIAL` 一旦打开、Fast 下带雾变体全变 RADIAL，画面即正常 —— 见下）。
- 决定性实证：开 `MEOW_FOG_FORCE_RADIAL=1` 后，`forced RADIAL` **6365 次**、`[fogshader]` 里 **Fast 下带雾变体 `dist` 全为 `0x2`（RADIAL）**、画面正常、无崩溃、无 FPE 编译失败。
- **落地方案（已默认开启）**：`fog.c` 里 `MEOW_FOG_FORCE_RADIAL`（**默认开**，`=0` 可关回忠实实现）——把 `GL_FOG_DISTANCE_MODE_NV` 的传入值在**状态更新之前**改写为 `GL_EYE_RADIAL_NV`，于是 `glstate->fog.distance` 与 ES2 转发路径（`gles_glFogfv == fpe_glFogfv`，负责 `fpe_state->fogdist`）都拿到 RADIAL。径向雾与平面雾在同等距离下视觉几乎一致 ⇒ 可逆的可用性兜底，而非关闭雾效。
- **遗留（可延后）**：① 平面变体为何坏未查到 shader/驱动层的原因（`[fogshader]`/`[fogreadback]`/`[fpeattr]` 诊断已留件内，将来可直接复用）；② agent 已用反汇编证明"雾 uniform 只在立即模式上传"这一判断**不成立**（ES2 下 `gles_glDraw* == fpe_glDraw*` ⇒ DL 每次 draw 都 realize），故我为此加的 `fpe_UploadFogUniforms()` 推送属**冗余**，可在下次动 gl4es 时删除以缩小 delta。

### ★第二轮深挖（3 个只读 agent，2026-09-29 11:3x）——真凶可能是我自己那段推送

**三方交叉结论**：

| 角度 | 结论 |
|---|---|
| **A 属性绑定路径** | **属性假设被推翻**：所有 FPE 变体创建都经 `gl4es_glLinkProgram`，它在 `gles_glLinkProgram` **之前**把 builtin 属性按名绑到固定槽（`program.c:777-783`，`hasBuiltinAttrib(converted,i)` → `glBindAttribLocation(id, ATT_*, "_gl4es_Vertex")`）⇒ `_gl4es_Vertex` 恒为 location 0 ✓。唯一不绑定的分支是 **PSA（`glProgramBinary`，`fpe_program` 的 `fpe_GetProgramPSA` 分支）**。**并发现我那个 `[fpeattr]` 探针的属性名写错了**（应为 `_gl4es_Vertex` 等，我写的是 `vertex/color/...`）⇒ location 一栏必然为空、等于没测 |
| **B shader 差异 + 驱动 + 上游史** | 两变体的**生成 shader 只差 5 处**（顶点 varying 声明 + 赋值、片元 varying 声明 + `fog_c` 表达式，外加一条含 `distance=` 的注释）⇒ 属性/uniform/精度/结构全同。上游：平面支自 `6df69d34`(2019) 起**从未被改过**，唯二的"大数值雾"修复（`143c3502`/`046e402d`）**只重写了 RADIAL 那支**。⚠️ 它同时指出一个**混淆源（M6）**：我那段"雾变化→推送 uniform"用 `GoUniformfv`（**不绑定程序**）⇒ 可能写坏别的程序；而 `MEOW_FOG_FORCE_RADIAL` 会让 `GOI(distance)` 提前 return、**减少推送次数** ⇒ **"FORCE_RADIAL 治好了"不能单独证明平面变体坏** |
| **C 日志考古** | "坏 Fast" 与 "好 Fast+强制RADIAL" 除 `dist` 外**逐字段相同**（prog 号、绘制次数分布、`[fpeattr]` 全文、renderer/`GALLIUM_THREAD`/splash/崩溃件全同）✓；地形（列表路径）两侧都是 `size=4,stride=0`（= `listdraw.c:532-534` 的列表路径形态 ✓）⇒ **属性/步长也不是病因** ✓ |

**⇒ 因此曾把"我那段推送"列为第一嫌疑**（当时的处置是"默认关闭、代码待删"；**判别实验结论见下：它无罪，代码已整段删除**）。

**判别实验的结果（2026-09-29，已全部做完）**：

- **E2（关掉我方那段 uniform 推送 + `MEOW_FOG_FORCE_RADIAL=0`，即纯上游行为，Fog: Fast）** ⇒ **仍然坏** ⇒ **我方那段推送无罪** ✓（日志可证：`[fogfix] active` 计数 = 0）。该推送已**整段删除**（含开关与日志标记）。
- **E1（新增 `MEOW_FOG_FORCE_PLANE=1`：全场景**只用一个**平面变体）** ⇒ **仍然坏，且错误渲染更稀疏** ⇒ **坏的是「平面（`FPE_FOG_DIST_PLANE_ABS`）变体自身」**（生成的 shader / 驱动编译那一层），**不是**"两变体共存/切换"（否则单变体平面就该正常）。
  ⚠️ **过程教训（已根治）**：第一次 E1 的结果**无效** —— 设备上跑的还是旧件（日志里 `forced` 一次都没出现，而 App 的距离模式设置 `0x855B`/`0x855C` **各 125 次**清晰可见）⇒ 由此新增**运行期自我报告**：每次运行首行（首次 `glFogfv`）打印
  `[meow-gl4es] build=<tag> force_radial=<0|1>` ⇒ 以后任何 `.logs` 都能一眼证明"装机件是哪一版 gl4es、哪些开关生效"。
- **最终处置（已落地；落地时随包件 `87fc358b…` / tag `2026-09-29-cleanup`，2026-09-29。当前随包值见 [`现状基线.md`](../../00-current/现状基线.md) §5 第 26 条）**：
  - 保留 **`MEOW_FOG_FORCE_RADIAL`（默认开）**：把距离模式一律按 `GL_EYE_RADIAL_NV` 处理 ⇒ 全场景只用**已验证可用**的那个变体（实机：`forced RADIAL` 6365 次、带雾变体 `dist` 全 0x2、画面正常）；
  - **移除** `MEOW_FOG_FORCE_PLANE`（E1 开关，只会产生坏画面）；
  - **整段删除**"我方雾 uniform 推送"：`fpe_UploadFogUniforms()` + `meow_fpe_fog_push()`（fpe.c）+ `MEOW_FOG_FIX` 开关 + `[fogfix] active` 日志标记 ⇒ 原地留档写明"当初为何存在 / 为何丢弃"（三条理由见 `deltas/glcore/src/gl/fog.c` 顶部）；
  - **修正 `[fpeattr]` 探针**：属性名改为按 gl4es 自己的 `builtin_attrib[]`（`_gl4es_Vertex`/`_gl4es_Color`/`_gl4es_MultiTexCoordN`/`_gl4es_FogCoord`…）经 `hasBuiltinAttrib()` 反查 —— 与 `program.c:777-783` link 前钉 location 时同源；原手写的 `"vertex"/"texcoord0"` 在生成的 shader 里不存在 ⇒ 恒 −1、那一栏等于没测；
  - 诊断开关与 `[fogshader]`/`[fogreadback]`/`[fpetrace]`/`[fpeattr]` 全部保留（将来回归/复现直接可用）；`MEOW_FOG_NO_NV_DISTANCE=1` 保留作**复现原 bug** 的反向开关。
- **仍可深挖（不在当前路上）**：平面变体为何坏 —— 候选手段（agent B 提供）：`ZINK_DEBUG=spirv` 抓两份 SPIR-V 离线 diff、把平面支改成 `vec3` varying 的等价写法（E3）、把径向支改成 `float` varying 的镜像反证（E4）、`abs()` → `max(x,-x)`（E5）、`LIBGL_NOPSA=1` 排 PSA、`GALLIUM_THREAD=0`。

**已完成的顺手修（A 发现）**：`[fpeattr]` 的属性名（原为 `"vertex"/"texcoord0"` 等**生成的 shader 里不存在**的名字 ⇒ 恒 −1）已改为经 `hasBuiltinAttrib()` 反查 gl4es 自己的名字，与 link 时钉 location 同源。

## 2. 现象二分（用户实机，2026-09-29）

| 设置 | 结果 |
|---|---|
| **Fog: Fast**（OF 默认档） | **坏**：世界被雾色覆盖 / 零碎面片 |
| **Fog: Fancy** | **正常** |
| **Fog: Off** | **正常** |
| Fast Render（本就 false）/ Chunk Loading（本就默认）/ Connected Textures 关 | **无效**（不是这些变量） |
| 纯原版 1.6.4 / 1.7.10、1.7.10+Forge（无 OF） | **正常** |

## 3. 取证工具（我们加的，全部 env 门控；均在 delta `tools/gl4es/deltas/glcore/src/gl/fog.c`）

| 开关 | 作用 | 备注 |
|---|---|---|
| `MEOW_FOG_TRACE=1` | 打印每次雾**状态变化**的实际值（`MODE/START/END/DENSITY/COLOR/COORD_SRC/DISTANCE_MODE_NV`，上限 4000）+ 前 8 次 `glFogCoord*` | ⚠️ **只覆盖"列表外"的调用**：`gl4es_glFogfv` 在 `glstate->list.compiling` 时提前 return（编译进列表的操作不会打出来）⇒ 无法回答"OF 是否在列表内设雾" |
| `MEOW_FOG_FIX=0` | 关掉我们加的"雾变化时推送 uniform" | 该推送**已被判定冗余**（§1①），保留仅为 A/B |
| `MEOW_FOG_NO_NV_DISTANCE=1` | 忽略 App 的 `GL_FOG_DISTANCE_MODE_NV` 设置 | **不是有效二分**（Fast 本来就是 ABS，见 §1②/§4）；仅对"天空 pass 的强制 RADIAL"有效 |
| `[fogfix] active …` 日志行 | 一次性标记，用来确认**装机件是不是新的** | 教训：曾让用户清空 env ⇒ 失去唯一标记 ⇒ 无法判断装机件新旧 |

## 4. OptiFine 的雾档位（**字节码证据**，修正第一轮）

反汇编工作区真实 OF jar（`stuffs/test-forge/libraries/optifine/OptiFine/1.7.10_HD_U_E7/OptiFine-1.7.10_HD_U_E7.jar`）里
**被补丁的 `EntityRenderer`**（`blt.class`，`setupFog = blt.a(IF)V`）：

```
getstatic ContextCapabilities.GL_NV_fog_distance ; ifeq → 跳过整段（我们自己宣称支持它，所以恒进入）
  if (Config.isFogFancy())  glFogi(GL_FOG_DISTANCE_MODE_NV, GL_EYE_RADIAL_NV)          // 0x855A ← 0x855B
  if (Config.isFogFast())   glFogi(GL_FOG_DISTANCE_MODE_NV, GL_EYE_PLANE_ABSOLUTE_NV)   // 0x855A ← 0x855C
（另：某个特天空/特殊 pass 无条件设 0x855B）
```

`Config.class` 里 `isFogFancy()=ofFogType==2`、`isFogFast()==1`、`isFogOff()==3`；`getFogStart()=gameSettings.ofFogStart`。

⇒ **Fast = 平面雾（ABS）**、**Fancy = 径向雾（RADIAL）**。实测 trace 里那 8000+ 次 `DISTANCE_MODE_NV` 变化 =
**Fast 下两套 pass 反复切换**（天空 RADIAL ↔ 地形 ABS），而不是"OF 一直在切某个值"。

## 5. 为什么"显示列表会上传雾 uniform"（**推翻第一轮**，含反汇编实证）

- 机制：`loader.h:205-211` 的 `LOAD_GLES_FPE(name)`：**ES2 时 `gles_##name = fpe_##name`**
  （我们运行期就是 ES2：`build_gl4es_meow.sh` 内置 `-DDEFAULT_ES=2`）⇒ `draw_renderlist` 里的
  `gles_glDrawArrays/gles_glDrawElements` **就是** `fpe_glDrawArrays/Elements` ⇒ 必然调 `realize_glenv()`。
- 反汇编（对已装机 `libgl4es.so`，sha256 `13d74d5c…`）：
  `glCallList(0xc7520) → draw_renderlist(0xd436c)`；listdraw 的 `gles_glDrawArrays` 槽取自 GOT `0x12ab98 → 0xa1604`，
  而 `0xa1604` = `cset w0,eq(mode==GL_POINTS)` + `bl 0xa1748`（= `realize_glenv`）+ 间接 draw；
  `0xa1748` 内含 `1.0/(end-start)` 与 `GoUniformfv` 序列，逐条对上 `fpe.c:1336-1338` + `1330-1340`。
- ⇒ **雾 uniform 的来源与时序没有问题**；DL 与立即模式**同源**（`drawing.c` 的立即模式同样走 `LOAD_GLES_FPE`）。
- ⇒ 我们 delta 里的 `fpe_UploadFogUniforms()`（从 `fog.c` 调用）**是冗余的**；其注释里"被 `draw_renderlist` 调用"也是**文实不符**（delta 并没有覆盖 `listdraw.c`）。**建议：回退该改动**（缩小 delta 面），只保留追踪。

## 6. 当前假设清单（按可能性）

### H1（首要）"雾变体在帧内抖动"⇒ 显示列表绘制用错变体
- Fast 下 `fogdist` 在 每帧内 **RADIAL（天空/特殊 pass）↔ ABS（地形 pass）** 之间切换 ⇒
  `glstate->fpe_state` 抖动 ⇒ 变体 key（`fpe.h:187-190` 的 `fogmode/fogdist/fogsource/fog`）随之切换；
  而**区块显示列表用的程序**是"当次 draw 时 `fpe_program()` 按**当时** `fpe_state` 选中的变体"。
  若 MC 的时序是"设好地形状态 → 画天空 → 再 glCallList 区块"（sky 的 RADIAL 状态残留），
  区块就会用**天空的变体**（texenv/雾源都不同）⇒ 画面异常。
- 为什么只有 Fast 中招：**Fancy 下 RADIAL 是恒定的**（天空与地形都设同一个）⇒ 变体不抖；Off 无雾 ⇒ 无变体。
- 离线可判别的部分：`LOAD_GLES_FPE`/`fpe_program` 调用链已全部确认（§5）；**"错配成哪个变体"必须实机判据**（§8 判据 B）。

### H2（次要，能自我一致地解释"uniform 明明写对了却没用"）
`GoUniformfv()`（`uniform.c:163-209`）**不绑定程序**：先按传入程序的缓存做 `memcmp`，相同就**直接 return（连 GL 都不碰）**，
不同则 `gles_glUniform*fv(m->id,…)` —— 只作用于**当前绑定**的程序。
若 gl4es 的记账（`gleshard->program/glprogram`）与 GPU 实际绑定不一致（blit 路径 `blit.c:277-296`、`gl4es_glUseProgram`
只更新 `glstate->glsl` 不动 `gleshard`），就会**写进别的程序**并把目标程序缓存标成"已最新"
⇒ 之后**同值永不再上传** ⇒ 该变体长期停在错值。
⇒ **正确姿势**是 gl4es 自带的 `APPLY_PROGRAM(prg,glprogram)` / `gl4es_glProgramUniform*`（`program.h:323-330`、`uniform.c:400-520`）。

### H3（只能解释"条带"，不能解释"整屏雾色"）
`fogp = hardext.highp ? "highp" : "mediump"`；**若本机缺 `GL_FRAGMENT_PRECISION_HIGH`**，则 `end/start/scale/fog_c`
全 fp16 ⇒ 在 212 附近 ulp=0.125 ⇒ 因子误差 ~0.6% 且远端呈阶梯 ⇒ 可见条带。**判别**：dump 生成的 shader 看是
`highp float end;` 还是 `mediump float end;`（FPE 的"默认 float 精度"恒为 mediump，但雾有显式限定符 ⇒ 别看 header 就下结论）。

### H4（独立真 bug，在册）
见 §1④。触发条件 = **App 在 `glNewList/glEndList` 之间设置非 COLOR 的雾状态**。
现有 `[fogtrace]` 结构上看不到列表内的调用（§3 备注）⇒ 需要新增"编译期也打印"的追踪才能判定。

### 已排除
- "`GoUniformfv` 只在立即模式上传"（§5）；- "RADIAL 是 Fast"（§4）；
- 上游落后：`ref/gl4es` HEAD = `81547d98`（`v1.1.6-91`），雾相关历史修复（`143c3502`/`046e402d`/`5c28420a`/`1f52c84f`/`460c5d16`）**都已在树内**；
- PSA（`.gl4es.psa`）路径：即便命中，`fill_program()→builtin_CheckUniform` 仍会重建 `builtin_fog`，不构成"雾 uniform 恒 0"。

## 7. 我们的 delta（现状）

| 文件 | 内容 |
|---|---|
| `deltas/glcore/src/gl/fog.c` | 雾追踪（§3 开关）、`MEOW_FOG_FORCE_RADIAL`（默认开）、build tag |
| `deltas/glcore/src/gl/fpe.c` | 恒等雾归一化（§11）+ FPE 诊断 |
| `deltas/glcore/src/gl/fpe_shader.c` | 随上游整份覆盖 + 诊断（前 2 份顶点 shader dump） |
| `deltas/glcore/src/gl/fpe.h` | 随上游整份覆盖（内容未改） |

> ⚠️ delta 是**整份覆盖**（`cp -a "$DELTA/." "$SRC_USE/"`）⇒ 覆盖到的文件在上游变动时需**手工合并**。

## 8. 下轮实机判据（**都能一次跑完**；不做这些无法收敛）

1. `MEOW_FOG_DUMP_SHADER=1`（待实现）⇒ 看生成的雾 shader：`highp` 还是 `mediump`（判 H3）、`length(FogSrc)` 还是 `abs(FogSrc)`（判变体）、`// Fog On: mode=… source=… distance=…` 那行注释（`fpe_shader.c:1357/770` 生成）。
2. `MEOW_FPE_TRACE=1`（待实现，在 `realize_glenv` 绑定之后打一行 `prog=%d dist=0x%X fog(%g,%g)`，限流）⇒
   **决定性判据**：区块 draw 前后这些行的 `dist` 是否与"刚设完的 pass"一致；若区块打的是 `dist=0x855B`（天空 RADIAL）⇒ **H1 坐实**。
3. **列表内雾调用**：加一个"`list.compiling` 也打印"的开关 ⇒ 若列表内出现 `START/END/MODE` ⇒ **H4 成立**。
4. `MEOW_FOG_FIX=0` A/B ⇒ 验证"推送冗余"（预期：画面无差别）。
5. `LIBGL_NOPSA=1` ⇒ 排除预编译档（预期：无差别）。
6. 回归：Fog: Fancy / Off 仍正常（任何改动后都要过这条）。

## 9. 产物

随包件 hash / tag / `delta-content-sha256` / 验收见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md) §5 第 26 条；
构建命令与运行期开关见 `Harmomeow-Craft-Launcher/tools/gl4es/README.md`。

## 10. 相关文件

- 上游：`ref/gl4es/src/gl/{fog.c,fpe.c,fpe_shader.c,listdraw.c,listrl.c,drawing.c,uniform.c,program.c,program.h,loader.h,shaderconv.c}`
- 我们的 delta：`tools/gl4es/deltas/glcore/src/gl/{fog.c,fpe.c,fpe.h,fpe_shader.c}`
- 同一实例的启动期崩溃（splash 的第二上下文）：[`../launch/Forge-splash-崩溃根因与共享上下文修复.md`](../launch/Forge-splash-崩溃根因与共享上下文修复.md)
- gl4es legacy 落地背景：[`legacy渲染-gl4es-落地方案.md`](legacy渲染-gl4es-落地方案.md)

## 11. 1.16.5 主菜单文字全黑（已修）

**现象**：MC 1.16.5 + gl4es（FPE）主菜单文字整片不可见；进一次世界后恢复。桌面 GL、1.7.10、1.20.6 正常。

**取证**（`MEOW_FPE_TRACE=1` + 用户导出日志）：字形绘制 = `prog=22`（256×256 图集、`at=1 ref=0.0039`、96 quad），其 FPE 状态 `fog=1`、`mode=GL_EXP`、`density=0`；`[fogshader] prog=22` 显示雾代码**确实被生成** ⇒ `fog_c≈2000`（GUI 的 eye-z）上 `FogF` 被算成 0，颜色被替换成雾色（黑）。

**为何 `density==0` 还会坏**：EXP/EXP2 在 density=0 时数学上是恒等（`FogF=1`），但本栈上 density 未如实到达 GPU ⇒ 实际按非零密度算。机制未定；**修法与根因无关**（恒等即可省略）。

**两级坑**：

1. 只在 `fpe_ReleventState()` 里归一化（`dest->fog=0`）**不够**：程序按 `fpe_state_t` 缓存（无 density 字段），而生成器读的是**原始** `glstate->fpe_state` ⇒ 雾代码照旧生成（实测 `[fogshader] .fog=1`，文字仍黑）。
2. 生成器必须消费归一化后的 `state`（与 `fpe_CustomShader(&state)` 同源）；`[fogshader]` / `[meowshader]` 诊断也改成同源重算，否则 dump 会继续误导。

**落地**：`fpe.c` 条件 `fixed && fog && !vertex_prg_enable && !fragment_prg_enable && mode∈{EXP,EXP2} && density==0`（`MEOW_FOG_NOOP=0` 回退上游）；`fpe_shader.c` 4 处回到上游 `if(fog)`。**不 bump `CACHE_VERSION`**：旧 PSA 的 fog=1 条目只会在 density>0 的查找中命中。
