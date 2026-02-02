import os
import sys
from alembic.script import ScriptDirectory
from sqlalchemy import text, create_engine
from app import app
from models import db

def masked_url(url):
    if not url: return "None"
    if '@' in url:
        # Mask everything before @ to hide password
        return "...@" + url.split('@')[-1]
    return url

def repair():
    print("Starting repair_migrations.py...")
    
    with app.app_context():
        # Get URI from Flask config
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        
        # If it's default sqlite or missing, try environment variables directly
        # Some platforms might use DATABASE_URL while app expects SQLALCHEMY_DATABASE_URI
        if not db_uri or 'sqlite' in db_uri:
            alt_uri = os.environ.get('SQLALCHEMY_DATABASE_URI') or os.environ.get('DATABASE_URL')
            if alt_uri and 'sqlite' not in alt_uri:
                print(f"Flask config URI was {masked_url(db_uri)}, but found non-sqlite environment URI.")
                db_uri = alt_uri
        
        # Normalize postgres protocol for SQLAlchemy 1.4+
        if db_uri and db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)
        
        print(f"Repairing migrations using database URI: {masked_url(db_uri)}")

        if not db_uri:
            print("No database URI found. Cannot proceed with repair.")
            return

        try:
            # Create a dedicated engine for repair to avoid any session/transaction conflicts
            engine = create_engine(db_uri)
            with engine.connect() as connection:
                print("Connection to database successful.")
                
                # Check for alembic_version table
                # We try a simple select first
                try:
                    result = connection.execute(text("SELECT version_num FROM alembic_version"))
                    row = result.first()
                except Exception:
                    print("alembic_version table not found or error accessing it. Skipping repair.")
                    return

                if not row:
                    print("alembic_version table is empty. Skipping repair.")
                    return
                
                current_db_version = row[0]
                print(f"Current DB version in database: {current_db_version}")

                # Check if this version exists in migrations/versions
                migrations_dir = os.path.join(os.getcwd(), 'migrations')
                if not os.path.exists(migrations_dir):
                    print(f"Migrations directory not found at {migrations_dir}")
                    return

                script = ScriptDirectory.from_config_directory(migrations_dir)
                
                try:
                    rev = script.get_revision(current_db_version)
                    if rev:
                        print(f"Revision {current_db_version} found locally. No repair needed.")
                        return
                except Exception:
                    print(f"Revision {current_db_version} NOT found locally! This indicates a migration purge.")
                    
                    # Find the baseline migration (the one with down_revision = None)
                    new_base = None
                    # walk_revisions yields from head down to base
                    for rev in script.walk_revisions():
                        if rev.down_revision is None:
                            new_base = rev.revision
                            # We found a base, but keep going to find the absolute root if there are branches
                    
                    if not new_base:
                        print("Could not find a base migration locally. Cannot repair.")
                        return

                    print(f"Stamping database from {current_db_version} to {new_base}...")
                    
                    # Update the version in the DB manually
                    # Using connection.execute and connection.commit() for maximum compatibility
                    connection.execute(text("UPDATE alembic_version SET version_num = :new_base"), {"new_base": new_base})
                    
                    # SQLAlchemy 2.0+ requires explicit commit on the connection if not in autocommit mode
                    try:
                        # For engines that support it
                        connection.commit()
                    except AttributeError:
                        # For older SQLAlchemy or specific drivers
                        pass
                        
                    print(f"Successfully stamped DB to {new_base}")

        except Exception as e:
            print(f"Error during repair: {e}")
            # We don't exit with error code because we want flask db upgrade to try anyway
            pass

if __name__ == "__main__":
    repair()
