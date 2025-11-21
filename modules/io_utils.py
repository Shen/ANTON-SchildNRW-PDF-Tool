import os
import sys
from typing import Optional

# Ermitteln des Basis-Verzeichnisses (auch im "frozen" Zustand)
if getattr(sys, "frozen", False):
    appdir = os.path.dirname(os.path.abspath(sys.executable))
else:
    appdir = os.path.dirname(os.path.abspath(__file__))
    appdir = os.path.abspath(os.path.join(appdir, ".."))

def resolve_path(p: str) -> str:
    """Nutze absolute Pfade direkt; relative Pfade werden an appdir angehängt."""
    return p if os.path.isabs(p) else os.path.join(appdir, p)

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def print_header() -> None:
    print("")
    print("ANTON-Tool")
    print("ZfsL Bielefeld")
    print("E-Mail: johannes.schirge@zfsl-bielefeld.nrw.schule")
    print("")
    print("This program comes with ABSOLUTELY NO WARRANTY")
    print("This is free software, and you are welcome to redistribute it under certain conditions.")
    print("For details look into LICENSE file (GNU GPLv3).")
    print("")
    print(f"Programmverzeichnis: {appdir}")

def ask_menu(prompt: str, allowed: set[int]) -> int:
    try:
        choice = int(input(prompt))
        if choice not in allowed:
            raise ValueError()
        return choice
    except (KeyboardInterrupt, EOFError):
        print("\nVorgang abgebrochen.")
        sys.exit(1)
    except Exception:
        print("\nFehlerhafte Eingabe! Das Programm wird abgebrochen.")
        sys.exit(1)


def pause(msg: Optional[str] = None) -> None:
    # Im NONINTERACTIVE-Modus (z. B. bei GUI/Batch) nicht blockieren
    if os.environ.get("NONINTERACTIVE", "0") == "1":
        return
    input(msg or "Weiter mit beliebiger Taste...")
