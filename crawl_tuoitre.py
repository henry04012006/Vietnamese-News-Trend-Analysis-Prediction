"""Collect Tuoi Tre articles using the site's public sitemaps."""

import argparse
import csv
import hashlib
import json
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import requests


def normalize_url(url, config):
    parsed = urlsplit(url.strip())
    if (parsed.scheme not in config['allowed_schemes']
            or parsed.hostname not in config['allowed_hosts']
            or parsed.username or parsed.password or parsed.port):
        raise ValueError(f'URL outside configured source: {url}')
    policy = config['url']
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if key.lower() not in policy['tracking_keys']
             and not any(key.lower().startswith(prefix) for prefix in policy['tracking_prefixes'])]
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path, urlencode(query), ''))


class ExcludedCategory(ValueError):
    """An identified source category is outside the requested corpus."""


class OutsideDateRange(ValueError):
    """An article is valid but falls outside the requested publication dates."""


def category_from_route(target, config):
    path = urlsplit(target).path
    if urlsplit(target).hostname not in config['allowed_hosts']:
        return None
    for category in config['categories']:
        root = urlsplit(category['url']).path.removesuffix('.htm')
        if path == root + '.htm' or path.startswith(root + '/'):
            return category['name']
    for route in config['category_routes']:
        if path == route['path'] + '.htm' or path.startswith(route['path'] + '/'):
            return route['category']
    for excluded in config['excluded_categories']:
        if path == excluded['path'] + '.htm' or path.startswith(excluded['path'] + '/'):
            raise ExcludedCategory(excluded['name'])
    return None


def extract_category(soup, url, config):
    categories = config['categories']
    path = urlsplit(url).path
    for category in categories:
        if category.get('article_path_prefix') and path.startswith(category['article_path_prefix']):
            return category['name']
    for link in soup.select(config['selectors']['category_links']):
        label = category_from_route(urljoin(url, link['href']), config)
        if label:
            return label
    for script in soup.select(config['selectors']['structured_data']):
        try:
            data = json.loads(script.get_text())
        except json.JSONDecodeError:
            continue
        documents = data if isinstance(data, list) else [data]
        for document in documents:
            if not isinstance(document, dict) or document.get('@type') != 'BreadcrumbList':
                continue
            for element in document.get('itemListElement', []):
                item = element.get('item', {})
                target = item.get('@id', '') if isinstance(item, dict) else item
                label = category_from_route(urljoin(url, target), config)
                if label:
                    return label
    meta = soup.select_one(config['selectors']['category_meta'])
    label = ' '.join(meta.get(config['selectors']['category_attribute'], '').split()).casefold() if meta else ''
    for category in categories:
        if label in [name.casefold() for name in [category['name'], *category.get('aliases', [])]]:
            return category['name']
    if label in [item['name'].casefold() for item in config['excluded_categories']]:
        raise ExcludedCategory(meta.get(config['selectors']['category_attribute']))
    raise ValueError('Missing or unsupported official category')


def parse_article(html, url, collected_at, config):
    soup = BeautifulSoup(html, 'html.parser')
    selectors = config['selectors']
    title = soup.select_one(selectors['title'])
    body = soup.select_one(selectors['body'])
    publication = soup.select_one(selectors['publication'])
    attr = selectors['publication_attribute']
    if publication is None:
        publication = soup.select_one(selectors['publication_fallback'])
        attr = selectors['publication_fallback_attribute']
    value = publication.get(attr, '') if publication else ''
    try:
        published = datetime.fromisoformat(value)
        if published.tzinfo is None:
            raise ValueError('timezone missing')
    except ValueError as exc:
        raise ValueError(f'Invalid publication time: {value!r}') from exc
    if title is None or body is None:
        raise ValueError('Missing title or article body')
    for node in body.select(selectors['remove']):
        node.decompose()
    # Join inline text without inserting spaces before punctuation.
    blocks = body.select(selectors['blocks'])
    paragraphs = [' '.join(node.get_text().split()) for node in blocks
                  if not any(parent in blocks for parent in node.parents)]
    description = soup.select_one(selectors['description'])
    category = extract_category(soup, url, config)
    content = config['output']['paragraph_separator'].join(p for p in paragraphs if p)
    category_policy = next(item for item in config['categories'] if item['name'] == category)
    if not content and category_policy.get('description_as_content') and description:
        content = ' '.join(description.get_text().split())
    url = normalize_url(url, config)
    row = {
        'title': ' '.join(title.get_text().split()),
        'content': content,
        'source': config['source'], 'url': url,
        'published_at': published.astimezone(ZoneInfo(config['timezone'])).isoformat(),
        'collected_at': collected_at,
        'description': ' '.join(description.get_text().split()) if description else '',
        'category': category,
        'article_id': hashlib.sha256((config['source'] + config['url']['id_separator'] + url).encode()).hexdigest(),
    }
    missing = [key for key in config['output']['required_fields'] if not row[key].strip()]
    if missing:
        raise ValueError(f'Missing required fields: {missing}')
    return row


class StopCrawl(RuntimeError):
    """An access restriction requires stopping the entire run."""


class CancelledDownload(StopCrawl):
    """Queued work cancelled before a new HTTP request begins."""


class RequestPacer:
    def __init__(self, stop_event):
        self.stop_event = stop_event
        self.lock = threading.Lock()
        self.last_request = None
        self.reason = None

    def cancel(self, reason):
        if self.reason is None:
            self.reason = str(reason)
        self.stop_event.set()

    def wait(self, delay):
        with self.lock:
            if self.stop_event.is_set():
                raise CancelledDownload(self.reason or 'Download batch cancelled')
            if self.last_request is not None:
                remaining = max(0, delay - (time.monotonic() - self.last_request))
                if self.stop_event.wait(remaining):
                    raise CancelledDownload(self.reason or 'Download batch cancelled')
            self.last_request = time.monotonic()


class Client:
    def __init__(self, config, pacer=None, stop_event=None):
        self.config = config
        self.policy = config['http']
        self.retry_exceptions = tuple(getattr(requests.exceptions, name) for name in self.policy['retry_exceptions'])
        self.session = requests.Session()
        self.session.headers['User-Agent'] = self.policy['user_agent']
        self.robots = RobotFileParser()
        self.last_request = None
        self.delay = self.policy['delay_seconds']
        self.pacer, self.stop_event = pacer, stop_event

    def bootstrap(self):
        response = self.get(self.config['robots_url'], check_robots=False)
        self.robots.parse(response.content.decode('utf-8-sig').splitlines())
        delay = self.robots.crawl_delay(self.policy['user_agent'])
        if delay is not None:
            self.delay = max(self.delay, delay)

    def get(self, url, check_robots=True):
        for redirect in range(self.policy['max_redirects'] + 1):
            url = normalize_url(url, self.config)
            if check_robots and not self.robots.can_fetch(self.policy['user_agent'], url):
                if self.pacer:
                    self.pacer.cancel(f'robots.txt disallows {url}')
                raise StopCrawl(f'robots.txt disallows {url}')
            for attempt in range(self.policy['attempts']):
                if self.stop_event is not None and self.stop_event.is_set():
                    raise CancelledDownload(self.pacer.reason if self.pacer and self.pacer.reason else 'Download batch cancelled')
                if self.pacer:
                    self.pacer.wait(self.delay)
                elif self.last_request is not None:
                    time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
                self.last_request = time.monotonic()
                try:
                    response = self.session.get(url, timeout=self.policy['timeout_seconds'], allow_redirects=False)
                    if response.status_code in self.policy['stop_statuses']:
                        if self.pacer:
                            self.pacer.cancel(f'HTTP {response.status_code}: {url}')
                        raise StopCrawl(f'HTTP {response.status_code}: {url}')
                    if response.status_code in self.policy['retry_statuses']:
                        response.raise_for_status()
                except self.retry_exceptions:
                    if attempt + 1 == self.policy['attempts']:
                        raise
                    backoff = self.policy['backoff_seconds'] * (attempt + 1)
                    if self.stop_event is not None:
                        if self.stop_event.wait(backoff):
                            raise CancelledDownload(self.pacer.reason or 'Download batch cancelled')
                    else:
                        time.sleep(backoff)
                    continue
                break
            if response.is_redirect:
                url = urljoin(url, response.headers['Location'])
                continue
            response.raise_for_status()
            return response
        raise StopCrawl(f'Too many redirects: {url}')


class DownloadPool:
    def __init__(self, parent, config, urls, pacer, stop_event):
        self.parent, self.config = parent, config
        self.pacer, self.stop_event = pacer, stop_event
        self.executor = ThreadPoolExecutor(max_workers=config['http']['workers'])
        self.local = threading.local()
        self.clients, self.futures = [], {}
        self.clients_lock = threading.Lock()
        self.stop_url = None
        self.urls = iter(urls)
        self.fill()

    def fetch(self, url):
        if self.stop_event.is_set():
            raise CancelledDownload(self.pacer.reason or 'Download batch cancelled')
        if not hasattr(self.local, 'client'):
            client = Client(self.config, self.pacer, self.stop_event)
            client.robots, client.delay = self.parent.robots, self.parent.delay
            self.local.client = client
            with self.clients_lock:
                self.clients.append(client)
        try:
            response = self.local.client.get(url)
            response._collected_at = datetime.now(ZoneInfo(self.config['timezone'])).isoformat()
            return response
        except CancelledDownload:
            raise
        except StopCrawl as exc:
            if self.stop_url is None:
                self.stop_url = url
            self.pacer.cancel(exc)
            raise

    def fill(self):
        while len(self.futures) < self.config['http']['prefetch'] and not self.stop_event.is_set():
            url = next(self.urls, None)
            if url is None:
                break
            self.futures[url] = self.executor.submit(self.fetch, url)

    def get(self, url):
        future = self.futures.pop(url)
        try:
            return future.result()
        finally:
            self.fill()

    def discard(self, url):
        future = self.futures.pop(url, None)
        if future is not None:
            future.cancel()
        self.fill()

    def close(self):
        self.stop_event.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
        for client in self.clients:
            client.session.close()


def sitemap_locations(xml, config):
    root = ET.fromstring(xml)
    ns = '{' + config['sitemap_namespace'] + '}'
    return [node.text.strip() for node in root.findall(f'*/{ns}loc') if node.text]


class ArticleStore:
    def __init__(self, directory, mode, config):
        self.directory, self.mode, self.config = directory, mode, config
        self.rows = []
        output = config['output']
        csv.field_size_limit(output['csv_field_limit'])
        if mode == 'category-sample':
            pattern = output['category_sample_csv']
        else:
            pattern = output['sample_csv'] if mode == 'sample' else output['monthly_csv'].format(month='*')
        for path in sorted(directory.glob(pattern)):
            with path.open(encoding=output['encoding'], newline='') as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames != output['fields']:
                    raise ValueError(f'Unexpected CSV schema: {path}')
                for row in reader:
                    self.remember(row)
        self.urls = {row['url'] for row in self.rows}
        self.ids = {row['article_id'] for row in self.rows}

    def remember(self, row):
        if self.mode == 'backfill':
            summary = {key: row[key] for key in self.config['output']['backfill_memory_fields']}
            summary['_content_chars'] = len(row['content'])
            summary['_missing_required'] = any(not row[key].strip() for key in self.config['output']['required_fields'])
            self.rows.append(summary)
        else:
            self.rows.append(row)

    def add(self, row):
        if row['url'] in self.urls or row['article_id'] in self.ids:
            return False
        output = self.config['output']
        filename = (output['sample_csv'] if self.mode == 'sample'
                    else output['monthly_csv'].format(month=row['published_at'][:7]))
        if self.mode == 'category-sample':
            filename = output['category_sample_csv']
        path = self.directory / filename
        has_header = path.exists() and path.stat().st_size > 0
        with path.open('a', encoding=output['encoding'], newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=output['fields'])
            if not has_header:
                writer.writeheader()
            writer.writerow(row)
        self.remember(row)
        self.urls.add(row['url'])
        self.ids.add(row['article_id'])
        return True


def discover(client, config, mode, start, end):
    if mode == 'category-sample':
        entries = []
        for category in config['categories']:
            response = client.get(category['url'])
            soup = BeautifulSoup(response.content, 'html.parser')
            candidates = []
            for link in soup.select(config['selectors']['category_article_links']):
                url = urljoin(response.url, link['href'])
                if (urlsplit(url).hostname in config['allowed_hosts']
                        and re.search(config['article_path_pattern'], urlsplit(url).path)):
                    candidates.append(normalize_url(url, config))
            candidates = list(dict.fromkeys(candidates))[:config['category_sample']['max_candidates']]
            entries.extend({'url': url, 'category': category['name'], 'category_page': category['url']}
                           for url in candidates)
            print(f'Category {category["name"]}: {len(candidates)} candidates', flush=True)
        return entries
    first_month = start.year * 12 + start.month - 1 - config['sitemap_lookback_months']
    maps = []
    indexes = [{'url': config['sitemap_index'], 'pattern': config['sitemap_pattern']}]
    if mode == 'backfill':
        indexes.extend(config['additional_sitemap_indexes'])
    for source in indexes:
        index = client.get(source['url'])
        for url in sitemap_locations(index.content, config):
            match = re.search(source['pattern'], url)
            if match:
                values = {key: int(value) for key, value in match.groupdict().items()}
                period = date(values['year'], values['month'], values['day'])
                period_end = date(values['year'], values['month'], values['last_day'])
                overlap_end = period_end + timedelta(days=config['sitemap_boundary_overlap_days'])
                if (period <= end and overlap_end >= start
                        and period.year * 12 + period.month - 1 >= first_month):
                    maps.append((period, url))
    maps.sort()
    if not maps:
        raise ValueError('No sitemaps in requested date range')
    if mode == 'sample':
        # Choose an early-year map, not the adjacent previous-year map.
        old = next(item for item in maps if item[0] >= start)
        chosen = [(maps[-1], 'recent', config['sample']['recent_count']),
                  (old, 'old', config['sample']['old_count'])]
    else:
        chosen = [(item, 'backfill', None) for item in maps]
    entries, seen = [], set()
    for (period, sitemap), group, count in chosen:
        response = client.get(sitemap)
        candidates = []
        for url in sitemap_locations(response.content, config):
            if (urlsplit(url).hostname in config['allowed_hosts']
                    and re.search(config['article_path_pattern'], urlsplit(url).path)):
                candidates.append(normalize_url(url, config))
        candidates = list(dict.fromkeys(candidates))
        if count is not None:
            if len(candidates) < count:
                raise ValueError(f'Not enough {group} URLs in {sitemap}')
            if group == 'old':
                candidates.reverse()
                candidates = [candidates[i * (len(candidates) - 1) // max(1, count - 1)] for i in range(count)]
            else:
                candidates = candidates[:count]
        for url in candidates:
            if url not in seen:
                entries.append({'url': url, 'group': group, 'sitemap': sitemap})
                seen.add(url)
        print(f'Sitemap {period}: {len(candidates)} URLs', flush=True)
    return entries


def write_json(path, value, config):
    temporary = path.with_name(path.name + config['output']['json_temp_suffix'])
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def load_results(path):
    results = {}
    if not path.exists():
        return results
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            if index == len(lines) - 1 and not line.endswith(b'\n'):
                path.write_bytes(b''.join(lines[:index]))
                break
            raise
        results[record['requested_url']] = record
        if index == len(lines) - 1 and not line.endswith(b'\n'):
            with path.open('ab') as stream:
                stream.write(b'\n')
    return results


def load_publication_cache(root, config, current_journal):
    policy = config['date_cache']
    cache, conflicts = {}, set()
    if not policy['enabled']:
        return cache
    paths = {path.resolve() for pattern in policy['journal_globs'] for path in root.glob(pattern)}
    for path in sorted(paths):
        if path == current_journal.resolve():
            continue
        # Read complete records only; never repair or modify another month's journal.
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                    if record.get('status') not in policy['trusted_statuses']:
                        continue
                    published = datetime.fromisoformat(record.get('published_at', ''))
                    if published.tzinfo is None:
                        continue
                    published = published.astimezone(ZoneInfo(config['timezone']))
                except (json.JSONDecodeError, ValueError):
                    continue
                requested = record.get('requested_url')
                if not requested:
                    continue
                resolved = record.get('resolved_url', requested)
                for url in {requested, resolved}:
                    if url in conflicts:
                        continue
                    if url in cache and cache[url]['published_at'][:10] != published.date().isoformat():
                        cache.pop(url)
                        conflicts.add(url)
                    else:
                        cache[url] = {'url': resolved, 'published_at': published.isoformat(), 'journal': str(path)}
    return cache


def summarize(store, config):
    rows = store.rows
    return {
        'total_valid': len(rows),
        'months': sorted({row['published_at'][:7] for row in rows}),
        'duplicate_urls': len(rows) - len({row['url'] for row in rows}),
        'duplicate_ids': len(rows) - len({row['article_id'] for row in rows}),
        'missing_required_rows': sum(row['_missing_required'] if '_missing_required' in row else
            any(not row[key].strip() for key in config['output']['required_fields']) for row in rows),
        'short_content_urls': [row['url'] for row in rows if row.get('_content_chars', len(row.get('content', '')))
                                < config['validation']['short_content_chars']],
        'first_publication': min((row['published_at'] for row in rows), default=None),
        'last_publication': max((row['published_at'] for row in rows), default=None),
        'valid_by_category': {category['name']: sum(row['category'] == category['name'] for row in rows)
                                for category in config['categories']},
    }


def update_backfill_report(report, entries, results, store, start, end, config):
    report.update(summarize(store, config))
    daily = Counter(row['published_at'][:10] for row in store.rows)
    report['valid_by_day'] = {(start + timedelta(days=i)).isoformat(): daily[(start + timedelta(days=i)).isoformat()]
                             for i in range((end - start).days + 1)}
    report['zero_record_days'] = [day for day, count in report['valid_by_day'].items() if not count]
    selected = [results[entry['url']] for entry in entries if entry['url'] in results]
    report['result_counts'] = dict(Counter(record['status'] for record in selected))
    report['unprocessed_urls'] = [entry['url'] for entry in entries if entry['url'] not in results]
    report['pending_count'] = len(report['unprocessed_urls'])
    report['unresolved_errors'] = [record for record in selected if record['status'] == 'error']
    report['unresolved_urls'] = [record['requested_url'] for record in report['unresolved_errors']]
    report['coverage_note'] = 'Counts describe saved articles, not completeness against all articles on the website.'


def run(mode, config, root):
    output = config['output']
    is_sample = mode in ('sample', 'category-sample')
    directory = root / output['directory']
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / output['lock']
    # Exclusive creation prevents two writers from corrupting the same CSV.
    with lock.open('x', encoding='utf-8') as stream:
        stream.write(datetime.now(ZoneInfo(config['timezone'])).isoformat())
    report = {'mode': mode, 'source': config['source'], 'status': 'running', 'errors': [], 'attempted': 0, 'saved': 0}
    error_path = directory / output['errors'].format(mode=mode)
    results, entries, store, publication_cache, pool = {}, [], None, {}, None
    journal_path = directory / output['journal'].format(mode=mode)

    def record_result(url, status, row=None, reason=None):
        record = {'requested_url': url, 'status': status,
                  'time': datetime.now(ZoneInfo(config['timezone'])).isoformat()}
        if row:
            record.update(resolved_url=row['url'], published_at=row['published_at'])
        if reason:
            record['reason'] = str(reason)
        with journal_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        results[url] = record

    def checkpoint():
        if mode == 'backfill' and store is not None:
            update_backfill_report(report, entries, results, store, start, end, config)
        report['updated_at'] = datetime.now(ZoneInfo(config['timezone'])).isoformat()
        write_json(directory / output['report'].format(mode=mode), report, config)

    def error(url, exc, category=None):
        record = {'url': url, 'reason': str(exc), 'time': datetime.now(ZoneInfo(config['timezone'])).isoformat()}
        if category:
            record['requested_category'] = category
        report['errors'].append(record)
        with error_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(f'ERROR {url}: {exc}', flush=True)

    try:
        start = date.fromisoformat(config['start_date'])
        now = datetime.now(ZoneInfo(config['timezone']))
        end = date.fromisoformat(config['end_date']) if config['end_date'] else now.date()
        if start > end:
            raise ValueError('start_date must not exceed end_date')
        report.update(start_date=start.isoformat(), end_date=end.isoformat(), started_at=now.isoformat())
        parallel = mode == 'backfill' and config['http']['workers'] > 1
        stop_event = threading.Event()
        pacer = RequestPacer(stop_event) if parallel else None
        client = Client(config, pacer, stop_event if parallel else None)
        client.bootstrap()
        manifest_path = directory / output['manifest'].format(mode=mode)
        if is_sample and manifest_path.exists():
            entries = json.loads(manifest_path.read_text(encoding='utf-8'))
        elif mode == 'backfill' and manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if not isinstance(manifest, dict) or manifest.get('start_date') != start.isoformat() or manifest.get('end_date') != end.isoformat():
                raise ValueError('Backfill manifest range mismatch; use a separate output directory')
            entries = manifest['entries']
        else:
            entries = discover(client, config, mode, start, end)
            manifest = {'start_date': start.isoformat(), 'end_date': end.isoformat(), 'entries': entries} if mode == 'backfill' else entries
            write_json(manifest_path, manifest, config)
        report['discovered'] = len(entries)
        store = ArticleStore(directory, mode, config)
        if mode == 'backfill':
            results = load_results(journal_path)
            publication_cache = load_publication_cache(root, config, journal_path)
            report.update(date_cache_entries=len(publication_cache), date_cache_skips=0)
        checkpoint()
        html_dir = directory / output['category_html_directory' if mode == 'category-sample' else 'html_directory']
        if is_sample:
            html_dir.mkdir(exist_ok=True)
        if parallel:
            def needs_download(entry):
                url = entry['url']
                previous = results.get(url, {})
                if previous.get('resolved_url', entry.get('resolved_url', url)) in store.urls:
                    return False
                if previous.get('status') in ('excluded', 'outside_range'):
                    return False
                if previous.get('status') == 'error' and not config['backfill']['retry_errors_on_resume']:
                    return False
                known = publication_cache.get(url)
                return not known or start <= date.fromisoformat(known['published_at'][:10]) <= end
            pool = DownloadPool(client, config, [entry['url'] for entry in entries if needs_download(entry)], pacer, stop_event)
        report['download_workers'] = config['http']['workers'] if parallel else 1
        for entry in entries:
            url = entry['url']
            previous = results.get(url, {})
            if mode == 'category-sample':
                valid_count = sum(row['category'] == entry['category'] for row in store.rows)
                if valid_count >= config['category_sample']['per_category']:
                    continue
            if previous.get('resolved_url', entry.get('resolved_url', url)) in store.urls:
                if pool:
                    pool.discard(url)
                if mode == 'backfill' and previous.get('status') != 'saved':
                    record_result(url, 'saved')
                continue
            if mode == 'backfill':
                if previous.get('status') in ('excluded', 'outside_range'):
                    continue
                if previous.get('status') == 'error' and not config['backfill']['retry_errors_on_resume']:
                    continue
                limit = config['backfill']['max_attempts_per_run']
                if limit is not None and report['attempted'] >= limit:
                    report['status'] = 'checkpointed'
                    break
                known = publication_cache.get(url)
                if known and not start <= date.fromisoformat(known['published_at'][:10]) <= end:
                    record_result(url, 'outside_range', known, reason=f'Verified publication cached from {known["journal"]}')
                    report['date_cache_skips'] += 1
                    if report['date_cache_skips'] % config['date_cache']['checkpoint_every'] == 0:
                        checkpoint()
                    continue
            report['attempted'] += 1
            row = None
            try:
                response = pool.get(url) if pool else client.get(url)
                collected = getattr(response, '_collected_at', None) or datetime.now(ZoneInfo(config['timezone'])).isoformat()
                row = parse_article(response.content, response.url, collected, config)
                if mode == 'category-sample' and row['category'] != entry['category']:
                    raise ValueError(f'Category mismatch: requested={entry["category"]}; official={row["category"]}')
                published = datetime.fromisoformat(row['published_at'])
                if not start <= published.date() <= end or published > datetime.fromisoformat(collected):
                    raise OutsideDateRange(f'Publication outside requested range: {row["published_at"]}')
                if is_sample:
                    (html_dir / output['html_filename'].format(**row)).write_bytes(response.content)
                report['saved'] += int(store.add(row))
                entry['resolved_url'] = row['url']
                if is_sample:
                    write_json(manifest_path, entries, config)
                else:
                    record_result(url, 'saved', row)
            except CancelledDownload:
                raise
            except StopCrawl as exc:
                if mode == 'backfill':
                    record_result(url, 'error', row, exc)
                raise
            except ExcludedCategory as exc:
                if mode == 'backfill':
                    record_result(url, 'excluded', row, exc)
                else:
                    error(url, exc, entry.get('category'))
            except OutsideDateRange as exc:
                if mode == 'backfill':
                    record_result(url, 'outside_range', row, exc)
                else:
                    error(url, exc, entry.get('category'))
            except (requests.RequestException, ValueError) as exc:
                error(url, exc, entry.get('category'))
                if mode == 'backfill':
                    record_result(url, 'error', row, exc)
            if report['attempted'] % config['progress_every'] == 0:
                checkpoint()
                print(f'Attempted {report["attempted"]}; saved {report["saved"]}; errors {len(report["errors"])}', flush=True)
        rows = store.rows
        report.update(summarize(store, config))
        if report['status'] == 'running':
            report['status'] = 'finished'
        if mode == 'backfill':
            update_backfill_report(report, entries, results, store, start, end, config)
            if report['status'] == 'finished' and report['unresolved_urls']:
                report['status'] = 'finished_with_errors'
        months, duplicates, duplicate_ids, missing = (report[key] for key in
            ('months', 'duplicate_urls', 'duplicate_ids', 'missing_required_rows'))
        if mode == 'category-sample':
            target = config['category_sample']['per_category']
            report['target_per_category'] = target
            report['missing_categories'] = [name for name, count in report['valid_by_category'].items() if count < target]
            report['automated_gate_pass'] = (not report['missing_categories'] and not duplicates
                                             and not duplicate_ids and not missing)
            report['manual_review_required'] = config['validation']['manual_review_count']
        if mode == 'sample':
            groups = {entry.get('resolved_url', entry['url']): entry['group'] for entry in entries}
            counts = {group: sum(groups.get(row['url']) == group for row in rows) for group in ('recent', 'old')}
            report['valid_by_group'] = counts
            report['automated_gate_pass'] = (len(entries) == sum(config['sample'].values())
                and len(rows) >= config['validation']['sample_min_valid']
                and len(months) >= config['validation']['sample_min_months']
                and all(counts.values()) and not duplicates and not duplicate_ids and not missing)
            report['manual_review_required'] = config['validation']['manual_review_count']
        print(json.dumps({key: report.get(key) for key in output['console_report_fields']},
                         ensure_ascii=False, indent=2), flush=True)
    except (StopCrawl, requests.RequestException, ValueError, OSError, ET.ParseError) as exc:
        report['status'] = 'stopped'
        error(locals().get('url', config['sitemap_index']), exc)
    except KeyboardInterrupt:
        report['status'] = 'interrupted'
    finally:
        if pool is not None:
            pool.close()
            if pool.pacer.reason:
                blocked_url = pool.stop_url or locals().get('url', config['sitemap_index'])
                if results.get(blocked_url, {}).get('status') != 'error':
                    record_result(blocked_url, 'error', reason=pool.pacer.reason)
                if report['status'] != 'stopped':
                    report['status'] = 'stopped'
                    error(blocked_url, StopCrawl(pool.pacer.reason))
        report['finished_at'] = datetime.now(ZoneInfo(config['timezone'])).isoformat()
        try:
            checkpoint()
        finally:
            lock.unlink()
    return report


def load_config(path):
    overrides = json.loads(path.read_text(encoding='utf-8-sig'))
    parent = overrides.pop('extends', None)
    if parent is None:
        return overrides
    base = load_config(path.parent / parent)

    def merge(target, source):
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                merge(target[key], value)
            else:
                target[key] = value
    merge(base, overrides)
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['sample', 'category-sample', 'backfill'])
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    report = run(args.mode, config, Path(__file__).resolve().parent)
    if args.mode == 'backfill':
        return 0 if report['status'] in ('finished', 'checkpointed') else 1
    return 0 if report['status'] == 'finished' and report['automated_gate_pass'] else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
