from 公共设置 import ROOT,save_json,sha256
import json,urllib.request,concurrent.futures
from pypdf import PdfReader

def fetch(ref):
    if not ref['url'].endswith('.pdf'):
        return {'id':ref['id'],'status':'web source only','url':ref['url']}
    target=ROOT/'文献'/f"文献{ref['id']}.pdf"
    try:
        if not target.exists():
            req=urllib.request.Request(ref['url'],headers={'User-Agent':'Mozilla/5.0 (course research)'})
            with urllib.request.urlopen(req,timeout=90) as response:
                data=response.read()
            if not data.startswith(b'%PDF'):
                raise ValueError('not a PDF')
            target.write_bytes(data)
        reader=PdfReader(target)
        target.with_suffix('.txt').write_text('\n'.join(p.extract_text() or '' for p in reader.pages),encoding='utf-8')
        return {'id':ref['id'],'status':'downloaded','pages':len(reader.pages),'sha256':sha256(target),'url':ref['url']}
    except Exception as e:
        return {'id':ref['id'],'status':'download failed; browser evidence retained in references','error':str(e),'url':ref['url']}

if __name__=='__main__':
    refs=json.loads((ROOT/'文献'/'文献索引.json').read_text(encoding='utf-8'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(fetch,refs))
    save_json('文献下载.json',results,folder='文献')
    print(json.dumps(results,ensure_ascii=False,indent=2))
