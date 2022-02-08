Set-Alias -Name "sqlite3" -Value "C:/SQLite3/sqlite3.exe" -Option constant -Scope global
venv\Scripts\Activate.ps1
$env:FLASK_ENV = "development"
# python app.py