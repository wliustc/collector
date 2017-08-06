# -*- coding: utf-8 -*-
import json,re
from scrapy.exceptions import DropItem
from Spider.items import *
from scrapy import Request
from scrapy.pipelines.images import ImagesPipeline
from datetime import datetime
from pymongo import MongoClient

DATE=datetime.now().strftime('%Y-%m-%d')
GALANCE=f'galance{datetime.now().strftime("%Y%m%d")}'
ERROR=f'{DATE}'

class SqlPipeline:

  def __init__(self, path):
    self.path = path

  @classmethod
  def from_settings(cls, settings):  #获取settings中的设置
    path=settings.get('DATAPATH', './')
    return cls(path)

  def open_spider(self,spider):
    self._={TweetItem:'tweet',AttitudeItem:'attitude',RelayItem:'relay',CommentItem:'comment',}
    self.f=open('{}{}.sql'.format(self.path,spider.name),'w',encoding='utf-8')

  def process_item(self, item, spider):
    table=self._.get(item.__class__,'init')
    fields=','.join(item.keys())
    values="','".join((str(_) for _ in item.values()))  #join只适用于都是字符串的情形
    sql="insert into {}({}) values('{}');\n".format(table,fields,values)
    #sql="insert into {0}({1}) values('{2}');\n".format(table,fields,values)
    #sql="insert into {table}({fields}) values('{values}');\n".format(table=table,fields=fields,values=values)
    self.f.write(sql)
    return item

  def close_spider(self, spider):
    self.f.write('commit;')
    self.f.close()

class JsonPipeline:

  def __init__(self, path):
    self.path = path

  @classmethod
  def from_settings(cls, settings):
    path = settings.get('DATAPATH', './')
    return cls(path)
  
  def open_spider(self,spider):
    self.f = open(f'{self.path}{spider.name}{DATE}.json', 'w', encoding='utf-8')

  def process_item(self, item, spider):
    #self.f.write('{}\n'.format(json.dumps(dict(item),ensure_ascii=False)))
    #self.f.write('{}\n'.format(dict(item)))
    self.f.write(f'{json.dumps(dict(item))}\n')  #使用时只需要json.loads即可,你不需要转码
    return item

class ImagePipeline(ImagesPipeline):

  def get_media_requests(self,item,info):
      # 默认使用的image_urls字段且必须是可迭代对象
      # when they have finished downloading, the results will be sent to the item_completed() method
      if 'image_url' in item:
          yield Request(item['image_url'],meta={'_id':item['_id']})   # Request行为也遵循custom_settings

  def file_path(self, request, response=None, info=None):
      image_guid = request.meta['_id']
      return f'{image_guid}.jpg'

  def thumb_path(self, request, thumb_id, response=None, info=None):
    '''
    thumb_guid = hashlib.sha1(url).hexdigest()  # change to request.url after deprecation
    return 'thumbs/%s/%s.jpg' % (thumb_id, thumb_guid)
    '''
    image_guid = thumb_id + response.url.split('/')[-1]
    return 'thumbs/{}/{}'.format(thumb_id, image_guid)

  def item_completed(self,results,item,info):    #每完成一个item，调用一次
      # results => [(True, {'url': 'https://images-na.ssl-images-amazon.com/images/I/41wSHmssJUL._AC_US218_.jpg', 'path': 'B071R3RLRN.jpg', 'checksum': '6ddc65d83642b862cd953212ad498500'})]
      if results and results[0][0]:
          item['image_path']=results[0][1]['path']
      return item

class MongoPipeline:

    def open_spider(self, spider):
        self.client = MongoClient('localhost:27017')
        self.log=self.client['log']
        self.amazon = self.client['amazon']

    def process_item(self, item, spider):
        if 'error' in item:
            self.log[ERROR].insert(dict(item))
            raise DropItem("Error page found:")  #注意要阻断item向其他管道传播
        elif 'number' in item:
            item['date']=DATE  
            self.log['count'].insert(dict(item))
            raise DropItem("page number inserted!") 
        else:
            if item['sales']=='':
                item['sales']=0
            else:
                item['sales']=int(item['sales'])

            merchant=re.findall(r'(?<=[sS]old [bB]y ).+(?=\s[aA]nd)|(?<=[sS]old [bB]y )[aA]mazon|(?<=[sS]old [bB]y ).+',item['soldBy'])
            item['soldBy']=merchant[0] if merchant else 'Unknown'
            item['rank']=float(item['rank']) if item['rank'] else float('inf')
            result=re.search(r'\$(\d+\.\d+)',item['price'].replace(',',''))
            item['price']=float(result.group(1)) if result else 0.0
            result=re.search(r'(\d+\.\d+ |\d+)', item['avgStar'])
            item['avgStar']=float(result.group(1)) if result else 0.0
            item['totalReviews']=int(item['totalReviews'].replace(',',''))
            item['brand']= re.sub(r'^by ','',item['brand'],count=1)        
            item['date']=DATE
            self.amazon[GALANCE].insert(dict(item))
            #self.amazon[GALANCE].update({'_id': item['_id']}, {'$setOnInsert': dict(item)}, upsert=True)  #没有则插入,有则不操作
            return item
            
    def close_spider(self, spider):
        self.client.close()