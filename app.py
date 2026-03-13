import os
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

from extensions import db, login_manager
from models import (
    User, Category, GearItem, Transaction, AuditLog,
    ROLE_ADMIN, ROLE_EQUIPMENT_MANAGER, ROLE_CLIMBER,
    CONDITION_AVAILABLE, CONDITION_CHECKED_OUT, CONDITION_MAINTENANCE, CONDITION_LOST, CONDITION_RETIRED,
    TX_ACTIVE, TX_COMPLETED, TX_OVERDUE
)

from sqlalchemy.exc import IntegrityError

def create_app():
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'super-secret-local-key-replace-me')
    
    db_url = os.getenv('DATABASE_URL', 'sqlite:///local.db')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        # Ensure tables exist
        db.create_all()
        # Create default admin if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role=ROLE_ADMIN)
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
            print("Created default admin user (admin/admin)")

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)

    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    # --- HELPERS ---
    def log_audit(gear_id, action, old_val=None, new_val=None, note=None):
        log = AuditLog(
            gear_id=gear_id,
            performed_by_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            old_value=old_val,
            new_value=new_val,
            note=note
        )
        db.session.add(log)

    def admin_required(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_admin_or_manager:
                flash("You do not have permission to access this page.", "error")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function

    # --- AUTH ROUTES ---
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                if not user.is_active:
                    flash('Account is inactive.', 'error')
                    return redirect(url_for('login'))
                login_user(user)
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'error')
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        if request.method == 'POST':
            email = request.form.get('email')
            phone = request.form.get('phone')
            password = request.form.get('password')
            
            current_user.email = email
            current_user.phone_number = phone
            
            if password:
                current_user.set_password(password)
                
            db.session.commit()
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('profile'))
            
        return render_template('profile.html')

    # --- CORE ROUTES ---
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        if current_user.is_admin_or_manager:
            total_gear = GearItem.query.count()
            checked_out = GearItem.query.filter_by(condition_status=CONDITION_CHECKED_OUT).count()
            maintenance = GearItem.query.filter_by(condition_status=CONDITION_MAINTENANCE).count()
            
            # Very basic 'alerts' concept
            alerts_count = maintenance
            
            recent_tx = Transaction.query.order_by(Transaction.checkout_date.desc()).limit(5).all()
            return render_template('dashboard_admin.html', 
                                   total_gear=total_gear, 
                                   checked_out=checked_out, 
                                   maintenance=maintenance,
                                   alerts_count=alerts_count,
                                   recent_tx=recent_tx)
        else:
            # Climber view
            my_tx = Transaction.query.filter_by(user_id=current_user.id, status=TX_ACTIVE).all()
            return render_template('dashboard_climber.html', active_checkouts=my_tx)

    # --- USER ROUTES ---
    @app.route('/users')
    @login_required
    @admin_required
    def user_list():
        users = User.query.all()
        return render_template('users.html', users=users)

    @app.route('/users/add', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def user_add():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            email = request.form.get('email')
            phone = request.form.get('phone')
            role = request.form.get('role')
            
            if not username or not password:
                flash('Username and Password are required', 'error')
                return redirect(url_for('user_add'))
                
            if User.query.filter_by(username=username).first():
                flash('Username already exists.', 'error')
                return redirect(url_for('user_add'))
                
            new_user = User(username=username, email=email, phone_number=phone, role=role)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash(f'User {username} created successfully.', 'success')
            return redirect(url_for('user_list'))
            
        return render_template('user_add.html', roles=[ROLE_ADMIN, ROLE_EQUIPMENT_MANAGER, ROLE_CLIMBER])

    @app.route('/users/<user_id>/edit', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def user_edit(user_id):
        user = User.query.get_or_404(user_id)
        if request.method == 'POST':
            user.username = request.form.get('username')
            user.email = request.form.get('email')
            user.phone_number = request.form.get('phone')
            user.role = request.form.get('role')
            user.is_active = 'is_active' in request.form
            
            password = request.form.get('password')
            if password:
                user.set_password(password)
                
            db.session.commit()
            flash(f'User {user.username} updated.', 'success')
            return redirect(url_for('user_list'))
            
        return render_template('user_edit.html', user=user, roles=[ROLE_ADMIN, ROLE_EQUIPMENT_MANAGER, ROLE_CLIMBER])

    @app.route('/users/<user_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def user_delete(user_id):
        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            flash('You cannot delete yourself.', 'error')
            return redirect(url_for('user_list'))
        
        username = user.username
        db.session.delete(user)
        db.session.commit()
        flash(f'User {username} deleted.', 'success')
        return redirect(url_for('user_list'))

    # --- CATEGORY ROUTES ---
    @app.route('/categories')
    @login_required
    @admin_required
    def category_list():
        categories = Category.query.all()
        return render_template('categories.html', categories=categories)

    @app.route('/categories/add', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def category_add():
        if request.method == 'POST':
            name = request.form.get('name')
            lifespan_str = request.form.get('default_lifespan_years')
            
            if not name:
                flash('Category name is required', 'error')
                return redirect(url_for('category_add'))

            lifespan = int(lifespan_str) if lifespan_str else None

            new_category = Category(
                name=name,
                default_lifespan_years=lifespan
            )

            try:
                db.session.add(new_category)
                db.session.commit()
                flash(f'Category "{name}" created successfully', 'success')
                return redirect(url_for('category_list'))
            except IntegrityError:
                db.session.rollback()
                flash('Category name already exists', 'error')
                return redirect(url_for('category_add'))

        return render_template('category_add.html')

    # --- GEAR ROUTES ---
    @app.route('/gear')
    @login_required
    def gear_list():
        status_filter = request.args.get('status')
        if status_filter:
            items = GearItem.query.filter_by(condition_status=status_filter).all()
        else:
            items = GearItem.query.all()
        return render_template('gear_list.html', items=items)

    @app.route('/gear/add', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def gear_add():
        categories = Category.query.all()
        if request.method == 'POST':
            name = request.form.get('name')
            cat_id = request.form.get('category_id')
            acq_method = request.form.get('acquisition_method')
            price = request.form.get('purchase_price')
            mfg_date_str = request.form.get('manufacture_date')
            
            cat = Category.query.get(cat_id)
            if not cat:
                # auto create if someone types a new one? For now just handle strictly
                pass 
                
            mfg_date = datetime.strptime(mfg_date_str, '%Y-%m-%d').date() if mfg_date_str else date.today()
            price = float(price) if price else None

            new_gear = GearItem(
                name=name,
                category_id=cat_id,
                acquisition_method=acq_method,
                purchase_price=price,
                manufacture_date=mfg_date,
                condition_status=CONDITION_AVAILABLE
            )
            db.session.add(new_gear)
            db.session.commit() # Commit to get ID
            
            log_audit(new_gear.id, 'ITEM_ADDED', new_val=CONDITION_AVAILABLE)
            db.session.commit()
            
            flash('Gear item added successfully', 'success')
            return redirect(url_for('gear_list'))
            
        return render_template('gear_add.html', categories=categories)

    @app.route('/gear/<id>')
    @login_required
    def gear_detail(id):
        item = GearItem.query.get_or_404(id)
        
        # Build a unified timeline of events
        timeline = []
        
        txs = Transaction.query.filter_by(gear_id=id).all()
        for tx in txs:
            timeline.append({
                'type': 'TRANSACTION',
                'date': tx.checkout_date,
                'data': tx
            })
            
        audits = AuditLog.query.filter_by(gear_id=id).all()
        for audit in audits:
            # Include all status-related changes or manual notes in the timeline
            if audit.action in ['MANUAL_STATUS_CHANGE', 'CONDITION_UPDATE', 'CHECKOUT', 'CHECKIN', 'ITEM_ADDED']:
                timeline.append({
                    'type': 'AUDIT',
                    'date': audit.timestamp,
                    'data': audit
                })
        
        # Sort by date descending
        timeline.sort(key=lambda x: x['date'], reverse=True)
        
        return render_template('gear_detail.html', item=item, timeline=timeline)

    @app.route('/gear/<id>/status', methods=['POST'])
    @login_required
    @admin_required
    def gear_status_update(id):
        gear = GearItem.query.get_or_404(id)
        new_status = request.form.get('status')
        note = request.form.get('note')
        
        old_status = gear.condition_status
        gear.condition_status = new_status
        
        log_audit(gear.id, 'MANUAL_STATUS_CHANGE', old_val=old_status, new_val=new_status, note=note)
        db.session.commit()
        
        flash(f'Updated status for {gear.name} to {new_status}.', 'success')
        return redirect(url_for('gear_detail', id=gear.id))

    # --- TRANSACTIONS ---
    @app.route('/checkout', methods=['GET', 'POST'])
    @login_required
    def checkout():
        if request.method == 'POST':
            if current_user.is_admin_or_manager:
                user_id = request.form.get('user_id')
            else:
                user_id = current_user.id
                
            gear_ids = request.form.getlist('gear_ids')
            activity = request.form.get('activity_name')
            exp_return_str = request.form.get('expected_return')
            condition_out = request.form.get('condition_out')
            
            if not gear_ids:
                flash('Please select at least one item.', 'error')
                return redirect(url_for('checkout'))

            exp_return = datetime.strptime(exp_return_str, '%Y-%m-%d').date()
            
            items_processed = 0
            for gear_id in gear_ids:
                gear = GearItem.query.get(gear_id)
                if not gear or gear.condition_status != CONDITION_AVAILABLE:
                    flash(f'Item {gear.name if gear else gear_id} is not available for checkout', 'error')
                    continue
                    
                tx = Transaction(
                    gear_id=gear.id,
                    user_id=user_id,
                    activity_name=activity,
                    expected_return=exp_return,
                    condition_out=condition_out,
                    status=TX_ACTIVE
                )
                
                old_status = gear.condition_status
                gear.condition_status = CONDITION_CHECKED_OUT
                
                db.session.add(tx)
                log_audit(gear.id, 'CHECKOUT', old_val=old_status, new_val=CONDITION_CHECKED_OUT)
                items_processed += 1
            
            db.session.commit()
            
            if items_processed > 0:
                flash(f'Successfully checked out {items_processed} items.', 'success')
            return redirect(url_for('dashboard'))
            
        users = User.query.filter_by(is_active=True).all() if current_user.is_admin_or_manager else []
        gear = GearItem.query.filter_by(condition_status=CONDITION_AVAILABLE).all()
        return render_template('checkout.html', users=users, available_gear=gear)

    @app.route('/checkin/bulk', methods=['GET', 'POST'])
    @login_required
    def checkin_bulk():
        selected_user_id = request.args.get('user_id')
        if not selected_user_id:
            selected_user_id = current_user.id
            
        # Permission check
        if not current_user.is_admin_or_manager and selected_user_id != current_user.id:
            flash("You do not have permission to view this user's checkouts.", "error")
            return redirect(url_for('dashboard'))

        selected_user = User.query.get_or_404(selected_user_id)
        active_txs = Transaction.query.filter_by(user_id=selected_user_id, status=TX_ACTIVE).all()
        
        if request.method == 'POST':
            tx_ids = request.form.getlist('tx_ids')
            condition_in = request.form.get('condition_in')
            new_gear_status = request.form.get('new_gear_status')

            if not tx_ids:
                flash('Please select at least one item to return.', 'error')
                return redirect(url_for('checkin_bulk', user_id=selected_user_id))

            # Prevent non-admins from retiring gear
            if not current_user.is_admin_or_manager and new_gear_status == 'RETIRED':
                new_gear_status = CONDITION_AVAILABLE

            items_processed = 0
            for tx_id in tx_ids:
                tx = Transaction.query.get(tx_id)
                if not tx or tx.status != TX_ACTIVE:
                    continue
                
                # Verify permission for this specific transaction
                if not current_user.is_admin_or_manager and tx.user_id != current_user.id:
                    continue

                tx.condition_in = condition_in
                tx.actual_return = datetime.utcnow()
                tx.status = TX_COMPLETED
                
                old_status = tx.gear.condition_status
                tx.gear.condition_status = new_gear_status
                
                db.session.add(tx)
                log_audit(tx.gear.id, 'CHECKIN', old_val=old_status, new_val=new_gear_status)
                items_processed += 1
            
            db.session.commit()
            
            if items_processed > 0:
                flash(f'Successfully checked in {items_processed} items.', 'success')
            return redirect(url_for('dashboard'))

        users = User.query.filter_by(is_active=True).all() if current_user.is_admin_or_manager else []
        return render_template('checkin_bulk.html', active_txs=active_txs, users=users, selected_user=selected_user)

    @app.route('/checkin/<tx_id>', methods=['GET', 'POST'])
    @login_required
    def checkin(tx_id):
        tx = Transaction.query.get_or_404(tx_id)
        if tx.status != TX_ACTIVE:
            flash('This transaction is already completed.', 'error')
            return redirect(url_for('dashboard'))
            
        if not current_user.is_admin_or_manager and tx.user_id != current_user.id:
            flash('You do not have permission to check in this item.', 'error')
            return redirect(url_for('dashboard'))
            
        if request.method == 'POST':
            condition_in = request.form.get('condition_in')
            # Fetch status from form
            new_gear_status = request.form.get('new_gear_status')
            
            # Prevent non-admins from retiring gear via form manipulation
            if not current_user.is_admin_or_manager and new_gear_status == 'RETIRED':
                new_gear_status = CONDITION_AVAILABLE
            
            tx.condition_in = condition_in
            tx.actual_return = datetime.utcnow()
            tx.status = TX_COMPLETED
            
            old_status = tx.gear.condition_status
            tx.gear.condition_status = new_gear_status
            
            log_audit(tx.gear.id, 'CHECKIN', old_val=old_status, new_val=new_gear_status)
            db.session.commit()
            
            flash(f'Successfully checked in {tx.gear.name}', 'success')
            return redirect(url_for('dashboard'))
            
        return render_template('checkin.html', tx=tx)

    # --- AUDIT & ALERTS ---
    @app.route('/audit')
    @login_required
    @admin_required
    def audit_log():
        logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
        return render_template('audit.html', logs=logs)

    @app.route('/alerts')
    @login_required
    @admin_required
    def safety_alerts():
        # Items in maintenance
        maintenance_items = GearItem.query.filter_by(condition_status=CONDITION_MAINTENANCE).all()
        # In a real system, compute manufacturing expiration here.
        # For MVP, we'll just show maintenance ones.
        return render_template('alerts.html', maintenance=maintenance_items)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
