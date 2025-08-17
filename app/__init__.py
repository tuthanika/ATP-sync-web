import os
import logging
from logging.handlers import TimedRotatingFileHandler
from flask import Flask, session, redirect, url_for, request
from app.routes import main_bp, api_bp, auth_bp
from app.utils.data_manager import DataManager
from functools import wraps

# Phiên bản ứng dụng toàn cầu, được bộ lập lịch sử dụng để truy cập khi không có ngữ cảnh
flask_app = None

def init_logger():
    """Định cấu hình logger"""
    # Nhận thư mục gốc hiện tại
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Đảm bảo thư mục nhật ký tồn tại
    log_dir = os.path.join(root_dir, 'data/log')
    os.makedirs(log_dir, exist_ok=True)
    
    # Đặt đường dẫn tệp nhật ký
    log_file = os.path.join(log_dir, 'alist_sync.log')
    
    # Tạo định dạng nhật ký
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Bộ xử lý tập tin - Xoay theo ngày
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Bộ xử lý giao diện điều khiển
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Định cấu hình logger gốc
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # Xóa bộ xử lý hiện có
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def create_app():
    """Tạo và định cấu hình ứng dụng"""
    global flask_app
    
    from flask import Flask
    import os
    
    # Tạo một phiên bản ứng dụng Flask
    app = Flask(__name__, static_folder='static')
    
    # Sử dụng cấu hình nội bộ thay vì nhập từ các mô -đun bên ngoài
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-key-for-alist-sync'
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # Thời gian hiệu lực phiên 24 Giờ
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Nhật ký khởi tạo
    logger = init_logger()
    app.logger = logger
    app.logger.info("Khởi tạo ứng dụng bắt đầu...")
    
    # Khởi tạo Trình quản lý dữ liệu
    data_manager = DataManager()
    app.config['DATA_MANAGER'] = data_manager
    
    # Khởi tạo ứng dụng(Bao gồm cả lịch trình)
    from app.app import init_app
    init_app(app)
    
    # Đăng ký một kế hoạch chi tiết
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Thêm đăng nhập Kiểm tra phần mềm trung gian
    @app.before_request
    def check_login():
        # Xác định một đường dẫn không yêu cầu đăng nhập
        exempt_routes = ['/auth/login', '/static', '/api']
        
        # Kiểm tra xem đường dẫn yêu cầu xác minh đăng nhập
        if any(request.path.startswith(path) for path in exempt_routes):
            return
        
        # Xác minh trạng thái đăng nhập
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for('auth.login'))
    
    # Lưu phiên bản ứng dụng toàn cầu
    flask_app = app
    
    app.logger.info("Khởi tạo ứng dụng đã hoàn thành")
    return app 