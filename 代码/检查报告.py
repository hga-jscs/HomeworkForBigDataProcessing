from 公共设置 import ROOT,save_json,sha256
from pypdf import PdfReader
import pdfplumber
import json

def main():
    path=ROOT.parent/'事件序列分析报告.pdf'
    reader=PdfReader(path)
    assert len(reader.pages)==8
    pages=[]
    with pdfplumber.open(path) as pdf:
        for i,page in enumerate(pdf.pages,1):
            chars=page.chars
            body=[c for c in chars if 50<c['top']<780]
            outside=[c['text'] for c in chars if c['x0']<45 or c['x1']>550 or c['top']<20 or c['bottom']>820]
            text=page.extract_text() or ''
            assert not outside,(i,outside[:20])
            assert '\ufffd' not in text and '\x00' not in text,(i,'bad text')
            assert f'{i} / 8' in text,(i,'footer')
            pages.append({'page':i,'characters':len(chars),'body_bottom':max(c['bottom'] for c in body),'min_font_size':min(c['size'] for c in body),'images':len(page.images),'links':len(page.hyperlinks),'bounds':'passed'})
    alltext='\n'.join(page.extract_text() for page in reader.pages)
    assert all(s in alltext for s in ['1. Abstract','2. Introduction','3. Method','4. Experiment','5. Analysis','6. Conclusion'])
    assert all(f'[{i}]' in alltext for i in range(1,10))
    result={'pages':len(reader.pages),'sha256':sha256(path),'size_bytes':path.stat().st_size,'checks':pages,'visual_review':'pending; render and inspect all eight pages'}
    save_json('排版检查.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
