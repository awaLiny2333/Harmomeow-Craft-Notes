# pojavexec 大战（自研 libpojavexec for 麒麟 + 鸿蒙 PC）

> 目标：彻底摆脱 HOML 黑箱 `libpojavexec.so`（GLFW/GL 桥），用 Amethyst Android 源码为蓝本，
> 为麒麟 + HarmonyOS PC 自研一个可编译、可裁剪、可维护的鸿蒙版桥，从而解开
> 关窗退出 / resize / 输入语义等被黑箱卡死的功能。
>
> 作战方式：三路侦查（子 agent）→ 归纳接口契约 → 可行性结论 → 编译/移植计划 → 逐里程碑实证。
> 一切发现与规划落盘本目录。
>
> ⚠️ **历史档案**（2026-09-07~08，写于改名之前）：文中 `jrelib` = 现 `meowjre`/`meowcraftlib`（`meowjre25` 为更早的历史名）、
> `libjrebridge` = 现 `libmeowjrebridge`、`libpojavexec`(自研) = 现 `libmeowcraftbridge`；
> **当前命名/状态见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)**。

## 背景锚点（已有情报速查）

- HOML `libpojavexec.so` 48KB（BIND_NOW），反编译情报见
  `../pojav桥启动.md` §5/§6（JNI_OnLoad 顺序、GLFW JNI 注册、
  pojav* C 导出、gl4es 内部、`POJAV_RENDERER` 读取、无 nglfwWindowShouldClose 等）。
- Amethyst-Android `app_pojavlauncher/src/main/jni/` 有 Android 版 pojavexec **完整源码**
  （`ref/Amethyst-Android/.../Android.mk` LOCAL_MODULE:=pojavexec；input_bridge_v3.c 等）。
- 我们的启动链：`jrelib`(libjrebridge JLI_Launch) + `libhoml_bridge.so`(surface/输入 NAPI) +
  lwjgl.jar(org.lwjgl.glfw.GLFW stub → System.loadLibrary("pojavexec"))。
- 渲染后端已定案：系统桌面 GL `libGLv4.so`（openglv4），不再需要 mobileglues/gl4es。

## 目录

| 文档 | 内容 |
|---|---|
| README.md | 本索引（作战意图/背景/结论导读） |
| 01-amethyst-source-map.md | ✅ Amethyst pojavexec 源码全景（16 编译单元/职责/Android 依赖三维矩阵/逐文件移植判定） |
| 02-interface-contract.md | ✅ 替换接口契约（A1-A5 符号分级 + lwjgl.jar native↔符号对照 + 关窗/resize/输入缺口） |
| 03-ohos-compile.md | ✅ OHOS NDK 编译可行性（工具链/毕昇 jni.h/Android→OHOS 对照表/链接蓝本/风险） |
| 04-feasibility-plan.md | ✅ **可行**结论 + 里程碑规划（已按用户决策更新：最小 drop-in / 保 homl_bridge / 仅 3.3.3） |
| 05-abi-forensics.md | ✅ homl_bridge→environ ABI 取证（二进制兼容红线/建议布局/事件 ring 情报/surface 注入缺口） |
| 06-m0-smoke.md | ✅ M0 冒烟编译通过（产物/命令/符号验证） |
| 07-render-window-handshake.md | ✅ 渲染窗口握手真相（两 so 无人写 env+0x000；drop-in 需自行补"写窗"一环；推荐 setSurface NAPI 通道） |
| 08-m1-dropin.md | ✅ **M1+M2 达成**：自研 libpojavexec.so 编进 jrelib、HOML 版下线、1.21.10 实机跑通（指纹验证） |
| 09-experience-and-ideas.md | ✅ 全经历 + 想法库（知识沉淀/排查法/so 账/M3 方案草稿/硬化路线） |
| 10-m3-close-resize-plan.md | ✅ M3 实现规格（R1 jar 解码 + R2 resize 侦查定稿） |
| 11-m3-done.md | ✅ **M3 达成**（关窗退出/resize/独立进程/防误点；待办=输入透传） |
| 12-input-forwarding-spec.md | ✅ Step A 输入透传规格（键码/鼠标/grab/摘 homl 前置） |
| 13-ime-native-spec.md | ✅ 隐形 IME 规格（含 v2 非 grab 常驻） |
| 14-input-ime-status.md | ✅ **输入+IME 实现定稿**：全链路清单 + 已知限制 + 日志指纹 |
| 15-stage-b-remove-homl-bridge.md | ✅ **Stage B 摘 homl_bridge+driver_helper**：侦查/改动/产物验证/待实机项 |
| 16-stage-c-pojav-rename.md | ✅ **Stage C pojavexec→meowcraftbridge 全链改名**：jar 常量池补丁 + 缓存令牌修复 |

## 状态
- [x] 建目录 + 读记忆锚点
- [x] 三路侦查（01/02/03）完成
- [x] 决策定稿（04：最小 drop-in、保留 homl_bridge、仅 LWJGL 3.3.3）
- [x] **M0 冒烟编译通过**（06）
- [x] ABI 取证（05）+ 渲染窗口握手查实（07）
- [x] **M1 移植 + M2 Drop-in 达成并实机验证**（08）——黑箱 pojavexec 正式自主替代
- [x] **M3（关窗退出 / 键鼠输入 / resize / 独立进程）达成**（10/11/12/14）
- [x] **Stage B 摘 homl_bridge/driver_helper**（15）、**Stage C 全链改名**（16）——黑箱清零
