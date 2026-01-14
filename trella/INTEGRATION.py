"""
QUICK INTEGRATION GUIDE
=======================

This file shows exactly what to add to your Staff Scheduler to integrate the Trello board module.

1. ADD TO: app/__init__.py (in create_app function, after other blueprints)
"""

# ============================================================================
# STEP 1: Add to app/__init__.py
# ============================================================================

# Add this import at the top
from app.trello import bp as trello_bp

# Add this line in create_app() function, after other blueprint registrations:
app.register_blueprint(trello_bp)

# Example location in create_app():
"""
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # ... existing blueprints ...
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # ADD THIS LINE:
    from app.trello import bp as trello_bp
    app.register_blueprint(trello_bp)
    
    # ... rest of code ...
"""


# ============================================================================
# STEP 2: Add navigation link to base.html
# ============================================================================

# Add this in your sidebar navigation, after other menu items:

NAVIGATION_HTML = '''
<!-- Boards - Add this in your sidebar navigation -->
<a href="{{ url_for('trello.index') }}" class="flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 {% if 'trello' in request.endpoint %}bg-{{ primary_color }}-500/10 text-{{ primary_color }}-400 border border-{{ primary_color }}-500/20{% else %}text-gray-400 hover:bg-dark-700/50 hover:text-white{% endif %}">
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2"/>
    </svg>
    <span class="font-medium">Boards</span>
</a>
'''


# ============================================================================
# STEP 3: Add permission check (optional - if using license system)
# ============================================================================

# Add this to your app/trello/__init__.py at the top:

LICENSE_CHECK_CODE = '''
from app.models import Settings

def check_boards_license():
    """Check if boards feature is enabled in license"""
    # Get license features from settings
    features_str = Settings.get('license_features', '')
    if not features_str:
        return True  # Allow if no license restrictions
    
    features = [f.strip() for f in features_str.split(',')]
    return 'boards' in features or 'all' in features

# Then add to your routes:
@bp.before_request
def check_license():
    if not check_boards_license():
        from flask import flash, redirect, url_for
        flash('Boards feature requires a higher license tier.', 'error')
        return redirect(url_for('admin.dashboard'))
'''


# ============================================================================
# STEP 4: Import models (add to main app/models.py or let auto-create)
# ============================================================================

# Option A: Add at bottom of app/models.py:
MODELS_IMPORT = '''
# Import Trello models (at bottom of models.py)
from app.trello.models import (
    TrelloBoard, TrelloList, TrelloCard, TrelloLabel,
    TrelloComment, TrelloChecklist, TrelloChecklistItem,
    TrelloAttachment, TrelloActivity
)
'''

# Option B: Just restart - Flask-SQLAlchemy will auto-create tables


# ============================================================================
# STEP 5: Add permissions seed (optional)
# ============================================================================

PERMISSIONS_SEED = '''
# Add to seed_data() function in app/__init__.py:
default_permissions = [
    # ... existing permissions ...
    
    # Boards permissions
    ('boards.view', 'View Boards', 'View Kanban boards', 'boards'),
    ('boards.create', 'Create Boards', 'Create new boards', 'boards'),
    ('boards.manage', 'Manage Boards', 'Edit and delete boards', 'boards'),
]
'''


# ============================================================================
# COMPLETE EXAMPLE: Updated __init__.py
# ============================================================================

COMPLETE_INIT_EXAMPLE = '''
"""
Staff Scheduler - Application Factory (with Trello Module)
"""
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Context processor for settings
    @app.context_processor
    def inject_settings():
        from app.models import Settings
        return {
            'site_name': Settings.get('site_name', 'Staff Scheduler'),
            'primary_color': Settings.get('primary_color', 'emerald'),
        }
    
    # ===== BLUEPRINTS =====
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # ===== ADD TRELLO MODULE =====
    from app.trello import bp as trello_bp
    app.register_blueprint(trello_bp)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app
'''

print("Integration guide loaded. Copy the relevant sections to your files.")
