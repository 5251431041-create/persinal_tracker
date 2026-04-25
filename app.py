from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import json, os, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__)

DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

def read_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def write_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def graph_path(filename):
    # Works both locally and on PythonAnywhere
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'static', 'graphs', filename)

@app.route('/')
def home():
    return redirect(url_for('gym'))

# ── GYM ───────────────────────────────────────────────────────────────────────

@app.route('/gym', methods=['GET','POST'])
def gym():
    path = 'data/gym_log.json'
    logs = read_json(path)
    if request.method == 'POST':
        logs.append({
            "date":     request.form['date'],
            "exercise": request.form['exercise'].strip().title(),
            "weight":   float(request.form['weight']),
            "reps":     int(request.form['reps']),
            "sets":     int(request.form['sets'])
        })
        write_json(path, logs)
        return redirect(url_for('gym'))
    exercises = sorted(set(e['exercise'] for e in logs))
    return render_template('gym.html', logs=logs, exercises=exercises)

@app.route('/gym/graph')
def gym_graph():
    exercise = request.args.get('exercise', '')
    logs = read_json('data/gym_log.json')
    filtered = sorted([e for e in logs if e['exercise'] == exercise], key=lambda e: e['date'])
    if not filtered:
        return "No data.", 404
    dates   = [e['date']   for e in filtered]
    weights = [e['weight'] for e in filtered]
    fig, ax = plt.subplots(figsize=(8,4))
    ax.plot(dates, weights, marker='o', color='steelblue', linewidth=2)
    ax.set_title(f'Progression - {exercise}')
    ax.set_xlabel('Date')
    ax.set_ylabel('Weight (kg)')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    fname = f"gym_{exercise.replace(' ','_')}.png"
    plt.savefig(graph_path(fname))
    plt.close()
    return render_template('gym_graph.html', graph_file=fname, exercise=exercise)

@app.route('/gym/delete/<int:index>', methods=['POST'])
def gym_delete(index):
    path = 'data/gym_log.json'
    logs = read_json(path)
    real = len(logs) - 1 - index
    if 0 <= real < len(logs):
        logs.pop(real)
        write_json(path, logs)
    return redirect(url_for('gym'))

# ── TIMETABLE ─────────────────────────────────────────────────────────────────

@app.route('/attendance/timetable', methods=['GET','POST'])
def timetable():
    path = 'data/timetable.json'
    tt   = read_json(path)
    if request.method == 'POST':
        for day in DAYS:
            tt[day] = int(request.form.get(day, 0))
        write_json(path, tt)
        return redirect(url_for('timetable'))
    return render_template('timetable.html', timetable=tt, days=DAYS)

# ── ATTENDANCE ────────────────────────────────────────────────────────────────

@app.route('/attendance', methods=['GET','POST'])
def attendance():
    att_path = 'data/attendance.json'
    tt_path  = 'data/timetable.json'
    logs = read_json(att_path)
    tt   = read_json(tt_path)

    if request.method == 'POST':
        date_str  = request.form['date']
        attended  = int(request.form['attended'])
        day_name  = datetime.strptime(date_str, '%Y-%m-%d').strftime('%A')
        scheduled = tt.get(day_name, 0)
        found = False
        for log in logs:
            if log['date'] == date_str:
                log['attended']  = attended
                log['scheduled'] = scheduled
                found = True
                break
        if not found:
            logs.append({"date": date_str, "day": day_name,
                         "scheduled": scheduled, "attended": attended})
        logs.sort(key=lambda x: x['date'])
        write_json(att_path, logs)
        return redirect(url_for('attendance'))

    total_scheduled = sum(log['scheduled'] for log in logs)
    total_attended  = sum(log['attended']  for log in logs)
    overall_pct     = round((total_attended / total_scheduled) * 100, 1) if total_scheduled > 0 else 0

    selected_date    = request.args.get('date', '')
    day_scheduled    = 0
    prefill_attended = 0
    if selected_date:
        try:
            day_name      = datetime.strptime(selected_date, '%Y-%m-%d').strftime('%A')
            day_scheduled = tt.get(day_name, 0)
            for log in logs:
                if log['date'] == selected_date:
                    prefill_attended = log['attended']
                    break
        except ValueError:
            pass

    return render_template('attendance.html',
                           logs=logs,
                           total_scheduled=total_scheduled,
                           total_attended=total_attended,
                           overall_pct=overall_pct,
                           selected_date=selected_date,
                           day_scheduled=day_scheduled,
                           prefill_attended=prefill_attended)

@app.route('/attendance/delete/<string:date>', methods=['POST'])
def attendance_delete(date):
    path = 'data/attendance.json'
    logs = [l for l in read_json(path) if l['date'] != date]
    write_json(path, logs)
    return redirect(url_for('attendance'))

@app.route('/attendance/graph')
def attendance_graph():
    logs = read_json('data/attendance.json')
    if not logs:
        return "No data yet.", 404
    dates, percents = [], []
    cs, ca = 0, 0
    for log in logs:
        cs += log['scheduled']
        ca += log['attended']
        if cs > 0:
            dates.append(log['date'])
            percents.append(round((ca / cs) * 100, 1))
    fig, ax = plt.subplots(figsize=(9,4))
    ax.plot(dates, percents, marker='o', color='steelblue', linewidth=2)
    ax.axhline(75, color='red', linestyle='--', linewidth=1, label='75%')
    ax.fill_between(dates, percents, 75,
                    where=[p < 75 for p in percents],
                    alpha=0.15, color='red')
    ax.set_title('Overall Attendance - Cumulative %')
    ax.set_xlabel('Date')
    ax.set_ylabel('%')
    ax.set_ylim(0, 105)
    ax.legend()
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    fname = 'attendance_overall.png'
    plt.savefig(graph_path(fname))
    plt.close()
    return render_template('attendance_graph.html', graph_file=fname)

# ── STUDY ─────────────────────────────────────────────────────────────────────

@app.route('/study', methods=['GET','POST'])
def study():
    path = 'data/study.json'
    logs = read_json(path)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            logs.append({
                "subject": request.form['subject'].strip().title(),
                "topic":   request.form['topic'].strip(),
                "lessons": [False, False, False, False, False],
                "date":    request.form['date'],
                "notes":   request.form.get('notes','').strip()
            })
            write_json(path, logs)

        elif action == 'toggle_lesson':
            idx          = int(request.form['index'])
            lesson_index = int(request.form['lesson_index'])
            if 0 <= idx < len(logs) and 0 <= lesson_index <= 4:
                logs[idx]['lessons'][lesson_index] = not logs[idx]['lessons'][lesson_index]
                write_json(path, logs)

        elif action == 'delete':
            idx = int(request.form['index'])
            if 0 <= idx < len(logs):
                logs.pop(idx)
                write_json(path, logs)

        return redirect(url_for('study'))

    fs = request.args.get('subject', 'All')
    fx = request.args.get('status',  'All')

    displayed = []
    for i, entry in enumerate(logs):
        done_count  = sum(entry['lessons'])
        is_complete = (done_count == 5)
        if fs != 'All' and entry['subject'] != fs:
            continue
        if fx == 'complete'   and not is_complete:
            continue
        if fx == 'incomplete' and is_complete:
            continue
        displayed.append((i, entry, done_count))

    subjects = sorted(set(e['subject'] for e in logs))

    progress = {}
    for subj in subjects:
        subj_logs = [e for e in logs if e['subject'] == subj]
        done_lessons  = sum(sum(e['lessons']) for e in subj_logs)
        total_lessons = len(subj_logs) * 5
        progress[subj] = {
            "topics":          len(subj_logs),
            "done_lessons":    done_lessons,
            "total_lessons":   total_lessons,
            "complete_topics": sum(1 for e in subj_logs if sum(e['lessons']) == 5)
        }

    return render_template('study.html',
                           displayed=displayed,
                           subjects=subjects,
                           progress=progress,
                           filter_subject=fs,
                           filter_status=fx)

# ── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True)