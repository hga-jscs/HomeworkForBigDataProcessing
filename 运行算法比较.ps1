param(
    [string]$PythonPath = 'C:\Users\何高昂\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',
    [switch]$OnlyReport,
    [switch]$Pilot,
    [switch]$ExternalCluster
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
if (-not (Test-Path -LiteralPath $PythonPath)) { throw '请用 -PythonPath 指定现有 Python 3.12 解释器。' }
if (-not $OnlyReport) {
    & $PythonPath (Join-Path $projectPath '算法比较\验证算法.py')
    if ($LASTEXITCODE -ne 0) { throw '算法正确性检查失败。' }
    if (-not (Test-Path -LiteralPath (Join-Path $projectPath '运行环境\pyspark'))) {
        & (Join-Path $projectPath '安装Spark.ps1') -PythonPath $PythonPath
    }
    $convertedPath = & wsl -d Ubuntu --exec wslpath -u $projectPath
    if ($LASTEXITCODE -ne 0 -or -not $convertedPath) { throw '无法转换 D 盘项目路径。' }
    $linuxProject = ($convertedPath -join "`n").Trim()
    $phase = if ($Pilot) { 'pilot' } else { 'formal' }
    try {
        if (-not $ExternalCluster) {
            & wsl -d Ubuntu --exec bash "$linuxProject/分布式处理/本机集群.sh" start
            if ($LASTEXITCODE -ne 0) { throw '工作进程启动失败。' }
        }
        & wsl -d Ubuntu --exec bash "$linuxProject/算法比较/提交比较.sh" --phase $phase
        if ($LASTEXITCODE -ne 0) { throw '算法比较失败；保留原始记录，可按同一协议恢复。' }
    } finally {
        if (-not $ExternalCluster) {
            & wsl -d Ubuntu --exec bash "$linuxProject/分布式处理/本机集群.sh" stop
        }
    }
    if ($Pilot) { Write-Host '试跑完成，结果保存在 结果\算法比较\试跑。'; return }
}
& $PythonPath (Join-Path $projectPath '算法比较\汇总比较.py')
if ($LASTEXITCODE -ne 0) { throw '正式实验不完整或一致性核验失败。' }
& $PythonPath (Join-Path $projectPath '算法比较\诊断波动.py')
if ($LASTEXITCODE -ne 0) { throw '耗时波动诊断失败。' }
& $PythonPath (Join-Path $projectPath '算法比较\核对既有模式.py')
if ($LASTEXITCODE -ne 0) { throw '与既有完整模式的核对失败。' }
& $PythonPath (Join-Path $projectPath '代码\生成对比报告.py')
if ($LASTEXITCODE -ne 0) { throw '报告生成失败。' }
& $PythonPath (Join-Path $projectPath '代码\检查对比报告.py')
if ($LASTEXITCODE -ne 0) { throw '报告结构检查失败。' }
Write-Host '完成：上一层目录为新的八页对比报告。PDF 交付前仍应检查每页渲染。'
