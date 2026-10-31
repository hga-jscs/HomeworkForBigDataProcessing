#!/usr/bin/env bash
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(dirname -- "$task_dir")"
export SPARK_HOME="${SPARK_HOME:-$project_dir/运行环境/pyspark}"
export PYTHONPATH="$project_dir/运行环境${PYTHONPATH:+:$PYTHONPATH}"
export PYSPARK_PYTHON=/usr/bin/python3 PYSPARK_DRIVER_PYTHON=/usr/bin/python3
export PYTHONDONTWRITEBYTECODE=1 TZ=UTC
export TMPDIR="$project_dir/临时文件/Spark"
export SPARK_LOCAL_DIRS="$TMPDIR/校验缓存"
export JAVA_TOOL_OPTIONS="-Djava.io.tmpdir=$TMPDIR -Duser.timezone=UTC -XX:-UsePerfData"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
mkdir -p "$SPARK_LOCAL_DIRS"
"$SPARK_HOME/bin/spark-submit" --master 'local[2]' --driver-memory 1536m \
  --conf "spark.sql.warehouse.dir=$TMPDIR/仓库" \
  --py-files "$task_dir/数据适配.py,$task_dir/模式分析.py" "$task_dir/校验框架.py"
