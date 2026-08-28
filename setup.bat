@echo off
REM Cree un environnement virtuel et installe les dependances.
cd /d "%~dp0"

python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Environnement pret. Pour lancer l'app :
echo   venv\Scripts\activate
echo   python app.py
