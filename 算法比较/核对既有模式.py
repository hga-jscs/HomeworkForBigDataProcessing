"""Read saved Spark output with DuckDB and compare all real-data supports."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'代码'))
from 公共设置 import save_json
import duckdb

def main():
    connection=duckdb.connect(config={'threads':1,'memory_limit':'256MB',
        'temp_directory':str(ROOT/'临时文件'/'模式核对')})
    checked={}
    for scenario,dataset in [('零售全量','零售分钟'),('服装全量','服装日级')]:
        source=ROOT/'数据'/'分布式仓库'/'运行批次'/dataset/'模式'/'发现模式'
        old={tuple(pattern):count for pattern,count in connection.execute('SELECT pattern, freq FROM read_parquet(?)',[str(source/'*.parquet')]).fetchall()}
        for method in ['GSP','PrefixSpan','SPADE','SPAM','MLlib']:
            file=ROOT/'结果'/'算法比较'/'正式'/'完整模式'/f'{scenario}_{method}.json'
            current={tuple(pattern):count for pattern,count in json.loads(file.read_text(encoding='utf-8'))}
            assert old==current,(scenario,method)
        checked[scenario]={'patterns_checked_per_method':len(old),'methods':5,'all_equal':True}
    connection.close()
    save_json('既有模式核对.json',{'engine':'DuckDB '+duckdb.__version__,'checks':checked,'passed':True})
    print(json.dumps(checked,ensure_ascii=False))

if __name__=='__main__':main()
