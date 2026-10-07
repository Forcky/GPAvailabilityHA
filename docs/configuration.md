# Configuration

## Adding the integration

Settings → Devices & services → **Add integration** → **GP Availability**.

### 1. Practice

Paste the link to the practice's online booking page. The integration works out the booking site from the link.

| Site | What to paste |
|---|---|
| **HotDoc** | The practice's page, e.g. `https://www.hotdoc.com.au/medical-centres/kingston-TAS-7050/<practice>/doctors`. A link to one doctor's page (`…/doctors/<doctor>`) also works and preselects that doctor. |
| **EasyVisit** | The booking page, e.g. `https://web.easyvisit.com.au/booking/123/456`, or just the location number (`123`). The second number (`456`) is the appointment type, which is then preselected. |

### 2. Appointment type

These are the practice's own types, e.g. *Standard appt.* or *Long appt.*. Each practice + appointment type pair is a separate integration entry. To watch Standard and Long appointments, add the integration twice.

On **HotDoc**, each type is listed once for existing patients and once for new patients, when the practice offers both. They can have different availability, so pick the one that applies to you.

### 3. Doctors and notifications

| Field | Meaning |
|---|---|
| **Doctors to watch** | Each ticked doctor becomes a device. The list shows each doctor's next available date. *Any doctor at …* watches the whole practice. |
| **Notify services** | Where alerts go, e.g. `notify.mobile_app_pixel_8`. Choose several or none. With none, only the event fires. You can also type a service name that isn't in the list. |
| **Check every** | Minutes between checks. Default: HotDoc 10 (5–60), EasyVisit 5 (2–60). |

Requests per check:
- **EasyVisit:** one request covers every doctor.
- **HotDoc:** one request per 7 days up to the longest cutoff, covering every watched doctor. The default 14-day cutoff takes 3 requests.

## Changing options later

Settings → Devices & services → GP Availability → **Configure**. You can change the watched doctors, notify services and check interval. The integration reloads when you save.

- Doctors you untick are removed along with their devices.
- If a doctor stops offering that appointment type, they stay watched and are shown as *not listed right now*.

## Entities

Each watched doctor is a device, grouped under the practice device.

| Entity | Type | Notes |
|---|---|---|
| `sensor.<doctor>_next_available` | timestamp | The earliest open slot (ignores the preferred window). Attributes: `open_slots`, `next_slots` (up to 10 × `{doctor, resource_id, start, booking_url}`), `booking_url`, `notes`, and `manual_confirm` (EasyVisit only) |
| `sensor.<doctor>_slots_before_cutoff` | count | Open slots that count: up to the last day, inside the preferred window. Attributes: `cutoff` (the last day that counts), `window` (e.g. `Wednesdays, 09:00–12:00`), `slots` (up to 10) |
| `binary_sensor.<doctor>_slot_before_cutoff` | on/off | On when any slot counts |
| `number.<doctor>_cutoff` | days (0–60) | See [Choosing a cutoff](#choosing-a-cutoff) |
| `select.<doctor>_preferred_days` | Any day / Weekdays / Weekends / Monday … Sunday | See [Preferred window](#preferred-window) |
| `time.<doctor>_preferred_earliest_time`, `time.<doctor>_preferred_latest_time` | time | Earliest and latest start time, inclusive (default 00:00–23:59) |
| `date.<doctor>_preferred_from_date`, `date.<doctor>_preferred_until_date` | date | Optional first and last day. Unknown = not set. |
| `button.<doctor>_reset_preferred_window` | button | Back to any day, any time, no dates |
| `switch.<doctor>_notifications` | on/off | Mutes notify services for this doctor. Checks carry on and the event still fires. |
| `button.<doctor>_send_test_notification` | button | Sends what counts right now, marked `[Test]` |
| `switch.<practice>_checking` | on/off | Off pauses the whole practice: no requests at all. See [Pausing checks](#pausing-checks). |
| `sensor.<practice>_last_checked` | timestamp | Diagnostic: when availability was last fetched |

On HotDoc, only slots up to the latest last day are fetched, so `open_slots` and `next_slots` stop there. **Next available** still shows the doctor's next opening beyond it, because HotDoc reports that separately.

All these settings are kept by the integration itself. They survive restarts and don't reload anything when you change them. A change is checked straight away, so slots that now count are announced.

## Choosing a cutoff

A slot counts when it falls **on or before today + cutoff days** (calendar days, in the practice's time zone):

| Cutoff | Counts |
|---|---|
| 0 | Today only |
| 1 | Today and tomorrow |
| 14 | Anything up to two weeks from today |

Tips:
- Set it just short of your doctor's current *Next available*. For example, if the next slot is 26 days away, a cutoff of 14 alerts you to cancellations in the next fortnight.
- EasyVisit only shows about **6 weeks** ahead, so anything larger has no extra effect there.
- On HotDoc, each extra week of cutoff adds a request per check.
- The cutoff rolls forward each day. Slots already open that come inside the window are announced when they do.
- *Any doctor* at a busy practice can have hundreds of slots a fortnight out. That's why it defaults to 2 days with notifications off.

## Preferred window

Narrow down which slots count, per doctor (or for *Any doctor*). Everything else then ignores slots outside the window: alerts, the event, **Slots before cutoff** and **Slot before cutoff**.

| Setting | Effect |
|---|---|
| **Preferred days** | Any day, Weekdays, Weekends, or one day of the week |
| **Preferred earliest / latest time** | The slot must *start* between these times (inclusive). If earliest is after latest, the window runs overnight. |
| **Preferred from date** | Ignore slots before this day |
| **Preferred until date** | The last day that counts. **When set, it replaces the cutoff.** |
| **Reset preferred window** | Clears all of the above |

Examples:
- **Only next Wednesday:** set both dates to that Wednesday.
- **Wednesday mornings, any week:** Preferred days *Wednesday*, latest time *12:00*. The cutoff still limits how far ahead.
- **Any GP after school, within a week:** on the *Any doctor* watch set Preferred days *Weekdays*, earliest time *15:30*, cutoff *7*, and turn its Notifications on.

Once the until date has passed, nothing counts. The `window` attribute shows `(passed)`. This is deliberate, so an expired "only that Wednesday" doesn't quietly widen to any day. Change the date or press **Reset preferred window**.

The integration only alerts; it never books. Booking automatically isn't possible without defeating the booking sites' protections. On HotDoc, the alert's **Book** buttons open that exact slot, so booking takes a tap or two.

## Pausing checks

The **Notifications** switch only mutes the alerts. Checks carry on, because the sensors and the event still update. To stop checking a practice altogether, turn off its **Checking** switch (on the practice's device). While it's off:

- No requests are made, not even when Home Assistant starts.
- Settings can still be changed; they are applied when checking resumes.
- The sensors keep their last values until a restart, then show unknown.

Turning it back on checks straight away. Home Assistant's own **⋮ → System options → Enable polling for changes** and **⋮ → Disable** do much the same for the whole entry.

## Defaults

| Setting | Doctor | Any doctor |
|---|---|---|
| Cutoff | 14 days | 2 days |
| Notifications | on | off |
| Preferred window | any day, any time, no dates | the same |
| Checking (per practice) | on | |
