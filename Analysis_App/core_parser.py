import glob
import re
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from core_events import Event

# -------------------------
# Regex principais
# -------------------------
TS_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s+(.*)$")

FPGA_RE = re.compile(
    r"\[FPGA\]\s+T=(?P<T>-?\d+(?:\.\d+)?)°C\s+VCCINT=(?P<VCCINT>-?\d+(?:\.\d+)?)V"
)
STM32_RE = re.compile(
    r"\[STM32\]\s+Vc=(?P<Vc>-?\d+(?:\.\d+)?)V\s+Vi=(?P<Vi>-?\d+(?:\.\d+)?)V\s+Io=(?P<Io>-?\d+(?:\.\d+)?)A\s+T=(?P<T>-?\d+(?:\.\d+)?)°C"
)

# Eventos
BITSTREAM_HEADER_RE = re.compile(r"^BITSTREAM TRANSITION @ (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})$")
BITSTREAM_FROM_RE = re.compile(r"^\s*From:\s*(.+?)\s*(?:\(|$)")
BITSTREAM_TO_RE = re.compile(r"^\s*To:\s*(.+?)\s*(?:\(|$)")

START_PROG_RE = re.compile(r"▶\s*Starting FPGA Programming\s*\[(.+?)\]")
PROG_FILE_RE = re.compile(r"^\s*File:\s*(.+)$")
PROG_DONE_RE = re.compile(r"✓\s*Programming completed successfully!")


def parse_hhmmss(base_day: date, hhmmss: str) -> datetime:
    h, m, s = map(int, hhmmss.split(":"))
    return datetime(base_day.year, base_day.month, base_day.day, h, m, s)


def resolve_input_files(input_path: str) -> List[Path]:
    """
    Aceita:
      - arquivo .txt
      - glob: "logs/*.txt"
      - pasta: "logs/"
    """
    p = Path(input_path)
    if p.is_dir():
        return sorted(Path(x) for x in glob.glob(str(p / "*.txt")))

    matches = glob.glob(input_path)
    if matches:
        return sorted(Path(x) for x in matches)

    # fallback: caminho único
    return [p]


def attach_event_to_nearest_timestamp(df: pd.DataFrame, evt: Event, max_delta_s: int) -> None:
    if df.empty:
        return
    diffs = (df["timestamp_dt"] - evt.t).abs()
    idx = diffs.idxmin()
    if pd.isna(idx):
        return
    if diffs.loc[idx] <= pd.Timedelta(seconds=max_delta_s):
        prev = df.at[idx, "observations"]
        msg = f"{evt.kind}: {evt.detail}".strip()
        df.at[idx, "observations"] = msg if not prev else (prev + " | " + msg)


def parse_one_file(
    path: Path,
    vc_step_threshold_v: float = 0.02,
) -> Tuple[pd.DataFrame, List[Event]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    inferred_day: Optional[date] = None
    for ln in lines:
        m = BITSTREAM_HEADER_RE.match(ln.strip())
        if m:
            inferred_day = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            break
    if inferred_day is None:
        inferred_day = date.today()

    rows: Dict[datetime, Dict[str, object]] = {}
    events: List[Event] = []

    pending_prog_mode: Optional[str] = None
    last_vc: Optional[float] = None

    for i, raw in enumerate(lines):
        ln = raw.rstrip("\n")

        # BITSTREAM TRANSITION block
        m_bs = BITSTREAM_HEADER_RE.match(ln.strip())
        if m_bs:
            day = datetime.strptime(m_bs.group(1), "%Y-%m-%d").date()
            t = parse_hhmmss(day, m_bs.group(2))

            bit_from, bit_to = None, None
            for j in range(i + 1, min(i + 12, len(lines))):
                m_from = BITSTREAM_FROM_RE.match(lines[j])
                if m_from:
                    bit_from = m_from.group(1).strip()
                m_to = BITSTREAM_TO_RE.match(lines[j])
                if m_to:
                    bit_to = m_to.group(1).strip()

            detail = f"From={bit_from or '?'} -> To={bit_to or '?'}"
            events.append(Event(t=t, kind="BITSTREAM_TRANSITION", detail=detail))
            continue

        # timestamped line
        m_ts = TS_RE.match(ln)
        if not m_ts:
            continue

        hhmmss, rest = m_ts.group(1), m_ts.group(2)
        t = parse_hhmmss(inferred_day, hhmmss)

        # FPGA readings
        m_fpga = FPGA_RE.search(rest)
        if m_fpga:
            r = rows.setdefault(t, {"timestamp_dt": t})
            r["T_FPGA_C"] = float(m_fpga.group("T"))
            r["VCCINT_FPGA_V"] = float(m_fpga.group("VCCINT"))

        # STM32 readings
        m_stm = STM32_RE.search(rest)
        if m_stm:
            r = rows.setdefault(t, {"timestamp_dt": t})
            vc = float(m_stm.group("Vc"))
            r["Vc_STM32_V"] = vc
            r["Vi_STM32_V"] = float(m_stm.group("Vi"))
            r["Io_STM32_A"] = float(m_stm.group("Io"))
            r["T_STM32_C"] = float(m_stm.group("T"))

            # Heurística: step de Vc
            if last_vc is not None and abs(vc - last_vc) >= vc_step_threshold_v:
                events.append(Event(t=t, kind="STM32_VC_STEP", detail=f"{last_vc:.3f}V -> {vc:.3f}V"))
            last_vc = vc

        # Program start
        m_start = START_PROG_RE.search(rest)
        if m_start:
            pending_prog_mode = m_start.group(1).strip()
            events.append(Event(t=t, kind="FPGA_PROGRAM_START", detail=f"mode={pending_prog_mode}"))
            continue

        # Program file (while pending)
        if pending_prog_mode is not None:
            m_file = PROG_FILE_RE.search(rest)
            if m_file:
                events.append(Event(t=t, kind="FPGA_PROGRAM_FILE", detail=m_file.group(1).strip()))

        # Program done
        if PROG_DONE_RE.search(rest):
            events.append(Event(t=t, kind="FPGA_PROGRAM_DONE", detail="success"))
            pending_prog_mode = None

    df = pd.DataFrame(rows.values()).sort_values("timestamp_dt").reset_index(drop=True)

    if not df.empty:
        df["timestamp"] = df["timestamp_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")
        df["observations"] = ""

        # Forward-fill para manter série contínua (se faltar FPGA/STM32 em algum segundo)
        value_cols = [
            "T_FPGA_C", "VCCINT_FPGA_V",
            "T_STM32_C", "Vc_STM32_V", "Vi_STM32_V", "Io_STM32_A"
        ]
        for c in value_cols:
            if c in df.columns:
                df[c] = df[c].ffill()

    return df, events


def parse_many(
    files: List[Path],
    vc_step_threshold_v: float,
    max_event_delta_s: int,
) -> pd.DataFrame:
    all_dfs: List[pd.DataFrame] = []
    all_events: List[Event] = []

    for f in files:
        df, evts = parse_one_file(f, vc_step_threshold_v=vc_step_threshold_v)
        if not df.empty:
            all_dfs.append(df)
            all_events.extend(evts)

    if not all_dfs:
        return pd.DataFrame()

    merged = pd.concat(all_dfs, ignore_index=True).sort_values("timestamp_dt").reset_index(drop=True)
    merged["observations"] = merged.get("observations", "").fillna("")

    # anexar eventos
    for evt in all_events:
        attach_event_to_nearest_timestamp(merged, evt, max_delta_s=max_event_delta_s)

    return merged
