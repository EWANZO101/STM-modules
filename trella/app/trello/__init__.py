"""
Trello-like Board Blueprint
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models import User, Settings
from .models import (
    TrelloBoard, TrelloList, TrelloCard, TrelloLabel,
    TrelloComment, TrelloChecklist, TrelloChecklistItem,
    TrelloAttachment, TrelloActivity, board_members
)

bp = Blueprint('trello', __name__, url_prefix='/trello', template_folder='templates')


def log_activity(board_id, action, target_type=None, target_id=None, details=None):
    """Log board activity"""
    activity = TrelloActivity(
        board_id=board_id,
        user_id=current_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details
    )
    db.session.add(activity)


def check_board_access(board, require_edit=False):
    """Check if current user can access the board"""
    if require_edit:
        return board.can_edit(current_user.id)
    return board.can_view(current_user.id)


# ══════════════════════════════════════════════════════════════════════════════
# BOARD ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@bp.route('/')
@login_required
def index():
    """List all boards"""
    # Get boards user has access to
    my_boards = TrelloBoard.query.filter_by(created_by=current_user.id, is_archived=False).all()
    member_boards = TrelloBoard.query.join(board_members).filter(
        board_members.c.user_id == current_user.id,
        TrelloBoard.is_archived == False
    ).all()
    public_boards = TrelloBoard.query.filter_by(is_private=False, is_archived=False).all()
    
    # Combine and deduplicate
    all_boards = list({b.id: b for b in my_boards + member_boards}.values())
    
    return render_template('trello/index.html',
        my_boards=my_boards,
        member_boards=[b for b in member_boards if b.created_by != current_user.id],
        public_boards=[b for b in public_boards if b not in all_boards]
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_board():
    """Create a new board"""
    if request.method == 'POST':
        board = TrelloBoard(
            name=request.form.get('name'),
            description=request.form.get('description'),
            background_color=request.form.get('background_color', 'slate'),
            is_private=request.form.get('is_private') == 'on',
            created_by=current_user.id
        )
        db.session.add(board)
        db.session.flush()
        
        # Add default labels
        default_labels = [
            ('', 'emerald'), ('', 'blue'), ('', 'purple'),
            ('', 'red'), ('', 'yellow'), ('', 'orange')
        ]
        for name, color in default_labels:
            db.session.add(TrelloLabel(board_id=board.id, name=name, color=color))
        
        # Add default lists
        default_lists = ['To Do', 'In Progress', 'Done']
        for i, name in enumerate(default_lists):
            db.session.add(TrelloList(board_id=board.id, name=name, position=i))
        
        log_activity(board.id, 'created_board', 'board', board.id)
        db.session.commit()
        
        flash(f'Board "{board.name}" created!', 'success')
        return redirect(url_for('trello.view_board', id=board.id))
    
    return render_template('trello/create_board.html')


@bp.route('/board/<int:id>')
@login_required
def view_board(id):
    """View a board with all lists and cards"""
    board = TrelloBoard.query.get_or_404(id)
    
    if not check_board_access(board):
        flash('You do not have access to this board.', 'error')
        return redirect(url_for('trello.index'))
    
    lists = TrelloList.query.filter_by(board_id=board.id, is_archived=False)\
                            .order_by(TrelloList.position).all()
    
    # Get all users for assignment
    users = User.query.filter_by(is_active=True).all()
    
    return render_template('trello/board.html',
        board=board,
        lists=lists,
        users=users,
        labels=board.labels.all()
    )


@bp.route('/board/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_board(id):
    """Edit board settings"""
    board = TrelloBoard.query.get_or_404(id)
    
    if not board.is_owner(current_user.id):
        flash('Only the board owner can edit settings.', 'error')
        return redirect(url_for('trello.view_board', id=id))
    
    if request.method == 'POST':
        board.name = request.form.get('name')
        board.description = request.form.get('description')
        board.background_color = request.form.get('background_color', 'slate')
        board.is_private = request.form.get('is_private') == 'on'
        
        log_activity(board.id, 'updated_board', 'board', board.id)
        db.session.commit()
        
        flash('Board updated!', 'success')
        return redirect(url_for('trello.view_board', id=id))
    
    return render_template('trello/edit_board.html', board=board)


@bp.route('/board/<int:id>/archive', methods=['POST'])
@login_required
def archive_board(id):
    """Archive a board"""
    board = TrelloBoard.query.get_or_404(id)
    
    if not board.is_owner(current_user.id):
        return jsonify({'error': 'Permission denied'}), 403
    
    board.is_archived = True
    log_activity(board.id, 'archived_board', 'board', board.id)
    db.session.commit()
    
    flash('Board archived.', 'info')
    return redirect(url_for('trello.index'))


@bp.route('/board/<int:id>/delete', methods=['POST'])
@login_required
def delete_board(id):
    """Delete a board permanently"""
    board = TrelloBoard.query.get_or_404(id)
    
    if not board.is_owner(current_user.id):
        flash('Only the board owner can delete it.', 'error')
        return redirect(url_for('trello.index'))
    
    name = board.name
    db.session.delete(board)
    db.session.commit()
    
    flash(f'Board "{name}" deleted.', 'success')
    return redirect(url_for('trello.index'))


# ══════════════════════════════════════════════════════════════════════════════
# LIST ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@bp.route('/board/<int:board_id>/list/create', methods=['POST'])
@login_required
def create_list(board_id):
    """Create a new list"""
    board = TrelloBoard.query.get_or_404(board_id)
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    # Get max position
    max_pos = db.session.query(db.func.max(TrelloList.position))\
                        .filter_by(board_id=board_id).scalar() or 0
    
    lst = TrelloList(
        board_id=board_id,
        name=request.form.get('name', 'New List'),
        position=max_pos + 1
    )
    db.session.add(lst)
    log_activity(board_id, 'created_list', 'list', lst.id, {'name': lst.name})
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'id': lst.id, 'name': lst.name})
    
    return redirect(url_for('trello.view_board', id=board_id))


@bp.route('/list/<int:id>/rename', methods=['POST'])
@login_required
def rename_list(id):
    """Rename a list"""
    lst = TrelloList.query.get_or_404(id)
    board = lst.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    old_name = lst.name
    lst.name = request.form.get('name', lst.name)
    log_activity(board.id, 'renamed_list', 'list', lst.id, 
                {'old_name': old_name, 'new_name': lst.name})
    db.session.commit()
    
    return jsonify({'success': True})


@bp.route('/list/<int:id>/archive', methods=['POST'])
@login_required
def archive_list(id):
    """Archive a list"""
    lst = TrelloList.query.get_or_404(id)
    board = lst.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    lst.is_archived = True
    log_activity(board.id, 'archived_list', 'list', lst.id, {'name': lst.name})
    db.session.commit()
    
    return jsonify({'success': True})


@bp.route('/list/<int:id>/move', methods=['POST'])
@login_required
def move_list(id):
    """Move list to new position"""
    lst = TrelloList.query.get_or_404(id)
    board = lst.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    new_position = request.json.get('position', 0)
    lst.position = new_position
    db.session.commit()
    
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════════════
# CARD ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@bp.route('/list/<int:list_id>/card/create', methods=['POST'])
@login_required
def create_card(list_id):
    """Create a new card"""
    lst = TrelloList.query.get_or_404(list_id)
    board = lst.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    # Get max position
    max_pos = db.session.query(db.func.max(TrelloCard.position))\
                        .filter_by(list_id=list_id).scalar() or 0
    
    card = TrelloCard(
        list_id=list_id,
        title=request.form.get('title', 'New Card'),
        position=max_pos + 1,
        created_by=current_user.id
    )
    db.session.add(card)
    log_activity(board.id, 'created_card', 'card', card.id, {'title': card.title})
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'id': card.id,
            'title': card.title,
            'list_id': list_id
        })
    
    return redirect(url_for('trello.view_board', id=board.id))


@bp.route('/card/<int:id>')
@login_required
def view_card(id):
    """View card details (modal data)"""
    card = TrelloCard.query.get_or_404(id)
    board = card.list.board
    
    if not check_board_access(board):
        return jsonify({'error': 'Permission denied'}), 403
    
    return jsonify({
        'id': card.id,
        'title': card.title,
        'description': card.description,
        'list_id': card.list_id,
        'list_name': card.list.name,
        'due_date': card.due_date.isoformat() if card.due_date else None,
        'due_complete': card.due_complete,
        'is_overdue': card.is_overdue,
        'cover_color': card.cover_color,
        'created_at': card.created_at.isoformat(),
        'labels': [{'id': l.id, 'name': l.name, 'color': l.color} for l in card.labels],
        'members': [{'id': m.id, 'name': m.name} for m in card.members],
        'comments': [{
            'id': c.id,
            'user': c.user.name,
            'content': c.content,
            'created_at': c.created_at.isoformat()
        } for c in card.comments.order_by(TrelloComment.created_at.desc())],
        'checklists': [{
            'id': cl.id,
            'name': cl.name,
            'items': [{
                'id': item.id,
                'content': item.content,
                'is_complete': item.is_complete
            } for item in cl.items]
        } for cl in card.checklists],
        'checklist_progress': card.checklist_progress
    })


@bp.route('/card/<int:id>/update', methods=['POST'])
@login_required
def update_card(id):
    """Update card details"""
    card = TrelloCard.query.get_or_404(id)
    board = card.list.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.json or request.form
    
    if 'title' in data:
        card.title = data['title']
    if 'description' in data:
        card.description = data['description']
    if 'due_date' in data:
        if data['due_date']:
            card.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        else:
            card.due_date = None
    if 'due_complete' in data:
        card.due_complete = data['due_complete']
    if 'cover_color' in data:
        card.cover_color = data['cover_color']
    
    log_activity(board.id, 'updated_card', 'card', card.id, {'title': card.title})
    db.session.commit()
    
    return jsonify({'success': True})


@bp.route('/card/<int:id>/move', methods=['POST'])
@login_required
def move_card(id):
    """Move card to different list or position"""
    card = TrelloCard.query.get_or_404(id)
    board = card.list.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.json
    old_list = card.list.name
    
    if 'list_id' in data:
        new_list = TrelloList.query.get(data['list_id'])
        if new_list and new_list.board_id == board.id:
            card.list_id = new_list.id
            log_activity(board.id, 'moved_card', 'card', card.id, 
                        {'from': old_list, 'to': new_list.name})
    
    if 'position' in data:
        card.position = data['position']
    
    db.session.commit()
    
    return jsonify({'success': True})


@bp.route('/card/<int:id>/archive', methods=['POST'])
@login_required
def archive_card(id):
    """Archive a card"""
    card = TrelloCard.query.get_or_404(id)
    board = card.list.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    card.is_archived = True
    log_activity(board.id, 'archived_card', 'card', card.id, {'title': card.title})
    db.session.commit()
    
    return jsonify({'success': True})


@bp.route('/card/<int:id>/delete', methods=['POST'])
@login_required
def delete_card(id):
    """Delete a card permanently"""
    card = TrelloCard.query.get_or_404(id)
    board = card.list.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    title = card.title
    db.session.delete(card)
    log_activity(board.id, 'deleted_card', 'card', id, {'title': title})
    db.session.commit()
    
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════════════
# CARD MEMBERS & LABELS
# ══════════════════════════════════════════════════════════════════════════════

@bp.route('/card/<int:id>/members', methods=['POST'])
@login_required
def update_card_members(id):
    """Update card members"""
    card = TrelloCard.query.get_or_404(id)
    board = card.list.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    member_ids = request.json.get('member_ids', [])
    card.members = User.query.filter(User.id.in_(member_ids)).all()
    db.session.commit()
    
    return jsonify({'success': True})


@bp.route('/card/<int:id>/labels', methods=['POST'])
@login_required
def update_card_labels(id):
    """Update card labels"""
    card = TrelloCard.query.get_or_404(id)
    board = card.list.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    label_ids = request.json.get('label_ids', [])
    card.labels = TrelloLabel.query.filter(
        TrelloLabel.id.in_(label_ids),
        TrelloLabel.board_id == board.id
    ).all()
    db.session.commit()
    
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════════════
# COMMENTS
# ══════════════════════════════════════════════════════════════════════════════

@bp.route('/card/<int:card_id>/comment', methods=['POST'])
@login_required
def add_comment(card_id):
    """Add a comment to a card"""
    card = TrelloCard.query.get_or_404(card_id)
    board = card.list.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    content = request.json.get('content') or request.form.get('content')
    if not content:
        return jsonify({'error': 'Comment content required'}), 400
    
    comment = TrelloComment(
        card_id=card_id,
        user_id=current_user.id,
        content=content
    )
    db.session.add(comment)
    log_activity(board.id, 'added_comment', 'card', card_id)
    db.session.commit()
    
    return jsonify({
        'id': comment.id,
        'user': current_user.name,
        'content': comment.content,
        'created_at': comment.created_at.isoformat()
    })


@bp.route('/comment/<int:id>/delete', methods=['POST'])
@login_required
def delete_comment(id):
    """Delete a comment"""
    comment = TrelloComment.query.get_or_404(id)
    card = comment.card
    board = card.list.board
    
    # Only comment author or board owner can delete
    if comment.user_id != current_user.id and not board.is_owner(current_user.id):
        return jsonify({'error': 'Permission denied'}), 403
    
    db.session.delete(comment)
    db.session.commit()
    
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════════════
# CHECKLISTS
# ══════════════════════════════════════════════════════════════════════════════

@bp.route('/card/<int:card_id>/checklist', methods=['POST'])
@login_required
def add_checklist(card_id):
    """Add a checklist to a card"""
    card = TrelloCard.query.get_or_404(card_id)
    board = card.list.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    checklist = TrelloChecklist(
        card_id=card_id,
        name=request.json.get('name', 'Checklist')
    )
    db.session.add(checklist)
    db.session.commit()
    
    return jsonify({
        'id': checklist.id,
        'name': checklist.name
    })


@bp.route('/checklist/<int:id>/item', methods=['POST'])
@login_required
def add_checklist_item(id):
    """Add an item to a checklist"""
    checklist = TrelloChecklist.query.get_or_404(id)
    card = checklist.card
    board = card.list.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    item = TrelloChecklistItem(
        checklist_id=id,
        content=request.json.get('content', '')
    )
    db.session.add(item)
    db.session.commit()
    
    return jsonify({
        'id': item.id,
        'content': item.content,
        'is_complete': item.is_complete
    })


@bp.route('/checklist/item/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_checklist_item(id):
    """Toggle checklist item completion"""
    item = TrelloChecklistItem.query.get_or_404(id)
    card = item.checklist.card
    board = card.list.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    item.is_complete = not item.is_complete
    if item.is_complete:
        item.completed_by = current_user.id
        item.completed_at = datetime.utcnow()
    else:
        item.completed_by = None
        item.completed_at = None
    
    db.session.commit()
    
    return jsonify({
        'is_complete': item.is_complete,
        'checklist_progress': card.checklist_progress
    })


@bp.route('/checklist/<int:id>/delete', methods=['POST'])
@login_required
def delete_checklist(id):
    """Delete a checklist"""
    checklist = TrelloChecklist.query.get_or_404(id)
    card = checklist.card
    board = card.list.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    db.session.delete(checklist)
    db.session.commit()
    
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════════════
# LABELS MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@bp.route('/board/<int:board_id>/labels')
@login_required
def get_labels(board_id):
    """Get all labels for a board"""
    board = TrelloBoard.query.get_or_404(board_id)
    
    if not check_board_access(board):
        return jsonify({'error': 'Permission denied'}), 403
    
    labels = TrelloLabel.query.filter_by(board_id=board_id).all()
    
    return jsonify([{
        'id': l.id,
        'name': l.name,
        'color': l.color
    } for l in labels])


@bp.route('/board/<int:board_id>/label/create', methods=['POST'])
@login_required
def create_label(board_id):
    """Create a new label"""
    board = TrelloBoard.query.get_or_404(board_id)
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    label = TrelloLabel(
        board_id=board_id,
        name=request.json.get('name', ''),
        color=request.json.get('color', 'gray')
    )
    db.session.add(label)
    db.session.commit()
    
    return jsonify({
        'id': label.id,
        'name': label.name,
        'color': label.color
    })


@bp.route('/label/<int:id>/update', methods=['POST'])
@login_required
def update_label(id):
    """Update a label"""
    label = TrelloLabel.query.get_or_404(id)
    board = label.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    label.name = request.json.get('name', label.name)
    label.color = request.json.get('color', label.color)
    db.session.commit()
    
    return jsonify({'success': True})


@bp.route('/label/<int:id>/delete', methods=['POST'])
@login_required
def delete_label(id):
    """Delete a label"""
    label = TrelloLabel.query.get_or_404(id)
    board = label.board
    
    if not check_board_access(board, require_edit=True):
        return jsonify({'error': 'Permission denied'}), 403
    
    db.session.delete(label)
    db.session.commit()
    
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVITY LOG
# ══════════════════════════════════════════════════════════════════════════════

@bp.route('/board/<int:id>/activity')
@login_required
def board_activity(id):
    """Get board activity log"""
    board = TrelloBoard.query.get_or_404(id)
    
    if not check_board_access(board):
        return jsonify({'error': 'Permission denied'}), 403
    
    activities = TrelloActivity.query.filter_by(board_id=id)\
                                     .order_by(TrelloActivity.created_at.desc())\
                                     .limit(50).all()
    
    return jsonify([{
        'id': a.id,
        'user': a.user.name if a.user else 'System',
        'action': a.action,
        'target_type': a.target_type,
        'details': a.details,
        'created_at': a.created_at.isoformat()
    } for a in activities])


# ══════════════════════════════════════════════════════════════════════════════
# BOARD MEMBERS
# ══════════════════════════════════════════════════════════════════════════════

@bp.route('/board/<int:id>/members')
@login_required
def get_board_members(id):
    """Get board members"""
    board = TrelloBoard.query.get_or_404(id)
    
    if not check_board_access(board):
        return jsonify({'error': 'Permission denied'}), 403
    
    return jsonify([{
        'id': m.id,
        'name': m.name,
        'email': m.email,
        'role': board.get_member_role(m.id)
    } for m in board.members])


@bp.route('/board/<int:id>/member/add', methods=['POST'])
@login_required
def add_board_member(id):
    """Add a member to the board"""
    board = TrelloBoard.query.get_or_404(id)
    
    if not board.is_owner(current_user.id):
        return jsonify({'error': 'Permission denied'}), 403
    
    user_id = request.json.get('user_id')
    role = request.json.get('role', 'member')
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user not in board.members:
        stmt = board_members.insert().values(
            board_id=board.id,
            user_id=user.id,
            role=role
        )
        db.session.execute(stmt)
        db.session.commit()
    
    return jsonify({'success': True})


@bp.route('/board/<int:id>/member/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_board_member(id, user_id):
    """Remove a member from the board"""
    board = TrelloBoard.query.get_or_404(id)
    
    if not board.is_owner(current_user.id):
        return jsonify({'error': 'Permission denied'}), 403
    
    stmt = board_members.delete().where(
        board_members.c.board_id == board.id,
        board_members.c.user_id == user_id
    )
    db.session.execute(stmt)
    db.session.commit()
    
    return jsonify({'success': True})
