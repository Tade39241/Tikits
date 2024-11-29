from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Event(db.Model):
    __tablename__='events'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description=db.Column(db.Text, nullable=False)
    start_time= db.Column(db.Time, nullable=False)
    end_time= db.Column(db.Time, nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(50), nullable=False)
    organiser_id = db.Column(db.Integer,  db.ForeignKey('organisers.id'), nullable = False)
    available_capacity= db.Column(db.Integer)
    num_attendees = db.Column(db.Integer,nullable=False)
    tickets = db.relationship('Ticket', primaryjoin="Event.id==Ticket.event_id", backref=db.backref('event'))


    def is_full(self):
        return self.num_attendees == self.capacity

    def is_almost_full(self):
        return len(self.num_attendees) >= 0.95 * self.capacity

    def remaining_capacity(self):
        return self.capacity - len(self.num_attendees)
    
    
    def __init__(self, name, date, duration, description, start_time, end_time , capacity, location, organiser_id,available_capacity,num_attendees):
        self.name=name
        self.date=date
        self.start_time=start_time
        self.end_time=end_time
        self.description=description
        self.duration=duration
        self.organiser_id=organiser_id
        self.capacity=capacity
        self.location=location
        self.available_capacity=capacity
        self.num_attendees=0


class Attendee(db.Model,UserMixin):
    __tablename__='attendees'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    is_organiser = db.Column(db.Boolean, nullable=False)
    tickets = db.relationship('Ticket', primaryjoin="Attendee.id==Ticket.user_id", backref=db.backref('attendee'))


    def __init__(self, username, email, password, is_organiser,):
        self.username=username
        self.email=email
        self.password=password
        self.is_organiser=is_organiser

class Organiser(db.Model,UserMixin):
    __tablename__='organisers'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    is_organiser = db.Column(db.Boolean, nullable=False)
    events = db.relationship('Event', primaryjoin="Organiser.id==Event.organiser_id", backref=db.backref('organiser'))


class Ticket(db.Model):
    __tablename__='tickets'
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(50), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('attendees.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'),nullable=False)    
    
    def __init__(self, barcode, user_id, event_id):
        self.barcode=barcode
        self.user_id=user_id
        self.event_id=event_id

def dbinit():
    db.session.commit()
