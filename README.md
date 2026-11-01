# 事件序列分析

大数据处理课程项目：事件序列中的频繁模式与行为变化分析。使用 Online Retail II 与 H&M 交易数据，在 Spark / PySpark 框架中比较 GSP、PrefixSpan、SPADE 和 SPAM，并以 MLlib PrefixSpan 作为工程参照。项目开发使用了 AI 辅助。

仓库包含源码、实验配置、依赖清单和必要说明。原始数据、处理后的数据、实验结果、报告成品、下载文献、第三方依赖和运行环境均不上传，由使用者在本地准备或生成。

## 项目结构

| 路径 | 内容 |
| --- | --- |
| `代码/` | 数据下载、预处理、单机算法、结果分析与报告生成 |
| `代码/导出结果.py` | 将正式结果直接导出为可用 Excel 打开的三张 CSV |
| `分布式处理/` | Spark 作业、数据适配、独立校验与集群提交脚本 |
| `分布式处理/参数/` | 零售交易、零售日级与服装交易的 JSON 配置 |
| `算法比较/` | 四种算法内核、穷举验证、实验比较与汇总 |
| `文献/` | 技术来源说明与文献索引 |
| `实验方案.json` | 单机基准的实验设计 |
| `requirements.txt`、`依赖版本.txt` | Windows 侧 Python 依赖 |
| `使用说明.md` | 实验语义、参数、运行方式与已有实验说明 |

## 环境准备

现有运行入口面向 Windows + WSL Ubuntu：Windows Python 3.12 用于数据处理和报告生成，WSL 内需要 Python 3.12、NumPy、SciPy 和 Java 17 或 21。Spark 安装脚本固定使用 PySpark 4.0.1、Py4J 0.10.9.9。报告生成使用 Windows 中文字体。

在 PowerShell 中克隆仓库，并进入项目根目录；建议放在空间充足的数据盘：

```powershell
git clone https://github.com/hga-jscs/HomeworkForBigDataProcessing.git
cd HomeworkForBigDataProcessing

# 确认当前 python 为 Python 3.12；也可直接指定自己的解释器完整路径。
$pythonPath = (Get-Command python -ErrorAction Stop).Source
& $pythonPath --version
New-Item -ItemType Directory -Force .\临时文件, .\结果 | Out-Null
$env:TEMP = (Resolve-Path .\临时文件).Path
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $env:TEMP '安装缓存'
& $pythonPath -m pip install --target .\依赖 -r .\requirements.txt
```

PowerShell 入口保留了原开发环境的默认解释器路径。换一台机器运行时，请像下文一样显式传入 `-PythonPath $pythonPath`。

## 运行

不下载数据即可运行四种算法的穷举正确性与分区完备性检查；结果写入本地 `结果/算法正确性.json`：

```powershell
& $pythonPath .\算法比较\验证算法.py
```

准备好 WSL 环境后，运行完整流程：

```powershell
.\完整复现.ps1 -PythonPath $pythonPath
```

完整流程会下载缺失的公开数据、准备 Spark、执行单机及分布式实验、进行算法比较，最后导出 CSV 并生成报告，需要充足的磁盘空间与运行时间。三张 CSV 写到 `结果/成果/`，算法对比报告写到项目目录的上一层，其余数据和实验产物主要写入项目内的 `数据/`、`结果/` 与 `临时文件/`。

其他入口：

```powershell
# 单机基准。
.\复现单机基准.ps1 -PythonPath $pythonPath

# 已完成数据准备与 Spark 安装后，运行指定数据集。
.\运行分布式实验.ps1 -Dataset 零售交易

# 已生成分布式顾客序列后，小规模试跑算法比较。
.\运行算法比较.ps1 -PythonPath $pythonPath -Pilot

# 仅在本地已有完整正式结果时，重新核验、导出 CSV 并生成报告。
.\运行算法比较.ps1 -PythonPath $pythonPath -OnlyReport
```

刚克隆的仓库不含已有实验结果，不能直接使用 `-OnlyReport`。数据获取入口为 `代码/准备数据.py` 和 `代码/下载服装数据.py`；配置中的 `{project}` 会替换为本机项目路径。详细前置条件、实验参数及 YARN / HDFS 迁移步骤见 [使用说明](使用说明.md)。

## CSV 结果输出

`完整复现.ps1`、正式模式的 `运行算法比较.ps1` 及它们的 `-OnlyReport` 入口，都会在结果核验后自动调用 [导出结果.py](代码/导出结果.py)。`-Pilot` 只做试跑，不覆盖正式 CSV。

| 文件 | 每行内容 | 当前正式实验行数 |
| --- | --- | ---: |
| `结果/成果/频繁模式.csv` | 数据集、购买顺序、支持顾客数、顾客支持度及发现期 | 2,914 |
| `结果/成果/行为变化.csv` | 前后期人数与支持度、变化百分点、四类配对人数、BY 判定 | 2,260 |
| `结果/成果/算法测量.csv` | 场景、算法、重复编号、耗时、模式数与单进程内存 | 75 |

频繁模式表包含 H&M 的 1,245 条与零售的 1,669 条，采用当前 5% 支持度、最长三步的全量主设置。变化表包含其中 1,212 条与 1,048 条二步、三步候选；测量表覆盖七个正式场景。人数、窗口、阈值和重复次数由实际结果读取，上表是当前实验的记录，不是脚本写死的输出数量。

例如，H&M 的“长裤 → 短裤”有 42,236 名发现顾客匹配，支持度为 25.87%。箭头表示跨购物篮的先后关系，允许间隔；支持度的分母是整个发现集。变化表则在独立评估集上比较同一模式的前后期表现，可用于筛选需要复查的上升或下降路径。

已有正式结果时，可以只重新导出 CSV，不启动 Spark、不重新计算实验，也不重排 PDF：

```powershell
& $pythonPath .\代码\导出结果.py

# 可选：另存到项目下的其他目录。
& $pythonPath .\代码\导出结果.py --output .\结果\重新导出
```

导出脚本仅使用 Python 标准库，默认按脚本位置定位项目；也可用 `--project` 指定其他项目副本。输入为 `结果/算法比较汇总.json`、`结果/算法比较/正式/`，以及两个主批次 `模式/_完成.json`、`变化/_完成.json` 和 `变化/完整统计.json`。商品名称表可选，缺失名称保留原始编码。

CSV 采用 UTF-8 BOM，便于 Excel 正确显示中文。变化列使用“百分点”；`BY校正后_log10_q` 保留极小概率；MLlib 的 Python 内存列留空，因为没有同口径数值。同目录另有字段说明和 `导出清单.json`，记录输入与 CSV 的 SHA-256。输入缺失、记录被修改或配对计数不一致时，导出会失败，不因输入校验失败覆盖已有表格。

无需下载数据即可运行导出功能的回归检查：

```powershell
& $pythonPath .\代码\验证结果导出.py
```

## 数据与实验范围

- 数据来源为 [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) 与 [H&M 数据](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data)。H&M 下载脚本使用 [Microsoft 公开镜像](https://huggingface.co/datasets/microsoft/hnm-search-data) 的基础交易与商品表，并校验文件哈希；使用数据须遵循各自的原始条款。
- 算法比较采用单项目步骤、严格跨篮、无限间隔的序列语义；同一购物篮内不定义先后关系。
- 既有分布式实验的两个执行器位于同一物理主机；YARN / HDFS 脚本是部署入口，真实多机部署仍需单独验证。
- `使用说明.md` 中的既有计数和结果路径对应原本地实验记录，这些记录不随代码仓库发布。
