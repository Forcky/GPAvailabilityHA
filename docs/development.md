# Development

## Architecture

```
custom_components/gp_availability/
  providers/
    base.py       Provider ABC, Practice/ApptType/Doctor/Availability, capped JSON GET
    easyvisit.py  EasyVisit client + parse_resources (Windows zone names → IANA)
    hotdoc.py     HotDoc client; reason × new/existing → availability types; 7-day windows
    __init__.py   PROVIDERS registry and detect(link)
  slots.py        pure logic, no HA imports: Slot, cutoff, "already announced" diff
  coordinator.py  DataUpdateCoordinator: one provider.fetch per poll, per-watch data,
                  announcements (event + notify services), settings in a Store
  entity.py       per-watch device (via_device_id -> practice device)
  sensor.py  binary_sensor.py  number.py  switch.py  button.py  select.py  time.py  date.py
  config_flow.py  link -> appointment type -> doctors/notify/interval; options flow
```

- **Data flow:** `provider.fetch` → `Availability(doctors, slots)` → `slots_for_watch` → `qualifying` → `diff_seen` → announce.
- **`coordinator.data`:** `{"doctors": {doctor_id: Doctor}, "watches": {watch_id: {"slots", "qualifying", "cutoff", "next_available", "url"}}}`.
- **Store `gp_availability.<entry_id>`:** holds `{"watches": {"<id>": {"cutoff_days", "notify", "seen"}}}`. `seen: null` means the watch hasn't polled yet, so its first poll is silent. `seen` holds `Slot.key` values (`"<doctor id>|<naive local ISO>"`).
- **Config entry:**
  - `data`: `provider`, `practice_id`, `practice_name`, `timezone`, `booking_url`, `appt_type_id`, `appt_type_name`. All ids are strings.
  - `options`: `watches` (`{"<doctor id>": "<name>"}`, with `"any"` for any doctor), `notify_targets` and `scan_interval`.
  - `unique_id`: `<provider>_<practice_id>_<appt_type_id>`.

The APIs are described in [API.md](../API.md).

## Adding a provider

1. Work out the site's public availability calls and write them up in `API.md`: endpoints, ids, time zones, limits, and anything odd.
2. Add `providers/<site>.py` with a `Provider` subclass:
   - `key` (stored in config entries, never change it), `name`, `default_scan_interval`, `min_scan_interval`
   - `parse_input(text)`: recognise the site's links. Return `None` for anything else, so `detect` can try the next provider.
   - `get_practice`, `get_appointment_types`, `get_doctors`, `fetch`, and `booking_url` if the practice URL isn't enough
   - Slots must be timezone-aware in the practice's zone, and doctor ids strings.
3. Register it in `PROVIDERS` in `providers/__init__.py`.
4. Add an anonymised recorded fixture and `tests/test_<site>.py` (link parsing, request shape, parsing incl. a DST change, errors), plus a config-flow test.
5. Update the providers table in the README, the setup text in `strings.json` (then copy it to `translations/en.json`), and `docs/configuration.md`.

## Running the tests

The tests use [`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component), which runs a real Home Assistant core. **It needs Linux or macOS**, because HA imports `fcntl`. On Windows, use WSL or Docker:

```bash
uv venv -p 3.14 .venv && source .venv/bin/activate   # or: python3.14 -m venv .venv
pip install -r requirements_test.txt
pytest -q

# or, with only Docker:
docker run --rm -v "$PWD:/src:ro" python:3.14-slim sh -c \
  'cp -r /src /w && cd /w && pip install -q -r requirements_test.txt && python -m pytest -q'
```

| File | Covers |
|---|---|
| `tests/test_slots.py` | Cutoff edges, re-announce logic, slot keys, formatting |
| `tests/test_easyvisit.py` | EasyVisit client envelope/errors/size cap, parsing, DST |
| `tests/test_hotdoc.py` | HotDoc request shape, 7-day windows, availability-type mapping, next available, DST, errors |
| `tests/test_init.py` | Entities, silent first poll, notifications once and again after reopening, mute switch, cutoff changes, test button, settings across reload, options flow pruning devices; a HotDoc entry end to end |
| `tests/test_config_flow.py` | Link detection for both sites, both full flows, validation errors |

Fixtures in `tests/fixtures/` are anonymised real responses (names, notes, slugs and ids replaced, real slot times kept): `resources_sample.json` (EasyVisit, 3 doctors), `hotdoc_clinic.json` and `hotdoc_time_slots.json` (HotDoc, 3 doctors, 29 Sep – 5 Oct 2026 across the DST change).

## CI

`.github/workflows/validate.yml` runs on push, on PRs, and daily. It has three jobs:
- **HACS validation**
- **hassfest**:
  - `manifest.json` keys must be ordered `domain`, `name`, then alphabetical.
  - Translation strings must not contain URLs; pass them via `description_placeholders`.
- **pytest**

## Releasing

1. Bump `version` in `custom_components/gp_availability/manifest.json`.
2. Merge to `main`.
3. `gh release create vX.Y.Z --target <full merge sha> --notes "..."`. The target must be the full SHA; a short one is rejected.

HACS offers the new release to users.

## Translations

`strings.json` is the source. Copy it to `translations/en.json` whenever it changes.
