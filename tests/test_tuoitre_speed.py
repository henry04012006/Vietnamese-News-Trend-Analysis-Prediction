import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import crawl_tuoitre as crawler


@pytest.fixture
def config():
    return crawler.load_config(Path('config/tuoitre.json'))


def test_cross_month_cache_skips_only_verified_outside_dates(config, tmp_path, monkeypatch):
    # A February article seen during January still needs its body fetched for February.
    config['start_date'], config['end_date'] = '2026-02-01', '2026-02-28'
    config['date_cache'] = {'enabled': True, 'journal_globs': ['history/*.jsonl'],
                            'trusted_statuses': ['saved', 'outside_range'], 'checkpoint_every': 250}
    history = tmp_path / 'history'
    history.mkdir()
    urls = [f'https://tuoitre.vn/article-{i}.htm' for i in range(3)]
    records = [{'requested_url': urls[0], 'status': 'saved', 'published_at': '2026-01-31T12:00:00+07:00'},
               {'requested_url': urls[1], 'status': 'outside_range', 'published_at': '2026-02-01T12:00:00+07:00'}]
    (history / 'january.jsonl').write_text(''.join(json.dumps(record) + '\n' for record in records))
    entries = [{'url': url, 'sitemap': 'February'} for url in urls]
    calls = []
    monkeypatch.setattr(crawler.Client, 'bootstrap', lambda self: None)
    monkeypatch.setattr(crawler, 'discover', lambda *args: entries)

    def fetch(self, url):
        calls.append(url)
        html = b'''<h1 class="detail-title">Article</h1>
        <nav class="detail-cate"><a href="/thoi-su.htm">Category</a></nav>
        <time itemprop="datePublished" datetime="2026-02-01T12:00:00+07:00"></time>
        <div class="detail-content"><p>Full article content.</p></div>'''
        return SimpleNamespace(url=url, content=html)

    monkeypatch.setattr(crawler.Client, 'get', fetch)
    report = crawler.run('backfill', config, tmp_path)

    assert calls == urls[1:]
    assert report['date_cache_skips'] == 1
    assert report['total_valid'] == 2
    assert report['result_counts'] == {'outside_range': 1, 'saved': 2}
    assert report['pending_count'] == 0


def test_date_cache_rejects_conflicts_naive_dates_and_partial_tail(config, tmp_path):
    # Uncertain metadata must never be evidence for silently dropping an article.
    config['date_cache'] = {'enabled': True, 'journal_globs': ['*.jsonl'],
                            'trusted_statuses': ['saved', 'outside_range'], 'checkpoint_every': 250}
    records = [
        {'requested_url': 'conflict', 'status': 'saved', 'published_at': '2026-01-31T12:00:00+07:00'},
        {'requested_url': 'conflict', 'status': 'outside_range', 'published_at': '2026-02-01T12:00:00+07:00'},
        {'requested_url': 'naive', 'status': 'saved', 'published_at': '2026-01-31T12:00:00'},
        {'requested_url': 'good', 'status': 'saved', 'published_at': '2026-01-31T12:00:00+07:00'},
    ]
    content = ''.join(json.dumps(record) + '\n' for record in records) + '{"unfinished'
    path = tmp_path / 'history.jsonl'
    path.write_text(content)

    cache = crawler.load_publication_cache(tmp_path, config, tmp_path / 'current.jsonl')

    assert set(cache) == {'good'}
    assert path.read_text() == content


@pytest.mark.parametrize('delay', [1, 0.5, 0.25])
def test_rate_policy_keeps_global_spacing(config, monkeypatch, delay):
    # Reducing delay must still space the request starts, accounting for elapsed download time.
    from unittest.mock import Mock
    import requests

    config['http']['delay_seconds'] = delay
    client = crawler.Client(config)
    client.robots.parse(['User-agent: *', 'Allow: /'])
    client.session = Mock()
    clock, starts = [0.0], []

    def fetch(url, **kwargs):
        starts.append(clock[0])
        clock[0] += 0.2
        response = requests.Response()
        response.status_code = 200
        response.url = url
        return response

    client.session.get.side_effect = fetch
    monkeypatch.setattr(crawler.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(crawler.time, 'sleep', lambda duration: clock.__setitem__(0, clock[0] + duration))
    client.get('https://tuoitre.vn/article-1.htm')
    client.get('https://tuoitre.vn/article-2.htm')

    assert starts == pytest.approx([0.0, delay])


def test_robots_delay_overrides_faster_request_policy(config, monkeypatch):
    # A site's longer crawl-delay must outrank the one-second local setting.
    config['http']['delay_seconds'] = 1
    client = crawler.Client(config)
    monkeypatch.setattr(client, 'get', lambda *args, **kwargs: SimpleNamespace(
        content=b'User-agent: *\nAllow: /\nCrawl-delay: 3\n'))

    client.bootstrap()

    assert client.delay == 3
