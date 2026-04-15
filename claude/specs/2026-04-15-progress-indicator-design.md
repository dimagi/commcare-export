# Progress Indicator Design

**Status:** Design — approved for planning
**Date:** 2026-04-15
**Scope:** commcare-export CLI, with a future-work note for CommCare HQ.

## Problem

`commcare-export` runs can take hours, especially for form and case exports
on large projects. The CLI currently writes only a handful of bookend
messages (`Running export...`, `Export finished!`) and routes everything
else through the logger (console default: `WARN`). From a user's
perspective, a multi-hour export looks like a hung process. There is no way
to answer "am I halfway yet?" or "is it still making progress?" without
enabling `--verbose` and reading debug output.

## Goal

Ship a live progress indicator on **stderr** that shows, for form and case
exports:

1. Percent complete and ETA when a total record count is available.
2. Records processed, rate, and elapsed time as a fallback when no total is
   known.
3. An explicit state when the client is waiting on HQ (rate-limit / retry
   backoff).

The same mechanism extends naturally to the `user` and `location`
resources, but those are out of primary focus.

## Non-goals

- Per-output-table progress (one iteration yields records for many tables).
- Instrumenting `LocationInfoProvider` enrichment lookups.
- A machine-readable progress event stream (e.g. JSON).
- Changes to CommCare HQ in this phase. HQ changes are captured under
  [Future work](#future-work).

## User experience

### Default (TTY, total count known)

```
Forms: [████████░░░░░░░░░░░░] 48,231 / 120,000 (40%) · 63 rec/s · ETA 19m
```

### Total count unknown (fallback)

```
Forms: 48,231 records · 63 rec/s · elapsed 12m
```

Used when the first batch has not yet arrived, or when the API did not
return `meta.total_count` (e.g. `user` / `location` endpoints).

### Throttled / backing off

```
Forms: [████████░░░░░░░░░░░░] 48,231 / 120,000 (40%) · throttled, retrying in 17s
```

Triggered by HTTP 429 `Retry-After`. Non-429 backoff retries use the same
treatment, labeled `retrying` instead of `throttled`.

### Transitioning between resources

When a resource completes, a final summary line is printed and a fresh bar
starts for the next resource:

```
Forms:  120,000 / 120,000 (100%) · done in 22m (90 rec/s avg)
Cases: [███░░░░░░░░░░░░░░░░░] 12,458 / 80,000 (16%) · 55 rec/s · ETA 20m
```

### Non-TTY fallback

When stderr is piped or redirected, or the user passes `--progress` to
force output to a non-TTY, a timestamped line is emitted every 10 seconds.
No carriage-return redraws:

```
[00:12:34] forms: 48,231/120,000 (40%)  63 rec/s  ETA 19m
[00:12:44] forms: 48,857/120,000 (40%)  62 rec/s  ETA 19m
```

A line is emitted at each tick even if nothing changed, so stalls are
distinguishable from a hung process.

### Visual rules

- Bar characters default to Unicode blocks (`█` / `░`); fall back to ASCII
  (`#` / `-`) when the locale is not UTF-8.
- Column widths for bar, percent, rate, and ETA are fixed so the line does
  not jitter between frames.
- Progress is written **only** to stderr. stdout (used by the markdown /
  JSON writers) is untouched. The log file never receives progress lines.
- Existing bookend `print(...)` calls stay on stdout as they are today.

## Architecture

Four small units, each with one responsibility:

```
┌──────────────────────────────────────────────────────────────┐
│ cli.py                                                       │
│   builds ProgressReporter (TTY-detect, --progress flag)      │
│   passes it to CommCareHqEnv                                 │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ CommCareHqClient.iterate()                                   │
│   emits progress events:                                     │
│     resource_started(name)                                   │
│     batch_received(fetched, total_count_or_None)             │
│     record_yielded()   ← once per object yielded             │
│     throttled(wait_seconds)                                  │
│     resource_finished()                                      │
└──────────────────────────┬───────────────────────────────────┘
                           │  (event objects)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ ProgressReporter (new module: progress.py)                   │
│   owns the state machine & render loop                       │
│   holds: current_resource, records, total, start_time,       │
│          rate_window, throttled_until                        │
│   decides when to redraw (~10 Hz on TTY, every 10 s otherwise)│
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ ProgressRenderer (TTY)   |   LineRenderer (non-TTY)          │
│   pure output — takes a state snapshot, writes to stderr     │
└──────────────────────────────────────────────────────────────┘
```

### Unit responsibilities

**`CommCareHqClient.iterate()`** — emits events against a reporter object
it holds. Knows nothing about rendering. If no reporter is configured, it
holds a `NullProgressReporter` whose methods are no-ops. This keeps
`MockCommCareHqClient` and existing tests unchanged.

**`ProgressReporter`** — pure state + timing. Computes the smoothed rate
as a fixed-window sliding average over the last 30 seconds: a deque of
`(monotonic_time, cumulative_records)` samples is updated on each
`record_yielded` (at most one sample per ~100 ms to bound deque size), old
samples are evicted on read, and rate is `(latest_count − oldest_count) /
(latest_t − oldest_t)`. Computes ETA as `(total − records) / rate`. Owns
the renderer and the render thread. Thread-safe: events mutate state
under a lock; the render thread reads a snapshot under the same lock.

**Renderers (`ProgressRenderer`, `LineRenderer`)** — dumb output. Take a
state dict, build the display string, write to stderr. `ProgressRenderer`
uses `\r\033[K` (CR + clear-to-EOL) to redraw in place. `LineRenderer`
writes newline-terminated lines at a slower cadence.

**Render driver** — a daemon `threading.Thread` ticking at 10 Hz on TTY or
0.1 Hz (every 10 s) off TTY. Driven by a timer rather than by events so
redraw cadence is independent of API batch size. Stopped via a
`threading.Event` on teardown.

### Integration points

1. **`commcare_hq_client.py::iterate`** — inside the existing
   `while more_to_fetch:` loop, after `batch = self.get(...)`, call
   `reporter.batch_received(len(batch['objects']), batch_meta.get('total_count'))`.
   In the `for obj in batch_objects:` yield loop, call
   `reporter.record_yielded()` before `yield obj`.

2. **`commcare_hq_client.py::on_wait` / `on_backoff`** — currently
   module-level functions. Refactor to closures built inside
   `CommCareHqClient.get()` (or `iterate()`) that close over
   `self.reporter`, so they can call `reporter.throttled(time_to_wait)`
   (label `"throttled"` for 429, `"retrying"` for other retries) in
   addition to their existing log lines.

3. **`commcare_minilinq.py::CommCareHqEnv.api_data`** — wrap the iterate
   call with `reporter.resource_started(resource)` before, and
   `reporter.resource_finished()` in a `finally`. This guarantees clean
   lifecycle boundaries between sequential resources (form → case → user →
   location).

4. **`cli.py::main_with_args`** — construct the reporter, thread it through
   `CommCareHqClient` and `CommCareHqEnv`. Stop the reporter in a `finally`
   so tracebacks and aborts do not mangle the terminal.

### Logging interaction

Python's `logging.StreamHandler` writes to stderr, which conflicts with the
CR-redrawn bar. A small `ProgressAwareStreamHandler` subclass acquires the
reporter's lock before emitting, writes `\r\033[K` to clear the bar, emits
the record, then releases the lock. The next render-thread tick redraws
the bar. Installed in `cli.py::set_up_logging` only when the reporter is
active.

### Rate & ETA math

- Rate: fixed-window sliding average over the last 30 s (see
  `ProgressReporter` above). Smooth enough that a per-batch spike does
  not jitter the display, responsive enough to show a real slowdown
  within ~10 s.
- ETA: `(total − records) / rate`. Formatted `Nm` under an hour, `NhMm`
  above. When `rate == 0` (warm-up, throttling, fewer than 2 samples),
  shown as `--`.
- Elapsed (fallback mode only): wall time since the current
  `resource_started`.

## CLI surface

One tri-state flag (mutually-exclusive group):

```
  --progress            Force-enable the progress indicator.
  --no-progress         Suppress the progress indicator.
  (neither)             Auto: on when stderr is a TTY, off otherwise.
```

Interactions with existing flags:

- `--verbose` (console log level `DEBUG`): progress stays on. Log lines
  print above the bar via the clear-and-redraw dance.
- `--dump-query`: no progress (process exits before iteration).
- `--output-format=markdown`: markdown goes to stdout, progress to stderr,
  no collision.

## Throttled-state rules

- On 429 with `Retry-After`, `on_wait` calls
  `reporter.throttled(wait_seconds)`. The bar freezes the rate and shows
  `throttled, retrying in Ns`, counting down each tick.
- On non-429 retries (`on_backoff`), same treatment, label `retrying`.
- On the next successful batch, throttled state clears automatically.

## Shutdown & error paths

- Normal completion: print a final "100%, done in Xm" summary for the
  active resource, stop the render thread, clear the bar, return.
- `KeyboardInterrupt`: clear the bar, let the existing "Export aborted"
  log through, join the render thread.
- Uncaught exception: stop the render thread in a `finally` in
  `main_with_args` so the traceback renders cleanly.

## Data model

`ProgressReporter` state (per active resource):

| Field              | Type                 | Notes                              |
|--------------------|----------------------|------------------------------------|
| `resource`         | `str \| None`        | `"form"`, `"case"`, ...            |
| `records`          | `int`                | records yielded so far             |
| `total`            | `int \| None`        | from first batch's `total_count`   |
| `started_at`       | `float` (monotonic)  | `resource_started()` timestamp     |
| `rate_samples`     | deque of (t, count)  | 30 s sliding window                |
| `throttled_until`  | `float \| None`      | monotonic deadline, or `None`      |
| `throttled_reason` | `str \| None`        | `"throttled"` / `"retrying"`       |

All access guarded by a single `threading.Lock`.

## Built-in queries (users, locations)

The reporter is resource-agnostic. `users_query` and `locations_query`
emit the same `resource_started` / `resource_finished` events via
`CommCareHqEnv`. When the endpoint does not return `total_count` (as is
likely for `user` / `location`), the reporter automatically falls back to
records+rate+elapsed display for that resource. No configuration changes
required.

## Testing strategy

Unit tests (`tests/test_progress.py`):

- `ProgressReporter` state transitions: `resource_started`,
  `batch_received` (with and without total), `record_yielded`,
  `throttled`, `resource_finished`.
- Rate EWMA math: fixed record/time sequences produce the expected
  smoothed rate.
- ETA formatting: minutes, hours, zero-rate `--` case.
- Renderer output strings: fixed state snapshots map to exact expected
  lines (both TTY and line renderers).
- `NullProgressReporter` is a silent no-op for every method.

Integration tests (`tests/test_commcare_hq_client.py`, extend existing):

- `iterate()` calls `record_yielded` exactly once per yielded object.
- `iterate()` calls `batch_received` once per API batch with the expected
  `total_count`.
- `on_wait` / `on_backoff` hooks call `throttled()` with the expected
  arguments.

CLI test (`tests/test_cli.py`):

- `--progress` / `--no-progress` / default auto-detect each resolve to
  the expected reporter type (real vs. null).
- Log handler installation: a log record emitted during progress prints
  the clear-and-redraw sequence to stderr.

No HQ-side tests in this phase.

## Implementation plan (high-level)

1. `progress.py` — `ProgressReporter`, `NullProgressReporter`, both
   renderers, render thread, rate/ETA math. Unit tests.
2. Wire `CommCareHqClient.iterate()` to emit events; null-reporter by
   default. Integration tests.
3. Wire `CommCareHqEnv.api_data` to manage resource lifecycle events.
4. `cli.py` — add flags, auto-detection, reporter construction, logging
   handler integration, teardown in `finally`.
5. Manual verification against a staging HQ project with ≥10 k forms.

## Future work

### `_count=first` on the HQ API

Currently forms/cases run an ES count on every paginated page (Tastypie's
default paginator). Once DET has a progress indicator, the per-page count
is wasted work on the HQ side. Planned follow-up HQ change:

- Add a `_count=first` (or equivalent) query-string option to
  `XFormInstanceResource` / `CommCareCaseResource`.
- When set, the paginator counts on the first page only; subsequent pages
  return `meta.total_count: null`.
- DET passes the flag on the first batch and omits it thereafter.

DET must already tolerate `total_count: null` on pages 2+ for this to be
safe; that tolerance is included in the current iterate-loop changes.
