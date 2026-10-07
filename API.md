# API notes

Both sites' availability APIs are undocumented. They were worked out from each site's own web app in September 2026 and confirmed with live calls. They may change without notice.

# HotDoc

The patient site `https://www.hotdoc.com.au` is a single-page app. Its settings put the API on the same host under `/api/patient`. Every request needs `Accept: application/au.com.hotdoc.v5`. No login, token or cookie is needed to read availability, and a plain client with an honest User-Agent works.

## Public endpoints (no auth)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/patient/clinics/{slug or id}` | The practice: `clinic`, `doctors`, `reasons`, `reason_groups`, `doctor_reasons`, … Slug and numeric id both work. |
| GET | `/api/patient/time_slots?start_time&end_time&timezone&clinic_id&availability_type_ids[]&doctor_ids[]` | Open slots. `availability_type_ids[]` and `doctor_ids[]` are repeated once per doctor; several doctors per call is fine. Times are UTC, e.g. `2026-09-28T14:00:00.000Z`. |

Other calls the site makes, not used here: `/api/patient/search`, `/api/patient/suburbs/search?query=`.

### Clinic response (fields used)

```
clinic:          id, slug, name, timezone (IANA, e.g. "Australia/Hobart"), listing_path
doctors[]:       id, slug, full_name, listing_path, accepts_new_patients, statement,
                 earliest_available (UTC, across all reasons), visible_on_hot_doc
reasons[]:       id, name, position, deleted_at, reason_group_id (-999 = Telehealth)
doctor_reasons[]: doctor_id, reason_id, is_for_new, availability_type_id, duration (s), deleted_at
```

An **appointment type** in this integration is a reason plus patient kind (`"<reason_id>:existing"` or `"<reason_id>:new"`). `doctor_reasons` maps each (doctor, reason, new/existing) to an `availability_type_id`, and that is what `time_slots` is queried with. The web app picks the entry whose `is_for_new` matches the patient.

### time_slots response

```
time_slots[]: id, day, label ("11:45 am"), start_time / end_time (local time with offset,
              e.g. "2026-09-30T11:45:00+10:00"), duration, availability_type_id (string),
              link (booking deep link: /request/consult/start?defaults=practice-…,practitioner-…,when-…)
doctors[]:    id, and next_available / prev_available for doctors with nothing in the window
days[]:       {date}
```

## Quirks

- **At most about 7 days per `time_slots` call.** 7 days works; 14, 22 and 30 days return HTTP 500 with an HTML page. The integration asks for contiguous 7-day windows up to the longest cutoff.
- **`next_available` is only given for doctors with no slots in the window.** For the others, the first slot is the next one. Combining the two gives "next available" without fetching the whole booking horizon.
- **Slots follow the availability type, not the doctor.** When a doctor id and availability type don't match, the response follows the type. Map slots to doctors through `doctor_reasons`, never through the ids sent.
- **`bookable` is unreliable for non-browser clients.** Every reason comes back `bookable: false` with the message "Due to extra screening measures, we cannot complete your booking at this time…". This blocks booking only; slots are still returned. Don't filter on it.
- `earliest_available` on a doctor covers all reasons, so it can be earlier than anything bookable for the chosen appointment type.
- Deleted reasons and doctor_reasons stay in the response with `deleted_at` set.

## Terms

`robots.txt` allows everything for general agents. The patient terms (clause 11.2) prohibit reverse engineering or tampering with the platform. There is no public or partner availability API. This integration keeps to personal, read-only, low-rate use: a 10-minute default interval, clinic data cached for 6 hours, and slots fetched only up to the longest cutoff.

# EasyVisit

Reverse-engineered from the web booking app (`https://web.easyvisit.com.au`, an Angular SPA, `main.<hash>.js`) in September 2026 and confirmed with live calls. Nothing here is documented by EasyVisit / Sonic Healthcare.

## Configuration

`GET https://web.easyvisit.com.au/assets/config/config.json` (public):

| key | value |
|---|---|
| `apiUrl` | `https://api.easyvisit.com.au` |
| `openid_connect_url` | `https://identity.apps.sonichealthcare.com/` (Gluu oxauth) |
| `client_id` | `eddb4e22-b4f9-479e-b079-e80b6ad2730e` (public PKCE client) |
| `redirect_uri` | `https://web.easyvisit.com.au/login` |
| `scope` | `openid email profile permission mobile_phone offline_access` |
| `appDeepLinkUrl` | `com.sonichealthcare.easyvisit:/` (the mobile app's redirect) |

OIDC endpoints: `/oxauth/restv1/authorize`, `/oxauth/restv1/token`. Grant types include `authorization_code` and `refresh_token`.

## Envelope

Every response looks like `{"StatusCode": 200, "Message": "Thanks for using EasyVisit", "Data": ...}`. Errors carry a non-200 `StatusCode` (for example 404 with `"Unable to find locations"`) and `Data: null`.

## Public endpoints (no auth)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/Location/{locationId}` | Practice details, opening hours, `photoData` (base64 JPEG) |
| GET | `/api/v1/Location/{locationId}/appointmenttypes` | `[{apptTypeID, name, description, telehealthType}]` |
| GET | `/api/v1/Location/{locationId}/appointmenttypes/{apptTypeId}/resources` | **Every doctor and every open slot** in the booking window. This is the only call the integration polls. |
| GET | `/api/v1/Location/{locationId}/availableslots?ResourceId=&ApptTypeID=&FromDate=YYYY-MM-DD&ToDate=YYYY-MM-DD` | One doctor, a date range; `Data` is the same `availableSlotDates` shape |
| GET | `/api/v1/application/disclaimer` | |

The booking page URL is `https://web.easyvisit.com.au/booking/{locationId}/{apptTypeId}`.

### Resource record

```
resourceId, name, gender, appointmentLength (min), nextAvailableSlot,
availableSlotDates: [{date, slots: [{resourceId, dateTime}], timeZoneId}],
manualConfirm, notesForPatients, billingInfo, specialties, languages,
photoData (base64, large), bio, ...
```

## Quirks

- **Slot times are naive local times.** `timeZoneId` is a *Windows* zone name (`"Tasmania Standard Time"`), mapped in `providers/easyvisit.py`. Tasmania changes to daylight saving on the first Sunday of October, so localise every slot, never apply a fixed offset.
- The resources response is about 225 KB for 12 doctors, almost all of it `photoData`. The client drops `photoData` and `bio` right away.
- The booking window is about 6 weeks. A new day appears at the end of the window each day.
- A doctor with nothing open still appears, with `availableSlotDates: []` and `nextAvailableSlot: null`.
- `manualConfirm: true` means the practice must approve a web booking before it is confirmed.

# Booking research (not used)

Worked out in October 2026 from each site's web app, without signing in or booking. Automatic booking was dropped, because neither site can be booked without defeating its protections (see [roadmap](docs/roadmap.md#not-planned-automatic-booking)). It is kept here so nobody has to redo it.

## EasyVisit

- **Sign-in:** OIDC authorization code + PKCE (S256) against `https://identity.apps.sonichealthcare.com/oxauth/restv1/authorize`, public client `eddb4e22-b4f9-479e-b079-e80b6ad2730e`, `redirect_uri` `https://web.easyvisit.com.au/login`, no `nonce`.
  - The token exchange is a form POST to `/oxauth/restv1/token`.
  - The web app keeps only the access and id tokens. It discards any refresh token, and a 401 sends you back to the start.
  - The discovery document advertises no device-authorization endpoint.
- **Requests:** API calls send `Authorization: Bearer <accessToken>`. There is no API key or device fingerprint.
- **Booking sequence:**
  1. `POST /api/v1/Booking/SlotLock` `{dateTime, resourceID, locationID[, oldLockID]}` → `Data.lockID`. HTTP 409 means the slot is already taken. There is no release call, only re-locking with `oldLockID`.
  2. `POST /api/v1/Booking/ValidateMultipleBooking` `{dateTime: <the day>, locationId[, familyMemberId]}` → `"true"` if the patient already has a booking that day at that practice. The web app then asks for a reason, sent as `MultipleAptBookingNotes`.
  3. `POST /api/v3/Booking` with `{dateTime, resourceID, locationID, appointmentTypeID, lockID, MultipleAptBookingNotes, Token, AppointmentBookedFrom: "Web"}`.
     - **For yourself,** that's the whole body.
     - **For a family member,** add `FamilyMemberId` plus `contactNumber` / `contactEmail` / `contactName` of the account holder.
     - The response is `Data.isManualConfirm`.
- **`Token` is a reCAPTCHA v3 token** from `recaptchaV3Service.execute("submit")`, for signed-in bookings too. That is why booking was dropped.
- **People:** `GET /api/v1/User` (account holder) and `GET /api/V1/user/related` (`[{familyMemberId, familyMember: {...}}]`).
- **No appointments list** in the web app. The only double-booking guard is the same-day check.
- **Cancelling** works only from the confirmation email (`cancel-booking/:locationId/:appointmentId/:token`):
  1. `GET /api/V1/Booking/AllowCancelAppointment`
  2. `POST /api/v1/Booking/ValidateCancellationToken`, which sends an SMS
  3. `POST /api/v1/Otp/ConfirmOTP`
  4. `POST /api/v1/Booking/CancelAppoinmentByToken` (sic)
- **Guests** use `POST /api/v2/Otp/GenerateOTP` (reCAPTCHA v2/v3) and `POST /api/v1/Otp/ConfirmOTP`.

## HotDoc

- **Sign-in:** `POST /api/patient/login` `{patient: {authentication_key: <email>, password}}`. It is followed by a one-time code emailed to you (`authorization: totp <code>`), probably once per new device.
  - The session comes back as `x-session-id` / `x-authentication-token` headers plus cookies. These are opaque tokens with no refresh.
  - A 403 can send you to a password re-check (`/access-check`).
- **Booking:** `POST /api/patient/appointments`, with `{appointment: {...doctor, reason, doctorReason, startTime, endTime, timeSlotId, patientIsNew, forDependent...}, stipulation_responses}`. Clinics can require answers to their own questions (`stipulations`).
  - The web app then polls the appointment until it is `confirmed` / `auto_confirmed`.
  - Server-side limits include `max_1_upcoming_appointment`, `overlaps_existing_appointment` and `too_close_to_appointment`.
- **The "extra screening measures" gate** (`bookable: false` on every reason) lifts only when a request carries the web app's own headers: `app-platform: web`, `app-device-uuid`, `build-revision` and `app-version`. There is no captcha. Sending those would mean posing as HotDoc's app, which this integration won't do.
- **Slot deep links:** each `time_slots[].link` (`/request/consult/start?defaults=practice-…,practitioner-…,when-…`) opens booking for that slot in the browser. The alerts' Book buttons use it.
