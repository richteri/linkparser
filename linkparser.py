#!/usr/bin/env python
# encoding=utf8
"""An RSS and Atom link extractor and serializer"""

import sys
import getopt
import json
import re
from bs4 import BeautifulSoup
import urlparse
import requests
import logging
from joblib import Parallel, delayed

RSS_KEY = 'rss'
ATOM_KEY = 'atom'

# matches HTTP, HTTPS and protocol-relative URLs
VALID_FEED_PROTOCOL_RE = re.compile('^(http:|https:)//.+$')
VALID_FEED_MIME_RE = re.compile('^(application|text)/((rss|atom)\\+)?xml.*$')
RSS_TAG_RE = re.compile('<rss\\s+')
ATOM_TAG_RE = re.compile('<feed\\s+')


def categorize_url(session, url, timeout=10):
    """A stateless URL reader for parallel processing"""
    head_r = None
    get_r = None
    try:
        head_r = session.head(url, timeout=timeout)
        if head_r.status_code == 200 and 'content-type' in head_r.headers and VALID_FEED_MIME_RE.match(head_r.headers['content-type']):
            get_r = session.get(head_r.url, timeout=timeout, stream=True)
            for line in get_r.iter_lines():
                if line:
                    if ATOM_TAG_RE.match(line):
                        return (ATOM_KEY, get_r.url)
                    if RSS_TAG_RE.match(line):
                        return (RSS_KEY, get_r.url)
    except (requests.ConnectionError, requests.Timeout) as error:
        logging.warning('Cannot connect to URL [%s]: %s', url, error)
    finally:
        try:
            if head_r:
                head_r.close()
            if get_r:
                get_r.close()
        except:
            logging.warning('Error closing request for URL [%s]: %s', url, sys.exc_info()[0])


class LinkParser(object):
    """Class for enumerating and processing all links in a HTML file"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.data = None
        self.base_url = None
        self.soup = None
        self.urls = set()

    def find_base_url(self):
        """Returns base URL in order of priority: provided - canonical link - base tag"""
        if self.base_url:
            return self.base_url

        if not self.soup:
            return
        
        canonical = self.soup.find('link', {'rel': 'canonical'})
        if canonical:
            return canonical.get('href')

        base = self.soup.find('base')
        if base:
            return base.get('href')


    def categorize_urls(self, thread_count=100, timeout=10):
        """Check enumerated URLs parallelly"""
        
        # prepare request session
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=thread_count, pool_maxsize=thread_count)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.mount('//', adapter)

        # run parallel jobs
        results = Parallel(n_jobs=thread_count, backend='threading')(
            delayed(categorize_url, check_pickle=False)(session, url, timeout) for url in self.urls)
        
        session.close()
        return results

    def feed(self, html, base_url=None, max_thread_count=100, timeout=10):
        """Processes all URLs found in the provided HTML text"""
        
        self.soup = BeautifulSoup(html, 'html.parser')

        if base_url == None:
            base_url = self.find_base_url()
        else:
            self.base_url = base_url

        # find all hrefs and convert them into absolute URLs
        for link in self.soup.find_all(['link', 'a']):
            href = urlparse.urljoin(base_url, link.get('href'))
            if href and VALID_FEED_PROTOCOL_RE.match(href):
                self.urls.add(href)

        logging.info('Number of links found: %s' % len(self.urls))
        thread_count = min(len(self.urls), max_thread_count)

        results = self.categorize_urls(thread_count, timeout)

        # init link registry for the first run
        if not self.data:
            self.data = {RSS_KEY: [], ATOM_KEY: []}
            
        for result in results:
            if result is not None:
                category, url = result
                if url not in self.data[category]:
                    self.data[category].append(url)

    def json(self):
        """Returns JSON representation of categorized feed URLs"""
        return json.dumps(self.data)


def main(argv):
    """Provides standalone parser functionality for command line use"""
    input_file = 'index.html'
    output_file = 'output.json'
    base_url = None
    try:
        opts, args = getopt.getopt(argv, "hi:o:b:", ["input=", "output=", "base="])
    except getopt.GetoptError:
        print 'linkparser.py [-i <input_file>] [-o <output_file>] [-b <base_url>]'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'linkparser.py [-i <input_file>] [-o <output_file>] [-b <base_url>]'
            sys.exit()
        elif opt in ("-i", "--input"):
            input_file = arg
        elif opt in ("-o", "--output"):
            output_file = arg
        elif opt in ("-b", "--base"):
            base_url = arg
            
    try:
        ih = open(input_file, 'r')
        html = ih.read()
        ih.close()
        p = LinkParser()
        p.feed(html, base_url=base_url)
        oh = open(output_file, 'w')
        oh.write(p.json())
        oh.close()
    except IOError as e:
        print e
        sys.exit(2)

if __name__ == "__main__":
    main(sys.argv[1:])
