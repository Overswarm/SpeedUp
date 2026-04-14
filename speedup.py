import sys
import os
import subprocess
import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QScrollArea,
    QFrame,
    QDoubleSpinBox,
    QSizePolicy,
    QSlider,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont


SUPPORTED_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus", ".aiff", ".alac",
}

DARK_STYLESHEET = """
QMainWindow {
    background-color: #1e1e2e;
}
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-size: 13px;
}
QLabel {
    color: #cdd6f4;
    background: transparent;
}
QLabel#headerLabel {
    font-size: 22px;
    font-weight: bold;
    color: #89b4fa;
}
QLabel#subLabel {
    font-size: 11px;
    color: #6c7086;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton#startButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
    font-size: 14px;
    padding: 10px 30px;
}
QPushButton#startButton:hover {
    background-color: #b4d0fb;
}
QPushButton#startButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}
QPushButton#clearButton {
    background-color: #f38ba8;
    color: #1e1e2e;
    font-weight: bold;
}
QPushButton#clearButton:hover {
    background-color: #f5a0b8;
}
QScrollArea {
    border: 2px dashed #45475a;
    border-radius: 8px;
    background-color: #181825;
}
QScrollArea#dropZone {
    border: 2px dashed #89b4fa;
}
QFrame#fileRow {
    background-color: #181825;
    border-radius: 6px;
    padding: 4px;
}
QDoubleSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px;
    font-size: 14px;
}
QDoubleSpinBox:focus {
    border-color: #89b4fa;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #313244;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #89b4fa;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QSlider::sub-page:horizontal {
    background: #89b4fa;
    border-radius: 3px;
}
"""

PROGRESS_BAR_STYLE = """
QProgressBar {{
    border: 1px solid #45475a;
    border-radius: 4px;
    text-align: center;
    background-color: #313244;
    color: #cdd6f4;
    height: 20px;
    font-size: 11px;
}}
QProgressBar::chunk {{
    background-color: {color};
    border-radius: 3px;
}}
"""


class FileProcessorThread(QThread):
    """Worker thread that processes a single audio file via ffmpeg."""
    progress = pyqtSignal(int)       # 0-100
    finished = pyqtSignal(bool, str) # success, message

    def __init__(self, input_path: str, output_path: str, speed: float):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.speed = speed
        self._cancelled = False

    def run(self):
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

            # Build ffmpeg command with atempo filter
            # atempo only accepts values between 0.5 and 100.0, so we chain
            # multiple atempo filters for values below 0.5
            atempo_filters = self._build_atempo_chain(self.speed)
            filter_str = ",".join(atempo_filters)

            cmd = [
                "ffmpeg", "-y",
                "-i", self.input_path,
                "-filter:a", filter_str,
                "-progress", "pipe:1",
                "-loglevel", "error",
                self.output_path,
            ]

            # Get input duration for progress calculation
            duration = self._get_duration()

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            # Parse ffmpeg progress output
            while True:
                if self._cancelled:
                    process.kill()
                    self._cleanup_output()
                    self.finished.emit(False, "Cancelled")
                    return

                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line.startswith("out_time_ms="):
                    try:
                        time_us = int(line.split("=")[1].strip())
                        if duration > 0:
                            # Output duration = input duration / speed
                            expected_output_duration = duration / self.speed
                            pct = min(int((time_us / 1_000_000) / expected_output_duration * 100), 99)
                            self.progress.emit(pct)
                    except (ValueError, ZeroDivisionError):
                        pass

            rc = process.returncode
            if rc == 0:
                self.progress.emit(100)
                self.finished.emit(True, "Done")
            else:
                stderr = process.stderr.read()
                self._cleanup_output()
                self.finished.emit(False, f"ffmpeg error: {stderr[:200]}")

        except Exception as e:
            self._cleanup_output()
            self.finished.emit(False, str(e)[:200])

    def cancel(self):
        self._cancelled = True

    def _cleanup_output(self):
        try:
            if os.path.exists(self.output_path):
                os.remove(self.output_path)
        except OSError:
            pass

    def _get_duration(self) -> float:
        """Get duration in seconds using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    self.input_path,
                ],
                capture_output=True, text=True, timeout=10,
            )
            return float(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            return 0.0

    @staticmethod
    def _build_atempo_chain(speed: float) -> list[str]:
        """Build a chain of atempo filters since each instance only supports 0.5-100.0."""
        filters = []
        remaining = speed
        if remaining < 0.5:
            while remaining < 0.5:
                filters.append("atempo=0.5")
                remaining /= 0.5
        filters.append(f"atempo={remaining:.4f}")
        return filters


class FileRowWidget(QFrame):
    """A single row showing file name, progress bar, and status."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setObjectName("fileRow")
        self.thread: FileProcessorThread | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        # File name
        name_label = QLabel(Path(file_path).name)
        name_label.setFixedWidth(250)
        name_label.setToolTip(file_path)
        layout.addWidget(name_label)

        # Progress bar
        from PyQt6.QtWidgets import QProgressBar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE.format(color="#89b4fa"))
        self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.progress_bar.setFixedHeight(22)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Pending")
        self.status_label.setFixedWidth(120)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)

    def set_status(self, text: str, color: str = "#cdd6f4"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; background: transparent;")

    def mark_processing(self):
        self.set_status("Processing...", "#f9e2af")
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE.format(color="#89b4fa"))

    def mark_done(self):
        self.set_status("Done", "#a6e3a1")
        self.progress_bar.setValue(100)
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE.format(color="#a6e3a1"))

    def mark_error(self, msg: str):
        self.set_status("Error", "#f38ba8")
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE.format(color="#f38ba8"))
        self.setToolTip(msg)


class DropArea(QScrollArea):
    """Scroll area that accepts drag-and-drop of audio files."""
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setWidgetResizable(True)
        self.setObjectName("dropZone")
        self.setMinimumHeight(250)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.container_layout.setSpacing(4)
        self.container_layout.setContentsMargins(6, 6, 6, 6)

        # Placeholder label
        self.placeholder = QLabel("Drag && drop audio files here\nor click 'Add Files' below")
        self.placeholder.setObjectName("subLabel")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color: #6c7086; font-size: 15px; padding: 60px; background: transparent;")
        self.container_layout.addWidget(self.placeholder)

        self.setWidget(self.container)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                if Path(path).suffix.lower() in SUPPORTED_EXTENSIONS:
                    paths.append(path)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for f in files:
                        fp = os.path.join(root, f)
                        if Path(fp).suffix.lower() in SUPPORTED_EXTENSIONS:
                            paths.append(fp)
        if paths:
            self.files_dropped.emit(paths)

    def hide_placeholder(self):
        self.placeholder.hide()

    def show_placeholder(self):
        self.placeholder.show()


class SpeedUpApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpeedUp - Bulk Audio Speed Changer")
        self.setMinimumSize(750, 600)
        self.resize(850, 650)

        self.file_rows: list[FileRowWidget] = []
        self.file_paths: set[str] = set()
        self.output_folder: str = ""
        self.processing = False
        self.active_threads: list[FileProcessorThread] = []
        self.current_index = 0

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 16, 20, 16)

        # Header
        header = QLabel("SpeedUp")
        header.setObjectName("headerLabel")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)

        subtitle = QLabel("Bulk audio speed changer — drag files below to get started")
        subtitle.setObjectName("subLabel")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(subtitle)

        # Drop area
        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self._add_files)
        main_layout.addWidget(self.drop_area, stretch=1)

        # Add / Clear buttons
        file_btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Files")
        add_btn.clicked.connect(self._browse_files)
        file_btn_layout.addWidget(add_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setObjectName("clearButton")
        self.clear_btn.clicked.connect(self._clear_files)
        file_btn_layout.addWidget(self.clear_btn)

        file_btn_layout.addStretch()

        # File count
        self.file_count_label = QLabel("0 files")
        self.file_count_label.setObjectName("subLabel")
        file_btn_layout.addWidget(self.file_count_label)
        main_layout.addLayout(file_btn_layout)

        # Speed control
        speed_layout = QHBoxLayout()
        speed_label = QLabel("Speed:")
        speed_label.setStyleSheet("font-weight: bold; font-size: 14px; background: transparent;")
        speed_layout.addWidget(speed_label)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 40)  # 0.1 to 4.0 in steps of 0.1
        self.speed_slider.setValue(15)      # default 1.5x
        self.speed_slider.setTickInterval(5)
        self.speed_slider.setSingleStep(1)
        self.speed_slider.valueChanged.connect(self._slider_changed)
        speed_layout.addWidget(self.speed_slider, stretch=1)

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.1, 4.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setDecimals(1)
        self.speed_spin.setValue(1.5)
        self.speed_spin.setSuffix("x")
        self.speed_spin.setFixedWidth(90)
        self.speed_spin.valueChanged.connect(self._spin_changed)
        speed_layout.addWidget(self.speed_spin)

        main_layout.addLayout(speed_layout)

        # Output folder
        output_layout = QHBoxLayout()
        output_label = QLabel("Output folder:")
        output_label.setStyleSheet("background: transparent;")
        output_layout.addWidget(output_label)

        self.output_path_label = QLabel("(not set — click 'Choose' to select)")
        self.output_path_label.setObjectName("subLabel")
        self.output_path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        output_layout.addWidget(self.output_path_label, stretch=1)

        output_btn = QPushButton("Choose")
        output_btn.clicked.connect(self._choose_output)
        output_layout.addWidget(output_btn)
        main_layout.addLayout(output_layout)

        # Start button
        self.start_btn = QPushButton("Start Processing")
        self.start_btn.setObjectName("startButton")
        self.start_btn.clicked.connect(self._start_processing)
        main_layout.addWidget(self.start_btn)

    # --- Slots ---

    def _slider_changed(self, value: int):
        speed = value / 10.0
        self.speed_spin.blockSignals(True)
        self.speed_spin.setValue(speed)
        self.speed_spin.blockSignals(False)

    def _spin_changed(self, value: float):
        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(int(round(value * 10)))
        self.speed_slider.blockSignals(False)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Audio Files",
            "",
            "Audio Files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma *.opus *.aiff *.alac);;All Files (*)",
        )
        if files:
            self._add_files(files)

    def _add_files(self, paths: list[str]):
        new_count = 0
        for p in paths:
            if p not in self.file_paths:
                self.file_paths.add(p)
                row = FileRowWidget(p)
                self.file_rows.append(row)
                self.drop_area.container_layout.addWidget(row)
                new_count += 1

        if self.file_rows:
            self.drop_area.hide_placeholder()

        self.file_count_label.setText(f"{len(self.file_rows)} file{'s' if len(self.file_rows) != 1 else ''}")

    def _clear_files(self):
        if self.processing:
            return
        for row in self.file_rows:
            row.setParent(None)
            row.deleteLater()
        self.file_rows.clear()
        self.file_paths.clear()
        self.drop_area.show_placeholder()
        self.file_count_label.setText("0 files")

    def _choose_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder
            display = folder if len(folder) < 60 else "..." + folder[-57:]
            self.output_path_label.setText(display)
            self.output_path_label.setToolTip(folder)
            self.output_path_label.setStyleSheet("color: #a6e3a1; background: transparent;")

    def _start_processing(self):
        if self.processing:
            # Cancel all
            self._cancel_processing()
            return

        if not self.file_rows:
            return

        if not self.output_folder:
            self._choose_output()
            if not self.output_folder:
                return

        self.processing = True
        self.start_btn.setText("Cancel")
        self.start_btn.setStyleSheet(
            "background-color: #f38ba8; color: #1e1e2e; font-weight: bold; font-size: 14px; "
            "padding: 10px 30px; border-radius: 6px;"
        )
        self.clear_btn.setEnabled(False)
        self.current_index = 0

        # Reset all rows
        for row in self.file_rows:
            row.set_progress(0)
            row.set_status("Pending")
            row.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE.format(color="#89b4fa"))

        # Process files sequentially (one at a time to avoid overwhelming the system)
        self._process_next()

    def _process_next(self):
        if self.current_index >= len(self.file_rows):
            self._finish_processing()
            return

        row = self.file_rows[self.current_index]
        row.mark_processing()

        speed = self.speed_spin.value()
        input_path = row.file_path
        filename = Path(input_path).stem
        ext = Path(input_path).suffix
        output_path = os.path.join(self.output_folder, f"{filename}_{speed:.1f}x{ext}")

        # Avoid overwriting if file already exists with same name
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.join(self.output_folder, f"{filename}_{speed:.1f}x_{counter}{ext}")
            counter += 1

        thread = FileProcessorThread(input_path, output_path, speed)
        thread.progress.connect(row.set_progress)
        thread.finished.connect(lambda ok, msg: self._on_file_done(row, ok, msg))
        self.active_threads.append(thread)
        row.thread = thread
        thread.start()

    def _on_file_done(self, row: FileRowWidget, success: bool, message: str):
        if success:
            row.mark_done()
        else:
            row.mark_error(message)

        self.current_index += 1
        if self.processing:
            self._process_next()

    def _cancel_processing(self):
        self.processing = False
        for thread in self.active_threads:
            thread.cancel()
        for thread in self.active_threads:
            thread.wait(3000)
        self.active_threads.clear()

        for row in self.file_rows:
            if row.status_label.text() == "Processing...":
                row.set_status("Cancelled", "#fab387")
            elif row.status_label.text() == "Pending":
                pass  # leave as pending

        self._reset_buttons()

    def _finish_processing(self):
        self.processing = False
        self.active_threads.clear()
        self._reset_buttons()

    def _reset_buttons(self):
        self.start_btn.setText("Start Processing")
        self.start_btn.setStyleSheet("")
        self.clear_btn.setEnabled(True)

    def closeEvent(self, event):
        if self.processing:
            self._cancel_processing()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)

    window = SpeedUpApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
