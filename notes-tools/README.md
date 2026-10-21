# notes-tools — 本 notes 仓库自用工具

> 这些脚本**服务 `notes/` 这个仓库本身**（文档工具），**不是**工程构建工具，也**不是** `stuffs/research/` 下的调研/构建产物
> （后者见 [`../00-current/工程与规范.md`](../00-current/工程与规范.md) 里"`stuffs/` 按用途分区"的约定）。
> 全部 `python3`，只改 `notes/` 下的 Markdown 与纯文本文件（不碰代码 / 配置）。`notes/` 是**独立 git 仓库**，改动按本仓约定提交。

| 脚本 | 作用 | 用法 |
|---|---|---|
| [`check_links.py`](check_links.py) | **链接检查**：报告相对 markdown 链接里解析不了的（自动跳过 `.git`；非 UTF-8 文件宽松解码）；有断链则退出码 1 | `python3 check_links.py ..`（`..` = notes 根） |
| [`notes_relink.py`](notes_relink.py) | **批量重算链接**：批量 `git mv`/改名之后，把"目标文件"与"被移动文件自身的出站链接"一起改成新相对路径 | 先改脚本内 `MOVED`（old→new，相对 notes 根），再 `python3 notes_relink.py [--dry-run]` |
| [`notes_repair_links.py`](notes_repair_links.py) | **按内容修断链**：某个相对链接解析不了时，用它 basename 在全库找**唯一**候选并改写（多候选取"最近且严格更近"，否则列出待人工判断） | `python3 notes_repair_links.py [--dry-run]` |
| [`notes_relabel.py`](notes_relabel.py) | **对齐链接显示文本**：把链接的显示文本从"旧文件名"改成"新文件名"（目标不变）；仅在"显示文本 == 旧 basename 且目标 basename == 新名"时改 | `python3 notes_relabel.py [--dry-run]` |
| [`notes_statusdup.py`](notes_statusdup.py) | **活状态去重复**：报告"活状态词"出现在其**唯一事实源（家）之外**的文件:行；发现即退出码 1 | `python3 notes_statusdup.py [--all] [notes_root]` |
| [`notes_stalepaths.py`](notes_stalepaths.py) | **过时路径检查**：报告正文里（反引号 / 《》包着）指向已不存在文件的路径；发现即退出码 1 | `python3 notes_stalepaths.py [--loose] [--include-archive] [notes_root]` |
| [`notes_linerefs.py`](notes_linerefs.py) | **行号引用盘点（第 4 道，提示性）**：列出正文里（反引号 / 散文）的 `文件:行` / `函数:行` / 裸 `:行` 引用并按目标文件聚合；**默认退出码 0（不阻塞）**，`--strict` 才有命中即退出 1 | `python3 notes_linerefs.py [--include-archive] [--strict] [notes_root]` |

## `notes_statusdup.py` 的语义（活状态单一事实源，2026-09-15 用户批准）

信息分两类，区别对待：

- **不变量**（定案事实、很少变：JRE = OpenJDK 26、现代 LWJGL 单代 3.4.3、命名对照、后端选型、支持窗口 1.6.x–26.3）**允许复述**——读者受益、同步成本低。
- **活状态**（会变：`已实机验证` / `未实机` / `待复验` / `待提交` / `未实现` / `在办` / `待办` / `进度`）**只有唯一一处能写**，别处只能写**指针**（`状态见 现状基线.md §5 第 N 条`）或**带日期的记录**。（上一行的词表是规则条文本身的引用、非现状断言；该词表 2026-09-15 定稿。）

**活状态的唯 4 个「家」**（白名单，只有这 4 个文件可裸写活状态；`90-archive/**` 整体豁免，历史允许陈旧）：

[`../00-current/现状基线.md`](../00-current/现状基线.md)（权威，§5 编号条目）· [`../00-current/项目总览与新人上手.md`](../00-current/项目总览与新人上手.md)（新人投影 §3）· [`../00-current/已知限制与待解.md`](../00-current/已知限制与待解.md)（未决/受限登记册）· [`../README.md`](../README.md)（极简投影）。

**带日期 = 记录、不带日期 = 断言**：`2026-09-10 实测 1.21.10 可玩` 是**既成事实的记录**，放哪儿都不会与别的文档变矛盾；而**不带日期**的 `已实机验证` 是在**断言"现在如此"**，必须落在家（或改成指针）。故脚本跳过两类行：① 自称历史的（`当时` / `历史` / `曾` / `旧` / `已归档` / `archive` / `此前`）；② 带日期的观测。`--all` 额外报告更软的规划词（`待办` / `在办` / `下一步候选` / `规划中` / `尚未` / `计划中` / `验证计划`），属提示、不强制清零。

## `notes_linerefs.py` 的定位（第 4 道：**提示性**，与三道强制检查不同）

前三道检查回答"**对不对**"——链接是否解析（`check_links.py`）/ 路径是否存在（`notes_stalepaths.py`）/
活状态是否越位（`notes_statusdup.py`），**必须全绿**；`notes_linerefs.py` 回答的是另一个问题：
"**哪些行号引用需要人工复核**"。它**不判对错**，只把全库的 `文件:行` 引用列成清单——
因为代码一动，`Foo.ets:472-511` 的行号就会**静默指错**（链接照样解析、路径照样存在，只有行号错），
而前三道检查都看不见这一类腐蚀。故它**默认退出码 0、不阻塞提交**；`--strict` 才在有命中时退出 1
（供将来决定是否升级为强制）。

- 覆盖形态：`路径:NN` / `路径:NN-MM` / `路径:NN,MM`、`Foo.java:123`、`函数名:104`、
  `Class.method:117-160`、裸 `:1723`（沿用同句前一个引用）。
- **markdown 链接的显示文本不当作引用**（把 `Foo.ets:12` 写成某链接的显示文本时，它只是标签，
  归 `check_links.py`）——避免两道检查重复报。
- 输出末段给**总数**与**按目标文件聚合的计数**（便于看"哪份代码被引用最多、最该复核"）。
- `SYM` 桶（函数/符号名）最松，可能混入 `spec:0` / `format:1` 这类 `键:值` 噪声（一眼可辨）；
  `FILE` 与 `BARE` 是高精度桶。
- `--include-archive` 纳入 `90-archive/**`（历史允许陈旧）。

## 使用规矩（踩过坑，见记忆 `meowcraft_bulk_rewrite_idempotency`）

1. 批量改完**立刻** `check_links.py`；出现断链用 `notes_repair_links.py` 兜底（**按内容修**，别猜路径）。
2. `notes_relink.py` **幂等**：目标当前目录已能解析的链接一律不动 —— 但仍**只用于"刚 `git mv` 过、链接还没重算"**的场景；跑第二遍是 no-op。
3. **别在一条消息里**同时跑"改文件的脚本"和"派 agent 改同一批文件"（并行会互相覆盖）。
4. 出事**别整目录 `git checkout`** 回滚（会丢同期 agent 的内容改动）——用按内容修复的 pass。
5. **正文里别写裸的 markdown 链接字面量**（例如把示例写成"方括号+圆括号+路径"）——`check_links.py` 的正则会把示例当成真链接而报断链；要举例请用文字描述或加空格断开。

## 典型流程（整理一个分区）

```sh
cd notes
mkdir -p <新子目录>
git mv 旧名.md <新子目录>/新名.md ...          # 批量移动/改名
python3 notes-tools/notes_relink.py --dry-run  # 先看规模（改脚本里的 MOVED）
python3 notes-tools/notes_relink.py
python3 notes-tools/notes_relabel.py
python3 notes-tools/check_links.py .           # 必须 all OK
```
