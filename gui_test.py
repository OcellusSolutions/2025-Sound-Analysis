import os
import csv
import wave
import math
import datetime
import numpy as np
from scipy.io import wavfile
import sys
from array import array
from typing import Optional, Dict, List, Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QGroupBox, QFormLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QProgressBar,
    QTextEdit
)


# ---------------- RMS helpers ----------------
def _wav_total_rms(wav_path: str, chunk_frames: int = 65536) -> float:
    """
    Compute RMS over the entire WAV file (across all channels) as a single value.
    Returns RMS in the sample's native integer scale.
    Supports sample widths: 8-bit PCM, 16-bit PCM, 32-bit PCM.
    """
    with wave.open(wav_path, "rb") as wf:
        sampwidth = wf.getsampwidth()
        n_frames = wf.getnframes()

        if sampwidth == 1:
            typecode = "B"  # unsigned 8-bit
            bias = 128
        elif sampwidth == 2:
            typecode = "h"  # signed 16-bit
            bias = 0
        elif sampwidth == 4:
            typecode = "i"  # signed 32-bit
            bias = 0
        else:
            raise ValueError(f"Unsupported WAV sample width: {sampwidth * 8} bits ({wav_path})")

        sumsq = 0.0
        count = 0

        frames_left = n_frames
        while frames_left > 0:
            to_read = min(chunk_frames, frames_left)
            frames_left -= to_read

            data = wf.readframes(to_read)
            if not data:
                break

            samples = array(typecode)
            samples.frombytes(data)

            if sampwidth == 1:
                for s in samples:
                    v = float(s - bias)
                    sumsq += v * v
            else:
                for s in samples:
                    v = float(s)
                    sumsq += v * v

            count += len(samples)

        if count == 0:
            return 0.0

        return math.sqrt(sumsq / count)

def psd(wav_path: str):
    fs, y = wavfile.read(wav_path)  # read in audio file
    y = y[0]
    y = y - np.mean(y)  # remove DC offset
    dt = 1 / fs
    timeSeries1 = np.array(y)
    N = np.size(timeSeries1)
    T = N * dt
    # nFFT = 2 ** int(np.ceil(np.log2(N)))
    nFFT = N
    freqs = np.arange(0, nFFT / 2)
    lnspc1 = np.fft.fft(y, axis=0) * dt
    Gxy_avg = 2 / T * np.conjugate(lnspc1[0:int(nFFT / 2)]) * lnspc1[0:int(nFFT / 2)]
    return Gxy_avg, freqs

def peak_f_range(Gxy_avg, freqs, f_low, f_high):
    peak_f_range = np.where(Gxy_avg == np.max(Gxy_avg))[0][0]
    return freqs[peak_f_range]


def process_selected_node_rms_to_csv(selector_result: dict, csv_filename: Optional[str] = None) -> str:
    """
    Processes WAV files for the selected node + folders, computes total RMS per file,
    and writes a CSV into selector_result["processed_dir"].
    Returns: full path to the CSV written.
    """
    node = selector_result.get("selected_node")
    folders = selector_result.get("selected_folders") or []
    wav_paths = selector_result.get("dateWavPaths") or []
    processed_dir = selector_result.get("processed_dir")

    if not node:
        raise ValueError("selector_result is missing 'selected_node'.")
    if not processed_dir:
        raise ValueError("selector_result is missing 'processed_dir' (choose an output directory in the UI).")

    os.makedirs(processed_dir, exist_ok=True)

    if csv_filename is None:
        csv_filename = f"{node}_wav_rms.csv"

    csv_path = os.path.join(processed_dir, csv_filename)

    rows = []
    for i, wav_path in enumerate(wav_paths):
        folder = folders[i] if i < len(folders) else ""

        if not os.path.isfile(wav_path):
            rows.append(
                {
                    "node": node,
                    "folder": folder,
                    "wav_path": wav_path,
                    "rms": "",
                    "error": "missing_file",
                }
            )
            continue

        try:
            with wave.open(wav_path, "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
            duration_sec = (n_frames / framerate) if framerate else 0.0

            rms = _wav_total_rms(wav_path)

            #TODO: f0, f1,... ratios of energy


            rows.append(
                {
                    "node": node,
                    "folder": folder,
                    "wav_path": wav_path,
                    "rms": rms,
                    "n_channels": n_channels,
                    "sampwidth_bytes": sampwidth,
                    "framerate_hz": framerate,
                    "n_frames": n_frames,
                    "duration_sec": duration_sec,
                    "error": "",
                }
            )
        except Exception as e:
            rows.append(
                {
                    "node": node,
                    "folder": folder,
                    "wav_path": wav_path,
                    "rms": "",
                    "error": str(e),
                }
            )

    fieldnames = [
        "node",
        "folder",
        "wav_path",
        "rms",
        "n_channels",
        "sampwidth_bytes",
        "framerate_hz",
        "n_frames",
        "duration_sec",
        "error",
    ]

    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    return csv_path


# ---------------- Threaded worker for UI responsiveness ----------------
class RmsWorker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # done, total
    finished_ok = pyqtSignal(str)    # csv_path
    failed = pyqtSignal(str)

    def __init__(self, selector_result: dict):
        super().__init__()
        self.selector_result = selector_result

    def run(self):
        try:
            wav_paths = self.selector_result.get("dateWavPaths") or []
            total = len(wav_paths)
            if total == 0:
                raise ValueError("No WAV paths found (did you select folders with audio.wav?)")

            # We'll compute and write ourselves so we can emit progress.
            node = self.selector_result.get("selected_node")
            folders = self.selector_result.get("selected_folders") or []
            processed_dir = self.selector_result.get("processed_dir")
            if not node or not processed_dir:
                raise ValueError("Missing selected_node or processed_dir.")

            os.makedirs(processed_dir, exist_ok=True)
            csv_path = os.path.join(processed_dir, f"{node}_wav_rms.csv")

            fieldnames = [
                "node",
                "folder",
                "wav_path",
                "rms",
                "n_channels",
                "sampwidth_bytes",
                "framerate_hz",
                "n_frames",
                "duration_sec",
                "error",
            ]

            self.log.emit(f"Writing CSV: {csv_path}")
            done = 0

            with open(csv_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()

                for i, wav_path in enumerate(wav_paths):
                    folder = folders[i] if i < len(folders) else ""

                    if not os.path.isfile(wav_path):
                        w.writerow(
                            {
                                "node": node,
                                "folder": folder,
                                "wav_path": wav_path,
                                "rms": "",
                                "n_channels": "",
                                "sampwidth_bytes": "",
                                "framerate_hz": "",
                                "n_frames": "",
                                "duration_sec": "",
                                "error": "missing_file",
                            }
                        )
                        done += 1
                        self.progress.emit(done, total)
                        continue

                    try:
                        with wave.open(wav_path, "rb") as wf:
                            n_channels = wf.getnchannels()
                            sampwidth = wf.getsampwidth()
                            framerate = wf.getframerate()
                            n_frames = wf.getnframes()
                        duration_sec = (n_frames / framerate) if framerate else 0.0

                        rms = _wav_total_rms(wav_path)

                        w.writerow(
                            {
                                "node": node,
                                "folder": folder,
                                "wav_path": wav_path,
                                "rms": rms,
                                "n_channels": n_channels,
                                "sampwidth_bytes": sampwidth,
                                "framerate_hz": framerate,
                                "n_frames": n_frames,
                                "duration_sec": duration_sec,
                                "error": "",
                            }
                        )
                    except Exception as e:
                        w.writerow(
                            {
                                "node": node,
                                "folder": folder,
                                "wav_path": wav_path,
                                "rms": "",
                                "n_channels": "",
                                "sampwidth_bytes": "",
                                "framerate_hz": "",
                                "n_frames": "",
                                "duration_sec": "",
                                "error": str(e),
                            }
                        )

                    done += 1
                    if done % 10 == 0 or done == total:
                        self.log.emit(f"Processed {done}/{total}")
                    self.progress.emit(done, total)

            self.finished_ok.emit(csv_path)

        except Exception as e:
            self.failed.emit(str(e))


# ---------------- Main UI ----------------
class MainWindow(QMainWindow):
    def __init__(self, local_base_path: str):
        super().__init__()
        self.setWindowTitle("Ocellus apis audio processing")
        self.resize(1180, 640)

        self.audioFile = "audio.wav"
        self.dataFile = "data.json"

        self.local_base_path = local_base_path
        self.local_node_list = self._find_nodes(local_base_path)

        self.selected_node: Optional[str] = None
        self.current_folders: List[str] = []

        self.worker: Optional[RmsWorker] = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        # --- Split panes ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Nodes
        nodes_group = QGroupBox("Nodes")
        nodes_layout = QVBoxLayout(nodes_group)
        self.nodes_list = QListWidget()
        self.nodes_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        for n in self.local_node_list:
            self.nodes_list.addItem(QListWidgetItem(n))
        self.nodes_list.currentItemChanged.connect(self.on_node_changed)
        nodes_layout.addWidget(self.nodes_list)

        # Folders
        folders_group = QGroupBox("Folders (multi-select)")
        folders_layout = QVBoxLayout(folders_group)
        self.folders_list = QListWidget()
        self.folders_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        folders_layout.addWidget(self.folders_list)

        btn_row = QWidget()
        btn_l = QHBoxLayout(btn_row)
        btn_l.setContentsMargins(0, 0, 0, 0)
        self.btn_select_all = QPushButton("Select All")
        self.btn_clear = QPushButton("Clear")
        self.btn_select_all.clicked.connect(self.select_all_folders)
        self.btn_clear.clicked.connect(self.clear_folder_selection)
        btn_l.addWidget(self.btn_select_all)
        btn_l.addWidget(self.btn_clear)
        btn_l.addStretch(1)
        folders_layout.addWidget(btn_row)

        splitter.addWidget(nodes_group)
        splitter.addWidget(folders_group)
        splitter.setSizes([300, 600])
        layout.addWidget(splitter, 1)

        # --- Directories ---
        # --- Directories (stacked, full width) ---
        dirs_group = QGroupBox("Directories")
        dirs_layout = QVBoxLayout(dirs_group)

        self.base_dir_edit = QLineEdit(self.local_base_path)
        self.processed_dir_edit = QLineEdit(os.path.join(self.local_base_path, "processed"))

        base_browse = QPushButton("Browse…")
        out_browse = QPushButton("Browse…")
        base_browse.clicked.connect(self.browse_base_dir)
        out_browse.clicked.connect(self.browse_processed_dir)

        # Row 1: Base dir (full width)
        base_row = QWidget()
        base_row_l = QHBoxLayout(base_row)
        base_row_l.setContentsMargins(0, 0, 0, 0)
        base_row_l.addWidget(QLabel("Main directory to nodes:"))
        base_row_l.addWidget(self.base_dir_edit, 1)  # <-- expand
        base_row_l.addWidget(base_browse)  # <-- fixed
        dirs_layout.addWidget(base_row)

        # Row 2: Output dir (full width)
        out_row = QWidget()
        out_row_l = QHBoxLayout(out_row)
        out_row_l.setContentsMargins(0, 0, 0, 0)
        out_row_l.addWidget(QLabel("Processed files output directory:"))
        out_row_l.addWidget(self.processed_dir_edit, 1)  # <-- expand
        out_row_l.addWidget(out_browse)  # <-- fixed
        dirs_layout.addWidget(out_row)

        layout.addWidget(dirs_group)

        # --- Params bar ---
        params_group = QGroupBox("Processing Parameters")
        params_form = QFormLayout(params_group)

        validator = QDoubleValidator(0.0, 1e9, 6)

        self.f0_low = QLineEdit("100")
        self.f0_high = QLineEdit("200")
        self.low_cut = QLineEdit("200")
        self.mid_cut = QLineEdit("500")
        self.high_cut = QLineEdit("1000")

        for w in (self.f0_low, self.f0_high, self.low_cut, self.mid_cut, self.high_cut):
            w.setValidator(validator)

        row = QWidget()
        row_l = QHBoxLayout(row)
        row_l.setContentsMargins(0, 0, 0, 0)

        def labeled(widget: QLineEdit, label: str):
            box = QWidget()
            bl = QHBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.addWidget(QLabel(label))
            bl.addWidget(widget)
            return box

        row_l.addWidget(labeled(self.f0_low, "f0 low (Hz)"))
        row_l.addWidget(labeled(self.f0_high, "f0 high (Hz)"))
        row_l.addWidget(labeled(self.low_cut, "low_cut (Hz)"))
        row_l.addWidget(labeled(self.mid_cut, "mid_cut (Hz)"))
        row_l.addWidget(labeled(self.high_cut, "high_cut (Hz)"))

        params_form.addRow(row)
        layout.addWidget(params_group)

        # --- Run/Progress/Log ---
        run_row = QWidget()
        run_l = QHBoxLayout(run_row)
        run_l.setContentsMargins(0, 0, 0, 0)

        self.run_btn = QPushButton("Run RMS → CSV")
        self.run_btn.clicked.connect(self.run_rms)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        run_l.addWidget(self.run_btn)
        run_l.addWidget(self.progress, 1)

        layout.addWidget(run_row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)

        # Preselect first node if present
        if self.local_node_list:
            self.nodes_list.setCurrentRow(0)

    def _find_nodes(self, base_path: str) -> List[str]:
        try:
            nodes = os.listdir(base_path)
            nodes = [n for n in nodes if not n.startswith(".")]
            nodes.sort()
            return nodes
        except Exception:
            return []

    def append_log(self, msg: str):
        self.log.append(msg)

    def browse_base_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Node directory", self.base_dir_edit.text() or "")
        if d:
            self.base_dir_edit.setText(d)
            # refresh nodes
            self.local_base_path = d
            self.local_node_list = self._find_nodes(d)
            self.nodes_list.clear()
            for n in self.local_node_list:
                self.nodes_list.addItem(QListWidgetItem(n))
            self.folders_list.clear()
            self.selected_node = None
            if self.local_node_list:
                self.nodes_list.setCurrentRow(0)

    def browse_processed_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Save directory", self.processed_dir_edit.text() or "")
        if d:
            self.processed_dir_edit.setText(d)

    def on_node_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current is None:
            return
        node = current.text()
        self.selected_node = node
        self.refresh_folders()

    def refresh_folders(self):
        base_dir = self.base_dir_edit.text().strip()
        node = self.selected_node
        self.folders_list.clear()
        self.current_folders = []

        if not node or not base_dir:
            return

        mainDir = os.path.join(base_dir, node)
        try:
            folders = os.listdir(mainDir)
            folders.sort()
            folders = [d for d in folders if "." not in d]
        except Exception as e:
            QMessageBox.critical(self, "Folder error", f"Could not list folders for node:\n{e}")
            return

        self.current_folders = folders
        for f in folders:
            self.folders_list.addItem(QListWidgetItem(f))

    def select_all_folders(self):
        for i in range(self.folders_list.count()):
            self.folders_list.item(i).setSelected(True)

    def clear_folder_selection(self):
        self.folders_list.clearSelection()

    def _read_params(self) -> Optional[Dict[str, float]]:
        def get_float(widget: QLineEdit, name: str) -> Optional[float]:
            t = widget.text().strip()
            try:
                return float(t)
            except ValueError:
                QMessageBox.critical(self, "Invalid number", f"{name} must be a number.")
                return None

        params = {
            "f0_low": get_float(self.f0_low, "f0 low"),
            "f0_high": get_float(self.f0_high, "f0 high"),
            "low_cut": get_float(self.low_cut, "low_cut"),
            "mid_cut": get_float(self.mid_cut, "mid_cut"),
            "high_cut": get_float(self.high_cut, "high_cut"),
        }
        if any(v is None for v in params.values()):
            return None
        return params  # type: ignore

    def _build_selector_result(self) -> Optional[Dict[str, Any]]:
        node = self.selected_node
        if not node:
            QMessageBox.information(self, "Missing selection", "Please select a node.")
            return None

        selected_items = self.folders_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Missing selection", "Please select at least one folder.")
            return None

        base_dir = self.base_dir_edit.text().strip()
        processed_dir = self.processed_dir_edit.text().strip()
        if not base_dir:
            QMessageBox.information(self, "Missing directory", "Please provide the main directory to nodes.")
            return None
        if not processed_dir:
            QMessageBox.information(self, "Missing directory", "Please provide a directory to save processed files.")
            return None

        params = self._read_params()
        if params is None:
            return None

        folders = [it.text() for it in selected_items]
        mainDir = os.path.join(base_dir, node)
        wavs = [os.path.join(mainDir, f, self.audioFile) for f in folders]
        jsns = [os.path.join(mainDir, f, self.dataFile) for f in folders]

        return {
            "selected_node": node,
            "selected_folders": folders,
            "dateWavPaths": wavs,
            "dateJsonPaths": jsns,
            "mainDir": mainDir,
            "params": params,
            "base_dir": base_dir,
            "processed_dir": processed_dir,
        }

    def run_rms(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "Busy", "A run is already in progress.")
            return

        selector_result = self._build_selector_result()
        if selector_result is None:
            return

        self.append_log("Starting RMS computation…")
        self.progress.setValue(0)
        self.run_btn.setEnabled(False)

        self.worker = RmsWorker(selector_result)
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_finished_ok)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_progress(self, done: int, total: int):
        if total <= 0:
            self.progress.setValue(0)
            return
        pct = int(100 * done / total)
        self.progress.setValue(pct)

    def on_finished_ok(self, csv_path: str):
        self.append_log(f"Done. CSV written to: {csv_path}")
        self.run_btn.setEnabled(True)
        QMessageBox.information(self, "Finished", f"CSV written to:\n{csv_path}")

    def on_failed(self, err: str):
        self.append_log(f"ERROR: {err}")
        self.run_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", err)


def main():
    local_base_path = "/Volumes/Case_portable/ocellus/hives_acs/"
    app = QApplication(sys.argv)
    w = MainWindow(local_base_path=local_base_path)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
