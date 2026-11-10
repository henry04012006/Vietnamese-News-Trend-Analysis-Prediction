import hashlib
import json
from pathlib import Path

import pytest

import crawl_tuoitre as crawler


@pytest.fixture
def config():
    return json.loads(Path('config/tuoitre.json').read_text(encoding='utf-8'))


def test_article_extracts_publication_body_and_stable_id(config):
    # Related articles and update dates must not contaminate the article.
    html = '''<h1 class="detail-title">Tin tiếng Việt</h1>
    <meta property="article:section" content="Thời sự">
    <time itemprop="datePublished" datetime="2026-01-02T09:00:30+07:00"></time>
    <meta property="article:modified_time" content="2026-02-03T12:00:00+07:00">
    <h2 class="detail-sapo">Mô tả.</h2>
    <div class="detail-content"><p>Đoạn <b>một</b>.</p>
    <div type="RelatedNewsBox"><p>Tin khác</p></div>
    <figure><figcaption><p>Chú thích ảnh</p></figcaption></figure>
    <p>Đoạn hai.</p><script>advertisement()</script></div>'''
    url = 'https://tuoitre.vn/tin-202601020900.htm?utm_source=x&edition=2#comments'

    row = crawler.parse_article(html, url, '2026-11-07T09:00:00+07:00', config)

    clean = 'https://tuoitre.vn/tin-202601020900.htm?edition=2'
    assert row == {
        'title': 'Tin tiếng Việt', 'description': 'Mô tả.', 'category': 'Thời sự',
        'content': 'Đoạn một.\n\nĐoạn hai.', 'source': 'Tuổi Trẻ', 'url': clean,
        'published_at': '2026-01-02T09:00:30+07:00',
        'collected_at': '2026-11-07T09:00:00+07:00',
        'article_id': hashlib.sha256(('Tuổi Trẻ|' + clean).encode()).hexdigest(),
    }


@pytest.mark.parametrize('date_value', ['', '2026-01-02T09:00:00'])
def test_article_rejects_missing_or_naive_publication(config, date_value):
    # Never substitute collection/update time for publication time.
    html = f'''<h1 class="detail-title">Tin</h1>
    <time itemprop="datePublished" datetime="{date_value}"></time>
    <div class="detail-content"><p>Nội dung.</p></div>'''
    with pytest.raises(ValueError, match='publication'):
        crawler.parse_article(html, 'https://tuoitre.vn/tin.htm', '2026-11-07T09:00:00+07:00', config)


def test_discovery_ignores_image_locations(config):
    # Sitemap image loc nodes are not articles.
    xml = '''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
    xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
    <url><loc>https://tuoitre.vn/bai-123.htm</loc>
    <image:image><image:loc>https://cdn2.tuoitre.vn/image.jpg</image:loc></image:image>
    </url></urlset>'''
    assert crawler.sitemap_locations(xml, config) == ['https://tuoitre.vn/bai-123.htm']


def test_csv_resume_skips_existing_url_and_id(config, tmp_path):
    # Restarting must not append a second copy of an already collected article.
    store = crawler.ArticleStore(tmp_path, 'sample', config)
    row = dict.fromkeys(config['output']['fields'], '')
    row.update(article_id='abc', url='https://tuoitre.vn/tin-1.htm', content='Đoạn một.\n\nĐoạn hai.')
    assert store.add(row) is True
    resumed = crawler.ArticleStore(tmp_path, 'sample', config)
    assert resumed.add(row) is False
    assert len(resumed.rows) == 1
    assert resumed.rows[0]['content'] == row['content']


def test_http_stops_on_rate_limit_without_retry(config, monkeypatch):
    # A 429 must not trigger repeated requests or evasive fallback.
    import requests
    from unittest.mock import Mock

    response = requests.Response()
    response.status_code = 429
    response.url = 'https://tuoitre.vn/bai-1.htm'
    session = Mock()
    session.get.return_value = response
    client = crawler.Client(config)
    client.session = session
    client.robots.parse(['User-agent: *', 'Allow: /'])
    monkeypatch.setattr(crawler.time, 'sleep', lambda _: None)

    with pytest.raises(crawler.StopCrawl, match='429'):
        client.get(response.url)
    assert session.get.call_count == 1


def test_backfill_writes_publication_month_and_resumes_without_fetch(config, tmp_path, monkeypatch):
    # A sitemap boundary must not put a January article into a February CSV.
    from types import SimpleNamespace

    url = 'https://tuoitre.vn/bai-202601312300.htm'
    html = b'''<h1 class="detail-title">Title</h1>
    <nav class="detail-cate"><a href="/thoi-su.htm">News</a></nav>
    <time itemprop="datePublished" datetime="2026-01-31T23:30:00+07:00"></time>
    <div class="detail-content"><p>Article body.</p></div>'''
    calls = []
    monkeypatch.setattr(crawler.Client, 'bootstrap', lambda self: None)
    monkeypatch.setattr(crawler, 'discover', lambda *args: [{'url': url, 'group': 'backfill', 'sitemap': 'February'}])

    def fetch(self, url):
        calls.append(url)
        return SimpleNamespace(content=html, url=url)

    monkeypatch.setattr(crawler.Client, 'get', fetch)
    first = crawler.run('backfill', config, tmp_path)
    second = crawler.run('backfill', config, tmp_path)

    assert first['saved'] == 1 and second['saved'] == 0
    assert calls == [url]
    path = tmp_path / config['output']['directory'] / 'tuoitre_2026-01.csv'
    assert path.exists()
    assert second['total_valid'] == 1


def test_parse_failure_is_logged_and_never_saved(config, tmp_path, monkeypatch):
    # Broken HTML cannot silently become a fabricated valid row.
    from types import SimpleNamespace

    url = 'https://tuoitre.vn/bad-1.htm'
    monkeypatch.setattr(crawler.Client, 'bootstrap', lambda self: None)
    monkeypatch.setattr(crawler, 'discover', lambda *args: [{'url': url, 'group': 'recent', 'sitemap': 'test'}])
    monkeypatch.setattr(crawler.Client, 'get', lambda *args: SimpleNamespace(content=b'<html/>', url=url))

    report = crawler.run('sample', config, tmp_path)

    assert not report['automated_gate_pass']
    assert report['total_valid'] == 0
    error_path = tmp_path / config['output']['directory'] / config['output']['errors'].format(mode='sample')
    assert json.loads(error_path.read_text(encoding='utf-8'))['url'] == url


def test_sample_redirect_keeps_group_and_resume_identity(config, tmp_path, monkeypatch):
    # Renamed headlines redirect to a new slug; still count and resume that sample.
    from types import SimpleNamespace

    original = 'https://tuoitre.vn/old-slug-123.htm'
    canonical = 'https://tuoitre.vn/new-slug-123.htm'
    html = b'''<h1 class="detail-title">Title</h1>
    <nav class="detail-cate"><a href="/thoi-su.htm">News</a></nav>
    <time itemprop="datePublished" datetime="2026-11-01T08:00:00+07:00"></time>
    <div class="detail-content"><p>Content.</p></div>'''
    calls = []
    monkeypatch.setattr(crawler.Client, 'bootstrap', lambda self: None)
    monkeypatch.setattr(crawler, 'discover', lambda *args: [{'url': original, 'group': 'recent', 'sitemap': 'test'}])

    def fetch(self, url):
        calls.append(url)
        return SimpleNamespace(content=html, url=canonical)

    monkeypatch.setattr(crawler.Client, 'get', fetch)
    first = crawler.run('sample', config, tmp_path)
    second = crawler.run('sample', config, tmp_path)

    assert first['valid_by_group']['recent'] == 1
    assert second['valid_by_group']['recent'] == 1
    assert calls == [original]


def test_discovery_obeys_configured_sitemap_lookback(config):
    # Operators can exclude previous-month sitemaps when checking a limited batch.
    from datetime import date
    from types import SimpleNamespace

    config['sitemap_lookback_months'] = 0
    config['additional_sitemap_indexes'] = []
    old = 'https://tuoitre.vn/StaticSitemaps/sitemaps-2025-12-26-31.xml'
    current = 'https://tuoitre.vn/StaticSitemaps/sitemaps-2026-1-1-5.xml'
    calls = []

    class FakeClient:
        def get(self, url):
            calls.append(url)
            values = [old, current] if url == config['sitemap_index'] else ['https://tuoitre.vn/bai-123.htm']
            xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            xml += ''.join(f'<url><loc>{value}</loc></url>' for value in values) + '</urlset>'
            return SimpleNamespace(content=xml)

    crawler.discover(FakeClient(), config, 'backfill', date(2026, 1, 1), date(2026, 1, 31))

    assert calls == [config['sitemap_index'], current]
