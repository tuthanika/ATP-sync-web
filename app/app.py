from flask import Flask, current_app
from apscheduler.schedulers.background import BackgroundScheduler
import os
import logging
import time
from datetime import datetime, timedelta
from app.utils.data_manager import DataManager
from app.utils.sync_manager import SyncManager
import pytz
import traceback

def init_app(app):
    """Khởi tạo ứng dụng"""
    # Nhật ký cấu hình
    logger = logging.getLogger()
    app.logger = logger
    logger.info("Khởi tạo ứng dụng...")
    
    # Khởi tạo Trình quản lý dữ liệu(Nếu không được khởi tạo)
    if 'DATA_MANAGER' not in app.config:
        data_manager = DataManager()
        app.config['DATA_MANAGER'] = data_manager
    else:
        data_manager = app.config['DATA_MANAGER']
    
    # Khởi tạo và lưu Trình quản lý đồng bộ hóa
    app.logger.info("Khởi tạo Trình quản lý đồng bộ hóa...")
    
    # Phiên bản SyncManager phải được tạo trong ngữ cảnh ứng dụng
    with app.app_context():
        sync_manager = SyncManager()
        app.config['SYNC_MANAGER'] = sync_manager
        
        # Khởi tạo bộ lập lịch cho Trình quản lý đồng bộ hóa
        app.logger.info("Đang tải các nhiệm vụ vào Lập lịch...")
        try:
            sync_manager.initialize_scheduler()
            app.logger.info("Khởi tạo lập lịch tác vụ đã hoàn thành")
        except Exception as e:
            app.logger.error(f"Khởi tạo Trình lập lịch tác vụ không thành công: {str(e)}")
            app.logger.error(traceback.format_exc())
    
        # Thêm các tác vụ làm sạch nhật ký vào bộ lập lịch của Trình quản lý đồng bộ hóa，Tránh sử dụng hai lịch trình
        try:
            # Tạo nhiệm vụ theo lịch trình để làm sạch nhật ký
            @sync_manager.scheduler.scheduled_job('cron', hour=3, minute=0, id='log_cleanup_job')
            def clean_old_logs():
                """Làm sạch nhật ký hết hạn thường xuyên"""
                # Đảm bảo chạy trong ngữ cảnh ứng dụng
                with app.app_context():
                    app.logger.info("Bắt đầu làm sạch nhật ký hết hạn...")
                    
                    try:
                        # Nhận số ngày lưu giữ nhật ký
                        settings = data_manager.get_settings()
                        keep_log_days = settings.get("keep_log_days", 7)
                        
                        # Làm sạch nhật ký hệ thống
                        data_manager.clear_old_logs(keep_log_days)
                        app.logger.info(f"Làm sạch nhật ký hệ thống đã hoàn thành，dự trữ{keep_log_days}Nhật ký trong ngày")
                        
                        # Làm sạch các phiên bản nhiệm vụ và nhật ký nhiệm vụ
                        data_manager.clear_old_task_instances(keep_log_days)
                        app.logger.info(f"Các phiên tác vụ và nhật ký tác vụ được dọn dẹp, lưu giữ hồ sơ trong {keep_log_days} ngày")
                        
                        # Làm sạch tệp nhật ký chính alist_sync.log
                        data_manager.clear_main_log_files(keep_log_days)
                        app.logger.info(f"Làm sạch tệp nhật ký chính được hoàn thành，dự trữ{keep_log_days}Nhật ký trong ngày")
                        
                    except Exception as e:
                        app.logger.error(f"Xảy ra lỗi trong khi làm sạch nhật ký: {str(e)}")
                        app.logger.error(traceback.format_exc())
            
            app.logger.info("Nhiệm vụ làm sạch nhật ký đã được Thêm  Lập lịch")
            
            # Trạng thái đầu ra của tất cả các tác vụ theo lịch trình
            jobs = sync_manager.scheduler.get_jobs()
            for job in jobs:
                app.logger.info(f"Kế hoạch nhiệm vụ: {job.id}, Chạy lần sau: {job.next_run_time}")
                
        except Exception as e:
            app.logger.error(f"Thêm tác vụ làm sạch nhật ký không thành công: {str(e)}")
            app.logger.error(traceback.format_exc())
    
    return app 