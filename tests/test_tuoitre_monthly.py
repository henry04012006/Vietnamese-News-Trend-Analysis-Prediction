from datetime import date
from pathlib import Path

import pytest

import crawl_tuoitre_monthly as runner
from crawl_tuoitre import load_config


@pytest.fixture
def config():
    return load_config(Path('config/tuoitre.json'))


def test_month_jobs_preserve_existing_january_and_clip_current_month(config):
    # Existing January output must be reused, while November ends on the requested day.
    config['monthly']['existing_month_directories'] = {'2026-01': 'already-collected-january'}

    jobs = runner.month_jobs(config, date(2026, 11, 7))

    assert len(jobs) == 11
    assert jobs[0]['directory'] == 'already-collected-january'
    assert jobs[1]['start_date'] == '2026-02-01' and jobs[1]['end_date'] == '2026-02-28'
    assert jobs[-1]['start_date'] == '2026-11-01' and jobs[-1]['end_date'] == '2026-11-07'


def test_monthly_queue_continues_article_errors_stops_global_errors_and_resumes(config, tmp_path, monkeypatch):
    # Article warnings stay visible; a stopped request blocks later months until resume.
    config['end_date'] = '2026-03-31'
    calls = []
    outcomes = iter(['finished_with_errors', 'stopped'])

    def first_run(mode, month_config, root):
        calls.append(month_config['start_date'])
        return {'status': next(outcomes), 'total_valid': 10, 'pending_count': 0, 'unresolved_urls': ['bad-url']}

    monkeypatch.setattr(runner.crawler, 'run', first_run)
    first = runner.run_monthly(config, tmp_path, date(2026, 11, 7))

    assert first['status'] == 'stopped'
    assert calls == ['2026-01-01', '2026-02-01']
    assert [job['status'] for job in first['months']] == ['finished_with_errors', 'stopped', 'pending']
    monkeypatch.setattr(runner.crawler, 'run', lambda mode, cfg, root:
                        calls.append(cfg['start_date']) or {'status': 'finished', 'total_valid': 20, 'pending_count': 0})

    resumed = runner.run_monthly(config, tmp_path, date(2026, 11, 7))

    assert calls == ['2026-01-01', '2026-02-01', '2026-02-01', '2026-03-01']
    assert resumed['status'] == 'finished_with_errors'
    assert resumed['warning_months'] == ['2026-01']


def test_monthly_queue_freezes_range_across_restarts(config, tmp_path, monkeypatch):
    # A restart on a later day must not silently change a completed month's manifest range.
    calls = []
    monkeypatch.setattr(runner.crawler, 'run', lambda mode, cfg, root:
                        calls.append(cfg['end_date']) or {'status': 'finished', 'total_valid': 1, 'pending_count': 0})

    first = runner.run_monthly(config, tmp_path, date(2026, 1, 15))
    second = runner.run_monthly(config, tmp_path, date(2026, 2, 20))

    assert first['end_date'] == second['end_date'] == '2026-01-15'
    assert calls == ['2026-01-15']


def test_monthly_lock_prevents_second_writer(config, tmp_path, monkeypatch):
    # A second queue cannot launch while the queue lock already exists.
    directory = tmp_path / config['monthly']['directory']
    directory.mkdir(parents=True)
    (directory / config['monthly']['lock']).write_text('active')
    monkeypatch.setattr(runner.crawler, 'run', lambda *args: pytest.fail('second writer started'))

    with pytest.raises(FileExistsError):
        runner.run_monthly(config, tmp_path, date(2026, 11, 7))
