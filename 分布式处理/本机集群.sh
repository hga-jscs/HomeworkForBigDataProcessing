#!/usr/bin/env bash
# Two separate worker JVMs on ONE host. This validates executor distribution,
# not physical multi-host scalability. All writable paths stay in the project.
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(dirname -- "$task_dir")"
export SPARK_HOME="${SPARK_HOME:-$project_dir/运行环境/pyspark}"
export TMPDIR="$project_dir/临时文件/Spark"
export SPARK_LOCAL_DIRS="$TMPDIR/集群缓存"
export SPARK_LOG_DIR="$project_dir/结果/集群日志"
export SPARK_PID_DIR="$TMPDIR/进程"
export SPARK_DAEMON_MEMORY=256m
export SPARK_LOCAL_IP=127.0.0.1
export PYTHONDONTWRITEBYTECODE=1
export TZ=UTC
export JAVA_TOOL_OPTIONS="-Djava.io.tmpdir=$TMPDIR -XX:-UsePerfData"
mkdir -p "$TMPDIR" "$SPARK_LOCAL_DIRS" "$SPARK_LOG_DIR" "$SPARK_PID_DIR"
action="${1:-start}"
case "$action" in
 start)
  "$SPARK_HOME/sbin/spark-daemon.sh" start org.apache.spark.deploy.master.Master 1 --host 127.0.0.1 --port 7079 --webui-port 8090
  for worker in 1 2; do
    "$SPARK_HOME/sbin/spark-daemon.sh" start org.apache.spark.deploy.worker.Worker "$worker" \
      --host 127.0.0.1 --port "$((7080+worker))" --webui-port "$((8090+worker))" \
      --cores 2 --memory 1536m --work-dir "$TMPDIR/工作节点$worker" spark://127.0.0.1:7079
  done
  ;;
 stop)
  for worker in 1 2; do
    "$SPARK_HOME/sbin/spark-daemon.sh" stop org.apache.spark.deploy.worker.Worker "$worker"
  done
  "$SPARK_HOME/sbin/spark-daemon.sh" stop org.apache.spark.deploy.master.Master 1
  ;;
 status)
  python3 -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8090/json/").read().decode())'
  ;;
 *) echo 'Usage: 本机集群.sh start|stop|status' >&2; exit 2 ;;
esac
