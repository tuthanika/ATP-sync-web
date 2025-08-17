import os

class Config:
    # Cấu hình cơ bản
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-alist-sync'
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 86400  # Thời gian hiệu lực phiên 24 Giờ
    DEBUG = False
    
    # Thư mục ứng dụng
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    
    # Cấu hình tệp tĩnh
    STATIC_FOLDER = 'static'
    
    # Thư mục dữ liệu
    DATA_DIR = os.environ.get('DATA_DIR') or '/app/data'
    
    # Thư mục tệp cấu hình
    CONFIG_DIR = os.path.join(DATA_DIR, 'config')
    
    # Cấu hình nhật ký
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_DIR = os.path.join(DATA_DIR, 'log')
    
    # Cấu hình nhiệm vụ
    MAX_CONCURRENT_TASKS = int(os.environ.get('MAX_CONCURRENT_TASKS', 3))
    DEFAULT_RETRY_COUNT = int(os.environ.get('DEFAULT_RETRY_COUNT', 3))
    DEFAULT_BLOCK_SIZE = int(os.environ.get('DEFAULT_BLOCK_SIZE', 10485760))  # 10MB
    
    # Cấu hình nhật ký tác vụ
    KEEP_LOG_DAYS = int(os.environ.get('KEEP_LOG_DAYS', 7))
    TASK_LOGS_DIR = os.path.join(LOG_DIR, 'task_logs')
    
    # Đảm bảo thư mục tồn tại
    @staticmethod
    def init_app(app):
        os.makedirs(Config.LOG_DIR, exist_ok=True)
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        os.makedirs(Config.CONFIG_DIR, exist_ok=True)
        os.makedirs(Config.TASK_LOGS_DIR, exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = 'INFO'
    
    # Môi trường sản xuất nên sử dụng các biến môi trường để đặt khóa mạnh
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'production-secret-key-for-alist-sync'


# Chọn Cấu hình theo các biến môi trường
config_name = os.environ.get('FLASK_ENV', 'production')
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}

# Sử dụng cấu hình sản xuất theo mặc định
Config = config.get(config_name, config['default']) 