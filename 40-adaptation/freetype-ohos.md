# FreeType 鸿蒙自编（libfreetype.so）

> 日期：2026-09-09 ｜ 状态：**已实机验证**（MC 字体正常）
> 相关：溯源 [`../30-supply-chain/provenance-master.md`](../30-supply-chain/provenance-master.md) §4.3、
> [`../30-supply-chain/per-so-catalog.md`](../30-supply-chain/per-so-catalog.md) §B；工具 `Harmomeow-Craft-Launcher/tools/freetype/README.md`
> 本文为决策记录 / 证据存档，**不复述现状**；当前状态见 [现状基线.md §5 第 14 条](../00-current/现状基线.md)。

## 0. 一句话

外部历史件的 `libfreetype.so` 经取证 = **原版 FreeType 2.13.3（无魔改）**；我们用上游 2.13.3 源码自编替换，
**`.text` / `.rodata` 与外部历史件逐字节一致**，字体实测正常 → 从「归因」升级「**源码级**」。

## 1. 现象/目标

- 非 bug，纯自主可控诉求：该 so 为外部历史件，无本地源码/构建配方（归因级）。
- 目标：从上游源码自编 drop-in，`libfreetype.so`（MC 字体渲染的 native）。

## 2. 取证：它就是原版 2.13.3

- **版本**：`FT_New_Library` 从 `.rodata` 读 major/minor（`02 00 00 00 0d 00 00 00` = 2/13）+ 指令 patch（`mov w9,#3`）→ **2.13.3**。
- **依赖**：`DT_NEEDED=libz.so + libc.so`（可选 png/harfbuzz/brotli/bzip2 全关）。
- **符号**：222 个 T（`FT_*`/`FTC_*`/`TT_*`），**无自定义符号**。
→ 结论：**stock FreeType 2.13.3 + OHOS 交叉编译**，无源码改动。

## 3. 自编（`tools/freetype/`）

- 源码：`ref/freetype` tag **`VER-2-13-3`**。
- 构建：OHOS clang 15 + sysroot，`BUILD_SHARED_LIBS=ON`，**只留 zlib**（`FT_DISABLE_BZIP2/PNG/HARFBUZZ/BROTLI=ON`）。
- 后处理：`llvm-strip --strip-unneeded` + 去 OHOS 元数据段（`.permission`/`.codesign`/`.comment`）对齐旧件形状。
- 断言：导出 `FT_/FTC_/TT_` ≥ 200（实际 222）。

## 4. 数据流

```
MC 字体渲染 → LWJGL lwjgl-freetype（org.lwjgl.util.freetype）→ libfreetype.so（我们自编）
```

## 5. 分发

替换 `libs/meowlwjgls/libs/arm64-v8a/libfreetype.so`；部署 `devecocli run --module entry meowjre`。

## 6. 版本范围

FreeType **2.13.3**（`ref/freetype` 有 `VER-2-13-3` tag）。升级需改 wrapper tag + 重验（`FT_Library_Version` 自报版本）。

## 7. 复现

```sh
sh Harmomeow-Craft-Launcher/tools/freetype/rebuild_for_meowcraft.sh
```

- sha256：`e41fe6b927f3d6605548473a6468000855ab9ad9239ef8d6ad988a3b2e0f1167`；**3 次干净重建 `cmp` 逐字节一致**。

## 8. 与外部历史件的差异（仅元数据）

| 项 | ours | 旧件 |
|---|---|---|
| `.text` / `.rodata` | — | **逐字节一致** |
| 文件大小 | 701912 | 701912 |
| 差异 | build-id（20B）+ 段表偏移（11B） | — |

→ **功能与代码完全等价**，drop-in 无损。

## 相关

- 工具：`Harmomeow-Craft-Launcher/tools/freetype/README.md`
- 同类：[`openal-ohos.md`](openal-ohos.md)、[`ohaudio-backend.md`](ohaudio-backend.md)
