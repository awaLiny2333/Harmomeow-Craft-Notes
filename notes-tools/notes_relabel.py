#!/usr/bin/env python3
"""Align markdown link DISPLAY text with renamed files.

The 20-design reorganisation renamed 23 files; link *targets* were rewritten by
notes_relink.py, but a link whose display text was the old file name still reads e.g.
[`lwjgl多版本并存方案.md`](lwjgl/LWJGL3世代管理-方案.md). This rewrites the display text to the
new basename **only when** the display is exactly the old basename and the target's basename
is the new one (so prose that deliberately mentions an old name is untouched).

Usage: notes_relabel.py [--dry-run]
"""
import os
import re
import sys

NOTES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # notes/ (this file lives in notes/notes-tools/)

# old basename -> new basename (link displays only)
OLD2NEW = {
    "收编自研路线与交接.md": "自研收编-总览与交接.md",
    "原版安装方案.md": "原版安装-方案.md",
    "fabric安装方案.md": "Fabric安装-方案.md",
    "fabric支持改动方案.md": "Fabric支持-改动方案.md",
    "fabric支持调研.md": "Fabric支持-调研.md",
    "账户系统-离线与微软登录.md": "账户系统-设计与进度.md",
    "净室-meow-launcher.md": "launcher净室-设计.md",
    "桌面标准启动链路.md": "桌面标准启动链路-对照.md",
    "lwjgl多版本并存方案.md": "LWJGL3世代管理-方案.md",
    "lwjgl3-并代可行性.md": "LWJGL3单代收敛-决策依据.md",
    "lwjgl2-ohos自编方案.md": "LWJGL2自编-方案.md",
    "LWJGL2-legacy适配复盘.md": "LWJGL2-legacy适配-复盘.md",
    "净室-lwjgl-glfw-bridge.md": "GLFW净室桥-设计.md",
    "sdl3桥接方案.md": "SDL3桥接-设计.md",
    "26.3-SDL适配复盘.md": "SDL3适配-复盘.md",
    "26.2-Vulkan后端跟进.md": "Vulkan后端-跟进与结案.md",
    "26.x渲染栈差异.md": "MC26.x渲染栈-差异分析.md",
    "legacy渲染-GLES-gl4es可行性.md": "legacy渲染-gl4es-落地方案.md",
    "性能优化-平台加速能力与路径调研.md": "平台加速能力-调研.md",
    "性能优化-实验台与glthread负项.md": "性能实验台与glthread-结论.md",
    "性能优化-QoS与绑核实验方案.md": "QoS与绑核-实验报告.md",
    "glthread-B方案-GL-guard.md": "glthread-GL-guard-方案.md",
    "glthread崩溃-bug报告.md": "glthread崩溃-Bug报告.md",
    "lwjgl自编方案.md": "LWJGL3自编-阶段1历史.md",
    "关键发现-系统OpenGL.md": "系统OpenGL-关键发现.md",
    "鸿蒙启动渲染可行设计.md": "鸿蒙启动渲染-早期构想.md",
    "技术路线总纲.md": "技术路线总纲-早期快照.md",
    "Amethyst深潜手册.md": "amethyst-源码深潜.md",
    "Pojav系启动渲染对照.md": "pojav系-启动渲染对照.md",
    # 10-research cleanup (2026-09-15)
    "鸿蒙OpenGL渲染.md": "鸿蒙OpenGL渲染-早期研究.md",
    "三项目对比与路线.md": "三项目对比-早期快照.md",
    "amethyst-深潜手册.md": "amethyst-源码深潜.md",
    # launch/install reorganisation (batch A, 2026-10-01)
    "启动流程-四大类型逐世代总览.md": "启动链-总览.md",
    "架构决策与踩坑.md": "决策与不变量.md",
    "渲染链与迁移结论.md": "渲染链-结论.md",
    "输入方案.md": "输入-总览.md",
    # batch B+C (render/perf convergence + research/adaptation cleanup, 2026-10-02)
    "Vulkan后端-绕过可行性-调研与方案.md": "Vulkan后端-取证存档.md",
    "Vulkan后端-实现历程与原理.md": "Vulkan后端-实现与原理.md",
}
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def main():
    dry = "--dry-run" in sys.argv
    total = 0
    for root, dirs, files in os.walk(NOTES):
        if "/.git" in root:
            continue
        for fn in files:
            if not (fn.endswith(".md") or fn.endswith(".txt")):
                continue
            path = os.path.join(root, fn)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()

            def repl(m):
                nonlocal total
                disp, tgt = m.group(1), m.group(2)
                base = os.path.basename(tgt.split("#")[0])
                # display may be wrapped in backticks and/or path-qualified
                # (e.g. `../20-design/glthread-B方案-GL-guard.md`); look through that.
                bare = disp.strip().strip("`").strip()
                new = OLD2NEW.get(bare) or OLD2NEW.get(os.path.basename(bare))
                if new is not None and new == base:
                    total += 1
                    wrapped = disp.strip().startswith("`")
                    return "[" + ("`" + tgt + "`" if wrapped else tgt) + "](" + tgt + ")"
                return m.group(0)

            new_text = LINK.sub(repl, text)
            if new_text != text and not dry:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(new_text)
    print("link displays aligned: %d" % total)


if __name__ == "__main__":
    main()
