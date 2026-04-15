from commcare_export.progress import NullProgressReporter


def test_null_reporter_methods_are_no_ops():
    reporter = NullProgressReporter()
    reporter.resource_started('form')
    reporter.batch_received(fetched=10, total=100)
    reporter.record_yielded()
    reporter.throttled(5.0, reason='throttled')
    reporter.resource_finished()
    reporter.start()
    reporter.stop()
