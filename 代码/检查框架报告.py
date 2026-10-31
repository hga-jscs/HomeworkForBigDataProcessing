from 公共设置 import ROOT,save_json,sha256
from pypdf import PdfReader
import pdfplumber

path=ROOT/'结果'/'框架基准报告.pdf'
reader=PdfReader(path)
assert len(reader.pages)==8
text='\n'.join(p.extract_text() for p in reader.pages)
for heading in ['1. Abstract','2. Introduction','3. Method','4. Experiment','5. Analysis','6. Conclusion']:
    assert heading in text,heading
for i in range(1,13):assert f'[{i}]' in text
assert '\ufffd' not in text and '\x00' not in text
page_checks=[]
with pdfplumber.open(path) as document:
    for i,page in enumerate(document.pages,1):
        assert f'{i} / 8' in page.extract_text()
        bad=[c for c in page.chars if c['x0']<43 or c['x1']>551 or c['top']<10 or c['bottom']>825]
        assert not bad,(i,bad[:2])
        body=[c for c in page.chars if 42<c['top']<790]
        page_checks.append({'page':i,'characters':len(page.chars),'body_bottom':round(max(c['bottom'] for c in body),2)})
save_json('框架报告排版检查.json',{'pages':8,'sha256':sha256(path),'checks':page_checks,
    'headings_references_bounds_and_characters':'passed','visual_review':'pending'})
print('Eight pages, headings, references, characters and layout bounds passed.')
