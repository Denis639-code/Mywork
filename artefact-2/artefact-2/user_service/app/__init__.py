import sys
import os
import requests

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
app.config['SECRET_KEY'] = "4sq6!YnT9VFv@obz%emJ"

# API -------------------------------------------------------------------------

headers = {"accept": "application/vnd.api+json", "Content-Type": "application/json"}

# MODEL -----------------------------------------------------------------------

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(60), unique=True, index=True)
    password = db.Column(db.String(60))
    name = db.Column(db.String(80), nullable=False)

    def as_dict(self):
        return {"id": self.id, "email": self.email, "name": self.name}

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

    @classmethod
    def create_user(cls, name, email, password):
        user = User(name     = name,
                    email    = email,
                    password = bcrypt.generate_password_hash(password).decode('utf-8') )
        db.session.add(user)
        db.session.commit()

        studygroup = {}
        studygroup["name"] = "personal"
        studygroup["members"] = [user.id]

        print(studygroup, file=sys.stderr)

        attempts = 3

        r = requests.post("http://studygroups:5000/api/v1/studygroups", headers=headers, data = json.dumps(studygroup))
        while (r.status_code != 200 and attempts > 0):
            r = requests.post("http://studygroups:5000/api/v1/studygroups", headers=headers, data = json.dumps(studygroup))
            attempts = attempts - 1

        if r.status_code == 200:
            return user
        else:
            User.query.filter_by(id=user.id).delete()
            db.commit()
            return None

# Clears the database and create tables within the application context
with app.app_context():
  db.create_all()

# ROUTES ----------------------------------------------------------------------


@app.route("/api/v1/users/<user_id>", methods=["GET", "DELETE"])
def user_id(user_id):
    if request.method == "GET":
        user = db.session.query(User).filter_by(id=user_id).first()
        if user == None:
            response = make_response("could not find user")
            response.status_code = 404
            return response

        return jsonify(user.as_dict())
    if request.method == "DELETE":
        # remove user from all studygroups
        r = requests.get("http://studygroups:5000/api/v1/studygroups", params={"user_id": user_id})
        if (r.status_code != 200):
            response = make_response("could not delete user")
            response.status_code = r.status_code
            return response

        studygroups = r.json()
        for studygroup in studygroups:
            studygroup_to_send = {}
            studygroup_to_send["members"] = [member for member in studygroup.get("members") if member != None and str(member) != user_id]
            r = requests.patch(f"http://studygroups:5000/api/v1/studygroups/{studygroup.get('id')}", headers=headers, data=json.dumps(studygroup_to_send))
            if (r.status_code != 200):
                response = make_response("could not delete user")
                response.status_code = r.status_code
                return response
            
        # Remove user from this database
        db.session.query(User).filter_by(id=user_id).delete()
        db.session.commit()

        response = make_response("user deleted")
        response.status_code = 200
        return response


# Maybe we should call this endpoint validate, instead of login ?
@app.route("/api/v1/users/<user_id>/login", methods=["POST"])
def login(user_id):
    if request.method == "POST":
        user = db.session.query(User).filter_by(id=user_id).first()
        password = request.json
        if user.check_password(password):
            response = make_response("login success")
            response.status_code = 200
            return response
        else:
            response = make_response("login failed")
            response.status_code = 403
            return response

@app.route("/api/v1//users", methods=["GET", "POST"])
def users():
    users = db.session.query(User).all()
    users = [user.as_dict() for user in users]

    if request.method == "GET":
        if "email" in request.args:
            users = db.session.query(User).filter_by(email=request.args["email"]).all()
        else:
            users = db.session.query(User).all()
        if users == []:
            response = make_response("user not found")
            response.status_code = 404
            return response
        users = [user.as_dict() for user in users]
        return jsonify(users)
    if request.method == "POST":
        # Create new user and return user object
        # Assumes that incoming data is already validated, ie. name and email is unique
        data = request.json
        user = User.create_user(name = data.get("name"),
                                email = data.get("email"),
                                password = data.get("password")
                                )

        if user == None:
            response = make_response("error: no user has been created")
            response.status_code = 500
            return response
        else:
            return jsonify(user.as_dict())
