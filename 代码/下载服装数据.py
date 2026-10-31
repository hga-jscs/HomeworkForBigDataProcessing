"""Download the unmodified H&M base transactions from Microsoft's public mirror.

Only raw transaction and article tables are used, never the synthetic search data.
Files are streamed to D:, verified against repository LFS SHA-256, and atomically
published. Re-running verifies existing files instead of downloading them again.
"""
from 公共设置 import ROOT, sha256, save_json
from pathlib import Path
import json, urllib.request, time, datetime, concurrent.futures, argparse

REPO = 'microsoft/hnm-search-data'
DEST = ROOT / '数据' / '服装交易'

def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)

def download(entry, revision):
    name = Path(entry['path']).name
    target = DEST / name
    digest = entry['lfs']['oid']
    url = f'https://huggingface.co/datasets/{REPO}/resolve/{revision}/{entry["path"]}?download=true'
    if target.exists() and target.stat().st_size == entry['size'] and sha256(target) == digest:
        print(f'{name}: verified existing file', flush=True)
    else:
        partial = target.with_suffix(target.suffix + '.下载中')
        for attempt in range(4):
            try:
                start = time.perf_counter()
                with urllib.request.urlopen(url, timeout=120) as source, partial.open('wb') as out:
                    total = 0
                    next_notice = 256 * 1024 * 1024
                    while chunk := source.read(4 * 1024 * 1024):
                        out.write(chunk)
                        total += len(chunk)
                        if total >= next_notice:
                            print(f'{name}: {total / 1024**2:.0f} MiB, {time.perf_counter()-start:.1f} s', flush=True)
                            next_notice += 256 * 1024 * 1024
                if partial.stat().st_size != entry['size'] or sha256(partial) != digest:
                    raise ValueError(f'Size/hash mismatch for {name}')
                partial.replace(target)
                break
            except Exception as error:
                if attempt == 3:
                    raise
                print(f'{name}: retry {attempt+1}, {type(error).__name__}', flush=True)
                time.sleep(2 * (attempt + 1))
    return {'file': name, 'url': url, 'bytes': entry['size'], 'sha256': digest,
            'verification': 'matches mirror repository LFS SHA-256'}

def parquet_download():
    """Public HF conversion of the same Microsoft raw base tables, in full.

    Range chunks bound retries on slow connections. Every completed file must
    match the conversion revision's LFS SHA-256 before it is made visible.
    """
    revision = get_json(f'https://huggingface.co/api/datasets/{REPO}/revision/refs%2Fconvert%2Fparquet')['sha']
    entries = []
    for kind in ('articles','transactions'):
        entries += get_json(f'https://huggingface.co/api/datasets/{REPO}/tree/{revision}/{kind}/train')
    entries = [e for e in entries if e['path'].endswith('.parquet')]
    chunk_dir = ROOT/'临时文件'/'服装下载'
    chunk_dir.mkdir(parents=True,exist_ok=True)
    jobs = []
    chunk_size = 8*1024**2
    for e in entries:
        target = DEST/e['path']
        if target.exists() and target.stat().st_size == e['size'] and sha256(target) == e['lfs']['oid']:
            continue
        for part,start in enumerate(range(0,e['size'],chunk_size)):
            jobs.append((e,part,start,min(e['size'],start+chunk_size)-1))
    def fetch(job):
        e,part,start,end = job
        name = e['path'].replace('/','_')+f'.{part}'
        dest = chunk_dir/name
        if dest.exists() and dest.stat().st_size == end-start+1: return
        for attempt in range(5):
            try:
                url = f'https://huggingface.co/datasets/{REPO}/resolve/{revision}/{e["path"]}?download=true&part={part}&attempt={attempt}'
                request = urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'})
                with urllib.request.urlopen(request,timeout=45) as response:
                    if response.status != 206 or not response.headers.get('Content-Range','').startswith(f'bytes {start}-{end}/'):
                        raise ValueError('Unexpected range response')
                    temporary = dest.with_suffix(dest.suffix+'.下载中')
                    with temporary.open('wb') as out:
                        while block := response.read(256*1024): out.write(block)
                if temporary.stat().st_size != end-start+1: raise ValueError('Incomplete range')
                temporary.replace(dest)
                print(f'{name}: complete',flush=True)
                return
            except Exception as error:
                if attempt == 4: raise
                print(f'{name}: retry {attempt+1} ({type(error).__name__})',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(fetch,jobs))
    files = []
    for e in entries:
        target = DEST/e['path']
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            partial = target.with_suffix('.下载中')
            with partial.open('wb') as out:
                for part,start in enumerate(range(0,e['size'],chunk_size)):
                    chunk = chunk_dir/(e['path'].replace('/','_')+f'.{part}')
                    with chunk.open('rb') as inp:
                        while block := inp.read(4*1024**2): out.write(block)
            if sha256(partial) != e['lfs']['oid']: raise ValueError(f'Hash mismatch: {target.name}')
            partial.replace(target)
        if target.stat().st_size != e['size'] or sha256(target) != e['lfs']['oid']:
            raise ValueError('Published file failed verification')
        files.append({'file':e['path'],'bytes':e['size'],'sha256':e['lfs']['oid']})
    record = {'original':'https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data',
        'mirror':f'https://huggingface.co/datasets/{REPO}','conversion_revision':revision,
        'format':'Hugging Face full Parquet conversion of raw base articles and transactions',
        'downloaded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope':'all seven transaction shards; excludes synthetic search queries, images and demographics',
        'verification':'every file matches its pinned conversion repository LFS SHA-256',
        'terms':'Original H&M terms apply; non-commercial and academic research. CDLA license for synthetic additions does not apply to base records.',
        'files':files}
    save_json('服装数据来源.json',record)
    print(json.dumps(record,ensure_ascii=False,indent=2),flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--format',choices=['csv','parquet'],default='parquet')
    args = parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    if args.format == 'parquet':
        parquet_download()
        return
    metadata = get_json(f'https://huggingface.co/api/datasets/{REPO}')
    revision = metadata['sha']
    entries = get_json(f'https://huggingface.co/api/datasets/{REPO}/tree/{revision}/data/raw')
    chosen = [e for e in entries if Path(e['path']).name in ('articles.csv', 'transactions_train.csv')]
    assert len(chosen) == 2
    with urllib.request.urlopen(f'https://huggingface.co/datasets/{REPO}/raw/{revision}/README.md', timeout=60) as r:
        (DEST/'镜像数据说明.md').write_bytes(r.read())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        files = list(pool.map(lambda entry: download(entry, revision), chosen))
    record = {'original': 'https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data',
              'mirror': f'https://huggingface.co/datasets/{REPO}', 'revision': revision,
              'downloaded_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'raw base tables only; excludes synthetic search queries, images and customer demographics',
              'terms': 'Original H&M terms apply; mirror states non-commercial and academic research use. Additions license is not a license for the base data.',
              'files': files}
    save_json('服装数据来源.json', record)
    print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)

if __name__ == '__main__':
    main()
