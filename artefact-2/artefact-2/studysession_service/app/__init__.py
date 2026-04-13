import sys
import os

from flask import Flask, redirect, render_template, request, url_for, flash, session, make_response, jsonify
import json

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

from wtforms import Form, SubmitField, StringField, EmailField, PasswordField, BooleanField, ValidationError
from wtforms.validators import DataRequired, Length, Email, EqualTo
from wtforms_sqlalchemy.fields import QuerySelectField

app = Flask("Flask Session", template_folder="/app/templates", static_folder="/app/static")

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SECRET_KEY'] = "P7$iF3$Bt2gaqoUNeP9^"

# MODEL -----------------------------------------------------------------------

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class StudySession(db.Model):
   __tablename__ = 'study-sessions'
   
   id = db.Column(db.Integer, primary_key=True)
   studygroup_id = db.Column(db.Integer, nullable = False)
   date = db.Column(db.String(20), nullable=False)
   time = db.Column(db.String(20), nullable=False)
   topic = db.Column(db.String(100), nullable=True)

   def as_dict(self):
       return {"id": self.id, "studygroup_id": self.studygroup_id, "date": self.date, "time": self.time, "topic": self.topic}

   @classmethod
   def create_studysession(cls, studygroup_id, date, time, topic):
        session = StudySession(
          studygroup_id = studygroup_id,
          date = date,
          time = time,
          topic = topic
        )
        db.session.add(session)
        db.session.commit()

        return session


with app.app_context():
  db.create_all()

# ROUTES ----------------------------------------------------------------------

@app.route("/api/v1/studysessions", methods=["GET", "POST"],)
def studygroups():
    if request.method == "GET":
        if "studygroup_id" in request.args:
            studygroup_id = request.args["studygroup_id"]
            sessions = StudySession.query.filter_by(studygroup_id=studygroup_id).order_by(StudySession.date).all()
        else:
            sessions = StudySession.query.order_by(StudySession.date).all()
        sessions = [session.as_dict() for session in sessions]
        return jsonify(sessions)

    if request.method == "POST":
        data = request.json
        session = StudySession.create_studysession(
                                                studygroup_id = data.get("studygroup_id"),
                                                date = data.get("date"),
                                                time = data.get("time"),
                                                topic = data.get("topic")
                                                )
        return jsonify(session.as_dict())

@app.route("/api/v1/studysessions/<studysession_id>", methods=["GET", "PATCH", "DELETE"])
def studysession(studysession_id):
    studysession = db.session.query(StudySession).filter_by(id=studysession_id).first()
    if studysession == None:
        response = make_response("Could not find studysession")
        response.status_code = 404
        return response

    if request.method == "GET":
        return jsonify(studysession.as_dict())

    if request.method == "PATCH":
        data = request.json

        if "topic" in data:
            studysession.topic = data.get("topic")
        if "date" in data:
            studysession.date = data.get("date")
        if "time" in data:
            studysession.time = data.get("time")

        db.session.commit()
        return jsonify(studysession.as_dict())

    if request.method == "DELETE":
        db.session.query(StudySession).filter_by(id=studysession_id).delete()
        db.session.commit()
        response = make_response("studysession deleted")
        response.status_code = 200
        return response

