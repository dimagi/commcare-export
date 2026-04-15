"""
Live stderr progress indicator for commcare-export.

See ``claude/specs/2026-04-15-progress-indicator-design.md``.
"""

import logging
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import TextIO


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
        self._samples: deque[tuple[float, int]] = deque()

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

    def attach_driver(self, driver):
        self._driver = driver

    def start(self):
        driver = getattr(self, '_driver', None)
        if driver is not None:
            driver.start()

    def stop(self):
        driver = getattr(self, '_driver', None)
        if driver is not None:
            driver.stop()


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


_CLEAR_LINE = '\r\x1b[K'


class RenderDriver:
    """
    Periodically snapshots a reporter and writes to a stream.

    On a TTY: in-place redraw using CR + clear-to-EOL, ~10 Hz.
    Off TTY: newline-terminated line every ``interval`` seconds.

    Runs in a daemon thread. ``start`` / ``stop`` are idempotent.
    """

    def __init__(
        self,
        reporter,
        stream,
        is_tty,
        interval,
        bar_width=20,
        unicode=True,
    ):
        self._reporter = reporter
        self._stream = stream
        self._is_tty = is_tty
        self._interval = interval
        self._bar_width = bar_width
        self._unicode = unicode
        self._stop_event = threading.Event()
        self._thread = None
        self._last_summary = None

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name='progress-render', daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._final_clear()

    def _run(self):
        while not self._stop_event.wait(self._interval):
            self.render_once()

    def render_once(self):
        snap = self._reporter.snapshot()
        self._emit_new_summary(snap)
        if self._is_tty:
            line = render_tty_line(
                snap, bar_width=self._bar_width, unicode=self._unicode
            )
            if line:
                self._stream.write(_CLEAR_LINE + line)
                self._stream.flush()
        else:
            line = render_log_line(snap)
            if line:
                self._stream.write(line + '\n')
                self._stream.flush()

    def _emit_new_summary(self, snapshot):
        summary = snapshot.last_summary
        if summary is None or summary is self._last_summary:
            return
        self._last_summary = summary
        if self._is_tty:
            self._stream.write(_CLEAR_LINE)
        self._stream.write(render_summary_line(summary) + '\n')
        self._stream.flush()

    def _final_clear(self):
        if self._is_tty:
            self._stream.write(_CLEAR_LINE)
            self._stream.flush()


class ProgressAwareStreamHandler(logging.StreamHandler[TextIO]):
    """
    A StreamHandler that clears any in-flight progress line on its
    reporter's stream before emitting a log record, so log output and
    the progress bar do not overwrite each other.
    """

    def __init__(self, stream, reporter):
        super().__init__(stream)
        self._reporter = reporter

    def emit(self, record):
        if isinstance(self._reporter, ProgressReporter):
            with self._reporter._lock:
                self.stream.write(_CLEAR_LINE)
                super().emit(record)
        else:
            super().emit(record)


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


def build_reporter(
    mode,
    stream=None,
    is_tty=None,
    interval=None,
    bar_width=20,
):
    if stream is None:
        stream = sys.stderr
    if is_tty is None:
        is_tty = stream.isatty()
    if interval is None:
        interval = 0.1 if is_tty else 10.0

    if mode == 'off':
        return NullProgressReporter()
    if mode == 'auto' and not is_tty:
        return NullProgressReporter()

    unicode = _stream_supports_unicode(stream)
    reporter = ProgressReporter()
    driver = RenderDriver(
        reporter,
        stream=stream,
        is_tty=is_tty,
        interval=interval,
        bar_width=bar_width,
        unicode=unicode,
    )
    reporter.attach_driver(driver)
    return reporter


def _stream_supports_unicode(stream):
    encoding = getattr(stream, 'encoding', None) or ''
    return 'utf' in encoding.lower()
