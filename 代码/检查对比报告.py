from 公共设置 import ROOT,save_json,sha256
from pypdf import PdfReader
import pdfplumber,json

path=ROOT.parent/'序列算法对比报告.pdf'
reader=PdfReader(path)
assert len(reader.pages)==8
texts=[page.extract_text() for page in reader.pages]
text='\n'.join(texts)
for heading in ['1. Abstract','2. Introduction','3. Method','4. Experiment','5. Analysis','6. Conclusion']:
    assert heading in text,heading
for number in range(1,11):assert f'[{number}]' in text
assert '\ufffd' not in text and '\x00' not in text
for value in ['GSP','PrefixSpan','SPADE','SPAM','31,788,324','163,249','1,669','1,245']:
    assert value in text,value
assert '6. Conclusion' in texts[7]
assert len(reader.pages[7].get('/Annots',[]))>=10,'References need clickable source links'
page_checks=[]
with pdfplumber.open(path) as document:
    for i,page in enumerate(document.pages,1):
        assert f'{i} / 8' in page.extract_text()
        bad=[char for char in page.chars if char['x0']<43 or char['x1']>551 or char['top']<10 or char['bottom']>825]
        assert not bad,(i,bad[:2])
        body=[char for char in page.chars if 42<char['top']<790]
        assert len(body)>250,('Unexpectedly empty page',i)
        page_checks.append({'page':i,'characters':len(page.chars),'body_bottom':round(max(c['bottom'] for c in body),2)})
save_json('对比报告排版检查.json',{'pages':8,'sha256':sha256(path),'checks':page_checks,
    'headings_references_bounds_characters_and_key_values':'passed','visual_review':'pending'})
print('Eight pages, six sections, linked references, bounds and measured values passed.')
