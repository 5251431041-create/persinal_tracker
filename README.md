# TrackOS

Personal tracker for gym, attendance, timetable, and study progress.

## Laptop

```powershell
cd D:\persinal_tracker
pip install -r requirements.txt
python -m flask --app app run --debug
```

Open http://127.0.0.1:5000

## Mobile on same Wi-Fi

Run:

```powershell
D:\persinal_tracker\run_mobile.bat
```

Open on phone:

```text
http://192.168.29.202:5000
```

Then install it:

- Android Chrome: menu > Add to Home screen > Install
- iPhone Safari: Share > Add to Home Screen

Keep the laptop server running while using it on mobile.

## Access from anywhere

Deploy to Render:

1. Push this folder to a GitHub repository.
2. In Render, create a new Web Service from that repository.
3. Use:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Add a persistent disk mounted at `/var/data`.
5. Add environment variable:
   - `TRACKOS_DATA_DIR=/var/data`
   - `SECRET_KEY=<any long random text>`
   - `ADMIN_PASSWORD=<your private app password>`

After deploy, open the Render URL on laptop or phone and install it from the browser.

## Ship-next checklist

- Add login before hosting publicly.
- Replace JSON files with SQLite when multiple users are needed.
- Add username/password before sharing the URL with anyone.
