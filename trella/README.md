# Trello Board Module for Staff Scheduler

A Trello-like Kanban board module for your Staff Scheduler application with full license integration.

## Features

- **Kanban Boards**: Create multiple boards with customizable backgrounds
- **Lists & Cards**: Organize work with draggable lists and cards
- **Labels**: Color-coded labels for categorization
- **Due Dates**: Track deadlines with overdue indicators
- **Checklists**: Break down tasks into subtasks
- **Comments**: Discuss cards with team members
- **Members**: Assign cards to team members
- **Activity Log**: Track all changes on boards
- **Privacy**: Public and private boards
- **License Protected**: Integrates with your License Manager

## Installation

### 1. Copy the Module Files

Copy the `app/trello` folder into your staff scheduler's `app/` directory:

```
staff/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── trello/                 # ← Copy this folder
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── templates/
│   │       └── trello/
│   │           ├── index.html
│   │           ├── board.html
│   │           ├── create_board.html
│   │           └── edit_board.html
│   └── ...
```

### 2. Register the Blueprint

In your `app/__init__.py`, add the Trello blueprint:

```python
def create_app(config_class=Config):
    app = Flask(__name__)
    # ... existing code ...
    
    # Add Trello blueprint
    from app.trello import bp as trello_bp
    app.register_blueprint(trello_bp)
    
    # ... rest of code ...
```

### 3. Import the Models

In your main `app/models.py`, add at the bottom:

```python
# Import Trello models
from app.trello.models import (
    TrelloBoard, TrelloList, TrelloCard, TrelloLabel,
    TrelloComment, TrelloChecklist, TrelloChecklistItem,
    TrelloAttachment, TrelloActivity
)
```

Or alternatively, import them in `app/__init__.py` after db initialization:

```python
with app.app_context():
    # Import models to register them
    from app.trello import models as trello_models
    db.create_all()
```

### 4. Add Navigation Link

In your `base.html` template, add a link to the boards in your sidebar navigation:

```html
<!-- Add in the navigation section -->
<a href="{{ url_for('trello.index') }}" class="flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 {% if 'trello' in request.endpoint %}bg-{{ primary_color }}-500/10 text-{{ primary_color }}-400 border border-{{ primary_color }}-500/20{% else %}text-gray-400 hover:bg-dark-700/50 hover:text-white{% endif %}">
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2"/>
    </svg>
    <span class="font-medium">Boards</span>
</a>
```

### 5. Add Permission (Optional)

If using permission-based access, add to your permissions seed:

```python
# In app/__init__.py seed_data() function
default_permissions = [
    # ... existing permissions ...
    ('boards.view', 'View Boards', 'View Kanban boards', 'boards'),
    ('boards.create', 'Create Boards', 'Create new boards', 'boards'),
    ('boards.manage', 'Manage Boards', 'Edit and delete boards', 'boards'),
]
```

### 6. Run Database Migration

Restart your application to create the new tables:

```bash
# If using Flask-Migrate
flask db migrate -m "Add Trello boards"
flask db upgrade

# Or simply restart (SQLite auto-creates)
python run.py
```

## License Integration

### Protecting the Module

To protect the Trello module with your License Manager, add this check to the blueprint:

In `app/trello/__init__.py`, add at the top:

```python
from functools import wraps
from flask import flash, redirect, url_for
from app.models import Settings

def require_feature(feature_name):
    """Decorator to check if a feature is enabled via license"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check license feature
            # This integrates with your License Manager
            license_features = Settings.get('license_features', '').split(',')
            if feature_name not in license_features:
                flash('This feature requires a higher license tier.', 'error')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

Then use it on routes:

```python
@bp.route('/')
@login_required
@require_feature('boards')  # Requires 'boards' feature in license
def index():
    # ...
```

### Tier-Based Features

You can also add tier-based restrictions:

```python
# In board.html template
{% if current_user.has_feature('advanced_boards') %}
    <!-- Show advanced features -->
{% endif %}
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/trello/` | List all boards |
| GET/POST | `/trello/create` | Create new board |
| GET | `/trello/board/<id>` | View board |
| GET/POST | `/trello/board/<id>/edit` | Edit board settings |
| POST | `/trello/board/<id>/archive` | Archive board |
| POST | `/trello/board/<id>/delete` | Delete board |
| POST | `/trello/board/<id>/list/create` | Create list |
| POST | `/trello/list/<id>/rename` | Rename list |
| POST | `/trello/list/<id>/archive` | Archive list |
| POST | `/trello/list/<id>/card/create` | Create card |
| GET | `/trello/card/<id>` | Get card details (JSON) |
| POST | `/trello/card/<id>/update` | Update card |
| POST | `/trello/card/<id>/move` | Move card |
| POST | `/trello/card/<id>/archive` | Archive card |
| POST | `/trello/card/<id>/delete` | Delete card |
| POST | `/trello/card/<id>/comment` | Add comment |
| POST | `/trello/card/<id>/checklist` | Add checklist |
| POST | `/trello/checklist/<id>/item` | Add checklist item |
| POST | `/trello/checklist/item/<id>/toggle` | Toggle item |
| GET | `/trello/board/<id>/activity` | Get activity log |

## Database Schema

```
trello_boards
├── id (PK)
├── name
├── description
├── background_color
├── is_private
├── is_archived
├── created_by (FK → users)
├── created_at
└── updated_at

trello_lists
├── id (PK)
├── board_id (FK → trello_boards)
├── name
├── position
├── is_archived
└── created_at

trello_cards
├── id (PK)
├── list_id (FK → trello_lists)
├── title
├── description
├── position
├── due_date
├── due_complete
├── is_archived
├── cover_color
├── created_by (FK → users)
├── created_at
└── updated_at

trello_labels
├── id (PK)
├── board_id (FK → trello_boards)
├── name
└── color

trello_comments
├── id (PK)
├── card_id (FK → trello_cards)
├── user_id (FK → users)
├── content
├── created_at
└── updated_at

trello_checklists
├── id (PK)
├── card_id (FK → trello_cards)
├── name
└── position

trello_checklist_items
├── id (PK)
├── checklist_id (FK → trello_checklists)
├── content
├── is_complete
├── position
├── completed_by (FK → users)
└── completed_at

trello_activities
├── id (PK)
├── board_id (FK → trello_boards)
├── user_id (FK → users)
├── action
├── target_type
├── target_id
├── details (JSON)
└── created_at

board_members (Association Table)
├── board_id (PK, FK)
├── user_id (PK, FK)
├── role
└── added_at

card_labels (Association Table)
├── card_id (PK, FK)
└── label_id (PK, FK)

card_members (Association Table)
├── card_id (PK, FK)
└── user_id (PK, FK)
```

## Customization

### Adding Custom Colors

Edit the background color options in `create_board.html` and `edit_board.html`:

```html
{% for color in ['slate', 'gray', 'red', 'orange', 'amber', 'yellow', 'lime', 'green', 'emerald', 'teal', 'cyan', 'sky', 'blue', 'indigo', 'violet', 'purple', 'fuchsia', 'pink', 'rose', 'custom1', 'custom2'] %}
```

### Adding Drag & Drop

For full drag-and-drop functionality, add SortableJS:

```html
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>
<script>
document.querySelectorAll('.cards-container').forEach(container => {
    new Sortable(container, {
        group: 'cards',
        animation: 150,
        onEnd: async function(evt) {
            const cardId = evt.item.dataset.cardId;
            const newListId = evt.to.dataset.listId;
            const newPosition = evt.newIndex;
            
            await fetch(`/trello/card/${cardId}/move`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    list_id: parseInt(newListId),
                    position: newPosition
                })
            });
        }
    });
});
</script>
```

## License

This module is part of the Staff Scheduler and is protected by the License Manager system.

---

For support, contact your system administrator.
