#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import sys
import threading
import traceback
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
from tkinter.scrolledtext import ScrolledText
from typing import TypedDict

from .io_utils import appdir, resolve_path, ensure_dir
from .settings import load_settings, Settings, save_settings
from .converter import ANTONConverter
from .pdf_generator import PDFGenerator


class _TextStream:
    """A lightweight stream wrapper that pushes text to a queue for GUI consumption."""

    def __init__(self, q: "queue.Queue[str]") -> None:
        self._q = q

    def write(self, s: str) -> int:
        if s:
            self._q.put(s)
        return len(s)

    def flush(self) -> None:  # pragma: no cover - noop
        pass


class _PadOptions(TypedDict, total=False):
    padx: int | tuple[int, int]
    pady: int | tuple[int, int]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ANTON-Konverter - GUI")
        self._configure_fonts()

        # Load settings from config.xml
        try:
            self.settings = load_settings(os.path.join(appdir, "config.xml"))
        except Exception as e:
            messagebox.showerror(
                "Konfiguration",
                (
                    "config.xml konnte nicht geladen werden.\n\n"
                    "Bitte stellen Sie sicher, dass sich die Programmdatei "
                    "(Programmdatei) und die config.xml im selben Ordner befinden.\n"
                    f"Gesuchter Pfad: {os.path.join(appdir, 'config.xml')}\n\n"
                    f"Details: {e}"
                ),
            )
            self.settings = Settings(
                anton_xml_file="",
                anton_outputpath="output",
                csv_file="",
                csv_delimiter=";",
                pdf_outputpath="pdf-files",
                pdf_antonlink="https://www.anton.app",
                pdf_einzeln="ja",
                pdf_onedoc="nein",
                pdf_schoolgroup="1",
            )
        # Ensure output directories exist at startup
        self._ensure_output_dirs()

        # UI State
        self._running = False
        self._log_q: "queue.Queue[str]" = queue.Queue()

        self._build_ui()
        self._set_initial_geometry()
        self.after(50, self._drain_log_queue)

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        pad_options: _PadOptions = {"padx": 10, "pady": 8}

        # Header (ohne globalen Einstellungen-Button)
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=6)

        # Tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, **pad_options)

        # Small color swatches for tabs (for subtle color hints)
        def _mk_swatch(color: str) -> tk.PhotoImage:
            img = tk.PhotoImage(width=10, height=10)
            img.put(color, to=(0, 0, 10, 10))
            return img
        self._img_start = _mk_swatch("#e8e8e8")
        self._img_anton = _mk_swatch("#6aa9ff")
        self._img_log = _mk_swatch("#5cc98a")
        self._img_info = _mk_swatch("#d7d7d7")

        # Subtle color accents for better separation
        anton_bg = "#eef6ff"   # light blue tint
        log_bg = "#eefaf2"   # light green tint

        # ANTON Tab
        # Start Tab (first)
        start_tab = ttk.Frame(notebook)
        notebook.add(start_tab, text="Start", image=self._img_start, compound="left")

        start_text = ScrolledText(start_tab, wrap=tk.WORD, height=14)
        start_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        start_text.insert(tk.END, (
            "Willkommen beim ANTON-Konverter!\n\n"
            "Dieses Programm hat zwei Bereiche:\n"
            "1) ANTON Konverter: Wandelt eine SchILD NRW XML-Exportdatei in zwei ANTON-kompatible CSV-Dateien (Schüler und Lehrkräfte).\n"
            "2) PDF-Generator: Erzeugt aus einer CSV-Datei personenbezogene PDF-Dateien mit Zugangsdaten.\n\n"
            "So gehen Sie vor:\n"
            "- Einstellungen prüfen (insb. Ausgabeordner).\n"
            "- Im ANTON-Tab die SchILD-XML-Datei wählen und konvertieren.\n"
            "- Im PDF-Tab CSV wählen und PDFs erzeugen.\n"
        ))
        start_text.configure(state=tk.DISABLED)
        # Overwrite start page text to reflect ANTON XML -> CSV and PDF export
        try:
            start_text.configure(state=tk.NORMAL)
            start_text.delete("1.0", tk.END)
            start_text.insert(tk.END, (
            "Willkommen beim ANTON-Konverter!\n\n"
            "Dieses Programm hat zwei Bereiche:\n"
            "1) ANTON Konverter: Wandelt eine SchILD NRW XML-Exportdatei\n"
            "   in zwei ANTON-kompatible CSV-Dateien (Schüler und Lehrkräfte).\n\n"
            "2) PDF-Generator: Erzeugt aus einer CSV-Datei\n"
            "   personenbezogene PDF-Dateien mit Zugangsdaten.\n\n"
            "So gehen Sie vor:\n"
            "- Einstellungen prüfen (insb. Ausgabeordner).\n"
            "- Im ANTON-Tab die SchILD-XML-Datei wählen und konvertieren.\n"
            "- Im PDF-Tab CSV wählen und PDFs erzeugen.\n"
            ))
            start_text.configure(state=tk.DISABLED)
        except Exception:
            pass

        anton_tab = tk.Frame(notebook, bg=anton_bg)
        notebook.add(anton_tab, text="ANTON Konverter", image=self._img_anton, compound="left")
        anton_head = tk.Frame(anton_tab, bg=anton_bg)
        anton_head.pack(fill=tk.X, padx=6, pady=(6, 6))
        lbl_converter_desc = tk.Label(
            anton_head,
            text="Konvertiert eine SchILD NRW XML-Datei in ANTON-CSV (Schüler/Lehrkräfte).",
            bg=anton_bg,
            fg="#444",
            wraplength=820,
            anchor="w",
            justify=tk.LEFT,
        )
        lbl_converter_desc.pack(anchor=tk.W, padx=2, pady=(0, 4))
        anton_head_row = tk.Frame(anton_head, bg=anton_bg)
        anton_head_row.pack(fill=tk.X)
        ttk.Button(anton_head_row, text="Einstellungen", command=self._open_settings_anton).pack(side=tk.LEFT)
        tk.Label(anton_head_row, text="Hinweis: Ausgabeordner für ANTON-CSV in den Einstellungen anpassen.", bg=anton_bg, fg="#555").pack(side=tk.LEFT, padx=(8, 0))

        anton_frame = tk.Frame(anton_tab, bg=anton_bg)
        anton_frame.pack(fill=tk.X, padx=6, pady=6)
        tk.Label(anton_frame, text="SchILD-XML (.xml):", bg=anton_bg).grid(row=0, column=0, sticky=tk.W)
        self.var_xml = tk.StringVar(value=self._resolved(getattr(self.settings, "anton_xml_file", "")))
        ttk.Entry(anton_frame, textvariable=self.var_xml, width=80).grid(row=0, column=1, sticky=tk.W)
        try:
            # Prefer stored SchILD XML path if present
            xml_pref = getattr(self.settings, "anton_xml_file", "")
            if xml_pref:
                self.var_xml.set(self._resolved(xml_pref))
        except Exception:
            pass
        ttk.Button(anton_frame, text="Durchsuchen...", command=self._pick_xml).grid(row=0, column=2, padx=6)
        self.btn_convert = ttk.Button(anton_frame, text="Konvertieren", command=self._run_convert)
        self.btn_convert.grid(row=0, column=3, padx=6)
        try:
            self.btn_convert.configure(text="Konvertieren")
        except Exception:
            pass

        anton_actions = tk.Frame(anton_tab, bg=anton_bg)
        anton_actions.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Button(anton_actions, text="Ausgabeordner öffnen", command=self._open_output).pack(side=tk.LEFT)

        # PDF Tab
        log_tab = tk.Frame(notebook, bg=log_bg)
        notebook.add(log_tab, text="PDF-Generator", image=self._img_log, compound="left")
        log_head = tk.Frame(log_tab, bg=log_bg)
        log_head.pack(fill=tk.X, padx=6, pady=(6, 6))
        lbl_log_desc = tk.Label(
            log_head,
            text="Erzeugt personalisierte Zugangsdaten-PDFs aus CSV.",
            bg=log_bg,
            fg="#444",
            wraplength=820,
            anchor="w",
            justify=tk.LEFT,
        )
        lbl_log_desc.pack(anchor=tk.W, padx=2, pady=(0, 4))
        log_head_row = tk.Frame(log_head, bg=log_bg)
        log_head_row.pack(fill=tk.X)
        ttk.Button(log_head_row, text="Einstellungen (PDF)", command=self._open_settings_pdf).pack(side=tk.LEFT)
        tk.Label(log_head_row, text="Hinweis: Bitte die PDF-Einstellungen prüfen und ggf. anpassen.", bg=log_bg, fg="#555").pack(side=tk.LEFT, padx=(8, 0))

        pdf_frame = tk.Frame(log_tab, bg=log_bg)
        pdf_frame.pack(fill=tk.X, padx=6, pady=6)
        tk.Label(pdf_frame, text="CSV (.csv):", bg=log_bg).grid(row=0, column=0, sticky=tk.W)
        initial_csv = self.settings.csv_file
        self.var_pdf_source = tk.StringVar(value=self._resolved(initial_csv))
        ttk.Entry(pdf_frame, textvariable=self.var_pdf_source, width=80).grid(row=0, column=1, sticky=tk.W)
        ttk.Button(pdf_frame, text="Durchsuchen...", command=self._pick_pdf_source).grid(row=0, column=2, padx=6)
        self.btn_run_pdf = ttk.Button(pdf_frame, text="PDFs erzeugen", command=self._run_pdf)
        self.btn_run_pdf.grid(row=0, column=3, padx=6)

        pdf_actions = tk.Frame(log_tab, bg=log_bg)
        pdf_actions.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(pdf_actions, text="PDF-Output öffnen", command=self._open_pdf_output).pack(side=tk.LEFT)

        # Info Tab (rechts)
        info_tab = ttk.Frame(notebook)
        notebook.add(info_tab, text="Info", image=self._img_info, compound="left")
        info_text = ScrolledText(info_tab, wrap=tk.WORD, height=14)
        info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        info_content = (
            "ANTON Konverter + PDF-Generator\n\n"
            "Erstellt durch:\n"
            "Johannes Schirge\n"
            "ZfsL Bielefeld\n"
            "johannes.schirge@zfsl-bielefeld.nrw.schule\n\n"
            "Hinweis:\n"
            "Dieses Programm wird OHNE JEGLICHE GARANTIE bereitgestellt. Eine Nutzung erfolgt auf eigene Verantwortung.\n"
            "Dies ist freie Software; Sie dürfen sie unter bestimmten Bedingungen weiterverbreiten.\n"
            "Einzelheiten finden Sie in der Datei LICENSE (GNU GPLv3).\n\n"
            "Rechtlicher Hinweis:\n"
            "Alle genannten Produktnamen, Logos und Marken sind Eigentum der jeweiligen Rechteinhaber.\n"
            "Die Verwendung dient ausschließlich der Identifikation und impliziert keine Verbindung, Unterstützung oder Billigung durch die Rechteinhaber."
        )
        info_text.insert(tk.END, info_content)
        info_text.configure(state=tk.DISABLED)

        # Select Start tab initially
        notebook.select(start_tab)
        # Rename first tab for ANTON XML conversion
        try:
            notebook.tab(anton_tab, text="ANTON Konverter")
        except Exception:
            pass

        # Keyboard shortcuts
        self.bind_all("<Alt-a>", lambda e: self._open_settings_anton())
        self.bind_all("<Alt-p>", lambda e: self._open_settings_pdf())
        self.bind_all("<F1>", lambda e: notebook.select(start_tab))
        # Dynamically adapt description wrap to available width
        def _adapt_wrap_converter(event=None):
            try:
                lbl_converter_desc.configure(wraplength=max(300, anton_tab.winfo_width() - 40))
            except Exception:
                pass
        def _adapt_wrap_log(event=None):
            try:
                lbl_log_desc.configure(wraplength=max(300, log_tab.winfo_width() - 40))
            except Exception:
                pass
        anton_tab.bind("<Configure>", _adapt_wrap_converter)
        log_tab.bind("<Configure>", _adapt_wrap_log)

        # Log
        frm_log = ttk.LabelFrame(self, text="Protokoll")
        frm_log.pack(fill=tk.BOTH, expand=True, **pad_options)
        self.txt = tk.Text(frm_log, wrap=tk.WORD, state=tk.DISABLED)
        self.txt.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        sb = ttk.Scrollbar(frm_log, orient=tk.VERTICAL, command=self.txt.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt.configure(yscrollcommand=sb.set)

        # Statusbar
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.status_var = tk.StringVar(value="Bereit")
        self.status_lbl = ttk.Label(status_frame, textvariable=self.status_var, foreground="#555")
        self.status_lbl.pack(anchor=tk.W)

    def _resolved(self, p: str) -> str:
        if not p:
            return ""
        try:
            return resolve_path(p)
        except Exception:
            return p

    # ---------------- Actions ----------------
    def _pick_xml(self) -> None:
        fn = filedialog.askopenfilename(
            title="SchILD-XML auswählen",
            filetypes=[("XML", "*.xml"), ("Alle Dateien", "*.*")],
            initialdir=os.path.dirname(self.var_xml.get() or appdir),
        )
        if fn:
            self.var_xml.set(fn)

    def _pick_pdf_source(self) -> None:
        fn = filedialog.askopenfilename(
            title="CSV-Datei wählen",
            filetypes=[
                ("CSV", "*.csv"),
                ("Alle Dateien", "*.*"),
            ],
            initialdir=os.path.dirname(self.var_pdf_source.get() or appdir),
        )
        if fn:
            self.var_pdf_source.set(fn)

    def _open_output(self) -> None:
        path = resolve_path(self.settings.anton_outputpath or "output")
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f"open '{path}'")
            else:
                os.system(f"xdg-open '{path}'")
        except Exception as e:
            messagebox.showerror("Öffnen fehlgeschlagen", str(e))

    def _open_settings(self) -> None:
        SettingsDialog(self, self.settings, on_save=self._apply_and_save_settings)

    def _open_settings_anton(self) -> None:
        SettingsDialog(self, self.settings, on_save=self._apply_and_save_settings, section="anton")

    def _open_settings_pdf(self) -> None:
        SettingsDialog(self, self.settings, on_save=self._apply_and_save_settings, section="pdf")

    def _open_pdf_output(self) -> None:
        path = resolve_path(self.settings.pdf_outputpath or "pdf-files")
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f"open '{path}'")
            else:
                os.system(f"xdg-open '{path}'")
        except Exception as e:
            messagebox.showerror("Öffnen fehlgeschlagen", str(e))

    def _apply_and_save_settings(self, new_settings: Settings) -> None:
        # Update state in app
        self.settings = new_settings
        # Ensure directories exist for updated settings
        self._ensure_output_dirs()
        # Reflect into entry fields
        self.var_xml.set(self._resolved(self.settings.anton_xml_file))
        initial_csv = self.settings.csv_file
        self.var_pdf_source.set(self._resolved(initial_csv))
        # Persist to config.xml
        try:
            cfg_path = os.path.join(appdir, "config.xml")
            save_settings(cfg_path, self.settings)
            messagebox.showinfo("Einstellungen", "Einstellungen wurden gespeichert.")
        except Exception as e:
            messagebox.showerror("Einstellungen", f"Konnte config.xml nicht speichern.\n\n{e}")

    def _ensure_output_dirs(self) -> None:
        try:
            anton_output_dir = resolve_path(self.settings.anton_outputpath or "output")
            pdf_dir = resolve_path(self.settings.pdf_outputpath or "pdf-files")
            ensure_dir(anton_output_dir)
            ensure_dir(pdf_dir)
        except Exception:
            # Do not block startup on directory errors; open buttons will still error if misconfigured
            pass

    def _set_running(self, running: bool) -> None:
        self._running = running
        state = tk.DISABLED if running else tk.NORMAL
        self.btn_convert.configure(state=state)
        self.btn_run_pdf.configure(state=state)
        self.status_var.set("Arbeitet..." if running else "Bereit")

    def _configure_fonts(self) -> None:
        # Increase default fonts for better readability
        try:
            for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkFixedFont"):
                f = tkfont.nametofont(name)
                # Prefer Segoe UI on Windows; falls nicht vorhanden, nimmt Tk den nächsten passenden Font
                f.configure(family="Segoe UI", size=11)
        except Exception:
            pass

    def _set_initial_geometry(self) -> None:
        # Compute an initial size responsive to content and screen
        try:
            self.update_idletasks()
            req_w = self.winfo_reqwidth()
            req_h = self.winfo_reqheight()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            # Target between 60% and 90% of screen, but not smaller than requested
            target_w = min(max(req_w, int(sw * 0.6)), int(sw * 0.9))
            target_h = min(max(req_h, int(sh * 0.6)), int(sh * 0.9))
            # Center on screen
            x = (sw - target_w) // 2
            y = max(20, (sh - target_h) // 4)
            self.geometry(f"{target_w}x{target_h}+{x}+{y}")
            # Set a reasonable minimum so things don't collapse
            self.minsize(int(sw * 0.5), int(sh * 0.5))
        except Exception:
            pass

    def _run_convert(self) -> None:
        if self._running:
            return
        xlsx = self.var_xml.get().strip()
        if not xlsx:
            messagebox.showwarning("Eingabe fehlt", "Bitte eine SchILD-XML-Datei auswählen.")
            return
        s = self.settings
        s.anton_xml_file = xlsx
        self._launch_thread(self._task_convert, s)

    def _run_pdf(self) -> None:
        if self._running:
            return
        # Einheitliche Pfadlogik über ein gemeinsames Feld
        path = (self.var_pdf_source.get() or "").strip()
        if not path:
            messagebox.showwarning("Eingabe fehlt", "Bitte eine CSV-Datei wählen.")
            return
        ext = os.path.splitext(path)[1].lower()
        s = self.settings
        if ext == ".csv":
            s.csv_file = path
            self._launch_thread(self._task_pdf_csv, s)
        else:
            messagebox.showwarning("Falsches Format", "Unterstützt wird nur .csv.")

    # ---------------- Background execution ----------------
    def _launch_thread(self, fn, s: Settings) -> None:
        self._set_running(True)
        self._println("Starte…\n")

        t = threading.Thread(target=self._run_captured, args=(fn, s), daemon=True)
        t.start()

    def _run_captured(self, fn, s: Settings) -> None:
        # Redirect stdout/stderr temporarily to GUI
        old_out, old_err = sys.stdout, sys.stderr
        stream = _TextStream(self._log_q)
        sys.stdout = stream
        sys.stderr = stream
        old_env = os.environ.get("NONINTERACTIVE")
        os.environ["NONINTERACTIVE"] = "1"
        try:
            fn(s)
        except Exception:
            traceback.print_exc()
        finally:
            # restore
            if old_env is None:
                os.environ.pop("NONINTERACTIVE", None)
            else:
                os.environ["NONINTERACTIVE"] = old_env
            sys.stdout = old_out
            sys.stderr = old_err
            self._set_running(False)
            self._println("\nFertig.\n")

    def _task_convert(self, s: Settings) -> None:
        # Use ANTON XML -> CSV converter
        try:
            conv = ANTONConverter(output_dir=s.anton_outputpath or "output")
            files = conv.convert(getattr(s, "anton_xml_file", ""))
            if files:
                print("Erstellt:")
                for k, v in files.items():
                    print(f" - {k}: {v}")
        except Exception as e:
            print(f"Fehler bei der Konvertierung: {e}")

    def _task_pdf_csv(self, s: Settings) -> None:
        PDFGenerator(s).generate()

    # ---------------- Logging ----------------
    def _println(self, text: str) -> None:
        self._log_q.put(text)

    def _drain_log_queue(self) -> None:
        try:
            while True:
                chunk = self._log_q.get_nowait()
                self._append_text(chunk)
        except queue.Empty:
            pass
        self.after(80, self._drain_log_queue)

    def _append_text(self, s: str) -> None:
        self.txt.configure(state=tk.NORMAL)
        self.txt.insert(tk.END, s)
        self.txt.see(tk.END)
        self.txt.configure(state=tk.DISABLED)


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: App, settings: Settings, on_save, section: str | None = None) -> None:
        super().__init__(parent)
        self.title("Einstellungen")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)

        self._parent = parent
        self._orig = settings
        self._on_save = on_save
        self._section = (section or "all").lower()

        def yesno_to_bool(v: str) -> bool:
            return (v or "").strip().lower() == "ja"

        # Variables
        self.var_anton_out = tk.StringVar(value=settings.anton_outputpath or "output")

        self.var_csv_delim = tk.StringVar(value=settings.csv_delimiter or ";")
        self.var_pdf_out = tk.StringVar(value=settings.pdf_outputpath or "pdf-files")
        self.var_pdf_source_link = tk.StringVar(value=settings.pdf_antonlink)
        self.var_pdf_onedoc = tk.BooleanVar(value=yesno_to_bool(getattr(settings, "pdf_onedoc", "nein")))
        self.var_pdf_schoolgroup = tk.StringVar(value=getattr(settings, "pdf_schoolgroup", "1") or "1")
        
        # XML mapping settings are no longer managed via GUI

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if self._section in ("anton", "all"):
            frm_anton = ttk.LabelFrame(body, text="ANTON")
            frm_anton.pack(fill=tk.X, padx=4, pady=6)
            ttk.Label(frm_anton, text="ANTON-Ausgabeordner:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
            ttk.Entry(frm_anton, textvariable=self.var_anton_out, width=50).grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Button(frm_anton, text="...", width=3, command=self._pick_output_dir).grid(row=0, column=2, padx=4, pady=4)
            ttk.Label(frm_anton, text="Hinweis: Die SchILD-XML-Datei wird im Hauptfenster gewählt.", foreground="#555").grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=4, pady=(2, 2))

        # CSV Optionen
        if self._section in ("pdf", "all"):
            frm_log = ttk.LabelFrame(body, text="CSV Optionen")
            frm_log.pack(fill=tk.X, padx=4, pady=6)
            ttk.Label(frm_log, text="CSV-Trennzeichen:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
            ttk.Entry(frm_log, textvariable=self.var_csv_delim, width=8).grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Label(frm_log, text="Hinweis: CSV-Datei wird im Hauptfenster gewählt.", foreground="#555").grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=4, pady=(2, 4))

        # PDF
        if self._section in ("pdf", "all"):
            frm_pdf = ttk.LabelFrame(body, text="PDF")
            frm_pdf.pack(fill=tk.X, padx=4, pady=6)
            ttk.Label(frm_pdf, text="PDF-Ausgabeordner:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
            ttk.Entry(frm_pdf, textvariable=self.var_pdf_out, width=50).grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Button(frm_pdf, text="…", width=3, command=self._pick_pdf_outdir).grid(row=0, column=2, padx=4, pady=4)
            ttk.Label(frm_pdf, text="ANTON-Link:").grid(row=1, column=0, sticky=tk.W, padx=4, pady=4)
            ttk.Entry(frm_pdf, textvariable=self.var_pdf_source_link, width=50).grid(row=1, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Label(frm_pdf, text="PDF-Ausgabe:").grid(row=2, column=0, sticky=tk.W, padx=4, pady=2)
            ttk.Radiobutton(frm_pdf, text="Sammeldokument (eine Datei, bei Schüler:innen pro Klasse)", variable=self.var_pdf_onedoc, value=True).grid(row=2, column=1, sticky=tk.W, padx=4, pady=2)
            ttk.Radiobutton(frm_pdf, text="Einzel-PDFs (je Person)", variable=self.var_pdf_onedoc, value=False).grid(row=3, column=1, sticky=tk.W, padx=4, pady=2)
            ttk.Label(frm_pdf, text="Adressaten:", anchor="w").grid(row=4, column=0, sticky=tk.W, padx=4, pady=2)
            ttk.Radiobutton(frm_pdf, text="Schüler:innen", variable=self.var_pdf_schoolgroup, value="1").grid(row=4, column=1, sticky=tk.W, padx=4, pady=2)
            ttk.Radiobutton(frm_pdf, text="Lehrkräfte", variable=self.var_pdf_schoolgroup, value="2").grid(row=5, column=1, sticky=tk.W, padx=4, pady=2)
            
            ttk.Label(frm_pdf, text="Hinweis: Der PDF-Ausgabeordner kann oben gesetzt werden.", foreground="#555").grid(row=6, column=0, columnspan=3, sticky=tk.W, padx=4, pady=(2, 4))
        # XML mapping section removed from GUI

        # Buttons
        frm_btn = ttk.Frame(self)
        frm_btn.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(frm_btn, text="Abbrechen", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(frm_btn, text="Speichern", command=self._save).pack(side=tk.RIGHT, padx=8)

        self.bind("<Escape>", lambda e: self.destroy())

    def _save(self) -> None:
        def yn(b: bool) -> str:
            return "ja" if b else "nein"

        one_doc = self.var_pdf_onedoc.get()
        pdf_onedoc = yn(one_doc)
        pdf_einzeln = yn(not one_doc)
        pdf_schoolgroup = "2" if (self.var_pdf_schoolgroup.get().strip() == "2") else "1"

        s = Settings(
            anton_xml_file=getattr(self._orig, "anton_xml_file", ""),
            anton_outputpath=self.var_anton_out.get().strip() or "output",
            csv_file=self._orig.csv_file,
            csv_delimiter=(self.var_csv_delim.get() or ";"),
            pdf_outputpath=self.var_pdf_out.get().strip() or "pdf-files",
            pdf_antonlink=self.var_pdf_source_link.get().strip(),
            pdf_einzeln=pdf_einzeln,
            pdf_onedoc=pdf_onedoc,
            pdf_schoolgroup=pdf_schoolgroup,
        )
        try:
            self._on_save(s)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Einstellungen", str(e))

    def _pick_output_dir(self) -> None:
        current = getattr(self._orig, "anton_outputpath", "output") or "output"
        start_dir = os.path.dirname(current) or appdir
        d = filedialog.askdirectory(title="ANTON-Ausgabeordner wählen", initialdir=start_dir)
        if d:
            self.var_anton_out.set(d)

    def _pick_pdf_outdir(self) -> None:
        d = filedialog.askdirectory(title="PDF-Ausgabeordner wählen", initialdir=os.path.dirname(self._orig.pdf_outputpath or appdir))
        if d:
            self.var_pdf_out.set(d)



def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()





















