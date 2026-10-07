# GP Availability for Home Assistant

[![Validate](https://github.com/Forcky/GPAvailabilityHA/actions/workflows/validate.yml/badge.svg)](https://github.com/Forcky/GPAvailabilityHA/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)

Get a notification on your phone as soon as an appointment opens up with **your** GP.

Popular GPs are often booked out for weeks, and cancellations are gone within minutes. This integration watches the practice's online booking page. When a slot with the doctor you choose opens up before your cutoff, you get an alert, and tapping it opens the booking page.

## Supported booking sites

| Site | Used by | Paste this link |
|---|---|---|
| [HotDoc](https://www.hotdoc.com.au) | Most Australian GP practices | The practice's HotDoc page, or one doctor's page (preselects that doctor) |
| [EasyVisit](https://www.easyvisit.com.au) | IPN / Sonic practices | The booking page, e.g. `https://web.easyvisit.com.au/booking/123/456`, or just the location ID |

HealthEngine is next on the [roadmap](docs/roadmap.md).

## Features

- **No login needed.** It reads the same public availability the booking page shows.
- **Watch as many doctors as you like**, each with their own cutoff, plus an optional *Any doctor* watch.
- **Preferred window.** Only hear about the slots you can make: certain days (e.g. Wednesdays), a time range, or specific dates ("only next Wednesday").
- **One tap to book.** On HotDoc, alerts open the exact slot and carry *Book* buttons for the new slots. Nothing is ever booked for you.
- **Announces each slot once.** If someone books a slot and it later reopens, you hear about it again.
- **Urgent alerts.** Notifications are sent high priority / time-sensitive, so a sleeping phone shows them straight away.
- **Automation-friendly.** Every new slot fires a `gp_availability_slot_available` event.
- **Pause any time.** A per-practice *Checking* switch stops all requests until you need it again.
- **Handles Tasmanian daylight saving** and other Australian time zones.

> Not affiliated with HotDoc, EasyVisit or Sonic Healthcare. It uses undocumented APIs that may change without notice. It is for personal use: it only reads availability, never books, and checks gently (HotDoc every 10 minutes by default). Please keep it that way.

## Quick start

1. **Install:** HACS → ⋮ → *Custom repositories* → add `https://github.com/Forcky/GPAvailabilityHA` as an **Integration**. Download **GP Availability**, then restart Home Assistant.
2. **Add:** Settings → Devices & services → *Add integration* → **GP Availability**.
3. **Paste the booking link** from the practice's HotDoc or EasyVisit page.
4. **Pick the appointment type and your doctor(s),** plus the notify service for your phone (e.g. `notify.mobile_app_pixel_8`).
5. **Test it:** press **Send test notification** on the doctor's device.

Coming from *EasyVisit GP Availability* 0.1.x? See [moving from EasyVisit GP Availability](docs/installation.md#moving-from-easyvisit-gp-availability-01x).

## What you get (per doctor)

| Entity | Description |
|---|---|
| **Next available** | The earliest open slot (timestamp), with the next 10 slots and the doctor's notes as attributes |
| **Slots before cutoff** | How many open slots count: on or before the cutoff (or until date) and inside the preferred window |
| **Slot before cutoff** | Binary sensor, on when any slot counts |
| **Cutoff** | Days ahead that count as soon enough (default 14; *Any doctor* defaults to 2) |
| **Notifications** | Turn alerts for this doctor on or off |
| **Preferred days / earliest time / latest time / from date / until date** | The preferred window; **Reset preferred window** clears it |
| **Send test notification** | Sends what counts right now |

Per practice: **Last checked**, and **Checking** to pause all checks.

## Documentation

- [Installation](docs/installation.md): HACS, manual install, updating, removing, moving from 0.1.x
- [Configuration](docs/configuration.md): setup, options, entities, choosing a cutoff
- [Notifications and automations](docs/notifications.md): how alerts are decided, the event, example automations and dashboard cards
- [Troubleshooting](docs/troubleshooting.md)
- [Development](docs/development.md): architecture, tests, adding a provider, releasing
- [API notes](API.md): the reverse-engineered HotDoc and EasyVisit APIs
- [Roadmap](docs/roadmap.md): HealthEngine, opt-in auto-booking

## Licence

MIT. See [LICENSE](LICENSE).
