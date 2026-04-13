import os
import sys

from flask import Flask, redirect, render_template, request, url_for, flash, session

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

from wtforms import Form, SubmitField, StringField, EmailField, PasswordField, BooleanField, ValidationError
from wtforms.validators import DataRequired, Length, Email, EqualTo
from wtforms_sqlalchemy.fields import QuerySelectField

app = Flask("Flask Session", template_folder="/app/templates", static_folder="/app/static")

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SECRET_KEY'] = "zs^CGUybDCZ6ivRaZa4Z"

# MODEL -----------------------------------------------------------------------

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class StudyGroup(db.Model):
    __tablename__ = 'study-groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    member1 = db.Column(db.Integer, db.ForeignKey('users.id'))
    member2 = db.Column(db.Integer, db.ForeignKey('users.id'))
    member3 = db.Column(db.Integer, db.ForeignKey('users.id'))
    member4 = db.Column(db.Integer, db.ForeignKey('users.id'))
    member5 = db.Column(db.Integer, db.ForeignKey('users.id'))

    def as_dict(self):
        return {"id": self.id, "name": self.name, "members": [self.member1, self.member2, self.member3, self.member4, self.member5]}

    @classmethod
    def create_studygroup(cls, name, members):
        studygroup = cls(
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



class StudySession(db.Model):
    __tablename__ = 'study-sessions'

    id = db.Column(db.Integer, primary_key=True)
    studygroup_id = db.Column(db.Integer, db.ForeignKey('study-groups.id'), nullable = False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    topic = db.Column(db.String(100), nullable=True)
    group = db.relationship('StudyGroup', backref='sessions')

    def as_dict(self):
        return {"id": self.id, "studygroup_id": self.studygroup_id, "date": self.date, "time": self.time, "topic": self.topic}

    @classmethod
    def create_studysession(cls, studygroup_id, date, time, topic):
        studysession = cls(
            studygroup_id = studygroup_id,
            date = date,
            time = time,
            topic = topic
            )
        db.session.add(studysession)
        db.session.commit()
        return studysession

class Todo(db.Model):
    __tablename__ = 'todos'

    id = db.Column(db.Integer, primary_key=True)
    studygroup_id = db.Column(db.Integer, db.ForeignKey('study-groups.id'), nullable=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    completed = db.Column(db.Boolean, default=False) 
    
    group = db.relationship("StudyGroup")

    def as_dict(self):
        return {"id": self.id, "studygroup_id": self.studygroup_id, "title": self.title, "content": self.content, "completed": self.completed}

    @classmethod
    def create_todo(cls, studygroup_id, title, content):
        todo = cls(
            studygroup_id = studygroup_id,
            title = title,
            content = content,
            completed = False
            )
        db.session.add(todo)
        db.session.commit()
        return todo


class User(UserMixin, db.Model):
  __tablename__ = 'users'

  id = db.Column(db.Integer, primary_key=True)
  email      = db.Column(db.String(60), unique=True, index=True)
  password   = db.Column(db.String(80))
  name = db.Column(db.String(80), nullable=False)

  study_groups = db.relationship(
        'StudyGroup',
        primaryjoin="or_("
                    "User.id==StudyGroup.member1, "
                    "User.id==StudyGroup.member2, "
                    "User.id==StudyGroup.member3, "
                    "User.id==StudyGroup.member4, "
                    "User.id==StudyGroup.member5)",
        viewonly=True,
        lazy='dynamic'
    )

  def check_password(self, password):
    return bcrypt.check_password_hash(self.password, password)

  @classmethod
  def create_user(cls, name, email, password):
    user = cls( name     = name.strip(),
                email    = email.strip(),
                password = bcrypt.generate_password_hash(password).decode('utf-8') )
    db.session.add(user)
    db.session.commit()
    StudyGroup.create_studygroup(name = "personal", members=[user.id])
    return user

  @staticmethod
  def get_by_id(id):
    return User.query.filter_by(id=id).first()

  @staticmethod
  def get_by_email(email):
    return User.query.filter_by(email=email.strip()).first()
  
  @staticmethod
  def email_exists(email):
    email = User.query.filter_by(email=email).first()
    return email is not None

# creates the above schemas/tables in the database
with app.app_context():
  db.create_all()

# FORMS -----------------------------------------------------------------------

# Custom validator to check if an email already exists
def email_exists(form, field):
  if User.email_exists(field.data):
    raise ValidationError('Email already exists.')

# WTForms for user registration
class RegistrationForm(Form):
  name = StringField('Name', validators=[DataRequired(), Length(min=1, max=80, message='You cannot have less than 1 or more than 80 characters')])
  email = EmailField('Email', validators=[DataRequired(), email_exists, Email()])
  password = PasswordField('Password', validators=[DataRequired(), EqualTo('confirm', message='Password must match')])
  confirm = PasswordField('Confirm', validators=[DataRequired()])
  submit = SubmitField('Register')


# creating WTForm for studySession
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



# We acknowledge the warning below, but it is still how this program functions

# WARNING --------------------------------------------------------------------
# Checking if an email is already registered during form validation introduces 
# a potential security risk. An attacker can use the registration form to check 
# if an email is already registered, effectively allowing them to enumerate 
# valid user emails. A more secure approach is to always return a success 
# message (e.g., "A confirmation email has been sent") regardless of whether 
# the email is already registered. This prevents attackers from determining 
# which emails are registered in the system. This example uses this insecure 
# solution for simplicity as this is purely a demonstration of the session 
# handling infrastructure.
# -----------------------------------------------------------------------------

# WTForms for user login
class LoginForm(Form):
  email = EmailField('Email', validators=[DataRequired(), Email()])
  password = PasswordField('Password', validators=[DataRequired()])
  remember = BooleanField('Remember Me')
  submit = SubmitField('Login')

# WTForms for study groups
def getUsers():
    return db.session.query(User).all()

class CreateStudyGroupForm(Form):
    addMember = QuerySelectField('user', validators=[DataRequired()], query_factory= getUsers, get_label='name')
    name = StringField("Studygroup name", validators=[Length(min=1, max=120)])
    submit = SubmitField('Add')
    submit2 = SubmitField("Plan your StudyGroup")


# SESSIONS --------------------------------------------------------------------

login_manager = LoginManager(app)
login_manager.login_view = 'home'
login_manager.session_protection = 'strong'

@login_manager.user_loader
def load_user_from_id(id):
    return User.get_by_id(id)

# ROUTES ----------------------------------------------------------------------

@app.route("/", methods=('GET','POST'))
def home():
  if current_user.is_authenticated:
    return redirect(url_for('dashboard'))
  else:
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
      user = User.get_by_email(form.email.data.strip())
      if user and user.check_password(form.password.data.strip()):
          login_user(user, form.remember.data)
          return redirect(url_for('dashboard'))
      else:
          flash("Invalid credentials","error")
    return render_template('login.html', form=form)

@app.route("/register", methods=('GET','POST'))
def register():
    if current_user.is_authenticated:
        flash('You are already logged in.','info')
        return redirect(url_for('home'))
    else:
        form = RegistrationForm(request.form)
        if request.method == 'POST' and form.validate():
            User.create_user(
            name = form.name.data,
            email = form.email.data,
            password = form.password.data
            )
            flash("Registration Successful","success")
            return redirect(url_for('home'))
        else:
            return render_template('register.html', form=form)

@app.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    user_groups = get_user_studygroups(current_user.id)

    group_ids = [g.id for g in user_groups]
  
    todos_count = Todo.query.filter(Todo.studygroup_id.in_(group_ids)).count()
    todos_completed_count = Todo.query.filter((Todo.studygroup_id.in_(group_ids)) & (Todo.completed == True)).count()
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

    if request.method == "POST":
        if form.validate():
            todo = Todo.create_todo(
                studygroup_id = request.form.get("group_id"),
                title = form.title.data,
                content = form.content.data
                )
            flash("Todo saved!", "success")

    user_groups = get_user_studygroups(current_user.id)

    group_ids = [g.id for g in user_groups]

    todos = Todo.query.filter(Todo.studygroup_id.in_(group_ids)).all()

    status = "all"
    if "status" in request.args:
        status = request.args.get("status")
        match status:
            case "completed":
                todos = [todo for todo in todos if todo.completed]
            case "pending":
                todos = [todo for todo in todos if not todo.completed]

    todos.reverse()
    return render_template("todos.html", form=form, todos=todos, groups=user_groups, status=status)

@app.route("/complete-todo/<todo_id>")
@login_required
def complete_todo(todo_id):
    todo = Todo.query.filter(Todo.id == todo_id).first()

    if todo:
        todo.completed = True
        db.session.commit()
        flash("Todo marked as done!", "success")

    return redirect(url_for("todos"))


#---------------------------------------------------------------------------------------------------------------

@app.route("/studygroups", methods=["GET"])
@login_required
def studygroups():
    studygroups = get_user_studygroups(current_user.id)
    studygroups = [studygroup.as_dict() for studygroup in studygroups]
    for studygroup in studygroups:
        studygroup["members"] = [get_user_name_from_id(id) for id in studygroup["members"] if id != None]
    return render_template("studygroups.html", studygroups=studygroups)


@app.route("/create-studygroup", methods=["GET", "POST"])
@login_required
def create_studygroup():
    form = CreateStudyGroupForm(request.form)
    if 'studygroup' not in session:
        session['studygroup'] = [(current_user.id, current_user.name)]
    if request.method == 'POST':
        if form.submit.data:
            if (form.addMember.data.id, form.addMember.data.name) not in session['studygroup']:
                session['studygroup'] = session['studygroup'] + [(form.addMember.data.id, form.addMember.data.name)]
        if form.submit2.data and form.validate():
          
          members = [id for (id, name) in session['studygroup']]
          new_group = StudyGroup.create_studygroup(name = form.name.data, members=members)
          session.pop('studygroup', None)
          return redirect(url_for("studygroups"))
    studygroup = [name for (id, name) in session['studygroup']]
    return render_template('create-studygroup.html', form=form, studygroup = studygroup)

#---------------------------------------------------------------------------------------------------------------

@app.route("/studysessions")
@login_required
def studysessions():
    user_groups = get_user_studygroups(current_user.id)

    sessions = []
    for group in user_groups:
        for session in group.sessions:
            session.group_id = group.id
            session.members = []
            for member_id in [group.member1, group.member2, group.member3, group.member4, group.member5]:
                if member_id:
                    user = User.get_by_id(member_id)
                    if user:
                        session.members.append(user.name)
            sessions.append(session)

    sessions.sort(key=lambda s: (s.date, s.time))
    sessions = [session.as_dict() for session in sessions]

    return render_template("studysessions.html", studysessions=sessions)

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
          new_session = StudySession(
              studygroup_id=studygroup_id,
              date=form.date.data,
              time=form.time.data,
              topic=form.topic.data
          )
          db.session.add(new_session)
          db.session.commit()
        elif form.done.data:
          return redirect(url_for("studygroups"))

    sessions = StudySession.query.filter_by(studygroup_id=studygroup_id).order_by(StudySession.date).all()
    
    return render_template("create-studysession.html", form=form, sessions=sessions)

#---------------------------------------------------------------------------------------------------------------

def get_user_studygroups(user_id):
    return StudyGroup.query.filter(
        (StudyGroup.member1 == user_id) |
        (StudyGroup.member2 == user_id) |
        (StudyGroup.member3 == user_id) |
        (StudyGroup.member4 == user_id) |
        (StudyGroup.member5 == user_id)
    ).all()

def get_user_name_from_id(user_id):
    return User.get_by_id(user_id).name
