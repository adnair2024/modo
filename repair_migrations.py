import os
import sys
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text, create_engine
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
                
                try:
                    result = connection.execute(text("SELECT version_num FROM alembic_version"))
                    row = result.first()
                except Exception:
                    print("alembic_version table not found. Skipping repair.")
                    return

                if not row:
                    print("alembic_version table is empty. Skipping repair.")
                    return
                
                current_db_version = row[0]
                print(f"Current DB version in database: {current_db_version}")

                # Correct way to load ScriptDirectory in Alembic 1.x
                migrations_dir = os.path.join(os.getcwd(), 'migrations')
                alembic_cfg = Config()
                alembic_cfg.set_main_option("script_location", migrations_dir)
                script = ScriptDirectory.from_config(alembic_cfg)
                
                try:
                    rev = script.get_revision(current_db_version)
                    if rev:
                        print(f"Revision {current_db_version} found locally. No repair needed.")
                        return
                except Exception:
                    print(f"Revision {current_db_version} NOT found locally! Repairing...")
                    
                    # Find the baseline migration (the one with down_revision = None)
                    new_base = None
                    for rev in script.walk_revisions():
                        if rev.down_revision is None:
                            new_base = rev.revision
                    
                    if not new_base:
                        print("Could not find a base migration locally. Cannot repair.")
                        return

                    print(f"Stamping database from {current_db_version} to {new_base}...")
                    
                    connection.execute(text("UPDATE alembic_version SET version_num = :new_base"), {"new_base": new_base})
                    
                    try:
                        connection.commit()
                    except AttributeError:
                        pass
                        
                    print(f"Successfully stamped DB to {new_base}")

        except Exception as e:
            print(f"Error during repair: {e}")
            pass

if __name__ == "__main__":
    repair()