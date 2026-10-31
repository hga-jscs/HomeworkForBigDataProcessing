"""Dataset-specific contracts; all row processing remains in Spark SQL."""
from pyspark.sql import functions as F, types as T

RETAIL_COLUMNS = ['invoice','stock','description','quantity','time','price','customer','country','sheet','row_number']
ARTICLE_COLUMNS = ['article_id','product_code','prod_name','product_type_no','product_type_name',
    'product_group_name','graphical_appearance_no','graphical_appearance_name','colour_group_code',
    'colour_group_name','perceived_colour_value_id','perceived_colour_value_name',
    'perceived_colour_master_id','perceived_colour_master_name','department_no','department_name',
    'index_code','index_name','index_group_no','index_group_name','section_no','section_name',
    'garment_group_no','garment_group_name','detail_desc']

def csv_strings(spark, uri, columns, multiline=False):
    schema = T.StructType([T.StructField(c, T.StringType(), True) for c in columns])
    return (spark.read.schema(schema).option('header', True).option('mode','FAILFAST')
            .option('enforceSchema', False).option('escape','"').option('multiLine', multiline).csv(uri))

def retail(spark, config):
    raw = csv_strings(spark, config['transactions'], RETAIL_COLUMNS)
    typed = raw.select('invoice', F.upper(F.trim('stock')).alias('product'), 'description',
        F.expr('try_cast(quantity as double)').alias('quantity'),
        F.expr('try_cast(time as timestamp)').alias('event_time'),
        F.expr('try_cast(price as double)').alias('price'),
        F.expr('cast(try_cast(customer as bigint) as string)').alias('customer'), 'country')
    reason = (F.when(F.col('customer').isNull() | F.col('event_time').isNull(), 'invalid_customer_or_time')
        .when(F.col('invoice').isNull() | F.upper('invoice').startswith('C') |
              F.col('quantity').isNull() | F.isnan('quantity') | (F.col('quantity')<=0), 'cancelled_or_invalid_quantity')
        .when(F.col('price').isNull() | F.isnan('price') | (F.col('price')<=0), 'invalid_price')
        .when(~F.col('product').rlike(r'^[0-9]{5}[A-Z]{0,2}$') | F.col('product').isNull(), 'invalid_product')
        .otherwise('accepted'))
    judged = typed.withColumn('quality', reason)
    # Exact baseline contract: full business-field deduplication, not invoice-only.
    accepted = judged.filter("quality = 'accepted'").drop('quality').dropDuplicates()
    clean = accepted.select('customer','event_time','product', F.col('product').alias('item'),
        'quantity','price', F.lit(None).cast('string').alias('channel'))
    return judged, clean, {'adapter':'online_retail', 'time_precision':'minute',
        'deduplication':'full business fields; compatible with the retained baseline'}

def fashion(spark, config):
    if config.get('granularity') != 'day':
        raise ValueError('H&M only records dates: granularity must be day')
    source_format = config.get('input_format', 'csv')
    columns = ['t_dat','customer_id','article_id','price','sales_channel_id']
    raw = (csv_strings(spark, config['transactions'], columns) if source_format == 'csv'
           else spark.read.parquet(config['transactions']))
    articles = (csv_strings(spark, config['articles'], ARTICLE_COLUMNS, multiline=True)
                if source_format == 'csv' else spark.read.parquet(config['articles']))
    # Parquet mirrors may expose int64 IDs; restore the documented ten-digit key.
    def article_key():
        text = F.col('article_id').cast('string')
        return F.when(text.rlike(r'^[0-9]{1,10}$'), F.lpad(text,10,'0'))
    dimension = articles.select(article_key().alias('product'),
        F.col('product_type_no').cast('string').alias('product_type'),
        F.col('product_type_name').alias('product_type_name'))
    if dimension.filter('product is null or product_type is null').limit(1).count():
        raise ValueError('Article dimension has invalid keys/categories')
    if dimension.groupBy('product').count().filter('count != 1').limit(1).count():
        raise ValueError('Article dimension key is not unique; join would multiply transactions')
    typed = raw.select(F.col('customer_id').cast('string').alias('customer'),
        F.expr('try_cast(t_dat as date)').cast('timestamp').alias('event_time'), article_key().alias('product'),
        F.expr('try_cast(price as double)').alias('price'),
        F.col('sales_channel_id').cast('string').alias('channel'))
    # Broadcast only the small article dimension, not transactions or customer sequences.
    joined = typed.join(F.broadcast(dimension), 'product', 'left')
    reason = (F.when(F.col('customer').isNull() | ~F.col('customer').rlike(r'^[0-9a-f]{64}$') |
                          F.col('event_time').isNull(), 'invalid_customer_or_date')
        .when(F.col('product').isNull(), 'invalid_article_id')
        .when(F.col('price').isNull() | F.isnan('price') | (F.col('price')<0), 'invalid_price')
        .when(~F.col('channel').isin('1','2') | F.col('channel').isNull(), 'invalid_channel')
        .when(F.col('product_type').isNull(), 'unmatched_article')
        .otherwise('accepted'))
    judged = joined.withColumn('quality', reason)
    level = config.get('item_level','product_type')
    if level not in ('product','product_type'):
        raise ValueError('item_level must be product or product_type')
    item = F.col('product') if level == 'product' else F.concat(F.lit('type:'),F.col('product_type'))
    clean = judged.filter("quality = 'accepted'").select('customer','event_time','product',item.alias('item'),
        F.lit(1.0).alias('quantity'),'price','channel')
    return judged, clean, {'adapter':'hm', 'time_precision':'day',
        'deduplication':'none: identical rows can be multiple purchased units',
        'item_level':level, 'article_rows':dimension.count(),
        'product_types':dimension.select('product_type').distinct().count()}

def adapt(spark, config):
    name = config['adapter']
    if name == 'online_retail': return retail(spark, config)
    if name == 'hm': return fashion(spark, config)
    raise ValueError(f'Unknown adapter: {name}')
