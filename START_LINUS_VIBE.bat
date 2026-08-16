@echo off
cd /d "%~dp0"
python linus_vibe.py --cwd "%CD%" %*
