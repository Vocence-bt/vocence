# Validator setup guide

This guide covers running a Vocence validator, including optional process management with **PM2** (two processes: sample generator and weight setter).

---

## Prerequisites

- **From the Vocence team:** Chutes permission, owner API URL (`API_URL`), Hippius corpus + validator keys.
- **Your side:** Bittensor wallet (coldkey + hotkey), `.env` configured (see [README](../README.md#validator-quick-start)).

---

## Option A: Single process (`vocence serve`)

Run both sample generation and weight setting in one process:

```bash
cd /path/to/vocence
uv sync
uv run vocence serve
```

Good for local or single-instance runs. For production, Option B (PM2) is recommended.

---

## Option B: Two processes with PM2 (recommended)

Run the **sample generator** and **weight setter** as separate PM2 processes so you can scale, restart, and monitor them independently.

### 1. Install PM2

PM2 is a process manager for Node.js; the Vocence CLI runs under it via `uv run vocence`.

**Install Node.js (if needed)** — PM2 requires Node:

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y nodejs npm

# Or use nvm (https://github.com/nvm-sh/nvm)
# nvm install --lts && nvm use --lts
```

**Install PM2 globally:**

```bash
sudo npm install -g pm2
```

Verify:

```bash
pm2 --version
```

### 2. Run the two validator processes

From your Vocence repo directory (where `.env` and `uv` are):

**Process 1 — Sample generator** (corpus → miners → eval → upload):

```bash
cd /path/to/vocence
pm2 start "uv run vocence services generator" --name vocence-generator
```

**Process 2 — Weight setter** (reads samples bucket, sets weights on chain):

```bash
pm2 start "uv run vocence services validator" --name vocence-validator
```

Both use the same `.env` in the current working directory. Ensure `LOG_DIR` is set if you want daily log files (e.g. `LOG_DIR=logs`).

### 3. Using an ecosystem file (optional)

To start both with one command and persist options, use the provided ecosystem config:

```bash
cd /path/to/vocence
pm2 start ecosystem.config.cjs
```

This starts `vocence-generator` and `vocence-validator` with cwd set to the repo. Logging level is set to **INFO** so you see all logs in `pm2 logs`. Edit `ecosystem.config.cjs` if your path or env differs.

### 4. Useful PM2 commands

| Command | Description |
|--------|-------------|
| `pm2 list` | List processes (vocence-generator, vocence-validator) |
| `pm2 logs` | Stream logs from all processes |
| `pm2 logs vocence-generator` | Logs for generator only |
| `pm2 logs vocence-validator` | Logs for weight setter only |
| `pm2 restart vocence-generator` | Restart generator |
| `pm2 stop vocence-validator` | Stop weight setter |
| `pm2 delete vocence-generator` | Remove from PM2 (stops if running) |
| `pm2 save` | Save process list (survives reboot if you set up startup) |
| `pm2 startup` | Print command to enable PM2 on boot (run the printed command as instructed) |

After `pm2 save` and `pm2 startup`, your two processes will restart on server reboot.

---

## Summary

| Process | CLI command | Role |
|--------|-------------|------|
| **Generator** | `vocence services generator` | Block-based sample generation: fetch audio, query miners, OpenAI eval, upload to your samples bucket. |
| **Validator** | `vocence services validator` | Weight setting: every 150 blocks, read scores from your bucket, set weights on chain. |

Both need the same `.env` (wallet, Hippius, Chutes, API_URL, etc.). Run them in the same directory so `uv run vocence` and `.env` resolve correctly.

For full CLI reference, see [CLI.md](CLI.md).
