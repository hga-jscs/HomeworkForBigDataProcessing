"""Exercise CSV semantics and failure handling without Spark or external data."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from 导出结果 import ROOT, DATASETS, PATTERN_FIELDS, CHANGE_FIELDS, export_results


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def fixture(project, empty=False):
    formal = project / '结果' / '算法比较' / '正式'
    scenarios, summaries, artifacts = [], {}, []
    for name, batch, _ in DATASETS:
        scenario = {'name': name, 'dataset': 'fashion' if batch == '服装日级' else 'retail',
                    'fraction': 100, 'support': .2, 'maximum': 3, 'repeats': 1}
        scenarios.append(scenario)
        items = ['type:272', 'type:274'] if batch == '服装日级' else ['A', 'B']
        patterns = [] if empty else [[[items[0]], 7], [[items[1]], 6], [items, 4]]
        descriptor = {'customers': 10, 'baskets': 30}
        summaries[name] = {'configuration': scenario, 'input': descriptor,
                           'patterns': len(patterns), 'all_outputs_exactly_equal': True}
        for method in ['GSP', 'MLlib']:
            pattern_file = formal / '完整模式' / f'{name}_{method}.json'
            record_file = formal / '原始记录' / f'{name}_{method}_第1次.json'
            write_json(pattern_file, patterns)
            record = {'status': 'complete', 'scenario': scenario, 'method': method, 'repeat': 1,
                      'exactly_equal_to_other_methods': True, 'input': descriptor,
                      'wall_seconds': 1.25, 'patterns': len(patterns)}
            if method == 'GSP':
                record['partition_metrics'] = [{'peak_python_rss_bytes': 1048576}]
                record['candidate_union'] = len(patterns)
            write_json(record_file, record)
            for path in [pattern_file, record_file]:
                artifacts.append({'file': path.relative_to(project).as_posix(),
                                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        config = {'minimum_support': .2, 'maximum_length': 3,
                  'periods': [['2022-01-01', '2022-02-01'], ['2023-01-01', '2023-02-01']]}
        base = project / '数据' / '分布式仓库' / '运行批次' / batch
        write_json(base / '模式' / '_完成.json', {'configuration': config,
                   'configuration_sha256': 'fixture', 'metrics': {'discovery_customers': 10}})
        write_json(base / '变化' / '_完成.json', {'configuration': config,
                   'configuration_sha256': 'fixture',
                   'metrics': {'tested_patterns': 0 if empty else 1, 'evaluation_customers': 20}})
        changes = [] if empty else [{'pattern': items, 'pattern_id': batch, 'customers': 20,
            'count0': 4, 'count1': 2, 'discordant0': 3, 'discordant1': 1,
            'support0': .2, 'support1': .1, 'delta': -.1, 'q_by': 0., 'log10_q_by': -400.}]
        write_json(base / '变化' / '完整统计.json', changes)
    protocol = {'phase': 'formal', 'algorithms': ['GSP', 'MLlib'], 'scenarios': scenarios}
    write_json(formal / '实验协议.json', protocol)
    write_json(project / '结果' / '算法比较汇总.json', {
        'protocol': protocol, 'complete_runs': 4, 'scenarios': summaries, 'artifacts': artifacts})


class ResultExportTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '临时文件'
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='结果导出测试-', dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        self.output = self.project / '结果' / '成果'
        fixture(self.project)

    def rows(self, name):
        with (self.output / name).open(encoding='utf-8-sig', newline='') as handle:
            return list(csv.DictReader(handle))

    def test_counts_windows_and_thresholds_come_from_results(self):
        result = export_results(self.project)
        self.assertEqual(result['rows'], {'频繁模式.csv': 6, '行为变化.csv': 2, '算法测量.csv': 4})
        pattern = next(x for x in self.rows('频繁模式.csv') if x['模式名称'] == '长裤 → 短裤')
        self.assertEqual(pattern['发现集顾客数'], '10')
        self.assertEqual(float(pattern['顾客支持度_%']), 40.)
        self.assertEqual(float(pattern['支持度阈值_%']), 20.)
        self.assertEqual(pattern['发现期'], '2022-01-01 至 2022-01-31')

    def test_pair_counts_percentage_points_and_underflow(self):
        export_results(self.project)
        row = self.rows('行为变化.csv')[0]
        self.assertEqual([int(row[k]) for k in ['两期均匹配人数', '仅前期匹配人数',
                         '仅后期匹配人数', '两期均未匹配人数']], [1, 3, 1, 15])
        self.assertEqual(float(row['变化_百分点']), -10.)
        self.assertEqual(row['BY判定_阈值0.05'], '显著下降')
        self.assertEqual(float(row['BY校正后_log10_q']), -400.)

    def test_excel_encoding_and_native_memory(self):
        export_results(self.project)
        self.assertTrue((self.output / '频繁模式.csv').read_bytes().startswith(b'\xef\xbb\xbf'))
        for row in self.rows('算法测量.csv'):
            self.assertEqual(row['单进程最大Python内存_MiB'], '' if row['算法实现'] == 'MLlib' else '1.0')

    def test_empty_pattern_and_change_tables_keep_headers(self):
        fixture(self.project, empty=True)
        export_results(self.project)
        for name, fields in [('频繁模式.csv', PATTERN_FIELDS), ('行为变化.csv', CHANGE_FIELDS)]:
            with (self.output / name).open(encoding='utf-8-sig', newline='') as handle:
                self.assertEqual(list(csv.reader(handle)), [fields])

    def test_missing_record_keeps_previous_output(self):
        self.output.mkdir(parents=True)
        previous = self.output / '频繁模式.csv'
        previous.write_bytes(b'previous result')
        (self.project / '结果' / '算法比较' / '正式' / '原始记录' / '服装全量_GSP_第1次.json').unlink()
        with self.assertRaises(FileNotFoundError):
            export_results(self.project)
        self.assertEqual(previous.read_bytes(), b'previous result')

    def test_tampered_audited_patterns_are_rejected(self):
        path = self.project / '结果' / '算法比较' / '正式' / '完整模式' / '服装全量_GSP.json'
        write_json(path, [])
        with self.assertRaisesRegex(ValueError, '已被修改'):
            export_results(self.project)
        self.assertFalse(self.output.exists())

    def test_inconsistent_paired_cohort_is_rejected(self):
        path = self.project / '数据' / '分布式仓库' / '运行批次' / '服装日级' / '变化' / '完整统计.json'
        changes = json.loads(path.read_text(encoding='utf-8'))
        changes[0]['customers'] = 21
        write_json(path, changes)
        with self.assertRaisesRegex(ValueError, '配对计数不一致'):
            export_results(self.project)

    def test_other_output_directory_and_missing_name_dictionary(self):
        export_results(self.project, '其他结果')
        self.assertFalse(self.output.exists())
        with (self.project / '其他结果' / '频繁模式.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(any(x['模式名称'] == 'A → B' and x['原始名称'] == 'A → B' for x in rows))


if __name__ == '__main__':
    unittest.main(verbosity=2)
