@echo off
rem Ouvre l'annotateur de BOITES (entrainement d'un detecteur de tetes).
rem Double-clic suffit - aucune ligne de commande a taper.
rem pythonw = aucun terminal noir ; la fenetre graphique suffit.
cd /d "%~dp0"
start "" "C:\Python311\pythonw.exe" "tools\annotateur_boites.py" %*
