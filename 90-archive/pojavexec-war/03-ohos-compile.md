> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)。

# 03 · OHOS NDK 编译可行性（工具链 / 头文件 / 链接 / Android→OHOS 对照）

> 来源：子 agent C 侦查（实际 find/ls/readelf 核验，只读）。

## 0. 一句话结论
**可行，证据链强**：① 现有 hvigor CMake 骨架可接纳 `.c` 源与附加 `.z.so`；② `jni.h` NDK 没有，但 `ref/bishengjdk17_0_13_06.hnp` 自带为 OHOS aarch64 编译的 BiSheng JDK 头（`include/jni.h` + `include/linux/jni_md.h`）；③ sysroot 里 Android 头/库的 OHOS 等价物逐一 find 验证存在；④ jrelib `libs/arm64-v8a/` 已躺着一个能跑的预编译 OHOS `libpojavexec.so`（NEEDED 实测 = libdriver_helper/libhilog_ndk.z/libace_napi.z/libnative_window/libc 等）——证明同源 C 桥在 OHOS "编得出、链得上、跑得起"。

## 1. 工具链 / sysroot（本机双 SDK 组合）
- 编译器：hms/BiSheng `.../hms/native/BiSheng/bin/clang`（15.0.4；hvigor 实际用它）
- sysroot：`.../openharmony/native/sysroot`（头 usr/include、库 usr/lib/aarch64-linux-ohos）
- 工具链文件：`.../openharmony/native/build/cmake/ohos.toolchain.cmake`、`.../hms/native/build/cmake/hmos.toolchain.bisheng.cmake`
- jrelib 实证：`CMAKE_TOOLCHAIN_FILE=hmos.toolchain.bisheng.cmake`，`CMAKE_C_COMPILER=BiSheng/bin/clang`，sysroot=openharmony；自动注入 `-D__MUSL__ --rtlib=compiler-rt -fuse-ld=lld -Wl,--no-undefined -lunwind -ldeviceinfo_ndk.z`。
- 手工编译命令形态（验证用）：
  ```
  CC=.../hms/native/BiSheng/bin/clang
  JREINC=.../ref/bishengjdk17_0_13_06.hnp/jdk-17.0.13/include
  $CC --target=aarch64-linux-ohos --sysroot=.../openharmony/native/sysroot -D__MUSL__ \
      -fPIC -std=gnu11 -I$JREINC -I$JREINC/linux -I<jni>/include -c x.c -o x.o
  $CC --target=aarch64-linux-ohos --sysroot=... -D__MUSL__ -shared -o libpojavexec.so x.o \
      -lhilog_ndk -lnative_window
  ```
- libclang_rt.builtins/libunwind/libc++ 位置已验证存在。

## 2. jni.h（关键缺口 → 有解）
- NDK 全树**无 jni.h/jni_md.h**（只有 js_native_api.h = NAPI）。
- **来源**：`ref/bishengjdk17_0_13_06.hnp/jdk-17.0.13/include/{jni.h,jni_md.h}`（1987 行；`_LP64` 下 jlong=long、jint=int，JNIEXPORT=visibility default）→ aarch64 musl 完全匹配；JNI ABI 跨版本稳定，即使运行时是 JDK25 也 OK。后备 `bishengjdk8u432.../include`。
- 姿势：C target 加 `-I<jdk>/include -I<jdk>/include/linux`，别动 sysroot。

## 3. Android → OHOS 等价物逐项对照（均已 find 验证）
| # | Android | OHOS | 备注 |
|---|---|---|---|
| 1 | android/log.h | hilog/log.h + libhilog_ndk.z.so | 写 log.h shim 把 LOGE... 映射 OH_LOG_Print，一处收口 |
| 2 | android/native_window.h (ANativeWindow_*) | native_window/external_window.h（OHNativeWindow / OH_NativeWindow_*；CreateNativeWindowFromSurfaceId(surfaceId)）+ libnative_window.so | 逐 API 换名（setBuffersGeometry→NativeWindowHandleOpt SET_BUFFER_GEOMETRY） |
| 3 | native_window_jni.h ANativeWindow_fromSurface | 无 JNI 版；用 XComponent surfaceId→OH_NativeWindow_CreateNativeWindowFromSurfaceId | 本工程 homl_bridge surfaceChanged 已实现同通道 |
| 4 | AHardwareBuffer/ARect | 无公开头；几何走 NativeWindowHandleOpt，格式用常量 | — |
| 5 | dlext/androidnsbypass | **无**；普通 dlopen（jre_bridge 已 RTLD_NOW\|GLOBAL 预 dlopen libGLv4） | 卸载 nsbypass 依赖 |
| 6 | android_get_device_api_level | 无 | 桩替换 |
| 7 | EGL/egl.h 等 | sysroot 有同名头；libEGL.so；EGLNativeWindowType = struct NativeWindow*（对得上 OHNativeWindow） | — |
| 8/9 | GLES2/GLES3 | 同名头 + libGLESv2/v3 | — |
| 10 | GL/osmesa.h | sysroot 只有 GL/{gl,glcorearb,glext}，无 osmesa；Amethyst 自带 GL/osmesa.h 自洽可编 | OSMesa 是运行时软渲路径，GLv4 后端不触发 |
| 11 | KHR/khrplatform.h | 有 | — |
| 12 | -ldl/-llog/-landroid | dl 内置于 libc（可省 -ldl）；-lhilog_ndk；-lnative_window | 预编译 pojavexec NEEDED 无 libdl |
| 13 | AInputQueue/触摸 | 无 C 注入；输入走 homl_bridge NAPI send_* | 与预编译 so 的 JavaCritical/CallbackBridge 导出形态一致 |
| 14 | bytehook/exithook/linkerhook/glxshim 族 | 无等价，应裁剪 | 预编译 NEEDED 里有 libdriver_helper（配套） |

## 4. 链接面蓝本
**实测预编译 OHOS libpojavexec.so NEEDED**：libdriver_helper/libace_napi.z/libhilog_ndk.z/libnative_window/libability_{access_control,base_want,runtime}/libc
→ 新编译可直接照抄；EGL/GLv4 **不静态链**（走 dlsym 指针表；`-Wl,--no-undefined` 下凡直接调用必须链上对应库）。

## 5. 最小验证路径
1. 手工 clang 冒烟：3 文件（glfwstub.c 定义 pojav_environ + JNI_OnLoad 返 JNI_VERSION_1_6 + pojavInit + 2-3 个 nglfw*/CallbackBridge 桩；log.h shim；jni 取毕昇 17）。产出后 readelf 核对 `.dynsym` 含 JNI_OnLoad/Java_*/pojav_environ，NEEDED 只有 libhilog_ndk.z + libc。
2. 接 hvigor：jrelib CMakeLists 增 `add_library(pojavexec SHARED <port 源>)` + jni include + `libhilog_ndk.z.so libnative_window.so`；**删除 libs/arm64-v8a/libpojavexec.so 避免冲突**。
3. 渲染不动：GL/EGL 走 dlsym 指针表；桩阶段可不实现 pojavInitOpenGL 调用体。

## 6. 最大编译/集成风险（按杀伤力）
| 风险 | 缓解 |
|---|---|
| jni.h 缺失 | 毕昇 include；只对 C target 加 |
| -Wl,--no-undefined 强链 | 直接调用必须链库，否则全走指针表（预编译 NEEDED 是正确蓝本） |
| Android linker-namespace 文件（egl_bridge/loader_dlopen/osm/swap_interval_no_egl） | 裁掉/改写为 OHNativeWindow+surfaceId+普通 dlopen；OSMesa/swap_interval 对 GLv4 可整文件删 |
| 符号可见性 | jni_md.h JNIEXPORT=default 保证；勿加 -fvisibility=hidden；构建后 readelf 验 .dynsym |
| musl vs bionic | 逐个编译错修（environ extern、signal、endian 头等） |
| namespace/部署 | 新 so 放 jrelib libs/arm64-v8a 与 homl_bridge 同目录；LD_LIBRARY_PATH/POJAV_NATIVEDIR 已闭环 |
| 与预编译产物冲突 | 删预编译 so 或只用预编译做对照 |

## 关键路径速查
- clang：`.../openharmony/native/llvm/bin/clang`（15.0.4）；`.../hms/native/BiSheng/bin/clang`
- sysroot：`.../openharmony/native/sysroot`；工具链 cmake 两处
- jni.h：`ref/bishengjdk17_0_13_06.hnp/jdk-17.0.13/include/{jni.h,linux/jni_md.h}`
- Amethyst 源：`ref/Amethyst-Android/app_pojavlauncher/src/main/jni/`
- 现成 OHOS 产物：`libs/jrelib/libs/arm64-v8a/{libpojavexec,libhoml_bridge,libdriver_helper}.so`
