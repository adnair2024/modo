import os
import sys
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from flask import Flask
from models import db

def repair():
    app = Flask(__name__)
    # Use the same DB URI as the app
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://localhost/modo')
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
    
    db.init_app(app)

    with app.app_context():
        engine = db.engine
        try:
            with engine.connect() as connection:
                # Check if alembic_version table exists
                result = connection.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE tablename = 'alembic_version'"))
                if not result.first():
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
                    
                    # Update the version in the DB manually to avoid Alembic's graph checks
                    connection.execute(text(f"UPDATE alembic_version SET version_num = '{new_base}'"))
                    connection.commit()
                    print(f"Successfully stamped DB to {new_base}")

        except Exception as e:
            print(f"Error during repair: {e}")
            # Don't exit with error, let the main entrypoint try to handle it
            pass

if __name__ == "__main__":
    repair()
