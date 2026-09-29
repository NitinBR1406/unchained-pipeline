"""Reproduce bounded detector diagnostics; never reads production media or renders."""
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "p0e4/evidence/claude_dispatch_beat_recovery_v01_execution/detector/clip_fx.py"
EXPECTED_SHA = "04fa93aff2847eaa9ae7b8542192ca37892c46b6b149c5235360a5c14abe3e97"

def main():
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA:
        raise RuntimeError("detector identity mismatch; do not test substituted code")
    spec = importlib.util.spec_from_file_location("recovered_detector", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sample_rate = module.SR
    signal = np.zeros(sample_rate * 4, dtype=np.float32)
    original_decoder = module._read_mono
    module._read_mono = lambda _: signal
    try:
        legacy = module.detect_hits("synthetic-memory")
        detailed = module.detect_hits_detailed("synthetic-memory")
        for onset in (0.5, 1.5, 2.5):
            n = np.arange(int(0.12 * sample_rate))
            burst = (0.8 * np.sin(2 * np.pi * 60 * n / sample_rate)
                     * np.exp(-n / (0.03 * sample_rate))).astype(np.float32)
            start = int(onset * sample_rate)
            signal[start:start + len(burst)] += burst
        bursts = module.detect_hits_detailed("synthetic-memory")
    finally:
        module._read_mono = original_decoder
    print(json.dumps({
        "detector_sha256": digest,
        "legacy_silence": legacy,
        "detailed_silence": detailed,
        "synthetic_60hz_bursts_expected_s": [0.5, 1.5, 2.5],
        "synthetic_60hz_bursts_observed": bursts,
        "real_music_tested": False,
        "decoder_tested": False,
        "resolve_tested": False,
    }, indent=2))

if __name__ == "__main__":
    main()
