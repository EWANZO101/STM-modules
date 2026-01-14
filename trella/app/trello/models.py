"""
Trello-like Board Models
"""
from datetime import datetime
from app import db


# Association tables
board_members = db.Table('board_members',
    db.Column('board_id', db.Integer, db.ForeignKey('trello_boards.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role', db.String(20), default='member'),  # owner, admin, member, viewer
    db.Column('added_at', db.DateTime, default=datetime.utcnow)
)

card_labels = db.Table('card_labels',
    db.Column('card_id', db.Integer, db.ForeignKey('trello_cards.id'), primary_key=True),
    db.Column('label_id', db.Integer, db.ForeignKey('trello_labels.id'), primary_key=True)
)

card_members = db.Table('card_members',
    db.Column('card_id', db.Integer, db.ForeignKey('trello_cards.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)


class TrelloBoard(db.Model):
    """Trello-style board"""
    __tablename__ = 'trello_boards'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    background_color = db.Column(db.String(20), default='slate')  # Tailwind color
    background_image = db.Column(db.String(255))
    is_private = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lists = db.relationship('TrelloList', backref='board', lazy='dynamic', 
                           order_by='TrelloList.position', cascade='all, delete-orphan')
    labels = db.relationship('TrelloLabel', backref='board', lazy='dynamic',
                            cascade='all, delete-orphan')
    members = db.relationship('User', secondary=board_members, backref='trello_boards')
    activities = db.relationship('TrelloActivity', backref='board', lazy='dynamic',
                                cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def get_member_role(self, user_id):
        """Get a user's role on this board"""
        result = db.session.execute(
            board_members.select().where(
                board_members.c.board_id == self.id,
                board_members.c.user_id == user_id
            )
        ).first()
        return result.role if result else None
    
    def is_owner(self, user_id):
        return self.created_by == user_id or self.get_member_role(user_id) == 'owner'
    
    def can_edit(self, user_id):
        role = self.get_member_role(user_id)
        return role in ['owner', 'admin', 'member'] or self.created_by == user_id
    
    def can_view(self, user_id):
        if not self.is_private:
            return True
        return user_id in [m.id for m in self.members] or self.created_by == user_id


class TrelloList(db.Model):
    """List within a board (column)"""
    __tablename__ = 'trello_lists'
    
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('trello_boards.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.Integer, default=0)
    is_archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    cards = db.relationship('TrelloCard', backref='list', lazy='dynamic',
                           order_by='TrelloCard.position', cascade='all, delete-orphan')


class TrelloCard(db.Model):
    """Card within a list"""
    __tablename__ = 'trello_cards'
    
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('trello_lists.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    position = db.Column(db.Integer, default=0)
    due_date = db.Column(db.DateTime)
    due_complete = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    cover_color = db.Column(db.String(20))
    cover_image = db.Column(db.String(255))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    labels = db.relationship('TrelloLabel', secondary=card_labels, backref='cards')
    members = db.relationship('User', secondary=card_members, backref='assigned_cards')
    comments = db.relationship('TrelloComment', backref='card', lazy='dynamic',
                              cascade='all, delete-orphan')
    checklists = db.relationship('TrelloChecklist', backref='card', lazy='dynamic',
                                cascade='all, delete-orphan')
    attachments = db.relationship('TrelloAttachment', backref='card', lazy='dynamic',
                                 cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])
    
    @property
    def is_overdue(self):
        if not self.due_date or self.due_complete:
            return False
        return datetime.utcnow() > self.due_date
    
    @property
    def checklist_progress(self):
        """Return (completed, total) checklist items"""
        total = 0
        completed = 0
        for checklist in self.checklists:
            for item in checklist.items:
                total += 1
                if item.is_complete:
                    completed += 1
        return (completed, total)


class TrelloLabel(db.Model):
    """Label for categorizing cards"""
    __tablename__ = 'trello_labels'
    
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('trello_boards.id'), nullable=False)
    name = db.Column(db.String(50))
    color = db.Column(db.String(20), nullable=False)  # emerald, blue, purple, red, yellow, etc.


class TrelloComment(db.Model):
    """Comment on a card"""
    __tablename__ = 'trello_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey('trello_cards.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User')


class TrelloChecklist(db.Model):
    """Checklist on a card"""
    __tablename__ = 'trello_checklists'
    
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey('trello_cards.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.Integer, default=0)
    
    items = db.relationship('TrelloChecklistItem', backref='checklist', lazy='dynamic',
                           cascade='all, delete-orphan', order_by='TrelloChecklistItem.position')


class TrelloChecklistItem(db.Model):
    """Item in a checklist"""
    __tablename__ = 'trello_checklist_items'
    
    id = db.Column(db.Integer, primary_key=True)
    checklist_id = db.Column(db.Integer, db.ForeignKey('trello_checklists.id'), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    is_complete = db.Column(db.Boolean, default=False)
    position = db.Column(db.Integer, default=0)
    completed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    completed_at = db.Column(db.DateTime)


class TrelloAttachment(db.Model):
    """Attachment on a card"""
    __tablename__ = 'trello_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey('trello_cards.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    filesize = db.Column(db.Integer)
    filetype = db.Column(db.String(50))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    uploader = db.relationship('User')


class TrelloActivity(db.Model):
    """Activity log for a board"""
    __tablename__ = 'trello_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('trello_boards.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50), nullable=False)  # created_card, moved_card, etc.
    target_type = db.Column(db.String(50))  # card, list, board
    target_id = db.Column(db.Integer)
    details = db.Column(db.JSON)  # Additional details as JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User')
