# LWJGL3 并代可行性：两代 → 单代（只留 3.4.3，丢掉 3.3.3）

> 已归档（2026-10-02；两代→单代的收敛依据已并入 [`../20-design/lwjgl/LWJGL3世代管理-方案.md`](../20-design/lwjgl/LWJGL3世代管理-方案.md)）。
> 2026-09-14。目标 = 随包**只留较新那一代**（3.4.3），让整个启动器的现代 LWJGL3 只有一份。
> **结论：可行，但不能"直接丢"** —— 必须在我们自己的 overlay 里补回 **5 个成员**。
> 落地进度见 §5。
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [`现状基线.md §5 第 9 条`](../00-current/现状基线.md)。

## 0. 背景（为什么要并）

- 原设计：现代**两代并存**（`3.3.3` 服务 MC 1.17–1.21.x；`3.4.3` 服务 ≥1.22 / 26.x），
  按版本 json 声明的 `org.lwjgl:lwjgl:<ver>` 选代（`MinecraftLauncher.lwjglGeneration`）。
- 并代收益：少 1 个 overlay 目录 + 1 个 jar（tar 里）+ 3 个 native（`_333`）+ 1 行世代表。
- **先验疑问**：[`../20-design/lwjgl/LWJGL3世代管理-方案.md`](../20-design/lwjgl/LWJGL3世代管理-方案.md) §0 只写了一句"跨代（3.3→3.4）不兼容"，**无证据**。
  本档把它查实。

## 1. 判据（零构建）：成员级 + 继承感知的兼容校验

工具：`Harmomeow-Craft-Launcher/tools/lwjgl/mc_lwjgl_compat_check.py`

做法：读 MC 客户端 jar 里**每一个** `org/lwjgl` 引用（解析常量池的
`Methodref/Fieldref/InterfaceMethodref` → `owner.name:desc`），再在 LWJGL jar 里**沿父类/接口链**
解析该成员是否被声明。

- **校验**：对 MC 各自声明的世代跑（1.16.5/1.19.4/1.21.10 → 3.3.3）→ **0 缺失**（方法可靠）。
- **对照 3.4.3** → **缺失类 0 个、缺失成员恰好 5 个**。

> 只看"文件级/类级"会误判：`limit()/free()/position()` 之类是**继承**来的，必须走父类链
> （第一版校验器就栽在这，用 3.3.3 做对照才发现）。

## 2. 缺口（= 需要补的 shim 面）

| 缺失成员（3.4.x 删/改） | 使用它的 MC 版本 | 性质 |
|---|---|---|
| `glfw.GLFWImage.mallocStack(int, MemoryStack)` | 1.13.2–1.18.2 | 3.4 生成器删掉的便利静态（实现是一行 `malloc(...)`） |
| `stb.STBIIOCallbacks.mallocStack(MemoryStack)` | 1.13.2–1.18.2 | 同上（stb_image 内存加载） |
| `stb.STBVorbisInfo.mallocStack(MemoryStack)` | 1.14.4–1.19.4 | 同上（OGG/Vorbis 音频） |
| `stb.STBImageResize.nstbir_resize_uint8(JIIIJIIII)I` | **1.13.2–1.21.11（全部现代版）** | resize→**resize2** 换名；新 `nstbir_resize_uint8_linear(...)J` **形参同形** |
| `util.tinyfd.TinyFileDialogs.tinyfd_messageBox(CS,CS,CS,CS,Z)Z` | 1.16.5–1.21.11 | 3.4 把末参 `Z`→`I`、返回也从 `Z`→`I` |

其它 3.4.0 的破坏性项（`mallocStack/callocStack` 全族、`NonnullDefault` 注解类被删、
`MemoryUtil`→`MemoryUtilFFM`、Unsafe accessor 改包级、stb `stbir_*` 全族换名）——
**经全量核对，除上表 5 项外 MC 都不用**。

## 3. 修法（全在我们 overlay 里；natives 零改动）

jar 本来就是「官方模块 + 自研 overlay 覆盖同名类」→ 在 `tools/lwjgl/deltas/overlay-3.4.3/`
新增 5 个类（与 `GLCapabilities` 同机制）：

- **3 个 struct**（`glfw/GLFWImage`、`stb/STBIIOCallbacks`、`stb/STBVorbisInfo`）：
  补回 `mallocStack()/callocStack()` **全 8 个静态**（委托现存的 `malloc/calloc`，即 3.3.x 原实现）。
- **`stb/STBImageResize`**：补回 `nstbir_resize_uint8(...)I`（委托新 `nstbir_resize_uint8_linear(...)J`；
  结果 `!=0L → 1/0`）+ 公开 `stbir_resize_uint8(ByteBuffer…)Z`。旧 `num_channels`（1/2/3/4）
  映射为 resize2 的**无 alpha** layout（`STBIR_1CHANNEL/2CHANNEL/RGB/4CHANNEL`）——对应 v1 的
  `STBIR_ALPHA_CHANNEL_NONE`+线性色彩空间+默认滤波。
- **`util/tinyfd/TinyFileDialogs`**：补回 boolean 重载（CharSequence 版 + ByteBuffer 版），
  委托新的 `(…,I)I`（`aDefaultButton?1:0` 进、`!=0` 出）——与 3.3.x 生成代码同语义。

## 4. 决定难度的未知点 —— 已清零

唯一真未知 = "MC 到底调不调被删的 API"。**已用全量校验锁死**（§2 的 5 项）。剩下的只有
T2 的语义保真（旧 `stbir_resize_uint8` 的通道语义）与**实机回归**。

## 5. 落地（进度）

- [x] 5 个 shim 写入 `tools/lwjgl/deltas/overlay-3.4.3/`。
- [x] 选代收敛：`LWJGL_GEN_TABLE` 单行、`LWJGL_GEN_JARS` 单 jar、删 `LWJGL_GEN_333`、升 `EXTRAS_VERSION`。
- [x] 删 3.3.3 资产：`deltas/overlay-3.3.3/`、3 个 `_333.so` + manifest 行（flat 目录 **14→11 so**）。
- [x] `pack_extras.py`：改为**丢弃 base tar 里所有 `lwjgl*.jar`**（防退役世代残留）。
- [x] 模块改名 `meowlwjgl3` → **`meowlwjgls`**（`build-profile.json5`、`libs/meowlwjgls/oh-package.json5`、
      `meowjre` 的 `oh-package.json5`+lock+`oh_modules`、`install_natives.sh`、文档）。
- [x] **jar 重建**（overlay 改了 → 重跑 `build_lwjgl_jar.sh … 3.4.3` + javac；本机无 JVM，由用户跑）→ 新 jar `b9b306a0…`（6185 类，与旧 3.4.3 同 ⇒ 只加方法不加类）。
- [x] 重打 `meowcraft_extras.tar.gz`（只含 `lwjgl-3.4.3.jar`）+ 构建部署（tar `f8437074…`）。
- [x] **实机回归**：1.13.2 / 1.14.4 / 1.16.5 / 1.17.1 / 1.18.2 / 1.19.4 / 1.21.10 / 1.21.11 + 26.x —— 用户确认"都能跑"。
- [x] 4 个只读审查 agent 全链 review（并代/shim、glthread 运行时、逐版本 UI、启动链路回归）；发现的问题已修（见 §8）。

## 6. 副产（可复用工具）

`stuffs/research/`：`mc_lwjgl_compat_check.py`（已收入 `tools/lwjgl/`）、`jar_class_dump.py`、
`mc_lwjgl_ref_scan.py`、`mc_lwjgl_api_scan.py`。

**方法论**：*改代际 / 换依赖前，先做成员级全量核对* —— 比"跑一把看看"便宜，且能直接定位到
"缺哪几个成员"。

## 7. 与"legacy LWJGL2"的边界

本文只解决**现代两代并一代**。legacy（MC ≤1.12.2 的 LWJGL2，随包无后缀 `liblwjgl.so`）是
**另一条轴**：要干掉它得改走 LWJGL3 + LWJGLX（shim），风险高（1.7.10 覆盖度、重验 legacy
输入/全屏），本次**不动**。

## 8. 全链 review（4 个只读 agent）与处置（2026-09-14）

**并代/shim agent**：5 个 shim 与官方 3.4.3/3.3.3 源**逐行比对 = 纯新增、语义等价**
（`STBImageResize` 的 `num_channels→layout` 正对应 v1 的"alpha 不特殊处理"；tinyfd 的 boolean/int 同 3.3.3）。
**glthread agent**：env 时序链（launcher 注入 → 桥逐行 setenv → 预 dlopen → 守卫构造读）成立；守卫
`SYNC_NONE ⇒ armed()==1` 不误触发失效安全、桥的"未武装 → 强制 `GALLIUM_THREAD=0`"兜底仍在。
**UI agent**：被删符号/键/字符串在 `entry/src/main/ets/` **零残留**；`string.json` 147 键无重复、被删键无人 `$r()`；
`.opacity` 仅视觉、不禁用交互（符合预期）。
**回归 agent**：legacy/gl4es 分支未被波及；`mcVersion`（解析后的真版本号，含 Fabric 继承）口径正确；
账户/隔离/argv/`startJvm` 自洽；删除流程"先删目录、失败即不动设置"正确。

**本次已修（另见 app 提交 `fix(review): …`）**：
1. `build_lwjgl_jar.sh`：默认版本 3.3.3→**3.4.3**；per-gen overlay **必须存在且必须传**（否则静默 merge 官方
   stock = 无桥转发的"能编但跑不起来"的 jar）；GLFW `meowcraftbridge` token **改成 assert**；`--with-lwjglx`
   回落路径少一级目录。
2. `meowjrebridge.cpp` `getStr`：固定 1024B **静默截断** → 两段式（先取长度）——否则用户尾部追加的覆盖项
   （如回滚用 `MEOW_GUARD_SYNC=flush`）会被吃掉。
3. `mc_lwjgl_compat_check.py`：补 **CP `Class` 常量**引用检查 + 过滤 `java.lang.Object` 成员 + docstring 声明
   "反射/间接访问不在覆盖内"。改进后对 8 个现代版仍 **0 缺失**（对 3.3.3 对照亦 0）。
4. `pack_extras.py`：`--require` 校验**提到写文件之前**（不再落一个坏 bundle）。
5. `guardNeedsSync`：legacy（<1.17）返回 `true`（"legacy 强制 OpenGLv4" 是未实测的 compat+glthread 组合 → 保守同步）。
6. `GameVersionsView.deleteVersion`：补回读 `glThreadOffIds`；**跨 .minecraft 根的同名实例不再误清**逐版本设置
   （存储只按 id 键；仅当没有别的已授权目录还留同名实例时才清）。
7. 陈旧注释/文档：`Constants`（旧的全局开关注释）、`ClasspathStager`（"两代"）、`RendererPolicy`（`mcVersion` 口径）、
   README（表/overlay 树/摘要）、`pack_extras.py` docstring。

**记录不改（低危/有意）**：守卫头注释里 `eglGetProcAddress` 的说法（实际只导出 glX 系，LWJGL 会回落 dlsym，行为无碍）；
`env_truthy` 把 `false/off` 当真（我们只写 0/1）；`Repeat.key` 里 `editingId/rendererBackend` 段冗余（无害）；
逐版本存储"只按 id"的模型限制（删版本处已缓解；彻底修需把键改成 `(root,id)`，属独立改造）。

### 8.1 第二轮（3 个 agent：验证修复 / 并代独立复审 / glthread 独立复审）

**结论**：7 条修复**全部核对正确**、**无 BLOCKER**。逐项：`getStr` 两段式被逐字节核对**无越界**；`build_lwjgl_jar.sh` 新守卫
**不误伤**文档流程（§1.4/§2/§3 都显式传 overlay）；`deleteVersion` 的跨根判断**标识同型**（都是目录 URI）且 `.some` 语义正确；
`guardNeedsSync` 提前 return 对 legacy 无副作用；校验器新逻辑**不误报**（8 个现代版仍 0，另实测 26.2/26.3-rc 只剩 `Enum` 类误报）；
`pack_extras` 失败确实**不落盘**（且成功路径 sha 逐字节不变）。

**本轮再修**：① 校验器忽略 `java.lang.Enum` 成员（26.x 曾误报 `Platform$Architecture.name()`）；
② `EXTRAS_VERSION` 再升（消除"tar 变了但 token 没变"的理论窗口——实测 `15ebb73` 那次构建因模块名报错**失败未部署**，
故未实际发生）；③ `lwjglClasspathOk` 增加"杂散 `lwjgl-<数字>*` jar"检查（prune 失败时的第二份提供者不再漏检）；
④ 桥另两处固定 buffer（argv 2048 / filesDir 512）也改两段式；⑤ 用户**显式** `MEOW_GUARD_SYNC=none` 覆盖"需要同步"的
版本时记一条 WARN（不改语义、只留痕）；⑥ 模块改名的工具脚本残留（`tools/{lwjgl,freetype,openal,jre25,jre26}` 的
`rebuild_*`、`tools/README.md`）已清；⑦ `tools/lwjgl/rebuild_for_meowcraft.sh` 默认 tag 3.3.3→3.4.3。

**已知残余（有意不改 / 需另行改造）**：
- **≤1.21.x 的自动 `none` 是"按版本号"的经验放行**：若某个 **modded 1.21.x** 命中同款 `glTexSubImage2D` 生命周期，
  仍会无保护崩溃（**仅 ≤1.21.x 无同步保护**；1.22–25.x 与 ≥26.x 均已同步）。**回滚**：逐版本关「线程化渲染」即彻底规避（`GALLIUM_THREAD=0` 无 UAF）。
- 逐版本设置**只按实例 id 键**：① 删版本已缓解；② **移除整个游戏目录**（`GameDirsView.removeDir`）不会清理这些设置，
  残留项会在别根同名实例上"落下来"。彻底修需把键改成 `(root,id)`。
  **→ 2026-09-15 已彻底修**：逐版本设置改存各实例目录内的 `.hmmcraft/instance-settings.json`（天然带 `(root,id)` 维度、
  随目录一起删），旧 Preferences 键弃用；见 [`../20-design/launch/实例设置存储-方案.md`](../20-design/launch/实例设置存储-方案.md)。
- 校验器只覆盖**直接常量池引用**：反射/`Class.forName`/Mixin 间接引用、以及"仅数组引用"的类不在内。
- 提交 `15ebb73` 的消息写"manifest 12→11"，实为 **14→11**（父提交是 14 行）——历史消息不改，以此为准。
