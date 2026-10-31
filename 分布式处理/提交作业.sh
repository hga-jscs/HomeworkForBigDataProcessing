#!/usr/bin/env bash
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(dirname -- "$task_dir")"
export SEQUENCE_PROJECT="${SEQUENCE_PROJECT:-$project_dir}"
export SPARK_HOME="${SPARK_HOME:-$project_dir/运行环境/pyspark}"
export PYTHONPATH="$project_dir/运行环境${PYTHONPATH:+:$PYTHONPATH}"
export PYSPARK_PYTHON="${PYSPARK_PYTHON:-/usr/bin/python3}"
export PYSPARK_DRIVER_PYTHON="$PYSPARK_PYTHON"
export PYTHONDONTWRITEBYTECODE=1
export TZ=UTC
export TMPDIR="$project_dir/临时文件/Spark"
export SPARK_LOCAL_DIRS="$TMPDIR/计算缓存"
export SPARK_LOG_DIR="$project_dir/结果/集群日志"
export SPARK_PID_DIR="$TMPDIR/进程"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
mkdir -p "$TMPDIR" "$SPARK_LOCAL_DIRS" "$SPARK_LOG_DIR" "$SPARK_PID_DIR" "$project_dir/结果/Spark事件"
export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:-} -Djava.io.tmpdir=$TMPDIR -Duser.timezone=UTC -XX:-UsePerfData"
config_file="${1:-$task_dir/参数/零售交易.json}"
stage="${2:-全部}"
master="${SPARK_MASTER:-local[4]}"
"$SPARK_HOME/bin/spark-submit" --master "$master" --deploy-mode client \
  --driver-memory "${DRIVER_MEMORY:-3g}" \
  --conf spark.driver.maxResultSize=256m \
  --conf spark.executor.memory="${EXECUTOR_MEMORY:-1536m}" \
  --conf spark.executor.cores=2 --conf spark.cores.max=4 \
  --conf spark.executorEnv.TZ=UTC \
  --conf spark.eventLog.enabled=true --conf spark.eventLog.compress=false \
  --conf "spark.eventLog.dir=$project_dir/结果/Spark事件" \
  --conf "spark.sql.warehouse.dir=$project_dir/临时文件/Spark/仓库" \
  --py-files "$task_dir/数据适配.py,$task_dir/模式分析.py" \
  "$task_dir/作业.py" --config "$config_file" --stage "$stage"
