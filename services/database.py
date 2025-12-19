"""
Database service for initialization and setup.
"""
from config import application, db
from models import User, CustomerNameCounter


def init_database():
    """Initialize database with tables and default users"""
    try:
        with application.app_context():
            # Create all tables
            db.create_all()

            # Check if admin user exists, if not create it
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User(
                    username='admin',
                    name='Administrator',
                    is_admin=True
                )
                admin_user.set_password('admin@796!')
                db.session.add(admin_user)
            else:
                if not admin_user.is_admin:
                    print(f"⚠️  Admin user found but is_admin was False. Fixing...")
                    admin_user.is_admin = True
                    db.session.commit()
                    print(f"✅ Admin user is_admin field updated to True")

            # Create default users if they don't exist
            default_users = [
                {'username': 'hemlata', 'name': 'Hemlata', 'password': 'hemlata123'},
                {'username': 'sneha', 'name': 'Sneha', 'password': 'sneha123'}
            ]

            for user_data in default_users:
                existing_user = User.query.filter_by(username=user_data['username']).first()
                if not existing_user:
                    new_user = User(
                        username=user_data['username'],
                        name=user_data['name'],
                        is_admin=False
                    )
                    new_user.set_password(user_data['password'])
                    db.session.add(new_user)

            # Initialize customer name counter if it doesn't exist
            counter = CustomerNameCounter.query.first()
            if not counter:
                counter = CustomerNameCounter(counter=0)
                db.session.add(counter)
                print("✅ Customer name counter initialized")

            db.session.commit()
            print("Database initialized successfully")

    except Exception as e:
        print(f"Database initialization error: {e}")
        db.session.rollback()

