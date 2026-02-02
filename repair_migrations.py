import os
import sys
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from flask import Flask
from models import db
from dotenv import load_dotenv

load_dotenv()

def repair():
    app = Flask(__name__)
    # Try multiple common environment variables for DB URL
    db_uri = os.environ.get('SQLALCHEMY_DATABASE_URI') or os.environ.get('DATABASE_URL')
    
    if not db_uri:
        # Fallback to sqlite for local dev if needed, but in prod we expect a URI
        basedir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(basedir, 'db.sqlite3')
        db_uri = f'sqlite:///{db_path}'
        print(f"Warning: No database URI found in environment. Using fallback: {db_uri}")
    else:
        # Hide password in logs
        masked_uri = db_uri.split('@')[-1] if '@' in db_uri else db_uri
        print(f"Using database URI: ...@{masked_uri}")

    if db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)

    with app.app_context():
        engine = db.engine
        print(f"Connecting to engine...")
        try:
            with engine.connect() as connection:
                print("Connection successful.")
                # Check if alembic_version table exists
                # Different query for Postgres vs SQLite
                if 'postgresql' in db_uri:
                    result = connection.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE tablename = 'alembic_version'"))
                else:
                    result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"))
                
                table_exists = result.first()

                if not table_exists:
                    print("No alembic_version table found. Skipping repair.")
                    return

                # Get current version from DB
                result = connection.execute(text("SELECT version_num FROM alembic_version"))
                row = result.first()
                if not row:
                    print("alembic_version table is empty. Skipping repair.")
                    return
                
                current_db_version = row[0]
                print(f"Current DB version: {current_db_version}")

                # Check if this version exists in migrations/versions
                migrations_dir = os.path.join(os.getcwd(), 'migrations')
                script = ScriptDirectory.from_config_directory(migrations_dir)
                
                try:
                    script.get_revision(current_db_version)
                    print(f"Revision {current_db_version} found locally. No repair needed.")
                except Exception:
                    print(f"Revision {current_db_version} NOT found locally! Repairing...")
                    
                    # Find the base migration (the one with down_revision = None)
                    all_revisions = script.get_all_revisions()
                    new_base = None
                    for rev in all_revisions:
                        if rev.down_revision is None:
                            new_base = rev.revision
                            break
                    
                    if not new_base:
                        print("Could not find a base migration locally. Cannot repair.")
                        return

                    print(f"Stamping database to {new_base}...")
                    
                    # Update the version in the DB manually
                    try:
                        connection.execute(text("UPDATE alembic_version SET version_num = :new_base"), {"new_base": new_base})
                        connection.commit()
                        print(f"Successfully stamped DB to {new_base}")
                    except Exception as commit_err:
                        print(f"Commit/Update might have failed or already applied: {commit_err}")
                        pass

        except Exception as e:
            print(f"Error during repair: {e}")
            # Don't exit with error, let the main entrypoint try to handle it
            pass

if __name__ == "__main__":
    repair()