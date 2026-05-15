# Trellis school advisory PWA

A mobile-first Progressive Web App that delivers a daily child-health advisory to primary school administrators in pilot wards. Works offline once installed.

## What's in this folder

| File | Purpose |
|---|---|
| `index.html` | The PWA itself — single-page app with traffic-light alert, action checklist, 5-day outlook |
| `manifest.json` | PWA manifest — defines name, icons, theme colour, display mode |
| `sw.js` | Service worker — caches assets and forecast data for offline use |
| `forecast.json` | Latest 51-ward May 2026 forecast |
| `ward_timeseries.json` | Per-ward population, facilities, and historical context |
| `README.md` | this file |

## Running it

The PWA needs to be served over HTTP (not `file://`) for the service worker to work. Three ways:

### Option A — Python's built-in server (no install needed)

```bash
cd pwa-school
python3 -m http.server 8081
```

Open `http://localhost:8081` on your phone (same Wi-Fi network) or laptop.

### Option B — Deploy to GitHub Pages, Netlify, or Vercel

Drag the `pwa-school` folder into a GitHub Pages site or Netlify drop. Public URL works on any device.

### Option C — Embed in a DHIS2 custom app

DHIS2 supports custom apps as zipped folders. Zip `pwa-school` and upload via DHIS2 → App Management.

## Installing on a phone

1. Open the PWA URL in Chrome / Safari on the phone
2. Wait ~5 seconds for the service worker to register (icon appears in the URL bar on Chrome)
3. Tap the menu → "Add to Home screen" / "Install app"
4. The PWA now opens like a native app, works offline

## What works offline

After the first online load:

- The complete UI loads from cache
- Last-fetched forecast data renders
- The 5-day outlook synthesises from the cached forecast
- An "Offline" banner shows at the top while disconnected

## How forecasts get refreshed

The service worker uses cache-first strategy. To pull a new forecast:

- Open the app while online — fresh data is fetched and cached
- Or force a refresh by clearing the app's cache (browser settings → Site data → Clear)

For production deployment, this should be replaced with a periodic background fetch + push notification when a new forecast lands.

## What this does NOT do

- Does not push notifications (would need a push subscription server)
- Does not log anything back to the project (no telemetry — privacy-first)
- Does not collect any user data — works with no account, no signup, no login

## Customisation

The `index.html` file is the entire app. The colour palette, font choices, and tone-of-voice strings (action lists, alert summaries) are at the top of the `<style>` block and inside the `actionsFor()` and `summaryFor()` JavaScript functions. Edit those to match local language, register, or branding.

For Pidgin or local-language variants: duplicate the action and summary functions, switch on a language toggle in the header, persist to localStorage.

## Planned production deployment

When real forecasts are produced nightly:

1. The Trellis pipeline writes a fresh `forecast.json` to the public deployment URL
2. Each registered school's PWA fetches it on next open
3. If a "likely" alert fires for a ward, the school administrator gets a notification (push)
4. The advisory page is the source of truth for that school's morning brief

That last step requires a push notification server, which is intentionally not included here. The PWA itself is the offline-first display layer.
