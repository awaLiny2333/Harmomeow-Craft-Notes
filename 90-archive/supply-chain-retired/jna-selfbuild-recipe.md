# JNA `libjnidispatch.so` 自编全栈留档（备不时之需）

> 📦 **已归档（2026-09-09）**：项目已决定摘除 JNA（非自编），本文为历史档案（非现状）。
> 现状见 [`../../30-supply-chain/provenance-master.md`](../../30-supply-chain/provenance-master.md)。

> 日期：2026-09-09 ｜ 状态：**配方已验证（PoC），但项目决定摘除 JNA**（见 [`jna-analysis.md`](jna-analysis.md)）。
> 本文把"如果哪天真要自编"的全部技术细节固化下来：源码/版本/工具链/JNI 头/libffi/编译链接命令/PoC 结果/版本矩阵。
> 当前决策是不自编；但 OpenAL 那条路证明过"配方留档 = 随时能复现"，故一并存档。

## 0. 一句话

用 **OHOS clang 15.0.4 + JNA 5.15.0 源码 + libffi 3.4.4 + 仓库内 `jni.h`**，直接 `clang` 编译链接
即可产出 ABI 等价的 `libjnidispatch.so`（native ABI `7.0.2`）；**无需 ant、无需源码补丁**。PoC 已跑通。

## 1. 源码与版本（关键：分清 jar 版本 vs native ABI 版本）

- 上游：`https://github.com/java-native-access/jna`（LGPL-2.1-or-later / Apache-2.0）。
- **`ref/` 里没有 JNA 源码**，需现拉。本项目目标 tag：**`5.15.0`**（commit `fad4d1dc4e791f8083d6a3afa28a3ea8bdcbe0ee`），
  `common.xml`: `jni.major=7 jni.minor=0 jni.revision=2`，`jni.md5=5fb98531302accd485c534c452dd952a`。
- **"6.1.6" 是 native ABI 版本，不是 jar 版本**：现件 `.so` 实为 **JNA 5.13.0**（`jni.major=6/minor=1/revision=6`，`jni.md5=147a998f0cbc89681a1ae6c0dd121629`，与二进制内 `getAPIChecksum` 一致）。
- **为什么锁 5.15.0**：`dispatch.c` 的 varargs 位在 5.13.0→5.15.0 之间改过
  （`fixed_args` 由 `(flags & USE_VARARGS) >> 7` 变为 `(flags >> USE_VARARGS_SHIFT) & USE_VARARGS`），
  用 5.13.0 的 native 配 5.15.0 的 jar 会**错处理 varargs**（所以"改 5 字节版本串"的止血法只消警告、不修 bug）。
- 版本矩阵见 §7。

## 2. 工具链

- OHOS NDK：`$HOME/devecow/deveco_tools/sdk/default/openharmony/native`
  - `CC = <sdk>/native/llvm/bin/aarch64-unknown-linux-ohos-clang`（clang 15.0.4，target 已含 ohos/musl）
  - `STRIP = <sdk>/native/llvm/bin/llvm-strip`
- **不需要 ant**：上游 `build.xml`+`native/Makefile` 只是驱动 `javah`+`make`；我们直接调 clang。
- JNA 自带 libffi 3.4.4 源码（`native/libffi/`），但**只带 `configure.ac`、无 `configure`**，且沙箱缺 `automake`/`libtoolize`。

## 3. JNI 头（NDK sysroot 没有 `jni.h`）

- 现成可用：**仓库内** `Meowcraft/libs/meowcraftlib/src/main/cpp/meowcraftbridge/jni.h` + `jni_md.h`（OpenJDK 25，GPL+CE）。
- **生成头是必需**（不是仅原型）：`com_sun_jna_Native.h` / `com_sun_jna_Function.h` 定义了
  `com_sun_jna_Native_CVT_*`、`TYPE_*`、`CB_*`、`com_sun_jna_Function_USE_VARARGS_SHIFT`，`dispatch.c` 依赖它们。
  - 规范做法（需 JVM，用户跑）：`javac -h <out> -d <tmp> $(find src/com/sun/jna -name '*.java')`。
  - **Agent 可行回退（已验证）**：~20 行 Python 解析 `Native.java`/`Function.java` 的 `static final int/long/boolean` 常量，生成 `#define`（产出 42 + 7 个）。

## 4. libffi（两条路，均已验证）

1. **官方源码自编 3.4.4**（JNA 自带的是同版本；其树内无 `configure`）：
   ```sh
   CC=$CC CFLAGS="-O2 -fPIC" ./configure \
     --build=aarch64-unknown-linux-gnu --host=aarch64-linux-musl \
     --enable-static --disable-shared --with-pic
   make   # -> .libs/libffi.a + include/ffi.h
   ```
   （`--build`/`--host` 必须显式给：libffi 的 `config.sub` 不认 `ohos`，且沙箱不能执行目标测试程序。）
2. **HNP 预编译**（已是 OHOS aarch64）：`/data/service/hnp/libffi.org/libffi_3.4.4/lib/libffi.a` + `.../include/ffi.h`。

> 注：现件只用 `mkstemp`（无 `memfd_create`/`mkostemp`/mntent）→ 若要**逐项对齐**现件，configure 加
> `ac_cv_func_memfd_create=no ac_cv_func_mkostemp=no`；这些导入在 OHOS libc 都存在，能用，实际影响低。

## 5. 编译 / 链接配方（PoC 验证过）

```sh
SDK=$HOME/devecow/deveco_tools/sdk/default/openharmony/native
CC=$SDK/llvm/bin/aarch64-unknown-linux-ohos-clang
STRIP=$SDK/llvm/bin/llvm-strip
JNI=<repo>/Meowcraft/libs/meowcraftlib/src/main/cpp/meowcraftbridge   # jni.h, jni_md.h
FFI=<libffi 前缀>                                                    # include/ffi.h + lib/libffi.a

# 1) 源码
git clone --depth 1 --branch 5.15.0 https://github.com/java-native-access/jna.git jna_src
# 2) 生成 com_sun_jna_{Native,Function}.h（见 §3）
# 3) 编译
CF="-O2 -fPIC -fno-omit-frame-pointer -fno-strict-aliasing -D_REENTRANT -DNO_JAWT \
    -DFFI_STATIC_BUILD -DJNA_JNI_VERSION=\"7.0.2\" \
    -DCHECKSUM=\"5fb98531302accd485c534c452dd952a\" \
    -W -Wall -Wno-unused -Wno-parentheses \
    -I<gen-headers> -I$JNI -I$FFI/include"
$CC $CF -c native/dispatch.c -o dispatch.o
$CC $CF -c native/callback.c -o callback.o
# 4) 链接 + strip
$CC -shared -o libjnidispatch.so dispatch.o callback.o $FFI/lib/libffi.a \
    -Wl,-soname,libjnidispatch.so -Wl,-Bsymbolic
$STRIP --strip-unneeded libjnidispatch.so
```

要点（由现件 ELF 反推）：
- `-DNO_JAWT`（无 `jawt.h`）；`-DFFI_STATIC_BUILD`（静态链 libffi）；
- **不要** `-DHAVE_PROTECTION`（现件把 protection 编译掉：`isProtected`=`mov w0,wzr;ret`，无 `signal`/`setjmp`/`mprotect` 导入）；
- `JNI_OnLoad` 用 `JNI_VERSION_1_4`；`DT_NEEDED` 仅 `libc.so`；`SONAME=libjnidispatch.so`。

## 6. PoC 结果（2026-09-09，agent 实跑）

产物：`stuffs/research/jna/jna_poc/out/libjnidispatch.so`（170,264 B；从 `~/deveco/` 迁入），静态核验：

| 断言 | 结果 |
|---|---|
| 导出符号集 vs 现件 | **144/144 完全一致** |
| `Java_com_sun_jna_Native_getNativeVersion` | `"7.0.2"` |
| `DT_NEEDED` / `SONAME` / `.note.ohos.ident` | `libc.so` / 正确 / 存在 |
| `isProtected()` | 0（与现件一致） |
| 非弱导入符号 | 全部在 sysroot `libc.so` 可解析 |

**未做**：实机加载（agent 沙箱不能 dlopen/执行任何 `.so`，含现件）→ 实机回归必须用户跑。

## 7. 版本矩阵（一个 `.so` 覆盖不了 1.17–1.21.x）

| MC | jna.jar | 期望 native ABI |
|---|---|---|
| 1.17–1.18.1 | 5.8.0 / 5.9.0 | 6.1.1 |
| 1.18.2–1.19.2 | 5.10.0 | 6.1.2 |
| 1.19.3–1.20.1 | 5.12.1 | 6.1.4 |
| 1.20.2–1.20.4 | 5.13.0 | **6.1.6**（= 现件） |
| 1.20.5–1.21.3 | 5.14.0 | 7.0.0 |
| 1.21.4–1.21.10 | 5.15.0 | 7.0.2 |
| 1.21.11 | 5.17.0 | 7.0.4 |

JNA 兼容判定只看 **major 相同 + expectedMinor ≤ nativeMinor** → 6.x 与 7.x 是两条线；全版本覆盖需**两套 native + 按版本选择**（仿 `oshi-overrides/manifest.txt`）。

## 8. 快速止血（不推荐，仅记录）

改现件 5 字节版本串：文件偏移 `0x443f` 处 `6.1.6` → `7.0.2`（等长）。可让 `isCompatibleVersion` 通过
（1.21.10/1.21.11），**但**留下 5.13.0-vs-5.15.0 的 varargs 语义 bug，且 udev 仍不可用 → **不采用**。

## 9. 工作量 / 风险（若要自编）

- **工作量**：单版本 ~0.5–1 天（PoC 已把硬骨头啃完）；全版本再加 ~0.5 天（两条 ABI 线 + 版本选择）。
- **风险**：① 多版本 ABI 矩阵；② libffi 特性集差异（低影响）；③ protection 必须关；④ **与现件无法逐字节一致**（不同 libffi configure/编译路径）——目标是功能等价 drop-in；⑤ 实机回归必须用户跑。

## 10. 为什么留档

项目当前决定**摘除 JNA**（功能收益≈0，见 [`jna-analysis.md`](jna-analysis.md)），但：
- 若将来 MC 需要 JNA 的某项能力（如新的 native FFI 需求）、或平台补上 `libudev`；
- 或需要某个特定 JNA 版本线；
- 本文 + PoC 结论可让任何人**快速复现**，不必重新调研。

## 相关

- 调研/定案：[`jna-analysis.md`](jna-analysis.md)
- 溯源：[`provenance-master.md`](../../30-supply-chain/provenance-master.md) §4.3、[`per-so-catalog.md`](../../30-supply-chain/per-so-catalog.md) §B
- 对照（同类自编）：`Meowcraft/tools/openal/`（OHOS 交叉编译 + 可复现）
