$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force -Path dist | Out-Null
uv run --with nuitka `
  --no-cache `
  nuitka --standalone --onefile `
    --include-package=textual `
    --include-package-data=textual `
    --include-package=httpx `
    --output-filename=dist\nasmanager-windows-x86_64.exe `
    src\nasmanager