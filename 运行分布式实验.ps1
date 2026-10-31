param(
    [ValidateSet('零售交易','服装交易','零售日级')][string]$Dataset = '零售交易',
    [ValidateSet('全部','清洗','序列','模式','变化')][string]$Stage = '全部',
    [switch]$Cluster
)
$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$convertedPath = & wsl -d Ubuntu --exec wslpath -u $projectPath
if ($LASTEXITCODE -ne 0 -or -not $convertedPath) { throw '无法转换 D 盘项目路径' }
$linuxProject = ($convertedPath -join "`n").Trim()
$entry = "$linuxProject/分布式处理/提交作业.sh"
$config = "$linuxProject/分布式处理/参数/$Dataset.json"
if ($Cluster) {
    & wsl -d Ubuntu --exec env 'SPARK_MASTER=spark://127.0.0.1:7079' 'DRIVER_MEMORY=1536m' 'SPARK_LOCAL_IP=127.0.0.1' bash $entry $config $Stage
} else {
    & wsl -d Ubuntu --exec bash $entry $config $Stage
}
if ($LASTEXITCODE -ne 0) { throw "Spark 退出码：$LASTEXITCODE" }
