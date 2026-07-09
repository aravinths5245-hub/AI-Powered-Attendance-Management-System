from werkzeug.security import generate_password_hash

from app import app
from models import db, User, Department, Course, Subject, Student, Faculty


def seed_data():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email='admin@example.com').first():
            admin = User(full_name='Admin User', email='admin@example.com', password_hash=generate_password_hash('admin123'), role='admin')
            db.session.add(admin)

        if not Department.query.first():
            dept = Department(name='Computer Science', code='CS')
            db.session.add(dept)
            db.session.flush()
            course = Course(name='B.Tech Computer Science', code='BTECH-CS', department_id=dept.id)
            subject = Subject(name='Artificial Intelligence', code='AI101', course_id=course.id)
            db.session.add_all([course, subject])

        if not Student.query.first():
            student = Student(student_id='STU001', full_name='Alicia Brown', email='alicia@example.com', phone='9999999999', department_id=1, course_id=1, year='2nd Year', status='active')
            db.session.add(student)

        if not Faculty.query.first():
            faculty = Faculty(faculty_id='FAC001', full_name='Dr. Michael Scott', email='faculty@example.com', phone='8888888888', department_id=1, subject_id=1, role='faculty')
            db.session.add(faculty)

        db.session.commit()


if __name__ == '__main__':
    seed_data()
    print('Seed data inserted successfully.')
