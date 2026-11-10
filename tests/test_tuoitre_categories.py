import json
from pathlib import Path

import pytest

import crawl_tuoitre as crawler


@pytest.fixture
def config():
    return json.loads(Path('config/tuoitre.json').read_text(encoding='utf-8'))


def article_html(category_markup):
    return f'''<h1 class="detail-title">Tiêu đề</h1>{category_markup}
    <time itemprop="datePublished" datetime="2026-01-02T09:00:00+07:00"></time>
    <div class="detail-content"><p>Nội dung bài báo.</p></div>'''


@pytest.mark.parametrize('markup,expected', [
    ('<meta property="article:section" content="Kinh doanh">', 'Kinh doanh'),
    ('<nav class="detail-cate"><a href="/nha-dat.htm">Nhà đất</a>'
     '<a href="/nha-dat/chinh-sach.htm">Chính sách</a></nav>'
     '<meta property="article:section" content="Chính sách">', 'Nhà đất'),
    ('<meta property="article:section" content="Giả - thật">', 'Giả - Thật'),
])
def test_category_uses_official_primary_label(config, markup, expected):
    # Breadcrumb's main category outranks subsection metadata.
    row = crawler.parse_article(article_html(markup), 'https://tuoitre.vn/tin-123.htm',
                                '2026-11-07T09:00:00+07:00', config)
    assert row['category'] == expected


def test_missing_category_is_rejected(config):
    # No silently empty or inferred category.
    with pytest.raises(ValueError, match='category'):
        crawler.parse_article(article_html(''), 'https://tuoitre.vn/tin-123.htm',
                              '2026-11-07T09:00:00+07:00', config)


def test_video_keeps_published_description_without_inventing_transcript(config):
    # Video subsection The gioi belongs to the top-level Video category.
    html = '''<h1 class="detail-title">Video title</h1>
    <div class="detail-cate"><a href="/video/the-gioi.htm">Thế giới</a></div>
    <meta property="article:published_time" content="2026-11-07T00:34:00+07:00">
    <p class="detail-sapo">Mô tả do Tuổi Trẻ đăng.</p>
    <div class="detail-content"><br></div>'''
    row = crawler.parse_article(html, 'https://tuoitre.vn/video/tin-123.htm',
                                '2026-11-07T09:00:00+07:00', config)
    assert row['category'] == 'Video'
    assert row['content'] == 'Mô tả do Tuổi Trẻ đăng.'


def test_category_discovery_uses_each_page_and_filters_navigation(config):
    # Same article can be cross-listed; keep per-page provenance until parsing it.
    from types import SimpleNamespace
    from datetime import date

    config['categories'] = config['categories'][:2]
    calls = []

    class FakeClient:
        def get(self, url):
            calls.append(url)
            return SimpleNamespace(url=url, content=b'''
            <a href="/kinh-doanh.htm">Navigation</a>
            <a class="box-category-link-title" href="/bai-123.htm">Article</a>
            <a class="box-category-link-title" href="/bai-123.htm">Duplicate</a>
            <a class="box-category-link-title" href="https://other.example/bai-456.htm">Other</a>''')

    entries = crawler.discover(FakeClient(), config, 'category-sample', date(2026, 1, 1), date(2026, 11, 7))

    assert calls == [item['url'] for item in config['categories']]
    assert [entry['category'] for entry in entries] == ['Video', 'Thời sự']
    assert all(entry['url'] == 'https://tuoitre.vn/bai-123.htm' for entry in entries)


def test_category_sample_rejects_cross_listing_meets_quota_and_resumes(config, tmp_path, monkeypatch):
    # Never relabel a science article as current affairs because a listing promotes it.
    from types import SimpleNamespace

    config['categories'] = [item for item in config['categories'] if item['name'] in ['Thời sự', 'Khoa học']]
    config['category_sample']['per_category'] = 1
    news, science = 'Thời sự', 'Khoa học'
    science_url, news_url = 'https://tuoitre.vn/science-1.htm', 'https://tuoitre.vn/news-2.htm'
    entries = [{'url': science_url, 'category': news}, {'url': news_url, 'category': news},
               {'url': science_url, 'category': science}]
    calls = []
    monkeypatch.setattr(crawler.Client, 'bootstrap', lambda self: None)
    monkeypatch.setattr(crawler, 'discover', lambda *args: entries)

    def fetch(self, url):
        calls.append(url)
        label = science if url == science_url else news
        html = article_html(f'<meta property="article:section" content="{label}">')
        return SimpleNamespace(url=url, content=html.encode('utf-8'))

    monkeypatch.setattr(crawler.Client, 'get', fetch)
    first = crawler.run('category-sample', config, tmp_path)
    count = len(calls)
    second = crawler.run('category-sample', config, tmp_path)

    assert first['automated_gate_pass'] and second['automated_gate_pass']
    assert first['valid_by_category'] == {news: 1, science: 1}
    assert first['total_valid'] == 2 and len(first['errors']) == 1
    assert len(calls) == count
    assert second['saved'] == 0
