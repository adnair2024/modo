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

def get_sql_type(column):
    from sqlalchemy.sql import sqltypes
    t = column.type
    if isinstance(t, sqltypes.Boolean): return "BOOLEAN"
    elif isinstance(t, sqltypes.DateTime): return "TIMESTAMP"
    elif isinstance(t, sqltypes.Date): return "DATE"
    elif isinstance(t, sqltypes.Integer): return "INTEGER"
    elif isinstance(t, sqltypes.String): return f"VARCHAR({t.length})"
    elif isinstance(t, sqltypes.Text): return "TEXT"
    return str(t)

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

        try:
            engine = create_engine(db_uri)
            with engine.connect() as connection:
                print("Connection to database successful.")
                
                # 1. Revision Repair
                try:
                    result = connection.execute(text("SELECT version_num FROM alembic_version"))
                    row = result.first()
                    current_db_version = row[0] if row else None
                except Exception:
                    current_db_version = None

                migrations_dir = os.path.join(os.getcwd(), 'migrations')
                alembic_cfg = Config()
                alembic_cfg.set_main_option("script_location", migrations_dir)
                script = ScriptDirectory.from_config(alembic_cfg)
                
                new_base = None
                for rev in script.walk_revisions():
                    if rev.down_revision is None:
                        new_base = rev.revision

                if current_db_version:
                    try:
                        script.get_revision(current_db_version)
                    except Exception:
                        print(f"Revision {current_db_version} NOT found locally! Repairing...")
                        if new_base:
                            connection.execute(text("UPDATE alembic_version SET version_num = :new_base"), {"new_base": new_base})
                            try: connection.commit()
                            except: pass

                # 2. Table and Column Sync
                print("Syncing schema: checking for missing tables and columns...")
                inspector = inspect(engine)
                existing_tables = inspector.get_table_names()
                
                # Create missing tables
                for table_name in db.metadata.tables:
                    if table_name not in existing_tables:
                        print(f"Table '{table_name}' is missing. Creating...")
                        try:
                            # We use create_all but only for the specific table to be safe
                            db.metadata.tables[table_name].create(engine)
                            print(f"Successfully created table {table_name}")
                        except Exception as e:
                            print(f"Error creating table {table_name}: {e}")
                    else:
                        # Check for missing columns in existing tables
                        existing_cols = [c['name'] for c in inspector.get_columns(table_name)]
                        table_obj = db.metadata.tables[table_name]
                        for col_name, col_obj in table_obj.columns.items():
                            if col_name not in existing_cols:
                                print(f"Adding missing column '{table_name}.{col_name}'...")
                                sql_type = get_sql_type(col_obj)
                                default_clause = ""
                                if col_obj.default is not None and hasattr(col_obj.default, 'arg'):
                                    if isinstance(col_obj.default.arg, bool):
                                        default_clause = f" DEFAULT {'TRUE' if col_obj.default.arg else 'FALSE'}"
                                    elif isinstance(col_obj.default.arg, (int, float, str)):
                                        default_clause = f" DEFAULT {repr(col_obj.default.arg)}"

                                safe_table_name = f'"{table_name}"' if table_name == 'user' else table_name
                                try:
                                    connection.execute(text(f"ALTER TABLE {safe_table_name} ADD COLUMN {col_name} {sql_type}{default_clause}"))
                                    try: connection.commit()
                                    except: pass
                                    print(f"Successfully added {col_name} to {table_name}")
                                except Exception as col_err:
                                    print(f"Could not add {col_name} to {table_name}: {col_err}")

        except Exception as e:
            print(f"Error during repair: {e}")
            pass

if __name__ == "__main__":
    repair()
