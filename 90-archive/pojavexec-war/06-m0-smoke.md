> 已归档（2026-09-15）：历史档，非现状；现行结论见 [`../../00-current/现状基线.md`](../../00-current/现状基线.md)。

# 06 · M0 冒烟编译结果（✅ 通过）

> 子 agent 于 `stuffs/research/pojav/pojav-war-m0/` 完成（不触碰仓库）。

## 产物
- glfwstub.c（6.9KB）/ glfwstub.o / **libpojavexec.so（37,880B，ELF64 AArch64 DYN）**

## 编译命令（可直接复用）
```
CC=.../hms/native/BiSheng/bin/clang          # target 默认 aarch64-unknown-linux-ohos
SYSROOT=.../openharmony/native/sysroot
JREINC=.../ref/bishengjdk17_0_13_06.hnp/jdk-17.0.13/include
$CC --target=aarch64-linux-ohos --sysroot=$SYSROOT -D__MUSL__ -fPIC -std=gnu11 \
    -I$JREINC -I$JREINC/linux -c glfwstub.c -o glfwstub.o
$CC --target=aarch64-linux-ohos --sysroot=$SYSROOT -D__MUSL__ -shared \
    -Wl,-soname,libpojavexec.so -o libpojavexec.so glfwstub.o
```

## 验证
- SONAME=libpojavexec.so ✅；NEEDED=**仅 libc.so**（干净，未强制 unwind/hilog——空实现无重定位依赖）
- `nm -D` 41 个 GLOBAL 全命中：JNI_OnLoad / JNI_OnLoadGLFW / pojav_environ(B,8B) / 12 个 GLFW Java_* / 3+1 个 CallbackBridge Java_* / RendererInit / VK / 11 个 pojav* / 8 个 critical_* + launchJVM
- 零障碍；仅需补 <stdlib.h>。

## 意义
证明：① 自研鸿蒙版可编（BiSheng clang + openharmony musl sysroot + 毕昇 jni.h）；② 链接 NEEDED 可控到最少；③ 符号面（02 表 A1-A4）一次性达成。M0 目标"能编出来"✅。
下一步 = M1：按 05 布局移植真实实现（ring/event/pump/EGL+libGLv4/JNI hooks），编进 jrelib 对照运行。
