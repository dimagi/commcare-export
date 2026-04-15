from commcare_export.progress import NullProgressReporter, SlidingRate


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
