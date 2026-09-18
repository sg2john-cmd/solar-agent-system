@echo off
rem ─────────────────────────────────────────────────────────────────────
rem  Moons A/B comparison — full A+B+C chamber, same 10 questions twice.
rem  Run A: moons OFF   then   Run B: moons ON   (comet OFF for both).
rem
rem  Requires LM Studio running with qwen3.8-27b loaded at 127.0.0.1:1234,
rem  context length raised (~80k) so long generations don't overflow.
rem
rem  Output is tee'd to tests\evidence\complex_ab_run_live.log AND the console.
rem  Expect ~25-30 min of live LLM time.
rem ─────────────────────────────────────────────────────────────────────
cd /d "A:\AI\Solar_Agent_System\v17\resonant_cognition"

echo.
echo === Moons A/B comparison starting... (log: tests\evidence\complex_ab_run_live.log) ===
echo     This runs ~25-30 min of live LLM time. Leave this window open.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "tests\_run_ab_tee.ps1"

set RC=%ERRORLEVEL%
echo.
echo === DONE (exit code %RC%). Transcripts saved to evidence as complex_ab_*.txt ===
pause
