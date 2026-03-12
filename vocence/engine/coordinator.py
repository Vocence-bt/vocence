"""
Validator engine service for Vocence.

Sets weights based on miner performance from the validator's own S3 samples bucket.
Implements winner-take-all scoring with "beat predecessors by threshold" rule.

Architecture:
- Validators submit sample metadata to API (for dashboard tracking)
- Validators upload samples to their own Hippius S3 bucket
- Validators calculate scores from their own S3 samples
- Validators set weights based on their own calculations
"""

import os
import asyncio
from typing import Dict, Any, List

import bittensor as bt
from minio import Minio
from openai import AsyncOpenAI

from vocence.domain.config import (
    API_URL,
    SUBNET_ID,
    CYCLE_LENGTH,
    CYCLE_OFFSET_BLOCKS,
    MIN_EVALS_TO_COMPETE,
    THRESHOLD_MARGIN,
    MAX_EVALS_FOR_SCORING,
    CHUTES_AUTH_KEY,
    OPENAI_AUTH_KEY,
    COLDKEY_NAME,
    HOTKEY_NAME,
    CHAIN_NETWORK,
    AUDIO_SOURCE_BUCKET,
    AUDIO_SAMPLES_BUCKET,
    VALIDATOR_ID,
    SAMPLE_SLOT_INTERVAL_BLOCKS,
    SAMPLE_SLOT_OFFSET_BLOCKS,
)
from vocence.shared.logging import emit_log, print_header
from vocence.domain.entities import ParticipantInfo
from vocence.adapters.storage import create_corpus_storage_client, create_validator_storage_client
from vocence.ranking.calculator import calculate_scores_from_samples
from vocence.pipeline.generation import generate_samples_continuously


async def fetch_participants_from_api() -> List[ParticipantInfo]:
    """Get valid participants from the centralized API.
    
    Returns:
        List of valid ParticipantInfo objects
    """
    try:
        from vocence.adapters.api import create_service_client_from_wallet
        
        client = create_service_client_from_wallet(
            wallet_name=COLDKEY_NAME,
            hotkey_name=HOTKEY_NAME,
            api_url=API_URL,
        )
        
        try:
            miners = await client.get_valid_miners()
            return miners
        finally:
            await client.close()
    except Exception as e:
        emit_log(f"Failed to get miners from API: {e}", "warn")
        return []


async def execute_cycle(
    subtensor: bt.AsyncSubtensor,
    wallet: bt.Wallet,
    storage_client: Minio,
    block: int,
) -> None:
    """Set weights based on miner performance.
    
    - Gets valid miners from centralized API
    - Calculates scores from validator's own S3 samples bucket
    - Sets weights based on own calculations
    
    Args:
        subtensor: Bittensor async subtensor instance
        wallet: Bittensor wallet for signing transactions
        storage_client: Minio client for validator's Hippius S3
        block: Current block number
    """
    emit_log(f"[{block}] Fetching participants from API", "info")
    
    try:
        participant_infos = await fetch_participants_from_api()
    except Exception as e:
        emit_log(f"[{block}] Failed to get participants from API: {e}", "error")
        return
    
    if not participant_infos:
        emit_log(f"[{block}] No participant commitments found", "warn")
        return

    # Filter to valid participants
    valid_participants = [p for p in participant_infos if p.is_valid]
    invalid_count = len(participant_infos) - len(valid_participants)

    if not valid_participants:
        emit_log(f"[{block}] No valid participants ({invalid_count} invalid)", "warn")
        return

    emit_log(f"[{block}] Found {len(valid_participants)} valid participants ({invalid_count} invalid)", "info")

    # Build participants dict for scoring
    participants = {
        p.hotkey: {"block": p.block or 0, "model_name": p.model_name, "chute_id": p.chute_id}
        for p in valid_participants
    }

    # Calculate scores from validator's own S3 bucket: most recent N evals only, valid miners only
    valid_hotkeys = set(participants.keys())
    emit_log(
        f"[{block}] Calculating scores from S3 bucket: {AUDIO_SAMPLES_BUCKET} (last {MAX_EVALS_FOR_SCORING} evals, valid miners only)",
        "info",
    )
    scores = await calculate_scores_from_samples(
        storage_client,
        max_evals=MAX_EVALS_FOR_SCORING,
        valid_hotkeys=valid_hotkeys,
    )
    
    if not scores:
        emit_log(f"[{block}] No samples found in bucket yet", "warn")
    
    # Log current scores
    for hotkey in participants:
        if hotkey in scores:
            s = scores[hotkey]
            emit_log(f"  {hotkey[:8]}: {s['wins']}/{s['total']} wins ({s['win_rate']:.1%})", "info")
        else:
            emit_log(f"  {hotkey[:8]}: no samples yet", "info")

    # Winner selection:
    # - If no eligible miners (total < MIN_EVALS_TO_COMPETE), earliest commit wins.
    # - If exactly one eligible miner, that miner wins.
    # - If multiple eligible miners, apply the existing \"beat predecessors by threshold\" rule
    #   among eligible miners only; if that finds no candidate, pick best win rate among eligible.
    ordered = sorted(participants.keys(), key=lambda hk: participants[hk]["block"])
    
    def get_total(hk: str) -> int:
        return scores.get(hk, {}).get("total", 0)
    
    def get_win_rate(hk: str) -> float:
        return scores.get(hk, {}).get("win_rate", 0.0)
    
    eligible_hks = [hk for hk in ordered if get_total(hk) >= MIN_EVALS_TO_COMPETE]

    # Case A: no eligible miners → earliest committed miner wins.
    if not eligible_hks:
        leader = ordered[0]
    # Case B: exactly one eligible miner → that miner wins.
    elif len(eligible_hks) == 1:
        leader = eligible_hks[0]
    else:
        # Case C: multiple eligible miners → apply threshold rule among eligible only.
        candidates_who_beat_all_earlier: List[str] = []
        for candidate in eligible_hks:
            candidate_rate = get_win_rate(candidate)
            beats_all = True
            for prior in ordered:
                if participants[prior]["block"] >= participants[candidate]["block"]:
                    break
                if get_total(prior) == 0:
                    continue
                prior_rate = get_win_rate(prior)
                if candidate_rate < prior_rate + THRESHOLD_MARGIN:
                    beats_all = False
                    break
            if beats_all:
                candidates_who_beat_all_earlier.append(candidate)

        if candidates_who_beat_all_earlier:
            # Among candidates, pick highest win rate, tie-break earliest block.
            leader = max(
                candidates_who_beat_all_earlier,
                key=lambda hk: (get_win_rate(hk), -participants[hk]["block"]),
            )
        else:
            # Fallback: best win rate among eligible miners, tie-break earliest block.
            leader = max(
                eligible_hks,
                key=lambda hk: (get_win_rate(hk), -participants[hk]["block"]),
            )
    
    leader_rate = get_win_rate(leader)
    emit_log(f"[{block}] Winner: {leader[:8]} win_rate={leader_rate:.1%}", "success")

    # Set weights on chain
    try:
        metagraph = await subtensor.metagraph(SUBNET_ID)
    except Exception as e:
        emit_log(f"[{block}] Failed to fetch metagraph: {e}", "error")
        return
    
    uids, weights = [], []
    for uid, hotkey in enumerate(metagraph.hotkeys):
        if hotkey in participants:
            uids.append(uid)
            weights.append(1.0 if hotkey == leader else 0.0)
    if uids:
        try:
            await subtensor.set_weights(wallet=wallet, netuid=SUBNET_ID, uids=uids, weights=weights, wait_for_inclusion=True)
            emit_log(f"[{block}] Set weights for {len(uids)} participants (winner takes all)", "success")
        except Exception as e:
            emit_log(f"[{block}] Failed to set weights: {e}", "error")


async def cycle_step(subtensor: bt.AsyncSubtensor, wallet: bt.Wallet, storage_client: Minio) -> None:
    """Wait for cycle boundary and run weight setting.
    
    Args:
        subtensor: Bittensor async subtensor instance
        wallet: Bittensor wallet for signing transactions
        storage_client: Minio client for validator's Hippius S3
    """
    current_block = await subtensor.get_current_block()
    if (current_block % CYCLE_LENGTH) != CYCLE_OFFSET_BLOCKS:
        remaining = (CYCLE_OFFSET_BLOCKS - (current_block % CYCLE_LENGTH)) % CYCLE_LENGTH
        if remaining == 0:
            remaining = CYCLE_LENGTH
        wait_time = 12 * remaining
        emit_log(f"Block {current_block}: waiting {remaining} blocks (~{wait_time}s) until cycle (offset={CYCLE_OFFSET_BLOCKS})", "info")
        await asyncio.sleep(wait_time)
        return

    # Cycle at block % CYCLE_LENGTH == CYCLE_OFFSET_BLOCKS (e.g. 165, 315, 465, ...)
    cycle_num = (current_block - CYCLE_OFFSET_BLOCKS) // CYCLE_LENGTH
    print_header(f"Vocence Cycle #{cycle_num} (block {current_block})")
    emit_log(f"Weight-setting cycle (every {CYCLE_LENGTH} blocks, offset {CYCLE_OFFSET_BLOCKS})", "info")
    try:
        await execute_cycle(subtensor, wallet, storage_client, current_block)
    except Exception as e:
        emit_log(f"[{current_block}] Cycle failed ({e}), will retry next cycle", "error")
        import traceback
        traceback.print_exc()
    else:
        # Wait at least one block so next cycle_step doesn't re-run for the same block
        await asyncio.sleep(12)


async def main() -> None:
    """Main entry point for the validator."""
    print_header("Vocence Validator Starting")
    
    # Check required environment variables
    if not CHUTES_AUTH_KEY:
        emit_log("CHUTES_AUTH_KEY environment variable required", "error")
        return
    if not OPENAI_AUTH_KEY:
        emit_log("OPENAI_AUTH_KEY environment variable required", "error")
        return
    
    emit_log(f"Using centralized API for miners: {API_URL}", "info")
    emit_log(f"Using corpus bucket (read) and own samples bucket for scoring: {AUDIO_SAMPLES_BUCKET}", "info")
    
    # Initialize clients (validator: two Hippius credential sets)
    emit_log("Initializing clients...", "info")
    subtensor = bt.AsyncSubtensor(network=CHAIN_NETWORK)
    wallet = bt.Wallet(name=COLDKEY_NAME, hotkey=HOTKEY_NAME)
    corpus_client = create_corpus_storage_client()
    validator_client = create_validator_storage_client()
    openai_client = AsyncOpenAI(api_key=OPENAI_AUTH_KEY)
    
    # Log configuration
    emit_log(f"Wallet: {COLDKEY_NAME}/{HOTKEY_NAME}", "info")
    emit_log(f"Network: {CHAIN_NETWORK}", "info")
    emit_log(f"Subnet ID: {SUBNET_ID}", "info")
    emit_log(f"Cycle length: {CYCLE_LENGTH} blocks, offset {CYCLE_OFFSET_BLOCKS} (~{CYCLE_LENGTH * 12}s)", "info")
    emit_log(f"Sample slots: every {SAMPLE_SLOT_INTERVAL_BLOCKS} blocks at offset {SAMPLE_SLOT_OFFSET_BLOCKS} (validator_id={VALIDATOR_ID})", "info")
    emit_log(f"Corpus bucket (read): s3://{AUDIO_SOURCE_BUCKET}", "info")
    emit_log(f"Samples bucket (own): s3://{AUDIO_SAMPLES_BUCKET}", "info")
    emit_log(f"Min evals to compete: {MIN_EVALS_TO_COMPETE}", "info")
    emit_log(f"Threshold margin: {THRESHOLD_MARGIN}", "info")
    emit_log(f"Max evals for scoring (recent window): {MAX_EVALS_FOR_SCORING}", "info")
    
    emit_log("Starting sample generation loop in background...", "start")
    generator_task = asyncio.create_task(
        generate_samples_continuously(corpus_client, validator_client, openai_client, subtensor.get_current_block)
    )
    
    def handle_generator_exception(task: asyncio.Task) -> None:
        """Handle exceptions from the background generator task."""
        try:
            exc = task.exception()
            if exc is not None:
                emit_log(f"Background generator task failed: {exc}", "error")
        except asyncio.CancelledError:
            emit_log("Background generator task was cancelled", "warn")
    
    generator_task.add_done_callback(handle_generator_exception)
    
    emit_log("Starting weight setting loop...", "start")
    while True:
        await cycle_step(subtensor, wallet, validator_client)


def main_sync() -> None:
    """Synchronous entry point for CLI."""
    asyncio.run(main())

