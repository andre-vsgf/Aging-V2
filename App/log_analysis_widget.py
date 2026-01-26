# -*- coding: utf-8 -*-
"""
Log Analysis Widget (Embedded)

This widget embeds the standalone log analysis utility into the main application.
It provides:
- File / folder selection for .txt logs
- CSV generation aligned by timestamp
- Plot generation (temperatures + voltages)
- Embedded preview charts and CSV preview table
- Event annotations merged into observations column

Design goals:
- Minimal UI footprint (fits at the right side of the Log tab)
- No external environment setup (works with the app packaging)
- Safe defaults; robust to missing fields; forward-fill time series

Notes:
- The router emits live telemetry; this widget is OFFLINE analysis for archived logs.
- Parsing targets the textual logs containing "[FPGA]" and "[STM32]" lines, plus bitstream/program events.
"""

from __future__ import annotations

import glob
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, QLineEdit,
    QFileDialog, QSpinBox, QDoubleSpinBox, QMessageBox, QProgressBar,
    QTableWidget, QTableWidgetItem
)

from PySide6.QtGui import QPainter, QPen, QPixmap, QColor

import re


# -------------------------
# Parsing regexes (offline)
# -------------------------
TS_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s+(.*)$")

FPGA_RE = re.compile(
    r"\[FPGA\]\s+T=(?P<T>-?\d+(?:\.\d+)?)°C\s+VCCINT=(?P<VCCINT>-?\d+(?:\.\d+)?)V"
)
STM32_RE = re.compile(
    r"\[STM32\]\s+Vc=(?P<Vc>-?\d+(?:\.\d+)?)V\s+Vi=(?P<Vi>-?\d+(?:\.\d+)?)V\s+Io=(?P<Io>-?\d+(?:\.\d+)?)A\s+T=(?P<T>-?\d+(?:\.\d+)?)°C"
)

BITSTREAM_HEADER_RE = re.compile(r"^BITSTREAM TRANSITION @ (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})$")
BITSTREAM_FROM_RE = re.compile(r"^\s*From:\s*(.+?)\s*(?:\(|$)")
BITSTREAM_TO_RE = re.compile(r"^\s*To:\s*(.+?)\s*(?:\(|$)")

START_PROG_RE = re.compile(r"▶\s*Starting FPGA Programming\s*\[(.+?)\]")
PROG_FILE_RE = re.compile(r"^\s*File:\s*(.+)$")
PROG_DONE_RE = re.compile(r"✓\s*Programming completed successfully!")


@dataclass
class Event:
    t: datetime
    kind: str
    detail: str


@dataclass
class RunConfig:
    input_path: str
    outdir: str
    max_event_delta_s: int
    vc_step_threshold_v: float


def _parse_hhmmss(base_day: date, hhmmss: str) -> datetime:
    h, m, s = map(int, hhmmss.split(":"))
    return datetime(base_day.year, base_day.month, base_day.day, h, m, s)


def _resolve_input_files(input_path: str) -> List[Path]:
    p = Path(input_path)
    if p.is_dir():
        return sorted(Path(x) for x in glob.glob(str(p / "*.txt")))

    matches = glob.glob(input_path)
    if matches:
        return sorted(Path(x) for x in matches)

    return [p]


def _attach_event_to_nearest(df: pd.DataFrame, evt: Event, max_delta_s: int) -> None:
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


def _parse_one_file(path: Path, vc_step_threshold_v: float) -> Tuple[pd.DataFrame, List[Event]]:
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

        m_bs = BITSTREAM_HEADER_RE.match(ln.strip())
        if m_bs:
            day = datetime.strptime(m_bs.group(1), "%Y-%m-%d").date()
            t = _parse_hhmmss(day, m_bs.group(2))

            bit_from, bit_to = None, None
            for j in range(i + 1, min(i + 12, len(lines))):
                m_from = BITSTREAM_FROM_RE.match(lines[j])
                if m_from:
                    bit_from = m_from.group(1).strip()
                m_to = BITSTREAM_TO_RE.match(lines[j])
                if m_to:
                    bit_to = m_to.group(1).strip()

            events.append(Event(t=t, kind="BITSTREAM_TRANSITION", detail=f"From={bit_from or '?'} -> To={bit_to or '?'}"))
            continue

        m_ts = TS_RE.match(ln)
        if not m_ts:
            continue

        hhmmss, rest = m_ts.group(1), m_ts.group(2)
        t = _parse_hhmmss(inferred_day, hhmmss)

        m_fpga = FPGA_RE.search(rest)
        if m_fpga:
            r = rows.setdefault(t, {"timestamp_dt": t})
            r["T_FPGA_C"] = float(m_fpga.group("T"))
            r["VCCINT_FPGA_V"] = float(m_fpga.group("VCCINT"))

        m_stm = STM32_RE.search(rest)
        if m_stm:
            r = rows.setdefault(t, {"timestamp_dt": t})
            vc = float(m_stm.group("Vc"))
            r["Vc_STM32_V"] = vc
            r["Vi_STM32_V"] = float(m_stm.group("Vi"))
            r["Io_STM32_A"] = float(m_stm.group("Io"))
            r["T_STM32_C"] = float(m_stm.group("T"))

            if last_vc is not None and abs(vc - last_vc) >= vc_step_threshold_v:
                events.append(Event(t=t, kind="STM32_VC_STEP", detail=f"{last_vc:.3f}V -> {vc:.3f}V"))
            last_vc = vc

        m_start = START_PROG_RE.search(rest)
        if m_start:
            pending_prog_mode = m_start.group(1).strip()
            events.append(Event(t=t, kind="FPGA_PROGRAM_START", detail=f"mode={pending_prog_mode}"))
            continue

        if pending_prog_mode is not None:
            m_file = PROG_FILE_RE.search(rest)
            if m_file:
                events.append(Event(t=t, kind="FPGA_PROGRAM_FILE", detail=m_file.group(1).strip()))

        if PROG_DONE_RE.search(rest):
            events.append(Event(t=t, kind="FPGA_PROGRAM_DONE", detail="success"))
            pending_prog_mode = None

    df = pd.DataFrame(rows.values()).sort_values("timestamp_dt").reset_index(drop=True)

    if not df.empty:
        df["timestamp"] = df["timestamp_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")
        df["observations"] = ""

        value_cols = [
            "T_FPGA_C", "VCCINT_FPGA_V",
            "T_STM32_C", "Vc_STM32_V", "Vi_STM32_V", "Io_STM32_A"
        ]
        for c in value_cols:
            if c in df.columns:
                df[c] = df[c].ffill()

    return df, events


def _parse_many(files: List[Path], vc_step_threshold_v: float, max_event_delta_s: int) -> pd.DataFrame:
    all_dfs: List[pd.DataFrame] = []
    all_events: List[Event] = []

    for f in files:
        df, evts = _parse_one_file(f, vc_step_threshold_v=vc_step_threshold_v)
        if not df.empty:
            all_dfs.append(df)
            all_events.extend(evts)

    if not all_dfs:
        return pd.DataFrame()

    merged = pd.concat(all_dfs, ignore_index=True).sort_values("timestamp_dt").reset_index(drop=True)
    merged["observations"] = merged.get("observations", "").fillna("")

    for evt in all_events:
        _attach_event_to_nearest(merged, evt, max_delta_s=max_event_delta_s)

    return merged


class _Worker(QObject):
    finished = Signal(object, object, object)  # df, csv_path, plot_paths
    error = Signal(str)
    progress = Signal(int)

    def __init__(self, cfg: RunConfig):
        super().__init__()
        self.cfg = cfg

    @Slot()
    def run(self):
        try:
            self.progress.emit(5)
            files = _resolve_input_files(self.cfg.input_path)
            files = [f for f in files if f.exists()]
            if not files:
                raise RuntimeError("Nenhum arquivo encontrado para o caminho selecionado.")

            self.progress.emit(15)
            df = _parse_many(files, vc_step_threshold_v=self.cfg.vc_step_threshold_v, max_event_delta_s=self.cfg.max_event_delta_s)
            if df.empty:
                raise RuntimeError("Nenhuma linha [FPGA]/[STM32] encontrada nos logs selecionados.")

            self.progress.emit(60)
            outdir = Path(self.cfg.outdir)
            outdir.mkdir(parents=True, exist_ok=True)

            stem = "merged" if len(files) > 1 else files[0].stem
            csv_path = outdir / f"{stem}.csv"

            cols = [
                "timestamp",
                "T_STM32_C", "Vc_STM32_V", "Vi_STM32_V", "Io_STM32_A",
                "T_FPGA_C", "VCCINT_FPGA_V",
                "observations",
            ]
            existing_cols = [c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols and c != "timestamp_dt"]
            df[existing_cols].to_csv(csv_path, index=False, encoding="utf-8")

            self.progress.emit(100)
            # plot_paths será gerado pela UI (LogAnalysisWidget) após atualizar os charts
            self.finished.emit(df, str(csv_path), [])

        except Exception as e:
            self.error.emit(str(e))

class _SimplePlot(QWidget):
    """
    Plot minimalista (Qt-native) para séries temporais.
    - Não depende de matplotlib
    - Suporta múltiplas séries
    - Renderiza eixos simples + polilinha(s)
    """
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._series: List[Tuple[List[float], str]] = []  # [(y_values, label), ...]
        self._x: Optional[List[float]] = None             # x em segundos relativos
        self._ylabel = ""
        self._xmin = 0.0
        self._xmax = 1.0
        self._ymin = 0.0
        self._ymax = 1.0
        self.setMinimumHeight(180)

    def set_data(self, x_seconds: List[float], series: List[Tuple[pd.Series, str]], ylabel: str):
        # Converte para listas simples
        self._x = list(x_seconds)
        self._series = [(list(s.values if hasattr(s, "values") else s), label) for (s, label) in series]
        self._ylabel = ylabel

        # ranges
        if self._x:
            self._xmin, self._xmax = float(min(self._x)), float(max(self._x))
            if self._xmin == self._xmax:
                self._xmax = self._xmin + 1.0
        ys = []
        for y, _ in self._series:
            ys.extend([v for v in y if v is not None])
        if ys:
            self._ymin, self._ymax = float(min(ys)), float(max(ys))
            if self._ymin == self._ymax:
                self._ymax = self._ymin + 1.0
        else:
            self._ymin, self._ymax = 0.0, 1.0

        self.update()

    def _map_x(self, x, left, width):
        return left + (x - self._xmin) * width / (self._xmax - self._xmin)

    def _map_y(self, y, top, height):
        # y cresce para baixo no Qt
        return top + (self._ymax - y) * height / (self._ymax - self._ymin)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Margens
        left = 52
        right = 10
        top = 24
        bottom = 22

        plot_w = max(10, w - left - right)
        plot_h = max(10, h - top - bottom)

        # Fundo
        p.fillRect(0, 0, w, h, QColor(245, 245, 245))

        # Título
        p.setPen(QPen(QColor(0, 0, 0)))
        p.drawText(8, 16, f"{self._title} — {self._ylabel}")

        # Eixos
        axis_pen = QPen(QColor(60, 60, 60))
        axis_pen.setWidth(1)
        p.setPen(axis_pen)
        p.drawLine(left, top, left, top + plot_h)                 # Y
        p.drawLine(left, top + plot_h, left + plot_w, top + plot_h)  # X

        # Sem dados
        if not self._x or not self._series:
            p.setPen(QPen(QColor(120, 120, 120)))
            p.drawText(left + 10, top + 20, "Sem dados para plotar.")
            return

        # Grade leve (3 linhas)
        grid_pen = QPen(QColor(200, 200, 200))
        grid_pen.setStyle(Qt.DashLine)
        p.setPen(grid_pen)
        for i in range(1, 4):
            yy = top + int(i * plot_h / 4)
            p.drawLine(left, yy, left + plot_w, yy)

        # Desenho das séries
        # Para evitar dependência de paleta externa, alterna 4 cores básicas.
        colors = [QColor(0, 90, 160), QColor(160, 60, 0), QColor(0, 140, 80), QColor(120, 60, 140)]

        for idx, (yvals, label) in enumerate(self._series):
            if len(yvals) != len(self._x):
                continue

            pen = QPen(colors[idx % len(colors)])
            pen.setWidth(2)
            p.setPen(pen)

            prev_ok = False
            prev_x = prev_y = 0.0

            for k in range(len(self._x)):
                y = yvals[k]
                if y is None:
                    prev_ok = False
                    continue

                xx = self._map_x(self._x[k], left, plot_w)
                yy = self._map_y(float(y), top, plot_h)

                if prev_ok:
                    p.drawLine(int(prev_x), int(prev_y), int(xx), int(yy))
                prev_x, prev_y = xx, yy
                prev_ok = True

        # Legenda simples (canto superior direito do plot)
        p.setPen(QPen(QColor(0, 0, 0)))
        lx = left + plot_w - 160
        ly = top + 16
        for idx, (_, label) in enumerate(self._series):
            c = colors[idx % len(colors)]
            p.fillRect(lx, ly - 8, 10, 10, c)
            p.drawText(lx + 14, ly, label)
            ly += 14

    def save_png(self, filepath: str):
        """
        Salva exatamente o que está renderizado no widget em PNG.
        Deve ser chamado no thread da UI.
        """
        pix: QPixmap = self.grab()
        pix.save(filepath, "PNG")



class LogAnalysisWidget(QWidget):
    """
    Embedded analysis widget. Intended to be placed at the right side of the Log tab.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._df: Optional[pd.DataFrame] = None
        self._csv_path: Optional[str] = None
        self._plot_paths: List[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        top = QGroupBox("Offline Log Analysis")
        top_l = QVBoxLayout(top)

        row1 = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Arquivo .txt, glob (logs/*.txt) ou pasta")
        btn_file = QPushButton("Arquivo(s)")
        btn_dir = QPushButton("Pasta")
        btn_out = QPushButton("Saída…")

        btn_file.clicked.connect(self._pick_file)
        btn_dir.clicked.connect(self._pick_dir)
        btn_out.clicked.connect(self._pick_outdir)

        row1.addWidget(QLabel("Logs:"))
        row1.addWidget(self.input_edit, 1)
        row1.addWidget(btn_file)
        row1.addWidget(btn_dir)

        row2 = QHBoxLayout()
        self.out_edit = QLineEdit(str(Path.cwd() / "out_logs"))
        row2.addWidget(QLabel("Saída:"))
        row2.addWidget(self.out_edit, 1)
        row2.addWidget(btn_out)

        row3 = QHBoxLayout()
        self.delta_spin = QSpinBox()
        self.delta_spin.setRange(0, 120)
        self.delta_spin.setValue(5)
        self.delta_spin.setSuffix(" s")

        self.vc_spin = QDoubleSpinBox()
        self.vc_spin.setRange(0.0, 1.0)
        self.vc_spin.setDecimals(3)
        self.vc_spin.setSingleStep(0.005)
        self.vc_spin.setValue(0.020)
        self.vc_spin.setSuffix(" V")

        self.btn_run = QPushButton("Gerar")
        self.btn_run.clicked.connect(self._run)

        row3.addWidget(QLabel("Δ evento:"))
        row3.addWidget(self.delta_spin)
        row3.addSpacing(8)
        row3.addWidget(QLabel("Step Vc:"))
        row3.addWidget(self.vc_spin)
        row3.addStretch(1)
        row3.addWidget(self.btn_run)

        top_l.addLayout(row1)
        top_l.addLayout(row2)
        top_l.addLayout(row3)

        root.addWidget(top)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        # Charts
        self.chart_temp = _SimplePlot("Temperaturas")
        self.chart_v = _SimplePlot("Tensões")

        root.addWidget(self.chart_temp, 1)
        root.addWidget(self.chart_v, 1)

        # Table preview (short)
        root.addWidget(QLabel("<b>Prévia do CSV</b>"))
        self.table = QTableWidget(0, 0)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, 1)

        # Bottom actions
        act = QHBoxLayout()
        self.btn_open_csv = QPushButton("Abrir CSV")
        self.btn_open_csv.setEnabled(False)
        self.btn_open_csv.clicked.connect(self._open_csv)

        self.btn_open_out = QPushButton("Abrir pasta")
        self.btn_open_out.setEnabled(False)
        self.btn_open_out.clicked.connect(self._open_out)

        act.addWidget(self.btn_open_csv)
        act.addWidget(self.btn_open_out)
        act.addStretch(1)
        root.addLayout(act)

        self._thread: Optional[QThread] = None
        self._worker: Optional[_Worker] = None

    def _pick_file(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Selecione log(s)", "", "Text Files (*.txt);;All Files (*)")
        if not files:
            return
        if len(files) == 1:
            self.input_edit.setText(files[0])
        else:
            # Minimalistic approach: when multi-selected, analyze the directory
            self.input_edit.setText(str(Path(files[0]).parent))

    def _pick_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecione a pasta de logs")
        if folder:
            self.input_edit.setText(folder)

    def _pick_outdir(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecione a pasta de saída")
        if folder:
            self.out_edit.setText(folder)

    def _run(self):
        input_path = self.input_edit.text().strip()
        if not input_path:
            QMessageBox.warning(self, "Atenção", "Selecione um arquivo/pasta de log.")
            return

        self.btn_run.setEnabled(False)
        self.btn_open_csv.setEnabled(False)
        self.btn_open_out.setEnabled(False)
        self.progress.setValue(0)

        cfg = RunConfig(
            input_path=input_path,
            outdir=self.out_edit.text().strip(),
            max_event_delta_s=int(self.delta_spin.value()),
            vc_step_threshold_v=float(self.vc_spin.value()),
        )

        self._thread = QThread()
        self._worker = _Worker(cfg)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    @Slot(str)
    def _on_error(self, msg: str):
        self.btn_run.setEnabled(True)
        QMessageBox.critical(self, "Erro", msg)

    @Slot(object, object, object)
    def _on_finished(self, df: pd.DataFrame, csv_path: str, plot_paths: List[str]):
        self._df = df
        self._csv_path = csv_path
        self._plot_paths = plot_paths

        self.btn_run.setEnabled(True)
        self.btn_open_csv.setEnabled(True)
        self.btn_open_out.setEnabled(True)

        self._refresh_table()
        self._refresh_charts()
        # Salvar PNGs usando os próprios widgets (thread da UI)
        try:
            outdir = Path(Path(csv_path).parent)
            stem = Path(csv_path).stem  # mesmo nome do CSV

            temp_png = outdir / f"{stem}_temperatures.png"
            volt_png = outdir / f"{stem}_voltages.png"

            self.chart_temp.save_png(str(temp_png))
            self.chart_v.save_png(str(volt_png))

            self._plot_paths = [str(temp_png), str(volt_png)]
        except Exception:
            # Não falha o fluxo principal por causa de export de imagem
            self._plot_paths = []


    def _refresh_table(self, max_rows: int = 200):
        if self._df is None or self._df.empty:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        df_view = self._df.copy()
        if "timestamp_dt" in df_view.columns:
            df_view = df_view.drop(columns=["timestamp_dt"])
        df_view = df_view.tail(max_rows)

        cols = list(df_view.columns)
        self.table.setColumnCount(len(cols))
        self.table.setRowCount(len(df_view))
        self.table.setHorizontalHeaderLabels(cols)

        for r_idx, (_, row) in enumerate(df_view.iterrows()):
            for c_idx, c in enumerate(cols):
                val = "" if pd.isna(row[c]) else str(row[c])
                self.table.setItem(r_idx, c_idx, QTableWidgetItem(val))

        self.table.resizeColumnsToContents()

    def _refresh_charts(self):
        if self._df is None or self._df.empty:
            return

        # X em segundos relativos (para plot simples)
        x_dt = self._df["timestamp_dt"]
        t0 = x_dt.iloc[0]
        x_seconds = [(t - t0).total_seconds() for t in x_dt]

        # Temperaturas
        temp_series = []
        if "T_STM32_C" in self._df.columns:
            temp_series.append((self._df["T_STM32_C"], "STM32 T (°C)"))
        if "T_FPGA_C" in self._df.columns:
            temp_series.append((self._df["T_FPGA_C"], "FPGA T (°C)"))
        self.chart_temp.set_data(x_seconds, temp_series, ylabel="Temperature (°C)")

        # Tensões
        v_series = []
        if "Vc_STM32_V" in self._df.columns:
            v_series.append((self._df["Vc_STM32_V"], "STM32 Vc (V)"))
        if "VCCINT_FPGA_V" in self._df.columns:
            v_series.append((self._df["VCCINT_FPGA_V"], "FPGA VCCINT (V)"))
        self.chart_v.set_data(x_seconds, v_series, ylabel="Voltage (V)")


    def _open_csv(self):
        if not self._csv_path:
            return
        self._open_path(self._csv_path)

    def _open_out(self):
        outdir = self.out_edit.text().strip()
        if outdir:
            self._open_path(outdir)

    def _open_path(self, path: str):
        import sys, os
        p = Path(path)
        if not p.exists():
            QMessageBox.warning(self, "Atenção", f"Caminho não existe: {path}")
            return
        if sys.platform.startswith("win"):
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif sys.platform.startswith("darwin"):
            os.system(f'open "{p}"')
        else:
            os.system(f'xdg-open "{p}"')
