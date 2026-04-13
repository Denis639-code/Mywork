import requests
import json
import os
import sys

from flask import Flask, redirect, render_template, request, url_for, flash, session, jsonify

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

from wtforms import Form, SubmitField, StringField, EmailField, PasswordField, BooleanField, ValidationError, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo
from wtforms_sqlalchemy.fields import QuerySelectField

app = Flask("Flask Session", template_folder="/app/templates", static_folder="/app/static")

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SECRET_KEY'] = "RwfhzFHp#8dzfjLyhtgN"

# API -----------------------------------------------------------------------

headers = {"accept": "application/vnd.api+json", "Content-Type": "application/json"}

# LOGIN -----------------------------------------------------------------------

class User(UserMixin):
    def __init__(self, id, name):
        self.id = id
        self.name = name

login_manager = LoginManager(app)
login_manager.login_view = '/'
login_manager.session_protection = 'strong'

@login_manager.user_loader
def load_user_from_id(user_id):
    r = requests.get(f"http://users:5000/api/v1/users/{user_id}", headers=headers)
    if (r.status_code != 200):
        return None
    else:
        data = r.json()
        return User(data.get("id"), data.get("name"))

def load_user_from_mail(user_email):
    r = requests.get(f"http://users:5000/api/v1/users", headers=headers, params={"email": user_email})
    if (r.status_code != 200):
        return None
    else:
        data = r.json()[0]
        return User(data.get("id"), data.get("name"))

# FORMS -----------------------------------------------------------------------

def email_exists(form, field):
    r = requests.get("http://users:5000/api/v1/users", params={"email": field.data}, headers=headers)
    # This check only works if we know for sure, that the user service is up and running, otherwise another status code could be returned
    if r.status_code == 200:
        raise ValidationError("Email already in use !")

class RegistrationForm(Form):
  name = StringField('Name', validators=[DataRequired(), Length(min=1, max=80, message='You cannot have less than 1 or more than 80 characters')])
  email = EmailField('Email', validators=[DataRequired(), email_exists, Email()])
  password = PasswordField('Password', validators=[DataRequired(), EqualTo('confirm', message='Password must match')])
  confirm = PasswordField('Confirm', validators=[DataRequired()])
  submit = SubmitField('Register')


class CreateStudySessionForm(Form):
   date = StringField('Date (YYYY-MM-DD)', validators=[DataRequired()])
   time = StringField('Time (HH:MM)', validators=[DataRequired()])
   topic = StringField('Topic', validators=[Length(max=40)])
   submit = SubmitField('Schedule Session')
   done = SubmitField('Done')


class TodoForm(Form):
    title = StringField("Title", validators=[DataRequired(), Length(max=120)])
    content = StringField("Content", validators=[DataRequired()])
    submit = SubmitField("Save Todo")


class LoginForm(Form):
  email = EmailField('Email', validators=[DataRequired(), Email()])
  password = PasswordField('Password', validators=[DataRequired()])
  remember = BooleanField('Remember Me')
  submit = SubmitField('Login')

class CreateStudyGroupForm(Form):
    addMember = SelectField('user')
    name = StringField("Studygroup name", validators=[Length(min=1, max=120)])
    submit = SubmitField('Add')
    submit2 = SubmitField("Create your StudyGroup")

# ROUTES ----------------------------------------------------------------------

@app.route("/", methods=('GET','POST'))
def home():
  if current_user.is_authenticated:
    return redirect(url_for('dashboard'))
  else:
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        user = load_user_from_mail(form.email.data.strip())
        if (user == None):
            flash("Invalid credentials", "error")
        else:
            r = requests.post(f"http://users:5000/api/v1/users/{user.id}/login", headers=headers, data=json.dumps(form.password.data.strip()))
            if r.status_code == 200:
                login_user(user, form.remember.data)
                return redirect(url_for('dashboard'))
            else:
                flash("Invalid credentials", "error")
    return render_template('login.html', form=form)

@app.route("/register", methods=('GET','POST'))
def register():
    if current_user.is_authenticated:
        flash('You are already logged in.','info')
        return redirect(url_for('home'))
    else:
        form = RegistrationForm(request.form)
        if request.method == 'POST' and form.validate():
            user = {}
            user["name"] = form.name.data
            user["email"] = form.email.data
            user["password"] = form.password.data
            r = requests.post("http://users:5000/api/v1/users", headers=headers, data = json.dumps(user))
            if r.status_code == 200:
                flash("Account created", "success")
                return redirect(url_for('home'))
            else:
                flash("Something went wrong", "error")
                return render_template('register.html', form=form)
        else:
            return render_template('register.html', form=form)

@app.route("/delete-user/<user_id>")
@login_required
def delete_user(user_id):
    r = requests.delete(f"http://users:5000/api/v1/users/{user_id}")
    if r.status_code == 200:
        flash("user deleted", "success")
    else:
        flash("user not deleted", "error")
    return redirect(url_for("admin"))

@app.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/dashboard", methods=["GET","POST"])
@login_required
def dashboard():
    user_id = current_user.id
    user_groups = get_user_studygroups(user_id)

    todos = []
    for group in user_groups:
        r = requests.get("http://todos:5000/api/v1/todos", headers=headers, params={"studygroup_id": group.get("id")})
        if r.status_code == 200:
            todos = todos + r.json()

    todos_count = len(todos)
    todos_completed_count = len([todo for todo in todos if todo.get("completed") == True])

    todos_pending_count = todos_count - todos_completed_count

    return render_template(
        "index.html",
        todos_count=todos_count,
        todos_completed_count=todos_completed_count,
        todos_pending_count=todos_pending_count
    )

#---------------------------------------------------------------------------------------------------------------

@app.route("/todos", methods=["GET", "POST"])
@login_required
def todos():
    form = TodoForm(request.form)
    user_id = current_user.id
    user_groups = get_user_studygroups(user_id)
    group_ids = [group.get("id") for group in user_groups]

    if request.method == "POST":
        if form.validate():
            selected_group = request.form.get("group_id")
            todo = {}
            todo["user_id"] = current_user.id
            todo["studygroup_id"] = int(selected_group)
            todo["title"] = form.title.data
            todo["content"] = form.content.data
            r = requests.post("http://todos:5000/api/v1/todos", headers=headers, data=json.dumps(todo))
            if r.status_code == 200:
                flash("Todo saved!", "success")
            else:
                flash("Something went wrong :(", "error")

    todos = []
    user_id = current_user.id
    user_groups = get_user_studygroups(user_id)

    for studygroup in user_groups:
        studygroup_id = studygroup.get("id")
        r = requests.get("http://todos:5000/api/v1/todos", params = {"studygroup_id": studygroup_id})
        if r.status_code == 200:
            new_todos = r.json()
            for todo in new_todos:
                todo["studygroup_name"] = studygroup.get("name")
            todos = todos + new_todos

    status = "all"
    if "status" in request.args:
        status = request.args.get("status")
        match status:
            case "completed":
                todos = [todo for todo in todos if todo.get("completed")]
            case "pending":
                todos = [todo for todo in todos if not todo.get("completed")]

    todos.reverse()
    return render_template("todos.html", form=form, todos=todos, groups=user_groups, status=status)

@app.route("/complete-todo/<todo_id>")
@login_required
def complete_todo(todo_id):
    todo = {}
    todo["completed"] = True

    r = requests.patch(f"http://todos:5000/api/v1/todos/{todo_id}", headers=headers, data=json.dumps(todo))
    if r.status_code != 200:
        flash("Could not mark todo as done", "error")

    return redirect(url_for("todos"))

@app.route("/delete-todo/<todo_id>")
@login_required
def delete_todo(todo_id):
    r = requests.delete(f"http://todos:5000/api/v1/todos/{todo_id}")
    if r.status_code == 200:
        flash("todo deleted", "success")
    else:
        flash("todo not deleted", "error")
    return redirect(url_for("admin"))

#---------------------------------------------------------------------------------------------------------------

@app.route("/studygroups", methods=["GET"])
@login_required
def studygroups():
    studygroups = get_user_studygroups(current_user.id)
    for studygroup in studygroups:
        studygroup["members"] = [get_user_name_from_id(id) for id in studygroup["members"] if id != None]
    return render_template("studygroups.html", studygroups=studygroups)

@app.route("/delete-studygroup/<studygroup_id>")
@login_required
def delete_studygroup(studygroup_id):
    r = requests.delete(f"http://studygroups:5000/api/v1/studygroups/{studygroup_id}")
    if r.status_code == 200:
        flash("studygroup deleted", "success")
    else:
        flash("studygroup not deleted", "error")
    return redirect(url_for("admin"))


@app.route("/create-studygroup", methods=["GET", "POST"])
@login_required
def create_studygroup():
    
    form = CreateStudyGroupForm(request.form)
    form.addMember.choices = [(json.dumps({"id": user.get("id"), "name":user.get("name")}), user.get("name")) for user in get_all_users()]
    if 'studygroup' not in session:
        session['studygroup'] = [(current_user.id, current_user.name)]
    if request.method == 'POST':
        if form.submit.data:
            member = json.loads(form.addMember.data)
            if (member.get("id"), member.get("name")) not in session.get('studygroup'):
                session['studygroup'] = session['studygroup'] + [(member.get("id"), member.get("name"))]
        if form.submit2.data and form.validate():
          studygroup = {}
          studygroup["name"] = form.name.data
          studygroup["members"] = [member[0] for member in session['studygroup']] 

          r = requests.post("http://studygroups:5000/api/v1/studygroups", headers=headers, data = json.dumps(studygroup))
          if r.status_code == 200:
              new_group = r.json()
          else:
              flash("Something went wrong", "error")
              return redirect(url_for("create_studygroup"))

          session.pop('studygroup', None)
          studygroup_id = new_group.get("id")
          return redirect(url_for("studygroups", studygroup_id=studygroup_id))
    studygroup = ", ".join([member[1] for member in session['studygroup']])
    return render_template('create-studygroup.html', form=form, studygroup=studygroup)

#---------------------------------------------------------------------------------------------------------------

@app.route("/studysessions")
@login_required
def studysessions():
    user_id = current_user.id
    user_groups = get_user_studygroups(user_id)

    studysessions = []

    for studygroup in user_groups:
        studygroup_id = studygroup.get("id")
        r = requests.get("http://studysessions:5000/api/v1/studysessions", params = {"studygroup_id": studygroup_id})
        if r.status_code == 200:
            new_studysessions = r.json()
            for studysession in new_studysessions:
                studysession["studygroup_name"] = studygroup.get("name")
                studysession["studygroup_members"] = [get_user_name_from_id(id) for id in studygroup.get("members") if not id == None]
            studysessions = studysessions + new_studysessions

    studysessions.sort(key=lambda s: (s.get("date"), s.get("time")))

    return render_template("studysessions.html", studysessions=studysessions)

@app.route("/create-studysession", methods=["GET", "POST"])
@login_required
def create_studysession():
    form = CreateStudySessionForm(request.form)
    studygroup_id = request.args.get("studygroup_id")
    if not studygroup_id:
       flash("no group have been created or selected")
       return redirect(url_for("studygroups"))

    if request.method == 'POST' and form.validate():
        if form.submit.data:
          studysession = {}
          studysession["studygroup_id"] = studygroup_id
          studysession["date"] = form.date.data
          studysession["time"] = form.time.data
          studysession["topic"] = form.topic.data

          r = requests.post("http://studysessions:5000/api/v1/studysessions", headers=headers, data = json.dumps(studysession))
          if r.status_code != 200:
              flash("Something went wrong", "error")
              return redirect(url_for("create_studysession"))


        elif form.done.data:
          return redirect(url_for("studysessions"))

    r = requests.get("http://studysessions:5000/api/v1/studysessions", headers=headers)
    if r.status_code == 200:
        sessions = r.json()
    else:
        flash("Something went wrong", "error")
        sessions = []
    
    return render_template("create-studysession.html", form=form, sessions=sessions)

@app.route("/delete-studysession/<studysession_id>")
@login_required
def delete_studysession(studysession_id):
    r = requests.delete(f"http://studysessions:5000/api/v1/studysessions/{studysession_id}")
    print(r)
    if r.status_code == 200:
        flash("studysession deleted", "success")
    else:
        flash("studysession not deleted", "error")
    return redirect(url_for("admin"))

#---------------------------------------------------------------------------------------------------------------

@app.route("/admin")
@login_required
def admin():
    studygroups = []
    users = []
    todos = []
    studysessions = []

    r = requests.get("http://studygroups:5000/api/v1/studygroups")
    if (r.status_code == 200):
        studygroups = r.json()

    r = requests.get("http://users:5000/api/v1/users")
    if (r.status_code == 200):
        users = r.json()

    r = requests.get("http://todos:5000/api/v1/todos")
    if (r.status_code == 200):
        todos = r.json()

    r = requests.get("http://studysessions:5000/api/v1/studysessions")
    if (r.status_code == 200):
        studysessions = r.json()

    for studygroup in studygroups:
        studygroup["members"] = [get_user_name_from_id(id) for id in studygroup["members"] if id != None]

    return render_template("admin.html", studygroups = studygroups, users = users, todos = todos, studysessions = studysessions)

# Helper functions ---------------------------------------------------------------------------------------------

def get_user_studygroups(user_id):
    r = requests.get("http://studygroups:5000/api/v1/studygroups", params = {"user_id": user_id})
    if r.status_code == 200:
        user_groups = r.json()
    else:
        flash("something went wrong", "error")
        user_groups = []
    return user_groups

def get_user_name_from_id(user_id):
    r = requests.get(f"http://users:5000/api/v1/users/{user_id}", headers=headers)
    if r.status_code == 200:
        return r.json().get("name")
    else:
        return "error"

def get_all_users():
    r = requests.get("http://users:5000/api/v1/users")
    if r.status_code == 200:
        return r.json()
    else:
        return []
