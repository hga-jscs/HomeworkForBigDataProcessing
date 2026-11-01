"""Export audited experiment results as readable CSV tables (standard library only)."""
import argparse
import csv
import hashlib
import json
import math
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASETS = [
    ('服装全量', '服装日级', 'H&M'),
    ('零售全量', '零售分钟', 'Online Retail II'),
]
FASHION_NAMES = {
    'type:245': '针织开衫', 'type:252': '毛衣', 'type:253': '背心上衣',
    'type:254': '上衣', 'type:255': 'T恤', 'type:258': '女式衬衫',
    'type:259': '衬衫', 'type:262': '夹克', 'type:264': '西装外套',
    'type:265': '连衣裙', 'type:267': '连体衣裤', 'type:272': '长裤',
    'type:273': '打底裤／连裤袜', 'type:274': '短裤', 'type:275': '半身裙',
    'type:286': '内裤', 'type:297': '睡衣套装', 'type:298': '比基尼上衣',
    'type:302': '袜子', 'type:306': '文胸', 'type:308': '连帽衫',
    'type:57': '连体泳衣', 'type:59': '泳装下装', 'type:66': '包',
    'type:67': '腰带', 'type:70': '耳饰', 'type:77': '项链',
    'type:78': '其他配饰', 'type:80': '围巾', 'type:81': '太阳镜',
    'type:87': '靴子', 'type:91': '凉鞋', 'type:94': '运动鞋',
}
PATTERN_FIELDS = [
    '数据集', '发现期', '发现集顾客数', '支持度阈值_%', '模式步数',
    '模式编码', '模式名称', '原始名称', '支持顾客数', '顾客支持度_%',
]
CHANGE_FIELDS = [
    '数据集', '前期', '后期', '评估顾客数', '模式编码', '模式名称',
    '前期匹配人数', '后期匹配人数', '前期支持度_%', '后期支持度_%',
    '变化_百分点', '两期均匹配人数', '仅前期匹配人数', '仅后期匹配人数',
    '两期均未匹配人数', 'BY校正后_log10_q', 'BY判定_阈值0.05', '原始模式标识',
]
MEASUREMENT_FIELDS = [
    '实验场景', '算法实现', '重复编号', '发现集顾客数', '购物篮数',
    '支持度阈值_%', '最长步数', '耗时_秒', '输出模式数',
    '单进程最大Python内存_MiB', '候选并集数', '同场景输出完全一致', '原始记录',
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def period_label(window):
    start, stop = map(date.fromisoformat, window)
    require(start < stop, f'无效观察窗口：{window}')
    return f'{start.isoformat()} 至 {(stop - timedelta(days=1)).isoformat()}'


def prepare_tables(project):
    """Read and validate all inputs before replacing any existing output."""
    sources = {}

    def read(path, optional=False):
        if optional and not path.exists():
            return {}
        content = path.read_bytes()
        sources[path.relative_to(project).as_posix()] = hashlib.sha256(content).hexdigest()
        return json.loads(content.decode('utf-8-sig'))

    summary = read(project / '结果' / '算法比较汇总.json')
    formal = project / '结果' / '算法比较' / '正式'
    protocol = read(formal / '实验协议.json')
    require(protocol['phase'] == 'formal' and summary['protocol'] == protocol,
            '正式协议与汇总不一致，请先运行 算法比较/汇总比较.py。')
    fingerprints = {x['file'].replace('\\', '/'): x['sha256'] for x in summary['artifacts']}

    def audited_read(path):
        value = read(path)
        key = path.relative_to(project).as_posix()
        require(fingerprints.get(key) == sources[key], f'文件未经过汇总核验或已被修改：{key}')
        return value

    fashion_names = read(project / '结果' / '服装类别名称.json', optional=True)
    product_names = read(project / '数据' / '商品说明.json', optional=True)

    def description(pattern, fashion, original=False):
        if fashion:
            labels = fashion_names if original else {**fashion_names, **FASHION_NAMES}
        else:
            labels = product_names
        return ' → '.join(labels.get(x, x).strip() for x in pattern)

    pattern_rows, change_rows, measurement_rows = [], [], []
    for scenario_name, batch, label in DATASETS:
        scenario = summary['scenarios'][scenario_name]
        configuration = scenario['configuration']
        require(configuration in protocol['scenarios'] and configuration['fraction'] == 100,
                f'缺少全量主设置：{scenario_name}')
        base = project / '数据' / '分布式仓库' / '运行批次' / batch
        mining = read(base / '模式' / '_完成.json')
        change = read(base / '变化' / '_完成.json')
        config = mining['configuration']
        require(config == change['configuration'] and
                mining['configuration_sha256'] == change['configuration_sha256'],
                f'{batch} 的模式和变化来自不同配置。')
        require(config['minimum_support'] == configuration['support'] and
                config['maximum_length'] == configuration['maximum'],
                f'{batch} 的框架参数与算法比较主设置不一致。')
        n = scenario['input']['customers']
        require(n > 0 and n == mining['metrics']['discovery_customers'],
                f'{batch} 的发现集人数不一致或为空。')
        earlier, later = map(period_label, config['periods'])
        patterns = None
        for method in protocol['algorithms']:
            current = audited_read(formal / '完整模式' / f'{scenario_name}_{method}.json')
            if patterns is None:
                patterns = current
            require(current == patterns, f'{scenario_name} 的模式或支持数在实现之间不一致。')
        require(patterns is not None and len(patterns) == scenario['patterns'],
                f'{scenario_name} 的模式数量与汇总不一致。')
        require(len({tuple(p) for p, _ in patterns}) == len(patterns), f'{scenario_name} 有重复模式。')
        fashion = batch == '服装日级'
        for pattern, count in sorted(patterns, key=lambda x: (len(x[0]), -x[1], x[0])):
            require(1 <= len(pattern) <= configuration['maximum'] and
                    math.ceil(configuration['support'] * n) <= count <= n,
                    f'{scenario_name} 的模式长度或支持数越界：{pattern}')
            pattern_rows.append({
                '数据集': label, '发现期': earlier, '发现集顾客数': n,
                '支持度阈值_%': configuration['support'] * 100, '模式步数': len(pattern),
                '模式编码': ' → '.join(pattern), '模式名称': description(pattern, fashion),
                '原始名称': description(pattern, fashion, original=True),
                '支持顾客数': count, '顾客支持度_%': count / n * 100,
            })
        changes = read(base / '变化' / '完整统计.json')
        metrics = change['metrics']
        candidates = {tuple(p) for p, _ in patterns if len(p) >= 2}
        require(len(changes) == metrics['tested_patterns'] == len(candidates) and
                {tuple(x['pattern']) for x in changes} == candidates,
                f'{batch} 的变化候选与主设置模式不一致。')
        for x in sorted(changes, key=lambda x: (x['log10_q_by'], x['pattern'])):
            customers = x['customers']
            both = x['count0'] - x['discordant0']
            neither = customers - both - x['discordant0'] - x['discordant1']
            require(customers > 0 and customers == metrics['evaluation_customers'] and
                    both == x['count1'] - x['discordant1'] and
                    min(both, neither, x['discordant0'], x['discordant1']) >= 0,
                    f'{batch} 的配对计数不一致：{x["pattern"]}')
            for actual, expected in [(x['support0'], x['count0'] / customers),
                                     (x['support1'], x['count1'] / customers),
                                     (x['delta'], (x['count1'] - x['count0']) / customers)]:
                require(math.isclose(actual, expected, abs_tol=1e-12), '支持度与人数不一致。')
            log_q = x['log10_q_by']
            require(log_q <= 0, '校正概率的 log10 值无效。')
            significant = log_q <= math.log10(.05)
            decision = '未检出显著变化'
            if significant and x['delta'] != 0:
                decision = '显著上升' if x['delta'] > 0 else '显著下降'
            change_rows.append({
                '数据集': label, '前期': earlier, '后期': later, '评估顾客数': customers,
                '模式编码': ' → '.join(x['pattern']), '模式名称': description(x['pattern'], fashion),
                '前期匹配人数': x['count0'], '后期匹配人数': x['count1'],
                '前期支持度_%': x['support0'] * 100, '后期支持度_%': x['support1'] * 100,
                '变化_百分点': x['delta'] * 100, '两期均匹配人数': both,
                '仅前期匹配人数': x['discordant0'], '仅后期匹配人数': x['discordant1'],
                '两期均未匹配人数': neither, 'BY校正后_log10_q': log_q,
                'BY判定_阈值0.05': decision, '原始模式标识': x['pattern_id'],
            })

    # Follow the frozen protocol, so stale extra files and pilot runs are not mixed in.
    for scenario in protocol['scenarios']:
        expected = summary['scenarios'][scenario['name']]
        require(expected['all_outputs_exactly_equal'], f'{scenario["name"]} 尚未通过一致性核验。')
        for method in protocol['algorithms']:
            for repeat in range(1, scenario['repeats'] + 1):
                path = formal / '原始记录' / f'{scenario["name"]}_{method}_第{repeat}次.json'
                x = audited_read(path)
                require(x['status'] == 'complete' and x['scenario'] == scenario and
                        x['method'] == method and x['repeat'] == repeat and
                        x['exactly_equal_to_other_methods'] and x['input'] == expected['input'] and
                        x['patterns'] == expected['patterns'], f'正式运行记录不完整或不一致：{path.name}')
                rss = [m['peak_python_rss_bytes'] / 1048576 for m in x.get('partition_metrics', [])]
                measurement_rows.append({
                    '实验场景': scenario['name'], '算法实现': method, '重复编号': repeat,
                    '发现集顾客数': x['input']['customers'], '购物篮数': x['input']['baskets'],
                    '支持度阈值_%': scenario['support'] * 100, '最长步数': scenario['maximum'],
                    '耗时_秒': x['wall_seconds'], '输出模式数': x['patterns'],
                    '单进程最大Python内存_MiB': max(rss) if rss else '',
                    '候选并集数': x.get('candidate_union', ''), '同场景输出完全一致': '是',
                    '原始记录': path.relative_to(project).as_posix(),
                })
    expected_runs = sum(x['repeats'] for x in protocol['scenarios']) * len(protocol['algorithms'])
    require(len(measurement_rows) == summary['complete_runs'] == expected_runs, '正式运行次数不完整。')
    tables = {
        '频繁模式.csv': (PATTERN_FIELDS, pattern_rows),
        '行为变化.csv': (CHANGE_FIELDS, change_rows),
        '算法测量.csv': (MEASUREMENT_FIELDS, measurement_rows),
    }
    return tables, sources


def export_results(project=ROOT, output=None):
    project = Path(project).resolve()
    output = Path(output) if output is not None else Path('结果') / '成果'
    if not output.is_absolute():
        output = project / output
    tables, sources = prepare_tables(project)
    counts = {name: len(rows) for name, (_, rows) in tables.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.结果导出-', dir=output.parent) as temporary:
        staging = Path(temporary)
        for name, (fields, rows) in tables.items():
            with (staging / name).open('w', encoding='utf-8-sig', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        description = f'''# 项目结果

本目录由 `代码/导出结果.py` 从已核验的正式实验与分布式批次输出生成。
CSV 使用 UTF-8 BOM，可直接用 Excel 打开；空表也保留完整表头。

| 文件 | 一行代表什么 | 行数 |
| --- | --- | ---: |
| 频繁模式.csv | 主设置中的购买顺序、支持人数与支持度 | {counts['频繁模式.csv']:,} |
| 行为变化.csv | 一个二步或三步候选模式的前后期配对统计 | {counts['行为变化.csv']:,} |
| 算法测量.csv | 正式协议中的一个场景、一个实现、一次测量 | {counts['算法测量.csv']:,} |

频繁模式与行为变化覆盖 H&M 和 Online Retail II 的全量主设置；算法测量覆盖正式协议的全部场景。
人数、观察窗口、阈值和重复次数均从现有结果读取。支持度分母是对应发现集或评估集的顾客数；
箭头表示严格跨购物篮的先后关系，允许中间出现其他购买，同一顾客只计一次。

变化字段以百分点计。四类配对人数之和等于评估顾客数；BY 判定采用 q≤0.05，
保留 log10(q) 以表达可能低于普通浮点范围的概率。内存列是单个 Python 工作进程最大 RSS，
MLlib 没有同口径数值，留空。商品名称表可选，缺失的名称保留编码。

原始模式及运行记录位于项目的 `结果/算法比较/正式/`；变化统计位于
`数据/分布式仓库/运行批次/服装日级/变化/完整统计.json` 和零售分钟的对应路径。
`导出清单.json` 记录本次读取文件的 SHA-256、输出行数与 CSV 哈希。
'''
        (staging / '说明.md').write_text(description, encoding='utf-8')
        manifest = {
            'format_version': 1, 'rows': counts, 'sources': sources,
            'outputs': {name: hashlib.sha256((staging / name).read_bytes()).hexdigest() for name in tables},
        }
        (staging / '导出清单.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        output.mkdir(parents=True, exist_ok=True)
        for path in staging.iterdir():
            path.replace(output / path.name)
    return {'output': str(output), 'rows': counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=ROOT, help='项目根目录；默认按脚本位置定位')
    parser.add_argument('--output', type=Path, help='输出目录；相对路径按项目根目录解析，默认 结果/成果')
    args = parser.parse_args()
    try:
        result = export_results(args.project, args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'结果导出失败：{error}\n请先完成正式算法比较及两个主批次的变化分析；已有 CSV 未因输入校验失败而替换。', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
