# Troubleshooting

## No notification arrived

1. **Press "Send test notification"** on the doctor's device.
   - If nothing arrives, the notify service is the problem. Check **Configure → Notify services**, and try the same service in Developer tools → Actions.
   - If it arrives, the integration and phone are fine. There simply hasn't been a *new* slot before the cutoff.
2. Check that **Notifications** is on for that doctor. *Any doctor* starts off.
3. Check the **Checking** switch on the practice device is on. When it's off nothing is checked; **Last checked** shows when the last check ran.
4. Check the doctor's **preferred window**: the `window` attribute of **Slots before cutoff** shows it. A passed until date means nothing counts. **Reset preferred window** clears it.
5. Remember the **first check after adding a doctor is silent**. Slots already open are only announced once they reopen, or if you raise the cutoff to include them.
6. Look at **Slots before cutoff**. If it's above 0, those slots have already been announced.
7. On Android, check that the companion app is allowed to show notifications and isn't battery-restricted.
8. Each doctor's alerts share one notification `tag`, so a new alert replaces the previous one in place instead of stacking. Swipe the old one away if you're unsure whether a new one arrived.

## "Isn't a HotDoc or EasyVisit booking link" during setup

Paste the whole link from the practice's booking page (see [Configuration](configuration.md#1-practice)). For EasyVisit you can also enter just the number after `/booking/`.

## "The booking site did not recognise that practice"

Check the link opens the practice's page in a browser. The booking site may also be temporarily unreachable; try again shortly.

## Entities are unavailable

The last check failed. The booking site may be down, or Home Assistant may have no internet. The integration retries on the next interval. **Cutoff** and **Notifications** stay usable while it retries. Check the logs as described below.

## Slot times look an hour off

Times are converted from the practice's own zone (HotDoc gives it with each slot; EasyVisit reports e.g. *Tasmania Standard Time*). Make sure Settings → System → General has the right time zone for **your** Home Assistant. Entities are stored in UTC and displayed in HA's zone.

## A doctor shows "Not listed for this appointment type right now"

The practice has stopped offering that appointment type for the doctor, or has hidden them online. They remain watched and come back automatically if they reappear.

## HotDoc: a doctor shows a next available date but no slots

HotDoc is only asked for slots up to the longest cutoff. **Next available** comes from HotDoc's own "next available" and can be later than that. Raise the cutoff if you want those slots to count.

## Debug logs

Add this to `configuration.yaml` and restart, or use the integration's **Enable debug logging**:

```yaml
logger:
  logs:
    custom_components.gp_availability: debug
```

Then filter Settings → System → Logs by `gp_availability`. Each announcement logs `"<doctor>: N new slot(s) by <date>"` at info level.

## Reporting an issue

Open an issue at <https://github.com/Forcky/GPAvailabilityHA/issues> with your HA version, the integration version, the booking site, and debug logs. Remove anything personal first.
