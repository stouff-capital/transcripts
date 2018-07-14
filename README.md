# Transcripts
Scraper based on https://github.com/jeremyjordan/stock-price-forecasting

## setup
set `.env` with ELASTICSEARCH_URL, ELASTICSEARCH_USER and ELASTICSEARCH_PASSWORD

## Data
##### Stock price
Price data is downloaded from Google Finance using the Pandas DataReader. See notebook to run the command to download all necessary data.

##### Quarterly earnings call transcripts
Transcripts are scraped from [Seeking Alpha](https://seekingalpha.com/) using the Python library [Scrapy](https://docs.scrapy.org/en/latest/).

To fetch a company transcript, complete the following steps.

```
cd webscrapper/
scrapy crawl transcripts -a symbol=<SYMBOL>
```

This will download all of the posted earnings call transcripts for company `<SYMBOL>` and store it as a JSON lines file in `data/company_transcripts/<SYMBOL>.json`.

Note: The transcripts provided by Seeking Alpha are protected by copyright and can not be used for commercial interests. However, given the educational nature of this project as part of the Udacity Machine Learning Nanodegree, use of this information is permitted under the Copyright Fair Use principle. This said, data is NOT provided in this repo in order to abide by Seeking Alpha's copyright requests.
