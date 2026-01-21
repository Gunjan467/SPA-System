from flask import Flask, render_template, request, redirect, session,url_for,flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
USERS = {
    "student1": {"password": "123", "role": "student"},
    "teacher1": {"password": "123", "role": "teacher"},
    "admin": {"password": "admin123", "role": "admin"}}
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="abc",
    database="spa_system")
cursor = db.cursor(dictionary=True, buffered=True)

app = Flask(__name__)

app.secret_key = ''

@app.context_processor
def inject_request():
    return dict(request=request)

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if (
            request.form['username'] == ADMIN_USERNAME and
            request.form['password'] == ADMIN_PASSWORD):
            return redirect(url_for('admin_panel'))
        else:
            return render_template(
                'admin_login.html',
                error="Invalid admin username or password")
           
    return render_template('admin_login.html')

@app.route('/admin/panel')
def admin_panel():
    return render_template('admin_panel.html')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        username= request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        # Fetch user by username AND role
        cursor.execute(
            "SELECT id, username, email, password, role FROM users "
            "WHERE username=%s AND role=%s",
            (username, role)
        )
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']

            # Role-based redirect
            if user['role'] == 'student':
                return redirect('/student-dashboard')
            else:
                return redirect('/teacher-dashboard')

        else:
            error = "Invalid username or password"

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/add')
def add_student():
    return render_template('add_student.html')

@app.route('/view')
def view_students():
    return render_template('view_students.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        if not username or not email or not password or not role:
            return render_template('register.html', error="All fields required")

        cursor.execute(
            "SELECT id FROM users WHERE username=%s OR email=%s",
            (username, email)
        )
        if cursor.fetchone():
            return render_template(
                'register.html',
                error="Username or Email already exists"
            )

        hashed_password = generate_password_hash(password)

        roll_no = None

        if role == 'student':
                cursor.execute("SELECT MAX(roll_no) FROM users WHERE role='student'")
                last_roll = cursor.fetchone()[0]
                roll_no = 1 if last_roll is None else last_roll + 1
        else:
            roll_no = None

        cursor.execute(
    """
    INSERT INTO users (username, email, password, role, roll_no)
    VALUES (%s, %s, %s, %s, %s)
    """,
    (username, email, hashed_password, role, roll_no))

        db.commit()
        return redirect('/login')

    return render_template('register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        # Later you can add email logic
        return redirect('/login')
    return render_template('forgot_password.html')

@app.route('/student-dashboard')
def student_dashboard():
    student_id = session.get('user_id')

    cursor.execute("""
        SELECT 
            SUM(attended_classes) AS attended,
            SUM(total_classes) AS total
        FROM attendance
        WHERE student_id = %s
    """, (student_id,))

    data = cursor.fetchone()

    overall_attendance = None
    if data and data['total']:
        overall_attendance = round((data['attended'] / data['total']) * 100, 2)

    return render_template(
        'student_dashboard.html',
        overall_attendance=overall_attendance)
    
@app.route('/student/gpa')
def student_gpa():
    if 'user_id' not in session:
        return redirect('/login')

    student_id = session['user_id']

    cursor.execute(
        "SELECT marks, out_of FROM marks WHERE student_id = %s",
        (student_id,)
    )
    rows = cursor.fetchall()

    gpa = None

    if rows:
        total_percentage = 0
        for row in rows:
            total_percentage += (row['marks'] / row['out_of']) * 100

        gpa = round((total_percentage / len(rows)) / 10, 2)

    return render_template(
        'student_gpa.html',
        gpa=gpa
    )

@app.route('/student/marks')
def student_marks():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect('/login')

    student_id = session['user_id']

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="spa_system"
    )
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT subject, marks, out_of, semester
        FROM marks
        WHERE student_id = %s
        ORDER BY semester
    """, (student_id,))

    marks = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('student_marks.html', marks=marks)

@app.route('/student/attendance')
def student_attendance():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect('/login')

    student_id = session['user_id']

    cursor.execute("""
        SELECT subject,
               total_classes,
               attended_classes,
               ROUND((attended_classes / total_classes) * 100, 2) AS percentage
        FROM attendance
        WHERE student_id = %s
    """, (student_id,))

    attendance = cursor.fetchall()

    total_classes = sum(row['total_classes'] for row in attendance)
    total_attended = sum(row['attended_classes'] for row in attendance)

    overall_percentage = (
        round((total_attended / total_classes) * 100, 2)
        if total_classes > 0 else 0)
    
    return render_template(
        'student_attendance.html',
        attendance=attendance,
        overall_percentage=overall_percentage)

@app.route('/student/progress')
def student_progress():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect('/login')

    student_id = session['user_id']

    cursor.execute("""
        SELECT semester,
               ROUND(AVG((marks / out_of) * 10), 2) AS gpa
        FROM marks
        WHERE student_id = %s
        GROUP BY semester
        ORDER BY semester
    """, (student_id,))

    progress = cursor.fetchall()

    return render_template(
        'student_progress.html',
        progress=progress
    )

@app.route('/student/feedback')
def student_feedback():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect('/login')

    cursor.execute("""
        SELECT subject, feedback, teacher_name, created_at
        FROM feedback
        WHERE student_id = %s
        ORDER BY created_at DESC
    """, (session['user_id'],))

    feedbacks = cursor.fetchall()
    return render_template('student_feedback.html', feedbacks=feedbacks)

@app.route('/student/comparison')
def student_comparison():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect('/login')

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="spa_system"
    )
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
    SELECT 
        m.subject,
        COALESCE(
            ROUND(AVG(CASE 
                WHEN m.student_id = %s THEN m.marks 
            END), 2),
            0
        ) AS student_avg,
        ROUND(AVG(m.marks), 2) AS class_avg
    FROM marks m
    GROUP BY m.subject
""", (session['user_id'],))


    comparison = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'student_comparison.html',
        comparison=comparison
    )

@app.route('/teacher-dashboard')
def teacher_dashboard():
    if 'user_id' not in session or session.get('role') != 'teacher':
        return redirect('/login')
    return render_template('teacher_dashboard.html')

@app.route('/teacher/students')
def teacher_students():
    cursor = db.cursor()
    cursor.execute(
        "SELECT roll_no, username, email FROM users WHERE role = 'student'"
    )
    students = cursor.fetchall()
    cursor.close()
    return render_template('teacher_students.html', students=students)

@app.route('/teacher/marks', methods=['GET', 'POST'])
def teacher_marks():
    if 'user_id' not in session or session.get('role') != 'teacher':
        return redirect('/login')

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="spa_system"
    )
    cursor = conn.cursor()

    # ================= POST: ADD / UPDATE =================
    if request.method == 'POST':
        mode = request.form.get('mode')

        # -------- ADD MARKS --------
        if mode == 'add':
            roll_no = request.form['roll_no']
            subject = request.form['subject']
            semester = int(request.form['semester'])
            marks_f = int(request.form['marks'])
            out_of = int(request.form['out_of'])

            if semester < 1:
                flash("Invalid semester", "error")
                return redirect('/teacher/marks')

            if marks_f < 0 or marks_f > out_of:
                flash("Marks must be between 0 and Out Of", "error")
                return redirect('/teacher/marks')

            cursor.execute(
                "SELECT id FROM users WHERE roll_no=%s AND role='student'",
                (roll_no,)
            )
            student = cursor.fetchone()

            if not student:
                flash("Student not found", "error")
                return redirect('/teacher/marks')

            student_id = student[0]

            cursor.execute("""
                SELECT id FROM marks
                WHERE student_id=%s AND subject=%s AND semester=%s
            """, (student_id, subject, semester))

            if cursor.fetchone():
                flash("Marks already exist for this subject and semester", "error")
                return redirect('/teacher/marks')

            cursor.execute("""
                INSERT INTO marks (student_id, subject, marks, out_of, semester)
                VALUES (%s, %s, %s, %s, %s)
            """, (student_id, subject, marks_f, out_of, semester))

            conn.commit()
            flash("Marks added successfully", "success")
            return redirect('/teacher/marks')

        # -------- UPDATE MARKS --------
        elif mode == 'update':
            record_id = request.form['record_id']
            marks_f = int(request.form['marks'])
            out_of = int(request.form['out_of'])

            if marks_f < 0 or marks_f > out_of:
                flash("Marks must be between 0 and Out Of", "error")
                return redirect('/teacher/marks')

            cursor.execute(
                "SELECT id FROM marks WHERE id=%s",
                (record_id,)
            )

            if not cursor.fetchone():
                flash("Marks record not found", "error")
                return redirect('/teacher/marks')

            cursor.execute("""
                UPDATE marks
                SET marks=%s, out_of=%s
                WHERE id=%s
            """, (marks_f, out_of, record_id))

            conn.commit()
            flash("Marks updated successfully", "success")
            return redirect('/teacher/marks')

        elif mode == 'delete':
                mark_id = request.form.get('mark_id')

                if not mark_id:
                    flash("Invalid record selected", "error")
                    return redirect('/teacher/marks')

                cursor.execute(
                    "DELETE FROM marks WHERE id = %s",
                    (mark_id,)
                )

                conn.commit()
                flash("Marks deleted successfully", "success")
                return redirect('/teacher/marks')

    # ================= GET: VIEW / FILTER =================
    subject = request.args.get('subject')
    semester = request.args.get('semester')
    search = request.args.get('search')

    query = """
        SELECT
            m.id,
            u.roll_no,
            u.username,
            m.subject,
            m.marks,
            m.out_of,
            m.semester
        FROM marks m
        JOIN users u ON u.id = m.student_id
        WHERE u.role='student'
    """
    params = []

    if subject:
        query += " AND m.subject=%s"
        params.append(subject)

    if semester and semester.isdigit() and int(semester) > 0:
        query += " AND m.semester=%s"
        params.append(int(semester))

    if search:
        query += " AND (u.roll_no LIKE %s OR u.username LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY u.roll_no, m.semester"

    cursor.execute(query, params)
    marks = cursor.fetchall()

    cursor.execute("SELECT DISTINCT subject FROM marks ORDER BY subject")
    subjects = [row[0] for row in cursor.fetchall()]

    cursor.execute("""
        SELECT DISTINCT semester
        FROM marks
        WHERE semester > 0
        ORDER BY semester
    """)
    semesters = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return render_template(
        'teacher_marks.html',
        marks=marks,
        subjects=subjects,
        semesters=semesters)

@app.route('/teacher/attendance', methods=['GET', 'POST'])
def teacher_attendance():
    if 'user_id' not in session or session.get('role') != 'teacher':
        return redirect('/login')

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="spa_system"
    )
    cursor = conn.cursor()

    # ================= POST =================
    if request.method == 'POST':
        mode = request.form.get('mode')

        # -------- ADD ATTENDANCE --------
        if mode == 'add':
            roll_no = request.form['roll_no']
            subject = request.form['subject']
            total = int(request.form['total_classes'])
            attended = int(request.form['attended_classes'])

            if total <= 0 or attended < 0 or attended > total:
                flash("Invalid attendance values", "error")
                return redirect('/teacher/attendance')

            cursor.execute(
                "SELECT id FROM users WHERE roll_no=%s AND role='student'",
                (roll_no,)
            )
            student = cursor.fetchone()

            if not student:
                flash("Student not found", "error")
                return redirect('/teacher/attendance')

            student_id = student[0]

            # duplicate check
            cursor.execute("""
                SELECT id FROM attendance
                WHERE student_id=%s AND subject=%s
            """, (student_id, subject))

            if cursor.fetchone():
                flash("Attendance already exists for this subject", "error")
                return redirect('/teacher/attendance')

            cursor.execute("""
                INSERT INTO attendance (student_id, subject, total_classes, attended_classes)
                VALUES (%s, %s, %s, %s)
            """, (student_id, subject, total, attended))

            conn.commit()
            flash("Attendance added successfully", "success")
            return redirect('/teacher/attendance')

        # -------- UPDATE ATTENDANCE --------
        elif mode == 'update':
            record_id = request.form['record_id']
            total = int(request.form['total_classes'])
            attended = int(request.form['attended_classes'])

            if total <= 0 or attended < 0 or attended > total:
                flash("Invalid attendance values", "error")
                return redirect('/teacher/attendance')

            cursor.execute("""
                UPDATE attendance
                SET total_classes=%s, attended_classes=%s
                WHERE id=%s
            """, (total, attended, record_id))

            conn.commit()
            flash("Attendance updated successfully", "success")
            return redirect('/teacher/attendance')

        # -------- DELETE --------
        elif mode == 'delete':
            record_id = request.form['record_id']
            cursor.execute("DELETE FROM attendance WHERE id=%s", (record_id,))
            conn.commit()
            flash("Attendance deleted", "success")
            return redirect('/teacher/attendance')

    # ================= GET =================
    search = request.args.get('search')
    subject = request.args.get('subject')

    query = """
        SELECT
            a.id,
            u.roll_no,
            u.username,
            a.subject,
            a.total_classes,
            a.attended_classes,
            ROUND((a.attended_classes / a.total_classes) * 100, 2)
        FROM attendance a
        JOIN users u ON u.id = a.student_id
        WHERE u.role='student'
        """
    params = []

    if search:
            query += " AND (u.roll_no LIKE %s OR u.username LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])

    if subject:
            query += " AND a.subject LIKE %s"
            params.append(f"%{subject}%")

    query += " ORDER BY u.roll_no"

    cursor.execute(query, params)
    attendance = cursor.fetchall()
    # -------- OVERALL ATTENDANCE (STUDENT-WISE) --------
    cursor.execute("""
        SELECT
            u.roll_no,
            u.username,
            SUM(a.total_classes) AS total_classes,
            SUM(a.attended_classes) AS total_attended,
            ROUND(SUM(a.attended_classes) * 100.0 / SUM(a.total_classes), 2) AS overall_percent
        FROM attendance a
        JOIN users u ON u.id = a.student_id
        WHERE u.role = 'student'
        GROUP BY u.roll_no, u.username
        ORDER BY u.roll_no
    """)
    overall_attendance = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
    'teacher_attendance.html',
    attendance=attendance,
    overall_attendance=overall_attendance
)

@app.route('/teacher/feedback', methods=['GET', 'POST'])
def teacher_feedback():
    if 'user_id' not in session or session.get('role') != 'teacher':
        return redirect('/login')

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="spa_system"
    )
    cursor = conn.cursor()

    # ================= POST =================
    if request.method == 'POST':
        mode = request.form.get('mode')

        # -------- ADD FEEDBACK --------
        if mode == 'add':
            roll_no = request.form['roll_no']
            subject = request.form['subject']
            text = request.form['feedback']

            cursor.execute(
                "SELECT id FROM users WHERE roll_no=%s AND role='student'",
                (roll_no,)
            )
            student = cursor.fetchone()

            if not student:
                flash("Student not found", "error")
                return redirect('/teacher/feedback')

            teacher_name = session.get('username')  # or session['name'] if you use that

            cursor.execute("""
                INSERT INTO feedback (student_id, subject, feedback, teacher_name)
                VALUES (%s, %s, %s, %s)
            """, (student[0], subject, text, teacher_name))


            conn.commit()
            flash("Feedback added successfully", "success")
            return redirect('/teacher/feedback')

        # -------- UPDATE --------
        elif mode == 'update':
            fid = request.form['feedback_id']
            text = request.form['feedback']

            cursor.execute("""
                UPDATE feedback SET feedback=%s WHERE id=%s
            """, (text, fid))

            conn.commit()
            flash("Feedback updated successfully", "success")
            return redirect('/teacher/feedback')

        # -------- DELETE --------
        elif mode == 'delete':
            fid = request.form['feedback_id']
            cursor.execute("DELETE FROM feedback WHERE id=%s", (fid,))
            conn.commit()
            flash("Feedback deleted", "success")
            return redirect('/teacher/feedback')

    # ================= GET =================
    search = request.args.get('search')
    subject = request.args.get('subject')

    query = """
        SELECT
    f.id,
    u.roll_no,
    u.username,
    f.subject,
    f.feedback,
    f.teacher_name,
    f.created_at
FROM feedback f
JOIN users u ON u.id = f.student_id
WHERE u.role='student'

    """
    params = []

    if search:
        query += " AND (u.roll_no LIKE %s OR u.username LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    if subject:
        query += " AND f.subject LIKE %s"
        params.append(f"%{subject}%")

    query += " ORDER BY f.created_at DESC"

    cursor.execute(query, params)
    feedbacks = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('teacher_feedback.html', feedbacks=feedbacks)

@app.route('/teacher/class-analytics')
def class_analytics():
    if 'user_id' not in session or session.get('role') != 'teacher':
        return redirect('/login')

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="spa_system"
    )
    cursor = conn.cursor(dictionary=True)

    # -------- GPA PER STUDENT --------
    semester = request.args.get('semester', 'All')

    semester_condition = ""
    params = []

    if semester != "All":
        semester_condition = "AND m.semester = %s"
        params.append(semester)

    cursor.execute(f"""
        SELECT u.username, ROUND(AVG(m.marks)/10,2) AS gpa
        FROM marks m
        JOIN users u ON u.id = m.student_id
        WHERE u.role='student' {semester_condition}
        GROUP BY u.id
    """, params)

    students = cursor.fetchall()

    gpas = [s['gpa'] for s in students]

    avg_gpa = round(sum(gpas)/len(gpas),2) if gpas else 0
    highest = max(students, key=lambda x:x['gpa'], default={'gpa':0,'username':'-'})
    lowest = min(students, key=lambda x:x['gpa'], default={'gpa':0,'username':'-'})

    # -------- GPA DISTRIBUTION --------
    dist = {"9-10":0,"8-9":0,"7-8":0,"6-7":0,"<6":0}
    for g in gpas:
        if g>=9: dist["9-10"]+=1
        elif g>=8: dist["8-9"]+=1
        elif g>=7: dist["7-8"]+=1
        elif g>=6: dist["6-7"]+=1
        else: dist["<6"]+=1

    # -------- SUBJECT PERFORMANCE --------
    semester_condition = ""
    params = []

    if semester != "All":
        semester_condition = "WHERE semester = %s"
        params.append(semester)

    cursor.execute(f"""
        SELECT subject, ROUND(AVG(marks)/10,2) AS avg_gpa
        FROM marks
        {semester_condition}
        GROUP BY subject
    """, params)

    subject_rows = cursor.fetchall()

    subject_labels = [s['subject'] for s in subject_rows]
    subject_values = [s['avg_gpa'] for s in subject_rows]

    # -------- RISK SUMMARY --------
    semester_condition = ""
    params = []

    if semester != "All":
        semester_condition = "AND semester = %s"
        params.append(semester)

    cursor.execute(f"""
        SELECT COUNT(DISTINCT student_id) AS cnt
        FROM marks
        WHERE marks < 40 {semester_condition}
    """, params)

    failed_students = cursor.fetchone()['cnt']

    low_gpa_count = len([g for g in gpas if g < 6])

    cursor.close()
    conn.close()

    return render_template(
        "class_analytics.html",
        semester=semester,
        avg_gpa=avg_gpa,
        highest=highest,
        lowest=lowest,
        dist=dist,
        subject_labels=subject_labels,
        subject_values=subject_values,
        low_gpa_count=low_gpa_count,
        failed_students=failed_students
    )

if __name__ == '__main__':
    app.run(debug=True)
