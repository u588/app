# -*- coding: utf-8 -*-
import scrapy


class ThsSpider(scrapy.Spider):
    name = 'ths'
    allowed_domains = ['10jqka.com.cn']
    start_urls = ['http://10jqka.com.cn/']

    def parse(self, response):
        pass
