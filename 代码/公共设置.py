from pathlib import Path
import os, sys, json, hashlib

ROOT = Path(__file__).resolve().parents[1]
for name in ('数据', '结果', '文献', '临时文件', '依赖'):
    (ROOT / name).mkdir(exist_ok=True)
for key in ('TEMP', 'TMP', 'TMPDIR'):
    os.environ[key] = str(ROOT / '临时文件')
os.environ['MPLCONFIGDIR'] = str(ROOT / '临时文件' / '绘图库缓存')
os.environ['PYTHONPYCACHEPREFIX'] = str(ROOT / '临时文件' / '字节码缓存')
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / '依赖'))

def save_json(name, obj, folder='结果'):
    (ROOT / folder / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def discovery(customer):
    return int(hashlib.sha256(('sequence-v1:' + str(customer)).encode()).hexdigest()[:8], 16) % 10 < 5
