from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# --- App & Config ---
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'  # Local DB
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# --- Initialize extensions (Fixed: only ONE init of db) ---
db = SQLAlchemy()
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."

# --- Models ---
class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    __tablename__ = 'students'
    sno = db.Column(db.Integer, primary_key=True)
    stu_name = db.Column(db.String(100), nullable=False)
    fee = db.Column(db.Integer, nullable=False)
    doj = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'sno': self.sno,
            'stu_name': self.stu_name,
            'fee': self.fee,
            'DOJ': self.doj.strftime('%Y-%m-%d') if self.doj else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

# --- DB Setup ---
with app.app_context():
    db.create_all()
    if not Admin.query.filter_by(username='Katyayani').first():
        admin = Admin(username='Katyayani')
        admin.set_password('katy@05102005')
        db.session.add(admin)
        db.session.commit()
        logging.info("Default admin created")

# --- Routes ---
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('login.html')

        admin = Admin.query.filter_by(username=username).first()
        if not admin or not admin.check_password(password):
            flash('Invalid username or password.', 'danger')
            return render_template('login.html')

        login_user(admin)
        flash('Login successful!', 'success')
        return redirect(request.args.get('next') or url_for('dashboard'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    student_count = Student.query.count()
    return render_template('dashboard.html', student_count=student_count)

@app.route('/students')
@login_required
def student_list():
    students = Student.query.all()
    return render_template('students.html', students=students)

@app.route('/students/add', methods=['GET', 'POST'])
@login_required
def add_student_form():
    if request.method == 'POST':
        sno = request.form.get('sno')
        name = request.form.get('stu_name')
        fee = request.form.get('fee')
        doj = request.form.get('doj')

        if not sno or not name or not fee or not doj:
            flash('All fields are required.', 'danger')
            return render_template('add_student.html')

        if Student.query.get(sno):
            flash('Student with this ID already exists.', 'danger')
            return render_template('add_student.html')

        try:
            new_student = Student(
                sno=sno,
                stu_name=name,
                fee=fee,
                doj=datetime.strptime(doj, '%Y-%m-%d').date()
            )
            db.session.add(new_student)
            db.session.commit()
            flash('Student added successfully!', 'success')
            return redirect(url_for('student_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return render_template('add_student.html')

@app.route('/students/search', methods=['GET', 'POST'])
@login_required
def search_student():
    if request.method == 'POST':
        sno = request.form.get('sno', '').strip()
        name = request.form.get('stu_name', '').strip()

        # Case 1: Both fields empty
        if not sno and not name:
            flash('Please enter Student ID or Name to search.', 'warning')
            return render_template('search_student.html')

        # Case 2: Both fields entered – validate match
        if sno and name:
            student = Student.query.get(sno)
            if student and student.stu_name.lower() == name.lower():
                return render_template('search_student.html', student=student)
            else:
                flash('Student ID and Name do not match any record.', 'warning')
                return render_template('search_student.html')

        # Case 3: Only ID
        if sno:
            student = Student.query.get(sno)
            if student:
                return render_template('search_student.html', student=student)
            else:
                flash('No student found with that ID.', 'warning')
                return render_template('search_student.html')

        # Case 4: Only name
        if name:
            students = Student.query.filter(Student.stu_name.ilike(f'%{name}%')).all()
            if students:
                return render_template('search_student.html', students=students)
            else:
                flash('No student found with that name.', 'warning')
                return render_template('search_student.html')

    return render_template('search_student.html')

@app.route('/students/update/<int:sno>', methods=['GET', 'POST'])
@login_required
def update_student(sno):
    student = Student.query.get_or_404(sno)
    if request.method == 'POST':
        new_fee = request.form.get('fee')
        if not new_fee:
            flash('Enter fee amount.', 'danger')
        else:
            try:
                student.fee = int(new_fee)
                db.session.commit()
                flash('Fee updated.', 'success')
                return redirect(url_for('student_list'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {str(e)}', 'danger')

    return render_template('update_student.html', student=student)

@app.route('/students/delete/<int:sno>', methods=['GET', 'POST'])
@login_required
def delete_student(sno):
    student = Student.query.get_or_404(sno)
    if request.method == 'POST':
        try:
            db.session.delete(student)
            db.session.commit()
            flash('Student deleted.', 'success')
            return redirect(url_for('student_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return render_template('delete_student.html', student=student)

# --- API Routes ---
@app.route('/api/students', methods=['GET'])
@login_required
def get_students_api():
    return jsonify([s.to_dict() for s in Student.query.all()])

@app.route('/api/students/<int:sno>', methods=['GET'])
@login_required
def get_student_api(sno):
    student = Student.query.get(sno)
    if not student:
        return jsonify({"error": "Not found"}), 404
    return jsonify(student.to_dict())

@app.route('/api/students', methods=['POST'])
@login_required
def add_student_api():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    required = ['sno', 'stu_name', 'fee', 'DOJ']
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    if Student.query.get(data['sno']):
        return jsonify({"error": "ID exists"}), 409

    try:
        student = Student(
            sno=data['sno'],
            stu_name=data['stu_name'],
            fee=data['fee'],
            doj=datetime.strptime(data['DOJ'], '%Y-%m-%d').date()
        )
        db.session.add(student)
        db.session.commit()
        return jsonify({"message": "Added"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/students/<int:sno>', methods=['PUT'])
@login_required
def update_student_api(sno):
    data = request.get_json()
    student = Student.query.get(sno)
    if not student:
        return jsonify({"error": "Not found"}), 404

    if 'fee' in data:
        student.fee = data['fee']
        db.session.commit()
        return jsonify({"message": "Updated"})

    return jsonify({"error": "No fee provided"}), 400

@app.route('/api/students/<int:sno>', methods=['DELETE'])
@login_required
def delete_student_api(sno):
    student = Student.query.get(sno)
    if not student:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(student)
    db.session.commit()
    return jsonify({"message": "Deleted"})

# --- Run App ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
