#!/usr/bin/env python3
"""Analyze random 5-second clips from bee hive recordings and append results.

Expected filename format: <apiary>_<hive>_<apiary>_<hive>_<yyyy>_<mm>_<dd>_<mic>.wav
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Iterable

import librosa
import numpy as np
import pandas as pd
import soundfile as sf
from scipy.signal import welch

CLIP_DURATION_S = 5.0
SAMPLE_RATE = 44100
DEFAULT_NUM_CLIPS = 58

FILENAME_RE = re.compile(
    r"^(?P<apiary_1>[^_]+)_(?P<hive_1>[^_]+)_(?P<apiary_2>[^_]+)_(?P<hive_2>[^_]+)"
    r"_(?P<year>\d{4})_(?P<month>\d{2})_(?P<day>\d{2})_(?P<mic>0[12])$"
)


@dataclass(frozen=True)
class ClipMetadata:
    apiary: str
    colony: str
    date: str
    microphone: int
    year: int
    month: int
    day: int
    seed: int
    clip_start_s: float


@dataclass(frozen=True)
class ClipFeatures:
    f0: float
    f1: float
    f2: float
    f3: float
    bp1: float
    bp2: float
    bp3: float
    bp4: float
    h2re: float
    f1vf0: float
    f2vf0: float
    f3vf0: float
    nihvl: float
    nihvlm: float
    interpretation: str


def parse_filename(path: str) -> tuple[str, str, str, int, int, int, int]:
    base = os.path.splitext(os.path.basename(path))[0]
    match = FILENAME_RE.match(base)
    if not match:
        raise ValueError(
            "Filename must match '<apiary>_<hive>_<apiary>_<hive>_<yyyy>_<mm>_<dd>_<mic>.wav'. "
            f"Got: {os.path.basename(path)}"
        )
    # New naming convention: ignore the first apiary/hive pair, use the second.
    apiary = match.group("apiary_2")
    colony = match.group("hive_2")
    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))
    microphone = int(match.group("mic"))
    date = f"{year:04d}-{month:02d}-{day:02d}"
    return apiary, colony, date, microphone, year, month, day


def random_start_times(duration_s: float, num_clips: int, seed: int) -> np.ndarray:
    max_start = max(0.0, duration_s - CLIP_DURATION_S)
    rng = np.random.default_rng(seed)
    return rng.uniform(0.0, max_start, size=num_clips)


def band_power(freqs: np.ndarray, psd: np.ndarray, fmin: float, fmax: float) -> float:
    mask = (freqs >= fmin) & (freqs < fmax)
    if not np.any(mask):
        return float("nan")
    return float(np.trapz(psd[mask], freqs[mask]))


def harmonic_peak(freqs: np.ndarray, psd: np.ndarray, target: float, rel_band: float = 0.05) -> float:
    if not np.isfinite(target) or target <= 0:
        return float("nan")
    low = target * (1.0 - rel_band)
    high = target * (1.0 + rel_band)
    mask = (freqs >= low) & (freqs <= high)
    if not np.any(mask):
        return float("nan")
    local_freqs = freqs[mask]
    local_psd = psd[mask]
    return float(local_freqs[np.argmax(local_psd)])


def harmonic_energy(freqs: np.ndarray, psd: np.ndarray, target: float, rel_band: float = 0.05) -> float:
    if not np.isfinite(target) or target <= 0:
        return 0.0
    low = target * (1.0 - rel_band)
    high = target * (1.0 + rel_band)
    mask = (freqs >= low) & (freqs <= high)
    if not np.any(mask):
        return 0.0
    return float(np.trapz(psd[mask], freqs[mask]))


def estimate_features(
    y: np.ndarray,
    sr: int,
    h2re_cutoff: float,
    nihvl_cutoff: float,
) -> ClipFeatures:
    f0_series = librosa.yin(y, fmin=60, fmax=1200, sr=sr)
    f0_series = f0_series[np.isfinite(f0_series)]
    f0 = float(np.nanmedian(f0_series)) if f0_series.size else float("nan")

    freqs, psd = welch(y, fs=sr, nperseg=2048)

    f1_target = f0 * 2.0
    f2_target = f0 * 3.0
    f3_target = f0 * 4.0

    f1 = harmonic_peak(freqs, psd, f1_target)
    f2 = harmonic_peak(freqs, psd, f2_target)
    f3 = harmonic_peak(freqs, psd, f3_target)

    bp1 = band_power(freqs, psd, 80, 250)
    bp2 = band_power(freqs, psd, 250, 450)
    bp3 = band_power(freqs, psd, 450, 650)
    bp4 = band_power(freqs, psd, 650, 1200)

    harmonic_total = sum(
        harmonic_energy(freqs, psd, target)
        for target in (f0, f1_target, f2_target, f3_target)
    )
    total_energy = float(np.trapz(psd, freqs))
    residual_energy = max(total_energy - harmonic_total, 0.0)
    h2re = float("nan") if residual_energy == 0 else harmonic_total / residual_energy

    f1vf0 = float("nan") if f0 == 0 else f1 / f0
    f2vf0 = float("nan") if f0 == 0 else f2 / f0
    f3vf0 = float("nan") if f0 == 0 else f3 / f0

    nihvl = float("nan") if bp1 == 0 else bp4 / bp1
    nihvlm = float("nan") if (bp1 + bp2) == 0 else bp4 / (bp1 + bp2)

    h2re_high = h2re >= h2re_cutoff
    nihvl_high = nihvl >= nihvl_cutoff

    if not h2re_high and not nihvl_high:
        interpretation = "weak, organized"
    elif h2re_high and not nihvl_high:
        interpretation = "coordinated, stable"
    elif not h2re_high and nihvl_high:
        interpretation = "disrupted, agitated"
    else:
        interpretation = "coordinated, energetic"

    return ClipFeatures(
        f0=f0,
        f1=f1,
        f2=f2,
        f3=f3,
        bp1=bp1,
        bp2=bp2,
        bp3=bp3,
        bp4=bp4,
        h2re=h2re,
        f1vf0=f1vf0,
        f2vf0=f2vf0,
        f3vf0=f3vf0,
        nihvl=nihvl,
        nihvlm=nihvlm,
        interpretation=interpretation,
    )


def analyze_file(
    path: str,
    num_clips: int,
    seed: int | None,
    h2re_cutoff: float,
    nihvl_cutoff: float,
) -> list[dict[str, object]]:
    apiary, colony, date, microphone, year, month, day = parse_filename(path)
    info = sf.info(path)
    duration_s = info.frames / info.samplerate

    if seed is None:
        seed = int.from_bytes(os.urandom(4), "little")

    starts = random_start_times(duration_s, num_clips, seed)

    rows: list[dict[str, object]] = []
    for start in starts:
        y, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True, offset=float(start), duration=CLIP_DURATION_S)
        metadata = ClipMetadata(
            apiary=apiary,
            colony=colony,
            date=date,
            microphone=microphone,
            year=year,
            month=month,
            day=day,
            seed=seed,
            clip_start_s=float(start),
        )
        features = estimate_features(y, SAMPLE_RATE, h2re_cutoff, nihvl_cutoff)
        rows.append({**metadata.__dict__, **features.__dict__})

    return rows


def read_existing(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path):
        return None
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_excel(path)


def write_output(path: str, rows: Iterable[dict[str, object]]) -> None:
    df_new = pd.DataFrame(rows)
    df_existing = read_existing(path)
    if df_existing is not None:
        df_new = pd.concat([df_existing, df_new], ignore_index=True)

    if "clip_start_s" in df_new.columns:
        df_new = df_new.sort_values("clip_start_s", ascending=True).reset_index(drop=True)

    if "clip_start_s" in df_new.columns:
        df_new["clip_start_s"] = df_new["clip_start_s"].round(3)

    integer_columns = ("f0", "f1", "f2", "f3")
    for column in integer_columns:
        if column in df_new.columns:
            df_new[column] = df_new[column].round(0)

    two_decimal_columns = (
        "bp1",
        "bp2",
        "bp3",
        "bp4",
        "h2re",
        "f1vf0",
        "f2vf0",
        "f3vf0",
        "nihvl",
        "nihvlm",
    )
    for column in two_decimal_columns:
        if column in df_new.columns:
            df_new[column] = df_new[column].round(2)

    if path.lower().endswith(".csv"):
        df_new.to_csv(path, index=False)
    else:
        df_new.to_excel(path, index=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav_files", nargs="+", help="Paths to WAV files to analyze")
    parser.add_argument("--output", default=None, help="Output Excel/CSV file")
    parser.add_argument("--num-clips", type=int, default=DEFAULT_NUM_CLIPS)
    parser.add_argument("--seed", type=int, default=None, help="Seed for random clip selection")
    parser.add_argument("--h2re-cutoff", type=float, default=0.0)
    parser.add_argument("--nihvl-cutoff", type=float, default=1.0)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.output is None:
        apiary, colony, *_ = parse_filename(args.wav_files[0])
        filename = f"SoundAnalysis_{apiary}_{colony}.xlsx"
        output_path = os.path.join(os.path.expanduser("~"), "Desktop", filename)
    else:
        output_path = os.path.expanduser(args.output)
    all_rows: list[dict[str, object]] = []
    for wav in args.wav_files:
        all_rows.extend(
            analyze_file(
                wav,
                num_clips=args.num_clips,
                seed=args.seed,
                h2re_cutoff=args.h2re_cutoff,
                nihvl_cutoff=args.nihvl_cutoff,
            )
        )

    write_output(output_path, all_rows)
    abs_output_path = os.path.abspath(output_path)
    if not os.path.exists(abs_output_path):
        raise FileNotFoundError(f"Output file was not created: {abs_output_path}")
    file_size_kb = os.path.getsize(abs_output_path) / 1024
    print(
        "Analysis complete. Results saved to: "
        f"{abs_output_path} ({file_size_kb:.1f} KB).",
        file=sys.stderr,
        flush=True,
    )


if __name__ == "__main__":
    main()
