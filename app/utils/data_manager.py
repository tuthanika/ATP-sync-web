import os
import json
import time
import datetime
from datetime import datetime as dt, timedelta
import glob
import logging
from pathlib import Path
from flask import current_app

class DataManager:
    """Trình quản lý dữ liệu，Chịu trách nhiệm xử lýJSONĐọc và ghi tệp"""
    
    def __init__(self, data_dir=None):
        """Khởi tạo Trình quản lý dữ liệu"""
        # Nhận thư mục gốc dự án
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Thiết lập thư mục dữ liệu
        self.data_dir = data_dir or os.path.join(project_root, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Đặt thư mục tệp cấu hình
        self.config_dir = os.path.join(self.data_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Thiết lập thư mục nhật ký
        self.log_dir = os.path.join(self.data_dir, "log")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Xác định đường dẫn tệp dữ liệu
        self.users_file = os.path.join(self.config_dir, "users.json")
        self.connections_file = os.path.join(self.config_dir, "connections.json")
        self.tasks_file = os.path.join(self.config_dir, "tasks.json")
        self.settings_file = os.path.join(self.config_dir, "settings.json")
        self.logs_file = os.path.join(self.log_dir, "logs.json")
        self.task_instances_file = os.path.join(self.config_dir, "task_instances.json")
        
        # Đảm bảo thư mục nhật ký tác vụ tồn tại
        self.task_logs_dir = os.path.join(self.log_dir, "task_logs")
        os.makedirs(self.task_logs_dir, exist_ok=True)
        
        # Tạo một tệp dữ liệu ban đầu（Nếu nó không tồn tại）
        self._ensure_file_exists(self.users_file, self._get_default_users())
        self._ensure_file_exists(self.connections_file, [])
        self._ensure_file_exists(self.tasks_file, [])
        self._ensure_file_exists(self.settings_file, self._get_default_settings())
        self._ensure_file_exists(self.logs_file, [])
        self._ensure_file_exists(self.task_instances_file, [])
    
    def _get_default_settings(self):
        """Nhận cài đặt mặc định"""
        return {
            "theme": "dark",
            "language": "zh_CN",
            "refresh_interval": 60,
            "keep_log_days": 7,  # Số ngày mặc định để giữ nhật ký là7bầu trời
            "max_concurrent_tasks": 3,
            "default_retry_count": 3,
            "default_block_size": 10485760,  # 10MB
            "bandwidth_limit": 0,
            "log_level": "INFO",
            "debug_mode": False,
            "enable_webhook": False,
            "notification_type": "webhook",
            "webhook_url": "",
            "dingtalk_secret": "",
            "bark_sound": "default",
            "telegram_bot_token": "",
            "telegram_chat_id": ""
        }
    
    def _ensure_file_exists(self, file_path, default_data):
        """Đảm bảo rằng tệp tồn tại，Tạo nếu nó không tồn tại"""
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_data, ensure_ascii=False, indent=2, fp=f)
                
    def _get_default_users(self):
        """Nhận người dùng mặc định"""
        return [
            {
                "id": 1,
                "username": "admin",
                "password": "admin",
                "created_at": self.format_timestamp(int(time.time())),
                "last_login": ""
            }
        ]
    
    def _read_json(self, file_path):
        """Đọc JSON tài liệu"""
        max_retries = 3
        retry_delay = 1
        for attempt in range(max_retries):
            try:
                # Cố gắng đọc nội dung tệp
                content = None
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Kiểm tra xem tệp có trống không
                    if not content:
                        raise ValueError("Nội dung tệp trống")
                    # Cố gắng phân tíchJSON
                    json_content = json.loads(content)
                    if isinstance(json_content, list) and not json_content:
                        raise ValueError("Nội dung tệp là một mảng trống")
                    return json_content
            except Exception as e:
                if attempt < max_retries - 1:
                    current_app.logger.error(f"ĐọcJSONXảy ra lỗi trong khi tệp ({file_path}): {str(e)}，Hãy thử đầu tiên {attempt + 1} Hãy thử lại")
                    time.sleep(retry_delay)
                else:
                    current_app.logger.error(f"ĐọcJSONXảy ra lỗi trong khi tệp ({file_path}): {str(e)}，Số lượng thử lại tối đa đạt được，Sẽ trả về giá trị mặc định")
            # Quay trở lại giá trị mặc định
            if "logs.json" in file_path:
                return []
            elif "users.json" in file_path:
                return self._get_default_users()
            elif "settings.json" in file_path:
                return self._get_default_settings()
            else:
                return []
    
    def _write_json(self, file_path, data):
        """Viết JSON tài liệu"""
        # Dữ liệu xác minh không thể là một mảng trống（Ngoại trừ các tệp cụ thể）
        if isinstance(data, list) and not data and not ("logs.json" in file_path or "task_instances.json" in file_path):
            current_app.logger.warning(f"Thử viết một mảng trống vào một tệp: {file_path}，Từ chối viết")
            return
        try:
            # Đảm bảo thư mục tồn tại
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            if os.name == 'nt': 
                # Ghi vào tệp tạm thời trước
                temp_file = file_path + ".tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, ensure_ascii=False, indent=2, fp=f)
                # Sau đó đổi tên nguyên tử thành tệp đích
                if os.path.exists(file_path):
                    # hiện hữuWindowsBạn cần xóa các tệp hiện có trước tiên
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        current_app.logger.error(f"Không xóa các tệp hiện có: {str(e)}")
                os.rename(temp_file, file_path)
            else:
                # KHÔNGWindowsViết trực tiếp vào hệ thống
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, ensure_ascii=False, indent=2, fp=f)
            # Viết hồ sơ đã thành công
            current_app.logger.info(f"Ghi thành công vào tệp: {file_path}")
        except Exception as e:
            current_app.logger.error(f"ViếtJSONXảy ra lỗi trong khi tệp ({file_path}): {str(e)}")
    
    def format_timestamp(self, timestamp):
        """Định dạng dấu thời gian là yyyy-MM-dd HH:mm:ss Định dạng"""
        if not timestamp:
            return ""
        return dt.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
    # Quản lý người dùng
    def get_users(self):
        """Nhận tất cả người dùng"""
        return self._read_json(self.users_file)
    
    def get_user(self, username):
        """Nhận người dùng thông qua tên người dùng"""
        users = self.get_users()
        for user in users:
            if user["username"] == username:
                return user
        return None
    
    def authenticate_user(self, username, password):
        """Xác minh tên người dùng và mật khẩu"""
        user = self.get_user(username)
        if user and user["password"] == password:
            # Cập nhật thời gian đăng nhập cuối cùng
            self.update_last_login(username)
            return user
        return None
    
    def update_user_password(self, username, new_password):
        """Cập nhật mật khẩu người dùng"""
        users = self.get_users()
        for i, user in enumerate(users):
            if user["username"] == username:
                users[i]["password"] = new_password
                users[i]["updated_at"] = self.format_timestamp(int(time.time()))
                self._write_json(self.users_file, users)
                return True
        return False
    
    def update_username(self, old_username, new_username):
        """Cập nhật tên người dùng"""
        if self.get_user(new_username):
            return False  # Tên người dùng mới đã tồn tại
            
        users = self.get_users()
        for i, user in enumerate(users):
            if user["username"] == old_username:
                users[i]["username"] = new_username
                users[i]["updated_at"] = self.format_timestamp(int(time.time()))
                self._write_json(self.users_file, users)
                return True
        return False
    
    def update_last_login(self, username):
        """Cập nhật thời gian đăng nhập cuối cùng của người dùng"""
        users = self.get_users()
        for i, user in enumerate(users):
            if user["username"] == username:
                users[i]["last_login"] = self.format_timestamp(int(time.time()))
                self._write_json(self.users_file, users)
                return True
        return False
    
    # Quản lý kết nối
    def get_connections(self):
        """Nhận tất cả các kết nối"""
        return self._read_json(self.connections_file)
    
    def get_connection(self, conn_id):
        """Nhận một kết nối duy nhất"""
        connections = self.get_connections()
        for conn in connections:
            if conn["connection_id"] == conn_id:
                return conn
        return None
    
    def add_connection(self, connection_data):
        """Thêm một kết nối"""
        connections = self.get_connections()
        # Tạo mớiID
        next_id = 1
        if connections:
            next_id = max(conn["connection_id"] for conn in connections) + 1
        
        connection_data["connection_id"] = next_id
        connection_data["created_at"] = self.format_timestamp(int(time.time()))
        connection_data["updated_at"] = self.format_timestamp(int(time.time()))
        
        connections.append(connection_data)
        self._write_json(self.connections_file, connections)
        return next_id
    
    def update_connection(self, conn_id, connection_data):
        """Cập nhật kết nối"""
        connections = self.get_connections()
        for i, conn in enumerate(connections):
            if conn["connection_id"] == conn_id:
                connection_data["connection_id"] = conn_id
                connection_data["created_at"] = conn.get("created_at")
                connection_data["updated_at"] = self.format_timestamp(int(time.time()))
                connections[i] = connection_data
                self._write_json(self.connections_file, connections)
                return True
        return False
    
    def delete_connection(self, conn_id):
        """Xóa kết nối"""
        connections = self.get_connections()
        connections = [conn for conn in connections if conn["connection_id"] != conn_id]
        self._write_json(self.connections_file, connections)
    
    # Quản lý nhiệm vụ
    def get_tasks(self):
        """Nhận tất cả các nhiệm vụ"""
        return self._read_json(self.tasks_file)
    
    def get_task(self, task_id):
        """Nhận nhiệm vụ duy nhất"""
        tasks = self.get_tasks()
        for task in tasks:
            if task["id"] == task_id:
                return task
        return None
    
    def add_task(self, task_data):
        """Thêm nhiệm vụ"""
        tasks = self.get_tasks()
        # Tạo mớiID
        next_id = 1
        if tasks:
            next_id = max(task["id"] for task in tasks) + 1
        
        task_data["id"] = next_id
        task_data["created_at"] = self.format_timestamp(int(time.time()))
        task_data["updated_at"] = self.format_timestamp(int(time.time()))
        task_data["status"] = "pending"
        task_data["last_run"] = ""
        task_data["next_run"] = ""
        
        tasks.append(task_data)
        self._write_json(self.tasks_file, tasks)
        return next_id
    
    def update_task(self, task_id, task_data):
        """Cập nhật nhiệm vụ"""
        tasks = self.get_tasks()
        for i, task in enumerate(tasks):
            if task["id"] == task_id:
                task_data["id"] = task_id
                task_data["created_at"] = task.get("created_at")
                task_data["updated_at"] = self.format_timestamp(int(time.time()))
                # Giữ các trường trạng thái khác
                for field in ["status", "last_run", "next_run"]:
                    if field in task and field not in task_data:
                        task_data[field] = task[field]
                
                tasks[i] = task_data
                self._write_json(self.tasks_file, tasks)
                return True
        return False
    
    def delete_task(self, task_id):
        """Xóa nhiệm vụ"""
        tasks = self.get_tasks()
        tasks = [task for task in tasks if task["id"] != task_id]
        self._write_json(self.tasks_file, tasks)
    
    def update_task_status(self, task_id, status, last_run=None, next_run=None):
        """Cập nhật trạng thái tác vụ"""
        tasks = self.get_tasks()
        for i, task in enumerate(tasks):
            if task["id"] == task_id:
                task["status"] = status
                if last_run:
                    task["last_run"] = self.format_timestamp(last_run)
                if next_run:
                    # Nếu dấu thời gian số được cung cấp，Được định dạng dưới dạng chuỗi
                    task["next_run"] = self.format_timestamp(next_run)
                    current_app.logger.debug(f"Cập nhật nhiệm vụ {task_id} Thời gian chạy tiếp theo: {task['next_run']}")
                tasks[i] = task
                self._write_json(self.tasks_file, tasks)
                return True
        return False
    
    # Quản lý cài đặt
    def get_settings(self):
        """Nhận cài đặt"""
        return self._read_json(self.settings_file)
    
    def update_settings(self, settings_data):
        """Cập nhật cài đặt"""
        current_settings = self.get_settings()
        current_settings.update(settings_data)
        self._write_json(self.settings_file, current_settings)
    
    # Quản lý nhật ký
    def get_logs(self, limit=100):
        """Nhận nhật ký mới nhất"""
        try:
            logs = self._read_json(self.logs_file)
            
            # Hãy chắc chắnlogsĐó là một danh sách
            if not isinstance(logs, list):
                print(f"Nội dung tệp nhật ký không phải là một danh sách hợp lệ，Đặt lại vào danh sách trống")
                logs = []
                self._write_json(self.logs_file, logs)
                
            logs_sorted = sorted(logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]
            
            # Định dạng dấu thời gian và thêm tên tác vụ bị thiếu
            for log in logs_sorted:
                if "timestamp" in log:
                    log["timestamp_formatted"] = self.format_timestamp(log["timestamp"])
                
                # Đảm bảo tất cả bao gồm task_id Tất cả các bản ghi là task_name
                if "task_id" in log and (not log.get("task_name") or log.get("task_name") == ""):
                    task = self.get_task(log["task_id"])
                    if task:
                        log["task_name"] = task.get("name", f"Nhiệm vụ {log['task_id']}")
                    else:
                        # Nếu không thể tìm thấy nhiệm vụ tương ứng，Nhiệm vụ sử dụngIDNhư một màn hình sao lưu
                        log["task_name"] = f"Nhiệm vụ {log['task_id']}"
            
            return logs_sorted
            
        except Exception as e:
            print(f"Xảy ra lỗi trong khi có được nhật ký: {str(e)}")
            # Nếu có sự cố xảy ra，Quay trở lại danh sách trống
            return []
    
    def add_log(self, log_data):
        """Thêm nhật ký"""
        try:
            logs = self._read_json(self.logs_file)
            timestamp = int(time.time())
            log_data["timestamp"] = timestamp
            log_data["timestamp_formatted"] = self.format_timestamp(timestamp)
            
            # Nếu nhật ký chứa task_id Nhưng không task_name，Thử thêm tên tác vụ
            if "task_id" in log_data and "task_name" not in log_data:
                task = self.get_task(log_data["task_id"])
                if task:
                    log_data["task_name"] = task.get("name", "Nhiệm vụ không xác định")
            
            # Hãy chắc chắnlogsĐó là một danh sách
            if not isinstance(logs, list):
                logs = []
                
            # Giới hạn số lượng nhật ký mới nhất 1000 dải
            logs.append(log_data)
            logs = sorted(logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:1000]
            
            # In thông tin gỡ lỗi trước khi ghi vào nhật ký
            print(f"Nhật ký viết，Số lượng nhật ký hiện tại: {len(logs)}")
            try:
                self._write_json(self.logs_file, logs)
                print(f"Nhật ký viết thành công - {log_data.get('message', 'Không có tin tức')}")
            except Exception as e:
                print(f"Xảy ra lỗi khi viết vào nhật ký: {str(e)}")
                # Cố gắng tạo lại tệp nhật ký
                with open(self.logs_file, 'w', encoding='utf-8') as f:
                    json.dump(logs, ensure_ascii=False, indent=2, fp=f)
        except Exception as e:
            print(f"Không thể thêm nhật ký: {str(e)}")
            # Đảm bảo tệp nhật ký tồn tại và hợp lệ
            self._ensure_file_exists(self.logs_file, [])
    
    def clear_old_logs(self, days=None):
        """Làm sạch các bản ghi cũ"""
        if days is None:
            settings = self.get_settings()
            days = settings.get("keep_log_days", 7)
        
        logs = self._read_json(self.logs_file)
        current_time = int(time.time())
        cutoff_time = current_time - (days * 86400)  # Có một ngày 86400 s
        
        logs = [log for log in logs if log.get("timestamp", 0) > cutoff_time]
        self._write_json(self.logs_file, logs)
    
    # Quản lý phiên nhiệm vụ
    def get_task_instances(self, task_id=None, limit=50):
        """Nhận danh sách các phiên bản nhiệm vụ，Có thể được giao nhiệm vụIDlọc"""
        instances = self._read_json(self.task_instances_file)
        
        # Sắp xếp theo dấu thời gian giảm dần
        instances = sorted(instances, key=lambda x: x.get("start_time", 0), reverse=True)
        
        # Nếu nhiệm vụ được chỉ địnhID，Sau đó, chỉ có trường hợp của nhiệm vụ được trả về
        if task_id:
            instances = [inst for inst in instances if inst.get("task_id") == task_id]
        
        # 返回指定数量的实例
        return instances[:limit]
    
    def get_task_instance(self, instance_id):
        """Nhận một phiên bản tác vụ duy nhất"""
        instances = self._read_json(self.task_instances_file)
        for instance in instances:
            if instance.get("task_instances_id") == instance_id:
                return instance
        return None
    
    def add_task_instance(self, task_id, start_params=None):
        """Thêm một bản ghi phiên bản nhiệm vụ mới"""
        instances = self._read_json(self.task_instances_file)
        task = self.get_task(task_id)
        
        if not task:
            return None
        
        # Tạo mớiID
        next_id = 1
        if instances:
            next_id = max(instance.get("task_instances_id", 0) for instance in instances) + 1
        
        # Nhận dấu thời gian hiện tại
        start_time = int(time.time())
        
        # Tạo bản ghi phiên bản tác vụ
        instance = {
            "task_instances_id": next_id,
            "task_id": task_id,
            "task_name": task.get("name", f"Nhiệm vụ {task_id}"),
            "start_time": start_time,
            "start_time_formatted": self.format_timestamp(start_time),
            "end_time": 0,
            "end_time_formatted": "",
            "status": "running",
            "params": start_params or {},
            "result": {}
        }
        
        instances.append(instance)
        self._write_json(self.task_instances_file, instances)
        
        # Tạo tệp nhật ký tác vụ
        self._create_task_log_file(task_id, instance["task_instances_id"], f"Bắt đầu thực hiện các tác vụ: {instance['task_name']}")
        
        return instance
    
    def update_task_instance(self, instance_id, status, result=None, end_time=None):
        """Cập nhật trạng thái phiên bản tác vụ"""
        instances = self._read_json(self.task_instances_file)
        
        for i, instance in enumerate(instances):
            if instance.get("task_instances_id") == instance_id:
                instances[i]["status"] = status
                
                if result:
                    instances[i]["result"] = result
                
                if end_time or status in ["completed", "failed"]:
                    end_time = end_time or int(time.time())
                    instances[i]["end_time"] = end_time
                    instances[i]["end_time_formatted"] = self.format_timestamp(end_time)
                
                self._write_json(self.task_instances_file, instances)
                
                # Cập nhật nhật ký tác vụ
                self._append_task_log(
                    instance.get("task_id"), 
                    instance_id, 
                    f"Trạng thái nhiệm vụ được cập nhật để: {status}" + (f", kết quả: {json.dumps(result, ensure_ascii=False)}" if result else "")
                )
                
                return True
                
        return False
    
    def clear_old_task_instances(self, days=None):
        """Làm sạch hồ sơ phiên bản nhiệm vụ cũ"""
        if days is None:
            settings = self.get_settings()
            days = settings.get("keep_log_days", 7)
        
        instances = self._read_json(self.task_instances_file)
        current_time = int(time.time())
        cutoff_time = current_time - (days * 86400)  # Có một ngày 86400 s
        
        # Giữ các trường hợp nhiệm vụ mới hơn
        new_instances = [inst for inst in instances if inst.get("start_time", 0) > cutoff_time]
        
        # Xóa tệp nhật ký tương ứng với thể hiện cũ
        old_instances = [inst for inst in instances if inst.get("start_time", 0) <= cutoff_time]
        for instance in old_instances:
            log_file = self._get_task_log_file_path(instance.get("task_id"), instance.get("task_instances_id"))
            if os.path.exists(log_file):
                try:
                    os.remove(log_file)
                except:
                    pass
        
        self._write_json(self.task_instances_file, new_instances)
    
    def clear_main_log_files(self, days=None):
        """Làm sạch tệp nhật ký chínhalist_sync.logSao lưu lịch sử
        Định dạng tệp nhật ký được xoay mỗi ngày là alist_sync.log.YYYY-MM-DD
        """
        if days is None:
            settings = self.get_settings()
            days = settings.get("keep_log_days", 7)
        
        # Tính thời hạn
        cutoff_date = dt.now() - timedelta(days=days)
        
        # Nhận tất cả các tệp nhật ký
        log_files = glob.glob(os.path.join(self.log_dir, "alist_sync.log.*"))
        
        # Lặp lại thông qua tất cả các tệp nhật ký
        for log_file in log_files:
            try:
                # Trích xuất phần ngày
                file_name = os.path.basename(log_file)
                date_part = file_name.split('.')[-1]  # Nhận phần ngày YYYY-MM-DD
                
                # Phân tích ngày
                file_date = dt.strptime(date_part, "%Y-%m-%d")
                
                # Nếu ngày sớm hơn thời gian lưu，Xóa bỏ
                if file_date < cutoff_date:
                    os.remove(log_file)
                    logging.info(f"Đã xóa tệp nhật ký đã hết hạn: {file_name}")
            except Exception as e:
                logging.error(f"Xử lý tệp nhật ký {log_file} Xảy ra lỗi trong khi: {str(e)}")
    
    # Quản lý nhật ký nhiệm vụ
    def _get_task_log_file_path(self, task_id, instance_id):
        """Nhận đường dẫn tệp nhật ký tác vụ"""
        return os.path.join(self.task_logs_dir, f"task_{task_id}_instance_{instance_id}.log")
    
    def _create_task_log_file(self, task_id, instance_id, initial_message=None):
        """Tạo tệp nhật ký tác vụ"""
        log_file = self._get_task_log_file_path(task_id, instance_id)
        
        with open(log_file, 'w', encoding='utf-8') as f:
            timestamp = self.format_timestamp(int(time.time()))
            f.write(f"[{timestamp}] Khởi động phiên bản tác vụ\n")
            
            if initial_message:
                f.write(f"[{timestamp}] {initial_message}\n")
    
    def _append_task_log(self, task_id, instance_id, message):
        """Nối nội dung vào tệp nhật ký tác vụ"""
        log_file = self._get_task_log_file_path(task_id, instance_id)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            timestamp = self.format_timestamp(int(time.time()))
            f.write(f"[{timestamp}] {message}\n")
    
    def get_task_log(self, task_id, instance_id):
        """Nhận nội dung nhật ký tác vụ"""
        log_file = self._get_task_log_file_path(task_id, instance_id)
        
        if not os.path.exists(log_file):
            return []
        
        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
            
        # Chuyển đổi văn bản nhật ký thành danh sách
        log_lines = log_content.split('\n')
        return [line for line in log_lines if line.strip()]
    
    # Hàm nhập và xuất
    def export_data(self):
        """Xuất tất cả dữ liệu dưới dạng từ điển"""
        export_data = {
            "users": self._read_json(self.users_file),
            "connections": self._read_json(self.connections_file),
            "tasks": self._read_json(self.tasks_file),
            "settings": self._read_json(self.settings_file)
        }
        return export_data
    
    def import_data(self, data, backup=True):
        """Nhập và ghi đè dữ liệu hiện có，Sao lưu tùy chọn của dữ liệu gốc
        
        Args:
            data (dict): Từ điển chứa dữ liệu được nhập
            backup (bool): Có sao lưu dữ liệu gốc không，Mặc định làTrue
            
        Returns:
            dict: Từ điển chứa kết quả nhập
        """
        result = {"success": True, "message": "Nhập dữ liệu thành công", "details": {}}
        backup_files = {}
        
        try:
            # Kiểm tra định dạng dữ liệu，Xác định xem đó là định dạng tiêu chuẩn hayalist_syncĐịnh dạng
            format_type = "unknown"
            
            if isinstance(data, dict):
                # Phát hiện phiên bản cũ của định dạng cấu hình cơ bản
                if "baseUrl" in data and "token" in data:
                    # Đây làalist_syncĐịnh dạng cấu hình cơ bản
                    format_type = "alist_sync_base_config"
                    result["details"]["format"] = format_type
                    result["details"]["detected_fields"] = ["baseUrl", "token"]
                    # Chuyển đổi sang định dạng tiêu chuẩn
                    data = self._convert_alist_sync_base_config(data)
                
                # Phát hiện định dạng cấu hình tác vụ đồng bộ kế thừa(Hai định dạng có thể)
                elif "tasks" in data and isinstance(data["tasks"], list):
                    # Kiểm tra xem đó là phiên bản cũ hay phiên bản mới
                    if data["tasks"] and all(isinstance(task, dict) for task in data["tasks"]):
                        old_format = any("->" in task.get("syncDirs", "") for task in data["tasks"] if "syncDirs" in task)
                        new_format = any(all(key in task for key in ["sourceStorage", "targetStorages", "syncDirs"]) 
                                        for task in data["tasks"])
                        
                        if old_format or new_format:
                            # Đây làalist_syncĐịnh dạng cấu hình tác vụ đồng bộ
                            format_type = "alist_sync_sync_config"
                            result["details"]["format"] = format_type
                            result["details"]["task_count"] = len(data["tasks"])
                            
                            # Phiên bản cấu hình thẻ
                            if new_format:
                                result["details"]["format_version"] = "Định dạng phiên bản mới"
                            else:
                                result["details"]["format_version"] = "Định dạng phiên bản cũ"
                            
                            # Chuyển đổi sang định dạng tiêu chuẩn
                            data = self._convert_alist_sync_sync_config(data)
                        else:
                            # Kiểm tra xem nó ở định dạng tiêu chuẩn
                            if all(key in data for key in ["users", "connections", "tasks", "settings"]):
                                format_type = "standard"
                                result["details"]["format"] = format_type
                            else:
                                # Định dạng không được công nhận
                                raise ValueError("Định dạng dữ liệu nhiệm vụ không được công nhận，Các trường cần thiết bị thiếu")
                    else:
                        # Nó có thể là một định dạng tiêu chuẩn hoặc định dạng không hợp lệ
                        if all(key in data for key in ["users", "connections", "tasks", "settings"]):
                            format_type = "standard"
                            result["details"]["format"] = format_type
                        else:
                            # Định dạng không được công nhận
                            raise ValueError("无法识别的数据格式，Các trường cần thiết bị thiếu")
                else:
                    # Có thể là một định dạng tiêu chuẩn
                    if all(key in data for key in ["users", "connections", "tasks", "settings"]):
                        format_type = "standard"
                        result["details"]["format"] = format_type
                    else:
                        # Định dạng không được công nhận
                        missing_keys = [k for k in ["users", "connections", "tasks", "settings"] if k not in data]
                        raise ValueError(f"Định dạng dữ liệu không hợp lệ，Các trường cần thiết bị thiếu: {', '.join(missing_keys)}")
            else:
                raise ValueError("Dữ liệu nhập phải có giá trịJSONSự vật")
            
            # Tạo sao chép lưu trước
            if backup:
                timestamp = int(time.time())
                backup_dir = os.path.join(self.data_dir, f"backup_{timestamp}")
                os.makedirs(backup_dir, exist_ok=True)
                
                # Tệp sao lưu
                for file_name, json_file in [
                    ("users", self.users_file),
                    ("connections", self.connections_file),
                    ("tasks", self.tasks_file),
                    ("settings", self.settings_file)
                ]:
                    if os.path.exists(json_file):
                        backup_file = os.path.join(backup_dir, os.path.basename(json_file))
                        with open(json_file, 'r', encoding='utf-8') as src, \
                             open(backup_file, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
                        backup_files[file_name] = backup_file
                
                result["details"]["backup_dir"] = backup_dir
                result["details"]["backup_files"] = backup_files
                result["details"]["backup_timestamp"] = self.format_timestamp(timestamp)
            
            # Xử lý dữ liệu nhập
            for data_type, file_path in [
                ("users", self.users_file),
                ("connections", self.connections_file),
                ("tasks", self.tasks_file),
                ("settings", self.settings_file)
            ]:
                if data_type in data:
                    self._write_json(file_path, data[data_type])
                    if isinstance(data[data_type], list):
                        result["details"][data_type] = f"nhập thành công，chung{len(data[data_type])}Ghi"
                    else:
                        result["details"][data_type] = "Nhập thành công"
                else:
                    result["details"][data_type] = "Không có dữ liệu được cung cấp，Không thay đổi"
            
            # Thêm số liệu thống kê
            if format_type == "alist_sync_base_config":
                result["message"] = "Nhập thành côngAList-SyncCấu hình cơ bản，Cập nhật thông tin kết nối"
            elif format_type == "alist_sync_sync_config":
                task_count = len(data.get("tasks", []))
                result["message"] = f"Nhập thành côngAList-SyncĐồng bộ hóa cấu hình tác vụ，chung{task_count}nhiệm vụ（Nhiệm vụ ban đầu đã được bảo hiểm）"
            else:
                # Định dạng tiêu chuẩn，Thêm số liệu thống kê
                result["message"] = "Dữ liệu hệ thống được nhập thành công，Cấu hình ban đầu đã bị ghi đè"
            
            return result
        except Exception as e:
            result["success"] = False
            result["message"] = f"nhập không thành công: {str(e)}"
            # Nếu nhập không thành công，Cố gắng khôi phục sao chép lưu
            if backup and backup_files:
                try:
                    for data_type, backup_file in backup_files.items():
                        dest_file = getattr(self, f"{data_type}_file")
                        with open(backup_file, 'r', encoding='utf-8') as src, \
                             open(dest_file, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
                    result["details"]["recovery"] = "Phục hồi từ sao chép lưu"
                except Exception as recovery_error:
                    result["details"]["recovery_error"] = str(recovery_error)
            return result
    
    def _convert_alist_sync_base_config(self, config):
        """Sẽalist_syncChuyển đổi cấu hình cơ bản thành định dạng tiêu chuẩn
        
        Args:
            config (dict): alist_syncCấu hình cơ bản
            
        Returns:
            dict: Dữ liệu cấu hình ở định dạng tiêu chuẩn
        """
        # Đọc dữ liệu hiện có làm cơ sở
        users = self._read_json(self.users_file)
        tasks = self._read_json(self.tasks_file)
        settings = self._read_json(self.settings_file)
        
        # Tạo dữ liệu kết nối mới，Hoàn toàn bao gồm các kết nối hiện có
        connections = [{
            "connection_id": 1,
            "name": "alist",
            "server": config.get("baseUrl", ""),
            "username": config.get("username", ""),
            "password": config.get("password", ""),
            "token": config.get("token", ""),
            "proxy": "",
            "max_retry": "3", 
            "insecure": False,
            "status": "online",
            "created_at": self.format_timestamp(int(time.time())),
            "updated_at": self.format_timestamp(int(time.time()))
        }]
        
        return {
            "users": users,
            "connections": connections,
            "tasks": tasks,
            "settings": settings
        }
    
    def _convert_alist_sync_sync_config(self, config):
        """Sẽalist_syncChuyển đổi cấu hình tác vụ đồng bộ thành định dạng tiêu chuẩn
        
        Args:
            config (dict): alist_syncĐồng bộ hóa cấu hình tác vụ
            
        Returns:
            dict: Dữ liệu cấu hình ở định dạng tiêu chuẩn
        """
        # Đọc dữ liệu hiện có làm cơ sở
        users = self._read_json(self.users_file)
        connections = self._read_json(self.connections_file)
        settings = self._read_json(self.settings_file)
        
        # Nhận tất cả các đường dẫn lưu trữ（Được sử dụng để xác định chính xác các tiền tố đường dẫn）
        storage_paths = self._get_storage_paths()
        
        # Chuyển đổi danh sách nhiệm vụ
        converted_tasks = []
        
        # Xử lý từng nhiệm vụ đồng bộ hóa
        for i, sync_task in enumerate(config.get("tasks", [])):
            # Tên nhiệm vụ(Nếu không, tên mặc định sẽ được tạo)
            task_name = sync_task.get("taskName") or f"Đồng bộ hóa các nhiệm vụ {i+1}"
            
            # Nhận chế độ đồng bộ hóa và Chính sách xử lý mục khác biệt
            sync_mode = sync_task.get("syncMode", "data")
            sync_del_action = sync_task.get("syncDelAction", "none")
            
            # Ánh xạ chế độ đồng bộ định dạng cũ sang định dạng mới
            sync_type = "file_sync"  # Mặc định là đồng bộ hóa tệp
            if sync_mode == "data" or sync_mode == "file":
                sync_type = "file_sync"
            elif sync_mode == "file_move":
                sync_type = "file_move"
            
            # Nhận gói và bộ lọc tệp
            schedule = self._convert_cron_format(sync_task.get("cron", ""))
            file_filter = sync_task.get("regexPatterns", "")
            exclude_dirs = sync_task.get("excludeDirs", "")
            
            # --------- Xử lý các định dạng đường dẫn khác nhau ---------
            
            # Kiểm tra xem nó có được bao gồm khôngpathsĐịnh dạng của mảng
            if "paths" in sync_task and isinstance(sync_task["paths"], list):
                # Xử lý các tác vụ chứa nhiều cặp đường dẫn đích nguồn
                for path_idx, path_item in enumerate(sync_task["paths"]):
                    # Xử lý các cặp đường dẫn thông thường
                    src_path = None
                    dst_path = None
                    
                    # Kiểm tra xem nó có phải là cặp đường dẫn trong chế độ di động không
                    if "srcPathMove" in path_item and "dstPathMove" in path_item:
                        src_path = path_item.get("srcPathMove", "").strip()
                        dst_path = path_item.get("dstPathMove", "").strip()
                    # Kiểm tra xem đó có phải là cặp đường dẫn thông thường không
                    elif "srcPath" in path_item and "dstPath" in path_item:
                        src_path = path_item.get("srcPath", "").strip()
                        dst_path = path_item.get("dstPath", "").strip()
                        
                    # Nếu đường dẫn hợp lệ không thể lấy được，hãy bỏ qua
                    if not src_path or not dst_path:
                        continue
                        
                    # Nhiệm vụ lắp ráp
                    path_task_name = f"{task_name} - con đường{path_idx+1}" if len(sync_task["paths"]) > 1 else task_name
                    
                    # Các đường dẫn nguồn phân chia thông minh và đường dẫn đích
                    src_conn_id, src_real_path = self._split_path_with_storage_list(src_path, storage_paths)
                    dst_conn_id, dst_real_path = self._split_path_with_storage_list(dst_path, storage_paths)
                    
                    # Tạo dữ liệu nhiệm vụ
                    task_data = {
                        "id": len(converted_tasks) + 1,  # Hãy chắc chắnIDchỉ một
                        "name": path_task_name,
                        "connection_id": 1,  # Kết nối mặc địnhID
                        "source_connection_id": src_conn_id,
                        "source_connection_name": src_conn_id,
                        "target_connection_ids": [dst_conn_id],
                        "target_connection_names": dst_conn_id,
                        "source_path": src_real_path,
                        "target_path": dst_real_path,
                        "sync_type": sync_type,
                        "sync_diff_action": sync_del_action,
                        "schedule": schedule,
                        "file_filter": file_filter,
                        "exclude_dirs": exclude_dirs,
                        "enabled": True,
                        "created_at": self.format_timestamp(int(time.time())),
                        "updated_at": self.format_timestamp(int(time.time())),
                        "last_run": "",
                        "next_run": "",
                        "status": "pending"
                    }
                    
                    converted_tasks.append(task_data)
                    
            # Xử lý các định dạng cũ: syncDirsBao gồm"Thư mục nguồn->Thư mục mục tiêu"Định dạng
            elif "syncDirs" in sync_task and "->" in sync_task.get("syncDirs", ""):
                dirs = sync_task.get("syncDirs", "").strip()
                if not dirs:
                    continue
                    
                parts = dirs.split("->")
                if len(parts) != 2:
                    continue
                    
                source_dir = parts[0].strip()
                dst_dir = parts[1].strip()
                
                # Tạo nhiệm vụ
                task_data = {
                    "id": len(converted_tasks) + 1,
                    "name": task_name,
                    "connection_id": 1,  # Kết nối mặc địnhID
                    "source_connection_id": "",
                    "source_connection_name": "",
                    "target_connection_ids": [""],
                    "target_connection_names": "",
                    "source_path": source_dir,
                    "target_path": dst_dir,
                    "sync_type": sync_type,
                    "sync_diff_action": sync_del_action,
                    "schedule": schedule,
                    "file_filter": file_filter,
                    "exclude_dirs": exclude_dirs,
                    "enabled": True,
                    "created_at": self.format_timestamp(int(time.time())),
                    "updated_at": self.format_timestamp(int(time.time())),
                    "last_run": "",
                    "next_run": "",
                    "status": "pending"
                }
                
                converted_tasks.append(task_data)
                
            # Xử lý định dạng tiêu chuẩn: cósourceStorageVàtargetStorages
            elif "syncDirs" in sync_task and "sourceStorage" in sync_task and "targetStorages" in sync_task:
                source_storage = sync_task.get("sourceStorage", "").strip()
                sync_dirs = sync_task.get("syncDirs", "").strip()
                
                # Nếu không có lưu trữ nguồn hoặc thư mục đồng bộ，hãy bỏ qua
                if not source_storage or not sync_dirs:
                    continue
                
                # Nhận danh sách lưu trữ mục tiêu，Bỏ qua các giá trị trống
                target_storages = [
                    storage for storage in sync_task.get("targetStorages", [])
                    if storage and storage.strip()
                ]
                
                # Nếu không có lưu trữ mục tiêu，hãy bỏ qua
                if not target_storages:
                    continue
                
                # Tạo một tác vụ duy nhất chứa tất cả lưu trữ mục tiêu
                # Định dạng đường dẫn nguồn
                source_path = sync_dirs
                
                # Tạo dữ liệu nhiệm vụ
                task_data = {
                    "id": len(converted_tasks) + 1,  # Hãy chắc chắnIDchỉ một
                    "name": task_name,
                    "connection_id": 1,  # Kết nối mặc địnhID
                    "source_connection_id": source_storage,
                    "source_connection_name": source_storage,
                    "target_connection_ids": target_storages,
                    "target_connection_names": ",".join([ts.split('/')[-1] if '/' in ts else ts for ts in target_storages]),
                    "source_path": sync_dirs,
                    "target_path": sync_dirs,
                    "sync_type": sync_type,
                    "sync_diff_action": sync_del_action,
                    "schedule": schedule,
                    "file_filter": file_filter,
                    "exclude_dirs": exclude_dirs,
                    "enabled": True,
                    "created_at": self.format_timestamp(int(time.time())),
                    "updated_at": self.format_timestamp(int(time.time())),
                    "last_run": "",
                    "next_run": "",
                    "status": "pending"
                }
                
                converted_tasks.append(task_data)
        
        return {
            "users": users,
            "connections": connections,
            "tasks": converted_tasks,
            "settings": settings
        }
    
    def _get_storage_paths(self):
        """Nhận danh sách tất cả các đường dẫn lưu trữ，Được sử dụng để phân chia thông minh các đường dẫn nhập
        
        Returns:
            list: Danh sách đường dẫn lưu trữ，Sắp xếp từ dài đến ngắn theo chiều dài
        """
        # Nhận thông tin kết nối được lưu từ tệp cấu hình
        connections = self._read_json(self.connections_file)
        if not connections:
            return []
            
        # Thu thập tất cả các đường dẫn lưu trữ có thể
        all_storage_paths = []
        
        # Nhận đường dẫn lưu trữ từ một kết nối
        from app.alist_sync import AlistSync
        for conn in connections:
            try:
                # Tạo một phiên bản AlistSync
                alist = AlistSync(
                    conn.get('server'),
                    conn.get('username'),
                    conn.get('password'),
                    conn.get('token')
                )
                
                # Cố gắng đăng nhập
                if alist.login():
                    # Nhận danh sách lưu trữ
                    storage_list = alist.get_storage_list()
                    if isinstance(storage_list, list):
                        all_storage_paths.extend(storage_list)
                
                # Đóng kết nối
                alist.close()
            except Exception as e:
                # Bỏ qua lỗi kết nối，Tiếp tục xử lý các kết nối khác
                continue
        
        # Xóa các sao chép
        all_storage_paths = list(set(all_storage_paths))
        
        # Sắp xếp từ dài đến ngắn theo chiều dài，Để đảm bảo đường dẫn cụ thể nhất được khớp
        all_storage_paths.sort(key=len, reverse=True)
        
        return all_storage_paths
        
    def _split_path_with_storage_list(self, full_path, storage_paths):
        """Tách thông minh các đường dẫn đầy đủ bằng cách sử dụng Danh sách đường dẫn lưu trữ
        
        Args:
            full_path (str): Hoàn thành đường dẫn
            storage_paths (list): Danh sách đường dẫn lưu trữ
            
        Returns:
            tuple: (Đường dẫn lưu trữ, đường dẫn thực tế)
        """
        # Phương thức phân tách đơn giản được sử dụng theo mặc định（/dav/xxx/）
        # Thử khớp đường dẫn lưu trữ trước tiên
        if storage_paths:
            for storage in storage_paths:
                if full_path.startswith(storage):
                    # Tìm đường dẫn lưu trữ phù hợp
                    real_path = full_path[len(storage):] if full_path.startswith(storage) else full_path
                    # Đảm bảo đường dẫn thực tế được bắt đầu bằng dấu gạch chéo
                    if not real_path.startswith('/'):
                        real_path = '/' + real_path
                    return storage, real_path
        
        # Nếu không có đường dẫn lưu trữ được khớp，Sử dụng phương thức phân chia mặc định
        parts = full_path.split('/', 2)
        if len(parts) >= 3:  # Định dạng phải là /dav/xxx/actual_path
            storage_path = f"/{parts[1]}/{parts[2]}" if parts[1] and parts[2] else ""
            actual_path = f"/{parts[3]}" if len(parts) > 3 and parts[3] else "/"
            return storage_path, actual_path
        
        # Không thể chia，Trả lại toàn bộ đường dẫn dưới dạng đường dẫn lưu trữ，Thư mục gốc được sử dụng làm đường dẫn thực tế
        return full_path, "/"
    
    def _convert_cron_format(self, cron_str):
        """Chuyển thànhcronĐịnh dạng biểu thức，Đảm bảo khả năng tương thích
        
        Args:
            cron_str (str): Biểu thức cron raw
            
        Returns:
            str: Biểu thức cron đã chuyển đổi
        """
        if not cron_str:
            return ""
            
        # alist_syncThông thường sử dụng biểu thức cron chuẩn, bạn có thể sử dụng trực tiếp
        return cron_str 