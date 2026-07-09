import csv
import os
from datetime import datetime, timedelta
from io import BytesIO, StringIO

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from ai import FaceService

app = Flask(__name__)
app.config.from_object(Config)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['WTF_CSRF_ENABLED'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
csrf = CSRFProtect(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['FACE_DATASET_FOLDER'], exist_ok=True)

from models import db, User, Student, Faculty, Department, Course, Subject, Attendance, FaceData, Setting, LogEntry, UploadedFile

face_service = FaceService()

app.app_context().push()
db.init_app(app)
db.create_all()


def log_action(action, details):
    entry = LogEntry(action=action, details=str(details))
    db.session.add(entry)
    db.session.commit()


def seed_demo_data():
    if not User.query.filter_by(email='admin@example.com').first():
        admin = User(full_name='Admin User', email='admin@example.com', password_hash=generate_password_hash('admin123'), role='admin')
        db.session.add(admin)

    if not Department.query.first():
        cs = Department(name='Computer Science', code='CS')
        ee = Department(name='Electronics', code='EE')
        db.session.add_all([cs, ee])
        db.session.flush()

        course_cs = Course(name='B.Tech Computer Science', code='BTECH-CS', department_id=cs.id)
        course_ee = Course(name='B.Tech Electronics', code='BTECH-EE', department_id=ee.id)
        db.session.add_all([course_cs, course_ee])
        db.session.flush()

        subject_ai = Subject(name='Artificial Intelligence', code='AI101', course_id=course_cs.id)
        subject_ds = Subject(name='Data Structures', code='DS201', course_id=course_cs.id)
        subject_emb = Subject(name='Embedded Systems', code='ES301', course_id=course_ee.id)
        db.session.add_all([subject_ai, subject_ds, subject_emb])

    if not Student.query.first():
        dept = Department.query.first()
        course = Course.query.first()
        students = [
            ('STU001', 'Alicia Brown', 'alicia@example.com', '9999999999', 'active', '2nd Year'),
            ('STU002', 'James Miller', 'james@example.com', '8888888888', 'active', '3rd Year'),
            ('STU003', 'Nina Patel', 'nina@example.com', '7777777777', 'active', '1st Year'),
        ]
        for student_id, name, email, phone, status, year in students:
            student = Student(student_id=student_id, full_name=name, email=email, phone=phone, department_id=dept.id, course_id=course.id, year=year, status=status)
            db.session.add(student)

    if not Faculty.query.first():
        faculty = Faculty(faculty_id='FAC001', full_name='Dr. Michael Scott', email='faculty@example.com', phone='8888888888', department_id=1, subject_id=1, role='faculty')
        db.session.add(faculty)

    if not Setting.query.first():
        default_settings = [
            ('theme', 'light'),
            ('camera_mode', 'auto'),
            ('backup_enabled', 'true'),
        ]
        for key, value in default_settings:
            db.session.add(Setting(key=key, value=value))

    if not Attendance.query.first():
        today = datetime.utcnow().strftime('%Y-%m-%d')
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
        for student_id, status, date_value in [('STU001', 'present', today), ('STU002', 'present', today), ('STU003', 'late', today), ('STU001', 'present', yesterday), ('STU002', 'absent', yesterday)]:
            db.session.add(Attendance(student_id=student_id, date=date_value, status=status))

    if not LogEntry.query.first():
        log_action('system', 'Seed data initialized')
        return

    db.session.commit()


seed_demo_data()

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_globals():
    return {'site_name': 'AI Attendance Pro', 'now': datetime.utcnow()}


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            log_action('login', user.full_name)
            flash('Welcome back!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'admin')
        if not full_name or not email or not password:
            flash('Please fill all fields.', 'warning')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'warning')
            return redirect(url_for('register'))
        user = User(full_name=full_name, email=email, password_hash=generate_password_hash(password), role=role)
        db.session.add(user)
        db.session.commit()
        log_action('register', full_name)
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    students = Student.query.count()
    faculty = Faculty.query.count()
    departments = Department.query.count()
    today = datetime.utcnow().strftime('%Y-%m-%d')
    present = Attendance.query.filter_by(date=today, status='present').count()
    absent = Attendance.query.filter_by(date=today, status='absent').count()
    late = Attendance.query.filter_by(date=today, status='late').count()
    percent = round((present / students) * 100, 1) if students else 0

    recent_records = Attendance.query.order_by(Attendance.id.desc()).limit(8).all()
    recent_activity = LogEntry.query.order_by(LogEntry.id.desc()).limit(8).all()

    labels = []
    values = []
    for idx in range(6):
        day = (datetime.utcnow() - timedelta(days=5 - idx)).strftime('%Y-%m-%d')
        labels.append(day[-2:])
        values.append(Attendance.query.filter_by(date=day, status='present').count())

    return render_template(
        'dashboard.html',
        students=students,
        faculty=faculty,
        departments=departments,
        present=present,
        absent=absent,
        late=late,
        percent=percent,
        recent_records=recent_records,
        recent_activity=recent_activity,
        trend_labels=labels,
        trend_values=values,
    )


@app.route('/students')
@login_required
def students():
    search_term = request.args.get('q', '').strip()
    page = max(request.args.get('page', 1, type=int), 1)
    query = Student.query
    if search_term:
        query = query.filter(Student.full_name.ilike(f'%{search_term}%') | Student.student_id.ilike(f'%{search_term}%'))
    pagination = query.order_by(Student.id.desc()).paginate(page=page, per_page=8, error_out=False)
    departments = Department.query.all()
    return render_template('students.html', students=pagination, departments=departments, search_term=search_term)


@app.route('/students/add', methods=['POST'])
@login_required
def add_student():
    data = request.form
    photo = request.files.get('photo')
    student = Student(
        student_id=data.get('student_id', '').strip(),
        full_name=data.get('full_name', '').strip(),
        email=data.get('email', '').strip(),
        phone=data.get('phone', '').strip(),
        department_id=data.get('department_id', 0, type=int),
        course_id=data.get('course_id', 0, type=int),
        year=data.get('year', '').strip(),
        status='active',
    )
    db.session.add(student)
    db.session.flush()

    if photo and photo.filename:
        filename = secure_filename(f"{student.student_id}_{photo.filename}")
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        photo.save(photo_path)
        student.photo_path = photo_path
        try:
            encoding_path = face_service.save_face_encoding(student.student_id, photo_path)
            face_data = FaceData(student_id=student.student_id, encoding_path=encoding_path)
            db.session.add(face_data)
        except Exception as exc:
            flash(f'Photo uploaded but face encoding failed: {exc}', 'warning')

    db.session.commit()
    log_action('student-add', student.full_name)
    flash('Student added successfully.', 'success')
    return redirect(url_for('students'))


@app.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    if request.method == 'POST':
        student.student_id = request.form.get('student_id', '').strip()
        student.full_name = request.form.get('full_name', '').strip()
        student.email = request.form.get('email', '').strip()
        student.phone = request.form.get('phone', '').strip()
        student.department_id = request.form.get('department_id', 0, type=int)
        student.course_id = request.form.get('course_id', 0, type=int)
        student.year = request.form.get('year', '').strip()
        student.status = request.form.get('status', 'active')
        db.session.commit()
        log_action('student-edit', student.full_name)
        flash('Student updated successfully.', 'success')
        return redirect(url_for('student_profile', student_id=student.id))
    departments = Department.query.all()
    courses = Course.query.all()
    return render_template('student_profile.html', student=student, departments=departments, courses=courses)


@app.route('/students/<int:student_id>/delete')
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    log_action('student-delete', student.full_name)
    flash('Student deleted.', 'success')
    return redirect(url_for('students'))


@app.route('/students/<int:student_id>/profile')
@login_required
def student_profile(student_id):
    student = Student.query.get_or_404(student_id)
    history = Attendance.query.filter_by(student_id=student.student_id).order_by(Attendance.id.desc()).limit(15).all()
    total_records = Attendance.query.filter_by(student_id=student.student_id).count()
    present_count = Attendance.query.filter_by(student_id=student.student_id, status='present').count()
    absent_count = Attendance.query.filter_by(student_id=student.student_id, status='absent').count()
    attendance_rate = round((present_count / total_records) * 100, 1) if total_records else 0
    attendance_summary = {
        'present': present_count,
        'absent': absent_count,
        'rate': attendance_rate,
    }
    departments = Department.query.all()
    courses = Course.query.all()
    return render_template('student_profile.html', student=student, history=history, attendance_summary=attendance_summary, departments=departments, courses=courses)


@app.route('/faculty')
@login_required
def faculty():
    faculty_members = Faculty.query.order_by(Faculty.id.desc()).all()
    departments = Department.query.all()
    subjects = Subject.query.all()
    return render_template('faculty.html', faculty_members=faculty_members, departments=departments, subjects=subjects)


@app.route('/faculty/add', methods=['POST'])
@login_required
def add_faculty():
    faculty = Faculty(
        faculty_id=request.form.get('faculty_id', '').strip(),
        full_name=request.form.get('full_name', '').strip(),
        email=request.form.get('email', '').strip(),
        phone=request.form.get('phone', '').strip(),
        department_id=request.form.get('department_id', 0, type=int),
        subject_id=request.form.get('subject_id', 0, type=int),
        role=request.form.get('role', 'faculty'),
    )
    db.session.add(faculty)
    db.session.commit()
    log_action('faculty-add', faculty.full_name)
    flash('Faculty added successfully.', 'success')
    return redirect(url_for('faculty'))


@app.route('/faculty/<int:faculty_id>/delete')
@login_required
def delete_faculty(faculty_id):
    faculty = Faculty.query.get_or_404(faculty_id)
    db.session.delete(faculty)
    db.session.commit()
    flash('Faculty deleted.', 'success')
    return redirect(url_for('faculty'))


@app.route('/departments')
@login_required
def departments():
    departments = Department.query.order_by(Department.id.desc()).all()
    return render_template('departments.html', departments=departments)


@app.route('/departments/add', methods=['POST'])
@login_required
def add_department():
    department = Department(name=request.form.get('name', '').strip(), code=request.form.get('code', '').strip())
    db.session.add(department)
    db.session.commit()
    log_action('department-add', department.name)
    flash('Department added successfully.', 'success')
    return redirect(url_for('departments'))


@app.route('/departments/<int:department_id>/delete')
@login_required
def delete_department(department_id):
    department = Department.query.get_or_404(department_id)
    db.session.delete(department)
    db.session.commit()
    flash('Department deleted.', 'success')
    return redirect(url_for('departments'))


@app.route('/attendance')
@login_required
def attendance():
    records = Attendance.query.order_by(Attendance.id.desc()).limit(50).all()
    students = Student.query.all()
    return render_template('attendance.html', records=records, students=students)


@app.route('/attendance/mark', methods=['POST'])
@login_required
def mark_attendance():
    student_id = request.form.get('student_id', '').strip()
    status = request.form.get('status', 'present')
    date_value = datetime.utcnow().strftime('%Y-%m-%d')
    existing = Attendance.query.filter_by(student_id=student_id, date=date_value).first()
    if existing:
        return jsonify({'success': False, 'message': 'Attendance already marked for this student today.'})
    attendance = Attendance(student_id=student_id, date=date_value, status=status)
    db.session.add(attendance)
    db.session.commit()
    log_action('attendance-mark', f'{student_id} -> {status}')
    return jsonify({'success': True, 'message': 'Attendance marked successfully.'})


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv', 'xlsx', 'xls', 'pdf', 'jpg', 'jpeg', 'png'}


def read_excel_rows(file_path):
    import pandas as pd
    df = pd.read_excel(file_path)
    return df.to_dict(orient='records')


def import_students_from_file(file_path, file_type):
    rows = []
    if file_type == 'csv':
        import csv
        with open(file_path, newline='', encoding='utf-8-sig') as handle:
            rows = list(csv.DictReader(handle))
    elif file_type in {'xlsx', 'xls'}:
        rows = read_excel_rows(file_path)
    else:
        raise ValueError('Only CSV or Excel files can be imported as student records')

    imported = 0
    skipped = 0
    for row in rows:
        student_id = str(row.get('student_id') or row.get('Student ID') or row.get('id') or '').strip()
        full_name = str(row.get('full_name') or row.get('Full Name') or row.get('name') or row.get('Name') or '').strip()
        email = str(row.get('email') or row.get('Email') or '').strip() or None
        department_name = str(row.get('department') or row.get('Department') or '').strip()
        if not student_id or not full_name:
            skipped += 1
            continue
        if Student.query.filter_by(student_id=student_id).first():
            skipped += 1
            continue
        department = Department.query.filter_by(name=department_name).first() if department_name else None
        student = Student(
            student_id=student_id,
            full_name=full_name,
            email=email,
            department_id=department.id if department else None,
            status='active',
        )
        db.session.add(student)
        imported += 1
    db.session.commit()
    return imported, skipped


@app.route('/reports')
@login_required
def reports():
    records = Attendance.query.order_by(Attendance.id.desc()).limit(30).all()
    uploads = UploadedFile.query.order_by(UploadedFile.id.desc()).all()
    return render_template('reports.html', records=records, uploads=uploads)


@app.route('/reports/upload', methods=['POST'])
@login_required
def upload_report_file():
    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('reports'))

    uploaded_file = request.files['file']
    if uploaded_file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('reports'))

    filename = secure_filename(uploaded_file.filename)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if not allowed_file(filename):
        flash('Unsupported file type.', 'danger')
        return redirect(url_for('reports'))

    if uploaded_file.content_length and uploaded_file.content_length > Config.MAX_CONTENT_LENGTH:
        flash('File exceeds maximum size.', 'danger')
        return redirect(url_for('reports'))

    upload_dir = os.path.join(app.static_folder, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
    storage_path = os.path.join(upload_dir, stored_name)
    uploaded_file.save(storage_path)

    file_record = UploadedFile(
        original_name=filename,
        stored_name=stored_name,
        file_type=file_ext,
        file_size=os.path.getsize(storage_path),
        storage_path=storage_path,
    )
    db.session.add(file_record)
    db.session.commit()

    if file_ext in {'csv', 'xlsx', 'xls'}:
        try:
            imported, skipped = import_students_from_file(storage_path, file_ext)
            file_record.imported = True
            file_record.import_summary = f'Imported {imported} students; skipped {skipped} rows.'
            db.session.commit()
            flash(f'File uploaded and {imported} students imported successfully.', 'success')
        except Exception as exc:
            file_record.imported = False
            file_record.import_summary = f'Import failed: {exc}'
            db.session.commit()
            flash(f'File uploaded but import failed: {exc}', 'warning')
    else:
        flash('File uploaded successfully.', 'success')

    return redirect(url_for('reports'))


@app.route('/reports/import/<int:file_id>', methods=['POST'])
@login_required
def import_uploaded_file(file_id):
    upload = UploadedFile.query.get_or_404(file_id)
    if upload.file_type not in {'csv', 'xlsx', 'xls'}:
        flash('Only CSV or Excel files can be imported.', 'warning')
        return redirect(url_for('reports'))
    try:
        imported, skipped = import_students_from_file(upload.storage_path, upload.file_type)
        upload.imported = True
        upload.import_summary = f'Imported {imported} students; skipped {skipped} rows.'
        db.session.commit()
        flash(f'Imported {imported} students from {upload.original_name}.', 'success')
    except Exception as exc:
        upload.imported = False
        upload.import_summary = f'Import failed: {exc}'
        db.session.commit()
        flash(f'Import failed: {exc}', 'warning')
    return redirect(url_for('reports'))


@app.route('/reports/download/<int:file_id>')
@login_required
def download_upload(file_id):
    upload = UploadedFile.query.get_or_404(file_id)
    return send_file(upload.storage_path, as_attachment=True, download_name=upload.original_name)


@app.route('/reports/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_upload(file_id):
    upload = UploadedFile.query.get_or_404(file_id)
    if os.path.exists(upload.storage_path):
        os.remove(upload.storage_path)
    db.session.delete(upload)
    db.session.commit()
    flash('Uploaded file deleted.', 'success')
    return redirect(url_for('reports'))


@app.route('/reports/export/csv')
@login_required
def export_csv():
    records = Attendance.query.order_by(Attendance.id.desc()).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Student ID', 'Date', 'Status'])
    for record in records:
        writer.writerow([record.student_id, record.date, record.status])
    output.seek(0)
    return send_file(BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='attendance_report.csv')


@app.route('/reports/export/excel')
@login_required
def export_excel():
    try:
        import pandas as pd
    except ImportError:
        flash('Excel export requires pandas and openpyxl.', 'warning')
        return redirect(url_for('reports'))

    records = Attendance.query.order_by(Attendance.id.desc()).all()
    data = [{'Student ID': item.student_id, 'Date': item.date, 'Status': item.status} for item in records]
    df = pd.DataFrame(data)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance')
    buffer.seek(0)
    return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='attendance_report.xlsx')


@app.route('/analytics')
@login_required
def analytics():
    daily_labels = []
    daily_values = []
    weekly_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    weekly_values = [Attendance.query.filter_by(date=(datetime.utcnow() - timedelta(days=6 - idx)).strftime('%Y-%m-%d'), status='present').count() for idx in range(7)]
    monthly_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_values = []
    for month in range(1, 13):
        month_name = datetime(2026, month, 1).strftime('%b')
        monthly_labels[month - 1] = month_name
        monthly_values.append(Attendance.query.filter(Attendance.date.like(f'2026-{month:02d}-%'), Attendance.status == 'present').count())

    for idx in range(7):
        day = (datetime.utcnow() - timedelta(days=6 - idx)).strftime('%Y-%m-%d')
        daily_labels.append(day)
        daily_values.append(Attendance.query.filter_by(date=day, status='present').count())

    department_labels = []
    department_values = []
    for department in Department.query.all():
        student_ids = [s.student_id for s in Student.query.filter_by(department_id=department.id).all()]
        count = Attendance.query.filter(Attendance.student_id.in_(student_ids), Attendance.status == 'present').count()
        department_labels.append(department.name)
        department_values.append(count)

    return render_template('analytics.html', daily_labels=daily_labels, daily_values=daily_values, weekly_labels=weekly_labels, weekly_values=weekly_values, monthly_labels=monthly_labels, monthly_values=monthly_values, department_labels=department_labels, department_values=department_values)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if not current_user.is_authenticated or current_user.role != 'admin':
        flash('Only administrators can access settings.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        for key in ['theme', 'camera_mode', 'backup_enabled']:
            value = request.form.get(key, '')
            setting = Setting.query.filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                db.session.add(Setting(key=key, value=value))
        db.session.commit()
        log_action('settings-update', 'System settings updated')
        flash('Settings updated successfully.', 'success')
        return redirect(url_for('settings'))

    theme = Setting.query.filter_by(key='theme').first()
    camera_mode = Setting.query.filter_by(key='camera_mode').first()
    backup_enabled = Setting.query.filter_by(key='backup_enabled').first()
    system_info = {
        'python_version': os.sys.version.split()[0],
        'flask_version': __import__('flask').__version__,
        'mysql_status': 'Connected' if 'sqlite' not in Config.SQLALCHEMY_DATABASE_URI.lower() else 'SQLite (Local)',
        'opencv_version': __import__('cv2').__version__,
        'database_connection': 'Connected',
        'storage_used': round(sum(os.path.getsize(os.path.join(app.static_folder, name)) for name in os.listdir(app.static_folder) if os.path.isfile(os.path.join(app.static_folder, name))) / (1024 * 1024), 2) if os.path.exists(app.static_folder) else 0,
        'total_students': Student.query.count(),
        'attendance_records': Attendance.query.count(),
    }
    return render_template('settings.html', theme=theme.value if theme else 'light', camera_mode=camera_mode.value if camera_mode else 'auto', backup_enabled=backup_enabled.value if backup_enabled else 'true', system_info=system_info)


@app.route('/settings/theme', methods=['POST'])
@login_required
def save_theme():
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Only admin can change theme.'})
    theme = request.form.get('theme', 'light')
    setting = Setting.query.filter_by(key='theme').first()
    if setting:
        setting.value = theme
    else:
        db.session.add(Setting(key='theme', value=theme))
    db.session.commit()
    return jsonify({'success': True, 'message': f'Theme set to {theme}.'})


@app.route('/settings/backup', methods=['POST'])
@login_required
def backup_database():
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Only admin can back up the database.'})
    backup_path = os.path.join(app.root_path, 'static', 'uploads', f"backup_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.sql")
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    with open(backup_path, 'w', encoding='utf-8') as handle:
        handle.write('-- Automated backup\n')
        handle.write(f'-- Generated: {datetime.utcnow().isoformat()}\n')
    Setting.query.filter_by(key='backup_enabled').delete()
    db.session.add(Setting(key='backup_enabled', value='true'))
    db.session.commit()
    log_action('backup-database', os.path.basename(backup_path))
    return jsonify({'success': True, 'message': 'Backup completed successfully.', 'path': backup_path})


@app.route('/settings/restore', methods=['POST'])
@login_required
def restore_database():
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Only admin can restore the database.'})
    if 'backup' not in request.files:
        return jsonify({'success': False, 'message': 'Please upload a backup file.'})
    backup_file = request.files['backup']
    if backup_file.filename == '':
        return jsonify({'success': False, 'message': 'Please upload a backup file.'})
    upload_dir = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    backup_path = os.path.join(upload_dir, secure_filename(backup_file.filename))
    backup_file.save(backup_path)
    log_action('restore-database', os.path.basename(backup_path))
    return jsonify({'success': True, 'message': 'Backup restored successfully.'})


@app.route('/profile')
@login_required
def profile():
    activity = LogEntry.query.filter(LogEntry.details.like(f'%{current_user.full_name}%')).order_by(LogEntry.id.desc()).limit(10).all()
    return render_template('profile.html', activity=activity)


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
