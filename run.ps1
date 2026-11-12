$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv')) { python -m venv .venv }
& ./.venv/Scripts/python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependencies failed' }
$securePassword = Read-Host 'Administrator paroli' -AsSecureString
$env:ADMIN_PASSWORD = [System.Net.NetworkCredential]::new('', $securePassword).Password
$env:SECRET_KEY = & ./.venv/Scripts/python.exe -c 'import secrets; print(secrets.token_hex(32))'
& ./.venv/Scripts/python.exe -m flask --app app:create_app seed
& ./.venv/Scripts/python.exe app.py
