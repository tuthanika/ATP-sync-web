import time
import threading
import requests
import os
import json
import hashlib
from flask import current_app
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
import logging
import traceback
from app.utils.notifier import Notifier

class SyncManager:
    """Trình quản lý đồng bộ hóa，Chịu trách nhiệm thực hiện các nhiệm vụ đồng bộ hóa"""
    
    def __init__(self):
        # Khởi tạo một bộ lập lịch với múi giờ
        self.scheduler = BackgroundScheduler(timezone=timezone('Asia/Shanghai'))
        self.scheduler.start()
        self.running_tasks = {}
        self.lock = threading.Lock()
        self.is_initialized = False
        self.notifier = Notifier()
    
    def initialize_scheduler(self):
        """Khởi tạo bộ lập lịch，Tải tất cả các nhiệm vụ"""
        if self.is_initialized:
            current_app.logger.info("Bộ lập lịch đã được khởi tạo，hãy bỏ qua")
            return
            
        current_app.logger.info("Bắt đầu khởi tạo Trình lập lịch tác vụ...")
        
        try:
            data_manager = current_app.config['DATA_MANAGER']
            tasks = data_manager.get_tasks()
            
            # Xóa tất cả các nhiệm vụ hiện có
            for job in self.scheduler.get_jobs():
                self.scheduler.remove_job(job.id)
                current_app.logger.debug(f"Loại bỏ các nhiệm vụ cũ: {job.id}")
            
            task_count = 0
            for task in tasks:
                if task.get("enabled", True) and task.get("schedule"):
                    # Kiểm tra xem nhiệm vụ có được bật không và có lịch trình theo lịch trình không
                    try:
                        self.schedule_task(task)
                        task_count += 1
                    except Exception as e:
                        current_app.logger.error(f"Thêm nhiệm vụ {task.get('name', task.get('id'))} thất bại: {str(e)}")
                    
            current_app.logger.info(f"{task_count} tác vụ theo lịch trình đã được tải vào trình lập lịch")
            
            # Cập nhật thời gian chạy tiếp theo của tất cả các tác vụ
            self._update_all_next_run_times()
            
            # Đầu ra tất cả các nhiệm vụ hiện đang được lên lịch
            jobs = self.scheduler.get_jobs()
            current_app.logger.info(f"Bộ lập lịch có {len(jobs)} nhiệm vụ")
            for job in jobs:
                current_app.logger.info(f"Nhiệm vụ theo lịch trình: {job.id}, Lập kế hoạch: {job.trigger}, Thời gian chạy tiếp theo: {job.next_run_time}")
            
            # Khởi tạo thẻ đã hoàn thành
            self.is_initialized = True
            
        except Exception as e:
            current_app.logger.error(f"Bộ lập lịch khởi tạo không thành công: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            
    def _update_all_next_run_times(self):
        """Cập nhật thời gian chạy tiếp theo của tất cả các tác vụ"""
        try:
            data_manager = current_app.config['DATA_MANAGER']
            jobs = self.scheduler.get_jobs()
            updated_count = 0
            
            current_app.logger.info(f"Cập nhật {len(jobs)} Lần sau khi chạy nhiệm vụ")
            
            for job in jobs:
                # từ job ID Trích xuất nhiệm vụID
                if job.id.startswith('task_'):
                    task_id = int(job.id.replace('task_', ''))
                    
                    # Nhận nhiệm vụ
                    task = data_manager.get_task(task_id)
                    if task and job.next_run_time:
                        # Cập nhật thời gian chạy tiếp theo của nhiệm vụ
                        next_run_timestamp = int(job.next_run_time.timestamp())
                        data_manager.update_task_status(task_id, task.get("status", "pending"), next_run=next_run_timestamp)
                        updated_count += 1
                        current_app.logger.debug(f"Cập nhật nhiệm vụ {task_id} Thời gian chạy tiếp theo: {job.next_run_time}")
            
            current_app.logger.info(f"Cập nhật thành công {updated_count} Lần sau khi chạy nhiệm vụ")
            return updated_count
            
        except Exception as e:
            current_app.logger.error(f"Thời gian chạy tiếp theo của tác vụ cập nhật không thành công: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            return 0
    
    def schedule_task(self, task):
        """Thêm tác vụ vào Lập lịch"""
        task_id = task["id"]
        schedule = task.get("schedule")
        
        if not schedule or not schedule.strip():
            current_app.logger.warning(f"Nhiệm vụ {task_id} Không có kế hoạch lập lịch hiệu quả，hãy bỏ qua")
            return
        
        # Xóa các tác vụ hiện có khỏi trình lập lịch（Nếu có）
        job_id = f"task_{task_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            current_app.logger.debug(f"Các nhiệm vụ hiện có bị xóa: {job_id}")
        
        try:
            # Phân tíchBiểu thức cron
            cron_parts = self._parse_cron_expression(schedule)
            
            # Thêm một tác vụ mới
            job = self.scheduler.add_job(
                self.run_task,
                'cron',
                id=job_id,
                args=[task_id],
                **cron_parts,
                replace_existing=True,
                misfire_grace_time=3600  # cho phép1Bỏ lỡ giờ thực hiện thời gian ân hạn
            )
            
            # Ghi lại thông tin lập lịch
            cron_readable = f"{cron_parts.get('minute')} {cron_parts.get('hour')} {cron_parts.get('day')} {cron_parts.get('month')} {cron_parts.get('day_of_week')}"
            current_app.logger.info(f"Nhiệm vụ được Thêm  {job_id}({task.get('name')}) Cho người lập lịch，Lập kế hoạch: {cron_readable}, Chạy lần sau: {job.next_run_time}")
            
            # Cập nhật thời gian chạy tiếp theo của nhiệm vụ
            try:
                if hasattr(current_app, 'config') and 'DATA_MANAGER' in current_app.config:
                    data_manager = current_app.config['DATA_MANAGER']
                    if job.next_run_time:
                        next_run_timestamp = int(job.next_run_time.timestamp())
                        data_manager.update_task_status(task_id, task.get("status", "pending"), next_run=next_run_timestamp)
                        current_app.logger.debug(f"Cập nhật nhiệm vụ {task_id} Thời gian chạy tiếp theo: {job.next_run_time}")
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                current_app.logger.error(f"Cập nhật nhiệm vụ {task_id} Thời gian chạy tiếp theo không thành công: {str(e)}")
                current_app.logger.error(f"Lỗi chi tiết: {error_details}")
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            current_app.logger.error(f"Thêm nhiệm vụ {task_id} Không lập lịch: {str(e)}")
            current_app.logger.error(f"Lỗi chi tiết: {error_details}")
    
    def _parse_cron_expression(self, cron_expr):
        """Phân tích cron sự biểu lộ"""
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"Không hợp lệ cron sự biểu lộ: {cron_expr}，Nên được5Các bộ phận")
        
        # Ghi lại kết quả phân tích
        result = {
            'minute': parts[0],
            'hour': parts[1],
            'day': parts[2],
            'month': parts[3],
            'day_of_week': parts[4]
        }
        current_app.logger.debug(f"Phân tích cron sự biểu lộ: {cron_expr} -> {result}")
        return result
    
    def run_task(self, task_id):
        """Chạy một tác vụ đồng bộ hóa"""
        # LấyFlaskPhiên bản ứng dụng
        from flask import current_app, Flask
        
        # Nếu không có ngữ cảnh ứng dụng，Hãy thử tạo một
        app = None
        app_context = None
        
        try:
            # Cố gắng lấy ứng dụng hiện tại
            app = current_app._get_current_object()
        except RuntimeError:
            # Nếu không có ngữ cảnh ứng dụng hiện tại，Cố gắng đi từ cấu hình
            try:
                # Hãy thử sử dụng một thể hiện ứng dụng toàn cầu
                from app import flask_app
                if flask_app:
                    app = flask_app
                    app_context = app.app_context()
                    app_context.push()
                    print(f"Sử dụng các trường hợp ứng dụng toàn cầu làm nhiệm vụ {task_id} Tạo ra một ngữ cảnh")
                else:
                    # Nếu không có trường hợp ứng dụng toàn cầu，Tạo một mới
                    from app import create_app
                    app = create_app()
                    app_context = app.app_context()
                    app_context.push()
                    print(f"Cho nhiệm vụ {task_id} Đã tạo ra một ngữ cảnh ứng dụng mới")
            except Exception as e:
                print(f"Không tạo ra một ngữ cảnh ứng dụng: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return {"status": "error", "message": f"Không thể tạo ngữ cảnh ứng dụng: {str(e)}"}
        
        try:
            # Nhận Trình quản lý dữ liệu
            data_manager = app.config['DATA_MANAGER']
            task = data_manager.get_task(task_id)
            
            if not task:
                return {"status": "error", "message": "Nhiệm vụ không tồn tại"}
            
            # Kiểm tra xem nhiệm vụ có đang chạy không
            with self.lock:
                if task_id in self.running_tasks:
                    return {"status": "error", "message": "Nhiệm vụ đang chạy"}
                self.running_tasks[task_id] = time.time()
            
            try:
                # Tạo bản ghi phiên bản tác vụ
                task_instance = data_manager.add_task_instance(task_id, {
                    "sync_type": task.get("sync_type", "file_sync"),
                    "source_path": task.get("source_path", "/"),
                    "target_path": task.get("target_path", "/")
                })
                
                instance_id = task_instance["task_instances_id"]
                
                # Cập nhật trạng thái tác vụ
                current_time = int(time.time())
                data_manager.update_task_status(task_id, "running", last_run=current_time)
                
                # Nhật ký nhật ký bắt đầu
                data_manager.add_log({
                    "task_id": task_id,
                    "instance_id": instance_id,
                    "level": "INFO",
                    "message": f"Bắt đầu thực hiện các tác vụ: {task.get('name', f'Nhiệm vụ {task_id}')}",
                    "details": {"instance_id": instance_id}
                })
                
                # Ghi lại nhật ký thể hiện
                data_manager._append_task_log(task_id, instance_id, "Chuẩn bị thực hiện các nhiệm vụ")
                
                # Thực hiện thao tác đồng bộ hóa
                result = self._execute_task_with_alist_sync(task, task_id, instance_id)
                
                # Cập nhật trạng thái tác vụ
                status = "completed" if result.get("status") == "success" else "failed"
                data_manager.update_task_status(task_id, status, last_run=current_time)
                
                # Cập nhật trạng thái phiên bản tác vụ
                data_manager.update_task_instance(instance_id, status, result)
                
                # Ghi lại nhật ký hoàn thành
                data_manager.add_log({
                    "task_id": task_id,
                    "instance_id": instance_id,
                    "level": "INFO" if status == "completed" else "ERROR",
                    "message": f"Thực thi nhiệm vụ {('thành công' if status == 'completed' else 'thất bại')}: {task.get('name', f'Nhiệm vụ {task_id}')}",
                    "details": result
                })
                
                # Ghi lại nhật ký thể hiện
                data_manager._append_task_log(
                    task_id, 
                    instance_id, 
                    f"Thực thi nhiệm vụ {('thành công' if status == 'completed' else 'thất bại')}: {json.dumps(result, ensure_ascii=False)}"
                )
                
                # Gửi thông báo
                task_duration = int(time.time()) - current_time
                notification_title = f"Thực thi nhiệm vụ {'thành công' if status == 'completed' else 'thất bại'}"
                notification_content = result.get("message", "")
                
                # Thêm thông tin nhiệm vụ
                task_info = {
                    "id": task_id,
                    "name": task.get('name', f'Nhiệm vụ {task_id}'),
                    "status": status,
                    "duration": f"{task_duration} s",
                    "instance_id": instance_id
                }
                
                # Gửi thông báo
                self.notifier.send_notification(notification_title, notification_content, task_info)
                
                return {
                    "status": "success",
                    "message": "Nhiệm vụ đã được thực hiện", 
                    "instance_id": instance_id,
                    "result": result
                }
                
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                
                # Một ngoại lệ đã xảy ra，Cập nhật trạng thái tác vụ không thành công
                data_manager.update_task_status(task_id, "failed", last_run=int(time.time()))
                
                # Nếu một thể hiện đã được tạo，Cập nhật trạng thái thể hiện
                if 'instance_id' in locals():
                    error_result = {"status": "error", "message": str(e)}
                    data_manager.update_task_instance(instance_id, "failed", error_result)
                    data_manager._append_task_log(task_id, instance_id, f"Ngoại lệ thực thi nhiệm vụ: {str(e)}\n{error_details}")
                
                #Nhật ký yêu cầu ghi âm
                data_manager.add_log({
                    "task_id": task_id,
                    "level": "ERROR",
                    "message": f"Ngoại lệ thực thi nhiệm vụ: {task.get('name', f'Nhiệm vụ {task_id}')}",
                    "details": {"error": str(e)}
                })
                
                # Gửi thông báo
                task_duration = 0
                if 'current_time' in locals():
                    task_duration = int(time.time()) - current_time
                    
                notification_title = f"Thực thi nhiệm vụ không thành công"
                notification_content = f"Một lỗi thực thi: {str(e)}"
                
                # Thêm thông tin nhiệm vụ
                task_info = {
                    "id": task_id,
                    "name": task.get('name', f'Nhiệm vụ {task_id}'),
                    "status": "failed",
                    "duration": f"{task_duration}s",
                    "instance_id": instance_id if 'instance_id' in locals() else None
                }
                
                # Gửi thông báo
                self.notifier.send_notification(notification_title, notification_content, task_info)
                
                return {"status": "error", "message": str(e)}
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Một ngoại lệ chưa được thực hiện xảy ra trong khi nhiệm vụ được thực hiện: {str(e)}\n{error_details}")
            return {"status": "error", "message": f"Một ngoại lệ chưa được thực hiện xảy ra trong khi nhiệm vụ được thực hiện: {str(e)}"}
            
        finally:
            # Hoàn thành nhiệm vụ，Xóa khỏi danh sách chạy
            with self.lock:
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
            
            # Nếu ngữ cảnh ứng dụng mới được tạo，Cần phát hành nó
            if app_context:
                app_context.pop()
    
    def _execute_task_with_alist_sync(self, task, task_id, instance_id):
        """sử dụngAlistSyncThực hiện các nhiệm vụ"""
        from app.alist_sync import main as alist_sync_main
        from app.alist_sync import logger as alist_sync_logger
        
        # Nhận Trình quản lý dữ liệu
        data_manager = current_app.config['DATA_MANAGER']
        
        try:
            # Nhận thông tin kết nối
            connection_id = task.get("connection_id")
            if not connection_id:
                raise ValueError("Nhiệm vụ không được chỉ định cho kết nốiID")
            
            connection = data_manager.get_connection(connection_id)
            if not connection:
                raise ValueError(f"Không tìm thấyIDvì{connection_id}Sự liên quan")
            
            data_manager._append_task_log(task_id, instance_id, f"Sử dụng kết nối {connection.get('name', connection_id)} Thực hiện các nhiệm vụ")
            
            # Chuẩn bị các tham số
            sync_type = task.get("sync_type", "file_sync")
            source_connection_id = task.get("source_connection_id")
            target_connection_ids = task.get("target_connection_ids", [])
            source_path = task.get("source_path", "/")
            target_path = task.get("target_path", "/")
            
            # Đặt các biến môi trường，Đảm bảo sử dụng thông tin kết nối chính xác
            os.environ["BASE_URL"] = connection.get("server", "")
            os.environ["USERNAME"] = connection.get("username", "")
            os.environ["PASSWORD"] = connection.get("password", "")
            os.environ["TOKEN"] = connection.get("token", "")
            
            data_manager._append_task_log(task_id, instance_id, f"Thiết lập kết nối: máy chủ={os.environ['BASE_URL']}, Tên người dùng={os.environ['USERNAME']}")
            
            # Xác định các hoạt động dựa trên loại nhiệm vụ
            if sync_type == "file_move":
                os.environ["MOVE_FILE"] = "true"
                data_manager._append_task_log(task_id, instance_id, "Đặt thành chế độ di chuyển tệp")
            else:
                os.environ["MOVE_FILE"] = "false"
                data_manager._append_task_log(task_id, instance_id, "Đặt thành chế độ đồng bộ hóa tệp")
            
            # Đặt hành vi xóa mục khác biệt
            os.environ["SYNC_DELETE_ACTION"] = task.get("sync_diff_action", "none")
            data_manager._append_task_log(task_id, instance_id, f"Đặt phương thức xử lý mục khác biệt: {os.environ['SYNC_DELETE_ACTION']}")
            
            # Thiết lập một thư mục đồng bộ
            dir_pairs = []
            exclude_dirs = []
            for target_id in target_connection_ids:
                # Sửa chữasource_connection_idVàtarget_connection_idsTình hình của định dạng đường dẫn
                source_pair = source_connection_id
                if isinstance(source_connection_id, str) and not source_connection_id.isdigit():
                    # nếu nhưsource_connection_idĐó là định dạng đường dẫn，Sử dụng trực tiếp
                    source_pair = f"{source_connection_id}"
                else:
                    # Nếu không thì thêm"/"Tiền tố
                    source_pair = f"/{source_connection_id}"
                
                target_pair = target_id
                if isinstance(target_id, str) and not target_id.isdigit():
                    # nếu nhưtarget_idĐó là định dạng đường dẫn，Sử dụng trực tiếp
                    target_pair = f"{target_id}"
                else:
                    # Nếu không thì thêm"/"Tiền tố
                    target_pair = f"/{target_id}"
                
                # Xây dựng một cặp thư mục hoàn chỉnh
                dir_pair = f"/{source_pair}/{source_path}:/{target_pair}/{target_path}".replace('//', '/')
                dir_pairs.append(dir_pair)

                if task.get("exclude_dirs"):
                    excludes = task.get("exclude_dirs").split(",")
                    for exclude in excludes:
                        exclude = exclude.strip().lstrip("/")
                        exclude_src = f"{source_pair.rstrip('/')}/{exclude}".replace("//", "/")
                        exclude_dst = f"{target_pair.rstrip('/')}/{exclude}".replace("//", "/")
                        exclude_dirs.extend([exclude_src, exclude_dst])
        
            if dir_pairs:
                os.environ["DIR_PAIRS"] = ";".join(dir_pairs)
                data_manager._append_task_log(task_id, instance_id, f"Thiết lập một cặp thư mục đồng bộ: {os.environ['DIR_PAIRS']}")
                
                # Đặt thư mục loại trừ
                if exclude_dirs:
                    os.environ["EXCLUDE_DIRS"] = ",".join(exclude_dirs)
                    data_manager._append_task_log(task_id, instance_id, f"Đặt thư mục loại trừ: {os.environ['EXCLUDE_DIRS']}")
                
                # Đặt tệp loại trừ
                if task.get("file_filter"):
                    os.environ["REGEX_PATTERNS"] = task.get("file_filter")
                    data_manager._append_task_log(task_id, instance_id, f"Đặt bộ lọc tệp: {os.environ['REGEX_PATTERNS']}")
                
                # Đặt tối thiểu/Kích thước tệp tối đa
                if task.get("size_min"):
                    os.environ["SIZE_MIN"] = str(task.get("size_min"))
                    data_manager._append_task_log(task_id, instance_id, f"Đặt kích thước tệp tối thiểu: {os.environ['SIZE_MIN']}")

                if task.get("size_max"):
                    os.environ["SIZE_MAX"] = str(task.get("size_max"))
                    data_manager._append_task_log(task_id, instance_id, f"Đặt kích thước tệp tối đa: {os.environ['SIZE_MAX']}")
                
                # Thực hiện chức năng chính
                data_manager._append_task_log(task_id, instance_id, "Bắt đầu thực hiện đồng bộ hóa...")
                
                # Tạo bộ xử lý nhật ký tùy chỉnh，Nhật ký đầu ra vào tệp nhật ký tác vụ
                class TaskLogHandler(logging.Handler):
                    def emit(self, record):
                        log_message = self.format(record)
                        data_manager._append_task_log(task_id, instance_id, log_message)
                
                # Lấyalist_synccủaloggerVà thêm bộ xử lý tùy chỉnh
                if alist_sync_logger:
                    task_log_handler = TaskLogHandler()
                    formatter = logging.Formatter('%(message)s')
                    task_log_handler.setFormatter(formatter)
                    alist_sync_logger.addHandler(task_log_handler)
                
                # Thực hiện chức năng chính
                alist_sync_main()
                
                # Nếu bạn đã thêm một bộ xử lý tùy chỉnh，Cần phải được gỡ bỏ
                if alist_sync_logger and 'task_log_handler' in locals():
                    alist_sync_logger.removeHandler(task_log_handler)
                
                return {"status": "success", "message": "Thực thi nhiệm vụ đồng bộ thành công", "dir_pairs": dir_pairs}
            else:
                return {"status": "error", "message": "Không có cặp thư mục hợp lệ nào được cấu hình"}
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            data_manager._append_task_log(task_id, instance_id, f"Một lỗi thực thi: {str(e)}\n{error_details}")
            raise
    
    def _one_way_sync(self, source_conn, target_conn, source_path, target_path, task):
        """Thực hiện đồng bộ hóa một chiều"""
        # Mô phỏng quá trình đồng bộ hóa
        data_manager = current_app.config['DATA_MANAGER']
        settings = data_manager.get_settings()
        
        # Liệt kê các tệp thư mục nguồn
        source_files = self._list_files(source_conn, source_path)
        if source_files.get("status") != "success":
            return source_files
        
        # Liệt kê tệp thư mục đích
        target_files = self._list_files(target_conn, target_path)
        if target_files.get("status") != "success":
            return target_files
        
        # So sánh danh sách tệp，Tìm ra các tệp cần được đồng bộ hóa
        to_sync = []
        source_file_dict = {f["name"]: f for f in source_files.get("data", [])}
        target_file_dict = {f["name"]: f for f in target_files.get("data", [])}
        
        for name, source_file in source_file_dict.items():
            if source_file["type"] == "folder":
                # Nếu đó là một thư mục và mục tiêu không tồn tại，Tạo một thư mục
                if name not in target_file_dict:
                    to_sync.append({
                        "action": "create_folder",
                        "path": os.path.join(target_path, name)
                    })
            else:
                # Nếu đó là một tệp，Kiểm tra xem cần đồng bộ hóa
                if name not in target_file_dict or target_file_dict[name]["size"] != source_file["size"]:
                    to_sync.append({
                        "action": "sync_file",
                        "source_path": os.path.join(source_path, name),
                        "target_path": os.path.join(target_path, name),
                        "size": source_file["size"]
                    })
        
        # Thực hiện đồng bộ hóa
        success_count = 0
        error_count = 0
        
        for item in to_sync:
            if item["action"] == "create_folder":
                result = self._create_folder(target_conn, item["path"])
            else:
                result = self._sync_file(
                    source_conn, 
                    target_conn, 
                    item["source_path"], 
                    item["target_path"],
                    item["size"]
                )
            
            if result.get("status") == "success":
                success_count += 1
            else:
                error_count += 1
                #Nhật ký yêu cầu ghi âm
                data_manager.add_log({
                    "task_id": task["id"],
                    "level": "ERROR",
                    "message": f"Dự án đồng bộ hóa thất bại: {item['source_path'] if 'source_path' in item else item['path']}",
                    "details": result.get("message")
                })
        
        # Tóm tắt kết quả trả về
        total = len(to_sync)
        message = f"Đồng bộ hóa đã hoàn tất, tổng cộng {total} mục, {success_count} mục đã thành công, {error_count} mục đã thất bại"
        
        return {
            "status": "success" if error_count == 0 else "partial",
            "message": message,
            "details": {
                "total": total,
                "success": success_count,
                "error": error_count
            }
        }
    
    def _list_files(self, connection, path):
        """Liệt kê các tệp và thư mục với các đường dẫn được chỉ định"""
        # mô phỏng API Gọi
        # Nó nên được thông qua trong các dự án thực tế Alist API Nhận danh sách tệp
        
        # Mô phỏng đơn giản để trả về một số tệp
        if path == "/":
            return {
                "status": "success",
                "data": [
                    {"name": "tài liệu", "type": "folder", "size": 0},
                    {"name": "hình ảnh", "type": "folder", "size": 0},
                    {"name": "băng hình", "type": "folder", "size": 0},
                    {"name": "Kiểm tra tệp.txt", "type": "file", "size": 1024}
                ]
            }
        elif path == "/tài liệu":
            return {
                "status": "success",
                "data": [
                    {"name": "Báo cáo.docx", "type": "file", "size": 15360},
                    {"name": "dữ liệu.xlsx", "type": "file", "size": 8192}
                ]
            }
        else:
            return {
                "status": "success",
                "data": []
            }
    
    def _create_folder(self, connection, path):
        """Tạo một thư mục trên kết nối đích"""
        # Mô phỏng việc tạo thư mục
        return {"status": "success", "message": f"Sáng tạo thư mục thành công: {path}"}
    
    def _sync_file(self, source_conn, target_conn, source_path, target_path, size):
        """Đồng bộ hóa một tệp duy nhất"""
        # Mô phỏng quá trình đồng bộ hóa tệp
        # Logic truyền tệp thực tế nên được thực hiện tại đây，Bao gồm tải xuống và tải lên
        
        # Mô phỏng đơn giản của một hoạt động tốn thời gian
        time.sleep(0.5)
        
        return {"status": "success", "message": f"Đồng bộ hóa tệp thành công: {source_path} -> {target_path}"}
    
    def stop_task(self, task_id):
        """Ngừng chạy nhiệm vụ"""
        with self.lock:
            if task_id in self.running_tasks:
                # Trong các dự án thực tế，Cần có một cơ chế để làm gián đoạn các nhiệm vụ chạy
                del self.running_tasks[task_id]
                
                # Cập nhật trạng thái tác vụ
                data_manager = current_app.config['DATA_MANAGER']
                data_manager.update_task_status(task_id, "stopped")
                
                return {"status": "success", "message": "Nhiệm vụ đã được dừng lại"}
            else:
                return {"status": "error", "message": "Nhiệm vụ không chạy"}
    
    def reload_scheduler(self):
        """Tải lại tất cả các tác vụ trong Trình lập lịch"""
        try:
            current_app.logger.info("Bắt đầu tải lại bộ lập lịch...")
            
            # Nhận Trình quản lý dữ liệu
            data_manager = current_app.config['DATA_MANAGER']
            
            # Nhận tất cả các nhiệm vụ
            tasks = data_manager.get_tasks()
            
            # Xóa tất cả các nhiệm vụ hiện có，Nhưng hãy tiếp tục làm sạch nhật ký và các nhiệm vụ hệ thống khác
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                if job.id.startswith('task_'):
                    self.scheduler.remove_job(job.id)
                    current_app.logger.debug(f"Nhiệm vụ bị xóa: {job.id}")
            
            # Tải lại tất cả các tác vụ được bật
            loaded_count = 0
            for task in tasks:
                if task.get("enabled", True):
                    self.schedule_task(task)
                    loaded_count += 1
            
            current_app.logger.info(f"Tải lại {loaded_count} Nhiệm vụ để lập lịch")
            
            # Cập nhật thời gian chạy tiếp theo của tất cả các tác vụ
            self._update_all_next_run_times()
            
            # Liệt kê tất cả các nhiệm vụ theo lịch trình hiện tại
            job_info = []
            for job in self.scheduler.get_jobs():
                job_info.append({
                    "id": job.id,
                    "next_run": str(job.next_run_time) if job.next_run_time else None
                })
                current_app.logger.info(f"Kế hoạch nhiệm vụ: {job.id}, Chạy lần sau: {job.next_run_time or 'Không có kế hoạch'}")
            
            return {
                "status": "success",
                "message": "Bộ lập lịch đã được tải lại",
                "loaded_tasks": loaded_count,
                "jobs": job_info
            }
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            current_app.logger.error(f"Tải lại lịch trình không thành công: {str(e)}")
            current_app.logger.error(error_details)
            raise
    
    def reload_tasks(self):
        """reload_tasksPhương thức（Bí danh tương thích），Tải lại danh sách tác vụ"""
        # Phương thức này làreload_schedulerBí danh của，Cung cấp khả năng tương thích ngược
        current_app.logger.info("Gọireload_tasks()Phương thức（Bí danh），Chuyển hướng đếnreload_scheduler()")
        return self.reload_scheduler()
    
    def shutdown(self):
        """Tắt bộ lập lịch"""
        self.scheduler.shutdown() 