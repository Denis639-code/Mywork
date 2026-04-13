import sys
import os

from flask import Flask, redirect, render_template, request, url_for, flash, session, make_response, jsonify
import json
import requests

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

from wtforms import Form, SubmitField, StringField, EmailField, PasswordField, BooleanField, ValidationError
from wtforms.validators import DataRequired, Length, Email, EqualTo
from wtforms_sqlalchemy.fields import QuerySelectField

app = Flask("Flask Session", template_folder="/app/templates", static_folder="/app/static")

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SECRET_KEY'] = "QVYsiP$3i@p*BNJ99g&6"

# MODEL -----------------------------------------------------------------------

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class StudyGroup(db.Model):
    __tablename__ = 'study-groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    member1 = db.Column(db.Integer)
    member2 = db.Column(db.Integer)
    member3 = db.Column(db.Integer)
    member4 = db.Column(db.Integer)
    member5 = db.Column(db.Integer)

    def as_dict(self):
        return {"id": self.id, "name": self.name, "members": [self.member1, self.member2, self.member3, self.member4, self.member5]}

    @classmethod
    def create_studygroup(cls, name, members):
        studygroup = StudyGroup(
          name = name,
          member1=members[0] if len(members) > 0 else None,
          member2=members[1] if len(members) > 1 else None,
          member3=members[2] if len(members) > 2 else None,
          member4=members[3] if len(members) > 3 else None,
          member5=members[4] if len(members) > 4 else None
        )
        db.session.add(studygroup)
        db.session.commit()
        return studygroup


with app.app_context():
  db.create_all()

# # ROUTES ----------------------------------------------------------------------

@app.route("/api/v1/studygroups", methods=["GET", "POST"])
def studygroups():
    if request.method == "GET":
        studygroups = []
        if "user_id" in request.args:
            user_id = request.args["user_id"]
            studygroups = StudyGroup.query.filter(
                (StudyGroup.member1 == user_id) |
                (StudyGroup.member2 == user_id) |
                (StudyGroup.member3 == user_id) |
                (StudyGroup.member4 == user_id) |
                (StudyGroup.member5 == user_id)
            ).all()

            studygroups = [group.as_dict() for group in studygroups]
        else:
            studygroups = StudyGroup.query.all()
            studygroups = [group.as_dict() for group in studygroups]

        return jsonify(studygroups)
    if request.method == "POST":
        data = request.json
        studygroup = StudyGroup.create_studygroup(name = data.get("name"), members = data.get("members"))

        return jsonify(studygroup.as_dict())


@app.route("/api/v1/studygroups/<studygroup_id>", methods=["GET", "PATCH", "DELETE"])
def studygroup(studygroup_id):
    studygroup = db.session.query(StudyGroup).filter_by(id=studygroup_id).first()
    if studygroup == None:
        response = make_response("Could not find studygroup")
        reponse.status_code = 404
        return response

    if request.method == "GET":
        return jsonify(studygroup.as_dict())

    if request.method == "PATCH":
        data = request.json
        members = data.get("members")

        if (len(members) == 0):
            return delete_studygroup(studygroup_id)
        else:
            studygroup.member1=members[0] if len(members) > 0 else None,
            studygroup.member2=members[1] if len(members) > 1 else None,
            studygroup.member3=members[2] if len(members) > 2 else None,
            studygroup.member4=members[3] if len(members) > 3 else None,
            studygroup.member5=members[4] if len(members) > 4 else None

            db.session.commit()

            return jsonify(studygroup.as_dict())

    if request.method == "DELETE":
        return delete_studygroup(studygroup_id)

def delete_studygroup(studygroup_id):
        # Delete all studygroup Todos
        r = requests.get("http://todos:5000/api/v1/todos", params={"studygroup_id": studygroup_id})
        if r.status_code != 200:
            response = make_response(f"Could not delete studygroup - id: {studygroup_id}")
            response.status_code = r.status_code
            return response

        todos = r.json()

        for todo in todos:
            r = requests.delete(f"http://todos:5000/api/v1/todos/{todo.get('id')}")
            if r.status_code != 200:
                response = make_response(f"Could not delete studygroup - id: {studygroup_id}")
                response.status_code = r.status_code
                return response

        # Delete all studygroup Studysessions
        r = requests.get("http://studysessions:5000/api/v1/studysessions", params={"studygroup_id": studygroup_id})
        if r.status_code != 200:
            response = make_response(f"Could not delete studygroup - id: {studygroup_id}")
            response.status_code = r.status_code
            return response

        studysessions = r.json()

        for studysession in studysessions:
            r = requests.delete(f"http://studysessions:5000/api/v1/studysessions/{studysession.get('id')}")
            if r.status_code != 200:
                response = make_response(f"Could not delete studygroup - id: {studygroup_id}")
                response.status_code = r.status_code
                return response
        

        # Delete the studygroup
        db.session.query(StudyGroup).filter_by(id=studygroup_id).delete()
        db.session.commit()
        response = make_response("studygroup deleted")
        response.status_code = 200
        return response
