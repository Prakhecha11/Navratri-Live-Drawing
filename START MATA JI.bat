   @echo off
   cd /d "%~dp0"
   set "PY=.venv\Scripts\python.exe"
   if not exist "%PY%" set "PY=python"
   "%PY%" -c "import cv2, numpy" 2>nul || "%PY%" -m pip install opencv-python numpy
   "%PY%" navratri_drawing.py
   pause