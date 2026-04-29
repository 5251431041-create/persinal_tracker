@echo off
cd /d %~dp0
echo.
echo TrackOS laptop: http://127.0.0.1:5000
echo TrackOS phone:  http://192.168.29.202:5000
echo.
echo Keep this window open while using the app on mobile.
echo.
python -m flask --app app run --host 0.0.0.0 --port 5000 --debug
