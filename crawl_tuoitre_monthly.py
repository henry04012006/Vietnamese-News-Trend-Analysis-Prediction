"""Resume Tuoi Tre collection sequentially, with one dataset and checkpoint per month."""

import argparse
import copy
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import crawl_tuoitre as crawler


def month_jobs(config, today):
    start = date.fromisoformat(config['start_date'])
    end = date.fromisoformat(config['end_date']) if config['end_date'] else today
    if start > end:
        raise ValueError('start_date must not exceed end_date')
    policy = config['monthly']
    current = start.replace(day=1)
    jobs = []
    while current <= end:
        following = date(current.year + current.month // 12, current.month % 12 + 1, 1)
        month = current.strftime('%Y-%m')
        directory = policy['existing_month_directories'].get(month)
        if directory is None:
            directory = str(Path(policy['directory']) / policy['month_directory_template'].format(month=month))
        jobs.append({'month': month, 'start_date': max(start, current).isoformat(),
                     'end_date': min(end, following - timedelta(days=1)).isoformat(),
                     'directory': directory, 'status': 'pending'})
        current = following
    return jobs


def run_monthly(config, root, today=None):
    policy = config['monthly']
    directory = root / policy['directory']
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / policy['lock']
    zone = ZoneInfo(config['timezone'])
    now = lambda: datetime.now(zone).isoformat()
    with lock.open('x', encoding='utf-8') as stream:
        json.dump({'pid': os.getpid(), 'started_at': now()}, stream)
    status_path = directory / policy['status']
    state = None

    def checkpoint():
        state['updated_at'] = now()
        state['warning_months'] = [job['month'] for job in state['months'] if job['status'] == 'finished_with_errors']
        state['completed_months'] = [job['month'] for job in state['months']
                                     if job['status'] in ('finished', 'finished_with_errors')]
        crawler.write_json(status_path, state, config)

    try:
        if status_path.exists():
            state = json.loads(status_path.read_text(encoding='utf-8'))
            if state['start_date'] != config['start_date'] or (config['end_date'] and state['end_date'] != config['end_date']):
                raise ValueError('Monthly queue range mismatch; use a separate monthly directory')
        else:
            jobs = month_jobs(config, today or datetime.now(zone).date())
            state = {'start_date': jobs[0]['start_date'], 'end_date': jobs[-1]['end_date'],
                     'started_at': now(), 'months': jobs}
        state.update(status='running', pid=os.getpid(), active_month=None)
        checkpoint()
        for job in state['months']:
            if job['status'] in ('finished', 'finished_with_errors'):
                continue
            month_config = copy.deepcopy(config)
            month_config.update(start_date=job['start_date'], end_date=job['end_date'])
            month_config['output']['directory'] = job['directory']
            month_directory = root / job['directory']
            month_directory.mkdir(parents=True, exist_ok=True)
            job['report'] = str(Path(job['directory']) / config['output']['report'].format(mode='backfill'))
            job.update(status='running', started_at=now())
            state['active_month'] = job['month']
            checkpoint()
            crawler.write_json(month_directory / policy['job_config'], month_config, config)
            crawler.write_json(month_directory / config['output']['process_info'],
                               {'pid': os.getpid(), 'started_at': now(), 'managed_by': str(status_path)}, config)
            print(f'Month {job["month"]}: {job["start_date"]} to {job["end_date"]}; output {job["directory"]}', flush=True)
            try:
                report = crawler.run('backfill', month_config, root)
            except Exception as exc:
                job.update(status='stopped', reason=str(exc))
                state['status'] = 'stopped'
                print(f'Month {job["month"]} stopped: {exc}', flush=True)
                break
            job.update({key: report.get(key) for key in policy['summary_fields']})
            job.update(status=report['status'], finished_at=now(), unresolved_count=len(report.get('unresolved_urls', [])))
            checkpoint()
            if job['status'] not in ('finished', 'finished_with_errors'):
                state['status'] = job['status']
                break
            if job['status'] == 'finished_with_errors' and not policy['continue_on_article_errors']:
                state['status'] = 'needs_review'
                break
        else:
            state['status'] = 'finished_with_errors' if any(
                job['status'] == 'finished_with_errors' for job in state['months']) else 'finished'
            state['active_month'] = None
        return state
    except KeyboardInterrupt:
        if state is not None:
            state['status'] = 'interrupted'
        return state
    finally:
        try:
            if state is not None:
                checkpoint()
        finally:
            lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    config = crawler.load_config(args.config)
    root = Path(__file__).resolve().parent
    try:
        state = run_monthly(config, root)
    except (OSError, ValueError) as exc:
        print(f'Monthly queue could not start: {exc}', file=sys.stderr)
        return 1
    print(json.dumps({key: state.get(key) for key in
                      ('status', 'start_date', 'end_date', 'active_month', 'completed_months', 'warning_months')},
                     ensure_ascii=False, indent=2), flush=True)
    return 0 if state['status'] == 'finished' else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
