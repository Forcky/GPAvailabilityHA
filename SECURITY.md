# Security

Please report vulnerabilities privately through GitHub's **Report a vulnerability** button (Security tab), not in a public issue.

## What this integration handles

- **Data:** only the public availability data of HotDoc and EasyVisit. It needs no credentials and stores none. Per-doctor settings and the list of slots already announced are kept in Home Assistant's `.storage`.
- **Notify targets** are limited to `notify.<service>`. Other services are rejected by the config flow and ignored at runtime.
- **Responses** over 10 MB are refused.
- **No sign-in.** Automatic booking was researched and dropped (see the roadmap), so no booking-site credentials are ever asked for or stored.
