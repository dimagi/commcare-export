"""
Live stderr progress indicator for commcare-export.

See ``claude/specs/2026-04-15-progress-indicator-design.md``.
"""


class NullProgressReporter:
    """No-op reporter. Used when progress is disabled."""

    def resource_started(self, resource):
        pass

    def batch_received(self, fetched, total):
        pass

    def record_yielded(self):
        pass

    def throttled(self, wait_seconds, reason='throttled'):
        pass

    def resource_finished(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass
