import io
import threading

from commcare_export.progress import (
    NullProgressReporter,
    ProgressReporter,
    ProgressSnapshot,
    RenderDriver,
    ResourceSummary,
    SlidingRate,
    format_bar,
    format_count,
    format_duration,
    format_eta,
    format_rate,
    render_log_line,
    render_summary_line,
    render_tty_line,
)


def test_null_reporter_methods_are_no_ops():
    reporter = NullProgressReporter()
    reporter.resource_started('form')
    reporter.batch_received(fetched=10, total=100)
    reporter.record_yielded()
    reporter.throttled(5.0, reason='throttled')
    reporter.resource_finished()
    reporter.start()
    reporter.stop()


def test_sliding_rate_empty_is_zero():
    rate = SlidingRate(window_seconds=30.0)
    assert rate.current(now=100.0) == 0.0


def test_sliding_rate_single_sample_is_zero():
    rate = SlidingRate(window_seconds=30.0)
    rate.add(count=10, now=100.0)
    assert rate.current(now=100.0) == 0.0


def test_sliding_rate_two_samples():
    rate = SlidingRate(window_seconds=30.0)
    rate.add(count=0, now=100.0)
    rate.add(count=60, now=110.0)
    assert rate.current(now=110.0) == 6.0


def test_sliding_rate_evicts_samples_outside_window():
    rate = SlidingRate(window_seconds=30.0)
    rate.add(count=0, now=100.0)
    rate.add(count=30, now=115.0)
    rate.add(count=60, now=130.0)
    rate.add(count=90, now=145.0)
    assert rate.current(now=145.0) == 2.0


def test_sliding_rate_coalesces_samples_within_100ms():
    rate = SlidingRate(window_seconds=30.0)
    rate.add(count=0, now=100.0)
    rate.add(count=5, now=100.05)
    rate.add(count=10, now=100.09)
    rate.add(count=20, now=110.0)
    assert len(rate._samples) == 2
    assert rate.current(now=110.0) == 2.0


def test_format_duration_seconds():
    assert format_duration(7) == '7s'
    assert format_duration(59) == '59s'


def test_format_duration_minutes():
    assert format_duration(60) == '1m'
    assert format_duration(119) == '1m'
    assert format_duration(1800) == '30m'


def test_format_duration_hours():
    assert format_duration(3600) == '1h0m'
    assert format_duration(3660) == '1h1m'
    assert format_duration(9000) == '2h30m'


def test_format_count_thousands_separator():
    assert format_count(0) == '0'
    assert format_count(999) == '999'
    assert format_count(1000) == '1,000'
    assert format_count(48231) == '48,231'
    assert format_count(120000) == '120,000'


def test_format_rate_integer():
    assert format_rate(0.0) == '0 rec/s'
    assert format_rate(63.4) == '63 rec/s'
    assert format_rate(1234.0) == '1,234 rec/s'


def test_format_eta_dashes_when_zero_or_none():
    assert format_eta(rate=0.0, remaining=100) == '--'
    assert format_eta(rate=10.0, remaining=None) == '--'


def test_format_eta_minutes_and_hours():
    assert format_eta(rate=10.0, remaining=600) == '1m'
    assert format_eta(rate=10.0, remaining=18000) == '30m'
    assert format_eta(rate=10.0, remaining=36000) == '1h0m'


def test_format_bar_ascii():
    assert format_bar(fraction=0.0, width=10, unicode=False) == '[----------]'
    assert format_bar(fraction=0.5, width=10, unicode=False) == '[#####-----]'
    assert format_bar(fraction=1.0, width=10, unicode=False) == '[##########]'


def test_format_bar_unicode():
    assert format_bar(fraction=0.4, width=5, unicode=True) == '[██░░░]'


def test_format_bar_clamps_fraction():
    assert format_bar(fraction=-0.1, width=5, unicode=False) == '[-----]'
    assert format_bar(fraction=1.5, width=5, unicode=False) == '[#####]'


def _make_reporter():
    return ProgressReporter(clock=_FakeClock(100.0))


class _FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_reporter_initial_snapshot_is_idle():
    reporter = _make_reporter()
    snap = reporter.snapshot()
    assert snap.resource is None
    assert snap.records == 0
    assert snap.total is None
    assert snap.rate == 0.0


def test_resource_started_sets_resource_and_resets_counters():
    clock = _FakeClock(100.0)
    reporter = ProgressReporter(clock=clock)
    reporter.resource_started('form')
    snap = reporter.snapshot()
    assert snap.resource == 'form'
    assert snap.records == 0
    assert snap.total is None
    assert snap.elapsed == 0.0


def test_batch_received_sets_total_when_known():
    reporter = _make_reporter()
    reporter.resource_started('form')
    reporter.batch_received(fetched=100, total=1000)
    assert reporter.snapshot().total == 1000


def test_batch_received_does_not_overwrite_existing_total():
    reporter = _make_reporter()
    reporter.resource_started('form')
    reporter.batch_received(fetched=100, total=1000)
    reporter.batch_received(fetched=100, total=900)
    assert reporter.snapshot().total == 1000


def test_batch_received_with_none_total_stays_none():
    reporter = _make_reporter()
    reporter.resource_started('form')
    reporter.batch_received(fetched=100, total=None)
    assert reporter.snapshot().total is None


def test_record_yielded_increments_records_and_rate():
    clock = _FakeClock(100.0)
    reporter = ProgressReporter(clock=clock)
    reporter.resource_started('form')
    for _ in range(60):
        reporter.record_yielded()
    clock.advance(10.0)
    for _ in range(60):
        reporter.record_yielded()
    snap = reporter.snapshot()
    assert snap.records == 120
    assert snap.rate == 6.0


def test_throttled_sets_deadline():
    clock = _FakeClock(100.0)
    reporter = ProgressReporter(clock=clock)
    reporter.resource_started('form')
    reporter.throttled(wait_seconds=30.0, reason='throttled')
    snap = reporter.snapshot()
    assert snap.throttled_reason == 'throttled'
    assert snap.throttled_remaining == 30.0
    clock.advance(10.0)
    assert reporter.snapshot().throttled_remaining == 20.0


def test_throttled_state_clears_on_next_record():
    reporter = _make_reporter()
    reporter.resource_started('form')
    reporter.throttled(wait_seconds=30.0, reason='throttled')
    reporter.record_yielded()
    snap = reporter.snapshot()
    assert snap.throttled_reason is None
    assert snap.throttled_remaining is None


def test_resource_finished_records_summary_and_clears_resource():
    clock = _FakeClock(100.0)
    reporter = ProgressReporter(clock=clock)
    reporter.resource_started('form')
    for _ in range(1000):
        reporter.record_yielded()
    clock.advance(10.0)
    reporter.resource_finished()
    snap = reporter.snapshot()
    assert snap.resource is None
    assert snap.last_summary is not None
    assert snap.last_summary.resource == 'form'
    assert snap.last_summary.records == 1000
    assert snap.last_summary.elapsed == 10.0


def test_snapshot_elapsed_tracks_clock():
    clock = _FakeClock(100.0)
    reporter = ProgressReporter(clock=clock)
    reporter.resource_started('form')
    clock.advance(45.0)
    assert reporter.snapshot().elapsed == 45.0


def _snap(**kwargs):
    base = dict(
        resource='form',
        records=0,
        total=None,
        elapsed=0.0,
        rate=0.0,
        throttled_reason=None,
        throttled_remaining=None,
        last_summary=None,
    )
    base.update(kwargs)
    return ProgressSnapshot(**base)


def test_render_tty_with_total_shows_bar_percent_rate_eta():
    snap = _snap(records=48231, total=120000, rate=63.0)
    line = render_tty_line(snap, bar_width=20, unicode=False)
    assert line.startswith('Forms: ')
    assert '48,231 / 120,000' in line
    assert '(40%)' in line
    assert '63 rec/s' in line
    assert 'ETA' in line


def test_render_tty_without_total_shows_fallback():
    snap = _snap(records=48231, total=None, elapsed=720.0, rate=63.0)
    line = render_tty_line(snap, bar_width=20, unicode=False)
    assert 'Forms: 48,231 records' in line
    assert '63 rec/s' in line
    assert 'elapsed 12m' in line


def test_render_tty_throttled_state():
    snap = _snap(
        records=48231,
        total=120000,
        rate=63.0,
        throttled_reason='throttled',
        throttled_remaining=17.4,
    )
    line = render_tty_line(snap, bar_width=20, unicode=False)
    assert 'throttled, retrying in 17s' in line
    assert 'ETA' not in line


def test_render_tty_retrying_label():
    snap = _snap(
        records=10,
        total=100,
        throttled_reason='retrying',
        throttled_remaining=5.0,
    )
    line = render_tty_line(snap, bar_width=20, unicode=False)
    assert 'retrying, retrying in 5s' not in line
    assert 'retrying in 5s' in line


def test_render_tty_title_cases_resource_name():
    snap = _snap(resource='case', records=1, total=10)
    line = render_tty_line(snap, bar_width=10, unicode=False)
    assert line.startswith('Cases: ')


def test_render_tty_idle_returns_empty():
    snap = _snap(resource=None)
    assert render_tty_line(snap, bar_width=20, unicode=False) == ''


def test_render_summary_line():
    summary = ResourceSummary(resource='form', records=900, elapsed=60.0)
    line = render_summary_line(summary)
    assert 'Forms:' in line
    assert '900' in line
    assert '(100%)' in line
    assert 'done in 1m' in line
    assert '15 rec/s avg' in line


def test_render_log_line_with_total():
    snap = _snap(records=48231, total=120000, rate=63.0, elapsed=754.0)
    line = render_log_line(snap)
    assert line.startswith('[00:12:34]')
    assert 'forms: 48,231/120,000 (40%)' in line
    assert '63 rec/s' in line
    assert 'ETA' in line


def test_render_log_line_without_total():
    snap = _snap(records=100, total=None, rate=10.0, elapsed=75.0)
    line = render_log_line(snap)
    assert 'forms: 100 records' in line
    assert 'elapsed 1m' in line


def test_render_log_line_throttled():
    snap = _snap(
        records=10,
        total=100,
        elapsed=30.0,
        throttled_reason='throttled',
        throttled_remaining=12.0,
    )
    line = render_log_line(snap)
    assert 'throttled, retrying in 12s' in line


def test_render_log_line_idle_returns_empty():
    snap = _snap(resource=None)
    assert render_log_line(snap) == ''


def test_render_driver_writes_redraw_sequence_on_tty():
    reporter = _make_reporter()
    reporter.resource_started('form')
    reporter.batch_received(fetched=100, total=1000)
    for _ in range(100):
        reporter.record_yielded()

    stream = io.StringIO()
    driver = RenderDriver(
        reporter, stream=stream, is_tty=True, interval=0.01, bar_width=10
    )
    driver.render_once()
    output = stream.getvalue()
    assert output.startswith('\r\x1b[K')
    assert 'Forms:' in output
    assert '\n' not in output


def test_render_driver_writes_newline_terminated_line_off_tty():
    reporter = _make_reporter()
    reporter.resource_started('form')
    reporter.batch_received(fetched=100, total=1000)

    stream = io.StringIO()
    driver = RenderDriver(
        reporter, stream=stream, is_tty=False, interval=10.0
    )
    driver.render_once()
    output = stream.getvalue()
    assert output.endswith('\n')
    assert '\x1b[K' not in output
    assert 'forms:' in output


def test_render_driver_prints_summary_line_after_resource_finished():
    reporter = _make_reporter()
    reporter.resource_started('form')
    for _ in range(10):
        reporter.record_yielded()
    reporter.resource_finished()

    stream = io.StringIO()
    driver = RenderDriver(reporter, stream=stream, is_tty=True, interval=0.01)
    driver.render_once()
    output = stream.getvalue()
    assert '(100%)' in output
    assert 'done in' in output
    assert output.endswith('\n')


def test_render_driver_thread_starts_and_stops_cleanly():
    reporter = _make_reporter()
    stream = io.StringIO()
    driver = RenderDriver(
        reporter, stream=stream, is_tty=True, interval=0.01
    )
    driver.start()
    assert driver._thread.is_alive()
    driver.stop()
    driver._thread.join(timeout=1.0)
    assert not driver._thread.is_alive()
