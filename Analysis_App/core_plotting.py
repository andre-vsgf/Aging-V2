from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import pandas as pd


def save_plots(df: pd.DataFrame, outdir: Path, stem: str) -> List[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []

    if df.empty:
        return paths

    x = df["timestamp_dt"]

    # Temperaturas
    fig = plt.figure()
    if "T_STM32_C" in df.columns:
        plt.plot(x, df["T_STM32_C"], label="STM32 T (°C)")
    if "T_FPGA_C" in df.columns:
        plt.plot(x, df["T_FPGA_C"], label="FPGA T (°C)")
    plt.xlabel("Time")
    plt.ylabel("Temperature (°C)")
    plt.legend()
    plt.tight_layout()
    p = outdir / f"{stem}_temperatures.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    paths.append(p)

    # Tensões
    fig = plt.figure()
    if "Vc_STM32_V" in df.columns:
        plt.plot(x, df["Vc_STM32_V"], label="STM32 Vc (V)")
    if "VCCINT_FPGA_V" in df.columns:
        plt.plot(x, df["VCCINT_FPGA_V"], label="FPGA VCCINT (V)")
    plt.xlabel("Time")
    plt.ylabel("Voltage (V)")
    plt.legend()
    plt.tight_layout()
    p = outdir / f"{stem}_voltages.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    paths.append(p)

    return paths
