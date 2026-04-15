"""
Live stderr progress indicator for commcare-export.

See ``claude/specs/2026-04-15-progress-indicator-design.md``.
"""

from collections import deque


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


class SlidingRate:
    """
    Records per second over a fixed trailing window.

    Samples are ``(monotonic_time, cumulative_count)`` pairs. The oldest
    samples outside the window are dropped on each read. ``add`` coalesces
    samples less than 100 ms apart to bound the deque size on high-rate
    streams.
    """

    _COALESCE_SECONDS = 0.1

    def __init__(self, window_seconds):
        self.window_seconds = window_seconds
        self._samples = deque()

    def add(self, count, now):
        if (
            self._samples
            and now - self._samples[-1][0] < self._COALESCE_SECONDS
        ):
            return
        self._samples.append((now, count))

    def current(self, now):
        self._evict(now)
        if len(self._samples) < 2:
            return 0.0
        oldest_t, oldest_c = self._samples[0]
        latest_t, latest_c = self._samples[-1]
        elapsed = latest_t - oldest_t
        if elapsed <= 0:
            return 0.0
        return (latest_c - oldest_c) / elapsed

    def _evict(self, now):
        cutoff = now - self.window_seconds
        while len(self._samples) > 1 and self._samples[0][0] < cutoff:
            self._samples.popleft()


def format_duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f'{seconds}s'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m'
    hours = minutes // 60
    return f'{hours}h{minutes % 60}m'


def format_count(n):
    return f'{int(n):,}'


def format_rate(rate):
    return f'{format_count(round(rate))} rec/s'


def format_eta(rate, remaining):
    if rate <= 0 or remaining is None or remaining < 0:
        return '--'
    return format_duration(remaining / rate)


def format_bar(fraction, width, unicode):
    fraction = max(0.0, min(1.0, fraction))
    filled_char = '█' if unicode else '#'
    empty_char = '░' if unicode else '-'
    filled = int(round(fraction * width))
    return f'[{filled_char * filled}{empty_char * (width - filled)}]'
