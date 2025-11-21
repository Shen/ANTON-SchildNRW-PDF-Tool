from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
import re
import pandas as pd

from .io_utils import resolve_path, ensure_dir


def _xml_ns(root: ET.Element) -> Dict[str, str]:
    tag = root.tag
    if tag.startswith("{") and "}" in tag:
        uri = tag[1:].split("}")[0]
        return {"ns": uri}
    return {"ns": ""}


def _get_text_ns(el: ET.Element, path: str, ns: Dict[str, str], default: str = "") -> str:
    try:
        node = el.find(path, ns)
        if node is not None and node.text is not None:
            return node.text.strip()
        return default
    except Exception:
        return default


def _norm_klasse(raw: str) -> str:
    if not raw:
        return ""
    s = str(raw).strip()
    s = s.replace(" ", "")
    if len(s) == 2 and s[0] == "0" and s[1].isdigit():
        s = s[1]
    if len(s) >= 2 and s[-1].isalpha():
        return s[:-1] + s[-1].lower()
    return s


def _klasse_from_membership_id(group_id: str) -> str:
    if not group_id:
        return ""
    match = re.search(r"klasse-([^-\s]+)", group_id, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def _build_membership_class_map(root: ET.Element, ns: Dict[str, str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for membership in root.findall("ns:membership", ns):
        group_id = _get_text_ns(membership, "ns:sourcedid/ns:id", ns)
        klasse_raw = _klasse_from_membership_id(group_id)
        klasse = _norm_klasse(klasse_raw)
        if not klasse:
            continue
        for member in membership.findall("ns:member", ns):
            person_id = _get_text_ns(member, "ns:sourcedid/ns:id", ns)
            if person_id:
                result[person_id] = klasse
    return result


def _split_name(person: ET.Element, ns: Dict[str, str]) -> Tuple[str, str]:
    given = _get_text_ns(person, "ns:name/ns:n/ns:given", ns)
    family = _get_text_ns(person, "ns:name/ns:n/ns:family", ns)
    if not given and not family:
        full = _get_text_ns(person, "ns:name/ns:fn", ns)
        if full:
            parts = full.split(" ")
            if len(parts) >= 2:
                given = " ".join(parts[1:])
                family = parts[0]
            else:
                given = full
                family = ""
    return given, family


def _read_reference(person: ET.Element, ns: Dict[str, str]) -> str:
    return _get_text_ns(person, "ns:sourcedid/ns:id", ns)


def _anrede_from_reference(ref: str) -> str:
    """Derive German salutation from a SchILD-style ID in Referenz.

    Expected pattern example: "ID-2409843-0075X"
    - Middle token (here: 2409843) last digit denotes gender: 3=male, 4=female
    Returns "Herr", "Frau" or "" if not detectable.
    """
    try:
        if not ref:
            return ""
        parts = str(ref).strip().split("-")
        if len(parts) >= 2:
            middle = parts[1]
            if middle and middle[-1] in ("3", "4"):
                return "Herr" if middle[-1] == "3" else "Frau"
    except Exception:
        pass
    return ""


def _is_student(person: ET.Element, ns: Dict[str, str]) -> bool:
    for r in person.findall("ns:institutionrole", ns):
        t = (r.get("institutionroletype") or "").strip().lower()
        if t == "student":
            return True
    return False


def _is_teacher_like(person: ET.Element, ns: Dict[str, str]) -> bool:
    for r in person.findall("ns:institutionrole", ns):
        t = (r.get("institutionroletype") or "").strip().lower()
        if t in {"faculty", "extern", "teacher", "staff"}:
            return True
    if not _is_student(person, ns) and _get_text_ns(person, "ns:email", ns):
        return True
    return False


class ANTONConverter:
    def __init__(self, output_dir: Optional[str] = None) -> None:
        self.now = datetime.now()
        self.dt_string = self.now.strftime("%Y-%m-%d_%H-%M-%S")
        self.output_dir = resolve_path(output_dir or "output")
        ensure_dir(self.output_dir)

    def convert(self, xml_path: str) -> Dict[str, str]:
        xml_abs = resolve_path(xml_path)
        if not os.path.isfile(xml_abs):
            raise FileNotFoundError(f"XML-Datei nicht gefunden: {xml_abs}")

        tree = ET.parse(xml_abs)
        root = tree.getroot()
        ns = _xml_ns(root)
        klasse_lookup = _build_membership_class_map(root, ns)

        schueler_rows: List[Dict[str, str]] = []
        lehr_rows: List[Dict[str, str]] = []

        for person in root.findall("ns:person", ns):
            try:
                if _is_student(person, ns):
                    vorname, nachname = _split_name(person, ns)
                    ref = _read_reference(person, ns)
                    klasse = klasse_lookup.get(ref, "")
                    if vorname or nachname:
                        schueler_rows.append({
                            "Vorname": vorname,
                            "Nachname": nachname,
                            "Klasse": klasse,
                            "Referenz": ref,
                        })
                elif _is_teacher_like(person, ns):
                    vorname, nachname = _split_name(person, ns)
                    ref = _read_reference(person, ns)
                    anrede = _anrede_from_reference(ref)
                    lehr_rows.append({
                        "Anrede": anrede,
                        "Vorname": vorname,
                        "Nachname": nachname,
                        "Referenz": ref,
                    })
            except Exception:
                continue

        df_s = pd.DataFrame(schueler_rows, columns=["Vorname", "Nachname", "Klasse", "Referenz"])
        df_l = pd.DataFrame(lehr_rows, columns=["Anrede", "Vorname", "Nachname", "Referenz"])

        out_files: Dict[str, str] = {}
        if not df_s.empty:
            f_s = os.path.join(self.output_dir, f"{self.dt_string}_ANTON_Schueler.csv")
            df_s.to_csv(f_s, sep=';', index=False, encoding='utf-8-sig')
            out_files["schueler_csv"] = f_s
        if not df_l.empty:
            f_l = os.path.join(self.output_dir, f"{self.dt_string}_ANTON_Lehrkraefte.csv")
            df_l.to_csv(f_l, sep=';', index=False, encoding='utf-8-sig')
            out_files["lehrkraefte_csv"] = f_l

        return out_files
