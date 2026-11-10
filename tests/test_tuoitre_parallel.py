import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import crawl_tuoitre as crawler


@pytest.fixture
def config():
    config = crawler.load_config(Path('config/tuoitre.json'))
    config['http'].update(workers=3, prefetch=6, delay_seconds=0.03)
    return config


def test_parallel_downloads_are_bounded_and_only_main_thread_writes(config, tmp_path, monkeypatch):
    # Downloads overlap, but CSV updates remain serial and produce the same unique records.
    urls = [f'https://tuoitre.vn/article-{i}.htm' for i in range(20)]
    monkeypatch.setattr(crawler, 'discover', lambda *args: [{'url': url} for url in urls])
    monkeypatch.setattr(crawler.Client, 'bootstrap', lambda self: None)
    state = {'active': 0, 'maximum': 0}
    lock, writer_threads = threading.Lock(), set()
    original_add = crawler.ArticleStore.add

    def fetch(self, url):
        with lock:
            state['active'] += 1
            state['maximum'] = max(state['maximum'], state['active'])
        time.sleep(0.02)
        with lock:
            state['active'] -= 1
        html = b'''<h1 class="detail-title">Article</h1><nav class="detail-cate">
        <a href="/thoi-su.htm">Category</a></nav>
        <time itemprop="datePublished" datetime="2026-01-02T12:00:00+07:00"></time>
        <div class="detail-content"><p>Complete article body.</p></div>'''
        return SimpleNamespace(url=url, content=html)

    def add(store, row):
        writer_threads.add(threading.get_ident())
        return original_add(store, row)

    monkeypatch.setattr(crawler.Client, 'get', fetch)
    monkeypatch.setattr(crawler.ArticleStore, 'add', add)
    report = crawler.run('backfill', config, tmp_path)

    assert 1 < state['maximum'] <= config['http']['workers']
    assert writer_threads == {threading.get_ident()}
    assert report['total_valid'] == len(urls)
    assert report['duplicate_ids'] == report['duplicate_urls'] == report['missing_required_rows'] == 0


def test_request_pacer_spaces_all_threads_and_stops_cancelled_requests():
    # Threads share the same start spacing rather than receiving independent request budgets.
    from concurrent.futures import ThreadPoolExecutor

    stop = threading.Event()
    pacer = crawler.RequestPacer(stop)
    starts = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(lambda: (pacer.wait(0.03), starts.append(time.monotonic()))) for _ in range(5)]
        for future in futures:
            future.result()

    starts.sort()
    assert all(b - a >= 0.025 for a, b in zip(starts, starts[1:]))
    stop.set()
    with pytest.raises(crawler.StopCrawl):
        pacer.wait(0.03)


def test_download_pool_bounds_prefetch_and_propagates_access_stop(config, monkeypatch):
    # Access denial cancels queued work; no unbounded download queue is permitted.
    parent = crawler.Client(config)
    stop = threading.Event()
    pacer = crawler.RequestPacer(stop)
    calls = []

    def fetch(self, url):
        calls.append(url)
        if url.endswith('-0.htm'):
            raise crawler.StopCrawl('HTTP 429')
        time.sleep(0.01)
        return SimpleNamespace(url=url, content=b'body')

    monkeypatch.setattr(crawler.Client, 'get', fetch)
    pool = crawler.DownloadPool(parent, config, [f'https://tuoitre.vn/article-{i}.htm' for i in range(50)], pacer, stop)
    try:
        assert len(pool.futures) <= config['http']['prefetch']
        with pytest.raises(crawler.StopCrawl, match='429'):
            pool.get('https://tuoitre.vn/article-0.htm')
    finally:
        pool.close()
    assert stop.is_set()
    assert len(calls) <= config['http']['workers']


def test_access_denial_in_inflight_prefetch_is_not_hidden_by_checkpoint(config, tmp_path, monkeypatch):
    # A 429 received while closing unused prefetch must still stop the entire queue.
    config['backfill']['max_attempts_per_run'] = 1
    config['http']['prefetch'] = 2
    urls = ['https://tuoitre.vn/article-0.htm', 'https://tuoitre.vn/article-1.htm']
    monkeypatch.setattr(crawler, 'discover', lambda *args: [{'url': url} for url in urls])
    monkeypatch.setattr(crawler.Client, 'bootstrap', lambda self: None)
    second_started = threading.Event()

    def fetch(self, url):
        if url == urls[1]:
            second_started.set()
            time.sleep(0.05)
            raise crawler.StopCrawl('HTTP 429: prefetched URL')
        assert second_started.wait(1)
        html = b'''<h1 class="detail-title">Article</h1><nav class="detail-cate">
        <a href="/thoi-su.htm">Category</a></nav>
        <time itemprop="datePublished" datetime="2026-01-02T12:00:00+07:00"></time>
        <div class="detail-content"><p>Article text.</p></div>'''
        return SimpleNamespace(url=url, content=html)

    monkeypatch.setattr(crawler.Client, 'get', fetch)
    report = crawler.run('backfill', config, tmp_path)

    assert report['status'] == 'stopped'
    assert any('429' in error['reason'] for error in report['errors'])
