# Galim Pro MQTT Monitor

Unofficial monitor that signs in to Galim Pro, reads active homework from the
Galim LMS API, and publishes it to Home Assistant through MQTT Discovery.

> This project is not affiliated with Galim or the Israeli Ministry of
> Education. Use it only with an account you are authorized to access.

## Status

The login and `/personal_api/tasks` request have been verified with a real
account. The account had no assignments at the time, so field mapping will be
confirmed and adjusted when the first real task payload is available.

## Home Assistant entities

MQTT Discovery creates:

- `sensor.galim_pro_homework`: number of active tasks
- Attributes: normalized task list, total count, and last update time

New tasks are also emitted as non-retained JSON on `galim_pro/homework/new`.

## Requirements

- Docker with Docker Compose
- A Home Assistant MQTT broker, typically the Mosquitto broker add-on
- Galim Pro access through a Ministry of Education account

## Setup

1. Configure Home Assistant's MQTT integration and broker.
2. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

3. Edit `.env` locally and set the Galim and MQTT values. Never commit it.
4. Build and start the monitor:

   ```bash
   docker compose up -d --build
   ```

5. Follow startup logs:

   ```bash
   docker compose logs -f galim-pro-monitor
   ```

The sensor should appear automatically after the first successful MQTT
connection and poll.

## Session handling

Playwright performs the Ministry login and stores browser state in
`data/browser_state.json`. Later starts try that session before logging in
again. When the API reports an expired session, the monitor removes the stale
state and authenticates again.

The `data/` directory contains bearer cookies and is Git-ignored. Treat it as
sensitive. The monitor never logs credentials or the LMS `SID` cookie.

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GALIM_USERNAME` | yes | — | Ministry login username |
| `GALIM_PASSWORD` | yes | — | Ministry login password |
| `MQTT_HOST` | yes | — | MQTT broker hostname or address |
| `MQTT_PORT` | no | `1883` | MQTT broker port |
| `MQTT_USERNAME` | no | — | MQTT username |
| `MQTT_PASSWORD` | no | — | MQTT password |
| `POLL_INTERVAL_MINUTES` | no | `30` | Poll interval |
| `SEED_QUIETLY` | no | `true` | Suppress new-task event on first poll |
| `HEADLESS` | no | `true` | Run Chromium without a visible window |
| `DATA_DIR` | no | `/app/data` | Persistent private state directory |
| `LOG_LEVEL` | no | `INFO` | Python logging level |

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
playwright install chromium
pytest -q
ruff check .
```

## Security

- Do not commit `.env`, `config.json`, browser state, cookies, screenshots, or
  captured API payloads containing student information.
- Use a dedicated MQTT account where possible.
- Keep MQTT on the local network or enable transport security.
- Review task attributes before sharing diagnostics.

## License

MIT

