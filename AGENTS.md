# AGENTS.md

Guidance for agents working in this repository.

## What this repo is

A Home Assistant custom integration (HACS-installable, domain `gp_availability`). It polls a practice's public online-booking availability (HotDoc or EasyVisit) and notifies when a watched doctor has a slot before a cutoff. Everything lives in `custom_components/gp_availability/`. The APIs are documented in `API.md`; read it before touching a provider.

Until 0.2.0 this was "EasyVisit GP Availability" (domain `easyvisit`, repo `Forcky/EasyVisitHA`). The domain change was deliberate and breaking; don't add compatibility shims for the old one.

## Layout

- `providers/`: one module per booking site, no Home Assistant imports.
  - `base.py`: the `Provider` ABC, the `Practice`/`ApptType`/`Doctor`/`Availability`/`ParsedInput` dataclasses, `ProviderError`, and `get_json` (the 10 MB cap).
  - `easyvisit.py`: unwraps the `{StatusCode, Message, Data}` envelope, drops `photoData`/`bio`, and holds `parse_resources` (naive local time + Windows zone name → aware datetime).
  - `hotdoc.py`: the clinic lookup, cached for 6 hours. An appointment type is `"<reason_id>:new|existing"`. `time_slots` is called in 7-day windows, and slots are mapped to doctors by `availability_type_id`.
  - `__init__.py`: the `PROVIDERS` registry and `detect(text)`, which finds the provider from a pasted link.
- `slots.py`: **no Home Assistant imports**. It holds `Slot` (doctor ids are strings), cutoff matching and the "already announced" diff.
- `coordinator.py`: one `provider.fetch` per poll, up to the longest cutoff. It builds per-watch data and runs `_announce` (event + notify services).
  - Per-watch settings (`cutoff_days`, `notify`, `seen`) live in a `helpers.storage.Store`, **not** the config entry, so changing them from an entity doesn't reload the integration.
  - `seen: None` marks a watch that hasn't polled yet; that first poll is silent.
  - Each watch also has a `window` (`slots.Window`: day preset, earliest/latest time, from/until dates; until replaces the cutoff). The top-level `polling` flag is the practice's Checking switch: off sets `update_interval = None`, skips the startup refresh, and `_async_update_data` returns the old data without a request.
- `entity.py`: one device per watch (`<entry_id>_<doctor id>`, with `any` = any doctor), linked by `via_device_id` to a practice device that `__init__.py` creates first. `via_device` (identifier tuple) is deprecated since 2026.8, hence `hacs.json`'s minimum HA version.
- Platforms: `sensor`, `binary_sensor`, `number` (cutoff), `switch` (notifications per watch; Checking per practice), `button` (test notification, reset window), `select` (preferred days), `time` (earliest/latest), `date` (from/until).
- `config_flow.py`: link → appointment type → doctors + notify targets + interval. The options flow edits the same fields and reloads. The watch list is stored in options as `{"<doctor id>": "<name>"}`.

To add a booking site, follow "Adding a provider" in `docs/development.md`. HealthEngine is the next candidate (see `docs/roadmap.md`).

## Validating changes

The tests need Linux or macOS, because HA imports `fcntl`. On Windows, run them in WSL or in Docker:

```bash
docker run --rm -v "<repo>:/src:ro" python:3.14-slim sh -c \
  'cp -r /src /w && cd /w && pip install -q -r requirements_test.txt && python -m pytest -q -p no:cacheprovider'
```

- `tests/test_slots.py` covers the pure logic.
- `tests/test_easyvisit.py` / `tests/test_hotdoc.py` cover the providers against mocked HTTP.
- `tests/test_init.py` / `tests/test_config_flow.py` run a real HA through `pytest-homeassistant-custom-component`, with the provider clients patched and a frozen clock.
- The fixtures in `tests/fixtures/` are anonymised real responses (names, notes, slugs and IDs replaced, real slot times kept).

CI (`.github/workflows/validate.yml`) runs HACS, hassfest and pytest. hassfest rules that trip easily:
- `manifest.json` keys must be ordered `domain`, `name`, then alphabetical.
- No translation string may contain a literal URL. Pass URLs through `description_placeholders`.

## Gotchas

- Slot times must end up timezone-aware in the practice's zone. EasyVisit slots are naive local times with a Windows zone name; HotDoc slots carry an offset. Never apply a fixed offset: Tasmania changes to DST on the first Sunday of October.
- HotDoc returns HTTP 500 for `time_slots` ranges much over 7 days, and marks every reason `bookable: false` for non-browser clients. Don't filter on `bookable`.
- Be polite to the booking sites: personal, read-only, low-rate. Don't lower HotDoc's minimum interval, and don't disguise the User-Agent as a browser.
- The Any-doctor watch at a busy practice has hundreds of qualifying slots. Keep it muted by default, with a short default cutoff.
- Automatic booking was researched and dropped: EasyVisit bookings carry a reCAPTCHA v3 token, and HotDoc only accepts its own web app's headers. Don't re-propose it without new facts (API.md, "Booking research"). HotDoc alerts carry per-slot Book links instead.
