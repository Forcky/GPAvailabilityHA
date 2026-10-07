# Notifications and automations

## When you get an alert

Each check (default every 10 minutes on HotDoc, 5 on EasyVisit):

1. Fetch the open slots for the appointment type, at least up to the latest last day across watches.
2. For each watched doctor, find the slots **on or before the last day** (the cutoff, or the preferred until date) that fall inside the [preferred window](configuration.md#preferred-window).
3. Compare them with the slots already announced. **Only new ones are announced.**
4. Forget any slot that has gone (someone booked it), so it is announced again if it reopens.

Also:
- **The first check after you add a doctor is silent.** Slots already open are recorded, not announced, so setup doesn't flood your phone. Use **Send test notification** to see them.
- **Raising the cutoff** announces the slots that are now inside it.
- **What has been announced survives restarts.** Slots that open while Home Assistant is down are announced on the first check after it starts.

## What the notification looks like

```
Alex Morgan: 2 new slots by Sun 11 Oct
Tue 29 Sep 09:00
Wed 30 Sep 14:15
```

- Up to 5 slots are listed, then "+N more". If other slots before the cutoff were already open, a line like "(4 open by Sun 11 Oct in total)" is added.
- *Any doctor* alerts include the doctor's name on each line.
- Tapping it opens the booking page: on HotDoc the first new slot's own booking page, otherwise the doctor's or practice's page (`url` / `clickAction`).
- On HotDoc it also has up to 3 **Book** buttons, one per new slot (e.g. *Book Tue 6 Oct 09:00*), each opening that slot's booking page. EasyVisit has no per-slot links, so its alerts have no buttons.
- It also sets `tag` (so a newer alert replaces the older one for the same doctor) and `group: gp_availability`.
- It is sent as urgent, so it arrives straight away even when the phone is asleep: `priority: high` and `ttl: 0` on Android, and `push: {interruption-level: time-sensitive}` on iOS, which also lets it through Focus modes that allow time-sensitive alerts. It does not break through Android Do Not Disturb; for that, use the automation below.

## The `gp_availability_slot_available` event

This event fires for every announcement, even when the Notifications switch is off:

```yaml
event_type: gp_availability_slot_available
data:
  entry_id: 01J...
  provider: hotdoc          # or easyvisit
  practice_id: "999"
  appt_type_id: "501:existing"
  watch_id: "2001"          # the booking site's doctor id; "any" = any doctor
  watch_name: Dr Alex Morgan
  cutoff: "2026-10-11"
  booking_url: https://www.hotdoc.com.au/medical-centres/.../doctors/dr-alex-morgan
  new_slots:
    - doctor: Dr Alex Morgan
      resource_id: "2001"
      booking_url: https://www.hotdoc.com.au/request/consult/start?defaults=...   # HotDoc only
      start: "2026-09-29T09:00:00+10:00"
```

`booking_url` is the doctor's own page when the site has one (HotDoc), otherwise the practice's booking page. Each slot in `new_slots` also has its own `booking_url` on HotDoc.

## Example automations

### Urgent alert that breaks through Do Not Disturb (Android)

Turn off the integration's own **Notifications** switch for this doctor and use this instead:

```yaml
alias: GP slot - urgent alert
triggers:
  - trigger: event
    event_type: gp_availability_slot_available
    event_data:
      watch_id: "2001"
actions:
  - action: notify.mobile_app_pixel_8
    data:
      title: "GP slot: {{ trigger.event.data.watch_name }}"
      message: >
        {% for s in trigger.event.data.new_slots[:5] %}
        {{ as_datetime(s.start).strftime('%a %-d %b %H:%M') }}
        {% endfor %}
      data:
        clickAction: "{{ trigger.event.data.booking_url }}"
        channel: gp_slots
        importance: high
        ttl: 0
        priority: high
```

### Only during the day

```yaml
alias: GP slot - daytime only
triggers:
  - trigger: event
    event_type: gp_availability_slot_available
conditions:
  - condition: time
    after: "07:00:00"
    before: "21:30:00"
actions:
  - action: notify.mobile_app_pixel_8
    data:
      title: "{{ trigger.event.data.watch_name }}: new GP slot"
      message: "{{ trigger.event.data.new_slots | length }} new before {{ trigger.event.data.cutoff }}"
      data:
        clickAction: "{{ trigger.event.data.booking_url }}"
```

### Announce on a speaker

```yaml
alias: GP slot - speaker
triggers:
  - trigger: event
    event_type: gp_availability_slot_available
    event_data:
      watch_id: "2001"
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.kitchen
      message: >
        Doctor {{ trigger.event.data.watch_name.split(' ')[-1] }} has an appointment
        on {{ as_datetime(trigger.event.data.new_slots[0].start).strftime('%A at %-I:%M %p') }}.
```

## Dashboard card

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Dr Morgan
    entities:
      - entity: sensor.alex_morgan_next_available
        name: Next available
      - entity: sensor.alex_morgan_slots_before_cutoff
        name: Before cutoff
      - entity: number.alex_morgan_cutoff
      - entity: switch.alex_morgan_notifications
  - type: markdown
    content: >
      {% set s = state_attr('sensor.alex_morgan_next_available', 'next_slots') or [] %}
      {% for x in s %}- {{ as_datetime(x.start).strftime('%a %-d %b %H:%M') }}
      {% else %}Nothing open.{% endfor %}

      [Book online]({{ state_attr('sensor.alex_morgan_next_available', 'booking_url') }})
```
