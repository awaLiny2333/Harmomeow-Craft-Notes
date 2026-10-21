# 16 · Stage C：pojavexec → meowcraftbridge 全链改名（2026-09-08）

> libpojavexec.so 名字彻底退役。至此 HSP native = libmeowjrebridge.so + libmeowcraftbridge.so，
> 全自研 meow 命名（Stage A/B 见 12-15；前置 08 supply-chain）。

## 为什么之前不能改
Java 侧随包 `lwjgl.jar`（`org/lwjgl/glfw/GLFW.class`）硬编码 `System.loadLibrary("pojavexec")`，
是名字唯一非源码持有者（launcher/gson/jsr305/patchjna 均无该名，已全量扫 jar 证实）。

## 方案 A = 常量池二进制补丁（非重编）
- `tools/patch_pojav_libname.py`（**该工具已删除**，原为入库可复现）：
  - 解析 GLFW.class 常量池，把 2 个 Utf8 `pojavexec`→`meowcraftbridge`、`libpojavexec.so`→`libmeowcraftbridge.so`
    （Utf8 长度前缀定界，改长度不破坏索引/字节码）；
  - 重打 meowcraft_extras.tar.gz，其余成员逐字节不变；自校验（恰 1 处替换/无残留/可回读）。
- 产出：meowcraft_extras.tar.gz `bdd7adee…`(原, 存 git 历史) → `b34e5932…`；patched lwjgl.jar `cfdc508a…`。
- 配套改名：CMake 删 `OUTPUT_NAME pojavexec`（默认出 libmeowcraftbridge.so）、`PojavLib()` dlopen 路径、
  日志串、Index.ets/d.ts/pojav_environ.h/entry cpp/libmeowassets 注释。

## 踩坑：install -r 缓存旧 jar（UnsatisfiedLinkError 那一跑的根因）
- stageClasspathDir 的 done 标记此前只判"文件存在"→ cacheDir/mc-cp/<id> 跨 install -r 保留，
  仍用旧 lwjgl.jar（继续 loadLibrary pojavexec），而 el1 新包已无 libpojavexec.so → 崩。
- 修复：done 文件内容改为 `EXTRAS_VERSION` 令牌，比对失败即重抽覆盖（永久自愈机制，
  今后 meowcraft_extras.tar.gz 内容再变更只需提升令牌）。

## 实机验证（日志铁证）
- `[LWJGL] Loading library: libmeowcraftbridge.so` → `Loaded from org.lwjgl.librarypath: ...`
- 0 处 `libpojavexec.so`/`UnsatisfiedLinkError`/`homl_bridge`；zink+Maleoon 渲染、输入/IME、pojavTerminate 干净收尾。

## 备忘
- 08 digest 已更新（v3 标注）；原 tar 由 git 历史 + HOML 锚点可还原。
- 设备上旧部署若残留 libpojavexec.so 属无害死文件（新包/新 jar 均不引用）。
