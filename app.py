from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from math import ceil
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, Response, flash, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('TRACKOS_DATA_DIR', BASE_DIR / 'data'))
GRAPH_DIR = BASE_DIR / 'static' / 'graphs'
DATA_DIR.mkdir(exist_ok=True)
GRAPH_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-before-hosting')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
COMMON_EXERCISES = [
    'incline bench press',
    'pec-dec fly',
    'shoulder press',
    'machine lateral raise',
    'tricep push downs',
    'preacher curls',
    't-bars rows',
    'lat pulldowns',
    'lat row(single arm)',
    'hammer curls',
    'squats',
    "SLDL'S",
    'GOBLIN SQUATS OR LEG EXTENSIONS',
    'incline dumbell press',
    'macine incline-fly',
    'machine rows',
    'single hand triceo-pushdowns',
    'incline dumbell curls',
    'cable lateral raises',
]
DEFAULTS = {
    'gym_log.json': [],
    'gym_plan.json': {day: [] for day in DAYS},
    'attendance.json': [],
    'study.json': [],
    'timetable.json': {day: 0 for day in DAYS},
}


def data_path(name: str) -> Path:
    return DATA_DIR / name


def read_json(name: str):
    path = data_path(name)
    if not path.exists():
        write_json(name, DEFAULTS[name])
    try:
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return DEFAULTS[name].copy() if isinstance(DEFAULTS[name], dict) else list(DEFAULTS[name])


def write_json(name: str, data) -> None:
    tmp = data_path(f'{name}.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    tmp.replace(data_path(name))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not ADMIN_PASSWORD or session.get('authenticated'):
            return view(*args, **kwargs)
        return redirect(url_for('login', next=request.full_path))
    return wrapped


def parse_date(value: str) -> str:
    return datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d')


def positive_float(value: str, label: str) -> float:
    number = float(value)
    if number <= 0:
        raise ValueError(f'{label} must be greater than zero.')
    return number


def positive_int(value: str, label: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError(f'{label} must be greater than zero.')
    return number


def attendance_stats(logs):
    total_scheduled = sum(int(log.get('scheduled', 0)) for log in logs)
    total_attended = sum(int(log.get('attended', 0)) for log in logs)
    overall_pct = round((total_attended / total_scheduled) * 100, 1) if total_scheduled else 0
    return total_scheduled, total_attended, overall_pct


def exercise_rows(exercises, weights, reps, sets, include_date=None):
    rows = []
    max_len = max(len(exercises), len(weights), len(reps), len(sets), 0)
    for i in range(max_len):
        exercise = exercises[i].strip().title() if i < len(exercises) else ''
        weight = weights[i].strip() if i < len(weights) else ''
        rep = reps[i].strip() if i < len(reps) else ''
        set_count = sets[i].strip() if i < len(sets) else ''

        if not any([exercise, weight, rep, set_count]):
            continue
        if not all([exercise, weight, rep, set_count]):
            raise ValueError('Complete every filled exercise row, or remove it.')

        row = {
            'exercise': exercise,
            'weight': positive_float(weight, 'Weight'),
            'reps': positive_int(rep, 'Reps'),
            'sets': positive_int(set_count, 'Sets'),
        }
        if include_date:
            row['date'] = include_date
        rows.append(row)
    return rows


def current_week_dates(today):
    start = today - timedelta(days=today.weekday())
    return [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]


def streak_from_dates(date_values):
    dates = {datetime.strptime(value, '%Y-%m-%d').date() for value in date_values}
    day = datetime.now().date()
    streak = 0
    while day in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


@app.route('/login', methods=['GET', 'POST'])
def login():
    if not ADMIN_PASSWORD:
        session['authenticated'] = True
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        if secrets.compare_digest(password, ADMIN_PASSWORD):
            session['authenticated'] = True
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Wrong password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    gym_logs = read_json('gym_log.json')
    gym_plan = read_json('gym_plan.json')
    for day in DAYS:
        gym_plan.setdefault(day, [])
    attendance_logs = read_json('attendance.json')
    timetable = read_json('timetable.json')
    study_logs = read_json('study.json')
    today_dt = datetime.now()
    today = today_dt.strftime('%Y-%m-%d')
    today_name = today_dt.strftime('%A')
    week_dates = current_week_dates(today_dt)

    total_scheduled, total_attended, overall_pct = attendance_stats(attendance_logs)
    total_lessons = len(study_logs) * 5
    done_lessons = sum(sum(entry.get('lessons', [])) for entry in study_logs)
    study_pct = round((done_lessons / total_lessons) * 100) if total_lessons else 0
    latest_gym = sorted(gym_logs, key=lambda row: row.get('date', ''), reverse=True)[:5]

    today_plan = gym_plan.get(today_name, [])
    today_classes = int(timetable.get(today_name, 0))
    today_attendance = next((log for log in attendance_logs if log.get('date') == today), None)
    study_due = [
        entry for entry in study_logs
        if entry.get('date', today) <= today and sum(entry.get('lessons', [])) < 5
    ][:5]

    gym_week_days = sorted({entry['date'] for entry in gym_logs if entry.get('date') in week_dates})
    attendance_week = [log for log in attendance_logs if log.get('date') in week_dates]
    week_scheduled, week_attended, week_attendance_pct = attendance_stats(attendance_week)
    study_week_lessons = sum(
        sum(entry.get('lessons', [])) for entry in study_logs if entry.get('date') in week_dates
    )

    gym_goal = 4
    study_goal = 10
    attendance_goal = 75
    gym_streak = streak_from_dates(entry['date'] for entry in gym_logs)
    study_streak = streak_from_dates(entry['date'] for entry in study_logs if sum(entry.get('lessons', [])) > 0)
    attendance_streak = streak_from_dates(
        log['date'] for log in attendance_logs
        if int(log.get('scheduled', 0)) > 0 and int(log.get('attended', 0)) >= int(log.get('scheduled', 0))
    )
    classes_needed = 0
    safe_misses = 0
    if total_scheduled:
        if overall_pct < attendance_goal:
            classes_needed = ceil((0.75 * total_scheduled - total_attended) / 0.25)
        else:
            safe_misses = int((total_attended - 0.75 * total_scheduled) / 0.75)

    insights = []
    if today_classes and not today_attendance:
        insights.append(f'You have {today_classes} classes scheduled today.')
    if today_plan:
        insights.append(f'{today_name} gym plan has {len(today_plan)} exercises ready.')
    if overall_pct < attendance_goal and total_scheduled:
        insights.append(f'Attend {classes_needed} classes in a row to reach 75%.')
    elif total_scheduled:
        insights.append(f'You can miss {safe_misses} classes and stay above 75%.')
    if len(gym_week_days) < gym_goal:
        insights.append(f'{gym_goal - len(gym_week_days)} gym day(s) left for this week goal.')
    if study_week_lessons < study_goal:
        insights.append(f'{study_goal - study_week_lessons} study lesson(s) left for this week goal.')

    return render_template(
        'dashboard.html',
        gym_count=len(gym_logs),
        latest_gym=latest_gym,
        today_name=today_name,
        today_plan=today_plan,
        today_classes=today_classes,
        today_attendance=today_attendance,
        study_due=study_due,
        week_dates=week_dates,
        gym_week_days=gym_week_days,
        week_attendance_pct=week_attendance_pct,
        week_attended=week_attended,
        week_scheduled=week_scheduled,
        study_week_lessons=study_week_lessons,
        gym_goal=gym_goal,
        study_goal=study_goal,
        attendance_goal=attendance_goal,
        gym_streak=gym_streak,
        study_streak=study_streak,
        attendance_streak=attendance_streak,
        classes_needed=classes_needed,
        safe_misses=safe_misses,
        insights=insights,
        total_scheduled=total_scheduled,
        total_attended=total_attended,
        overall_pct=overall_pct,
        study_topics=len(study_logs),
        done_lessons=done_lessons,
        total_lessons=total_lessons,
        study_pct=study_pct,
        today=today,
    )


@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')


@app.route('/export')
@login_required
def export_data():
    payload = {
        'exported_at': datetime.now().isoformat(timespec='seconds'),
        'gym_log': read_json('gym_log.json'),
        'gym_plan': read_json('gym_plan.json'),
        'attendance': read_json('attendance.json'),
        'timetable': read_json('timetable.json'),
        'study': read_json('study.json'),
    }
    return Response(
        json.dumps(payload, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=trackos-export.json'},
    )


@app.route('/gym', methods=['GET', 'POST'])
@login_required
def gym():
    logs = read_json('gym_log.json')
    gym_plan = read_json('gym_plan.json')
    for day in DAYS:
        gym_plan.setdefault(day, [])
    if request.method == 'POST':
        try:
            date = parse_date(request.form['date'])
            exercises = request.form.getlist('exercise[]') or request.form.getlist('exercise')
            weights = request.form.getlist('weight[]') or request.form.getlist('weight')
            reps = request.form.getlist('reps[]') or request.form.getlist('reps')
            sets = request.form.getlist('sets[]') or request.form.getlist('sets')

            entries = exercise_rows(exercises, weights, reps, sets, include_date=date)

            if not entries:
                raise ValueError('Add at least one complete exercise.')
            logs.extend(entries)
            logs.sort(key=lambda row: row['date'])
            write_json('gym_log.json', logs)
            flash(f'{len(entries)} exercise(s) saved.', 'ok')
        except (IndexError, KeyError, ValueError) as exc:
            flash(str(exc), 'error')
        return redirect(url_for('gym'))

    exercises = sorted({entry['exercise'] for entry in logs})
    exercise_options = sorted(set(COMMON_EXERCISES) | set(exercises))
    sessions = {}
    for index, entry in enumerate(logs):
        sessions.setdefault(entry['date'], []).append((index, entry))
    workout_days = len(sessions)
    total_volume = int(sum(float(entry['weight']) * int(entry['reps']) * int(entry['sets']) for entry in logs))
    total_sets = sum(int(entry['sets']) for entry in logs)
    top_exercise = ''
    if logs:
        top_exercise = max(
            exercises,
            key=lambda name: sum(1 for entry in logs if entry['exercise'] == name),
        )
    grouped_sessions = sorted(sessions.items(), reverse=True)
    latest_session = []
    if grouped_sessions:
        latest_session = [entry for _, entry in grouped_sessions[0][1]]
    return render_template(
        'gym.html',
        logs=logs,
        exercises=exercises,
        exercise_options=exercise_options,
        gym_plan=gym_plan,
        days=DAYS,
        grouped_sessions=grouped_sessions,
        latest_session=latest_session,
        workout_days=workout_days,
        total_volume=total_volume,
        total_sets=total_sets,
        top_exercise=top_exercise,
        today=datetime.now().strftime('%Y-%m-%d'),
    )


@app.route('/gym/plan', methods=['POST'])
@login_required
def gym_plan_save():
    gym_plan = read_json('gym_plan.json')
    for day_name in DAYS:
        gym_plan.setdefault(day_name, [])
    try:
        day = request.form['day']
        if day not in DAYS:
            raise ValueError('Choose a valid day.')
        exercises = request.form.getlist('plan_exercise[]')
        weights = request.form.getlist('plan_weight[]')
        reps = request.form.getlist('plan_reps[]')
        sets = request.form.getlist('plan_sets[]')

        plan_entries = exercise_rows(exercises, weights, reps, sets)
        gym_plan[day] = plan_entries
        write_json('gym_plan.json', gym_plan)
        flash(f'{day} plan saved.', 'ok')
    except (IndexError, KeyError, ValueError) as exc:
        flash(str(exc), 'error')
    return redirect(url_for('gym'))


@app.route('/gym/graph')
@login_required
def gym_graph():
    exercise = request.args.get('exercise', '')
    logs = read_json('gym_log.json')
    filtered = sorted([entry for entry in logs if entry.get('exercise') == exercise], key=lambda entry: entry['date'])
    if not filtered:
        flash('Add data for that exercise first.', 'error')
        return redirect(url_for('gym'))

    dates = [entry['date'] for entry in filtered]
    weights = [entry['weight'] for entry in filtered]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(dates, weights, marker='o', color='#2563eb', linewidth=2)
    ax.set_title(f'{exercise} Progress')
    ax.set_xlabel('Date')
    ax.set_ylabel('Weight (kg)')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    fname = f"gym_{exercise.replace(' ', '_')}.png"
    plt.savefig(GRAPH_DIR / fname)
    plt.close()
    return render_template('gym_graph.html', graph_file=fname, exercise=exercise)


@app.route('/gym/repeat-last', methods=['POST'])
@login_required
def gym_repeat_last():
    logs = read_json('gym_log.json')
    if not logs:
        flash('No previous workout to repeat.', 'error')
        return redirect(url_for('gym'))

    date = request.form.get('date') or datetime.now().strftime('%Y-%m-%d')
    try:
        date = parse_date(date)
    except ValueError:
        date = datetime.now().strftime('%Y-%m-%d')

    latest_date = max(entry['date'] for entry in logs)
    copied = []
    for entry in logs:
        if entry['date'] == latest_date:
            copied.append({
                'date': date,
                'exercise': entry['exercise'],
                'weight': entry['weight'],
                'reps': entry['reps'],
                'sets': entry['sets'],
            })

    logs.extend(copied)
    logs.sort(key=lambda row: row['date'])
    write_json('gym_log.json', logs)
    flash(f'Repeated {len(copied)} exercise(s) from {latest_date}.', 'ok')
    return redirect(url_for('gym'))


@app.route('/gym/update/<int:index>', methods=['POST'])
@login_required
def gym_update(index):
    logs = read_json('gym_log.json')
    try:
        if not 0 <= index < len(logs):
            raise ValueError('Workout entry not found.')
        exercise = request.form['exercise'].strip().title()
        if not exercise:
            raise ValueError('Exercise is required.')
        logs[index] = {
            'date': parse_date(request.form['date']),
            'exercise': exercise,
            'weight': positive_float(request.form['weight'], 'Weight'),
            'reps': positive_int(request.form['reps'], 'Reps'),
            'sets': positive_int(request.form['sets'], 'Sets'),
        }
        logs.sort(key=lambda row: row['date'])
        write_json('gym_log.json', logs)
        flash('Workout updated.', 'ok')
    except (KeyError, ValueError) as exc:
        flash(str(exc), 'error')
    return redirect(url_for('gym'))


@app.route('/gym/delete/<int:index>', methods=['POST'])
@login_required
def gym_delete(index):
    logs = read_json('gym_log.json')
    if 0 <= index < len(logs):
        logs.pop(index)
        write_json('gym_log.json', logs)
        flash('Workout deleted.', 'ok')
    return redirect(url_for('gym'))


@app.route('/attendance/timetable', methods=['GET', 'POST'])
@login_required
def timetable():
    tt = read_json('timetable.json')
    if request.method == 'POST':
        try:
            for day in DAYS:
                tt[day] = max(0, min(20, int(request.form.get(day, 0))))
            write_json('timetable.json', tt)
            flash('Timetable saved.', 'ok')
        except ValueError:
            flash('Use whole numbers for classes.', 'error')
        return redirect(url_for('timetable'))
    return render_template('timetable.html', timetable=tt, days=DAYS)


@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    logs = read_json('attendance.json')
    tt = read_json('timetable.json')

    if request.method == 'POST':
        try:
            date_str = parse_date(request.form['date'])
            attended = int(request.form['attended'])
            day_name = datetime.strptime(date_str, '%Y-%m-%d').strftime('%A')
            scheduled = int(tt.get(day_name, 0))
            if scheduled <= 0:
                raise ValueError('Set timetable classes for this day first.')
            if attended < 0 or attended > scheduled:
                raise ValueError('Attended classes must be between 0 and scheduled classes.')

            for log in logs:
                if log['date'] == date_str:
                    log.update({'day': day_name, 'scheduled': scheduled, 'attended': attended})
                    break
            else:
                logs.append({'date': date_str, 'day': day_name, 'scheduled': scheduled, 'attended': attended})
            logs.sort(key=lambda row: row['date'])
            write_json('attendance.json', logs)
            flash('Attendance saved.', 'ok')
        except (KeyError, ValueError) as exc:
            flash(str(exc), 'error')
        return redirect(url_for('attendance', date=request.form.get('date', '')))

    total_scheduled, total_attended, overall_pct = attendance_stats(logs)
    classes_needed = 0
    safe_misses = 0
    if total_scheduled > 0:
        if overall_pct < 75:
            classes_needed = int(((0.75 * total_scheduled - total_attended) / 0.25) + 0.999999)
        else:
            safe_misses = int((total_attended - 0.75 * total_scheduled) / 0.75)
    selected_date = request.args.get('date', '')
    day_scheduled = 0
    prefill_attended = 0
    if selected_date:
        try:
            selected_date = parse_date(selected_date)
            day_name = datetime.strptime(selected_date, '%Y-%m-%d').strftime('%A')
            day_scheduled = int(tt.get(day_name, 0))
            prefill_attended = next((log['attended'] for log in logs if log['date'] == selected_date), 0)
        except ValueError:
            selected_date = ''

    return render_template(
        'attendance.html',
        logs=logs,
        total_scheduled=total_scheduled,
        total_attended=total_attended,
        overall_pct=overall_pct,
        classes_needed=classes_needed,
        safe_misses=safe_misses,
        selected_date=selected_date,
        day_scheduled=day_scheduled,
        prefill_attended=prefill_attended,
    )


@app.route('/attendance/delete/<string:date>', methods=['POST'])
@login_required
def attendance_delete(date):
    logs = [log for log in read_json('attendance.json') if log['date'] != date]
    write_json('attendance.json', logs)
    flash('Attendance entry deleted.', 'ok')
    return redirect(url_for('attendance'))


@app.route('/attendance/graph')
@login_required
def attendance_graph():
    logs = read_json('attendance.json')
    if not logs:
        flash('No attendance data yet.', 'error')
        return redirect(url_for('attendance'))

    dates, percents = [], []
    scheduled_sum, attended_sum = 0, 0
    for log in logs:
        scheduled_sum += int(log['scheduled'])
        attended_sum += int(log['attended'])
        if scheduled_sum:
            dates.append(log['date'])
            percents.append(round((attended_sum / scheduled_sum) * 100, 1))

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(dates, percents, marker='o', color='#2563eb', linewidth=2)
    ax.axhline(75, color='#dc2626', linestyle='--', linewidth=1, label='75%')
    ax.fill_between(dates, percents, 75, where=[p < 75 for p in percents], alpha=0.15, color='#dc2626')
    ax.set_title('Attendance Trend')
    ax.set_xlabel('Date')
    ax.set_ylabel('%')
    ax.set_ylim(0, 105)
    ax.legend()
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    fname = 'attendance_overall.png'
    plt.savefig(GRAPH_DIR / fname)
    plt.close()
    return render_template('attendance_graph.html', graph_file=fname)


@app.route('/study', methods=['GET', 'POST'])
@login_required
def study():
    logs = read_json('study.json')

    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'add':
                subject = request.form['subject'].strip().title()
                topic = request.form['topic'].strip()
                if not subject or not topic:
                    raise ValueError('Subject and topic are required.')
                logs.append({
                    'subject': subject,
                    'topic': topic,
                    'lessons': [False, False, False, False, False],
                    'date': parse_date(request.form['date']),
                    'notes': request.form.get('notes', '').strip(),
                })
                logs.sort(key=lambda row: row['date'], reverse=True)
                flash('Topic added.', 'ok')
            elif action == 'toggle_lesson':
                idx = int(request.form['index'])
                lesson_index = int(request.form['lesson_index'])
                if 0 <= idx < len(logs) and 0 <= lesson_index < 5:
                    logs[idx]['lessons'][lesson_index] = not logs[idx]['lessons'][lesson_index]
            elif action == 'delete':
                idx = int(request.form['index'])
                if 0 <= idx < len(logs):
                    logs.pop(idx)
                    flash('Topic deleted.', 'ok')
            write_json('study.json', logs)
        except (KeyError, ValueError) as exc:
            flash(str(exc), 'error')
        return redirect(url_for('study'))

    filter_subject = request.args.get('subject', 'All')
    filter_status = request.args.get('status', 'All')
    displayed = []
    for i, entry in enumerate(logs):
        done_count = sum(entry.get('lessons', []))
        is_complete = done_count == 5
        if filter_subject != 'All' and entry['subject'] != filter_subject:
            continue
        if filter_status == 'complete' and not is_complete:
            continue
        if filter_status == 'incomplete' and is_complete:
            continue
        displayed.append((i, entry, done_count))

    subjects = sorted({entry['subject'] for entry in logs})
    progress = {}
    for subject in subjects:
        subject_logs = [entry for entry in logs if entry['subject'] == subject]
        done_lessons = sum(sum(entry.get('lessons', [])) for entry in subject_logs)
        total_lessons = len(subject_logs) * 5
        progress[subject] = {
            'topics': len(subject_logs),
            'done_lessons': done_lessons,
            'total_lessons': total_lessons,
            'complete_topics': sum(1 for entry in subject_logs if sum(entry.get('lessons', [])) == 5),
        }

    return render_template(
        'study.html',
        displayed=displayed,
        subjects=subjects,
        progress=progress,
        filter_subject=filter_subject,
        filter_status=filter_status,
    )


if __name__ == '__main__':
    app.run(debug=True)
