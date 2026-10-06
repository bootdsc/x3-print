@echo off
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller pywebview pyserial || exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --windowed --name X3Print ^
  --icon "%~dp0assets\x3print.ico" --add-data "%~dp0x3print\web;x3print\web" ^
  --exclude-module numpy --exclude-module PIL --exclude-module tkinter ^
  --specpath build --workpath build --distpath dist X3Print.pyw || exit /b 1
echo Built dist\X3Print.exe
