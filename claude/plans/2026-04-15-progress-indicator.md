# Progress Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live stderr progress indicator to `commcare-export` that shows percent/ETA (or records/rate/elapsed as fallback) for form and case exports, with an explicit throttled state on HQ rate-limit backoff.

**Architecture:** New `commcare_export.progress` module with a thread-safe `ProgressReporter` (pure state), two renderers (`tty_render` / `line_render`), and a daemon `RenderDriver` thread that periodically snapshots state and writes to stderr. `CommCareHqClient.iterate()` emits lifecycle events against a reporter it holds; a `NullProgressReporter` is the default so existing tests and mocks are unchanged. CLI adds a tri-state `--progress` / `--no-progress` flag with TTY auto-detection.

**Tech Stack:** Python 3.10+, `threading`, `logging`, `argparse`. Tests via `pytest`. Line length 79 (ruff). Quote style single.

**Spec:** `claude/specs/2026-04-15-progress-indicator-design.md`

---

## File structure

- **Create:** `commcare_export/progress.py` — all progress types.
- **Create:** `tests/test_progress.py` — unit tests for progress module.
- **Modify:** `commcare_export/commcare_hq_client.py` — accept a reporter, emit events in `iterate()`, refactor `on_wait`/`on_backoff` to closures.
- **Modify:** `commcare_export/commcare_minilinq.py` — pass reporter through where needed (thin).
- **Modify:** `commcare_export/cli.py` — `--progress`/`--no-progress` flag, reporter construction, log-handler install, teardown.
- **Modify:** `tests/test_commcare_hq_client.py` — assert events are emitted at the right points.
- **Modify:** `tests/test_cli.py` — assert flag behavior and TTY auto-detect.

**Note about spec deviation:** The spec places resource lifecycle events in `CommCareHqEnv.api_data`. That function returns a lazy `RepeatableIterator`, so a `finally` there would fire before iteration begins. The plan places `resource_started` / `resource_finished` inside `CommCareHqClient.iterate()`'s inner generator instead — same semantic, correct timing.

---

## Task 1: Define the reporter protocol and NullProgressReporter

**Files:**
- Create: `commcare_export/progress.py`
- Create: `tests/test_progress.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_progress.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_progress.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'commcare_export.progress'`.

- [ ] **Step 3: Create progress module with NullProgressReporter**

Create `commcare_export/progress.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_progress.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commcare_export/progress.py tests/test_progress.py
git commit -m "Add NullProgressReporter skeleton"
```

---

## Task 2: SlidingRate — fixed-window rate tracker

**Files:**
- Modify: `commcare_export/progress.py`
- Modify: `tests/test_progress.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_progress.py`:

```python
from commcare_export.progress import SlidingRate


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_progress.py -v`
Expected: FAIL with `ImportError: cannot import name 'SlidingRate'`.

- [ ] **Step 3: Implement SlidingRate**

Add to `commcare_export/progress.py` (after `NullProgressReporter`):

```python
from collections import deque


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
        if self._samples and now - self._samples[-1][0] < self._COALESCE_SECONDS:
            self._samples[-1] = (now, count)
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add commcare_export/progress.py tests/test_progress.py
git commit -m "Add SlidingRate fixed-window rate tracker"
```

---

## Task 3: Format helpers (duration, number, rate, eta, bar)

**Files:**
- Modify: `commcare_export/progress.py`
- Modify: `tests/test_progress.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_progress.py`:

```python
from commcare_export.progress import (
    format_bar,
    format_count,
    format_duration,
    format_eta,
    format_rate,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_progress.py -v`
Expected: FAIL on the new tests.

- [ ] **Step 3: Implement formatters**

Add to `commcare_export/progress.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commcare_export/progress.py tests/test_progress.py
git commit -m "Add progress display format helpers"
```

---

## Task 4: ProgressReporter state machine (no threading, no IO)

**Files:**
- Modify: `commcare_export/progress.py`
- Modify: `tests/test_progress.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_progress.py`:

```python
from commcare_export.progress import ProgressReporter, ProgressSnapshot


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_progress.py -v`
Expected: FAIL — `ProgressReporter` / `ProgressSnapshot` not defined.

- [ ] **Step 3: Implement ProgressReporter and ProgressSnapshot**

Add to `commcare_export/progress.py`:

```python
import threading
import time
from dataclasses import dataclass


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
            self._rate.add(0, self._started_at)
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commcare_export/progress.py tests/test_progress.py
git commit -m "Add ProgressReporter state machine"
```

---

## Task 5: TTY renderer (pure snapshot → string)

**Files:**
- Modify: `commcare_export/progress.py`
- Modify: `tests/test_progress.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_progress.py`:

```python
from commcare_export.progress import (
    ResourceSummary,
    render_tty_line,
    render_summary_line,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_progress.py -v`
Expected: FAIL — `render_tty_line` / `render_summary_line` not defined.

- [ ] **Step 3: Implement renderers**

Add to `commcare_export/progress.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commcare_export/progress.py tests/test_progress.py
git commit -m "Add TTY progress renderer"
```

---

## Task 6: Line renderer (non-TTY) with timestamps

**Files:**
- Modify: `commcare_export/progress.py`
- Modify: `tests/test_progress.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_progress.py`:

```python
from commcare_export.progress import render_log_line


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
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: FAIL on the four new tests.

- [ ] **Step 3: Implement log-line renderer**

Add to `commcare_export/progress.py`:

```python
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
    resource = snapshot.resource
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commcare_export/progress.py tests/test_progress.py
git commit -m "Add non-TTY line progress renderer"
```

---

## Task 7: RenderDriver (daemon thread, writes to a stream)

**Files:**
- Modify: `commcare_export/progress.py`
- Modify: `tests/test_progress.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_progress.py`:

```python
import io
import threading

from commcare_export.progress import RenderDriver


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
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: FAIL — `RenderDriver` not defined.

- [ ] **Step 3: Implement RenderDriver**

Add to `commcare_export/progress.py`:

```python
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
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
            self._thread = None
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commcare_export/progress.py tests/test_progress.py
git commit -m "Add RenderDriver with TTY and line-mode rendering"
```

---

## Task 8: Connect RenderDriver to ProgressReporter via start/stop

**Files:**
- Modify: `commcare_export/progress.py`
- Modify: `tests/test_progress.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_progress.py`:

```python
import sys

from commcare_export.progress import build_reporter


def test_build_reporter_off_returns_null():
    reporter = build_reporter(mode='off')
    assert isinstance(reporter, NullProgressReporter)


def test_build_reporter_on_tty_returns_live(monkeypatch):
    stream = io.StringIO()
    reporter = build_reporter(
        mode='on', stream=stream, is_tty=True
    )
    assert isinstance(reporter, ProgressReporter)
    reporter.start()
    reporter.stop()


def test_build_reporter_auto_on_tty(monkeypatch):
    stream = io.StringIO()
    reporter = build_reporter(
        mode='auto', stream=stream, is_tty=True
    )
    assert isinstance(reporter, ProgressReporter)


def test_build_reporter_auto_off_tty():
    stream = io.StringIO()
    reporter = build_reporter(
        mode='auto', stream=stream, is_tty=False
    )
    assert isinstance(reporter, NullProgressReporter)


def test_reporter_start_stop_drives_renders():
    stream = io.StringIO()
    reporter = build_reporter(
        mode='on', stream=stream, is_tty=True, interval=0.02
    )
    reporter.start()
    try:
        reporter.resource_started('form')
        reporter.batch_received(fetched=10, total=100)
        for _ in range(10):
            reporter.record_yielded()
        import time
        time.sleep(0.1)
    finally:
        reporter.stop()
    assert 'Forms:' in stream.getvalue()
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: FAIL — `build_reporter` not defined and `ProgressReporter.start/stop` are no-ops.

- [ ] **Step 3: Wire reporter to driver via start/stop**

Modify `ProgressReporter` in `commcare_export/progress.py`:

Replace the existing `start` / `stop` placeholders with:

```python
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
```

Add the `build_reporter` factory at the bottom of `commcare_export/progress.py`:

```python
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
```

Add `import sys` at the top of the file if not already present.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commcare_export/progress.py tests/test_progress.py
git commit -m "Add build_reporter factory and driver attachment"
```

---

## Task 9: Wire CommCareHqClient.iterate() to emit events

**Files:**
- Modify: `commcare_export/commcare_hq_client.py`
- Modify: `tests/test_commcare_hq_client.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_commcare_hq_client.py` (inside `TestCommCareHqClient`):

```python
    def test_iterate_emits_progress_events(self):
        from commcare_export.progress import ProgressReporter

        reporter = ProgressReporter()
        client = CommCareHqClient(
            '/fake/commcare-hq/url',
            'fake-project',
            None,
            None,
            progress_reporter=reporter,
        )
        client.session = FakeSession()
        paginator = SimplePaginator('fake')
        paginator.init()
        checkpoint_manager = CheckpointManagerWithDetails(
            None, None, PaginationMode.date_indexed
        )
        results = list(
            client.iterate(
                'form',
                paginator,
                checkpoint_manager=checkpoint_manager,
            )
        )
        assert len(results) == 2
        snap = reporter.snapshot()
        assert snap.resource is None
        assert snap.last_summary is not None
        assert snap.last_summary.resource == 'form'
        assert snap.last_summary.records == 2
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_commcare_hq_client.py::TestCommCareHqClient::test_iterate_emits_progress_events -v`
Expected: FAIL — `CommCareHqClient.__init__` does not accept `progress_reporter`.

- [ ] **Step 3: Modify `CommCareHqClient` to accept and emit events**

Modify `commcare_export/commcare_hq_client.py`:

Add import near the top:

```python
from commcare_export.progress import NullProgressReporter
```

Change `CommCareHqClient.__init__` to accept the reporter:

```python
    def __init__(
        self,
        url,
        project,
        username,
        password,
        auth_mode=AUTH_MODE_PASSWORD,
        version=LATEST_KNOWN_VERSION,
        progress_reporter=None,
    ):
        self.version = version
        self.url = url
        self.project = project
        self.__auth = self._get_auth(username, password, auth_mode)
        self.__session = None
        self.progress_reporter = (
            progress_reporter if progress_reporter is not None
            else NullProgressReporter()
        )
```

Modify the inner `iterate_resource` generator in `iterate()` to bracket resource lifecycle and emit per-batch / per-record events. Replace the existing `def iterate_resource(...)` body (from after the `def` line through the end of the outer `while more_to_fetch:` loop) with:

```python
        def iterate_resource(resource=resource, params=params):
            reporter = self.progress_reporter
            reporter.resource_started(resource)
            try:
                more_to_fetch = True
                last_batch_ids = set()
                total_count = unknown_count
                fetched = 0
                repeat_counter = 0
                last_params = None

                while more_to_fetch:
                    if params == last_params:
                        repeat_counter += 1
                    else:
                        repeat_counter = 0
                    if repeat_counter >= RESOURCE_REPEAT_LIMIT:
                        raise ResourceRepeatException(
                            f"Requested resource '{resource}' "
                            f"{repeat_counter} times with same parameters"
                        )

                    batch = self.get(resource, params)
                    last_params = copy.copy(params)
                    batch_meta = batch['meta']
                    if total_count == unknown_count or fetched >= total_count:
                        if batch_meta.get('total_count'):
                            total_count = int(batch_meta['total_count'])
                        else:
                            total_count = unknown_count
                        fetched = 0

                    batch_objects = batch['objects']
                    fetched += len(batch_objects)
                    reporter.batch_received(
                        fetched=len(batch_objects),
                        total=batch_meta.get('total_count'),
                    )
                    logger.debug('Received %s of %s', fetched, total_count)
                    if not batch_objects:
                        more_to_fetch = False
                    else:
                        got_new_data = False
                        for obj in batch_objects:
                            if obj['id'] not in last_batch_ids:
                                reporter.record_yielded()
                                yield obj
                                got_new_data = True

                        if batch_meta.get('next'):
                            last_batch_ids = {
                                obj['id'] for obj in batch_objects
                            }
                            params = paginator.next_page_params_from_batch(
                                batch
                            )
                            if not params:
                                more_to_fetch = False
                        else:
                            more_to_fetch = False

                        limit = batch_meta.get('limit')
                        if more_to_fetch:
                            repeated_last_page_of_non_counting_resource = (
                                not got_new_data
                                and total_count == unknown_count
                                and (limit and len(batch_objects) < limit)
                            )
                            more_to_fetch = (
                                not repeated_last_page_of_non_counting_resource
                            )

                        paginator.set_checkpoint(
                            checkpoint_manager,
                            batch,
                            not more_to_fetch,
                        )
            finally:
                reporter.resource_finished()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_commcare_hq_client.py -v`
Expected: PASS (all existing tests + the new one).

- [ ] **Step 5: Commit**

```bash
git add commcare_export/commcare_hq_client.py tests/test_commcare_hq_client.py
git commit -m "Emit progress events from CommCareHqClient.iterate()"
```

---

## Task 10: Refactor on_wait / on_backoff to closures that notify the reporter

**Files:**
- Modify: `commcare_export/commcare_hq_client.py`
- Modify: `tests/test_commcare_hq_client.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_commcare_hq_client.py` (inside `TestCommCareHqClient`):

```python
    def test_on_wait_notifies_reporter_throttled(self):
        from commcare_export.progress import ProgressReporter

        reporter = ProgressReporter()
        client = CommCareHqClient(
            '/fake/commcare-hq/url',
            'fake-project',
            None,
            None,
            progress_reporter=reporter,
        )
        reporter.resource_started('form')
        client._notify_wait({'wait': 12.5})
        snap = reporter.snapshot()
        assert snap.throttled_reason == 'throttled'
        assert snap.throttled_remaining is not None
        assert snap.throttled_remaining >= 12.0

    def test_on_backoff_notifies_reporter_retrying(self):
        from commcare_export.progress import ProgressReporter

        reporter = ProgressReporter()
        client = CommCareHqClient(
            '/fake/commcare-hq/url',
            'fake-project',
            None,
            None,
            progress_reporter=reporter,
        )
        reporter.resource_started('form')
        client._notify_backoff(
            {'tries': 2, 'elapsed': 1.5, 'wait': 4.0}
        )
        snap = reporter.snapshot()
        assert snap.throttled_reason == 'retrying'
        assert snap.throttled_remaining is not None
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_commcare_hq_client.py::TestCommCareHqClient -v -k notifies`
Expected: FAIL — `_notify_wait` / `_notify_backoff` not defined.

- [ ] **Step 3: Refactor to instance methods used by the decorators**

Modify `commcare_export/commcare_hq_client.py`:

Replace the three module-level functions `on_wait`, `on_backoff`, `on_giveup` and their helper `_log_backoff` with methods on `CommCareHqClient`. Keep `is_client_error` at module level (it is pure). Remove:

```python
def on_wait(details):
    time_to_wait = details["wait"]
    logger.warning(f"Rate limit reached. Waiting for {time_to_wait} seconds.")


def on_backoff(details):
    _log_backoff(details, 'Waiting for retry.')


def on_giveup(details):
    _log_backoff(details, 'Giving up.')


def _log_backoff(details, action_message):
    details['__suffix'] = action_message
    logger.warning(
        "Request failed after {tries} attempts ({elapsed:.1f}s). {__suffix}"
        .format(**details)
    )
```

Add these methods on `CommCareHqClient`:

```python
    def _notify_wait(self, details):
        time_to_wait = details['wait']
        logger.warning(
            f'Rate limit reached. Waiting for {time_to_wait} seconds.'
        )
        self.progress_reporter.throttled(
            wait_seconds=float(time_to_wait), reason='throttled'
        )

    def _notify_backoff(self, details):
        self._log_backoff(details, 'Waiting for retry.')
        wait = float(details.get('wait') or 0.0)
        self.progress_reporter.throttled(
            wait_seconds=wait, reason='retrying'
        )

    def _notify_giveup(self, details):
        self._log_backoff(details, 'Giving up.')

    @staticmethod
    def _log_backoff(details, action_message):
        details = dict(details)
        details['__suffix'] = action_message
        logger.warning(
            'Request failed after {tries} attempts ({elapsed:.1f}s). '
            '{__suffix}'.format(**details)
        )
```

In `CommCareHqClient.get()`, update the backoff decorators to refer to these bound methods:

```python
        @backoff.on_predicate(
            backoff.runtime,
            predicate=lambda r: r.status_code == 429,
            value=lambda r: ceil(float(r.headers.get("Retry-After", 1.0))),
            jitter=None,
            on_backoff=self._notify_wait,
        )
        @backoff.on_exception(
            backoff.expo,
            requests.exceptions.RequestException,
            max_time=300,
            giveup=is_client_error,
            on_backoff=self._notify_backoff,
            on_giveup=self._notify_giveup,
        )
        def _get(resource, params=None):
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_commcare_hq_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commcare_export/commcare_hq_client.py tests/test_commcare_hq_client.py
git commit -m "Notify reporter from rate-limit and backoff handlers"
```

---

## Task 11: Logging handler that clears the bar around log records

**Files:**
- Modify: `commcare_export/progress.py`
- Modify: `tests/test_progress.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_progress.py`:

```python
import logging

from commcare_export.progress import ProgressAwareStreamHandler


def test_progress_aware_handler_clears_line_before_emitting():
    stream = io.StringIO()
    reporter = _make_reporter()
    reporter.resource_started('form')
    handler = ProgressAwareStreamHandler(stream=stream, reporter=reporter)
    handler.setFormatter(logging.Formatter('%(message)s'))
    record = logging.LogRecord(
        'x', logging.INFO, '', 0, 'hello', None, None
    )
    handler.emit(record)
    output = stream.getvalue()
    assert output.startswith('\r\x1b[K')
    assert 'hello' in output
    assert output.endswith('hello\n')


def test_progress_aware_handler_skips_clear_when_no_driver():
    stream = io.StringIO()
    reporter = NullProgressReporter()
    handler = ProgressAwareStreamHandler(stream=stream, reporter=reporter)
    handler.setFormatter(logging.Formatter('%(message)s'))
    record = logging.LogRecord(
        'x', logging.INFO, '', 0, 'world', None, None
    )
    handler.emit(record)
    assert stream.getvalue() == 'world\n'
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: FAIL — `ProgressAwareStreamHandler` not defined.

- [ ] **Step 3: Implement the handler**

Add to `commcare_export/progress.py`:

```python
import logging


class ProgressAwareStreamHandler(logging.StreamHandler):
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
            self.stream.write(_CLEAR_LINE)
        super().emit(record)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_progress.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commcare_export/progress.py tests/test_progress.py
git commit -m "Add ProgressAwareStreamHandler for clean log output"
```

---

## Task 12: Add --progress / --no-progress CLI flags and wire reporter

**Files:**
- Modify: `commcare_export/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
import sys

import pytest

from commcare_export.cli import CLI_ARGS, _progress_mode_from_args
from commcare_export.progress import (
    NullProgressReporter,
    ProgressReporter,
    build_reporter,
)


class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_progress_mode_defaults_to_auto():
    args = _Args(progress=None, no_progress=False)
    assert _progress_mode_from_args(args) == 'auto'


def test_progress_mode_on_when_progress_flag_set():
    args = _Args(progress=True, no_progress=False)
    assert _progress_mode_from_args(args) == 'on'


def test_progress_mode_off_when_no_progress_flag_set():
    args = _Args(progress=False, no_progress=True)
    assert _progress_mode_from_args(args) == 'off'


def test_build_reporter_off_returns_null_reporter():
    assert isinstance(build_reporter(mode='off'), NullProgressReporter)
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_cli.py -v -k progress`
Expected: FAIL — `_progress_mode_from_args` not defined.

- [ ] **Step 3: Add flags and helper**

Modify `commcare_export/cli.py`:

Add these imports near the top (alphabetical with existing):

```python
from commcare_export.progress import (
    ProgressAwareStreamHandler,
    build_reporter,
)
```

Add the new arguments at the end of `CLI_ARGS` (before the closing `]`):

```python
    Argument(
        'progress',
        default=None,
        action='store_true',
        help='Force-enable the live progress indicator on stderr.',
    ),
    Argument(
        'no-progress',
        default=False,
        action='store_true',
        help='Suppress the live progress indicator.',
    ),
```

Add the mode helper above `def main(argv):`:

```python
def _progress_mode_from_args(args):
    if args.no_progress:
        return 'off'
    if args.progress:
        return 'on'
    return 'auto'
```

Modify `set_up_logging` so the console `StreamHandler` is the progress-aware one when a reporter is provided. Change the function signature and body:

```python
def set_up_logging(args, reporter=None):
    if reporter is not None:
        stream_handler = ProgressAwareStreamHandler(
            stream=sys.stderr, reporter=reporter
        )
    else:
        stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter('%(message)s'))
    handlers = [stream_handler]
    if not args.no_logfile:
        success, log_file, error, file_handler = set_up_file_logging(
            args.log_dir
        )
        if success:
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
                )
            )
            handlers.append(file_handler)
            print(f'Writing logs to {log_file}')
        else:
            print(
                f'Warning: Unable to write to log file {log_file}: {error}'
            )
            print('Logging to console only.')

    log_level = logging.DEBUG if args.verbose else logging.WARN
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    for handler in handlers:
        root_logger.addHandler(handler)
```

Modify `main(argv)` to build the reporter before logging, pass it in, and tear it down in a `finally`:

```python
def main(argv):
    parser = argparse.ArgumentParser(
        'commcare-export', 'Output a customized export of CommCareHQ data.'
    )
    for arg in CLI_ARGS:
        arg.add_to_parser(parser)

    args = parser.parse_args(argv)

    if args.output_format and args.output:
        errors = []
        errors.extend(validate_output_filename(args.output_format, args.output))
        if errors:
            raise Exception(
                f'Could not proceed. Following issues were found: '
                f'{", ".join(errors)}.'
            )

    reporter = build_reporter(mode=_progress_mode_from_args(args))
    set_up_logging(args, reporter=reporter)

    logging.getLogger('alembic').setLevel(logging.WARN)
    logging.getLogger('backoff').setLevel(logging.FATAL)
    logging.getLogger('urllib3').setLevel(logging.WARN)

    if args.version:
        print(f'commcare-export version {__version__}')
        sys.exit(0)

    if not args.project:
        error_msg = 'commcare-export: error: argument --project is required'
        logger.error(error_msg)
        sys.exit(1)

    print('Running export...')
    reporter.start()
    try:
        exit_code = main_with_args(args, reporter=reporter)
        if exit_code > 0:
            print('Error occurred! See log file for error.')
        sys.exit(exit_code)
    except Exception:
        print('Error occurred! See log file for error.')
        raise
    finally:
        reporter.stop()
        print('Export finished!')
```

Modify `main_with_args` to accept and wire the reporter into `_get_api_client` / `CommCareHqClient`:

Change the signature:

```python
def main_with_args(args, reporter=None):
    if reporter is None:
        from commcare_export.progress import NullProgressReporter
        reporter = NullProgressReporter()
    logger.info(f'CommCare Export Version {__version__}')
    ...
```

Change `_get_api_client` to accept and pass the reporter:

```python
def _get_api_client(args, commcarehq_base_url, reporter):
    return CommCareHqClient(
        url=commcarehq_base_url,
        project=args.project,
        username=args.username,
        password=args.password,
        auth_mode=args.auth_mode,
        version=args.api_version,
        progress_reporter=reporter,
    )
```

In `main_with_args`, update the call site:

```python
    api_client = _get_api_client(args, commcarehq_base_url, reporter)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_cli.py tests/test_progress.py tests/test_commcare_hq_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commcare_export/cli.py tests/test_cli.py
git commit -m "Add --progress / --no-progress flags and wire reporter"
```

---

## Task 13: Full-stack test — iterate produces redraw output on stderr

**Files:**
- Modify: `tests/test_progress.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_progress.py`:

```python
import time

from commcare_export.commcare_hq_client import CommCareHqClient
from commcare_export.commcare_minilinq import (
    PaginationMode,
    SimplePaginator,
)
from commcare_export.checkpoint import CheckpointManagerWithDetails


class _ScriptedSession:
    def __init__(self):
        self._calls = 0

    def get(self, url, params=None, auth=None, timeout=None):
        import requests
        import simplejson
        self._calls += 1
        if self._calls == 1:
            body = {
                'meta': {
                    'next': '?offset=1', 'offset': 0, 'limit': 2,
                    'total_count': 4,
                },
                'objects': [
                    {'id': 1, 'foo': 'a'},
                    {'id': 2, 'foo': 'b'},
                ],
            }
        else:
            body = {
                'meta': {
                    'next': None, 'offset': 2, 'limit': 2, 'total_count': 4,
                },
                'objects': [
                    {'id': 3, 'foo': 'c'},
                    {'id': 4, 'foo': 'd'},
                ],
            }
        resp = requests.Response()
        resp._content = simplejson.dumps(body).encode('utf-8')
        resp.status_code = 200
        return resp


def test_full_stack_progress_bar_rendered_to_stream():
    stream = io.StringIO()
    reporter = build_reporter(
        mode='on', stream=stream, is_tty=True, interval=0.02
    )
    client = CommCareHqClient(
        '/fake', 'p', None, None, progress_reporter=reporter
    )
    client.session = _ScriptedSession()
    paginator = SimplePaginator('fake', page_size=2)
    paginator.init()
    cm = CheckpointManagerWithDetails(None, None, PaginationMode.date_indexed)

    reporter.start()
    try:
        results = list(
            client.iterate('form', paginator, checkpoint_manager=cm)
        )
        time.sleep(0.1)
    finally:
        reporter.stop()

    output = stream.getvalue()
    assert len(results) == 4
    assert 'Forms:' in output
    assert '4 / 4 (100%)' in output
    assert '\r\x1b[K' in output
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_progress.py::test_full_stack_progress_bar_rendered_to_stream -v`
Expected: PASS.

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest -m "not dbtest"`
Expected: PASS (all tests, no regressions).

- [ ] **Step 4: Lint and format**

Run:
```bash
uv run ruff check commcare_export/progress.py commcare_export/commcare_hq_client.py commcare_export/cli.py tests/test_progress.py
uv run ruff format commcare_export/progress.py commcare_export/cli.py tests/test_progress.py
uv run mypy commcare_export/ tests/
```
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add tests/test_progress.py
git commit -m "Add full-stack progress rendering integration test"
```

---

## Task 14: Manual verification against a staging HQ project

- [ ] **Step 1: Run against staging**

```bash
uv run commcare-export \
    --query examples/demo-registration.xlsx \
    --project <staging-project> \
    --commcare-hq <staging-url> \
    --username <user> \
    --password <apikey> \
    --auth-mode apikey \
    --output-format json \
    --output /tmp/staging.json
```

Confirm by eye:
- A progress bar redraws on stderr while forms stream.
- Percent and ETA update; rate stabilizes.
- Resource switching prints a `done in` summary line before the next resource's bar appears.
- `--no-progress` suppresses output.
- `2>/tmp/err.log` (non-TTY) produces timestamped lines every 10 s, no carriage-return garbage.

- [ ] **Step 2: Capture findings**

If manual verification surfaces issues, file a follow-up task; otherwise note completion.

---

## Notes for the executor

- Run tests only with `-m "not dbtest"` — the SQL writer tests rely on a database.
- Keep line length ≤ 79 (ruff). Single-quote strings.
- Do not "improve" unrelated code; the spec forbids scope creep.
- `CommCareHqClient`'s existing behavior (for non-progress callers) must remain byte-identical. All existing tests continue to pass unchanged.
- Format/reflow commits separately from logic commits per `CLAUDE.md`.

## Future work (not in scope)

- HQ-side `_count=first` flag so pagination counts only the first page. Once shipped, DET passes the flag on page 1 and omits it thereafter. DET already tolerates `total_count: null` on later pages after this plan — the flag ships cleanly.
