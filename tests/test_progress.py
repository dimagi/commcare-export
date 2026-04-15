from commcare_export.progress import (
    NullProgressReporter,
    SlidingRate,
    format_bar,
    format_count,
    format_duration,
    format_eta,
    format_rate,
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
