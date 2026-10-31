from 公共设置 import ROOT,save_json,sha256
import json, math, html, io
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.mathtext import math_to_image
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image,Flowable,KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY,TA_LEFT,TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader
import reportlab.lib.textsplit as textsplit
import reportlab.platypus.paragraph as paragraph_module

# Extend the library's Japanese line-start rules to Chinese full-width punctuation.
# This changes only the current process, never the installed library on C:.
textsplit.ALL_CANNOT_START += '，；：！？）】》’”'
paragraph_module.ALL_CANNOT_START = textsplit.ALL_CANNOT_START

def read(name,folder='结果'):
    return json.loads((ROOT/folder/name).read_text(encoding='utf-8'))

FONT='C:/Windows/Fonts/msyh.ttc'
BOLD='C:/Windows/Fonts/msyhbd.ttc'
pdfmetrics.registerFont(TTFont('Chinese',FONT,subfontIndex=0))
pdfmetrics.registerFont(TTFont('ChineseBold',BOLD,subfontIndex=0))
pdfmetrics.registerFontFamily('Chinese',normal='Chinese',bold='ChineseBold')
fp=FontProperties(fname=FONT)
plt.rcParams.update({'font.family':fp.get_name(),'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':180})
BLUE=colors.HexColor('#183D56'); TEAL='#147D92'; RED='#B24B3F'; INK=colors.HexColor('#24333E')
styles={
 'body':ParagraphStyle('body',fontName='Chinese',fontSize=10.1,leading=16.5,textColor=INK,spaceAfter=7,wordWrap='CJK',alignment=TA_JUSTIFY),
 'small':ParagraphStyle('small',fontName='Chinese',fontSize=8.4,leading=12.4,textColor=INK,spaceAfter=5,wordWrap='CJK'),
 'caption':ParagraphStyle('caption',fontName='Chinese',fontSize=8.3,leading=12.2,textColor=colors.HexColor('#526472'),spaceAfter=8,wordWrap='CJK'),
 'h1':ParagraphStyle('h1',fontName='ChineseBold',fontSize=15.5,leading=21,textColor=BLUE,spaceBefore=5,spaceAfter=9,keepWithNext=True),
 'h2':ParagraphStyle('h2',fontName='ChineseBold',fontSize=11.5,leading=17,textColor=BLUE,spaceBefore=7,spaceAfter=6,keepWithNext=True),
 'title':ParagraphStyle('title',fontName='ChineseBold',fontSize=21,leading=29,textColor=BLUE,spaceAfter=8),
 'subtitle':ParagraphStyle('subtitle',fontName='Chinese',fontSize=10.5,leading=17,textColor=colors.HexColor('#526472'),spaceAfter=15),
 'cell':ParagraphStyle('cell',fontName='Chinese',fontSize=8.4,leading=12.5,textColor=INK,wordWrap='CJK'),
 'head':ParagraphStyle('head',fontName='ChineseBold',fontSize=8.5,leading=12.5,textColor=colors.white,wordWrap='CJK'),
 'ref':ParagraphStyle('ref',fontName='Chinese',fontSize=8.5,leading=12.8,textColor=INK,spaceAfter=8,wordWrap='CJK')}

story=[]
def typography(text):
    for char,markup in {'ᵤ':'<sub>u</sub>','ⱼ':'<sub>j</sub>','ʸ':'<super>y</super>','₁':'<sub>1</sub>','₂':'<sub>2</sub>','ₖ':'<sub>k</sub>'}.items():
        text=text.replace(char,markup)
    return text
def p(text,kind='body'):
    story.append(Paragraph(typography(text),styles[kind]))
def h(text):p(text,'h1')
def sub(text):p(text,'h2')
def page():story.append(PageBreak())
def table(rows,widths):
    cells=[[Paragraph(typography(str(c)),styles['head' if i==0 else 'cell']) for c in row] for i,row in enumerate(rows)]
    t=Table(cells,colWidths=widths,hAlign='LEFT',repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BLUE),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#F0F5F7'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#BCCBD4'))]))
    story.extend([t,Spacer(1,8)])
def equation(tex,number):
    target=ROOT/'结果'/f'公式{number}.png'
    math_to_image('$'+tex+'$',str(target),dpi=230,format='png',color='#183D56')
    from PIL import Image as PILImage
    with PILImage.open(target) as im:w,ht=im.size
    scale=min(1,470/(w*72/230)); width=w*72/230*scale; height=ht*72/230*scale
    story.append(Image(str(target),width=width,height=height,hAlign='CENTER'))
    story.append(Spacer(1,9))
def plot_image(name,width=490):
    from PIL import Image as PILImage
    file=ROOT/'结果'/name
    with PILImage.open(file) as im:w,ht=im.size
    story.append(Image(str(file),width=width,height=width*ht/w))
    story.append(Spacer(1,5))

class Pipeline(Flowable):
    def __init__(self):super().__init__();self.width=490;self.height=63
    def draw(self):
        c=self.canv
        boxes=[('原始交易','两年 Excel / CSV'),('交易分区','清洗 + Parquet'),('顾客序列','时间排序 / 集合'),('模式与检验','发现 / 留出对照')]
        for i,(title,detail) in enumerate(boxes):
            x=i*126
            c.setFillColor(colors.HexColor('#EDF4F7'));c.setStrokeColor(colors.HexColor('#BDD0DB'));c.roundRect(x,7,112,49,5,fill=1,stroke=1)
            c.setFillColor(BLUE);c.setFont('ChineseBold',9.5);c.drawCentredString(x+56,36,title)
            c.setFont('Chinese',8);c.drawCentredString(x+56,20,detail)
            if i<3:
                c.setStrokeColor(BLUE);c.line(x+115,31,x+123,31);c.line(x+120,34,x+123,31);c.line(x+120,28,x+123,31)

def figures(rows,perm,thresholds,selected):
    fig,ax=plt.subplots(figsize=(7.2,2.55),layout='constrained')
    y=np.arange(len(selected)); vals=np.array([r['delta']*100 for r in selected]);lo=np.array([r['ci_low']*100 for r in selected]);hi=np.array([r['ci_high']*100 for r in selected])
    for i,v in enumerate(vals):
        ax.errorbar(v,i,xerr=[[v-lo[i]],[hi[i]-v]],fmt='o',color=TEAL if v>=0 else RED,capsize=4,markersize=6)
    ax.axvline(0,color='#A0A9AF',lw=1);ax.set_yticks(y,[' → '.join(r['pattern']) for r in selected]);ax.invert_yaxis();ax.set_xlabel('支持度变化（2011 - 2010，百分点）',fontproperties=fp);ax.grid(axis='x',alpha=.2)
    fig.savefig(ROOT/'结果'/'模式变化.png',dpi=220);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.2,3.25),layout='constrained')
    for i,r in enumerate(perm):
        a,b=r['null_interval'];ax.plot([a,b],[i,i],color='#9BBCC7',lw=5,solid_capstyle='round');ax.plot(r['null_mean'],i,'|',color=TEAL,ms=12);ax.plot(r['observed'],i,'o',color=RED,ms=4)
    ax.plot([],[],color='#9BBCC7',lw=5,label='置换分布的 95% 范围');ax.plot([],[],'o',color=RED,label='实际支持人数')
    ax.set_yticks(range(len(perm)),[' → '.join(r['pattern']) for r in perm],fontsize=8.5);ax.invert_yaxis();ax.set_xlabel('支持该模式的顾客数（留出集 n = 785）',fontproperties=fp);ax.legend(prop=fp,loc='lower center',bbox_to_anchor=(.5,1.01),ncol=2,frameon=False);ax.grid(axis='x',alpha=.2)
    fig.savefig(ROOT/'结果'/'顺序对照.png',dpi=220);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(7.2,2.2),layout='constrained')
    x=[t['support']*100 for t in thresholds];k=[sum(int(c) for length,c in t['counts'].items() if int(length)>=2) for t in thresholds]
    axes[0].plot(x,k,'o-',color=TEAL);axes[0].set_yscale('log');axes[0].set_xlabel('最小支持度（%）',fontproperties=fp);axes[0].set_ylabel('二步与三步模式数（对数轴）',fontproperties=fp)
    axes[1].plot(x,[t['seconds'] for t in thresholds],'o-',color=RED);axes[1].set_xlabel('最小支持度（%）',fontproperties=fp);axes[1].set_ylabel('挖掘耗时（秒）',fontproperties=fp)
    for ax in axes:ax.grid(alpha=.2);ax.set_xticks(x)
    fig.savefig(ROOT/'结果'/'阈值代价.png',dpi=220);plt.close(fig)

def main():
    summary=read('实验汇总.json');clean=read('数据整理.json');diagnosis=read('结果诊断.json');rows=read('跨年变化.json');perm=read('顺序置换.json');thresholds=read('阈值实验.json');robust=read('稳健性实验.json');scales=read('规模实验.json');refs=read('文献索引.json','文献')
    selected=[next(r for r in rows if tuple(r['pattern'])==pair) for pair in [('22528','85123A'),('22662','22382'),('85123A','85123A'),('22423','22423')]]
    figures(rows,perm,thresholds,selected)
    n=summary['evaluation_customers']; index={tuple(r['pattern']):i for i,r in enumerate(rows)}
    # Page 1
    p('事件序列中的频繁模式<br/>与行为变化分析','title')
    p('基于前缀投影、配对检验与顺序置换的真实交易实验<br/>大数据处理课程研究报告　｜　实验日期：2026 年 10 月 31 日','subtitle')
    h('1. Abstract')
    p(f'本课题研究交易、日志等离散事件中“哪些行为经常先后发生，以及这些模式是否随时间改变”。以 UCI Online Retail II 的 1,067,371 条交易明细为对象，构建按年月分区的数据处理流程，将同一顾客、同一时间的商品合并为无序购物篮，再用前缀投影挖掘跨购物篮的频繁序列。为区分模式发现与效果验证，按顾客划分发现集和留出集，在相同月份、相同顾客之间开展跨年配对检验，并用多重检验校正、购物篮顺序置换和时间间隔约束检查解释的可靠性。')
    p(f'实验在 763 名发现顾客中获得 46,740 个二步或三步候选模式；在 785 名留出顾客中，1,695 个模式通过 BY 校正。然而，10 个高频异商品序列均未显著偏离随机顺序对照；将相邻事件间隔限制为 30 天后，通过检验的模式仅剩 1 个。这说明频繁共现、长期复购与时间顺序应分别解释。本文完成了可复现的单机处理与分析原型，其价值在于形成“发现模式—验证变化—检查替代解释”的证据链，而非提出新的序列挖掘算法。')
    p('<b>关键词：</b>频繁序列；购物篮；前缀投影；行为变化；配对检验；顺序置换','small')
    h('2. Introduction')
    sub('2.1 问题背景与课内联系')
    p('课程中的关联规则能够回答“哪些商品经常一起出现”，但商品 A 与 B 的共现无法区分 A→B、B→A 或同一笔订单中的同时购买。实际事件数据还涉及行为发生的时间、同一对象的重复记录以及不同时间段的样本组成。本课题把课内的支持度、频繁项集和剪枝思想扩展到事件先后顺序，并把清洗、分组聚合、时间排序及分区存储落实为数据流水线。')
    p('本实验将“行为变化”限定为：在固定顾客队列和固定观察窗口内，某个序列的顾客支持率发生改变。它不是未来购买预测，也不等同于因果关系、业务流程变点定位或消费偏好的净变化；商品可得性和购物次数都可能产生同样的观测现象。')
    sub('2.2 研究问题与预期产出')
    p('<b>问题一：</b>正确保留事件顺序后，哪些二步、三步模式能够覆盖足够多的顾客？输出应能追溯到支持顾客，并明确同篮共现与跨篮顺序的区别。<b>问题二：</b>同一批顾客中的模式支持率是否跨年改变，这种变化能否经受多重检验与观察机会控制？<b>问题三：</b>高频序列是否超出保留购物篮构成的随机顺序模型，降低支持阈值又会付出多少计算和解释成本？')
    # Page 2
    page();h('2. Introduction（续）')
    sub('2.3 已有研究：从频繁挖掘到可信解释')
    table([
      ['研究','主要贡献','对本课题仍需补足的环节'],
      ['Agrawal 与 Srikant，1995 [1]','定义跨事务的频繁子序列，建立候选生成与支持度筛选框架。','解决“出现多少”，不直接检验不同年份的变化。'],
      ['PrefixSpan，2001 [2]<br/>SPADE，2001 [3]','前者用前缀投影压缩搜索；后者用垂直标识列表和等价类分解提高效率。','高支持度仍可能由热门商品和长序列造成；效率并不提供统计解释。'],
      ['SPEck，2022 [9]','通过保留不同数据性质的零模型和精确采样挖掘显著序列。','显著性的含义依赖零模型；跨年配对变化是另一种检验目标。'],
      ['HOPPER，2024 [4]','以最小描述长度建模事件间延迟，发现较紧凑的模式集合。','采用启发式搜索；不直接解决固定顾客的跨年差异检验。'],
      ['Kraus 与 van der Aa，2026 [5]','提出三步框架，刻画突发、渐进和循环等过程漂移。','变点检测精度和噪声影响后续解释；本文的双窗口比较不能替代该框架。']
    ],[113,182,199])
    p('这些研究形成三条互补路线：高效枚举模式、判断模式是否超出随机结构、刻画行为如何变化。本文采用前缀投影作为挖掘基础，借鉴零模型对照思想，在独立顾客上检验跨年差异；未复现 SPEck、HOPPER 或完整流程漂移算法，因而不作优于这些方法的性能声明。','body')
    h('3. Method')
    sub('3.1 数据对象与模式支持度')
    p('设顾客 u 在年份 y 的记录为 Sᵤʸ。第 j 个事件由时间 tᵤⱼʸ 和商品集合 Bᵤⱼʸ 构成；时间严格递增。相同时间戳的订单合并，篮内不排序。模式 P=(a₁,…,aₖ) 的每一步只含一个商品，但允许跨越中间购物篮，也允许同一商品在不同时间重复出现。')
    equation(r'X_u^y(P)=\mathbf{1}\{\exists j_1<\cdots<j_k:\ a_r\in B_{u,j_r}^y,\ r=1,\ldots,k\}',1)
    equation(r'\widehat{s}_y(P)=\frac{1}{|U|}\sum_{u\in U}X_u^y(P),\qquad \widehat{\Delta}(P)=\widehat{s}_{2011}(P)-\widehat{s}_{2010}(P)',2)
    p('例如，〈{A,B},{C},{B}〉支持 A→B 和 B→B，却不因为第一篮同时含 A、B 就判定其中存在先后关系。每个顾客对一个模式最多贡献一次支持，避免把高频顾客的重复订单当成独立样本。','small')
    # Page 3
    page();h('3. Method（续）')
    sub('3.2 前缀投影与正确性论证')
    p('从空前缀开始，对每个顾客记录当前前缀的最早结束位置，只扫描该位置之后的购物篮。按可追加商品聚合支持顾客，保留支持人数达到阈值的扩展，并递归到长度 3。发现集阈值为 ceil(0.02×763)=16 人；输出仅覆盖上述“单商品步骤”语言，不包含 {A,B}→C 这类多商品步骤模式。')
    p('<b>剪枝依据。</b>若顾客支持扩展 P·a，就必然支持前缀 P，故 s(P·a)≤s(P)。不频繁前缀不可能产生频繁扩展。<b>最早结束位置的充分性。</b>对无间隔上限的匹配，前缀结束越早，可继续搜索的后缀越大；任何较晚结束位置后的扩展，也位于最早位置之后。因此每名顾客只保留一个最早结束位置不会漏掉合法扩展。按模式长度归纳，算法在给定阈值及最大长度内枚举全部合法频繁模式。')
    p('该压缩只适用于主实验。增加最大时间间隔后，较早匹配可能距下一事件太远，而较晚匹配仍合法；因此敏感性实验保留所有可达结束位置。反例为第 0、99 天出现 A，第 100 天出现 B：2 天上限下，不能只保留第 0 天的 A。模式输出仍可能组合爆炸，前缀投影并不保证总耗时随原始数据量线性增长。')
    sub('3.3 同一顾客的跨年配对检验')
    p('候选模式仅由发现集的 2010 年数据确定。对留出顾客，令 b 为仅在 2010 年支持该模式的人数，c 为仅在 2011 年支持的人数。零假设为两类不一致配对的概率相同；在顾客之间可视为独立、零假设成立的条件下，c | (b+c) 服从二项分布，进行双侧精确 McNemar 检验。')
    equation(r'p(P)=\min\{1,\ 2\Pr[Z\leq\min(b,c)]\},\qquad Z\sim\mathrm{Binomial}(b+c,1/2)',3)
    p('当 b+c=0 时取 p=1。全部 m=46,740 个候选同时进入 Benjamini-Yekutieli（BY）校正 [6]，允许模式检验之间相互依赖。它控制错误发现率 E[V/max(R,1)]≤0.05，其中 V 是错误拒绝数，R 是拒绝总数。将 p 排序，取满足下式的最大 k，拒绝前 k 个假设；无满足者则不拒绝。')
    equation(r'p_{(k)}\leq\frac{k\alpha}{mH_m},\qquad H_m=\sum_{j=1}^{m}\frac{1}{j},\quad\alpha=0.05',4)
    p('以顾客为单位进行 2,000 次配对自助重采样，给出支持度差的边际 95% 百分位区间。它不具有“从众多结果中挑出示例后仍同时覆盖”的保证。发现集与检验集按顾客分离，避免同一人的重复记录跨集合造成信息泄漏；但同一商户中顾客之间的潜在依赖仍是检验假设的限制。','small')
    sub('3.4 将共现变化与序列形成比例分开')
    p('对异商品 A、B，令 w 为买过两种商品的顾客比例，r 为这些顾客中满足 A→B 的比例。因为支持序列必然支持无序共现，样本支持率恒有 s=w·r。用下标 0、1 表示两个年份，可得一个精确的描述性分解：')
    equation(r's_1-s_0=(w_1-w_0)r_0+w_1(r_1-r_0)',5)
    p('第一项固定基准年的序列形成比例，表示共同购买机会改变带来的部分；第二项表示在共同出现后形成该序列的比例变化。若某年 w=0，约定 r=0。该恒等式不需要分布假设，但第二项仍受复购次数、商品进入时间及条件人群构成影响，不能解释为因果效应。','small')
    # Page 4
    page();h('4. Experiment')
    sub('4.1 实验环境与数据架构')
    p(f'本地环境为 Windows 11（build 26200）、Intel Core i9-14900HX（24 核 / 32 线程）、{summary["physical_memory_bytes"]/1024**3:.2f} GiB 物理内存；Python 3.12.14、DuckDB {summary["duckdb"]}、NumPy {summary["numpy"]}、SciPy {summary["scipy"]}。DuckDB 使用 4 线程和 2 GB 缓冲区上限，序列挖掘使用单个 Python 进程。代码、数据、新装依赖、缓存及数据库临时目录均设于 D 盘；已有 Python 解释器从原安装位置读取。')
    story.append(Pipeline())
    p('图 1　实际执行的数据流程。按年、月输出 Parquet，SQL 完成筛选、去重、聚合与队列连接，对应课程的数据预处理、数据仓库与频繁模式内容。本次为单机原型，未验证集群或超内存规模；DuckDB 的磁盘溢写机制 [8] 也未在本次实验中得到验证。','caption')
    sub('4.2 真实数据与清洗口径')
    p('Online Retail II [7] 是英国一家非实体零售商在 2009-12 至 2011-12 的交易明细，包含批发顾客。两张工作表全部导入；每行是商品明细而非独立订单。保留正数量、正价格及有效顾客，排除撤销单、非标准商品编码，再按全部业务字段去重。重复明细的出现次数不参与支持度计算。')
    table([['顺序清洗步骤','剩余行数','本步排除']]+[[r['stage'],f"{r['rows']:,}",'—' if i==0 else f"{clean['cleaning'][i-1]['rows']-r['rows']:,}"] for i,r in enumerate(clean['cleaning'])],[270,109,115])
    p('商品编码规则为 5 位数字后接 0 至 2 位字母，用于排除运费、手工调整等条目；可能同时舍弃少量非标准编码商品。158 个顾客时间点对应多张发票，合并为一个集合，避免按发票号制造虚假先后关系。','small')
    sub('4.3 观察窗口与对照设置')
    p('两个窗口均为 1 月 1 日至 12 月 1 日（左闭右开），对齐月份并避开末年不完整的 12 月。窗口内有效明细分别为 355,219 和 348,617 条。选择两个年份各有至少 2 个购物时间点的 1,548 名顾客，共 21,815 个购物篮；固定 SHA-256 分组得到 763 名发现顾客和 785 名留出顾客。该队列只代表持续复购顾客。')
    p('主实验不限制间隔；补充 30 / 90 天间隔、两年购物篮数量对齐、1% / 2% / 3% / 5% 支持阈值实验。顺序对照选取发现集支持度最高的 10 个异商品二步模式，在留出集 2010 年内进行 499 次顾客内购物篮顺序置换。整个篮一起移动，保留篮内共现、商品次数及每人购物篮数。','small')
    # Page 5
    page();h('4. Experiment（续）')
    sub('4.4 模式数量与跨年变化')
    p(f'2% 阈值下，发现集产生 1,429 个单步、21,080 个二步和 25,660 个三步模式，单次挖掘耗时 {summary["mining_seconds"]:.2f} 秒。二步和三步模式进入跨年检验：未校正时 12,324 个 p≤0.05，BY 校正后保留 1,695 个，其中上升 {summary["significant_increase"]:,} 个、下降 {summary["significant_decrease"]:,} 个。两者差距说明直接罗列未经校正的差异会夸大证据。')
    p(f'统计主程序共耗时 {summary["total_seconds"]:.1f} 秒，进程峰值工作集为 {summary["peak_working_set_bytes"]/1024**3:.2f} GiB；该时间包含所有敏感性实验及重复计时，不含数据下载、Excel 转换和报告生成。','small')
    label=['园艺跪垫 → 白色心形烛台','玩偶午餐袋 → 太空男孩午餐袋','白色心形烛台 → 同商品','三层蛋糕架 → 同商品']
    table([['代表性模式（商品编码）','2010','2011','差值 / 百分点','BY 调整 p']]+[[f'{label[i]}<br/>{" → ".join(r["pattern"])}',f'{r["count2010"]}/{n}<br/>{r["support2010"]*100:.2f}%',f'{r["count2011"]}/{n}<br/>{r["support2011"]*100:.2f}%',f'{r["delta"]*100:+.2f}',f'{r["q_by"]:.2g}'] for i,r in enumerate(selected)],[222,63,63,78,68])
    plot_image('模式变化.png')
    p('图 2　四个示例的支持度差与配对自助区间。示例按可解释性选取；完整结果保留。误差条是边际 95% 区间，不是多个被选结果的同时置信区间。例如蛋糕架复购的区间不跨零，但 BY 调整 p=0.283，不能据此宣布该模式通过多重检验。','caption')
    sub('4.5 实现核验与结果留存')
    p(f'随机生成 120 个小型序列数据库，与组合穷举结果比较不同阈值下的完整频繁模式；再检查时间约束匹配，共通过 {read("算法验证.json")["assertions"]:,} 项断言。主实验的共享前缀匹配与独立逐模式匹配比较了 {diagnosis["trie_brute_cells_checked"]:,} 个布尔结果；全部 {diagnosis["training_pattern_counts_checked"]:,} 个发现模式的支持人数再次核对一致。验证覆盖篮内无序、重复商品及最大间隔反例。')
    p('原始下载文件保存 SHA-256；清洗计数、顾客划分、模式支持矩阵、全部 p 值和校正值、置换与敏感性汇总均可由代码重建。所有图表直接读取本次输出文件，未使用模拟数值替代真实实验。','small')
    # Page 6
    page();h('5. Analysis')
    sub('5.1 高频出现是否意味着顺序偏好？')
    p('对异商品 A、B，额外计算顾客级无序共现：只要全年购物记录同时含 A 与 B 就计一次，不考虑顺序；其分母仍是 785 人。A→B 与 B→A 的支持人数不能相加当作总人数，同一个顾客可能同时满足两个方向。')
    unordered=read('无序对照.json'); picks=[next(r for r in unordered if tuple(r['pattern'])==tuple(perm[j]['pattern'])) for j in (0,1,7)]
    table([['模式','全年无序共现','A→B','B→A']]+[[' → '.join(r['pattern']),str(r['cooccurrence']),str(r['forward']),str(r['reverse'])] for r in picks],[245,95,77,77])
    plot_image('顺序对照.png')
    p('图 3　10 个模式的实际支持人数与随机购物篮顺序对照。灰蓝线为 499 次置换的经验 95% 范围，红点为实际值。范围是零模型参考区间，不是参数置信区间。','caption')
    p('用支持人数到置换中心的绝对偏离做双侧随机化检验，中心由实际值及 499 次置换共同计算。p 值为“不小于实际偏离的置换次数加 1”除以 500。10 个模式经 Bonferroni 校正后均未达到 0.05，最小校正值为 0.54。这组结果与保留商品流行程度及购物次数的随机顺序模型相容，尚无额外顺序偏好的证据；未拒绝零假设不等于证明没有顺序效应。')
    sub('5.2 商品出现率是重要的替代解释')
    p(f'园艺跪垫 22528→烛台 85123A 从 51 人降到 0 人，但清洗后的 2011 年窗口内，22528 本身已无有效交易。对全部显著变化进行事后诊断，{diagnosis["significant_with_absent_2011_product"]:,}/{diagnosis["significant_patterns"]:,} 个模式包含此类当年未出现商品。这只能说明交易记录中的商品构成发生变化；是否停售、缺货或改编码，需要额外业务资料才能判断。','body')
    decomposition=read('变化分解.json')[0]
    p(f'另一个案例 22662→22382 的无序共现人数从 67 增到 87，条件序列比例从 13/67 增至 62/87。按第 3.4 节分解，支持率上升的 6.24 个百分点中，共现变化项为 {decomposition["cooccurrence_term"]*100:.2f}，条件比例变化项为 {decomposition["conditional_term"]*100:.2f}。后者提示应进一步检查商品进入时间及复购频率，而不能直接归因为偏好变化。','small')
    # Page 7
    page();h('5. Analysis（续）')
    sub('5.3 时间间隔与观察机会改变结论')
    table([['同一候选集合的设置','BY 显著数','与主实验同号的差值比例'],['不限间隔，全部购物篮','1,695','100%']]+[[{'gap30':'相邻步骤间隔 ≤ 30 天','gap90':'相邻步骤间隔 ≤ 90 天','balanced_baskets':'两年均截取前 min(n₁,n₂) 个篮'}[r['variant']],str(r['significant']),f"{r['same_sign_as_primary']*100:.1f}%"] for r in robust],[273,90,131])
    p(f'留出顾客的平均购物篮数为 {summary["basket_lengths"]["2010"]["mean"]:.2f} 与 {summary["basket_lengths"]["2011"]["mean"]:.2f}。对齐购物篮数量后显著数降至 367；30 天与 90 天上限分别得到 1 和 437 个。间隔收紧既改变问题定义，也减少可匹配机会，显著数下降不等于原结论全是错误。前 min(n₁,n₂) 篮截断又会缩短部分顾客的日历跨度，因此它是暴露机会的敏感性检查，不能彻底消除混杂。')
    sub('5.4 模式数量、计算成本与冗余')
    plot_image('阈值代价.png')
    p(f'图 4　相同 763 名发现顾客上的阈值敏感性，均限制长度 ≤ 3。耗时为各设置一次实际运行，包含挖掘、不含下载及清洗；不同运行间系统负载会影响计时。','caption')
    p(f'将阈值从 2% 降到 1% 后，二步与三步模式数从 46,740 增至 {sum(v for k,v in thresholds[0]["counts"].items() if int(k)>=2):,}，模式数量本身成为解释和计算负担。1,695 个显著模式具有 {diagnosis["unique_significant_support_vectors"]:,} 种不同的两年支持向量，未发现完全重复；但共享商品和顾客仍会使模式相互关联，不能把它们计作同样多的独立行为规律。后续可用闭合序列或描述长度压缩结果。')
    sub('5.5 实验局限与待解决问题')
    p('首先，数据来自单个商户的 2009—2011 年历史记录，复购队列排除了新客和流失客户；不能外推为当前电商规律。其次，按商品编码挖掘缺少稳定品类、上下架及促销信息，缺失顾客和退货也已被过滤。再次，最多三步且只有单商品步骤；只比较两个窗口，尚不能定位变化发生的月份，也不能识别渐进或循环漂移。最后，本次验证了百万明细的单机处理，尚未验证多节点、流式更新或超内存规模。')
    # Page 8
    page();h('6. Conclusion')
    p('本文把选题具体化为一套可运行的事件序列分析流程：先以明确的数据语义构建顾客购物篮序列，再用前缀投影发现模式，最后在独立顾客上检验跨年变化并检查替代解释。真实实验表明，频繁模式数量可以很大，但高频本身不能证明特殊的事件顺序；变化检测还受到商品出现率、观察机会与时间尺度的明显影响。')
    p('从课程实践看，已经完成全量数据导入、清洗与分区存储、序列挖掘、数学论证、独立检验及结果分析。下一阶段应优先引入稳定商品映射和业务可得性信息，扩展多商品步骤与紧凑模式集，再在滚动窗口和不同数据集上检验解释是否稳定；分布式部署及其扩展性应作为独立实验验证。当前结果支持继续研究“可信的行为变化分析”，尚不支持将这些序列直接部署为购买推荐或业务因果规则。')
    sub('参考文献')
    for r in refs:
        url=('https://doi.org/'+r['doi']) if r.get('doi') else r['url']
        # Keep actual paper titles, hyperlinks, and publication metadata visible.
        authors=r['authors'] if r['id']!=2 else 'J. Pei, J. Han, B. Mortazavi-Asl, et al.'
        p(f'[{r["id"]}] {html.escape(authors)}. {r["year"]}. <link href="{html.escape(url,quote=True)}" color="#147D92">{html.escape(r["title"])}</link>. {html.escape(r["venue"])}.','ref')
    p('复现资料位于同级“事件序列分析”文件夹：实验方案、运行入口、完整代码、原始数据及校验值、结果表和文献核对记录。随机种子为 20261031，顺序置换使用 20261032。文献链接核对日期：2026-10-31。','small')
    output=ROOT/'结果'/'单机基准报告.pdf'
    def decorate(c,doc):
        c.saveState();c.setStrokeColor(colors.HexColor('#D5DFE5'));c.line(50,796,545,796)
        c.setFillColor(colors.HexColor('#617583'));c.setFont('Chinese',8)
        c.drawString(50,806,'大数据处理  /  事件序列分析');c.drawRightString(545,806,'真实数据实验报告')
        c.line(50,44,545,44);c.drawString(50,30,'2026.10.31');c.drawRightString(545,30,f'{doc.page} / 8');c.restoreState()
    doc=SimpleDocTemplate(str(output),pagesize=(595.28,841.89),leftMargin=50,rightMargin=50,topMargin=58,bottomMargin=58,title='事件序列中的频繁模式与行为变化分析',author='大数据处理课程项目',pageCompression=1)
    doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
    reader=PdfReader(output)
    text='\n\n'.join(p.extract_text() or '' for p in reader.pages)
    (ROOT/'结果'/'报告正文.txt').write_text(text,encoding='utf-8')
    save_json('报告检查.json',{'pages':len(reader.pages),'bytes':output.stat().st_size,'sha256':sha256(output),'sections':{s:s in text for s in ['1. Abstract','2. Introduction','3. Method','4. Experiment','5. Analysis','6. Conclusion']}})
    print('PDF',output,'pages',len(reader.pages))
    assert len(reader.pages)==8, f'Expected 8 pages, got {len(reader.pages)}'

if __name__=='__main__':
    main()
