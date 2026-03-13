"""
Configuration settings for Vocence validator.

All configurable values are loaded from environment variables (.env or process env)
with sensible defaults defined here. Load .env first so imports see env vars.
"""

import os
from pathlib import Path
from typing import List

# Load .env from current working directory (or parents) so all config below sees it
def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(Path.cwd() / ".env")
        load_dotenv()  # also discover .env in cwd/parents
    except ImportError:
        pass


_load_env()

# Bittensor network configuration
# NETWORK / CHAIN_NETWORK: finney (mainnet), test (testnet), or local
# NETUID / SUBNET_ID: subnet id (default 102 mainnet; for testnet set NETWORK=test and NETUID=XXX in .env)
CHAIN_NETWORK = os.environ.get("CHAIN_NETWORK") or os.environ.get("NETWORK", "finney")
SUBNET_ID = int(os.environ.get("SUBNET_ID") or os.environ.get("NETUID", "102"))
CYCLE_LENGTH = int(os.environ.get("CYCLE_LENGTH", "150"))  # Set weights every 150 blocks (~30 minutes)
# Block % CYCLE_LENGTH == CYCLE_OFFSET_BLOCKS → run (e.g. 15 → blocks 165, 315, 465, ...)
CYCLE_OFFSET_BLOCKS = int(os.environ.get("CYCLE_OFFSET_BLOCKS", "15"))
# Allow execution when block is within ±N of the exact cycle/slot block (avoids missing due to transient failures)
CYCLE_BLOCK_TOLERANCE = int(os.environ.get("CYCLE_BLOCK_TOLERANCE", "2"))
SAMPLE_SLOT_BLOCK_TOLERANCE = int(os.environ.get("SAMPLE_SLOT_BLOCK_TOLERANCE", "2"))
# Timeout for subtensor RPC (get_current_block, metagraph, set_weights); prevents hanging forever if connection drops
SUBTENSOR_TIMEOUT_SEC = int(os.environ.get("SUBTENSOR_TIMEOUT_SEC", "60"))
QUERY_TIMEOUT = int(os.environ.get("QUERY_TIMEOUT", "300"))

# Assessment configuration
ASSESSMENT_INTERVAL = int(os.environ.get("ASSESSMENT_INTERVAL", "600"))  # Legacy; sample timing is block-based when subtensor is used
# Block-based sample slots: validators send tasks every SAMPLE_SLOT_INTERVAL_BLOCKS; offset staggers 5 validators (id 0->0, 1->30, 2->60, 3->90, 4->120).
VALIDATOR_ID = int(os.environ.get("VALIDATOR_ID", "1"))  # 0–4 for staggered slots; default 1
SAMPLE_SLOT_INTERVAL_BLOCKS = int(os.environ.get("SAMPLE_SLOT_INTERVAL_BLOCKS", "150"))
# Derived: block % INTERVAL == this value → run sample round
SAMPLE_SLOT_OFFSET_BLOCKS = (VALIDATOR_ID % 6) * 25  # 0, 25, 50, 75, 100, 125
MIN_EVALS_TO_COMPETE = int(os.environ.get("MIN_EVALS_TO_COMPETE", "40"))  # Miner must have more than 35 evals in the scoring window to be eligible
THRESHOLD_MARGIN = float(os.environ.get("THRESHOLD_MARGIN", "0.05"))
# Most recent N evaluations used for scoring (validator S3 + owner metrics). Default 50.
MAX_EVALS_FOR_SCORING = int(os.environ.get("MAX_EVALS_FOR_SCORING", "50"))

# Chutes API configuration
CHUTES_BASE_URL = os.environ.get("CHUTES_BASE_URL", "https://api.chutes.ai")
CHUTES_AUTH_KEY = os.environ.get("CHUTES_AUTH_KEY") or os.environ.get("CHUTES_API_KEY")

# Wallet configuration
COLDKEY_NAME = os.environ.get("COLDKEY_NAME") or os.environ.get("WALLET_NAME", "default")
HOTKEY_NAME = os.environ.get("HOTKEY_NAME", "default")

# Hippius S3 configuration (https://console.hippius.com/dashboard/settings)
#
# Owner (centralized service): one credential set for corpus bucket (upload source audio).
# Validator: two credential sets — corpus (read owner's bucket via owner-provided sub_key)
# and validator's own (samples bucket, DB-related storage).
#
# Validator identity: used to build the validator's samples bucket name (e.g. audio-samples-rt21, audio-samples-yuma).
# Set VALIDATOR_NAME in .env (e.g. rt21, yuma); validators typically set this.
VALIDATOR_NAME = (os.environ.get("VALIDATOR_NAME", "default").strip().lower().replace("_", "-") or "default")

# Bucket names (shared)
AUDIO_SOURCE_BUCKET = os.environ.get("HIPPIUS_AUDIO_SOURCE_BUCKET", "audio-corpus")  # Corpus (owner writes, validators read)
# Validator's own bucket: derived from VALIDATOR_NAME unless overridden (e.g. audio-samples-rt21, audio-samples-yuma).
AUDIO_SAMPLES_BUCKET = os.environ.get("HIPPIUS_AUDIO_SAMPLES_BUCKET") or f"audio-samples-{VALIDATOR_NAME}"

# Owner: single set for corpus bucket (used by source-downloader CLI)
HIPPIUS_OWNER_ACCESS_KEY = os.environ.get("HIPPIUS_OWNER_ACCESS_KEY") or os.environ.get("HIPPIUS_ACCESS_KEY", "")
HIPPIUS_OWNER_SECRET_KEY = os.environ.get("HIPPIUS_OWNER_SECRET_KEY") or os.environ.get("HIPPIUS_SECRET_KEY", "")

# Validator: corpus access (owner-provided sub_key, read-only for corpus bucket)
HIPPIUS_CORPUS_ACCESS_KEY = os.environ.get("HIPPIUS_CORPUS_ACCESS_KEY", "")
HIPPIUS_CORPUS_SECRET_KEY = os.environ.get("HIPPIUS_CORPUS_SECRET_KEY", "")

# Validator: validator's own credentials (samples bucket, uploads, etc.)
HIPPIUS_VALIDATOR_ACCESS_KEY = os.environ.get("HIPPIUS_VALIDATOR_ACCESS_KEY") or os.environ.get("HIPPIUS_ACCESS_KEY", "")
HIPPIUS_VALIDATOR_SECRET_KEY = os.environ.get("HIPPIUS_VALIDATOR_SECRET_KEY") or os.environ.get("HIPPIUS_SECRET_KEY", "")

# Legacy (deprecated): use OWNER_* or VALIDATOR_* / CORPUS_* depending on role
HIPPIUS_ACCESS_KEY = HIPPIUS_OWNER_ACCESS_KEY  # backward compat; validator code uses create_*_storage_client()
HIPPIUS_SECRET_KEY = HIPPIUS_OWNER_SECRET_KEY

# OpenAI configuration (OPENAI_AUTH_KEY or OPENAI_API_KEY from .env)
OPENAI_AUTH_KEY = os.environ.get("OPENAI_AUTH_KEY") or os.environ.get("OPENAI_API_KEY")
# Model for audio-in description and comparison (transcription + traits, first/second choice)
GPT_AUDIO_MODEL = os.environ.get("GPT_AUDIO_MODEL", "gpt-4o-audio-preview")

# Audio generation placeholder model
PLACEHOLDER_TTS_ENDPOINT = os.environ.get(
    "PLACEHOLDER_TTS_ENDPOINT",
    "https://chutes-wan-2-2-tts-14b-fast.chutes.ai/synthesize"
)

# Audio processing settings
MIN_AUDIO_SIZE = int(os.environ.get("MIN_AUDIO_SIZE", "100000"))  # 0.1MB minimum
MAX_AUDIO_SIZE = int(os.environ.get("MAX_AUDIO_SIZE", "10000000"))  # 10MB maximum
CLIP_LENGTH_SECONDS = int(os.environ.get("CLIP_LENGTH_SECONDS", "20"))  # seconds

# Validator: required duration range for source audio from corpus (skip if outside range)
AUDIO_SOURCE_MIN_DURATION_SEC = int(os.environ.get("AUDIO_SOURCE_MIN_DURATION_SEC", "20"))
AUDIO_SOURCE_MAX_DURATION_SEC = int(os.environ.get("AUDIO_SOURCE_MAX_DURATION_SEC", "25"))

# Track recently used audio to avoid repeats (in-memory)
USED_AUDIO_FILES: List[str] = []
MAX_AUDIO_HISTORY = int(os.environ.get("MAX_AUDIO_HISTORY", "50"))

# Chute endpoint resolution
CHUTE_INFO_CACHE_TTL = int(os.environ.get("CHUTE_INFO_CACHE_TTL", "300"))  # 5 minutes
# Max concurrent requests to miners' chutes per round. Raise for more miners (e.g. 20); lower if you hit rate limits.
MAX_PARALLEL_MINERS = int(os.environ.get("MAX_PARALLEL_MINERS", "20"))
# Max concurrent OpenAI evaluations (forced-choice) per round. Lower if you hit OpenAI rate limits.
MAX_PARALLEL_EVALS = int(os.environ.get("MAX_PARALLEL_EVALS", "4"))

# Validator: optional local copy of metadata before uploading to Hippius (default: disabled)
# Only when VALIDATOR_SAVE_LOCAL_SAMPLES is true AND VALIDATOR_LOCAL_SAMPLES_DIR is set do we create the dir and save.
_validator_save_local = (os.environ.get("VALIDATOR_SAVE_LOCAL_SAMPLES", "false").strip().lower() in ("1", "true", "yes"))
_validator_local_dir = (os.environ.get("VALIDATOR_LOCAL_SAMPLES_DIR", "").strip() or None)
VALIDATOR_SAVE_LOCAL_SAMPLES = _validator_save_local and bool(_validator_local_dir)
VALIDATOR_LOCAL_SAMPLES_DIR = _validator_local_dir if VALIDATOR_SAVE_LOCAL_SAMPLES else None

# Database configuration
DB_CONNECTION_STRING = os.environ.get("DB_CONNECTION_STRING")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "vocence")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "vocence")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "vocence")
DATABASE_ECHO = (os.environ.get("DATABASE_ECHO", "").lower() == "true")

# Owner/validator API client (validators and generator call owner API)
API_URL = os.environ.get("API_URL", "http://localhost:8000")
API_TIMEOUT = int(os.environ.get("API_TIMEOUT", "30"))
API_MAX_RETRIES = int(os.environ.get("API_MAX_RETRIES", "3"))

# HTTP service (owner API server)
SERVICE_HOST = os.environ.get("SERVICE_HOST", "0.0.0.0")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", "8031"))
SERVICE_RELOAD = (os.environ.get("SERVICE_RELOAD", "").lower() == "true")

# Serve process logs: daily .log files (UTC), one file per day. Set to empty to disable file logging.
LOG_DIR = os.environ.get("LOG_DIR", "logs")

# Background worker intervals (seconds)
PARTICIPANT_VALIDATION_INTERVAL = int(os.environ.get("PARTICIPANT_VALIDATION_INTERVAL", "300"))
METRICS_CALCULATION_INTERVAL = int(os.environ.get("METRICS_CALCULATION_INTERVAL", "300"))

# Auth (owner API)
SIGNATURE_EXPIRY_SECONDS = int(os.environ.get("SIGNATURE_EXPIRY_SECONDS", "300"))
ADMIN_HOTKEYS = [x.strip() for x in os.environ.get("ADMIN_HOTKEYS", "").split(",") if x.strip()]

# HuggingFace configuration
HF_AUTH_TOKEN = os.environ.get("HF_AUTH_TOKEN")
MODEL_FINGERPRINT_CACHE_TTL = int(os.environ.get("MODEL_FINGERPRINT_CACHE_TTL", "3600"))  # 1 hour

# Source audio downloader (LibriVox only)
AUDIO_CORPUS_MAX_ENTRIES = int(os.environ.get("AUDIO_CORPUS_MAX_ENTRIES", "1000000"))  # Max clips in corpus; prune oldest when exceeded
AUDIO_CORPUS_MANIFEST_PATH = os.environ.get(
    "AUDIO_CORPUS_MANIFEST_PATH",
    os.path.join(os.getcwd(), "data", "audio_corpus_manifest.json"),
)
SOURCE_AUDIO_DOWNLOAD_INTERVAL = int(os.environ.get("SOURCE_AUDIO_DOWNLOAD_INTERVAL", "60"))  # Seconds between rounds
LIBRIVOX_CLIPS_PER_CHAPTER = int(os.environ.get("LIBRIVOX_CLIPS_PER_CHAPTER", "10"))
LIBRIVOX_CLIP_MIN_SEC = int(os.environ.get("LIBRIVOX_CLIP_MIN_SEC", "20"))
LIBRIVOX_CLIP_MAX_SEC = int(os.environ.get("LIBRIVOX_CLIP_MAX_SEC", "25"))

