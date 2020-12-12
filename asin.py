#!/usr/bin/env python3

import random
import string
import urllib.parse
import urllib.request
from urllib.error import HTTPError

from bs4 import BeautifulSoup


def get_asin(title):
    try:
        asin = get_asin_from_amazon(title)
        return asin if asin is not None else random_asin()
    except HTTPError:
        return random_asin()


def get_asin_from_amazon(title):
    title = urllib.parse.quote(title)
    url = 'https://www.amazon.com/s?k={}&i=digital-text'.format(title)
    req = urllib.request.Request(url)
    req.add_header(
        'User-Agent',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:78.0) '
        'Gecko/20100101 Firefox/78.0')
    with urllib.request.urlopen(req) as f:
        soup = BeautifulSoup(f.read().decode('utf-8'), features="lxml")
        tag = soup.div.find(filter)
        if tag is None:
            return None
        return tag['data-asin'] if tag.has_attr('data-asin') else None


def random_asin():
    asin = 'B'
    asin += ''.join(random.choices(string.ascii_uppercase +
                                   string.digits, k=9))
    return asin


def filter(tag):
    if tag is None:
        return False
    if tag.has_attr('class') and 's-asin' in tag['class'] and \
       'AdHolder' not in tag['class']:
        return True
    return False
