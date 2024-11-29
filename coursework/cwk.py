from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_login import login_required, current_user, LoginManager, login_user, logout_user
from flask_mail import Mail,Message
from db_schema import db, Organiser, Event, Ticket,Attendee, dbinit
import werkzeug
import uuid
import json
from random import randint
from datetime import datetime
import barcode
from markupsafe import Markup, escape
from functools import wraps
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///tickets.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']= False
app.secret_key="random key"
app.config['SECURITY_PASSWORD_SALT']= 'password salt'
app.config['MAIL_USE_TLS']=False
app.config['MAIL_SUPPRESS_SEND'] = False
app.config['Mail_DEFAULT_SENDER'] = "Event-flow@warwick.ac.uk"
mail = Mail(app)

db.init_app(app)

resetdb = False
if resetdb:
    with app.app_context():
        # drop everything, create all the tables, then put some data into the tables
        db.drop_all()
        db.create_all()
        dbinit()


login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(id):
    type = session.get('type')
    if type == 'organiser':
        user = Organiser.query.filter_by(id = id).first()
    elif type == 'attendee':
        user = Attendee.query.filter_by(id = id).first()
    else:
        user = None
    return user

# ensures that the current user is an organiser
def organiser_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session.get('type') == 'organiser':
            return f(*args, **kwargs)
        else:
            flash("You need to be an organiser")
            return redirect(url_for('index'))
    return wrap

# ensures that the current user is an attendee
def attendee_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session.get('type') == 'attendee':
            return f(*args, **kwargs)
        else:
            flash("You need to be an attendee")
            return redirect(url_for('index'))
    return wrap

#ensures that the current user is logged in
def registration_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session.get('otp'):
             return f(*args, **kwargs)
        else:
            return redirect(url_for('index'))
    return wrap

#route to the index
@app.route('/')
def index():
    with open('README.md') as readme:
      with open('requirements.txt') as req:
        return render_template('index.html', README=readme.read(), requirements=req.read())

@app.route('/validate', methods=['GET', 'POST'])
@registration_required
def validate():
    if request.method == 'POST':
        user_otp = escape(request.form.get('otp'))
        # takes the otp code the user input and checks if its the same as the one saved in the session/sent to their email
        if user_otp == session['otp']:
            user_dict = json.loads(session['user'])

            if user_dict['is_organiser']==True:

                # if valid the user object is created using the values that were serialised in json then converted back, added to DB then redirected to login
                user = Organiser(username=user_dict['username'],email=user_dict['email'],password=user_dict['password'],is_organiser=user_dict['is_organiser'])
            else:
                user = Attendee(username=user_dict['username'],email=user_dict['email'],password=user_dict['password'],is_organiser=user_dict['is_organiser'])
            db.session.add(user)
            db.session.commit()

            flash("VALID OTP CODE",category='OTP')
            return redirect(url_for('login'))
        else:
            # if not the user remains on the page awaiting a correct input
            flash('Incorrect OTP code. Try again.',category='OTP')
            return render_template('validate.html')
    else:
        return render_template('validate.html')
       
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = escape (request.form['email'])
        password = escape( request.form['password'])
        checkbox = request.form.get('organiser',default=False)

        # checks if the checkbox is ticked and logs in as a organiser if it is
        if checkbox != False:
            user = Organiser.query.filter_by(email=email).first()
            if user:
                if werkzeug.security.check_password_hash(user.password,password):
                    login_user(user, remember = False)
                    session.permanent = True
                    # saves the user name as well as the user type in the session
                    session['type'] = 'organiser'
                    session['username'] = user.username
                    return redirect(url_for('dashboard'))
                else:
                    flash("Incorrect Details",category='login')
                    return render_template('login.html')
                
        else:
            user = Attendee.query.filter_by(email = email).first()
            if user:
                if werkzeug.security.check_password_hash(user.password,password):
                    login_user(user, remember = False)
                    session.permanent = True
                     # saves the user name as well as the user type in the session
                    session['type'] = 'attendee'
                    session['username'] = user.username
                    return redirect(url_for('dashboard'))
                else:
                    flash("Incorrect Details",category='login')
                    return render_template('login.html')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = escape(request.form['name'])
        email = escape(request.form['email'])
        password = escape(request.form['password'])
        confirm_password = escape(request.form['confirm_password'])
        organiser_code = escape(request.form.get('organiser_code',False))
        hashed_pw = werkzeug.security.generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        if password != confirm_password:
            # Passwords don't match, show error message
            return render_template('registration.html', error='Passwords do not match')
        # checks to see if the organiser code is valid, if it is the user object is registered as a organiser if not then they are a attendee
        if organiser_code =='Dc5_G1gz':
            user = Organiser(username=username, email=email, password=hashed_pw,is_organiser=True)
        else:
            user = Attendee(username=username, email=email, password=hashed_pw,is_organiser=False)
        # saves the user sign up data in a dictionary to allow it to be converted to JSON and get saved in the session
        user_dict = {
            'username': user.username,
            'email': user.email,
            'password': user.password,
            'is_organiser': user.is_organiser,
        }

        # before the user data is added to the database and commited we will send a OTP to their email to check if they're valid emails
        otp = randint(111111,999999)
        # the OTP and the user are then saved in the session
        session['otp'] = str(otp)
        session['user'] = json.dumps(user_dict)
        # this then sends the OTP to the recicpients email address then redirects them to the validation page
        msg = Message('OTP', sender=app.config['Mail_DEFAULT_SENDER'],recipients=[email])
        msg.body = session['otp']
        mail.send(msg)
        return redirect(url_for('validate'))
    else:
        return render_template('registration.html')

@app.route('/events')
def events():
    events = Event.query.all()
    return render_template('events.html', events=events)

@app.route('/request_ticket/<int:event_id>', methods=['GET', 'POST'])
@login_required
@attendee_required
def request_ticket(event_id):
    event = Event.query.get(event_id)
    if event is None:
        flash('Event not found')
        return redirect(url_for('events'))

    if event.is_full():
        flash('This event is full')
        return redirect(url_for('event_details', event_id=event.id))
    
    if request.method == 'POST':
        quantity = int(request.form.get('num_tickets'))

        # if the event is not full...
        if not event.is_full():
            ticket_list = []
            for i in range(quantity):
                # generate a unique universal identefier then assigns it as a barcode number for the ticket
                number = str(uuid.uuid4())
                ticket = Ticket(barcode=number,user_id=current_user.id,event_id=event.id)
                ticket_list.append(ticket)
            db.session.add_all(ticket_list)
            if (event.available_capacity - quantity) < 0:
                flash("not this many tickets available",category='request_ticket')
            else:
                event.num_attendees +=quantity
                event.available_capacity-=quantity
                db.session.commit()
            # alerts organiser that their event is full
            if event.available_capacity==0:
                organiser = Organiser.query.filter_by(id=event.organiser_id).first()

                msg = Message('Capacity Alert!',sender=app.config['Mail_DEFAULT_SENDER'],recipients=[organiser.email])
                msg.body = f'Your event { event.name } has reached the maximum capacity of {event.capacity} attendees.'
                mail.send(msg)

            return redirect(url_for('events'))
    return render_template('request_ticket.html', event=event)

@app.route('/logout')
@login_required
def logout():
    # removes data from session
    session.pop('username',None)
    session.pop('type',None)
    logout_user()
    return redirect(url_for('index'))

@app.route('/create_event', methods=['GET', 'POST'])
@login_required
@organiser_required
def create_event():
    if request.method == 'POST':
        # Get data from form
        event_name = escape(request.form['event_name'])
        event_date = escape(request.form['event_date'])
        event_description = escape(request.form['event_description'])
        event_date = datetime.strptime(request.form['event_date'], '%Y-%m-%d')
        event_start_time = datetime.strptime(request.form['event_start_time'], "%H:%M")
        event_end_time = datetime.strptime(request.form['event_end_time'], "%H:%M")
        event_capacity = escape(request.form['event_capacity'])
        event_location = escape(request.form['event_location'])
        event_duration = event_end_time - event_start_time
        event_duration = event_duration.total_seconds()/60

    
        # Create new Event object
        event = Event(  name=event_name, 
                        date=event_date,
                        description=event_description,
                        start_time =event_start_time.time(),
                        end_time=event_end_time.time(),
                        duration= event_duration,
                        capacity= event_capacity,
                        location= event_location, 
                        organiser_id=current_user.id,
                        available_capacity=event_capacity,
                        num_attendees=0,
                        )
        
        # Add event to database and commit
        db.session.add(event)
        db.session.commit()

        return redirect(url_for('dashboard'))
    else:
        return render_template('create_event.html')

@app.route('/dashboard')
@login_required
def dashboard():

    if current_user.is_organiser:
        # If user is an organiser, display their events and allow editing
        events = Event.query.filter_by(organiser_id=current_user.id).all()
        return render_template('organiser_dashboard.html', events=events)
    else:
        # If user is an attendee, display their tickets and associated events
        tickets = Ticket.query.filter_by(user_id=current_user.id).all()
        events = [ticket.event for ticket in tickets ]
        # only shows one event if they have multiple tickets to one
        if len(events) ==0:
            different_events = events
        else:
            different_events = [events[0]]
        for i in range(1,len(events)):
            if events[i] not in different_events:
                different_events.append(events[i])

        return render_template('attendee_dashboard.html', tickets=tickets, events=different_events)

@app.route('/event/<int:event_id>', methods=['GET'])
@login_required
def event_details(event_id):
    event = Event.query.get(event_id)

    return render_template('event_details.html', event=event, user=current_user)

@app.route('/event/ticket/<int:ticket_id>', methods=['GET','POST'])
@login_required
def ticket_details(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    # generates and renders a barcode based on uuid
    EAN = barcode.get_barcode_class('code128')
    my_ean = EAN(ticket.barcode).render()

    #if ticket is deleted reduce the num of attendees and increment the available capacity
    if request.method == 'POST':
        db.session.delete(ticket)
        ticket.event.num_attendees-=1
        ticket.event.available_capacity+=1
        db.session.commit()

        return redirect(url_for('dashboard'))

    
    return render_template('ticket_details.html', user=current_user,ticket=ticket,svg_code=Markup(my_ean, "unicode_escape"))

@app.route('/cancel_event/<event_id>', methods=['GET', 'POST'])
@organiser_required
def cancel_event(event_id):
    event = Event.query.get(event_id)
    #if the event does not exist then abort 404
    if not event:
        abort(404)
    # if the current user is trying to accesss an event they did not create
    if current_user.id != event.organiser_id:
        abort(403)

    if request.method == 'POST':
        flash('The event has been cancelled.')
        attendees = Attendee.query.join(Ticket).filter_by(event_id=event_id).all()
        emails = [attendee.email for attendee in attendees]

        # sends out an email to all ticket holders
    
        msg = Message('We regret to inform you',sender=app.config['Mail_DEFAULT_SENDER'],recipients=emails)
        msg.body = 'The event organiser has decided to cancel the event'
        mail.send(msg)
    
        # deletes all tickets for that event form the database
        tickets =  Ticket.query.filter_by(event_id=event.id).all()
        for ticket in tickets:
            db.session.delete(ticket)

        db.session.delete(event)
        db.session.commit()
        
        return redirect(url_for('dashboard'))

    return render_template('cancel_event.html', event=event)

@app.route('/promote_user', methods=['GET', 'POST'])
@organiser_required
def promote_user():

    attendee_list = Attendee.query.all()
    # a list of emails of all attendees
    emails = [attendee.email for attendee in attendee_list]
    
    if request.method == 'POST':
        email = escape(request.form['attendee_email'])
        user = Attendee.query.filter_by(email=email).first()

        # if the user is already an organiser then just redirect
        if Organiser.query.filter_by(email=email).first():
            flash("Already an organiser")
            return redirect(url_for('dashboard'))
        # if not add them to the organiser database
        added_user = Organiser(username=user.username, email=user.email, password=user.password,is_organiser=True)
        db.session.add(added_user)
        db.session.commit()
        # then alert them of their promotion
        msg = Message("You've been promoted!",sender=app.config['Mail_DEFAULT_SENDER'],recipients=[email])
        msg.body = f" Hi {user.username}, {current_user.username} has decided to promote you to an organiser. \n \n You can log in as an organiser with the same details as before just click the 'login as organiser box' "
        mail.send(msg)

        return redirect(url_for('dashboard'))
    

    return render_template('promote_user.html',attendee_list=emails)
