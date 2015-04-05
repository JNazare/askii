import sys
import os

# Activate your virtual env
activate_env=os.path.expanduser("/var/www/askii/askiienv/bin/activate_this.py")
execfile(activate_env, dict(__file__=activate_env))

sys.path.insert(0, '/var/www/askii')
from index import app as application

