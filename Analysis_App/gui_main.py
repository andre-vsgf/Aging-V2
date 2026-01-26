import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd
from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox,
    QGroupBox, QMessageBox, QTableWidget, QTableWidgetItem, QProgressBar
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core_parser import resolve_input_files, parse_many
from core_plotting import save_plots


@dataclass
class RunConfig:
    input_path: str
    outdir: str
    max_event_delta_s: int
    vc_step_threshold_v: float


class Worker(QObject):
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
            files = resolve_input_files(self.cfg.input_path)
            if not files:
                raise RuntimeError("Nenhum arquivo encontrado.")

            self.progress.emit(15)
            df = parse_many(
                files=files,
                vc_step_threshold_v=self.cfg.vc_step_threshold_v,
                max_event_delta_s=self.cfg.max_event_delta_s,
            )
            if df.empty:
                raise RuntimeError("Nenhuma linha [FPGA]/[STM32] encontrada nos logs selecionados.")

            self.progress.emit(55)
            outdir = Path(self.cfg.outdir)
            outdir.mkdir(parents=True, exist_ok=True)

            stem = "merged"
            csv_path = outdir / f"{stem}.csv"

            cols = [
                "timestamp",
                "T_STM32_C", "Vc_STM32_V", "Vi_STM32_V", "Io_STM32_A",
                "T_FPGA_C", "VCCINT_FPGA_V",
                "observations",
            ]
            existing_cols = [c for c in cols if c in df.columns] + [
                c for c in df.columns if c not in cols and c != "timestamp_dt"
            ]
            df_out = df[existing_cols].copy()
            df_out.to_csv(csv_path, index=False, encoding="utf-8")

            self.progress.emit(80)
            plot_paths = save_plots(df, outdir=outdir, stem=stem)

            self.progress.emit(100)
            self.finished.emit(df, str(csv_path), [str(p) for p in plot_paths])

        except Exception as e:
            self.error.emit(str(e))


class MplChart(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.title = title

        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def plot_series(self, x, series: List[tuple], xlabel: str, ylabel: str):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        for y, label in series:
            ax.plot(x, y, label=label)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.legend()
        self.figure.tight_layout()
        self.canvas.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Tool - FPGA/STM32")
        self.setMinimumSize(1100, 700)

        self.df: Optional[pd.DataFrame] = None
        self.csv_path: Optional[str] = None
        self.plot_paths: List[str] = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout()
        central.setLayout(root)

        # -----------------
        # Top controls
        # -----------------
        controls = QGroupBox("Entrada e Saída")
        c_layout = QHBoxLayout()
        controls.setLayout(c_layout)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Selecione um .txt, um glob (logs/*.txt) ou uma pasta")

        btn_pick_file = QPushButton("Selecionar arquivo(s)")
        btn_pick_file.clicked.connect(self.pick_files)

        btn_pick_folder = QPushButton("Selecionar pasta")
        btn_pick_folder.clicked.connect(self.pick_folder)

        self.outdir_edit = QLineEdit(str(Path.cwd() / "out"))
        self.outdir_edit.setPlaceholderText("Pasta de saída")

        btn_pick_out = QPushButton("Saída…")
        btn_pick_out.clicked.connect(self.pick_outdir)

        c_layout.addWidget(QLabel("Log(s):"))
        c_layout.addWidget(self.input_edit, 2)
        c_layout.addWidget(btn_pick_file)
        c_layout.addWidget(btn_pick_folder)
        c_layout.addSpacing(12)
        c_layout.addWidget(QLabel("Saída:"))
        c_layout.addWidget(self.outdir_edit, 1)
        c_layout.addWidget(btn_pick_out)

        root.addWidget(controls)

        # -----------------
        # Settings row
        # -----------------
        settings = QGroupBox("Configurações")
        s_layout = QHBoxLayout()
        settings.setLayout(s_layout)

        self.delta_spin = QSpinBox()
        self.delta_spin.setRange(0, 120)
        self.delta_spin.setValue(5)
        self.delta_spin.setSuffix(" s")
        self.delta_spin.setToolTip("Janela para anexar eventos ao timestamp mais próximo")

        self.vc_spin = QDoubleSpinBox()
        self.vc_spin.setRange(0.0, 1.0)
        self.vc_spin.setSingleStep(0.005)
        self.vc_spin.setDecimals(3)
        self.vc_spin.setValue(0.020)
        self.vc_spin.setSuffix(" V")
        self.vc_spin.setToolTip("Limiar para detectar step de Vc")

        self.btn_run = QPushButton("Gerar CSV + Gráficos")
        self.btn_run.clicked.connect(self.run_pipeline)

        self.btn_open_out = QPushButton("Abrir pasta de saída")
        self.btn_open_out.setEnabled(False)
        self.btn_open_out.clicked.connect(self.open_outdir)

        self.btn_open_csv = QPushButton("Abrir CSV")
        self.btn_open_csv.setEnabled(False)
        self.btn_open_csv.clicked.connect(self.open_csv)

        s_layout.addWidget(QLabel("Δ evento:"))
        s_layout.addWidget(self.delta_spin)
        s_layout.addSpacing(10)
        s_layout.addWidget(QLabel("Step Vc:"))
        s_layout.addWidget(self.vc_spin)
        s_layout.addStretch(1)
        s_layout.addWidget(self.btn_run)
        s_layout.addWidget(self.btn_open_csv)
        s_layout.addWidget(self.btn_open_out)

        root.addWidget(settings)

        # progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        # -----------------
        # Charts + table
        # -----------------
        body = QHBoxLayout()
        root.addLayout(body, 1)

        left = QVBoxLayout()
        body.addLayout(left, 2)

        self.chart_temp = MplChart("Temperaturas")
        self.chart_v = MplChart("Tensões")
        left.addWidget(self.chart_temp, 1)
        left.addWidget(self.chart_v, 1)

        right = QVBoxLayout()
        body.addLayout(right, 1)

        right.addWidget(QLabel("<b>Prévia do CSV</b>"))
        self.table = QTableWidget(0, 0)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        right.addWidget(self.table, 1)

        self.status = QLabel("Pronto.")
        self.status.setAlignment(Qt.AlignLeft)
        root.addWidget(self.status)

        self._thread: Optional[QThread] = None
        self._worker: Optional[Worker] = None

    # -----------
    # File pickers
    # -----------
    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Selecione log(s)", "", "Text Files (*.txt);;All Files (*)")
        if files:
            # PyInstaller/Windows: use ; para juntar múltiplos, e a função resolve_input_files aceita glob/pasta;
            # aqui simplificamos: se múltiplos, escrevemos o diretório e usamos glob interno via pasta.
            # Para manter precisão: se múltiplos, preferimos um glob baseado no diretório e filtramos no parse.
            # Porém, aqui vamos só colocar o diretório e o usuário pode escolher “pasta” também.
            if len(files) == 1:
                self.input_edit.setText(files[0])
            else:
                # estratégia: colocar o primeiro arquivo e o parser vai aceitar lista via pasta/glob
                # para multi-seleção exata, sugere-se usar pasta, ou você pode adaptar para aceitar lista em string.
                self.input_edit.setText(str(Path(files[0]).parent))

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecione a pasta de logs")
        if folder:
            self.input_edit.setText(folder)

    def pick_outdir(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecione a pasta de saída")
        if folder:
            self.outdir_edit.setText(folder)

    # -----
    # Runner
    # -----
    def run_pipeline(self):
        input_path = self.input_edit.text().strip()
        outdir = self.outdir_edit.text().strip()
        if not input_path:
            QMessageBox.warning(self, "Atenção", "Selecione um arquivo/pasta de log.")
            return

        self.btn_run.setEnabled(False)
        self.btn_open_out.setEnabled(False)
        self.btn_open_csv.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText("Processando…")

        cfg = RunConfig(
            input_path=input_path,
            outdir=outdir,
            max_event_delta_s=int(self.delta_spin.value()),
            vc_step_threshold_v=float(self.vc_spin.value()),
        )

        self._thread = QThread()
        self._worker = Worker(cfg)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.error.connect(self.on_error)
        self._worker.finished.connect(self.on_finished)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    @Slot(str)
    def on_error(self, msg: str):
        self.btn_run.setEnabled(True)
        self.status.setText("Erro.")
        QMessageBox.critical(self, "Erro", msg)

    @Slot(object, object, object)
    def on_finished(self, df: pd.DataFrame, csv_path: str, plot_paths: List[str]):
        self.df = df
        self.csv_path = csv_path
        self.plot_paths = plot_paths

        self.btn_run.setEnabled(True)
        self.btn_open_out.setEnabled(True)
        self.btn_open_csv.setEnabled(True)

        self.status.setText(f"Concluído. CSV: {csv_path}")
        self.refresh_table()
        self.refresh_charts()

    def refresh_table(self, max_rows: int = 250):
        if self.df is None or self.df.empty:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        # Mostra um subconjunto para não ficar pesado
        df_view = self.df.copy()
        # removemos timestamp_dt para exibição
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

    def refresh_charts(self):
        if self.df is None or self.df.empty:
            return

        x = self.df["timestamp_dt"]

        # Temperaturas
        temp_series = []
        if "T_STM32_C" in self.df.columns:
            temp_series.append((self.df["T_STM32_C"], "STM32 T (°C)"))
        if "T_FPGA_C" in self.df.columns:
            temp_series.append((self.df["T_FPGA_C"], "FPGA T (°C)"))
        self.chart_temp.plot_series(x, temp_series, xlabel="Time", ylabel="Temperature (°C)")

        # Tensões
        v_series = []
        if "Vc_STM32_V" in self.df.columns:
            v_series.append((self.df["Vc_STM32_V"], "STM32 Vc (V)"))
        if "VCCINT_FPGA_V" in self.df.columns:
            v_series.append((self.df["VCCINT_FPGA_V"], "FPGA VCCINT (V)"))
        self.chart_v.plot_series(x, v_series, xlabel="Time", ylabel="Voltage (V)")

    # -------------
    # Open functions
    # -------------
    def open_outdir(self):
        outdir = self.outdir_edit.text().strip()
        if outdir:
            self._open_path(outdir)

    def open_csv(self):
        if self.csv_path:
            self._open_path(self.csv_path)

    def _open_path(self, path: str):
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
