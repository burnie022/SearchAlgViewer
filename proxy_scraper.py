from typing import List
import requests
from lxml.html import fromstring
import time
import proxyscrape
import random

headers = {
        'dnt': '1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'referer': 'https://www.amazon.com/',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    }


class ProxyScraper:
    def __init__(self):
        my_resource = proxyscrape.get_proxyscrape_resource(proxytype='http', timeout=5000, ssl='yes', anonymity='elite',
                                                 country='us')
        proxyscrape.add_resource_type("my_resource", my_resource)
        self.stack_code = 0
        self.proxy_stack_reserves = []
        self.proxy_stack = []
        self.collector = proxyscrape.create_collector('my_collector', "my_resource")
        self.refresh_proxies()


    def refresh_proxies(self):
        self.stack_code += 1

        # Proxies from 'https://free-proxy-list.net/'
        new_proxies = self._filter_proxies(self._fetch_primary_proxies())
        for p in new_proxies:
            self.proxy_stack.append(f"{p[0]}:{p[1]}")
        random.shuffle(self.proxy_stack)

        # Backup proxies from proxyscrape using proxyscrape API
        proxies = set(self.collector.get_proxies())
        self.proxy_stack_reserves.clear()
        for proxy in proxies:
            self.proxy_stack_reserves.append(f"{proxy.host}:{proxy.port}")
        random.shuffle(self.proxy_stack_reserves)


    def get_proxy_stack(self):
        return self.proxy_stack, self.proxy_stack_reserves, self.stack_code


    def blacklist_proxies(self, bad_proxies:List):
        for proxy in bad_proxies:
            host, port = proxy.split(":")
            self.collector.blacklist_proxy(host=host, port=port)


    # Fetch proxies from 'https://free-proxy-list.net/'
    def _fetch_primary_proxies(self):
        url = 'https://free-proxy-list.net/'
        response = requests.get(url)
        parser = fromstring(response.text)

        proxy_results = []
        for i in parser.xpath('//tbody/tr'):
            if i.xpath('.//td[7][contains(text(),"yes")]'):
                # Grabbing IP and corresponding PORT
                # proxy = ":".join([i.xpath('.//td[1]/text()')[0], i.xpath('.//td[2]/text()')[0]])
                # proxies.add(proxy)
                proxy = (i.xpath('.//td[1]/text()')[0], i.xpath('.//td[2]/text()')[0], i.xpath('.//td[3]/text()')[0],
                         i.xpath('.//td[4]/text()')[0], i.xpath('.//td[5]/text()')[0], i.xpath('.//td[6]/text()')[0],
                         i.xpath('.//td[7]/text()')[0])
                # proxies.add(proxy)
                proxy_results.append(proxy)
        return proxy_results  # proxies

    def _filter_proxies(self, proxies, code='US', anonymity='elite proxy'):
        filtered_proxies = []
        for p in proxies:
            if p[2] == code and p[4] == anonymity:
                filtered_proxies.append(p)
        return filtered_proxies



if __name__ == "__main__":
    scraper = ProxyScraper()
    time.sleep(8)
    # scraper._fetch_proxies()
    proxies = scraper.get_proxy_stack()

    print(F"PRIMARY PROXIES: {len(proxies[0])}")
    for p in proxies[0]:
        print(p)

    print(f"\nSECONDARY PROXIES: {len(proxies[1])}")
    for p in proxies[1]:
        print(p)

