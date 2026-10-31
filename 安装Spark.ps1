param([string]$PythonPath='C:\Users\何高昂\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
$ErrorActionPreference='Stop'
$env:TEMP=Join-Path $PSScriptRoot '临时文件'
$env:TMP=$env:TEMP
$env:PIP_CACHE_DIR=Join-Path $env:TEMP '安装缓存'
$env:PYTHONDONTWRITEBYTECODE='1'
$runtime=Join-Path $PSScriptRoot '运行环境'
if (-not (Test-Path -LiteralPath (Join-Path $runtime 'pyspark\bin\spark-submit'))) {
    & $PythonPath -m pip install --no-cache-dir --target $runtime pyspark==4.0.1 py4j==0.10.9.9
    if ($LASTEXITCODE -ne 0) { throw 'Spark 安装失败' }
}
& wsl -d Ubuntu --exec env PYTHONDONTWRITEBYTECODE=1 python3 -c 'import numpy,scipy; print("Linux scientific runtime:",numpy.__version__,scipy.__version__)'
if ($LASTEXITCODE -ne 0) { throw 'Linux Python 缺少 numpy 或 scipy；请在 D 盘 Linux 环境中准备依赖后继续' }
& wsl -d Ubuntu --exec java -version
if ($LASTEXITCODE -ne 0) { throw '请准备 Java 17 或 21' }
