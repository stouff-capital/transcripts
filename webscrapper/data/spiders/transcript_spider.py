import scrapy
import json
import re
from furl import furl
from data.items import TranscriptItem
from scrapy.http import Request
from dateutil.parser import parse as parse_date
# from scrapy.exceptions import CloseSpider

from dotenv import load_dotenv
from pathlib import Path  # python3 only
env_path = Path('..') / '.env'
load_dotenv(dotenv_path=env_path)
import os

import requests
from requests.auth import HTTPBasicAuth
auth=(os.getenv("ELASTICSEARCH_USER"), os.getenv("ELASTICSEARCH_PASSWORD"))

from datetime import date, timedelta
yesterday = date.today() - timedelta(1)

class TranscriptSpider(scrapy.Spider):
    name = "transcripts"
    rotate_user_agent = True # Necessary to avoid getting blocked by domain


    # Allow the companies for scraping to be specified by ticker symbol
    def __init__(self, symbol=None, symbols=None, *args, **kwargs):
        '''
        Accepts either a single company ticker symbol, or a comma-separated list of company ticker symbols for scraping.
        '''
        super(TranscriptSpider, self).__init__(*args, **kwargs)
        if symbols:
            symbols = symbols.split(',')
            self.start_urls = ['https://seekingalpha.com/symbol/{}/earnings/more_transcripts?page=1'.format(s) for s in symbols]
        elif symbol:
            self.symbol = symbol
            self.start_urls = ['https://seekingalpha.com/symbol/{}/earnings/more_transcripts?page=1'.format(symbol)]

    def parse(self, response):
        data = json.loads(response.body.decode('utf8'))
        selector = scrapy.Selector(text=data['html'], type="html")

        if data['count'] > 0:
            # This is necessary when start_urls contains a list of companies
            company = re.search(r'(?<=symbol\/)(.*)(?=\/earnings)', response.url).group(0)

            # Select parent node for only the child nodes that contain an earnings call transcript
            links = [link for link in selector.css('.symbol_article') if link.xpath('a[contains(text(), "Earnings Call Transcript")]')]

            k = 0
            for link in links:
                item = TranscriptItem()

                # Scrape basic info from link
                item['title'] = link.xpath('a[contains(text(), "Earnings Call Transcript")]/text()').extract_first()
                item['url'] = response.urljoin(link.xpath('a[contains(text(), "Earnings Call Transcript")]/@href').extract_first()+'?part=single')

                date_txt = link.css('.date_on_by::text').extract_first()
                if "Yesterday" in date_txt:
                    date_txt = yesterday.strftime('%a, %b. %d')
                item['date'] = parse_date( date_txt )

                item['company'] = company

                #check existing content in db
                query = {
                    "query": {
                        "match_phrase" : {
                            "url" : item['url']
                        }
                    }
                }
                res = requests.get(f'{os.getenv("ELASTICSEARCH_URL")}/transcripts/sa/_search', json=query, auth=auth)
                dic_res = json.loads(res.content)

                if dic_res['hits']['total'] == 0:
                    # Request transcript url for further scraping, passing what we've collected so far as meta information
                    request = scrapy.Request(item['url'], callback=self.parse_transcript)
                    #request = scrapy.Request(item['url'], callback=self.parse_transcript, meta={'proxy': 'https://93.91.154.195:8080'})
                    request.meta['item'] = item
                    yield request
                else:
                    self.logger.info('already in db based on url')

            f = furl(response.url)
            f.args['page'] = str(int(f.args['page'])+1)
            next_page = str(f.url)
            yield scrapy.Request(next_page)


    def parse_transcript(self, response):
        item = response.meta['item']

        transcript = [''.join(x.xpath('./descendant::text()').extract()) for x in response.xpath('//div[@id="a-body"]/p')]

        try:
            # Split transcript into list of executives on the call, list of analysts on the call, and the actual transcript
            # Different transcripts have iterations of the following terms, so can't use .index("Executives")
            # ie. Some transcripts have "Executives" while others have "Executives: "
            executives_start = [i for i, j in enumerate(transcript) if "Executive" in j][0]
            analysts_start = [i for i, j in enumerate(transcript) if "Analyst" in j][0]
            operator_start = [i for i, j in enumerate(transcript) if "Operator" in j][0]
            copyright_start = transcript.index("Copyright policy:")

            item['executives'] = transcript[executives_start+1:analysts_start]
            item['analysts'] = transcript[analysts_start+1:operator_start]
            item['body'] = transcript[operator_start+1:copyright_start]
        except:
            # If the formatting is really strange, just store everything in body and flag the anomoly in executives/analyst fields
            item['executives'] = 'Parsing error'
            item['analysts'] = 'Parsing error'
            item['body'] = transcript

        #change data model for db
        db_doc = {
            'company': item['company'],
            'title': item['title'],
            'url': item['url'],
            'date': item['date'].strftime('%Y-%m-%d'),
            'text': " ".join(item['body'])
        }
        res = requests.post(f'{os.getenv("ELASTICSEARCH_URL")}/transcripts/sa/', auth=auth, json=db_doc)

        yield item
