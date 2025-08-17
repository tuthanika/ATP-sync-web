#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Các tập tin khởi động hợp nhất
Hỗ trợ ba chế độ khởi động：
1. Chạy trực tiếp: python startup.py
2. FlaskMáy chủ phát triển: FLASK_APP=startup flask run
3. WSGImáy chủ: sử dụng application Sự vật
"""

import os
import sys
import time
import logging
from datetime import datetime

# Đặt múi giờ
# os.environ['TZ'] = 'Asia/Shanghai'
# if hasattr(time, 'tzset'):
#     time.tzset()

# Thêm thư mục hiện tại vàoPYTHONPATH
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Nhật ký cấu hình
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Nhập các chức năng nhà máy ứng dụng
from app import create_app

# Tạo một phiên bản ứng dụng
application = app = create_app()

def print_app_info():
    """In thông tin ứng dụng"""
    print(f"Trình thông dịch Python: {sys.executable}")
    print(f"Thư mục làm việc hiện tại: {os.getcwd()}")
    print(f"Thời gian hiện tại: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    # print(f"Cài đặt múi giờ: {os.environ['TZ']}")
    
    with app.app_context():
        print("\n===== Thông tin cấu hình ứng dụng =====")
        print(f"SECRET_KEY: {'*' * 8}")
        print(f"DEBUG: {app.config.get('DEBUG')}")
        
        # Kiểm tra trình quản lý đồng bộ hóa
        if 'SYNC_MANAGER' in app.config:
            sync_manager = app.config['SYNC_MANAGER']
            print("\n===== Thông tin nhiệm vụ của người lập lịch =====")
            jobs = sync_manager.scheduler.get_jobs()
            print(f"Bộ lập lịch có {len(jobs)} nhiệm vụ:")
            
            for job in jobs:
                job_id = job.id
                next_run = job.next_run_time
                print(f" - Nhiệm vụ: {job_id}, Chạy tiếp theo: {next_run}")
        else:
            print("Trình quản lý đồng bộ hóa không được khởi tạo！")

if __name__ == '__main__':
    # Đọc cấu hình biến môi trường
    port = int(os.environ.get('FLASK_PORT', os.environ.get('PORT', 5000)))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # In thông tin ứng dụng
    print_app_info()
    
    print(f"\nBắt đầu ứng dụng  Flask: http://localhost:{port}")
    print(f"Chế độ gỡ lỗi: {'Mở' if debug else 'Đóng'}")
    
    # Bắt đầu ứng dụng
    app.run(debug=debug, host='0.0.0.0', port=port) 