import os
import sys
from alembic.script import ScriptDirectory
from alembic.config import Config
from sqlalchemy import text, create_engine, inspect
from app import app
from models import db

def masked_url(url):
    if not url: return "None"
    if '@' in url:
        return "...@" + url.split('@')[-1]
    return url

def repair():
    print("Starting repair_migrations.py...")
    
    with app.app_context():
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        
        if not db_uri or 'sqlite' in db_uri:
            alt_uri = os.environ.get('SQLALCHEMY_DATABASE_URI') or os.environ.get('DATABASE_URL')
            if alt_uri and 'sqlite' not in alt_uri:
                db_uri = alt_uri
        
        if db_uri and db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)
        
        print(f"Repairing migrations using database URI: {masked_url(db_uri)}")

        if not db_uri:
            print("No database URI found. Cannot proceed with repair.")
            return

        try:
            engine = create_engine(db_uri)
            with engine.connect() as connection:
                print("Connection to database successful.")
                
                # 1. Handle Migration Revision Repair
                try:
                    result = connection.execute(text("SELECT version_num FROM alembic_version"))
                    row = result.first()
                    if not row:
                        print("alembic_version table is empty.")
                        current_db_version = None
                    else:
                        current_db_version = row[0]
                        print(f"Current DB version in database: {current_db_version}")
                except Exception:
                    print("alembic_version table not found. Might be a fresh DB.")
                    current_db_version = None

                migrations_dir = os.path.join(os.getcwd(), 'migrations')
                alembic_cfg = Config()
                alembic_cfg.set_main_option("script_location", migrations_dir)
                script = ScriptDirectory.from_config(alembic_cfg)
                
                needs_stamp = False
                new_base = None
                # Find the baseline migration
                for rev in script.walk_revisions():
                    if rev.down_revision is None:
                        new_base = rev.revision

                if current_db_version:
                    try:
                        script.get_revision(current_db_version)
                    except Exception:
                        print(f"Revision {current_db_version} NOT found locally! Repairing revision state...")
                        needs_stamp = True
                
                if needs_stamp and new_base:
                    print(f"Stamping database to {new_base}...")
                    connection.execute(text("UPDATE alembic_version SET version_num = :new_base"), {"new_base": new_base})
                    try: connection.commit()
                    except: pass

                # 2. Handle Schema Debt (Missing Columns)
                # We know at least 'user' table is missing columns from the new baseline
                print("Checking for missing columns in 'user' table...")
                inspector = inspect(engine)
                columns = [c['name'] for c in inspector.get_columns('user')]
                
                # List of columns that were in fdbb13ae7f30 but might be missing from old DB
                expected_user_columns = {
                    'enable_vim_mode': 'BOOLEAN DEFAULT FALSE',
                    'is_verified': 'BOOLEAN DEFAULT FALSE',
                    'auto_select_priority': 'BOOLEAN DEFAULT FALSE',
                    'notify_pomodoro': 'BOOLEAN DEFAULT TRUE',
                    'notify_event_start': 'BOOLEAN DEFAULT TRUE',
                    'event_notify_minutes': 'INTEGER DEFAULT 30',
                    'accent_color': 'VARCHAR(20) DEFAULT \'indigo\'',
                    'auto_start_break': 'BOOLEAN DEFAULT FALSE',
                    'auto_start_focus': 'BOOLEAN DEFAULT FALSE'
                }
                
                for col_name, col_type in expected_user_columns.items():
                    if col_name not in columns:
                        print(f"Adding missing column 'user.{col_name}'...")
                        try:
                            connection.execute(text(f"ALTER TABLE \"user\" ADD COLUMN {col_name} {col_type}"))
                            try: connection.commit()
                            except: pass
                            print(f"Successfully added {col_name}")
                        except Exception as col_err:
                            print(f"Could not add {col_name}: {col_err}")

                # Also check 'event' table if it exists
                if 'event' in inspector.get_table_names():
                    event_cols = [c['name'] for c in inspector.get_columns('event')]
                    if 'recurrence_days' not in event_cols:
                        print("Adding missing column 'event.recurrence_days'...")
                        connection.execute(text("ALTER TABLE event ADD COLUMN recurrence_days VARCHAR(50)"))
                        try: connection.commit()
                        except: pass

        except Exception as e:
            print(f"Error during repair: {e}")
            pass

if __name__ == "__main__":
    repair()
