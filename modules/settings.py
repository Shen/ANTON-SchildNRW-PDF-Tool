from dataclasses import dataclass
import xml.etree.ElementTree as ET
from typing import Optional


@dataclass
class Settings:
    # ANTON Konverter
    anton_xml_file: str
    anton_outputpath: str

    # CSV/PDF-Generator
    csv_file: str

    # CSV/PDF-Optionen
    csv_delimiter: str = ";"
    pdf_outputpath: str = "pdf-files"
    pdf_antonlink: str = "https://www.anton.app"
    pdf_einzeln: str = "ja"  # legacy flag, "ja" = einzelne PDFs
    pdf_onedoc: str = "nein"  # "ja" = Sammeldokument wie im alten ANTON-PDF
    pdf_schoolgroup: str = "1"  # "1"=Schüler:innen, "2"=Lehrkräfte


def _get_text(root: ET.Element, tag: str, default: str = "") -> str:
    el = root.find(tag)
    return el.text.strip() if el is not None and el.text is not None else default


def _warn_invalid(raw: str, varname: str, default: str) -> None:
    print(f"Ungueltiger Wert {raw!r} fuer Variable {varname!r} in der config.xml. Nutze Standardwert {default!r}")


def _norm_yes_no(value: str, *, varname: str, default_yes: bool) -> str:
    v_raw = value or ""
    v = v_raw.strip().lower()
    if v == "":
        return "ja" if default_yes else "nein"
    if v in ("ja", "nein"):
        return v
    default_str = "ja" if default_yes else "nein"
    _warn_invalid(v_raw, varname, default_str)
    return default_str


def load_settings(config_path: str) -> Settings:
    with open(config_path, "r", encoding="utf-8") as f:
        xml_text = f.read()
    root = ET.fromstring(xml_text)

    # ANTON-Pfade
    anton_xml_file = _get_text(root, "anton_xml_file")
    anton_outputpath = _get_text(root, "anton_outputpath", "output")

    # CSV/PDF
    csv_file = _get_text(root, "csv_file")
    csv_delimiter = _get_text(root, "csv_delimiter", ";")
    pdf_outputpath = _get_text(root, "pdf_outputpath", "pdf-files")
    pdf_antonlink = _get_text(root, "pdf_antonlink", "https://www.anton.app")
    pdf_einzeln_raw = _get_text(root, "pdf_einzeln", "ja")
    pdf_onedoc_raw = _get_text(root, "pdf_onedoc", "")
    pdf_schoolgroup_raw = _get_text(root, "pdf_schoolgroup", "1")

    pdf_einzeln = _norm_yes_no(pdf_einzeln_raw, varname="pdf_einzeln", default_yes=True)
    pdf_onedoc = _norm_yes_no(pdf_onedoc_raw, varname="pdf_onedoc", default_yes=False)
    # Kompatibilität: Falls pdf_onedoc nicht gesetzt ist, leite es aus pdf_einzeln ab
    if pdf_onedoc_raw.strip() == "":
        pdf_onedoc = "nein" if pdf_einzeln == "ja" else "ja"
    pdf_schoolgroup = "2" if pdf_schoolgroup_raw.strip() == "2" else "1"

    return Settings(
        anton_xml_file=(anton_xml_file or ""),
        anton_outputpath=anton_outputpath,
        csv_file=csv_file,
        csv_delimiter=csv_delimiter,
        pdf_outputpath=pdf_outputpath,
        pdf_antonlink=pdf_antonlink,
        pdf_einzeln=pdf_einzeln,
        pdf_onedoc=pdf_onedoc,
        pdf_schoolgroup=pdf_schoolgroup,
    )


def save_settings(config_path: str, s: Settings) -> None:
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
    except Exception:
        root = ET.Element("config")
        tree = ET.ElementTree(root)

    def set_text(tag: str, value: Optional[str]) -> None:
        el = root.find(tag)
        if el is None:
            el = ET.SubElement(root, tag)
        el.text = (value or "")

    # ANTON / PDF
    set_text("anton_xml_file", s.anton_xml_file)
    set_text("anton_outputpath", s.anton_outputpath)
    set_text("csv_file", s.csv_file)
    set_text("csv_delimiter", s.csv_delimiter)
    set_text("pdf_outputpath", s.pdf_outputpath)
    set_text("pdf_antonlink", s.pdf_antonlink)
    set_text("pdf_einzeln", s.pdf_einzeln)
    set_text("pdf_onedoc", s.pdf_onedoc)
    set_text("pdf_schoolgroup", s.pdf_schoolgroup)
    tree.write(config_path, encoding="utf-8", xml_declaration=False)


