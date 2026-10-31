#!/usr/bin/env bash
# Deployment template. Requires an existing Hadoop/YARN cluster and shared HDFS.
set -euo pipefail
: "${SPARK_HOME:?Set Spark 4.0.1 installation directory}"
: "${HADOOP_CONF_DIR:?Set the course cluster Hadoop client configuration directory}"
: "${SPARK_JAVA_HOME:?Set Java 17 or 21 installed at this path on every node}"
: "${PYTHON_ENVIRONMENT_ARCHIVE:?Set HDFS URI of a packed Linux Python environment with numpy and scipy}"
: "${SPARK_EVENT_DIRECTORY:?Set writable HDFS URI for Spark event logs}"
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
config="${1:?Pass a JSON configuration containing absolute HDFS input/output URIs}"
stage="${2:-全部}"
# No {project} placeholders are allowed in a remote-cluster configuration.
if python3 -c 'import sys; sys.exit(0 if "{project}" in open(sys.argv[1],encoding="utf-8").read() else 1)' "$config"; then
  echo 'Replace {project} with absolute HDFS URIs in the cluster configuration.' >&2; exit 2
fi
export JAVA_HOME="$SPARK_JAVA_HOME"
"$SPARK_HOME/bin/spark-submit" --master yarn --deploy-mode cluster \
  --num-executors "${EXECUTORS:-4}" --executor-cores "${EXECUTOR_CORES:-4}" \
  --executor-memory "${EXECUTOR_MEMORY:-4g}" --driver-memory "${DRIVER_MEMORY:-2g}" \
  --archives "$PYTHON_ENVIRONMENT_ARCHIVE#environment" \
  --conf spark.pyspark.python=./environment/bin/python \
  --conf spark.yarn.appMasterEnv.TZ=UTC --conf spark.executorEnv.TZ=UTC \
  --conf "spark.yarn.appMasterEnv.JAVA_HOME=$SPARK_JAVA_HOME" \
  --conf "spark.executorEnv.JAVA_HOME=$SPARK_JAVA_HOME" \
  --conf spark.driver.maxResultSize=256m \
  --conf spark.eventLog.enabled=true --conf "spark.eventLog.dir=$SPARK_EVENT_DIRECTORY" \
  --files "$config" --py-files "$task_dir/数据适配.py,$task_dir/模式分析.py" \
  "$task_dir/作业.py" --config "$(basename -- "$config")" --stage "$stage"
