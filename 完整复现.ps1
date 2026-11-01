param(
    [string]$PythonPath = 'C:\Users\何高昂\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',
    [switch]$OnlyReport
)
$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TEMP = Join-Path $projectPath '临时文件'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
$env:MPLCONFIGDIR = Join-Path $env:TEMP '绘图库缓存'
$env:PIP_CACHE_DIR = Join-Path $env:TEMP '安装缓存'
$env:OPENBLAS_NUM_THREADS = '4'
$env:OMP_NUM_THREADS = '4'
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw '未找到 Python。请用 -PythonPath 指定现有的 Python 3.12 解释器。'
}
if (-not (Test-Path -LiteralPath (Join-Path $projectPath '依赖\duckdb'))) {
    & $PythonPath -m pip install --target (Join-Path $projectPath '依赖') -r (Join-Path $projectPath '依赖版本.txt') --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
}
if (-not $OnlyReport) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectPath '结果\跨年变化.json'))) {
        & (Join-Path $projectPath '复现单机基准.ps1') -PythonPath $PythonPath
    }
    & $PythonPath (Join-Path $projectPath '代码\下载服装数据.py')
    if ($LASTEXITCODE -ne 0) { throw '数据下载失败' }
    & (Join-Path $projectPath '安装Spark.ps1') -PythonPath $PythonPath
    & (Join-Path $projectPath '运行分布式实验.ps1') -Dataset '零售交易'
    & (Join-Path $projectPath '运行分布式实验.ps1') -Dataset '零售日级'
    $convertedPath = & wsl -d Ubuntu --exec wslpath -u $projectPath
    if ($LASTEXITCODE -ne 0 -or -not $convertedPath) { throw '无法转换 D 盘项目路径' }
    $linuxProject=($convertedPath -join "`n").Trim()
    try {
        & wsl -d Ubuntu --exec bash "$linuxProject/分布式处理/本机集群.sh" start
        if ($LASTEXITCODE -ne 0) { throw '工作节点启动失败' }
        & (Join-Path $projectPath '运行分布式实验.ps1') -Dataset '服装交易' -Cluster
    } finally {
        & wsl -d Ubuntu --exec bash "$linuxProject/分布式处理/本机集群.sh" stop
    }
    & wsl -d Ubuntu --exec bash "$linuxProject/分布式处理/运行校验.sh"
    if ($LASTEXITCODE -ne 0) { throw '分布式语义校验失败' }
    & $PythonPath (Join-Path $projectPath '代码\汇总框架实验.py')
    if ($LASTEXITCODE -ne 0) { throw '结果汇总失败' }
}
& (Join-Path $projectPath '运行算法比较.ps1') -PythonPath $PythonPath -OnlyReport:$OnlyReport
Write-Host '完成。报告位于上一层目录，CSV 结果表位于 结果\成果。'
