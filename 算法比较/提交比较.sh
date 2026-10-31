#!/usr/bin/env bash
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(dirname -- "$task_dir")"
export SPARK_HOME="$project_dir/运行环境/pyspark"
export PYTHONPATH="$project_dir/运行环境${PYTHONPATH:+:$PYTHONPATH}"
export PYSPARK_PYTHON=/usr/bin/python3 PYSPARK_DRIVER_PYTHON=/usr/bin/python3
export PYTHONDONTWRITEBYTECODE=1 TZ=UTC SPARK_LOCAL_IP=127.0.0.1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export TMPDIR="$project_dir/临时文件/Spark"
export SPARK_LOCAL_DIRS="$TMPDIR/算法比较"
export JAVA_TOOL_OPTIONS="-Djava.io.tmpdir=$TMPDIR -Duser.timezone=UTC -XX:-UsePerfData"
mkdir -p "$SPARK_LOCAL_DIRS" "$project_dir/结果/算法比较/事件日志"
"$SPARK_HOME/bin/spark-submit" --master "${SPARK_MASTER:-spark://127.0.0.1:7079}" --deploy-mode client \
  --driver-memory 1536m --executor-memory 1536m --executor-cores 2 \
  --conf spark.cores.max=4 --conf spark.driver.maxResultSize=256m \
  --conf spark.python.worker.reuse=false --conf spark.executorEnv.TZ=UTC \
  --conf spark.eventLog.enabled=true --conf spark.eventLog.compress=false \
  --conf "spark.eventLog.dir=$project_dir/结果/算法比较/事件日志" \
  --conf "spark.sql.warehouse.dir=$TMPDIR/仓库" \
  --py-files "$task_dir/算法内核.py" "$task_dir/运行比较.py" "$@"
