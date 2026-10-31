"""Eight-page course report generated exclusively from committed experiment outputs."""
from 生成报告 import (ROOT,read,story,p,h,sub,page,table,equation,plot_image,styles,BLUE,INK,
    fp,plt,np,colors,Flowable,SimpleDocTemplate,PdfReader,save_json,sha256)
import json, html

class Architecture(Flowable):
    def __init__(self):super().__init__();self.width=494;self.height=145
    def draw(self):
        c=self.canv
        boxes=[('数据适配','零售分钟 / 服装日期'),('Spark SQL','质量检查 / 维表连接'),
               ('分区仓库','年、月 Parquet'),('顾客序列','按顾客聚合并排序')]
        for i,(title,detail) in enumerate(boxes):
            x=i*125
            c.setFillColor(colors.HexColor('#EDF4F7'));c.setStrokeColor(colors.HexColor('#BDD0DB'))
            c.roundRect(x,86,119,49,5,fill=1,stroke=1)
            c.setFillColor(BLUE);c.setFont('ChineseBold',9.5);c.drawCentredString(x+59.5,116,title)
            c.setFont('Chinese',7.8);c.drawCentredString(x+59.5,99,detail)
            if i<3:c.line(x+120,110,x+124,110)
        bottom=[('工作节点 1','模式匹配 / 分区统计'),('工作节点 2…N','模式匹配 / 分区统计'),('Driver','有限候选 / 统计检验')]
        for i,(title,detail) in enumerate(bottom):
            x=i*167
            c.setFillColor(colors.HexColor('#F4F7F2'));c.setStrokeColor(colors.HexColor('#BDCEB8'))
            c.roundRect(x,13,159,49,5,fill=1,stroke=1)
            c.setFillColor(BLUE);c.setFont('ChineseBold',9.5);c.drawCentredString(x+79.5,43,title)
            c.setFont('Chinese',8);c.drawCentredString(x+79.5,26,detail)
        c.setFillColor(INK);c.setFont('Chinese',8)
        c.drawCentredString(247,73,'MLlib PrefixSpan 分布式挖掘 → 广播有界候选 → 归并支持计数')
        c.line(80,62,80,68);c.line(247,62,247,68);c.line(414,62,414,68)

def metric(data,run,stage):return data[run][stage]['metrics']
def grouped(sequence,period,split):return next(r for r in sequence['groups'] if r['period']==period and r['split']==split)
def comma(x):return f'{x:,}'

def main():
    data=read('框架实验汇总.json');check=read('分布式校验.json');labels=read('服装类别名称.json')
    retail={s:metric(data,'零售分钟',s) for s in ['清洗','序列','模式','变化']}
    fashion={s:metric(data,'服装日级',s) for s in retail}
    gran=data['granularity_ablation']
    hmresults=json.loads((ROOT/'数据'/'分布式仓库'/'运行批次'/'服装日级'/'变化'/'完整统计.json').read_text(encoding='utf-8'))
    negative=sorted([r for r in hmresults if r['delta']<0],key=lambda r:r['delta'])[:2]
    positive=sorted([r for r in hmresults if r['delta']>0],key=lambda r:r['delta'],reverse=True)[:2]
    examples=negative+positive
    fig,ax=plt.subplots(figsize=(7.2,2.35),layout='constrained')
    y=np.arange(len(examples));height=.32
    ax.barh(y-height/2,[r['support0']*100 for r in examples],height,color='#829AAA',label='2019')
    ax.barh(y+height/2,[r['support1']*100 for r in examples],height,color='#147D92',label='2020')
    ax.set_yticks(y,[' → '.join(labels.get(x,x) for x in r['pattern']) for r in examples],fontsize=8.2)
    ax.invert_yaxis();ax.set_xlabel('留出顾客支持率（%）',fontproperties=fp);ax.legend(frameon=False,ncol=2);ax.grid(axis='x',alpha=.18)
    fig.savefig(ROOT/'结果'/'服装模式变化.png',dpi=220);plt.close(fig)
    app_id=data['服装日级']['变化']['application_id']
    events=next(x for x in data['event_metrics'] if x['application_id']==app_id)
    hmdis=grouped(fashion['序列'],0,'discovery')['customers'];hmeval=grouped(fashion['序列'],0,'evaluation')['customers']
    hmpatterns=fashion['模式']['pattern_counts'];rtpatterns=retail['模式']['pattern_counts']
    # Page 1
    p('事件序列中的频繁模式<br/>与行为变化分析','title')
    p('面向多源交易的 Spark 分布式处理框架与日粒度适配<br/>大数据处理课程研究报告　｜　2026 年 10 月 31 日','subtitle')
    h('1. Abstract')
    p('本课题研究大量交易事件中哪些行为经常先后发生，以及这些模式在不同时间窗口内如何改变。项目以可扩展的数据处理框架为主要产出：使用 Apache Spark 与 PySpark 实现数据适配、质量检查、分区存储、顾客序列构建、频繁模式挖掘及跨期统计。统一数据模型同时支持分钟级零售记录与仅含日期的服装交易；同一顾客的同一时间单位被合并为无序购物篮，避免制造不存在的先后顺序。')
    p(f'实验完整处理 Online Retail II 的 1,067,371 条明细与 H&amp;M 的 31,788,324 条交易。以 Spark MLlib PrefixSpan 发现单商品步骤序列，再在独立顾客上进行配对检验与 BY 多重校正。H&amp;M 全量处理在同一物理主机上的两个独立 Spark 工作进程中完成，形成 {comma(fashion["序列"]["cohort_customers"])} 人的配对队列；其 {comma(fashion["变化"]["tested_patterns"])} 个候选中有 {comma(fashion["变化"]["significant_by"])} 个通过校正。零售数据的 Spark 结果与独立实现逐项吻合。时间粒度对照进一步表明，日级合并会丢失部分跨篮顺序，数据粒度必须进入分析定义。')
    p('<b>关键词：</b>大数据处理；Spark；频繁序列；分区存储；日粒度；行为变化','small')
    h('2. Introduction')
    sub('2.1 从单次分析走向可扩展的处理流程')
    p('课程中的频繁项集和关联规则能够回答“哪些商品经常共同出现”，而顾客事件序列还要求保留时间顺序。随着数据规模和来源增加，困难不只在于挖掘算法：商品编码、重复记录、时间精度、跨表连接与分区聚合的语义若不统一，即使程序成功运行，结果也可能失真。')
    p('因此，本文的核心目标是建立可通过参数迁移到集群的批处理框架，并用两套真实数据验证数据流和结果的一致性。课内联系包括 MapReduce 式分区归并、Spark RDD 与 DataFrame、数据清洗、数据仓库分区以及频繁模式的支持度剪枝；课外扩展为事件序列、跨期配对推断与时间粒度的信息损失。')
    p('本文把“行为变化”限定为固定顾客队列中序列支持率的变化。它不直接等同于偏好改变或因果作用。框架提供本机与 Standalone 提交入口，并给出面向课程 Hadoop 环境的 YARN / HDFS 配置入口；真实多机性能仍需在相应硬件上测量。')
    # Page 2
    page();h('2. Introduction（续）')
    sub('2.2 已有研究及本项目的位置')
    table([
        ['研究','贡献','本课题需要补足的部分'],
        ['Agrawal 与 Srikant [1]','定义跨事务频繁序列，将支持度从项集推广到有序事件。','频率本身不能说明跨期变化或其原因。'],
        ['PrefixSpan [2]；SPADE [3]','分别用前缀投影与垂直标识列表提高模式搜索效率。','算法不会自动解决输入质量、时间精度和多源编码。'],
        ['Spark / RDD [4]','以分区数据与变换血缘支持并行计算、复用及故障恢复。','通用计算抽象仍需具体的数据模型和一致性检查。'],
        ['SPEck [5]','借助不同零模型与采样区分高频和统计显著序列。','零模型依赖研究问题；跨年配对差异是另一种检验目标。'],
        ['HOPPER [6]；流程漂移研究 [7]','前者利用事件间延迟描述模式，后者刻画多类过程漂移。','精细延迟方法不能恢复日级数据未记录的小时顺序；双窗口比较也不能定位变点。']
    ],[119,179,196])
    p('本文沿用已有序列挖掘和统计方法，贡献集中在可复用的数据流程、跨粒度适配及实证核验。没有将“改用 Spark”视为新的挖掘算法，也未复现上述研究全部实验，因此不作算法优越性声明。')
    h('3. Method')
    sub('3.1 统一事件模型与支持度')
    p('一条清洗后记录表示为 (u,t,a,c,q,p)，依次为顾客、事件时间、商品、分析层级上的项目、数量和价格。分析项目 c 可以是原商品，也可以是商品类别。给定时间粒度 g，以 τ<sub>g</sub>(t) 将时间映射为原时间点或自然日；同一顾客、同一映射时间的项目取集合 B。按时间严格递增排列，得到窗口 y 中的序列 Sᵤʸ。')
    equation(r'X_u^y(P)=\mathbf{1}\{\exists j_1<\cdots<j_k:\ a_r\in B_{u,j_r}^y,\ r=1,\ldots,k\}',11)
    p('模式 P=(a₁,…,aₖ) 每一步只包含一个项目，可以跳过中间篮，也允许同一项目在不同篮复购。每名顾客对每个模式最多计一次支持；〈{A,B},{B}〉支持 A→B，但第一篮中的 A、B 不构成先后关系。','small')
    # Page 3
    page();h('3. Method（续）')
    sub('3.2 分布式架构与数据适配')
    story.append(Architecture())
    p('图 1　框架的数据流。交易与完整顾客序列留在分区数据中；Driver 只接收质量摘要、受上限约束的候选目录及归并后的支持计数。工作节点数量由集群资源配置决定。','caption')
    p('<b>清洗层：</b>使用明确的字段类型读入 CSV / Parquet，将不合法记录按原因写入隔离表。H&amp;M 的小型商品维表通过广播连接补充类别；维表键必须唯一，防止连接把交易行数放大。清洗结果按年、月写入 Parquet，并以顾客哈希桶分散同月写入负载。')
    table([
        ['适配项目','Online Retail II','H&amp;M'],
        ['时间与购物篮','同顾客、同时间戳合并；另支持日级重建。','仅知道日期；同顾客同日合并，不能视为精确订单。'],
        ['重复与编码','按原基准的完整业务字段去重；保留标准商品编码。','保留相同购买明细的次数；商品号规范为十位字符串。'],
        ['分析层级','商品编码。','可选商品或商品类型；主实验采用类型，降低换款编码影响。']
    ],[85,204,205])
    p('<b>序列层：</b>先筛选两个左闭右开的观察窗口，按顾客和时间聚合购物篮。通过顾客键 Shuffle，把该顾客的篮放到同一归并组；对收集到的“时间—集合”结构显式排序，再生成序列。不能依赖输入文件顺序或 collect_list 的返回顺序。两窗口均至少有两个篮的顾客组成固定队列，哈希划分发现集和留出集。')
    sub('3.3 分区归并为什么保持语义')
    p('篮内的集合并满足交换律、结合律和幂等律，因此各分区先去重聚合，再取并集，与集中处理全部记录得到相同篮。项目集合只在这一层去重；H&amp;M 的原始购买次数仍保存在交易与数量统计中。顾客完整序列完成匹配后，按模式归并的支持计数也是可加的：')
    equation(r'C_y(P)=\sum_{r=1}^{R}\sum_{u\in U_r}X_u^y(P),\qquad U_r\cap U_s=\varnothing\ (r\ne s)',12)
    p('关键条件是同一顾客不能被拆成多个独立支持样本。实现先构造每顾客每窗口一条序列，再按顾客连接两个窗口，保证分区统计不会重复计人。','small')
    # Page 4
    page();h('3. Method（续）')
    sub('3.4 候选发现、支持计数与差异检验')
    p('主实验在发现集第一个窗口采用 5% 最小支持度、最长 3 个项目的 PrefixSpan [2,11]。扩展模式的支持顾客必然是前缀支持顾客的子集，故 s(P·a)≤s(P)，不频繁前缀可以剪枝。MLlib 原生允许篮内多项目步骤；输出后仅保留各步骤长度均为 1 的序列，与本文定义一致。')
    p('候选目录建立共享前缀树，广播给执行进程。每个分区逐顾客匹配两期序列，只返回模式的四个计数：两期支持人数以及“只在前期 / 只在后期支持”的人数 b、c。树的状态在整篮扫描后统一扩展，保证不能在同一天内连走两步。')
    equation(r'\widehat{s}_y(P)=C_y(P)/n,\quad\widehat{\Delta}(P)=(C_1-C_0)/n,\quad Z\mid(b+c)\sim\mathrm{Binomial}(b+c,1/2)',13)
    p('顾客之间可视为独立、两期不一致方向等概率时，双侧精确 McNemar 检验的 p 值为 min{1,2Pr[Z≤min(b,c)]}，b+c=0 时取 1。发现集与留出集按顾客分离；全部发现出的二步、三步候选进入同一检验族，再做 BY 校正 [8]。')
    equation(r'p_{(k)}\leq \frac{k\alpha}{mH_m},\qquad H_m=\sum_{j=1}^{m}\frac{1}{j},\quad\alpha=0.05',14)
    p('取满足上式的最大 k，拒绝前 k 个假设；允许模式检验之间存在依赖。该控制不消除商品供给、活动频率或观察窗口造成的混杂，也不把高度相关的多个序列变成独立行为规律。')
    sub('3.5 时间粗化的边界与资源控制')
    p('<b>粒度命题：</b>固定顾客、窗口、项目编码和模式，把同日多个篮合并后，任何仍然成立的跨日匹配都能在原序列中找到，故 X<sub>day</sub>(P)≤X<sub>time</sub>(P)。反向不成立：上午 A、下午 B 合并为 {A,B} 后不再支持 A→B。该结论不适用于同时改变顾客队列或项目类别的比较。')
    p('<b>资源边界：</b>候选广播上限为 50,000 个；每顾客每窗口最多 10,000 篮、每篮最多 5,000 个项目，超限明确失败而不静默截断。PrefixSpan 的局部投影阈值设为 200,000，它是投影规模参数，不是严格内存上限。低支持度仍可能导致模式组合爆炸。')
    p('<b>批次与恢复：</b>输出使用独立运行批次；四阶段完成后分别写入参数指纹、数据摘要、应用编号和完成清单。重复运行只跳过同参数的完成阶段，中断阶段可重建。输入需保持不可变；当前实现是批处理快照，尚未实现迟到事件、增量修订或跨月状态维护。','small')
    sub('3.6 大样本检验的数值稳定性')
    p('H&amp;M 实验中有 149 个原始 p 值小于普通双精度尾概率计算的表示范围，直接输出为 0。为保留其数量级，对这类结果计算二项概率各项的对数，再以 log-sum-exp 求尾部和；BY 排序和校正也在对数域进行。完整结果同时保存 log<sub>10</sub>(p)、log<sub>10</sub>(q) 和下溢标记，数值 0 不被解释为数学概率为零。使用 2,000 个不一致配对全部同向的案例核对，结果与 p=2<super>−1999</super> 的解析值一致；校正后的显著判定未因数值补算改变。')
    # Page 5
    page();h('4. Experiment')
    sub('4.1 实验环境与执行范围')
    p('主机为 Intel Core i9-14900HX，24 物理核 / 32 逻辑线程，15.63 GiB 内存。Spark 在现有 WSL2 Ubuntu 环境执行，WSL 可见约 7.6 GiB；Python 3.12.3、OpenJDK 21.0.12.1、Spark / PySpark 4.0.1、NumPy 1.26.4、SciPy 1.11.4。代码、数据、新增依赖、Shuffle、日志和下载缓存均位于 D 盘项目目录。')
    table([
        ['配置','零售主实验','H&amp;M 主实验'],
        ['执行方式','local[4]；Driver 3 GiB','Standalone；2 个工作进程'],
        ['执行资源','同 JVM 内执行任务','每执行器 2 核、1,536 MiB；Driver 1,536 MiB'],
        ['SQL 初始 Shuffle 分区','8','24；启用自适应执行'],
        ['存储与验证范围','D 盘本地 Parquet','共享本地路径；同主机跨进程验证']
    ],[120,165,209])
    p('两工作节点是两个独立进程，实际承担不同任务；它们仍共享同一 CPU、内存与磁盘。YARN / HDFS 提交入口按官方文档 [12] 组织，未在物理多机集群执行；下文耗时不表示集群加速比，也不是与 DuckDB 的公平性能竞赛。','small')
    sub('4.2 数据来源、完整性与队列')
    p('Online Retail II [9] 使用两张工作表的全部 1,067,371 条明细，按既有口径剔除无效顾客、撤销及非正交易、非标准编码后，完整字段去重得到 776,577 条记录。H&amp;M [10] 使用公开镜像对原始基础表的完整 Parquet 转换：7 个交易分片与商品维表，各文件均核对固定版本的 SHA-256；未使用其合成搜索数据。')
    table([
        ['数据特征','零售','H&amp;M'],
        ['有效明细 / 有交易顾客',f'776,577 / {comma(retail["清洗"]["customers"])}',f'{comma(fashion["清洗"]["rows"])} / {comma(fashion["清洗"]["customers"])}'],
        ['有交易商品 / 分析项目','4,619 / 4,619',f'{comma(fashion["清洗"]["products"])} / {fashion["清洗"]["items"]} 类'],
        ['两期窗口','2010、2011 年 1—11 月','2019、2020 年 1—8 月'],
        ['配对队列 / 发现 / 留出',f'1,548 / 763 / 785',f'{comma(fashion["序列"]["cohort_customers"])} / {comma(hmdis)} / {comma(hmeval)}']
    ],[136,169,189])
    p('H&amp;M 的 105,542 行商品维表键唯一，全部交易均匹配；有效交易行未因相同内容而去重。两个年份对齐月份，避开 2020 年 9 月的不完整末月。配对队列只代表两期均有重复购买日的顾客，不能把全部交易行数当成独立样本量。','small')
    # Page 6
    page();h('4. Experiment（续）')
    sub('4.3 全流程运行与模式结果')
    table([['指标','零售分钟','H&amp;M 日级'],
       ['清洗与分区 / 秒',f'{retail["清洗"]["wall_seconds"]:.1f}',f'{fashion["清洗"]["wall_seconds"]:.1f}'],
       ['序列构建 / 秒',f'{retail["序列"]["wall_seconds"]:.1f}',f'{fashion["序列"]["wall_seconds"]:.1f}'],
       ['模式挖掘 / 秒',f'{retail["模式"]["wall_seconds"]:.1f}',f'{fashion["模式"]["wall_seconds"]:.1f}'],
       ['配对统计 / 秒',f'{retail["变化"]["wall_seconds"]:.1f}',f'{fashion["变化"]["wall_seconds"]:.1f}'],
       ['一步 / 二步 / 三步模式',' / '.join(comma(rtpatterns.get(str(k),0)) for k in (1,2,3)), ' / '.join(comma(hmpatterns.get(str(k),0)) for k in (1,2,3))],
       ['检验族大小 / BY 显著',f'{comma(retail["变化"]["tested_patterns"])} / {comma(retail["变化"]["significant_by"])}',f'{comma(fashion["变化"]["tested_patterns"])} / {comma(fashion["变化"]["significant_by"])}'],
       ['显著上升 / 显著下降',f'{retail["变化"]["increased"]} / {retail["变化"]["decreased"]}',f'{fashion["变化"]["increased"]} / {fashion["变化"]["decreased"]}']
    ],[220,137,137])
    p('表中为各阶段一次实际运行的墙钟时间，包含阶段内质量检查和写出，不含下载、启动、独立核验、对数尾概率补算及报告生成。两数据集规模、项目层级与执行方式不同，不能据此比较算法优劣；缓存、D 盘挂载和系统负载也会影响时间。','caption')
    sub('4.4 分布式执行证据与独立核验')
    counts=events['executor_tasks']
    p(f'H&amp;M 应用的事件日志记录 {comma(events["tasks"])} 次任务结束，执行器任务分配为 '+ '、'.join(f'{key} 号 {comma(value)} 次' for key,value in sorted(counts.items()))+f'；失败任务 {events["failed_tasks"]} 次。累计 Shuffle 写出 {events["shuffle_write_bytes"]/1024**3:.2f} GiB，磁盘溢写 {events["disk_spill_bytes"]/1024**3:.2f} GiB。它们是各阶段任务的累计计数，含重复扫描和中间结果，不能当成原始数据大小。')
    p(f'对 40 个随机序列，组合穷举与 MLlib 得到的 {check["exhaustive_patterns_checked"]} 个频繁模式及支持数一致；另核查同篮无序和跨篮重复。H&amp;M 适配夹具验证了重复购买保留、无效日期隔离、商品连接与重分区后顺序不变。真实零售数据的 3,096 条“顾客—窗口”序列、1,669 个模式支持数、1,048 个配对计数及原始 p 值均与独立实现一致。')
    p(f'H&amp;M 的原始行数由另一引擎复核为 31,788,324；再使用独立贪心匹配器，对全部 {comma(hmeval)} 名留出顾客的 3 个代表模式逐个核算，两期支持数及不一致配对数均吻合。保留原始文件校验值、阶段清单、事件日志及完整统计表，支持逐项复查。')
    p('原单机 2% 阈值实验作为补充基准保留；本节采用 5% 阈值，因此检验族从 46,740 个变为 1,048 个，BY 校正值和显著数也随之变化。不能把检验族改变解释成 Spark 使同一统计结果变得更显著。','small')
    # Page 7
    page();h('5. Analysis')
    sub('5.1 大样本差异与业务解释之间仍有距离')
    plot_image('服装模式变化.png')
    p(f'图 2　H&amp;M 中支持率下降最多与上升最多的各两个模式。共同分母为 {comma(hmeval)} 名留出顾客，按差值选图属于事后描述；英文名称来自商品类型维表。箭头仅表示跨购买日的子序列。','caption')
    earlier_days=grouped(fashion['序列'],0,'evaluation')['baskets'];later_days=grouped(fashion['序列'],1,'evaluation')['baskets']
    p(f'类别层级减少了单件商品换款对编码的影响，也将不同商品合并，因而更容易形成复购模式。留出顾客的购买日总数从 {comma(earlier_days)} 降至 {comma(later_days)}，减少 {(1-later_days/earlier_days)*100:.2f}%；这会减少序列形成机会，是大量下降的重要替代解释。供给、渠道和活跃度也可能参与其中。大样本下很小的差异也会显著，必须同时查看百分点差、支持人数和观察机会。')
    sub('5.2 日粒度究竟损失了什么')
    table([['固定 785 名零售留出顾客','2010','2011'],
        ['分钟篮 → 日篮',f'{comma(gran["minute_baskets"][0])} → {comma(gran["day_baskets"][0])}',f'{comma(gran["minute_baskets"][1])} → {comma(gran["day_baskets"][1])}'],
        ['支持人数下降的模式 / 1,048',str(gran['patterns_with_reduced_support0']),str(gran['patterns_with_reduced_support1'])],
        ['丢失的“顾客—模式”匹配',comma(gran['lost_customer_pattern_matches0']),comma(gran['lost_customer_pattern_matches1'])]
    ],[260,117,117])
    p('此对照固定顾客、窗口、商品与候选，只合并同日购物篮；每个模式的日级支持人数均不大于分钟级，符合粗化命题。损失的是日内先后与部分同日复购，而跨日顺序仍可研究。H&amp;M 应回答“之后某天是否出现某类购买”，不能回答“同一天先买了什么”。','small')
    sub('5.3 当前不足与后续问题')
    p('框架仍有三个边界。第一，两个执行器共享物理主机，尚无真实跨机网络、节点故障或横向扩容试验；YARN 配置入口需要实机验收。第二，完整顾客序列在单组内聚合，超长顾客与低支持度造成的投影膨胀仍是瓶颈，需探索分块序列状态与负载均衡。第三，当前比较两个固定窗口，后续应加入最大时间间隔、等购买日数、商品可得性及顾客分群对照，再研究增量更新和漂移定位。')
    # Page 8
    page();h('6. Conclusion')
    p('本文围绕事件序列中的频繁模式与行为变化，构建了由多源适配、Spark 清洗、分区仓库、顾客序列、分布式挖掘和配对统计组成的批处理框架。其复用单位是参数化数据流程与统一事件语义，可以更换数据来源、项目层级、观察窗口及集群提交方式。')
    p('百万级零售与三千万级服装交易的实际运行验证了全流程；独立实现与匹配器检查支持了结果的一致性。日级适配保留跨日顺序，同时明确舍弃不可观测的日内顺序。后续评价应同时考察数据语义、统计解释和集群资源行为，不能仅以是否在一台电脑上跑通作为项目完成标准。')
    sub('参考文献')
    references=[
       ('Agrawal R, Srikant R. Mining Sequential Patterns. ICDE, 1995: 3–14.','https://doi.org/10.1109/ICDE.1995.380415'),
       ('Pei J, et al. PrefixSpan: Mining Sequential Patterns Efficiently by Prefix-Projected Pattern Growth. ICDE, 2001: 215–224.','https://doi.org/10.1109/ICDE.2001.914830'),
       ('Zaki M J. SPADE: An Efficient Algorithm for Mining Frequent Sequences. Machine Learning, 2001, 42: 31–60.','https://doi.org/10.1023/A:1007652502315'),
       ('Zaharia M, et al. Resilient Distributed Datasets: A Fault-Tolerant Abstraction for In-Memory Cluster Computing. NSDI, 2012: 15–28.','https://www.usenix.org/conference/nsdi12/technical-sessions/presentation/zaharia'),
       ('Jenkins S, Walzer-Goldfeld S, Riondato M. SPEck: Mining Statistically-significant Sequential Patterns Efficiently with Exact Sampling. DMKD, 2022, 36: 1575–1599.','https://doi.org/10.1007/s10618-022-00848-x'),
       ('Cüppers J, Krieger P, Vreeken J. Discovering Sequential Patterns with Predictable Inter-event Delays. AAAI, 2024, 38(8): 8346–8354.','https://doi.org/10.1609/aaai.v38i8.28676'),
       ('Kraus A, van der Aa H. Comprehensive characterization of concept drifts in process mining. Information Systems, 2026, 135: 102584.','https://doi.org/10.1016/j.is.2025.102584'),
       ('Benjamini Y, Yekutieli D. The control of the false discovery rate in multiple testing under dependency. Annals of Statistics, 2001, 29(4): 1165–1188.','https://doi.org/10.1214/aos/1013699998'),
       ('Chen D. Online Retail II. UCI Machine Learning Repository, 2012. CC BY 4.0.','https://doi.org/10.24432/C5CG6D'),
       ('H&M. Personalized Fashion Recommendations, Kaggle, 2022. 本次基础交易表镜像：Microsoft hnm-search-data；遵循原始非商业与学术研究条款。','https://huggingface.co/datasets/microsoft/hnm-search-data'),
       ('Apache Spark 4.0.1. Frequent Pattern Mining / PrefixSpan，2026-10-31 访问。','https://spark.apache.org/docs/4.0.1/ml-frequent-pattern-mining.html'),
       ('Apache Spark 4.0.1. Standalone、Running on YARN 与 SQL Performance Tuning 文档，2026-10-31 访问。','https://spark.apache.org/docs/4.0.1/running-on-yarn.html')]
    styles['ref'].fontSize=8.1;styles['ref'].leading=11.8;styles['ref'].spaceAfter=5
    for i,(title,url) in enumerate(references,1):
        p(f'[{i}] {html.escape(title)} <link href="{html.escape(url,quote=True)}" color="#147D92">→</link>','ref')
    output=ROOT/'结果'/'框架基准报告.pdf'
    def decorate(c,doc):
        c.saveState();c.setStrokeColor(colors.HexColor('#CBD6DD'));c.line(50,803,545,803)
        c.setFont('Chinese',8);c.setFillColor(colors.HexColor('#526472'));c.drawString(50,815,'大数据处理课程项目　|　事件序列处理框架')
        c.drawRightString(545,28,f'{doc.page} / 8');c.restoreState()
    doc=SimpleDocTemplate(str(output),pagesize=(595.28,841.89),leftMargin=50,rightMargin=50,topMargin=53,bottomMargin=48,
                         title='事件序列中的频繁模式与行为变化分析',author='大数据处理课程项目',pageCompression=1)
    doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
    reader=PdfReader(output)
    save_json('框架报告生成.json',{'pages':len(reader.pages),'bytes':output.stat().st_size,'sha256':sha256(output),'output':str(output)})
    (ROOT/'结果'/'框架报告文本.txt').write_text('\n\n'.join(x.extract_text() for x in reader.pages),encoding='utf-8')
    print(f'pages={len(reader.pages)}, bytes={output.stat().st_size}')
    assert len(reader.pages)==8,'Report page count must be eight'

if __name__=='__main__':main()
