import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

import crawl_tuoitre as crawler


@pytest.fixture
def config():
    return json.loads(Path('config/tuoitre.json').read_text(encoding='utf-8'))


def test_jsonld_stock_subcategory_maps_to_business(config):
    # The source's breadcrumb gives the parent route even when visible nav says Back to topic.
    html = '''<meta property="article:section" content="Tin tức thị trường">
    <script type="application/ld+json">{"@type":"BreadcrumbList","itemListElement":[
    {"item":{"@id":"https://tuoitre.vn/chung-khoan.htm","name":"Chứng khoán"}},
    {"item":{"@id":"https://tuoitre.vn/chung-khoan/tin-tuc-thi-truong.htm","name":"Tin tức thị trường"}}
    ]}</script>'''

    label = crawler.extract_category(BeautifulSoup(html, 'html.parser'), 'https://tuoitre.vn/tin-123.htm', config)

    assert label == 'Kinh doanh'


def test_real_out_of_scope_category_is_not_mapped_to_business(config):
    # A corporate story published under Can biet must not be assigned by its content.
    html = '<nav class="detail-cate"><a href="/can-biet.htm">Cần biết</a></nav>'

    with pytest.raises(crawler.ExcludedCategory):
        crawler.extract_category(BeautifulSoup(html, 'html.parser'), 'https://tuoitre.vn/tin-123.htm', config)


def test_month_discovery_covers_video_and_boundary_without_scanning_whole_prior_month(config):
    # The last December interval may contain January 1; earlier December intervals are irrelevant.
    from datetime import date
    from types import SimpleNamespace

    index = config['sitemap_index']
    video_index = 'https://tuoitre.vn/sitemaps/video.rss'
    old = 'https://tuoitre.vn/StaticSitemaps/sitemaps-2025-12-21-25.xml'
    boundary = 'https://tuoitre.vn/StaticSitemaps/sitemaps-2025-12-26-31.xml'
    january = 'https://tuoitre.vn/StaticSitemaps/sitemaps-2026-1-1-5.xml'
    video = 'https://tuoitre.vn/StaticSitemaps/sitemaps-video-2026-1-1-5.xml'
    calls = []

    class FakeClient:
        def get(self, url):
            calls.append(url)
            if url == index:
                urls = [old, boundary, january]
            elif url == video_index:
                urls = [video]
            else:
                suffix = 'video/article-2.htm' if url == video else 'article-1.htm'
                urls = ['https://tuoitre.vn/' + suffix]
            xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            xml += ''.join(f'<url><loc>{value}</loc></url>' for value in urls) + '</urlset>'
            return SimpleNamespace(content=xml)

    entries = crawler.discover(FakeClient(), config, 'backfill', date(2026, 1, 1), date(2026, 1, 31))

    assert old not in calls
    assert boundary in calls and video in calls
    assert {entry['url'] for entry in entries} == {
        'https://tuoitre.vn/article-1.htm', 'https://tuoitre.vn/video/article-2.htm'}


def test_backfill_does_not_retain_article_body_in_memory(config, tmp_path):
    # The CSV remains complete while memory grows with metadata, not article text.
    import csv

    row = dict.fromkeys(config['output']['fields'], 'valid')
    body = 'article text ' * 100000
    row.update(article_id='id1', url='https://tuoitre.vn/article-1.htm', content=body,
               category=config['categories'][1]['name'], published_at='2026-01-01T12:00:00+07:00')
    store = crawler.ArticleStore(tmp_path, 'backfill', config)

    store.add(row)
    resumed = crawler.ArticleStore(tmp_path, 'backfill', config)

    assert 'content' not in store.rows[0] and 'content' not in resumed.rows[0]
    with (tmp_path / config['output']['monthly_csv'].format(month='2026-01')).open(
            encoding=config['output']['encoding'], newline='') as stream:
        assert next(csv.DictReader(stream))['content'] == body


def test_month_checkpoint_resume_preserves_failures_and_daily_coverage(config, tmp_path, monkeypatch):
    # Resume keeps the manifest, skips saved/excluded/outside URLs, and exposes unresolved failures.
    from types import SimpleNamespace

    config['start_date'], config['end_date'] = '2026-01-01', '2026-01-31'
    config['backfill'] = {'max_attempts_per_run': 1, 'retry_errors_on_resume': False}
    urls = [f'https://tuoitre.vn/article-{i}.htm' for i in range(5)]
    entries = [{'url': url, 'sitemap': 'January'} for url in urls]
    calls, discoveries = [], []
    monkeypatch.setattr(crawler.Client, 'bootstrap', lambda self: None)

    def discovery(*args):
        discoveries.append(True)
        return entries

    def fetch(self, url):
        calls.append(url)
        if url == urls[4]:
            return SimpleNamespace(url=url, content=b'<html/>')
        category = '/can-biet.htm' if url == urls[3] else '/thoi-su.htm'
        published = '2026-02-01' if url == urls[2] else '2026-01-01'
        html = f'''<h1 class="detail-title">Article</h1>
        <nav class="detail-cate"><a href="{category}">Category</a></nav>
        <time itemprop="datePublished" datetime="{published}T12:00:00+07:00"></time>
        <div class="detail-content"><p>Article text.</p></div>'''
        return SimpleNamespace(url=url, content=html.encode())

    monkeypatch.setattr(crawler, 'discover', discovery)
    monkeypatch.setattr(crawler.Client, 'get', fetch)

    first = crawler.run('backfill', config, tmp_path)
    config['backfill']['max_attempts_per_run'] = None
    second = crawler.run('backfill', config, tmp_path)
    third = crawler.run('backfill', config, tmp_path)

    assert first['status'] == 'checkpointed' and first['pending_count'] == 4
    assert second['total_valid'] == 2 and third['total_valid'] == 2
    assert calls == urls and len(discoveries) == 1
    assert third['status'] == 'finished_with_errors'
    assert third['result_counts'] == {'saved': 2, 'outside_range': 1, 'excluded': 1, 'error': 1}
    assert third['unresolved_urls'] == [urls[4]] and third['pending_count'] == 0
    assert third['valid_by_day']['2026-01-01'] == 2
    assert len(third['zero_record_days']) == 30
    assert third['missing_required_rows'] == third['duplicate_ids'] == third['duplicate_urls'] == 0


def test_pilot_config_inherits_http_and_overrides_only_output_and_dates(tmp_path):
    # Monthly configuration cannot accidentally reset the shared request policy.
    (tmp_path / 'base.json').write_text(json.dumps({'http': {'delay_seconds': 2}, 'output': {'encoding': 'utf-8'}}))
    (tmp_path / 'pilot.json').write_text(json.dumps({'extends': 'base.json', 'output': {'directory': 'pilot'}}))

    config = crawler.load_config(tmp_path / 'pilot.json')

    assert config['http']['delay_seconds'] == 2
    assert config['output'] == {'encoding': 'utf-8', 'directory': 'pilot'}


def test_result_journal_repairs_interrupted_last_line_before_append(tmp_path):
    # Both an unfinished record and a missing final newline must be recoverable.
    path = tmp_path / 'results.jsonl'
    record = {'requested_url': 'https://tuoitre.vn/article-1.htm', 'status': 'saved'}
    path.write_text(json.dumps(record) + '\n{"requested_', encoding='utf-8')

    assert crawler.load_results(path) == {record['requested_url']: record}
    assert path.read_text(encoding='utf-8') == json.dumps(record) + '\n'
    path.write_text(json.dumps(record), encoding='utf-8')
    assert crawler.load_results(path) == {record['requested_url']: record}
    assert path.read_bytes().endswith(b'\n')


def test_premature_http_body_is_retried_within_configured_limit(config, monkeypatch):
    # The live pilot saw a truncated HTTP response; retry it before marking the URL unresolved.
    import requests
    from unittest.mock import Mock

    response = requests.Response()
    response.status_code = 200
    response.url = 'https://tuoitre.vn/article-1.htm'
    client = crawler.Client(config)
    client.session = Mock()
    client.session.get.side_effect = [requests.exceptions.ChunkedEncodingError('Response ended prematurely'), response]
    client.robots.parse(['User-agent: *', 'Allow: /'])
    monkeypatch.setattr(crawler.time, 'sleep', lambda _: None)

    assert client.get(response.url) is response
    assert client.session.get.call_count == 2
