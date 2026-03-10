# Validator setup guide (Docker + Watchtower)

This guide covers running a Vocence validator using **Docker** and **Watchtower**. The same image is built and published by the team via CI/CD; validators run that image and auto-update when a new one is pushed.

---

## Prerequisites

- **From the Vocence team:** Chutes permission, owner API URL (`API_URL`), Hippius corpus + validator keys.
- **Your side:** Bittensor wallet (coldkey + hotkey), Docker and Docker Compose installed.

---

## 0. Install Docker and Docker Compose

You need Docker and Docker Compose on the machine that will run the validator.

### Ubuntu / Debian (easiest)

Use Docker’s official script (installs Engine + Compose plugin, avoids repo conflicts):

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

Add your user to the `docker` group so you can run Docker without `sudo`:

```bash
sudo usermod -aG docker $USER
# Log out and back in (or reboot) for the group change to take effect
```

Verify:

```bash
docker --version
docker compose version
```

### If you prefer manual APT install

If the Docker repo is **already** on your system (e.g. from a previous install), you can just install the packages:

```bash
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

If you see a **Signed-By conflict** (`/usr/share/keyrings/docker.asc != /etc/apt/keyrings/docker.asc`), remove the duplicate Docker list file so only one key path is used, then run the commands above:

```bash
sudo rm -f /etc/apt/sources.list.d/docker.list
# If the repo was only in that file, re-add it from https://docs.docker.com/engine/install/ubuntu/
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Other Linux / macOS / Windows

- **Linux (other distros):** [Install Docker Engine](https://docs.docker.com/engine/install/)
- **macOS:** [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/) (includes Compose)
- **Windows:** [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) (includes Compose)

Use `docker compose` (with a space) as in this guide; it’s the Compose V2 plugin. If you have the older `docker-compose` (with a hyphen), that works too.

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
docker compose up -d
```

- **Validator:** Docker pulls the image from Docker Hub (e.g. `vocence102/vocence:latest`) if it isn’t already on your machine, then runs it (`vocence serve` — sample generation + weight setting in one process).
- **Watchtower:** Polls Docker Hub every 5 minutes; when the team pushes a new image, it pulls and restarts the validator so you stay up to date without manual steps.

### Overriding the image (optional)

Validators normally use `vocence102/vocence:latest`; the dev team’s CI pushes every new build as `latest`, and Watchtower updates you automatically. Override only if the team gives you a different image name:

```bash
DOCKER_IMAGE=vocence102/vocence:latest
```

Then run `docker compose up -d` as above.

---

## 3. Logs and health

- **Stream logs (stdout):**  
  `docker compose logs -f validator`
- **Daily log files:**  
  All application logs are written daily (UTC) into the **`logs/`** directory in your project folder. Files are named `vocence_YYYY-MM-DD.log`. The compose file mounts `./logs` into the container, so you can read them on the host (e.g. `tail -f logs/vocence_2025-02-28.log`). If the container cannot write logs, create the directory and give the container user access: `mkdir -p logs && sudo chown 1000:1000 logs`.
- **Watchtower logs:**  
  `docker compose logs -f watchtower`
- **Restart validator only:**  
  `docker compose restart validator`
- **Stop everything:**  
  `docker compose down`

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
| Run validator | `docker compose up -d` (uses published image + your `.env` and wallets). |
| Updates | Automatic via Watchtower when the team pushes a new image. |
| Logs (stream) | `docker compose logs -f validator` |
| Logs (daily files) | `logs/vocence_YYYY-MM-DD.log` in the project directory. |
| Config | `.env` and `~/.bittensor/wallets` on the host. |

For the full CI/CD flow (how the image is built and published), see [cicd-pipeline.md](cicd-pipeline.md). For CLI options (e.g. split generator vs weight setter if you run without Docker), see [CLI.md](CLI.md).
