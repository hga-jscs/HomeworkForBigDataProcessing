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
$steps = if ($OnlyReport) { @('生成报告.py') } else { @('准备数据.py','验证算法.py','整理交易.py','运行实验.py','解释结果.py','分解变化.py','生成报告.py') }
foreach ($step in $steps) {
    Write-Host "运行：$step"
    & $PythonPath (Join-Path $projectPath "代码\$step")
    if ($LASTEXITCODE -ne 0) { throw "执行失败：$step" }
}
Write-Host '完成。单机基准报告位于结果目录；当前框架报告由完整复现.ps1 生成。'
