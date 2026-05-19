import sys
import os

# PythonAnywhere 경로 설정 — 본인 아이디로 변경
project_home = '/home/본인아이디/seat-loader'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

from main import app as application
