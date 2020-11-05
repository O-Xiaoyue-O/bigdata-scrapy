# 練習5_4：爬取指定網站的Google搜尋列表
import time
import random
import json
import html
import urllib
import configparser
from datetime import datetime

import loguru
import sqlalchemy
import sqlalchemy.ext.automap
import sqlalchemy.orm
import sqlalchemy.schema

import re
import ntpath
import requests
from lxml import etree

__articletable__ = 'crawler_article'
__articlemetatable__ = 'crawler_articlemeta'
__fieldstable__ = 'crawler_fields'
__listtable__ = 'crawler_list'
__mediatable__ = 'crawler_media'

__wp_posts_table__ = 'wp_posts'
__wp_postmeta_table__ = 'wp_postmeta'
__wp_term_relationships_table__ = 'wp_term_relationships'
__wp_term_taxonomy_table__ = 'wp_term_taxonomy'
__wp_termmeta_table__ = 'wp_termmeta'
__wp_terms_table__ = 'wp_terms'

__post_type__ = 'scrapy'
__taxonomy_name__ = 'scrapies'

source_id = 1
topics = None
fields = None

#請求網頁
def requestHtml(url):
  s = requests.Session()
  r = s.get(url, headers=headers_Get)
  r.encoding = 'utf-8'
  return etree.HTML(r.text)

#組合列表中的標題
def composeItems(pageLinks, links, titles):
  contain = 'article'
  for idx, link in enumerate(links):
    if link.find(contain) >= 0 :
      pageLinks.append({"title":titles[idx], "link":link})

  return pageLinks

#取得最後一頁
def findLastPage(searchPages):
  lastPage = 1
  for searchPage in searchPages:
    try:
      lastPage = int(searchPage)
      print(lastPage)
    except ValueError:
      print(searchPage + " is not integer")
  return lastPage

#清空字串內全部的 html tag，只留下內文
TAG_RE = re.compile(r'<[^>]+>')
def remove_tags(text):
    return TAG_RE.sub('', text)

#解析檔案路徑及檔名
def path_leaf(path):
    head, tail = ntpath.split(path)
    return tail #or ntpath.basename(head)

#以分包的方法下載檔案
def download_file(url, filename):
    # NOTE the stream=True parameter below
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    # If you have chunk encoded response uncomment if
                    # and set chunk_size parameter to None.
                    #if chunk: 
                    f.write(chunk)

        files.download(filename)
        return filename
    except:
        print("Error")
        return 0

def fetch_item_link(pageLinks, currentPage):
    global lastPage
    startItem = (currentPage-1)*10
    fullUrl = baseUrl + queryString + startParam + str(startItem) + suffix
    dom = requestHtml(fullUrl)
    links = dom.xpath('//div[@class="yuRUbf"]/a/@href')
    titles = dom.xpath('//div[@class="yuRUbf"]//h3/span/text()')
    #將 etree type 轉成字串
    links = [str(link) for link in links]
    titles = [str(title) for title in titles]
    #取得最後一頁的數值
    searchPages = dom.xpath('//td/a/text()')
    lastPage = findLastPage(searchPages)

    return composeItems(pageLinks, links, titles)

def crawl_google_list():
    global lastPage
    currentPage = 1
    #解析回傳的列表標題及連結
    pageLinks = []
    pageLinks = fetch_item_link(pageLinks, currentPage)

    #等待數秒(1~5秒間)
    time.sleep(random.randint(3000, 8000)/1000)
    #逐頁爬取文章連結及標題
    while currentPage <= lastPage :
        currentPage = currentPage + 1
        pageLinks = fetch_item_link(pageLinks, currentPage)
        time.sleep(random.randint(1000, 5000)/1000)

    #去除重複的內容
    #print(len(pageLinks))
    pageLinks = [dict(t) for t in {tuple(d.items()) for d in pageLinks}]
    #print(len(pageLinks))

    #排序連結
    #print(pageLinks)
    sortedPageLinks = sorted(pageLinks, key=lambda k: k['link']) 
    #print(sortedPageLinks)
    return sortedPageLinks

def parse_article_element(dom, label, element_xpath, keepSpace):
    try:
        element = dom.xpath(element_xpath)[0]
        #清除空白字元
        if keepSpace is False:
            element = element.replace(' ', '')
        return element
    except:
        print('找不到：'+label)
        return ''
     
def crawl_article(pageLinks):
    #讀取內容頁
    articles = []
    for pageLink in pageLinks:
        try:
            print('讀取 >>> ' + pageLink['link'])
            dom = requestHtml(pageLink['link'])
        except:
            print('頁面錯誤。')

        #標題
        articleTitle = pageLink['title']
        articleTitle = parse_article_element(dom, '標題', '//div[@class="article__head"]//h1/text()', True)

        #作者
        #TOFIX 還有另一個 xpath '//div[@class="author--item"]/a/text()'，要想辦法將2者合一
        author = parse_article_element(dom, '作者', '//div[@class="author--item"]/span/text()', False)
       
        #發文日期
        postDate = parse_article_element(dom, '發文日期', '//time[@class="mt5"]/text()', False)
  
        #前言
        preface =  parse_article_element(dom, '前言', '//div[@class="preface"]/p/text()', True)
  
        #內文
        content =  parse_article_element(dom, '內文', '//div[contains(@class, "article__content")]', True)
        if content != '':
            content = etree.tostring(content)
            content = str(content)
            content = remove_tags(content)
            content = content.replace('廣告', '')
            #處理 HTML Entity Code 問題
            content = html.unescape(content)

        #關鍵字
        keywords = parse_article_element(dom, '關鍵字', '//meta[@name="keywords"]/@content', True)
  
        #相關圖檔
        images = []
        try:
            urls = dom.xpath('//span[contains(@class, "imgzoom")]/@data-zoom')
            for url in urls:
                filename = 'images/' + path_leaf(url)
                images.append({'url':url, 'filename': filename})
                #TOFIX
                #download_file(url, filename)
            #print(images)
        except:
            print('沒有附圖')

        articles.append({
            'title':str(articleTitle), 
            'link':str(pageLink['link']), 
            'keywords':str(keywords), 
            'author':str(author), 
            'preface':str(preface), 
            'content':content, 
            'images':json.dumps(images, ensure_ascii=False).encode('utf-8').decode('utf-8'), #解決 HTML Entity 編碼問題
            'post_date':str(postDate)
        })
        time.sleep(random.randint(1000, 5000)/1000)
    return articles

#發現重複的列表項目，若有不再予以新增
def find_duplicate_db_list(item):
    sqlalchemy.Table(__listtable__, metadata, autoload=True)
    Alist = automap.classes[__listtable__]

    aList = session.query(
        Alist
    ).filter(
        Alist.source_id == 1, #item['source_id'],
        Alist.article_title == item['title'],
        Alist.article_url == item['link']
    ).first()

    if aList:
        loguru.logger.info('Find duplicate source article: ' + str(aList.id))
        return aList.id
    else:
        return False

def create_db_list_item(item):
    loguru.logger.info(item['title'])

    itemDuplicateId = find_duplicate_db_list(item)
    if itemDuplicateId != False:
        return itemDuplicateId

    created = int(time.mktime(datetime.now().timetuple()))
    sqlalchemy.Table(__listtable__, metadata, autoload=True)
    Alist = automap.classes[__listtable__]

    alist = Alist()
    alist.source_id = 1 #item['source_id']
    alist.topic = keyword #item['topics']
    alist.article_title = item['title']
    alist.article_url = item['link']
    alist.created = created
    session.add(alist)
    session.flush()

    return alist.id

def create_db_article(item, listId):
    created = int(time.mktime(datetime.now().timetuple()))
    sqlalchemy.Table(__articletable__, metadata, autoload=True)
    Article = automap.classes[__articletable__]

    sourceContent = {
        'keywords': item['keywords'], 
        'author': item['author'], 
        'preface': item['preface'],  
        'content': item['content'],
        'post_date': item['post_date']
    }
    sourceContent = json.dumps(sourceContent, ensure_ascii=False).encode('utf-8').decode('utf-8')
    print(sourceContent)

    article = Article()
    article.list_id = listId
    article.source_url = item['link']
    article.title = item['title']
    article.source_content = sourceContent
    article.source_media = item['images']
    article.created = created
    session.add(article)
    return

def create_db_crawler(articles):
    for item in articles:
        listId = create_db_list_item(item)
        create_db_article(item, listId)
        try:
            session.commit()
        except Exception as e:
            loguru.logger.error('新增資料失敗')
            loguru.logger.error(e)
            session.rollback()

    #session.close()
    loguru.logger.info('完成爬蟲及寫入資料.')
    return

def get_db_articles():
    loguru.logger.info('get_db_articles')
    #TODO:從資料庫合併查詢 list ,article, articlemeta 及 article_media
    sqlalchemy.Table(__listtable__, metadata, autoload=True)
    Listtable = automap.classes[__listtable__]

    sqlalchemy.Table(__articletable__, metadata, autoload=True)
    Articletable = automap.classes[__articletable__]

    articles = session.query(
        Listtable, Articletable
    ).filter(
        Listtable.source_id == 1,
        Listtable.id == Articletable.list_id
    ).with_entities(
        Listtable.id,
        Listtable.topic,
        Listtable.article_url,
        Articletable.title,
        Articletable.source_content
    ).all()

    return articles

#組合 fields, articles ...等
def compose_articles(articles):
    loguru.logger.info('compose_articles: 商業智慧')
    return articles

def to_wordpress(posts):
    loguru.logger.info('Write article to wordpress.')
    termIds = find_or_insert_term('category', "商業智慧")
    insert_or_update_posts(termIds, posts)

def insert_or_update_posts(termIds, posts):
    loguru.logger.info('insert_or_update_posts')

    current_time = datetime.now().timetuple()

    sqlalchemy.Table(__wp_posts_table__, metadata, autoload=True)
    Poststable = automap.classes[__wp_posts_table__] 

    for post in posts:
        slug = urllib.parse.quote(post.title, encoding="utf8")
        slug = str(source_id) + '_' + path_leaf(post.article_url)  + '_' + slug[:40]
        loguru.logger.info(slug)

        if find_duplicate(slug) == False:

            content = remove_tags(post.source_content)

            poststable = Poststable()
            poststable.post_author = '1'
            poststable.post_date = current_time
            poststable.post_date_gmt = current_time
            poststable.post_content = content
            poststable.post_title = post.title
            poststable.post_excerpt = ''
            poststable.post_status = 'publish'
            poststable.comment_status = 'closed'
            poststable.ping_status = 'closed'
            poststable.post_password = ''
            poststable.post_name = slug
            poststable.to_ping = ''
            poststable.pinged = ''
            poststable.post_modified =  current_time
            poststable.post_modified_gmt = current_time
            poststable.post_content_filtered = ''
            poststable.post_parent = '0'
            poststable.guid = ''
            poststable.menu_order = 0
            poststable.post_type = __post_type__
            poststable.post_mime_type = ''
            poststable.comment_count = '0'
            session.add(poststable)
            session.flush()

            process_postmeta(poststable.ID, post)
            process_categories(poststable.ID, termIds)

    try:
        session.commit()
    except Exception as e:
        loguru.logger.error('新增資料失敗')
        loguru.logger.error(e)
        session.rollback()
    finally:
        session.close()

def process_postmeta(ID, post):
    loguru.logger.info('process_postmeta')
    sqlalchemy.Table(__wp_postmeta_table__, metadata, autoload=True)
    Postmetatable = automap.classes[__wp_postmeta_table__]

    #reference
    postmetatable = Postmetatable()
    postmetatable.post_id = ID
    postmetatable.meta_key = 'reference'
    postmetatable.meta_value = post.article_url
    session.add(postmetatable)
    session.flush()

    #isbn
    postmetatable = Postmetatable()
    postmetatable.post_id = ID
    postmetatable.meta_key = 'isbn'
    postmetatable.meta_value = '' #TOFIX:post.isbn
    session.add(postmetatable)
    session.flush()

def process_categories(ID, termIds):
    loguru.logger.info('process_categories')
    find_or_insert_relation(ID, termIds)
    #TOFIX: count to taxonomy

def find_duplicate(slug):
    sqlalchemy.Table(__wp_posts_table__, metadata, autoload=True)
    Poststable = automap.classes[__wp_posts_table__] 

    post = session.query(
        Poststable
    ).filter(
        Poststable.post_name == slug
    ).first()

    if post:
        loguru.logger.info('Find duplicate id: ' + str(post.ID))
        return True
    else:
        return False

def find_or_insert_term(taxonomy, topics):
    loguru.logger.info('find_or_insert_term')
    slug = urllib.parse.quote(topics, encoding="utf8")
    loguru.logger.info(slug)

    sqlalchemy.Table(__wp_terms_table__, metadata, autoload=True)
    Termstable = automap.classes[__wp_terms_table__]

    sqlalchemy.Table(__wp_term_taxonomy_table__, metadata, autoload=True)
    Taxonomytable = automap.classes[__wp_term_taxonomy_table__]

    #查詢是不是已有同名的分類或標籤
    term = session.query(
        Termstable, Taxonomytable
    ).filter(
        Termstable.name == topics,
        Taxonomytable.taxonomy == taxonomy,
        Termstable.term_id == Taxonomytable.term_id
    ).with_entities(
        Termstable.term_id,
        Taxonomytable.term_taxonomy_id
    ).first()

    if term:
        loguru.logger.info('Find exist term id: ' + str(term.term_taxonomy_id))
        return term.term_taxonomy_id


    termstable = Termstable()
    termstable.name = topics
    termstable.slug = slug
    termstable.term_group = '0'
    session.add(termstable)
    session.flush()

    term_id = termstable.term_id
        
    taxonomytable = Taxonomytable()
    taxonomytable.term_id = term_id
    taxonomytable.taxonomy = __taxonomy_name__
    taxonomytable.description = ''
    taxonomytable.parent = '0'
    session.add(taxonomytable)
    session.flush()

    try:
        session.commit()
    except Exception as e:
        loguru.logger.error('新增分類失敗')
        loguru.logger.error(e)
        session.rollback()
        return 0
    finally:
        return term_id

def find_or_insert_relation(ID, termIds):
    loguru.logger.info('find_or_insert_relation')
    sqlalchemy.Table(__wp_term_relationships_table__, metadata, autoload=True)
    Relationtable = automap.classes[__wp_term_relationships_table__]
    relationtable = Relationtable()
    relationtable.object_id = ID
    relationtable.term_taxonomy_id = termIds
    relationtable.term_order = '0'
    session.add(relationtable)
    session.flush()

def main():
    '''
    pageLinks = crawl_google_list()
    #print(pageLinks)
    articles = crawl_article(pageLinks)
    create_db_crawler(articles)
    '''
    #寫入 WordPress
    dbArticles = get_db_articles()
    posts = compose_articles(dbArticles)
    to_wordpress(posts)

if __name__ == '__main__':
    loguru.logger.add(
        f'./logs/{datetime.now().strftime("%Y%m%d%m%H%M%S")}.log',
        rotation='1 day',
        retention='7 days',
        level='DEBUG'
    )

    #取得資料庫連線設定
    config = configparser.ConfigParser()
    config.read("config.ini")

    host = config['mysql']['Host']
    port = int(config['mysql']['Port'])
    username = config['mysql']['User']
    password = config['mysql']['Password']
    database = config['mysql']['Database']
    chartset = config['mysql']['Charset']

    # 建立連線引擎
    connect_string = connect_string = 'mysql+mysqlconnector://{}:{}@{}:{}/{}?charset={}'.format(username, password, host, port, database, chartset)
    connect_args = {'connect_timeout': 10}
    engine = sqlalchemy.create_engine(connect_string, connect_args=connect_args, echo=False)
    
    # 取得資料庫元資料
    metadata = sqlalchemy.schema.MetaData(engine)
    # 產生自動對應參照
    automap = sqlalchemy.ext.automap.automap_base()
    automap.prepare(engine, reflect=True)
    # 準備 ORM 連線
    session = sqlalchemy.orm.Session(engine)

    #可以從瀏覽器的開發者工具取得 request 的 header 資訊
    headers_Get = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-CN;q=0.6',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    #爬取指定網站的 Google 列表搜尋
    baseUrl = 'https://www.google.com/search?q='
    #商業智慧+site:www.cw.com.tw
    keyword = "\"商業智慧\""
    site = 'site:www.cw.com.tw'
    queryString = keyword + '+' + site
    startParam = '&start='
    suffix = '&aqs=chrome..69i57j0i333.5056j0j7&sourceid=chrome&ie=UTF-8'

    lastPage = 1

    main()