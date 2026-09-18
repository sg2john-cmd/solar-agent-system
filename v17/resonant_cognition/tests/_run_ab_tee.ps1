# Tee the moons A/B chamber run to BOTH console and a clean UTF-8 log file.
# Tee-Object writes both stdout and stderr (2>&1) live AND captures them in $out.
# We then re-save $out as UTF-8, because Tee-Object's default file encoding is UTF-16
# which mangles the em-dashes / planet names when opened in a normal editor.

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { $OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$log  = Join-Path (Get-Location) 'tests\evidence\complex_ab_run_live.log'
if (Test-Path $log) { Remove-Item $log -Force }

# Live console + capture both streams into memory.
$out = python -X utf8 tests/run_complex_chamber_ab.py 2>&1 | Tee-Object -FilePath $log
$code = $LASTEXITCODE

# Re-save the captured output as UTF-8 so it opens cleanly in any editor.
[System.IO.File]::WriteAllLines($log, ($out | ForEach-Object { [string]$_ }), (New-Object System.Text.UTF8Encoding $false))

exit $code
