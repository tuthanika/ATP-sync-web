import os
import sys
import time
import logging
from datetime import datetime

# Đặt múi giờ
os.environ['TZ'] = 'Asia/Shanghai'
if hasattr(time, 'tzset'):
    time.tzset()

# Thêm thư mục hiện tại vàoPYTHONPATH
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Định cấu hình nhật ký vào bảng điều khiển
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Thông tin khởi động đầu ra
print(f"Trình thông dịch Python: {sys.executable}")
print(f"Thư mục làm việc hiện tại: {os.getcwd()}")
print(f"Thời gian hiện tại: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Cài đặt múi giờ: {os.environ['TZ']}")

# Nhập các chức năng nhà máy ứng dụng
from app import create_app

# Tạo một phiên bản ứng dụng
app = create_app()

# Thông tin ứng dụng
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
    # Đọc cấu hình cổng，Nếu không, hãy sử dụng cổng mặc định5000
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"\nBắt đầu ứng dụng  Flask: http://localhost:{port}")
    print(f"Chế độ gỡ lỗi: {'Mở' if debug else 'Đóng'}")
    
    # Bắt đầu ứng dụng
    app.run(debug=debug, host='0.0.0.0', port=port) 