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
app.config['SECRET_KEY'] = "^h#3FXSDrujYuArUx&et"

# MODEL -----------------------------------------------------------------------

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class Todo(db.Model):
    __tablename__ = 'todos'

    id = db.Column(db.Integer, primary_key=True)
    studygroup_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    completed = db.Column(db.Boolean, default=False) 
    
    def as_dict(self):
        return {"id": self.id, "studygroup_id": self.studygroup_id, "title": self.title, "content": self.content, "completed": self.completed}

    @classmethod
    def create_todo(cls, studygroup_id, title, content):
        todo = Todo(studygroup_id = studygroup_id, title = title, content = content)
        db.session.add(todo)
        db.session.commit()

        return todo

with app.app_context():
  db.create_all()

# ROUTES ----------------------------------------------------------------------

@app.route("/api/v1/todos", methods=["GET", "POST"])
def notes():
    if request.method == "GET":
        if "studygroup_id" in request.args:
            studygroup_id = request.args["studygroup_id"]
            todos = Todo.query.filter_by(studygroup_id=studygroup_id).all()
        else:
            todos = Todo.query.all()
        todos = [todo.as_dict() for todo in todos]
        return jsonify(todos)

    if request.method == "POST":
        data = request.json
        todo = Todo.create_todo(studygroup_id = data.get("studygroup_id"),
                                title = data.get("title"),
                                content = data.get("content")
                                )

        return jsonify(todo.as_dict())

@app.route("/api/v1/todos/<todo_id>", methods=["GET", "PATCH", "DELETE"])
def todo(todo_id):
    todo = db.session.query(Todo).filter_by(id=todo_id).first()
    if todo == None:
        response = make_response("Could not find todo")
        reponse.status_code = 404
        return response

    if request.method == "GET":
        return jsonify(todo.as_dict())

    if request.method == "PATCH":
        data = request.json

        if "completed" in data:
            todo.completed = data.get("completed")
        if "title" in data:
            todo.title = data.get("title")

        db.session.commit()
        return jsonify(todo.as_dict())

    if request.method == "DELETE":
        db.session.query(Todo).filter_by(id=todo_id).delete()
        db.session.commit()
        response = make_response("todo deleted")
        response.status_code = 200
        return response

