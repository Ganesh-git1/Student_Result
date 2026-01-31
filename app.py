from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from config import Config, ADMIN_USERNAME, ADMIN_PASSWORD
from models import db, Student, Result
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField, IntegerField
from wtforms.validators import DataRequired, NumberRange
import os
import csv
import io
from datetime import datetime
from sqlalchemy import or_
import math


app = Flask(__name__)
app.config.from_object(Config)

# add this after app config
@app.context_processor
def inject_site_config():
    # Provide SITE_NAME to all templates; fall back to 'ResultHub'
    return {'SITE_NAME': app.config.get('SITE_NAME', 'ResultHub')}


# Initialize extensions
db.init_app(app)

# Simple forms
class StudentForm(FlaskForm):
    roll = StringField('Roll Number', validators=[DataRequired()])
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email')
    submit = SubmitField('Save')

class ResultForm(FlaskForm):
    roll = StringField('Student Roll', validators=[DataRequired()])
    subject = StringField('Subject', validators=[DataRequired()])
    marks = FloatField('Marks Obtained', validators=[DataRequired(), NumberRange(min=0)])
    max_marks = FloatField('Maximum Marks', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Save')

# Helpers
def is_admin_logged_in():
    return session.get('admin_logged_in')

with app.app_context():
    db.create_all()

0
# Public: student can view their result by roll number
@app.route('/')
def index():
    return redirect(url_for('student_result'))

@app.route('/student/result', methods=['GET', 'POST'])
def student_result():
    roll = request.args.get('roll') or ''
    student = None
    results = []
    if roll:
        student = Student.query.filter_by(roll=roll).first()
        if student:
            results = Result.query.filter_by(student_id=student.id).all()
        else:
            flash('Student not found', 'warning')
    return render_template('student/result.html', student=student, results=results, roll=roll)

# Admin auth
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Logged in successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('Logged out', 'info')
    return redirect(url_for('login'))

# Admin dashboard
@app.route('/admin')
def admin_dashboard():
    if not is_admin_logged_in():
        return redirect(url_for('login'))

    # Pagination & search params
    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1
    per_page = 10

    q = (request.args.get('q') or '').strip()

    # Build base query
    base_query = Student.query
    if q:
        # search both roll and name (case-insensitive)
        like_expr = f"%{q}%"
        base_query = base_query.filter(or_(
            Student.roll.ilike(like_expr),
            Student.name.ilike(like_expr)
        ))

    total = base_query.count()
    total_pages = max(1, math.ceil(total / per_page))

    students = base_query.order_by(Student.created_at.desc()) \
                         .offset((page - 1) * per_page) \
                         .limit(per_page) \
                         .all()

    # Small stats for the dashboard header
    stats = {
        'total_students': Student.query.count(),
        'shown': len(students),
        'total_results': Result.query.count()
    }

    return render_template('admin/dashboard.html',
                           students=students,
                           q=q,
                           page=page,
                           total_pages=total_pages,
                           per_page=per_page,
                           total=total,
                           stats=stats)


@app.route('/admin/student/add', methods=['GET', 'POST'])
def add_student():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    form = StudentForm()
    if form.validate_on_submit():
        existing = Student.query.filter_by(roll=form.roll.data).first()
        if existing:
            flash('Roll already exists', 'warning')
            return redirect(url_for('add_student'))
        student = Student(roll=form.roll.data, name=form.name.data, email=form.email.data)
        db.session.add(student)
        db.session.commit()
        flash('Student added', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/add_student.html', form=form)

@app.route('/admin/students/import', methods=['GET', 'POST'])
def import_students():
    if not is_admin_logged_in():
        return redirect(url_for('login'))

    summary = None
    if request.method == 'POST':
        uploaded = request.files.get('file')
        do_update = bool(request.form.get('update_existing'))
        if not uploaded or uploaded.filename == '':
            flash('No file selected', 'warning')
            return redirect(url_for('import_students'))

        # basic filename check
        if not uploaded.filename.lower().endswith('.csv'):
            flash('Please upload a CSV file', 'warning')
            return redirect(url_for('import_students'))

        # read CSV content (assume UTF-8; handle broken chars gracefully)
        try:
            text = uploaded.stream.read().decode('utf-8', errors='replace')
        except Exception:
            flash('Failed to read uploaded file. Ensure it is a valid CSV (UTF-8).', 'danger')
            return redirect(url_for('import_students'))

        reader = csv.DictReader(io.StringIO(text))
        # expected columns: roll,name,email (email optional)
        required_cols = {'roll', 'name'}
        header_cols = set([c.strip().lower() for c in reader.fieldnames or []])
        if not required_cols.issubset(header_cols):
            flash(f'CSV must include these columns: {", ".join(sorted(required_cols))}', 'warning')
            return redirect(url_for('import_students'))

        added = 0
        updated = 0
        skipped = 0
        errors = []
        row_no = 1
        for row in reader:
            row_no += 1
            try:
                roll = (row.get('roll') or row.get('Roll') or '').strip()
                name = (row.get('name') or row.get('Name') or '').strip()
                email = (row.get('email') or row.get('Email') or '').strip() or None

                if not roll or not name:
                    errors.append(f'Row {row_no}: missing roll or name')
                    continue

                existing = Student.query.filter_by(roll=roll).first()
                if existing:
                    if do_update:
                        existing.name = name
                        existing.email = email
                        db.session.add(existing)
                        updated += 1
                    else:
                        skipped += 1
                else:
                    student = Student(roll=roll, name=name, email=email)
                    db.session.add(student)
                    added += 1
            except Exception as e:
                errors.append(f'Row {row_no}: {str(e)}')

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Database error while saving: ' + str(e), 'danger')
            return redirect(url_for('import_students'))

        summary = {
            'added': added,
            'updated': updated,
            'skipped': skipped,
            'errors': errors,
        }
        flash(f'Import finished — added: {added}, updated: {updated}, skipped: {skipped}', 'success')

    return render_template('admin/import_students.html', summary=summary)


@app.route('/admin/result/add', methods=['GET', 'POST'])
def add_result():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    form = ResultForm()
    if form.validate_on_submit():
        student = Student.query.filter_by(roll=form.roll.data).first()
        if not student:
            flash('Student not found. Add student first.', 'warning')
            return redirect(url_for('add_student'))
        res = Result(student_id=student.id, subject=form.subject.data, marks=form.marks.data, max_marks=form.max_marks.data)
        db.session.add(res)
        db.session.commit()
        flash('Result added', 'success')
        return redirect(url_for('view_results'))
    return render_template('admin/add_result.html', form=form)

@app.route('/admin/results')
def view_results():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    # Optionally allow filter by roll via query param
    roll = request.args.get('roll')
    query = Result.query.join(Student)
    if roll:
        query = query.filter(Student.roll == roll)
    results = query.order_by(Result.created_at.desc()).all()
    return render_template('admin/view_results.html', results=results)

@app.route('/admin/result/delete/<int:result_id>', methods=['POST'])
def delete_result(result_id):
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    r = Result.query.get_or_404(result_id)
    db.session.delete(r)
    db.session.commit()
    flash('Result deleted', 'info')
    return redirect(url_for('view_results'))

@app.route('/admin/student/delete/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    s = Student.query.get_or_404(student_id)
    # delete related results first
    Result.query.filter_by(student_id=s.id).delete()
    db.session.delete(s)
    db.session.commit()
    flash('Student and results deleted', 'info')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
