from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect

cache = Cache()
csrf = CSRFProtect()
