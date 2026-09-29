$ErrorActionPreference = "Stop"
Write-Host "Applying Django migrations..." -ForegroundColor Cyan
python manage.py migrate --noinput
Write-Host "Starting Aarogya backend at http://127.0.0.1:8000/" -ForegroundColor Green
python manage.py runserver
