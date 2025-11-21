import os
import os.path
import sys
import time
import requests
import certifi
import csv
import string
import urllib.parse
import qrcode
import codecs
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from tabulate import tabulate
from bs4 import BeautifulSoup
from datetime import datetime

# This tool creates user-pdf-files from a CSV file, which you exported from ANTON App.

# Copyright (C) 2020 Johannes Schirge
# Mail: johannes@bi-co.net

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

print("")
print("Copyright (C) 2020 Johannes Schirge (Shen@github)")
print("This program comes with ABSOLUTELY NO WARRANTY")
print("This is free software, and you are welcome to redistribute it under certain conditions.")
print("For details look into LICENSE file (GNU GPLv3).")
print("")


# determine if running in a build package (frozen) or from seperate python script
frozen = 'not'
if getattr(sys, 'frozen', False):
  # we are running in a bundle
  appdir = os.path.dirname(os.path.abspath(sys.executable))
  ## print("Executable is in frozen state, appdir set to: " + appdir) # for debug
else:
  # we are running in a normal Python environment
  appdir = os.path.dirname(os.path.abspath(__file__))
  ## print("Executable is run in normal Python environment, appdir set to: " + appdir) # for debug

# read config from xml file
configfile = codecs.open(os.path.join(appdir,'config.xml'),mode='r', encoding='utf-8')
config = configfile.read()
configfile.close()

# load config values into variables
config_xmlsoup = BeautifulSoup(config, "html.parser") # parse
config_csvfile = config_xmlsoup.find('csvfile').string
config_csvDelimiter = config_xmlsoup.find('csvdelimiter').string
config_pdfOneDoc = config_xmlsoup.find('pdfonedoc').string
config_schoolgroup = config_xmlsoup.find('schoolgroup').string


# ANTON Info-Text
print("")
print("###################################################################################")
print("# ANTON PDF-Generator                                                             #")
print("# Dieses Tool erstellt PDF-Dateien mit den ANTON-Nutzernamen aus einer CSV-Datei. #")
print("###################################################################################")
print("")
print("")
print("Wenn du sicher bist, dass deine Einstellungen in der config.xml korrekt sind,")
print("drücke eine beliebige Taste, um fortzufahren.")
input("Andernfalls breche den Prozess mit [STRG + C] ab.")
print("")
print("Alles klar! Dann fangen wir mal an.")
print("")  

# check if user-import-csv-file exists
if not os.path.isfile(config_csvfile):
      print("FEHLER!")
      print("Die csv-Datei (" + config_csvfile + "), die Sie in der config.xml eingetragen haben, existiert nicht. Bitte speichern Sie die Datei '" + config_csvfile + "' im Hauptverzeichnis des Scripts oder bearbeiten Sie die config.xml")
      input("Drücken Sie eine beliebige Taste, um zu bestätigen und den Prozess zu beenden.")  
      sys.exit(1)

# set/create output-directory
output_dir = 'output'
if not os.path.exists(output_dir):
  os.makedirs(output_dir)

# set/create temporary-directory
tmp_dir = 'tmp'
if not os.path.exists(tmp_dir):
  os.makedirs(tmp_dir)

# adds date and time as string to variable
today = datetime.now().strftime('%Y-%m-%d_%H-%M-%S') 

# QR-Code class
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4,
)

# display expected results for ANTON-users
print("")
print("Hier eine Übersicht der importierten Nutzer:")
print("") 
usertable = [["Vorname","Name","Klasse","Referenz", "Login-Code"]]
with codecs.open(os.path.join(appdir, config_csvfile),mode='r', encoding='utf-8') as csvfile:
  readCSV = csv.reader(csvfile, delimiter=config_csvDelimiter)
  next(readCSV, None)  # skip the headers
  for row in readCSV:
    if (len(row) != 5): # check if number of columns is consistent
      print("FEHLER: Die Reihe des Nutzers",row[1],"hat",len(row),"Spalten. Es müssen 5 sein. Bitte korrigiere die csv-Datei.")
      input("Drücke eine beliebige Taste, um den Prozess zu beenden.")
      sys.exit(1)
    line = row[0]
    currentuser = [row[0],row[1],row[2],row[3],row[4]]
    usertable.append(currentuser)
print(tabulate(usertable,headers="firstrow"))

# ask user to check values and continue
print("\nÜberprüfe, ob die Daten für die zu generierenden PDF-Dateien korrekt sind.")
input("Wenn alles gut aussieht, drücke eine beliebige Taste, um fortzufahren. Wenn nicht, drücke Strg+C, um abzubrechen.")
print("\nUnd los geht's. Ich erstelle nun die PDF-Datei(en).\n")
print("\nDies kann eine Weile dauern. Gönn dir einen Kaffee oder Tee.\n")

# prepare pdf-output (if pdfOneDoc == ja)
if config_pdfOneDoc == 'ja':
  output_filename = "Nutzerliste_" + today + ".pdf"
  output_filepath = os.path.join( output_dir, output_filename )
  doc = SimpleDocTemplate(output_filepath, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=18, bottomMargin=18)

# prepare pdf-content
Story=[]

# read rows from CSV file
with codecs.open(os.path.join(appdir, config_csvfile),mode='r', encoding='utf-8') as csvfile:
  readCSV = csv.reader(csvfile, delimiter=config_csvDelimiter)
  next(readCSV, None)  # skip the headers
  for row in readCSV:
    line = row[0]
    print("Vorname:",row[0],"| Nachname:",row[1],"| Klasse: ",row[2],"| Referenz:",row[3],"| Login-Code:",row[4],)
  # build the dataset for the request
    data = [
      ('firstname', row[0]),
      ('surname', row[1]), 
      ('class', row[2]),
      ('reference', row[3]),
      ('logincode', row[4]),
      ]

    # generate qr-code
    qr.add_data(row[4])
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(os.path.join( tmp_dir, row[2] + "_" + row[1] + "_" + row[0] + ".jpg" ))
    qr.clear()

      # prepare pdf-output (if pdfOneDoc == nein)
    if config_pdfOneDoc == 'nein':
      output_filename = row[2] + "_" + row[1] + "_" + row[0] + "_" + today + ".pdf"
      output_filepath = os.path.join( output_dir, output_filename )
      doc = SimpleDocTemplate(output_filepath, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=18, bottomMargin=18)

    antonlogo = "assets/ANTON_Logo.jpg" # ANTON-Logo
    if config_schoolgroup == '1': #Schüler
      antonfirstname = row[0]
      antonsurname = row[1]
      antonclass = row[2]
      antonreference = row[3]
      antonlogincode = row[4]
      antonlink = "https://www.anton.app"
        
    if config_schoolgroup == '2': #Lehrer
      antonfirstname = row[0]
      antonsurname = row[1]
      antonclass = row[2]
      antonreference = row[3]
      antonlogincode = row[4]
      antonlink = "https://www.anton.app"
        
    # adds anton-logo to pdf-file 
    im = Image(antonlogo, 150, 150)
    Story.append(im)
    #Story.append(Spacer(1, 12))

    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))

    # adds text to pdf-file   
    ptext = '<font size=14>Hallo %s!</font>' % antonfirstname
    Story.append(Paragraph(ptext, styles["Justify"]))
    Story.append(Spacer(1, 12))

    ptext = '<font size=14>Willkommen bei ANTON – der Lern-App für die Schule.</font>'
    Story.append(Paragraph(ptext, styles["Normal"]))
    Story.append(Spacer(1, 12))

    ptext = '<font size=14>Für dich wurde ein Account angelegt.</font>'
    Story.append(Paragraph(ptext, styles["Normal"]))
    Story.append(Spacer(1, 24))

    ptext = '<font size=14>Gehe im Browser auf </font>'
    Story.append(Paragraph(ptext, styles["Normal"]))
    Story.append(Spacer(1, 12))

    ptext = '<font size=18>%s</font>' % antonlink
    Story.append(Paragraph(ptext, styles["Normal"]))
    Story.append(Spacer(1, 12))

    ptext = '<font size=14>oder lade dir die kostenlose ANTON-App herunter.</font>'
    Story.append(Paragraph(ptext, styles["Normal"]))
    Story.append(Spacer(1, 24))      

    ptext = '<font size=14>Du kannst dich mit folgendem Code bei ANTON einloggen:</font>'
    Story.append(Paragraph(ptext, styles["Normal"]))
    Story.append(Spacer(1, 24))

    ptext = '<font size=24>%s</font>' % antonlogincode
    Story.append(Paragraph(ptext, styles["Heading1"]))
    Story.append(Spacer(1, 24))

    ptext = '<font size=14>Oder du scannst in der ANTON-App diesen QR-Code:</font>'
    Story.append(Paragraph(ptext, styles["Normal"]))
    Story.append(Spacer(1, 12))         

    # adds qr-code to pdf-file
    im2 = Image(os.path.join( tmp_dir, row[2] + "_" + row[1] + "_" + row[0] + ".jpg" ), 200, 200)
    Story.append(im2)
    del im2
    if config_pdfOneDoc == 'nein':
      # create pdf-file (single documents)
      doc.build(Story)	  
    else:
      Story.append(PageBreak())

      # create pdf-file (one document)
if config_pdfOneDoc == 'ja':
  doc.build(Story)

# Clean up tmp-folder
filelist = [ f for f in os.listdir(tmp_dir) ]
for f in filelist:
    os.remove(os.path.join(tmp_dir, f))

print("")
print("###################################################################################")
print("# Es wurde für jeden Nutzer eine PDF-Seite mit Infos zur Anmeldung generiert.     #")
print("# Du findest die Datei(en) im Unterordner 'output'!                               #")
print("###################################################################################")
print("")
input("Drücke eine beliebige Taste, um den Prozess zu beenden.")
