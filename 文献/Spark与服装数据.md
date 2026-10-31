# 本次框架扩展的技术与数据依据

访问日期：2026-10-31。以下是实际查阅的主要来源；实验数字来自本地运行，不引用外部基准数字替代。

| 来源 | 对实现的作用 |
|---|---|
| [Zaharia et al., NSDI 2012, pp. 15–28](https://www.usenix.org/conference/nsdi12/technical-sessions/presentation/zaharia) | RDD 的分区变换、迭代复用和故障恢复抽象；本项目不声称自行实现 Spark 调度器。 |
| [PySpark 4.0.1 安装](https://spark.apache.org/docs/4.0.1/api/python/getting_started/install.html) | 固定版本、Python 与 Java 前置条件；使用现有 Python 3.12 和 Java 21。 |
| [MLlib Frequent Pattern Mining](https://spark.apache.org/docs/4.0.1/ml-frequent-pattern-mining.html) | PrefixSpan 参数与 array-of-arrays 输入；原生允许篮内多项目模式，项目输出额外限制单项目步骤。 |
| [RDD Programming Guide](https://spark.apache.org/docs/4.0.1/rdd-programming-guide.html) | 广播有界目录，分区内匹配，再归并充分统计量；不向 Driver 收集原始顾客数据。 |
| [SQL Performance Tuning](https://spark.apache.org/docs/4.0.1/sql-performance-tuning.html) | 小维表广播、分区数量、文件切片和自适应执行；这些优化不保证线性扩展。 |
| [Standalone](https://spark.apache.org/docs/4.0.1/spark-standalone.html) | 单主机上启动独立 Master / Worker 进程进行部署验证。 |
| [Running on YARN](https://spark.apache.org/docs/4.0.1/running-on-yarn.html) | 集群模式、Hadoop 客户端配置与 Python 环境分发；Spark 4 和原 Hadoop 服务的 JDK 需分别配置。 |
| [H&M Kaggle 原始数据](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data) | 基础交易、商品与顾客表的来源；本任务不复现原推荐竞赛。 |
| [Microsoft hnm-search-data](https://huggingface.co/datasets/microsoft/hnm-search-data) | 公开镜像中 `data/raw` 的真实基础交易表；仅取对应完整 Parquet 转换，不使用新增的合成搜索数据。 |

H&M 文件获取通过 Hugging Face 的公开转换分支，固定 commit 和 LFS SHA-256 详见 `结果/服装数据来源.json`。该分支包含 7 个交易文件，本地独立核验合计 31,788,324 行。原始交易只有日期，不含订单编号或时分秒；日购物篮是分析定义。镜像说明对新增合成数据给出的许可与基础交易使用条款有区别，已在使用说明中分别标注。

报告沿用并重新整理了 PrefixSpan、SPADE、SPEck、HOPPER、流程漂移与 BY 的已有文献；原索引及可获得的全文继续保留在同目录。最新框架报告的参考文献序号与原单机报告不完全相同。
