import uuid
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db

# ENUMS
ROLE_ADMIN = 'ADMIN'
ROLE_EQUIPMENT_MANAGER = 'EQUIPMENT_MANAGER'
ROLE_CLIMBER = 'CLIMBER'

ACQUISITION_BOUGHT = 'BOUGHT'
ACQUISITION_DONATED = 'DONATED'

CONDITION_AVAILABLE = 'AVAILABLE'
CONDITION_CHECKED_OUT = 'CHECKED_OUT'
CONDITION_MAINTENANCE = 'MAINTENANCE'
CONDITION_LOST = 'LOST'
CONDITION_RETIRED = 'RETIRED'

TX_ACTIVE = 'ACTIVE'
TX_COMPLETED = 'COMPLETED'
TX_OVERDUE = 'OVERDUE'

def generate_uuid():
    return str(uuid.uuid4())

class User(UserMixin, db.Model):
    __tablename__ = 'users_user'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(254), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(50), default=ROLE_CLIMBER, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin_or_manager(self):
        return self.role in [ROLE_ADMIN, ROLE_EQUIPMENT_MANAGER]

class Category(db.Model):
    __tablename__ = 'inventory_category'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(100), nullable=False, unique=True)
    default_lifespan_years = db.Column(db.Integer, nullable=True)
    
    gear_items = db.relationship('GearItem', backref='category', lazy=True)

class GearItem(db.Model):
    __tablename__ = 'inventory_gear'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.String(36), db.ForeignKey('inventory_category.id'), nullable=False)
    
    acquisition_method = db.Column(db.String(20), default=ACQUISITION_BOUGHT)
    purchase_price = db.Column(db.Numeric(10, 2), nullable=True)
    acquisition_date = db.Column(db.Date, nullable=False, default=date.today)
    manufacture_date = db.Column(db.Date, nullable=False)
    
    condition_status = db.Column(db.String(30), default=CONDITION_AVAILABLE)
    photo_url = db.Column(db.String(500), nullable=True)

    transactions = db.relationship('Transaction', backref='gear', lazy=True)
    audits = db.relationship('AuditLog', backref='gear', lazy=True)

class Transaction(db.Model):
    __tablename__ = 'transactions_checkout'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    gear_id = db.Column(db.String(36), db.ForeignKey('inventory_gear.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users_user.id'), nullable=False)
    
    activity_name = db.Column(db.String(255), nullable=False)
    checkout_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expected_return = db.Column(db.Date, nullable=False)
    actual_return = db.Column(db.DateTime, nullable=True)
    
    condition_out = db.Column(db.Text, nullable=True)
    condition_in = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default=TX_ACTIVE)

    user = db.relationship('User', backref='transactions', lazy=True)

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    gear_id = db.Column(db.String(36), db.ForeignKey('inventory_gear.id'), nullable=False)
    performed_by_id = db.Column(db.String(36), db.ForeignKey('users_user.id'), nullable=True)
    
    action = db.Column(db.String(50), nullable=False)  # e.g., STATUS_CHANGED, CREATED
    old_value = db.Column(db.String(255), nullable=True)
    new_value = db.Column(db.String(255), nullable=True)
    note = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    performed_by = db.relationship('User', backref='audit_logs', lazy=True)
