import os
import sys
import logging
import time

# Đặt các biến môi trường
os.environ['TZ'] = 'Asia/Shanghai'
if hasattr(time, 'tzset'):
    time.tzset()

# Thiết lập đường dẫn Python
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Tạo một phiên bản ứng dụng
from app import create_app
application = app = create_app()

# Thông tin môi trường ứng dụng
env = os.environ.get('FLASK_ENV', 'production')
port = int(os.environ.get('PORT', 5000))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port) 