# Changelog

All notable changes to the Vocence subnet codebase are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.1.0] - 2025-02-28

### Added

- **Voice intelligence subnet (Q1: PromptTTS)**  
  Bittensor subnet for development and evaluation of voice intelligence models (PromptTTS, STT, STS, voice cloning, etc.). Initial release focuses on PromptTTS: miners deploy models that generate speech from text + voice-trait instructions; validators score content correctness, audio quality, and prompt adherence.

- **Validator**
  - Sample generation loop: download audio from corpus, get transcription + voice traits via GPT audio model, query miners (Chutes `/speak`), run forced-choice evaluation, upload results to validator’s Hippius bucket.
  - Weight-setting loop: every `CYCLE_LENGTH` blocks, compute scores from last `MAX_EVALS_FOR_SCORING` evaluations, apply winner-take-all with “beat predecessors by threshold” rule, set weights on chain.
  - Defaults: sample every 10 minutes (`ASSESSMENT_INTERVAL=600`), scoring window 50 evals (`MAX_EVALS_FOR_SCORING=50`), miner must have more than 35 evals in window to be eligible (`MIN_EVALS_TO_COMPETE=36`).

- **Miner**
  - CLI: `vocence miner push` (deploy to Chutes), `vocence miner commit` (commit model + chute ID to chain). Optional `--network` and `--netuid` to override .env.
  - Canonical wrapper template (`chute_template/vocence_chute.py.jinja2`) and miner sample guide. Chute ID must contain the word `vocence` for owner validation.

- **Owner / centralized API**
  - HTTP API: participants (valid miners), evaluations submission, metrics, blocklist, status. Background workers: participant validation (HuggingFace + Chutes + wrapper integrity), metrics calculation.
  - Source audio downloader: LibriVox clips (20–25s, capped to validator max), upload to corpus bucket. Clip duration capped so validator never sees >25s.

- **Configuration**
  - Single config module (`vocence.domain.config`): loads `.env` on import, all defaults in one place. Mainnet default subnet 102; testnet subnet set via .env (`NETUID=XXX`).

### Changed

- N/A (initial release)

### Fixed

- N/A (initial release)

---

[0.1.0]: https://github.com/Vocence-bt/vocence/releases/tag/v0.1.0
