import sys
import os

# PythonAnywhere 경로 설정 (본인의 아이디로 변경될 예정)
# project_home = '/home/본인아이디/seat-loader'
# if project_home not in sys.path:
#     sys.path = [project_home] + sys.path

from main import app
from a2wsgi import ASGIMiddleware

# PythonAnywhere의 WSGI 서버가 인식할 수 있도록 FastAPI를 변환
application = ASGIMiddleware(app)
