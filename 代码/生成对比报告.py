"""Eight-page report, using audited measurements rather than embedded results."""
from 生成报告 import (ROOT,read,story,p,h,sub,page,table,equation,plot_image,styles,
    BLUE,INK,fp,plt,np,colors,Flowable,SimpleDocTemplate,PdfReader,save_json,sha256)
import html,json,math

METHODS=['GSP','PrefixSpan','SPADE','SPAM','MLlib']
PALETTE={'GSP':'#B56A4B','PrefixSpan':'#147D92','SPADE':'#8064A2','SPAM':'#567D46','MLlib':'#263D56'}

def comma(value):return f'{value:,}'
def median(data,method,field='wall_seconds'):return data['methods'][method][field]['median']
def time_cell(data,method):
    value=data['methods'][method]['wall_seconds']
    return f'{value["median"]:.2f}<br/><font size="7.5">[{value["minimum"]:.2f}, {value["maximum"]:.2f}]</font>'

class Architecture(Flowable):
    def __init__(self):super().__init__();self.width=494;self.height=119
    def draw(self):
        c=self.canv
        rows=[(['原始交易','Spark 清洗与连接','分区 Parquet','顾客完整序列'],82),
              (['分区内四种内核','候选并集与去重','广播树、全局计数','频繁模式与跨期统计'],17)]
        for names,y in rows:
            for i,name in enumerate(names):
                x=i*125
                c.setFillColor(colors.HexColor('#EDF4F7' if y>20 else '#F0F4ED'))
                c.setStrokeColor(colors.HexColor('#BDD0DB'));c.roundRect(x,y,119,30,4,fill=1,stroke=1)
                c.setFillColor(BLUE);c.setFont('Chinese',8.5);c.drawCentredString(x+59.5,y+11,name)
                if i<3:
                    c.line(x+120,y+15,x+124,y+15)
        c.setFillColor(INK);c.setFont('Chinese',8)
        c.drawCentredString(247,62,'按顾客分区：完整序列留在工作进程；Driver 仅收集有上限的候选和计数')
        c.line(434,82,434,75);c.line(60,47,60,54)

def figures(data):
    names=['服装十分之一','服装二分之一','服装全量']
    x=[data[name]['input']['customers']/1000 for name in names]
    fig,axes=plt.subplots(1,2,figsize=(7.3,2.75),layout='constrained')
    for method in METHODS:
        values=[data[name]['methods'][method]['wall_seconds'] for name in names]
        central=[v['median'] for v in values]
        error=[[v['median']-v['minimum'] for v in values],[v['maximum']-v['median'] for v in values]]
        axes[0].errorbar(x,central,yerr=error,marker='o',ms=4,capsize=3,lw=1.4,color=PALETTE[method],label=method)
        if method!='MLlib':
            axes[1].plot(x,[median(data[name],method,'kernel_seconds_max') for name in names],marker='o',ms=4,lw=1.4,color=PALETTE[method])
    for ax in axes:
        ax.set_xlabel('发现集顾客（千人）',fontproperties=fp,fontsize=9)
        ax.grid(alpha=.18);ax.set_xticks([x[0],x[1],x[2]],[f'{v:.1f}' for v in x]);ax.tick_params(labelsize=8)
    axes[0].set_yscale('log')
    axes[0].set_ylabel('完整挖掘耗时（秒，对数轴）',fontproperties=fp,fontsize=9)
    axes[1].set_ylabel('最慢分区内核（秒）',fontproperties=fp,fontsize=9)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,frameon=False,ncol=5,fontsize=8,loc='outside upper center')
    fig.savefig(ROOT/'结果'/'算法规模变化.png',dpi=230);plt.close(fig)

def main():
    audited=read('算法比较汇总.json');data=audited['scenarios'];correct=audited['correctness']
    retail=data['零售全量'];fashion=data['服装全量'];low=data['服装低阈值'];high=data['服装高阈值'];two=data['服装两步']
    framework=read('框架实验汇总.json');environment=audited['environments'][0]
    diagnostic=read('算法比较/波动诊断.json')
    paired=framework['服装日级']['变化']['metrics']
    groups=framework['服装日级']['序列']['metrics']['groups']
    evaluation_days=[next(row['baskets'] for row in groups if row['period']==period and row['split']=='evaluation') for period in (0,1)]
    fastest=min(METHODS[:-1],key=lambda method:median(fashion,method))
    slowest=max(METHODS[:-1],key=lambda method:median(fashion,method))
    figures(data)
    # Page 1
    p('事件序列中的频繁模式<br/>与行为变化分析','title')
    p('GSP、PrefixSpan、SPADE 与 SPAM 的 Spark 框架及实证比较<br/>大数据处理课程实验报告　｜　2026 年 10 月 31 日','subtitle')
    h('1. Abstract')
    p('本项目从真实交易中发现跨时间购物篮的频繁行为，并为后续跨期变化分析提供候选模式。针对候选生成、前缀投影、垂直列表和位图四类策略，分别实现 GSP、PrefixSpan、SPADE 与 SPAM 的核心搜索过程，将它们接入相同的 Spark 分区挖掘、候选合并及全局精确计数流程；另以 Spark MLlib 原生 PrefixSpan 作为工程参考。数据层保留分钟级零售与 H&amp;M 日级购买的区别，同日购买不被人为排列为先后事件。')
    p(f'复用全量交易预处理后，本轮在 763 名零售发现顾客和 {comma(fashion["input"]["customers"])} 名 H&amp;M 发现顾客上进行 {audited["complete_runs"]} 次正式测量。所有场景的五个实现均得到完全相同的频繁模式与支持数；主设置分别得到 {comma(retail["patterns"])} 与 {comma(fashion["patterns"])} 个模式。H&amp;M 主实验中，统一框架内 {fastest} 的三次耗时中位数最小，为 {median(fashion,fastest):.2f} 秒。结果表明，算法选择还取决于候选规模、数据表示及框架开销；单机上的两个执行器验证了分布式流程，但尚不能证明多机扩展能力。')
    p('<b>关键词：</b>大数据处理；频繁序列；Spark；前缀投影；垂直列表；位图','small')
    h('2. Introduction')
    p('频繁项集关心共同出现，频繁序列进一步要求事件顺序。本课题把课程中的支持度剪枝、分组聚合、分区存储和 Spark 计算连接起来，回答三个问题：四种算法是否得到同一结果；在真实数据上各付出多少时间与内存；输入规模和支持度改变后，瓶颈发生在哪里。')
    table([
        ['原始研究','贡献及项目角色','仍需检验的代价'],
        ['GSP [1]，EDBT 1996','类 Apriori 逐层候选生成与剪枝；经典基准。','频繁单项多时，候选连接与逐层计数可能膨胀。'],
        ['PrefixSpan [2]，ICDE 2001','前缀投影、递归增长；与现有 Spark 基线衔接。','投影扫描、状态维护及模式数量仍决定成本。'],
        ['SPADE [3]<br/>Machine Learning, 2001','垂直 ID 列表、时序连接和等价类分解。','大量结束位置和列表连接会占用资源。'],
        ['SPAM [4]，KDD 2002','位图、位运算与深度优先搜索；位图方案。','原文假定数据及结构可驻留主存；收益依赖表示与数据。']
    ],[130,192,172])
    p('这些是不同搜索与存储策略，不代表算法代际越晚就必然越快。本文复现其核心思想，不宣称重现原作者的全部实现或提出新的序列挖掘算法。','small')
    # Page 2
    page();h('3. Method')
    sub('3.1 数据模型、模式语言与支持度')
    p('顾客 u 的序列 S<sub>u</sub>=(B<sub>u,1</sub>,…,B<sub>u,m</sub>) 是按时间排列的无序购物篮。零售记录按顾客和原时间戳合篮；H&amp;M 按顾客和自然日合篮，并连接商品维表映射为商品类型。H&amp;M 相同购买明细保留，集合化仅发生在篮内；不从只有日期的数据恢复小时或订单顺序。')
    equation(r'X_u(P)=\mathbf{1}\{\exists j_1<\cdots<j_k:\ a_i\in B_{u,j_i},\ i=1,\ldots,k\}',21)
    equation(r'P\in\mathcal{F}(\sigma,L)\Leftrightarrow 1\leq |P|\leq L\ \mathrm{and}\ C(P)=\sum_{u=1}^{N}X_u(P)\geq\lceil\sigma N\rceil',22)
    p('P=(a₁,…,aₖ) 每一步只有一个项目，可跳篮，可跨篮复购，无最大间隔约束。每顾客对每模式只计一次。〈{A,B},{B}〉支持 A→B 和 B→B；仅有 {A,B} 一篮时不支持 A→B。本文不枚举 {A,B}→C 这样的篮内多项目步骤。','small')
    sub('3.2 共用的 Spark 数据处理与挖掘框架')
    story.append(Architecture())
    p('图 1　全量预处理与可替换的挖掘层。Spark SQL 完成质量检查、维表连接和年/月 Parquet 分区；按顾客聚合后显式按时间排序。四种算法共用下层流程，已有配对变化分析继续接收其候选。','caption')
    p('将完整顾客序列按哈希分到 R 个互不相交分区 U<sub>r</sub>，每个分区内以相同相对支持度 σ 运行所选内核，取局部频繁模式并集 A。Driver 仅接收有上限的 A，建立前缀树并广播；再次分区扫描完整顾客序列，按模式归并支持人数，保留全局达到阈值者。')
    sub('3.3 两阶段挖掘的完备性')
    equation(r'C(P)=\sum_{r=1}^{R}C_r(P),\quad N=\sum_{r=1}^{R}n_r,\quad A=\bigcup_{r=1}^{R}\{P:C_r(P)\geq\lceil\sigma n_r\rceil\}',23)
    p('若全局频繁 P 不在 A 中，则在每个非空分区都有整数 C<sub>r</sub>(P)&lt;ceil(σn<sub>r</sub>)，即 C<sub>r</sub>(P)&lt;σn<sub>r</sub>。相加得 C(P)&lt;σN，与全局频繁矛盾。因此局部并集不漏解；第二阶段精确计数排除仅局部频繁的候选，输出恰为目标集合。空分区不产生候选。该证明将 Partition [5] 的局部候选原则用于顾客序列，不把原频繁项集论文称为序列算法。')
    # Page 3
    page();h('3. Method（续）')
    sub('3.4 四种内核为何保持同一语义')
    p('<b>GSP：</b>以频繁单项为起点。长度 k−1 的模式满足前后缀连接条件时形成长度 k 候选；若删除任一项目得到的子序列不频繁，候选立即剪枝。依据是“支持长模式的顾客必支持其任一子序列”。候选进入前缀树，逐顾客计数后得到本层频繁模式，再进入下一层。树的状态在整个购物篮扫描结束后才扩展，防止同篮走两步。')
    p('<b>PrefixSpan：</b>每个前缀为每名支持顾客保留最早结束位置，只扫描其后的投影后缀，收集可追加项目。对无间隔上限的单项目步骤，较早结束位置留下的可选后缀包含所有较晚位置的后缀，因此这种压缩不漏解。频繁扩展递归增长到 L；如果以后引入最大间隔，必须重新设计状态，不能直接沿用这一压缩。')
    p('<b>SPADE：</b>为模式 P 保存垂直表 I(P)，记录每个顾客所有合法结束位置。同一前缀 q 的等价类内，P=q·a 与 Q=q·b 进行时序连接，构成 q·a·b；每位顾客只需保留右表中严格晚于左表最早结束位置的条目：')
    equation(r'I_u(qab)=\{t\in I_u(qb):t>\min I_u(qa)\}',24)
    p('左表为空时结果为空；支持数为结果中非空顾客列表的数量。共同前缀保证连接得到合法扩展；反之，合法 qab 的末位置必属于 qb 且晚于某个 qa 的结束位置，故会被保留。实现用有序位置元组、二分定位和等价类递归，未复刻原论文全部磁盘布局。','small')
    p('<b>SPAM：</b>每名顾客使用一个独立整数位图 Mᵤ(a)，第 t 位表示项目 a 出现在第 t 篮。将前缀位图的最早置位位置记为 e，构造只保留 e 之后位置的掩码，再与扩展项目位图按位与：')
    equation(r'M_u(Pa)=M_u(a)\ \mathrm{AND}\ \mathrm{SuffixMask}(\min\mathrm{SetBits}(M_u(P))+1)',25)
    p('结果非零即该顾客支持扩展；支持数不是置位数之和。位图边界按顾客隔离，不允许跨人连接。以深度优先方式增长，并按支持度剪枝。这里用 Python 整数实现 S-step；没有篮内 I-step，也没有把 Python 位图等同于原作者的底层工程实现。','small')
    sub('3.5 公平性与框架边界')
    p('四个内核统一字符串到整数的编码、局部单项过滤、输入分区、阈值和全局计数。MLlib [6] 单独列为原生工程基线：它使用 JVM 与自身分布式策略，内部还探索多项目步骤，最终只筛选单项目步骤。因此它与 Python 内核的耗时差不能仅归因于算法。局部分区需能装入工作进程；候选并集超过 250,000 个时明确失败，不静默截断。')
    # Page 4
    page();h('4. Experiment')
    sub('4.1 环境与数据范围')
    p(f'实验主机为 Intel Core i9-14900HX（24 物理核 / 32 逻辑线程）、15.63 GiB 内存；WSL2 Ubuntu 可见约 {environment["physical_memory_visible_bytes"]/1024**3:.2f} GiB。使用 Python {environment["python"]}、Java {environment["java"]}、Spark / PySpark {environment["spark"]}。Standalone 启动两个独立 worker / executor，各 2 核、1,536 MiB；Driver 1,536 MiB。所有实验统一 4 个顾客分区，关闭自适应分区与 Python worker 复用。新增数据、依赖、日志及临时目录均在 D 盘。')
    p('Online Retail II [7] 的 1,067,371 条原始明细经质量规则与完整字段去重后为 776,577 条。H&amp;M [8,9] 的 31,788,324 条购买连接 105,542 行商品维表，来源为固定版本的基础交易 Parquet 转换，逐文件校验 SHA-256。复用已有全量 Spark 清洗与序列结果，本轮重新执行以下发现集上的算法比较。')
    table([
        ['本轮挖掘输入','零售分钟','H&amp;M 日级'],
        ['观察窗口','2010-01-01 至 12-01','2019-01-01 至 09-01'],
        ['发现顾客 N',comma(retail['input']['customers']),comma(fashion['input']['customers'])],
        ['购物篮 / 篮内项目出现',f'{comma(retail["input"]["baskets"])} / {comma(retail["input"]["item_occurrences"])}',f'{comma(fashion["input"]["baskets"])} / {comma(fashion["input"]["item_occurrences"])}'],
        ['项目层级','商品编码','商品类型'],
        ['5% 阈值对应人数',comma(math.ceil(retail['input']['customers']*.05)),comma(math.ceil(fashion['input']['customers']*.05))]
    ],[150,164,180])
    p('窗口均左闭右开。原项目先选两期均有至少两个篮的固定顾客队列，再按顾客哈希划分发现 / 留出集；此次只在第一期发现集上比较挖掘。H&amp;M 的全体交易数不能作为本轮模式支持度分母。','caption')
    sub('4.2 实验协议与测量口径')
    p('主设置 σ=5%、L=3。零售全发现集、H&amp;M 全发现集，以及 H&amp;M 固定哈希的 10%、50% 嵌套子集均重复 3 次，报告中位数和最小—最大范围。各轮按固定种子打乱并轮换算法顺序；先完成公共小样本预热与数据缓存。另以 H&amp;M 全发现集测试 σ=2%、10% 及 L=2，每种实现各运行 1 次，用于探索参数影响，不据此检验显著速度差。')
    p('完整挖掘时间从缓存序列开始，包含局部挖掘、候选合并、全局精确计数及清理，排除下载、原始清洗、输入缓存准备和结果文件写出。内核时间包含各分区编码与搜索，记录最慢分区；内存为单次运行中局部挖掘 Python 工作进程的最大 Linux RSS 高水位，包含解释器、输入和输出结构，不含 JVM，也不是全系统峰值。')
    sub('4.3 正确性与证据保存')
    p(f'{correct["databases"]} 个边界 / 随机小数据库经独立组合穷举核对，完成 {comma(correct["algorithm_database_parameter_checks"])} 次算法—参数检查和 {comma(correct["support_entries_checked"])} 个支持数核对；另有 {comma(correct["partition_completeness_checks"])} 次不均匀及空分区并集检查。正式实验保存每次耗时、分区统计、完整模式、结果 SHA-256、源程序指纹及 Spark 事件日志。')
    # Page 5
    page();h('4. Experiment（续）')
    sub('4.4 主实验：相同结果下的耗时')
    table([['实现','零售完整挖掘 / 秒','H&amp;M 完整挖掘 / 秒']]+
        [[m if m!='MLlib' else 'MLlib PrefixSpan<br/>原生工程参考',time_cell(retail,m),time_cell(fashion,m)] for m in METHODS],
        [164,165,165])
    p('表 1　三次运行中位数；方括号为实测最小—最大值，不是置信区间。前四行共用 Spark 包装流程；最后一行使用 MLlib 自身执行策略。','caption')
    p(f'五个实现对零售均得到一步 / 二步 / 三步 '+ ' / '.join(comma(retail['counts_by_length'].get(str(i),0)) for i in (1,2,3))+f' 个模式，对 H&amp;M 均得到 '+ ' / '.join(comma(fashion['counts_by_length'].get(str(i),0)) for i in (1,2,3))+f' 个。全部 {audited["complete_runs"]} 次正式测量的输出按场景逐项比较一致，并非只比较模式总数。')
    sub('4.5 内核耗时与内存')
    table([['统一框架内核','H&amp;M 最慢分区 / 秒','H&amp;M 单进程 RSS / MiB','零售单进程 RSS / MiB']]+
        [[m,f'{median(fashion,m,"kernel_seconds_max"):.3f}',f'{median(fashion,m,"peak_single_python_worker_bytes")/1024**2:.1f}',f'{median(retail,m,"peak_single_python_worker_bytes")/1024**2:.1f}'] for m in METHODS[:-1]],
        [109,123,135,127])
    p('表 2　先对每次运行取四个分区中的最大值，再报告三次中位数。工作进程每次重新启动，减少前次分配对高水位的污染。未测得同口径的原生 MLlib 内存，因此没有填入 JVM 估计值。','caption')
    p(f'H&amp;M 中 {fastest} 的完整耗时中位数为 {median(fashion,fastest):.2f} 秒，{slowest} 为 {median(fashion,slowest):.2f} 秒，两者比值为 {median(fashion,slowest)/median(fashion,fastest):.2f}，只描述本次实现。PrefixSpan 与原生 MLlib 的三次范围重叠，不能仅凭中位数判定前者稳定更快。内核之外的进程启动、序列传递、候选合并及第二遍计数同样贡献完整耗时。')
    p(f'零售局部候选并集为 {comma(retail["candidate_union"])} 个，最终保留 {comma(retail["patterns"])} 个，膨胀为 {retail["candidate_inflation"]:.2f} 倍；H&amp;M 分别为 {comma(fashion["candidate_union"])} 与 {comma(fashion["patterns"])}，为 {fashion["candidate_inflation"]:.2f} 倍。不同局部分布会增加第二遍工作量，这个代价属于共同框架，而非某一种内核独有。')
    # Page 6
    page();h('5. Analysis')
    sub('5.1 数据规模与支持度的影响')
    plot_image('算法规模变化.png')
    p('图 2　H&amp;M 10%、50%、100% 嵌套顾客样本；σ=5%、L=3。左图为对数轴，点为三次中位数，误差棒为实测范围；右图是最慢分区内核时间。MLlib 无同口径内核指标。','caption')
    half_native=data['服装二分之一']['methods']['MLlib']['wall_seconds']
    native_diagnostic=next((row for row in diagnostic['anomalies'].values() if row['scenario']=='服装二分之一' and row['method']=='MLlib'),None)
    variation=(f'对应日志中存在长任务及垃圾回收，单任务 GC 计数最高 {native_diagnostic["maximum_single_task_gc_seconds"]:.2f} 秒；这不足以完全解释波动，不能全部归因于算法。' if native_diagnostic else '三次测量保留全部记录；仍需增加重复次数判断稳定差异。')
    p('50% 规模的 MLlib 耗时为 '+ '、'.join(f'{v:.2f}' for v in half_native['values'])+' 秒。'+variation+'三档样本同时改变顾客组成与频繁模式边界，资源未增加，因而不是线性复杂度或集群加速比证明。')
    table([['σ','模式数','GSP 秒','PrefixSpan 秒','SPADE 秒','SPAM 秒','MLlib 秒']]+
        [[f'{x["configuration"]["support"]:.0%}',comma(x['patterns'])]+[f'{median(x,m):.2f}' for m in METHODS] for x in [low,fashion,high]],
        [43,66,77,77,77,77,77])
    p('表 3　H&amp;M 全发现集、L=3。5% 为三次中位数，2% 和 10% 为单次探索；不把这些单次差异当作稳定排名。','caption')
    p(f'阈值由 5% 降为 2% 后，模式数从 {comma(fashion["patterns"])} 增至 {comma(low["patterns"])}，候选并集从 {comma(fashion["candidate_union"])} 增至 {comma(low["candidate_union"])}。输出与计数负担确实增加，但本组耗时并非严格单调：SPADE 的 2% 单次耗时 {median(low,"SPADE"):.2f} 秒，低于 5% 的三次中位数 {median(fashion,"SPADE"):.2f} 秒。这也说明参数实验仍需增加重复次数。')
    p(f'最长模式由 3 改为 2 时，H&amp;M 保留 {comma(two["patterns"])} 个模式；四种内核的完整耗时依次为 '+ '、'.join(f'{m} {median(two,m):.2f} 秒' for m in METHODS[:-1])+f'，原生 MLlib 为 {median(two,"MLlib"):.2f} 秒。这组仅运行一次，作用是确认长度限制确实改变任务，而非推导一般性的加速倍数。')
    # Page 7
    page();h('5. Analysis（续）')
    sub('5.2 从数据结构解释差异')
    gsp_partitions=retail['methods']['GSP']['first_run_partition_metrics']
    candidates2=sum(r['generated_candidates'].get('2',0) for r in gsp_partitions)
    local_items=[r['frequent_items'] for r in gsp_partitions]
    p(f'<b>商品种类与候选：</b>零售四个分区分别有 '+ '、'.join(map(str,local_items))+f' 个局部频繁单项；GSP 第一轮测量共生成 {comma(candidates2)} 个二步候选（含跨分区重复）。即使最终模式只有 {comma(retail["patterns"])} 个，生成及计数仍要付出成本。这与其较高的零售内存占用相符。H&amp;M 使用类别层级，不能把两数据集的差异仅解释为顾客人数差异。')
    p('<b>列表与位图：</b>SPADE 存储同一顾客的多个结束位置，连接时需要列表访问；SPAM 以整数位图压缩位置并利用按位与，但顾客字典、递归结果和 Python 对象仍有开销。PrefixSpan 的最早结束位置表示在当前无间隔约束下较紧凑。以上是结合实现和测量的解释，尚未通过逐个替换数据结构的消融实验隔离因果贡献。')
    sub('5.3 对原项目行为变化任务的影响')
    p(f'四个内核在同一参数下产生同一候选集合，因此换算法不会凭空改变统计结论。原框架在独立留出顾客上计数两期支持，以配对 McNemar 检验和 BY 校正 [10] 评估变化；发现与检验按顾客分离。H&amp;M 在 {comma(paired["evaluation_customers"])} 名留出顾客上对 {comma(paired["tested_patterns"])} 个二步 / 三步候选检验，{comma(paired["significant_by"])} 个通过校正，其中 {paired["increased"]} 个上升、{comma(paired["decreased"])} 个下降。这里沿用已保存的实算结果，没有将本轮重复计时当作新的统计样本。')
    p(f'留出顾客购买日总数同期从 {comma(evaluation_days[0])} 降为 {comma(evaluation_days[1])}，观察机会减少是大量模式下降的替代解释。频繁度不等于因果或偏好变化。日级合篮还会消除日内顺序：固定顾客、窗口和项目编码时，日级匹配必能映射回原时间序列，故日级支持数不超过原时间支持数；算法加速不能恢复缺失的时间精度。')
    sub('5.4 当前不足与下一步验证')
    events=audited['event_metrics'];tasks=sum(x['tasks'] for x in events);fails=sum(x['failed_tasks'] for x in events)
    p(f'<b>部署范围：</b>正式 Spark 应用共记录 {comma(tasks)} 次任务结束、{fails} 次失败任务，两个执行器均承担工作；包含预热与输入准备。它们共用同一物理 CPU、内存及 D 盘。本轮没有验证跨机网络、HDFS 吞吐、故障恢复、节点扩容或超内存挖掘。已有预处理 YARN 入口需在目标集群验收；比较脚本目前读取项目内的共享本地路径。')
    p('<b>算法与测量范围：</b>只比较单项目步骤、无间隔约束、最长 2—3 步的两个交易领域，不能外推到长日志序列。三次重复主要反映当前机器波动，仍有 JVM 预热、操作系统缓存和后台负载影响。Python 高水位无法给出集群总内存，原生 MLlib 与共用包装层也不是语言完全受控的比较。')
    p('<b>后续重点：</b>固定工作负载逐步增加物理节点，记录吞吐、Shuffle、总内存及倾斜；对分区数与候选膨胀做消融；扩展长序列、低阈值与时间间隔约束。若候选目录或单顾客序列超过单进程容量，需要进一步设计分布式候选存储与可合并状态。','small')
    # Page 8
    page();h('6. Conclusion')
    p('本文在事件序列分析项目中实现了 GSP、PrefixSpan、SPADE 与 SPAM 四种核心策略，并构建统一的 Spark 分区候选生成和全局支持计数流程。通过反单调性、结束位置语义和局部候选完备性，说明四种方法在给定模式语言下应返回相同结果；独立穷举与真实数据比较进一步提供了验证。')
    p(f'全部 {audited["complete_runs"]} 次正式测量按场景得到一致模式与支持数，但耗时和内存随数据结构、支持度及输入组成变化。本次 H&amp;M 主设置的统一框架以 {fastest} 耗时中位数最低；这支持当前参数下的实现选择，不构成普遍算法优劣结论。项目保留原生 MLlib PrefixSpan 作为工程参照，并继续使用日级适配及独立留出统计。后续工作的重点是多机资源行为、候选膨胀与长序列约束，而不是只看本机能否运行。')
    sub('参考文献')
    references=[
        ('Srikant R, Agrawal R. Mining Sequential Patterns: Generalizations and Performance Improvements. EDBT, 1996: 3–17. DOI: 10.1007/BFb0014140.','https://rsrikant.com/papers/edbt96.pdf'),
        ('Pei J, et al. PrefixSpan: Mining Sequential Patterns Efficiently by Prefix-Projected Pattern Growth. ICDE, 2001: 215–224. DOI: 10.1109/ICDE.2001.914830.','https://www.cs.sfu.ca/~jpei/publications/span.pdf'),
        ('Zaki M J. SPADE: An Efficient Algorithm for Mining Frequent Sequences. Machine Learning, 2001, 42: 31–60. DOI: 10.1023/A:1007652502315.','https://philippe-fournier-viger.com/spmf/SPADE.pdf'),
        ('Ayres J, et al. Sequential PAttern Mining using A Bitmap Representation. KDD, 2002: 429–435. DOI: 10.1145/775047.775109.','https://www.cs.cornell.edu/johannes/papers/2002/kdd2002-spam.pdf'),
        ('Savasere A, Omiecinski E, Navathe S. An Efficient Algorithm for Mining Association Rules in Large Databases. VLDB, 1995: 432–444.','https://www.vldb.org/conf/1995/P432.PDF'),
        ('Apache Spark. Frequent Pattern Mining / PrefixSpan, version 4.0.1. 官方文档，2026-10-31 访问。','https://spark.apache.org/docs/4.0.1/ml-frequent-pattern-mining.html'),
        ('Chen D. Online Retail II [Dataset]. UCI Machine Learning Repository. DOI: 10.24432/C5CG6D.','https://archive.ics.uci.edu/dataset/502/online+retail+ii'),
        ('H&M. Personalized Fashion Recommendations. Kaggle, 2022. 原始交易与商品数据。','https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data'),
        ('Microsoft. hnm-search-data. 本文仅使用基础交易和商品表的完整 Parquet 转换；固定版本 ac35fedf926b4a7e7ca4a4303ee275db866abd8f。','https://huggingface.co/datasets/microsoft/hnm-search-data'),
        ('Benjamini Y, Yekutieli D. The control of the false discovery rate in multiple testing under dependency. Annals of Statistics, 2001, 29(4): 1165–1188. DOI: 10.1214/aos/1013699998.','https://www.math.tau.ac.il/~ybenja/depApr27.pdf')]
    styles['ref'].fontSize=8.2;styles['ref'].leading=12.1;styles['ref'].spaceAfter=7
    for i,(title,url) in enumerate(references,1):
        p(f'[{i}] {html.escape(title)} <link href="{html.escape(url,quote=True)}" color="#147D92">原文 ↗</link>','ref')
    output=ROOT.parent/'序列算法对比报告.pdf'
    def decorate(c,doc):
        c.saveState();c.setStrokeColor(colors.HexColor('#CBD6DD'));c.line(50,803,545,803)
        c.setFont('Chinese',8);c.setFillColor(colors.HexColor('#526472'))
        c.drawString(50,815,'大数据处理课程项目　|　频繁序列算法对比')
        c.drawRightString(545,28,f'{doc.page} / 8');c.restoreState()
    doc=SimpleDocTemplate(str(output),pagesize=(595.28,841.89),leftMargin=50,rightMargin=50,
        topMargin=53,bottomMargin=48,title='事件序列中的频繁模式与行为变化分析：四种算法比较',
        author='大数据处理课程项目',pageCompression=1)
    doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
    reader=PdfReader(output)
    save_json('对比报告生成.json',{'pages':len(reader.pages),'bytes':output.stat().st_size,'sha256':sha256(output),'output':str(output)})
    (ROOT/'结果'/'对比报告文本.txt').write_text('\n\n'.join(x.extract_text() for x in reader.pages),encoding='utf-8')
    print(f'pages={len(reader.pages)}, bytes={output.stat().st_size}')
    assert len(reader.pages)==8,'Report must be eight pages'

if __name__=='__main__':main()
