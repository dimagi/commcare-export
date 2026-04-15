"""
Live stderr progress indicator for commcare-export.

See ``claude/specs/2026-04-15-progress-indicator-design.md``.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass


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


@dataclass(frozen=True)
class ResourceSummary:
    resource: str
    records: int
    elapsed: float


@dataclass(frozen=True)
class ProgressSnapshot:
    resource: str | None
    records: int
    total: int | None
    elapsed: float
    rate: float
    throttled_reason: str | None
    throttled_remaining: float | None
    last_summary: ResourceSummary | None


class ProgressReporter:
    """
    Thread-safe progress state. Event methods mutate state under a lock;
    ``snapshot`` returns an immutable view suitable for rendering.

    Rendering and the render thread live elsewhere; this class is pure
    state + timing so it can be unit-tested without IO.
    """

    _RATE_WINDOW_SECONDS = 30.0

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._resource = None
        self._records = 0
        self._total = None
        self._started_at = None
        self._rate = SlidingRate(self._RATE_WINDOW_SECONDS)
        self._throttled_reason = None
        self._throttled_until = None
        self._last_summary = None

    def resource_started(self, resource):
        with self._lock:
            self._resource = resource
            self._records = 0
            self._total = None
            self._started_at = self._clock()
            self._rate = SlidingRate(self._RATE_WINDOW_SECONDS)
            self._throttled_reason = None
            self._throttled_until = None

    def batch_received(self, fetched, total):
        with self._lock:
            if self._total is None and total is not None:
                self._total = int(total)

    def record_yielded(self):
        with self._lock:
            self._records += 1
            self._rate.add(self._records, self._clock())
            self._throttled_reason = None
            self._throttled_until = None

    def throttled(self, wait_seconds, reason='throttled'):
        with self._lock:
            self._throttled_reason = reason
            self._throttled_until = self._clock() + wait_seconds

    def resource_finished(self):
        with self._lock:
            if self._resource is None:
                return
            elapsed = self._clock() - (self._started_at or self._clock())
            self._last_summary = ResourceSummary(
                resource=self._resource,
                records=self._records,
                elapsed=elapsed,
            )
            self._resource = None

    def snapshot(self):
        with self._lock:
            now = self._clock()
            elapsed = (
                0.0 if self._started_at is None
                else now - self._started_at
            )
            throttled_remaining = None
            if self._throttled_until is not None:
                remaining = self._throttled_until - now
                throttled_remaining = max(0.0, remaining)
            return ProgressSnapshot(
                resource=self._resource,
                records=self._records,
                total=self._total,
                elapsed=elapsed,
                rate=self._rate.current(now),
                throttled_reason=self._throttled_reason,
                throttled_remaining=throttled_remaining,
                last_summary=self._last_summary,
            )

    def start(self):
        pass

    def stop(self):
        pass


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


_RESOURCE_LABELS = {
    'form': 'Forms',
    'case': 'Cases',
    'user': 'Users',
    'web-user': 'Web Users',
    'location': 'Locations',
    'application': 'Applications',
    'messaging-event': 'Messaging events',
    'ucr': 'UCR',
}


def _label(resource):
    return _RESOURCE_LABELS.get(resource, resource.title())


def render_tty_line(snapshot, bar_width, unicode):
    if snapshot.resource is None:
        return ''
    label = _label(snapshot.resource)
    records = format_count(snapshot.records)
    total = snapshot.total

    if snapshot.throttled_reason is not None:
        if snapshot.throttled_reason == 'retrying':
            state = f'retrying in {int(snapshot.throttled_remaining or 0)}s'
        else:
            state = (
                f'{snapshot.throttled_reason}, retrying in '
                f'{int(snapshot.throttled_remaining or 0)}s'
            )
    elif total is None:
        rate = format_rate(snapshot.rate)
        elapsed = format_duration(snapshot.elapsed)
        return f'{label}: {records} records · {rate} · elapsed {elapsed}'
    else:
        rate = format_rate(snapshot.rate)
        remaining = max(0, total - snapshot.records)
        eta = format_eta(snapshot.rate, remaining)
        state = f'{rate} · ETA {eta}'

    if total is None:
        bar = ''
        counts = records
        percent = ''
    else:
        fraction = snapshot.records / total if total else 0.0
        bar = format_bar(fraction, bar_width, unicode) + ' '
        counts = f'{records} / {format_count(total)}'
        percent = f' ({int(fraction * 100)}%)'

    return f'{label}: {bar}{counts}{percent} · {state}'


def render_summary_line(summary):
    label = _label(summary.resource)
    records = format_count(summary.records)
    elapsed = format_duration(summary.elapsed)
    avg_rate = (
        summary.records / summary.elapsed if summary.elapsed > 0 else 0.0
    )
    return (
        f'{label}: {records} / {records} (100%) · '
        f'done in {elapsed} ({format_rate(avg_rate).replace(" rec/s", "")}'
        f' rec/s avg)'
    )


def _format_timestamp(elapsed):
    total = int(elapsed)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f'[{h:02d}:{m:02d}:{s:02d}]'


def render_log_line(snapshot):
    if snapshot.resource is None:
        return ''
    timestamp = _format_timestamp(snapshot.elapsed)
    resource = _label(snapshot.resource).lower()
    records = format_count(snapshot.records)
    total = snapshot.total

    if snapshot.throttled_reason is not None:
        state = (
            f'{snapshot.throttled_reason}, retrying in '
            f'{int(snapshot.throttled_remaining or 0)}s'
        )
    elif total is None:
        state = (
            f'{format_rate(snapshot.rate)}  '
            f'elapsed {format_duration(snapshot.elapsed)}'
        )
    else:
        remaining = max(0, total - snapshot.records)
        state = (
            f'{format_rate(snapshot.rate)}  '
            f'ETA {format_eta(snapshot.rate, remaining)}'
        )

    if total is None:
        counts = f'{records} records'
    else:
        percent = int((snapshot.records / total) * 100) if total else 0
        counts = f'{records}/{format_count(total)} ({percent}%)'

    return f'{timestamp} {resource}: {counts}  {state}'
