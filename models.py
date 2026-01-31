from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    results = db.relationship('Result', backref='student', lazy=True)

    def __repr__(self):
        return f"<Student {self.roll} - {self.name}>"

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject = db.Column(db.String(128), nullable=False)
    marks = db.Column(db.Float, nullable=False)
    max_marks = db.Column(db.Float, nullable=False, default=100.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def percentage(self):
        try:
            return (self.marks / self.max_marks) * 100
        except Exception:
            return 0

    def __repr__(self):
        return f"<Result {self.subject} - {self.marks}/{self.max_marks}>"
