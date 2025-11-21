# ANTON SchILD NRW Tool

Dieses Projekt bündelt den ANTON-Konverter und den PDF-Generator in einer schlanken Desktop-Anwendung.
Beide Bereiche richten sich ausschließlich auf den SchILD NRW → ANTON-Workflow.

## Funktionen

- **ANTON Konverter**: Wandelt eine SchILD NRW XML-Datei in zwei ANTON-kompatible CSVs (Schüler:innen und Lehrkräfte).
- **PDF-Generator**: Erzeugt personalisierte Zugangsdaten-PDFs aus CSV- oder Excel-Dateien (z. B. aus dem Konverter exportiert).

## Konfiguration

Die Datei `config.xml` im Programmordner speichert Pfade, Standard-Trennzeichen, PDF-Optionen und Support-Kontakt.
Alle Felder können auch direkt im Programm unter *Einstellungen* gepflegt werden.

## Nutzung

1. Anwendung starten, Einstellungen prüfen (insbesondere Ausgabeordner).
2. Im Tab **ANTON Konverter** die SchILD-XML auswählen und `Konvertieren` klicken.
   Es entstehen zwei CSV-Dateien im konfigurierten Ordner.
3. Im Tab **PDF-Generator** die CSV/XLS-Datei wählen und PDFs erzeugen.
   Optional können Einzel-PDFs oder eine Gesamtliste erstellt werden.

## Build

### Windows

```
powershell -ExecutionPolicy Bypass -File scripts/build_win_utf8.ps1 -OneFile
```
Alternativ `-OneDir` für ein entpacktes Build.

### macOS

```
chmod +x scripts/build_mac.sh
ONEFILE=1 scripts/build_mac.sh
```

## Lizenz

- Lizenz: GNU GPLv3 (siehe `LICENSE`).
- Nutzung auf eigene Verantwortung; Marken gehören den jeweiligen Inhabern.