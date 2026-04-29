@echo off
cd /d %~dp0
python -m flask --app app run --host 127.0.0.1 --port 5000 --debug
