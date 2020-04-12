from concurrent.futures import ProcessPoolExecutor
import requests

def get_page(url):
    res = requests.get(url).text
    return {'url': url, 'res': res}


def parse_page(res):
    print('0',  res)
    res = res.result()
    print('1', res)
    with open('a.txt', 'a', encoding='utf-8') as f:
        f.write('%s-%s\n' % (res['url'], len(res['res'])))

if __name__ == '__main__':
    urls = [
        'http://www.openstack.org',
        'https://www.python.org',
        'http://www.sina.com.cn/'
    ]
    t = ProcessPoolExecutor()
    for url in urls:
        t.submit(get_page, url).add_done_callback(parse_page)