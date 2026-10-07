# Roadmap

## Next: HealthEngine

HealthEngine is the second-largest GP booking site in Australia. Its practice pages (`/medical-centre/<state>/<suburb>/<slug>/s<id>`) embed the open slots in the page's Next.js data. A single request per check would cover a practice. Its terms forbid screen scraping for commercial purposes, so it would be personal, read-only use like the others. See "Adding a provider" in [development.md](development.md).

Also seen at Australian GPs, less often: AutoMed (server-rendered pages that need a session cookie), and Halaxy (open JSON, but mostly allied health).

## Not planned: automatic booking

Researched in October 2026 (details in [API.md](../API.md#booking-research-not-used)) and dropped, because neither site can be booked automatically without defeating its protections:

- **EasyVisit:** every booking, including for signed-in users, carries a reCAPTCHA v3 token produced in the browser. There is no list of your appointments to guard against double booking, and cancelling needs the token from the confirmation email plus an SMS code.
- **HotDoc:** booking only works for clients that present HotDoc's own web-app headers. It also needs an emailed login code and a password re-check, and clinics can add questions before booking.

What the integration does instead: the [preferred window](configuration.md#preferred-window) narrows alerts to the slots you can make, and on HotDoc each alert opens the exact slot with **Book** buttons, so booking takes a tap or two.

## Ideas

- Quiet hours for notifications
- Several preferred windows per doctor (e.g. Wednesday mornings *or* Friday afternoons)
- Snooze for a doctor until a date
