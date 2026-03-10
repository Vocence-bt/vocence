# Validator setup guide (Docker + Watchtower)

This guide covers running a Vocence validator using **Docker** and **Watchtower**. The same image is built and published by the team via CI/CD; validators run that image and auto-update when a new one is pushed.

---

## Prerequisites

- **From the Vocence team:** Chutes permission, owner API URL (`API_URL`), Hippius corpus + validator keys.
- **Your side:** Bittensor wallet (coldkey + hotkey), Docker and Docker Compose installed.

---

## 1. Prepare environment and wallet

1. **Clone the repo** (only needed for config and compose file; the validator runs from the published image):

   ```bash
   git clone https://github.com/Vocence-bt/vocence
   cd vocence
   ```

2. **Create `.env`** from the example and fill in values (wallet, Chutes, Hippius, API_URL, etc.):

   ```bash
   cp env.example .env
   # Edit .env: NETWORK, NETUID (102), WALLET_NAME, HOTKEY_NAME,
   # CHUTES_API_KEY, API_URL, HIPPIUS_* keys, VALIDATOR_NAME, etc.
   ```

3. **Bittensor wallets** must be available at `~/.bittensor/wallets` on the host (coldkey and hotkey). The compose file mounts this directory read-only into the validator container.

---

## 2. Run with Docker Compose

Start the validator and Watchtower:

```bash
docker-compose up -d
```

- **Validator:** Docker pulls the image from Docker Hub (e.g. `vocence102/vocence:latest`) if it isn’t already on your machine, then runs it (`vocence serve` — sample generation + weight setting in one process).
- **Watchtower:** Polls Docker Hub every 5 minutes; when the team pushes a new image, it pulls and restarts the validator so you stay up to date without manual steps.

### Overriding the image (optional)

If the team uses a different image name or tag, set it in `.env`:

```bash
DOCKER_IMAGE=vocence102/vocence:latest
```

Then run `docker-compose up -d` as above.

---

## 3. Logs and health

- **Stream logs:**  
  `docker-compose logs -f validator`
- **Watchtower logs:**  
  `docker-compose logs -f watchtower`
- **Restart validator only:**  
  `docker-compose restart validator`
- **Stop everything:**  
  `docker-compose down`

The validator service has a healthcheck; Docker will report its status in `docker ps`.

---

## 4. How updates work

1. The team pushes code to `main`/`master`; GitHub Actions builds the Docker image and pushes it to Docker Hub (see [CI/CD pipeline](cicd-pipeline.md)).
2. On each validator host, Watchtower runs in the same stack and polls the registry (default every 300 seconds).
3. When a new image is available for the validator container, Watchtower pulls it and restarts the container (rolling restart).
4. No manual pull or restart is required; all validators using this setup stay in sync with the published image.

---

## Summary

| What | How |
|------|-----|
| Run validator | `docker-compose up -d` (uses published image + your `.env` and wallets). |
| Updates | Automatic via Watchtower when the team pushes a new image. |
| Logs | `docker-compose logs -f validator` |
| Config | `.env` and `~/.bittensor/wallets` on the host. |

For the full CI/CD flow (how the image is built and published), see [cicd-pipeline.md](cicd-pipeline.md). For CLI options (e.g. split generator vs weight setter if you run without Docker), see [CLI.md](CLI.md).
