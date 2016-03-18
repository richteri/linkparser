from unittest import TestCase
from linkparser import LinkParser, RSS_KEY, ATOM_KEY, categorize_url
import json
import requests

SAMPLE_RSS = 'http://feeds.huffingtonpost.com/huffingtonpost/raw_feed'
SAMPLE_ATOM = 'http://feeds.feedburner.com/PTCC'


def build_session():
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1)
    session.mount('http://', adapter)
    return session


def read_file(input_file):
    f = open(input_file, 'r')
    contents = f.read()
    f.close()
    return contents


class linkparserTest(TestCase):

    def test_empty_href(self):
        p = LinkParser()
        p.feed('<a href>test</a><link href><a href="' + SAMPLE_RSS + '"></a>')
        self.assertListEqual([SAMPLE_RSS], p.data[RSS_KEY])

    def test_categorize_rss(self):
        session = build_session()
        category, url = categorize_url(session, SAMPLE_RSS, None)
        self.assertEqual(category, RSS_KEY)
        self.assertEqual(url, SAMPLE_RSS)
        session.close()

    def test_categorize_atom(self):
        session = build_session()
        category, url = categorize_url(session, SAMPLE_ATOM, None)
        self.assertEqual(category, ATOM_KEY)
        self.assertEqual(url, SAMPLE_ATOM)
        session.close()

    def test_categorize_non_feed(self):
        session = build_session()
        result = categorize_url(session, 'http://index.hu', None)
        self.assertIsNone(result)

    def test_categorize_invalid_url(self):
        session = build_session()
        result = categorize_url(session, 'http://index.hux', None)
        self.assertIsNone(result)

    def test_categorize_relative_urls_canonical(self):
        p = LinkParser()
        p.feed('''
            <link rel="canonical" href="http://feeds.huffingtonpost.com" />
            <link rel="alternate" type="application/rss+xml" title="The Full Feed" href="huffingtonpost/raw_feed" />
        ''')
        self.assertEqual(p.find_base_url(), 'http://feeds.huffingtonpost.com')
        self.assertListEqual([SAMPLE_RSS], p.data[RSS_KEY])

    def test_categorize_relative_urls_provided(self):
        p = LinkParser()
        p.feed(base_url='http://feeds.huffingtonpost.com', html='''
            <link rel="alternate" type="application/rss+xml" title="The Full Feed" href="huffingtonpost/raw_feed" />
        ''')
        self.assertEqual(p.find_base_url(), 'http://feeds.huffingtonpost.com')
        self.assertListEqual([SAMPLE_RSS], p.data[RSS_KEY])

    def test_multiple_runs(self):
        p = LinkParser()
        p.feed('''
            <link rel="canonical" href="http://feeds.huffingtonpost.com" />
            <link rel="alternate" type="application/rss+xml" title="The Full Feed" href="huffingtonpost/raw_feed" />
        ''')
        p.feed('<link rel="alternate" type="application/atom+xml" href="http://feeds.feedburner.com/PTCC" />')
        self.assertListEqual([SAMPLE_RSS], p.data[RSS_KEY])
        self.assertListEqual([SAMPLE_ATOM], p.data[ATOM_KEY])

    def xtest_500plus_links(self):
        p = LinkParser()

        input_html = read_file('01_input.html')
        p.feed(input_html, timeout=60)
        output_json = read_file('01_output.json')
        data = json.loads(output_json)

        self.assertSetEqual(set(data[RSS_KEY]), set(p.data[RSS_KEY]))
        self.assertSetEqual(set(data[ATOM_KEY]), set(p.data[ATOM_KEY]))

