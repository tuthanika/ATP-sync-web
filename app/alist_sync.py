import http.client
import json
import re
from datetime import datetime, timedelta
import os
import logging
from typing import List, Dict, Optional, Union
from logging.handlers import TimedRotatingFileHandler
from typing import List, Tuple, Pattern
from urllib.parse import unquote

def normalize_filename(name: str) -> str:
    return unquote(name.strip())

def setup_logger():
    """Định cấu hình logger"""
    # Lấy thư mục nơi đặt tệp hiện tại
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Nhận thư mục gốc dự án
    project_root = os.path.dirname(current_dir)
    # Tạo thư mục nhật ký
    log_dir = os.path.join(project_root, 'data/log')
    os.makedirs(log_dir, exist_ok=True)

    # Đặt đường dẫn tệp nhật ký
    log_file = os.path.join(log_dir, 'alist_sync.log')

   # Tạo TimedRotatingFileHandler
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )

    # Tạo bộ xử lý bảng điều khiển
    console_handler = logging.StreamHandler()

    # Đặt định dạng nhật ký
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Định cấu hình logger gốc
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Tránh bổ sung nhiều bộ xử lý
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


# Khởi tạo logger
logger = setup_logger()


def parse_time_and_adjust_utc(date_str: str) -> datetime:
    """
    Chuỗi thời gian phân tích cú pháp，trong trường hợp củaUTCĐịnh dạng（Bao gồm'Z'）Thêm 8Giờ
    """
    iso_8601_pattern = r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?([+-]\d{2}:\d{2}|Z)?'
    match_iso = re.match(iso_8601_pattern, date_str)
    if match_iso:
        year, month, day, hour, minute, second, microsecond, timezone = match_iso.groups()
        if microsecond:
            microsecond = int(float(microsecond) * 1000000)
        else:
            microsecond = 0
        dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), microsecond)
        if timezone == "Z":
            dt = dt + timedelta(hours=8)  # UTCThời gian Thêm 8Giờ
        elif timezone:
            # Xử lý độ lệch múi giờ khác
            sign = 1 if timezone[0] == "+" else -1
            hours = int(timezone[1:3])
            minutes = int(timezone[4:6])
            offset = timedelta(hours=sign * hours, minutes=sign * minutes)
            dt = dt - offset
        return dt
    return None


class AlistSync:
    def __init__(self, base_url: str, username: str = None, password: str = None, token: str = None,
                 sync_delete_action: str = "none", exclude_list: List[str] = None, move_file_action: bool = False,
                 regex_patterns_list=None, regex_pattern=None, size_min: int = None, size_max: int = None,
                 task_list: List[str] = None):
        """
        khởi tạoAlistSyncloại
        
        tham số:
            base_url: Địa chỉ máy chủ AList/Openlist
            username: Tên người dùng
            password: mật khẩu
            token: Mã thông báo xác thực
            sync_delete_action: Cách xử lý các mục khác biệt trong thư mục đích
                - "none": Không xử lý sự khác biệt của thư mục đích
                - "move": Di chuyển đến thư mục trash của đích
                - "delete": Xóa các mục khác biệt trong thư mục đích
            exclude_list: Loại trừ danh sách thư mục
            move_file_action: Có nên di chuyển tệp nguồn không
            regex_patterns_list: Danh sách các mẫu biểu thức chính quy
            regex_pattern: Mẫu biểu thức chính quy
            size_min: Chỉ chuyển các tệp lớn hơn kích thước được chỉ định（Byte，mặc định tắt）
            size_max: Chỉ chuyển các tệp nhỏ hơn kích thước được chỉ định（Byte，mặc định tắt）
            task_list: Danh sách nhiệm vụ
        """
        if regex_patterns_list is None:
            regex_patterns_list = []
        self.base_url = base_url
        self.username = username
        self.password = password
        self.token = token  # Thêm thuộc tính mã thông báo
        self.sync_delete_action = sync_delete_action.lower()
        self.sync_delete = self.sync_delete_action in ["move", "delete"]
        self.connection = self._create_connection()
        self.task_list = task_list
        self.exclude_list = exclude_list
        self.move_file_action = move_file_action
        self.regex_patterns_list = regex_patterns_list
        self.regex_pattern = regex_pattern
        self.size_min = size_min
        self.size_max = size_max

    def _create_connection(self) -> Union[http.client.HTTPConnection, http.client.HTTPSConnection]:
        """Tạo HTTP(S)kết nối"""
        try:
            match = re.match(r"(?:http[s]?://)?([^:/]+)(?::(\d+))?", self.base_url)
            if not match:
                raise ValueError("Invalid base URL format")

            host = match.group(1)
            port_part = match.group(2)
            port = int(port_part) if port_part else (443 if self.base_url.startswith("https://") else 80)

            logger.info(f"Tạo một kết nối - Máy chủ: {host}, Cổng: {port}")
            return (http.client.HTTPSConnection(host, port)
                    if self.base_url.startswith("https://")
                    else http.client.HTTPConnection(host, port))
        except Exception as e:
            logger.error(f"Không tạo được kết nối: {str(e)}")
            raise

    def _make_request(self, method: str, path: str, headers: Dict = None,
                      payload: str = None) -> Optional[Dict]:
        """Gửi yêu cầu HTTP và trả về phản hồi JSON"""
        try:
            logger.debug(f"Gửi một yêu cầu - Phương thức: {method}, path: {path}")
            self.connection.request(method, path, body=payload, headers=headers)
            response = self.connection.getresponse()
            result = json.loads(response.read().decode("utf-8"))
            logger.debug(f"Yêu cầu phản hồi: {result}")
            return result
        except Exception as e:
            logger.error(f"Yêu cầu không thành công - Phương thức: {method}, path: {path}, sai lầm: {str(e)}")
            return None

    def login(self) -> bool:
        """Đăng nhập và nhận đượctoken"""
        # Nếu có mã thông báo, hãy trả về True trực tiếp
        if self.token and self.get_setting():
            return True

        # Nếu không, hãy đăng nhập bằng tên người dùng và mật khẩu
        if not self.username or not self.password:
            logger.error("tokenHoặc tên người dùng và mật khẩu không chính xác")
            return False

        payload = json.dumps({"username": self.username, "password": self.password})
        headers = {
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Content-Type": "application/json"
        }
        response = self._make_request("POST", "/api/auth/login", headers, payload)
        if response and response.get("data", {}).get("token"):
            self.token = response["data"]["token"]
            logger.info("Xác minh mã thông báo thành công")
            return True
        logger.error("Lấytokenthất bại")
        return False

    def get_setting(self) -> bool:
        """Xác minh tính chính xác của mã thông báo"""
        headers = {
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Content-Type": "application/json",
            "Authorization": self.token
        }
        response = self._make_request("GET", "/api/admin/setting/list", headers)
        if response and response.get("data", {}):
            token_value = None
            for item in response["data"]:
                if item["key"] == "token":
                    token_value = item["value"]
                    logger.info("Xác minh mã thông báo thành công")
                    break
            if self.token == token_value:
                logger.info("Xác minh mã thông báo thành công")
                return True
        logger.info("Xác minh mã thông báo không thành công")
        return False

    def _directory_operation(self, operation: str, **kwargs) -> Optional[Dict]:
        """Thực hiện các thao tác thư mục"""
        if not self.token:
            if not self.login():
                return None

        headers = {
            "Authorization": self.token,
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Content-Type": "application/json"
        }
        payload = json.dumps(kwargs)
        path = f"/api/fs/{operation}"
        return self._make_request("POST", path, headers, payload)

    def _task_operation(self, method: str, operation: str, **kwargs) -> Optional[Dict]:
        """Thực hiện các hoạt động nhiệm vụ"""
        if not self.token:
            if not self.login():
                return None

        headers = {
            "Authorization": self.token,
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Content-Type": "application/json"
        }
        payload = json.dumps(kwargs)
        path = f"/api/admin/task/{operation}"
        return self._make_request(method, path, headers, payload)

    def get_copy_task_undone(self):
        """Nhận các tác vụ sao chép chưa hoàn thànhh"""
        response = self._task_operation("GET", "copy/undone")
        name_list = []
        if response and response.get("data", []):
            for item in response["data"]:
                name = item["name"]
                result = name.replace("](", "")
                name_list.append(result)
        self.task_list = name_list
        return True
        # return name_list

    def get_copy_task_retry_failed(self) -> List[Dict]:
        """Hoàn thành các tác vụ sao chép"""
        response = self._task_operation("POST", "copy/retry_failed")
        return response.get("data", []) if response else []

    def get_copy_task_done(self) -> List[Dict]:
        """Hoàn thành các tác vụ sao chép"""
        response = self._task_operation("GET", "copy/done")
        return response.get("data", []) if response else []

    def get_directory_contents(self, directory_path: str) -> List[Dict]:
        """Nhận nội dung của thư mục"""
        response = self._directory_operation("list", path=directory_path)
        return response.get("data", {}).get("content", []) if response else []

    def create_directory(self, directory_path: str) -> bool:
        """Tạo một thư mục"""
        response = self._directory_operation("mkdir", path=directory_path)
        if response:
            logger.info(f"Thư mục【{directory_path}】Tạo thành công")
            return True
        logger.error("Tạo thư mục không thành công")
        return False

    def remove_empty_directory(self, directory_path: str) -> bool:
        """Xóa các thư mục trống"""
        response = self._directory_operation("remove_empty_directory", src_dir=directory_path)
        if response:
            logger.info(f"Xóa các thư mục trống【{directory_path}】thành công")
            return True
        logger.error("Không xóa một thư mục trống")
        return False

    # Xóa đệ quy các thư mục trống
    def _remove_empty_folders(self, base_dir: str, src_dir: str):
        if base_dir in src_dir and self.is_path_exists(src_dir):
            src_contents = self.get_directory_contents(src_dir)
            if src_contents:
                for item in src_contents:
                    if item.get('is_dir', False):
                        name = item.get('name', 'Dự án không xác định')
                        src_path = f"{src_dir}/{name}"
                        self._remove_empty_folders(base_dir, src_path)
            else:
                # Xóa các thư mục trống khi các tệp được di chuyển
                if base_dir != src_dir:
                    # Tìm cái cuối cùng / Chỉ số của
                    last_slash_index = src_dir.rfind('/')
                    # Chuỗi phân chia
                    remove_dir = src_dir[:last_slash_index]
                    remove_names = src_dir[last_slash_index + 1:]
                    self._directory_operation("remove", dir=remove_dir, names=[remove_names])
                    logger.info(f"Xóa các thư mục trống【{src_dir}】thành công")
                    self._remove_empty_folders(base_dir, remove_dir)

    def _copy_item(self, src_dir: str, dst_dir: str, item_name: str) -> bool:
        """Sao chép tệp hoặc thư mục"""
        response = self._directory_operation("copy",
                                             src_dir=src_dir,
                                             dst_dir=dst_dir,
                                             names=[item_name])
        if response:
            logger.info(f"tài liệu【{item_name}】Sao chép thành công")
            return True
        logger.error("Sao chép tệp không thành công")
        return False

    def _move_item(self, src_dir: str, dst_dir: str, item_name: str) -> bool:
        """Di chuyển các tập tin hoặc thư mục"""
        response = self._directory_operation("move",
                                             src_dir=src_dir,
                                             dst_dir=dst_dir,
                                             names=[item_name])
        if response:
            logger.info(f"Tệp từ【{src_dir}/{item_name}】Di chuyển đến【{dst_dir}/{item_name}】Thành công trên thiết bị di động")
            return True
        logger.error("Di chuyển tập tin không thành công")
        return False

    def is_path_exists(self, path: str) -> bool:
        """Kiểm tra xem đường dẫn tồn tại"""
        response = self._directory_operation("get", path=path)
        return bool(response and response.get("message") == "success")

    def get_storage_list(self) -> List[str]:
        """Nhận danh sách lưu trữ"""
        if not self.token:
            if not self.login():
                return []

        headers = {
            "Authorization": self.token,
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Content-Type": "application/json"
        }
        response = self._make_request("GET", "/api/admin/storage/list", headers)
        if response:
            storage_list = response["data"]["content"]
            return [item["mount_path"] for item in storage_list]
        logger.error("Không nhận được danh sách lưu trữ")
        return []

    def check_regex(self, path: str) -> bool:
        if self.regex_patterns_list:
            for regex in self.regex_patterns_list:
                if regex.match(path):
                    return True
        if self.regex_pattern and self.regex_pattern.match(path):
            return True
        return False

    def sync_directories(self, src_dir: str, dst_dir: str) -> bool:
        """Đồng bộ hóa hai thư mục"""
        try:

            # Thử lại nhiệm vụ thất bại
            self.get_copy_task_retry_failed()
            # Nhận nhiệm vụ đang chạy
            self.get_copy_task_undone()

            logger.info(f"Bắt đầu đồng bộ hóa thư mục - Thư mục nguồn: {src_dir}, Thư mục mục tiêu: {dst_dir}")
            if not self.is_path_exists(src_dir):
                logger.error(f"Thư mục nguồn【{src_dir}】Không tồn tại，Dừng đồng bộ hóa")
                return False
            result = self._recursive_copy(src_dir, dst_dir)
            # Xóa đệ quy các thư mục trống
            if self.move_file_action:
                self._remove_empty_folders(src_dir, src_dir)

            logger.info(f"Đồng bộ hóa thư mục được hoàn thành - Thư mục nguồn: {src_dir}, Thư mục mục tiêu: {dst_dir}, kết quả: {'thành công' if result else 'thất bại'}")
            return result
        except Exception as e:
            logger.error(f"Đồng bộ hóa thư mục không thành công: {str(e)}")
            return False

    def _recursive_copy(self, src_dir: str, dst_dir: str) -> bool:
        """Sao chép đệ quy nội dung thư mụcp"""
        try:
            if self.is_path_excluded(src_dir):
                logger.info(f"Loại trừ thư mục: {src_dir}, Bỏ qua đồng bộ hóa")
                return True
            logger.info(f"Bắt đầu sao chép đệ quy - Thư mục nguồn: {src_dir}, Thư mục mục tiêu: {dst_dir}")
            src_contents = self.get_directory_contents(src_dir)
            if not src_contents:
                logger.info(f"Thư mục nguồn trống hoặc nội dung không nhận được: {src_dir}")
                # return True

            if self.sync_delete:
                self._handle_sync_delete(src_dir, dst_dir, src_contents)
            if src_contents:
                for item in src_contents:
                    if not self._copy_item_with_check(src_dir, dst_dir, item):
                        logger.error(f"Không thể sao chép dự án: {item.get('name', 'Dự án không xác định')}")
                        return False
                logger.info(f"Sao chép đệ quy được hoàn thành - Thư mục nguồn: {src_dir}, Thư mục mục tiêu: {dst_dir}")
            return True
        except Exception as e:
            logger.error(f"sao chép đệ quy không thành công: {str(e)}")
        return False

    def _handle_sync_delete(self, src_dir: str, dst_dir: str, src_contents: List[Dict]):
        """
        Xử lý logic xóa đồng bộ
        
        tham số:
            src_dir: Thư mục nguồn
            dst_dir: Thư mục mục tiêu
            src_contents: Danh sách nội dung thư mục nguồn
            
        Cách xử lý:
            - "none": Không xử lý sự khác biệt của thư mục đích
            - "move": Di chuyển đến thư mục trash của đích
            - "delete": Xóa các mục khác biệt trong thư mục đích
        """
        try:
            # Nếu sự khác biệt không được xử lý，Trở lại trực tiếp
            if self.sync_delete_action == "none":
                logger.info("Chính sách xử lý khác biệt：Không xử lý sự khác biệt của thư mục đích")
                return
                
            dst_contents = self.get_directory_contents(dst_dir)
            src_names = {}
            if src_contents:
                src_names = {normalize_filename(item["name"]) for item in src_contents}

            dst_names = {}
            if dst_contents:
                dst_names = {normalize_filename(item["name"]) for item in dst_contents}

            if src_names:
                to_delete = set(dst_names) - set(src_names)
            else:
                to_delete = dst_names

            if not to_delete:
                logger.info("Không có mục khác biệt được xử lý")
                return

            # Chính sách xử lý hồ sơ
            if self.sync_delete_action == "move":
                logger.info("Chính sách xử lý khác biệt：Di chuyển đến thư mục trash của đích")
            elif self.sync_delete_action == "delete":
                logger.info("Chính sách xử lý khác biệt：Xóa các mục khác biệt trong thư mục đích")
                
            for name in to_delete:
                full_dst_path = f"{dst_dir.rstrip('/')}/{name}".replace("//", "/")
                if self.is_path_excluded(full_dst_path):
                    logger.info(f"Loại trừ thư mục: {full_dst_path}, Bỏ qua xóa")
                    continue

                if self.sync_delete_action == "move":
                    logger.info(f"Xử lý các dự án di động: {name}")
                    trash_dir = self._get_trash_dir(dst_dir)
                    if trash_dir:
                        if not self.is_path_exists(trash_dir):
                            logger.info(f"Tạo một thư mục Bin Recycle: {trash_dir}")
                            self.create_directory(trash_dir)
                        logger.info(f"Di chuyển đến thùng rác: {name}")
                        self._move_item(dst_dir, trash_dir, name)
                elif self.sync_delete_action == "delete":
                    logger.info(f"Quy trình đã xóa các mục: {name}")
                    logger.info(f"Xóa dự án trực tiếp: {name}")
                    self._directory_operation("remove", dir=dst_dir, names=[name])
        except Exception as e:
            logger.error(f"Không thể xử lý việc xóa đồng bộ: {str(e)}")

    def _get_trash_dir(self, dst_dir: str) -> Optional[str]:
        """Nhận đường dẫn thư mục Bin Recycle"""
        storage_list = self.get_storage_list()
        for mount_path in storage_list:
            if dst_dir.startswith(mount_path):
                return f"{mount_path}/trash{dst_dir[len(mount_path):]}"
        return None

    def close(self):
        """Đóng kết nối"""
        try:
            if hasattr(self, 'connection') and self.connection:
                self.connection.close()
                logger.debug("Kết nối được đóng lại")
        except Exception as e:
            logger.error(f"Xảy ra lỗi khi đóng kết nối: {str(e)}")

    def get_file_info(self, path: str) -> Optional[Dict]:
        """Nhận thông tin tập tin，Bao gồm kích thước và thời gian sửa đổi"""
        response = self._directory_operation("get", path=path)
        if response and response.get("message") == "success":
            return response.get("data", {})
        return None

    def _copy_item_with_check(self, src_dir: str, dst_dir: str, item: Dict) -> bool:
        """Sao chép dự án và kiểm tra nó"""
        try:
            item_name = item.get('name')
            if not item_name:
                logger.error("Tên dự án trống")
                return False
                
            src_path = f"{src_dir}/{item_name}".replace("//", "/")
            dst_path = f"{dst_dir}/{item_name}".replace("//", "/")

            if self.is_path_excluded(src_path) or self.is_path_excluded(dst_path):
                logger.info(f"Loại trừ các đường dẫn: {src_path} hoặc {dst_path}, Bỏ qua xử lý")
                return True

            if not item_name:
                logger.error("Tên dự án trống")
                return False

            logger.info(f"Dự án xử lý: {item_name}")

            # Xử lý các tập tin
            src_path = f"{src_dir}/{item_name}".replace('//', '/')
            dst_path = f"{dst_dir}/{item_name}".replace('//', '/')

            # Nếu đó là một thư mục，Xử lý đệ quy
            if item.get('is_dir', False):

                # Đảm bảo thư mục con mục tiêu tồn tại
                if not self.is_path_exists(dst_path):
                    logger.info(f"Tạo một thư mục con mục tiêu: {dst_path}")
                    if not self.create_directory(dst_path):
                        return False
                else:
                    logger.info(f"Thư mục【{dst_path}】Đã tồn tại，bỏ qua bước tạo")

                # Các thư mục con sao chép đệ quy
                return self._recursive_copy(src_path, dst_path)
            else:
                # Lọc kích thước tập tin
                file_size = item.get("size")
                if self.size_min is not None and file_size is not None and file_size < self.size_min:
                    logger.info(f"tài liệu【{item_name}】Nhỏ hơn kích thước chuyển tối thiểu({self.size_min}Byte)，Bỏ qua đồng bộ hóa")
                    return True
                if self.size_max is not None and file_size is not None and file_size > self.size_max:
                    logger.info(f"tài liệu【{item_name}】Lớn hơn kích thước truyền tối đa({self.size_max}Byte)，Bỏ qua đồng bộ hóa")
                    return True

                # Đánh giá biểu thức chính quy, nếu nó khớp với biểu thức chính quy, bỏ qua bước sao chép
                if(self.regex_patterns_list or self.regex_pattern):
                    if not self.check_regex(item_name):
                        logger.info(f"Không phù hợp với các biểu thức chính quy: {src_path}, Bỏ qua đồng bộ hóa")
                        return True

                    # Kiểm tra xem nó có nằm trong danh sách các nhiệm vụ còn dang dở không，Nếu có，Nhảy
                    self.get_copy_task_undone()
                    for task_item in self.task_list:
                        if src_dir in task_item and dst_dir in task_item and src_path in task_item:
                            logger.info(f"tài liệu【{item_name}】Trong danh sách các nhiệm vụ còn dang dở，Bỏ qua sao chép")
                            return True
                # Kiểm tra xem tệp đích có tồn tại không
                if not self.is_path_exists(dst_path):
                    logger.info(f"Sao chép tệp: {item_name}")
                    return self._copy_item(src_dir, dst_dir, item_name)
                else:
                    # Nhận thông tin tệp nguồn và mục tiêu
                    src_size = item.get("size")
                    dst_info = self.get_file_info(dst_path)

                    if not dst_info:
                        logger.error(f"Không lấy được thông tin tệp đích: {dst_path}")
                        return False

                    dst_size = dst_info.get("size")

                    # So sánh kích thước tệp
                    if src_size == dst_size:
                        logger.info(f"tài liệu【{item_name}】Đã tồn tại và có cùng kích thước，Bỏ qua sao chép")
                        if self.move_file_action:
                            if not self._directory_operation("remove", dir=src_dir, names=[item_name]):
                                logger.error(f"Không xóa tệp nguồn: {src_path}")
                                return False
                            else:
                                logger.info(f"Xóa thành công tệp nguồn: {src_path}")
                                return True
                        else:
                            return True
                    else:
                        # So sánh thời gian sửa đổi
                        src_modified = parse_time_and_adjust_utc(item.get("modified"))
                        dst_modified = parse_time_and_adjust_utc(dst_info.get("modified"))

                        if src_modified and dst_modified and dst_modified > src_modified:
                            logger.info(f"tài liệu【{item_name}】Tệp đích được sửa đổi sau tệp nguồn nên việc sao chép bị bỏ qua.")
                            if self.move_file_action:
                                if not self._directory_operation("remove", dir=src_dir, names=[item_name]):
                                    logger.error(f"Không xóa tệp nguồn: {src_dir}")
                                    return False
                                else:
                                    logger.error(f"Xóa các tập tin nguồn: {src_dir}")
                                    return True
                            else:
                                return True
                        else:
                            logger.info(f"tài liệu【{item_name}】Có một sự thay đổi，Xóa và sao chép lại")
                            # Xóa các tập tin cũ
                            if not self._directory_operation("remove", dir=dst_dir, names=[item_name]):
                                logger.error(f"Không xóa tệp đích: {dst_path}")
                                return False
                            # Sao chép tệp mới
                            return self._copy_item(src_dir, dst_dir, item_name)
        except Exception as e:
            logger.error(f"Xảy ra lỗi trong khi sao chép dự án: {str(e)}")
            return False
    def is_path_excluded(self, path: str) -> bool:
        """Kiểm tra xem path có nằm trong hoặc bên dưới bất kỳ thư mục loại trừ nào"""
        if not path or not self.exclude_list:
            return False
        normalized_path = path.rstrip("/")
        for exclude in self.exclude_list:
            exclude = exclude.rstrip("/")
            if normalized_path == exclude or normalized_path.startswith(exclude + "/"):
                return True
        return False

def get_dir_pairs_from_env() -> List[str]:
    """Nhận danh sách các cặp thư mục từ các biến môi trường"""
    dir_pairs_list = []

    # Nhận chínhDIR_PAIRS
    if dir_pairs := os.environ.get("DIR_PAIRS"):
        dir_pairs_list.extend(dir_pairs.split(";"))

    # LấyDIR_PAIRS1đếnDIR_PAIRS50
    for i in range(1, 51):
        if dir_pairs := os.environ.get(f"DIR_PAIRS{i}"):
            dir_pairs_list.extend(dir_pairs.split(";"))

    return dir_pairs_list


def main(dir_pairs: str = None, sync_del_action: str = None, exclude_dirs: str = None, move_file: bool = False,
         regex_patterns: str = None, size_min: int = None, size_max: int = None):
    """
    Chức năng chính，Để thực hiện dòng lệnh
    
    tham số:
        dir_pairs: Cặp thư mục, định dạng là "thư mục nguồn: thư mục đích", nhiều cặp thư mục được phân tách bằng dấu chấm phẩy
        sync_del_action: Cách xử lý các mục khác biệt trong thư mục đích
            - "none": Không xử lý sự khác biệt của thư mục đích（mặc định）
            - "move": Di chuyển đến thư mục trash của đích
            - "delete": Xóa các mục khác biệt trong thư mục đích
        exclude_dirs: Thư mục loại trừ，Nhiều thư mục được phân tách bằng dấu phẩy
        move_file: Có nên di chuyển tệp nguồn không，Mặc định làFalse
        regex_patterns: Mẫu biểu thức chính quy
        size_min: Chỉ chuyển các tệp lớn hơn kích thước được chỉ định（Byte，mặc định tắt）
        size_max: Chỉ chuyển các tệp nhỏ hơn kích thước được chỉ định（Byte，mặc định tắt）
    """
    code_souce()
    xiaojin()

    logger.info("Bắt đầu thực hiện các tác vụ đồng bộ hóa")
    # Nhận cấu hình từ biến môi trường 0
    base_url = os.environ.get("BASE_URL")
    username = os.environ.get("USERNAME")
    password = os.environ.get("PASSWORD")
    token = os.environ.get("TOKEN")  # Thêm tokenBiến môi trường

    # Có nên xóa các tệp dự phòng trong thư mục đích
    if sync_del_action:
        sync_delete_action = sync_del_action
    else:
        sync_delete_action = os.environ.get("SYNC_DELETE_ACTION", "none")
    
    # xác minhsync_delete_actionGiá trị có hợp lệ không?
    sync_delete_action = sync_delete_action.lower()
    if sync_delete_action not in ["none", "move", "delete"]:
        logger.warning(f"Phương thức xử lý sự khác biệt không hợp lệ: {sync_delete_action}，Giá trị mặc định sẽ được sử dụng: none")
        sync_delete_action = "none"
    else:
        logger.info(f"Phương thức xử lý thời hạn khác biệt: {sync_delete_action}")

    # Có nên xóa thư mục nguồn không
    if move_file:
        move_file_action = move_file
    else:
        move_file_action = os.environ.get("MOVE_FILE", "false").lower() == "true"

    # Xóa thư mục nguồn và xóa thư mục mục tiêu dự phòng không thể có hiệu lực cùng một lúc
    if move_file_action and sync_delete_action != "none":
        logger.warning("Không thể bật tệp nguồn và xử lý các khác biệt thư mục mục tiêu mục tiêu cùng một lúc，Vô hiệu hóa thư mục mục tiêu Xử lý mục khác nhau")
        sync_delete_action = "none"

    # Loại trừ thư mục
    if exclude_dirs:
        exclude_list = exclude_dirs.split(",")
    else:
        exclude_dirs = os.environ.get("EXCLUDE_DIRS", "")
        exclude_list = exclude_dirs.split(",")

    # biểu thức chính quy
    if not regex_patterns:
        regex_patterns = os.environ.get("REGEX_PATTERNS", None)
        # regex_patterns_list = regex_patterns.split(" ")
    # else:
    #     regex_patterns = os.environ.get("REGEX_PATTERNS", None)
    #     regex_patterns_list = regex_patterns.split(" ")

    # Khởi tạo một danh sách trống，Được sử dụng để lưu trữ các đối tượng biểu thức chính quy được biên dịch
    regex_and_replace_list: List[Pattern[str]] = []
    # if regex_patterns_list:
    #     for pattern_replacement in regex_patterns_list:
    #         try:
    #             compiled_pattern = re.compile(pattern_replacement)
    #             regex_and_replace_list.append(compiled_pattern)
    #         except re.error as e:
    #             print(f"biểu thức chính quy {pattern_replacement} không biên dịch được：{e}")
    regex_pattern = None
    try:
        if regex_patterns:
            regex_pattern = re.compile(regex_patterns)
        # regex_and_replace_list.append(compiled_pattern)
    except re.error as e:
        print(f"biểu thức chính quy {regex_patterns} không biên dịch được：{e}")

    # Giải quyết giới hạn kích thước tệp
    if size_min is None:
        size_min_env = os.environ.get("SIZE_MIN")
        size_min = int(size_min_env) if size_min_env and size_min_env.isdigit() else None
    if size_max is None:
        size_max_env = os.environ.get("SIZE_MAX")
        size_max = int(size_max_env) if size_max_env and size_max_env.isdigit() else None

    if not base_url:
        logger.error("Địa chỉ dịch vụ(BASE_URL)Biến môi trường không được đặt")
        return

    # Sửa đổi logic xác minh
    if not token and not (username and password):
        logger.error("Cần đặt mã thông báo(TOKEN)Hoặc đặt tên người dùng cùng một lúc(USERNAME)và mật khẩu(PASSWORD)")
        return

    logger.info(
        f"Thông tin cấu hình - URL: {base_url}, Tên người dùng: {username}, Chính sách xử lý khác biệt: {sync_delete_action}, Xóa thư mục nguồn: {move_file_action}")

   # Thêm tham số mã thông báo khi tạo phiên bản AlistSync
    alist_sync = AlistSync(base_url, username, password, token, sync_delete_action, exclude_list, move_file_action,
                           regex_and_replace_list, regex_pattern, size_min=size_min, size_max=size_max)
    # xác minh token Nó có đúng không
    if not alist_sync.login():
        logger.error("Mã thông báo không chính xác hoặc mật khẩu tên người dùng")
        return False
    try:
        # Nhận cặp thư mục đồng bộ
        dir_pairs_list = []
        if dir_pairs:
            dir_pairs_list.extend(dir_pairs.split(";"))
        else:
            dir_pairs_list = get_dir_pairs_from_env()

        logger.info(f"")
        logger.info(f"")
        num = 1
        for pair in dir_pairs_list:
            logger.info(f"No.{num:02d}【{pair}】")
            num += 1

        # Thực hiện đồng bộ hóa
        i = 1
        for pair in dir_pairs_list:
            src_dir, dst_dir = pair.split(":")
            logger.info(f"")
            logger.info(f"")
            logger.info(f"")
            logger.info(f"")
            logger.info(f"")
            logger.info(f"Các [{i:02d}] thư mục được đồng bộ hóa【{src_dir.strip()}】---->【 {dst_dir.strip()}】")
            logger.info(f"")
            logger.info(f"")
            i += 1
            alist_sync.sync_directories(src_dir.strip(), dst_dir.strip())

        logger.info("Tất cả các nhiệm vụ đồng bộ được hoàn thành")
    except Exception as e:
        logger.error(f"Xảy ra lỗi trong khi thực hiện một tác vụ đồng bộ: {str(e)}")
    finally:
        alist_sync.close()
        logger.info("Đóng kết nối，Nhiệm vụ kết thúc")


def code_souce():
    logger.info("ATP Sync Web！ https://github.com/tuthanika/ATP-sync-web")


def xiaojin():
    pt = """

                                   ..
                                  ....                       
                               .:----=:                      
                      ...:::---==-:::-+.                     
                  ..:=====-=+=-::::::==               .:-.   
              .-==*=-:::::::::::::::=*-:           .:-=++.   
           .-==++++-::::::::::::::-++:-==:.       .=-=::=-.  
   ....:::-=-::-++-:::::::::::::::--:::::==:      -:.:=..+:  
  ==-------::::-==-:::::::::::::::::::::::-+-.  .=:   .:=-.. 
  ==-::::+-:::::==-:::::::::::::::::::::::::=+.:+-    :-:    
   :--==+*::::::-=-::::::::::::::::::::::::::-*+:    .+.     
      ..-*:::::::==::::::::::::::::::::::::::-+.     -+.     
        -*:::::::-=-:::::::--:::::::::::::::=-.      +-      
        :*::::::::-=::::::-=:::::=:::::::::-:       .*.      
        .+=:::::::::::::::-::::-*-::......::        --       
         :+::-:::::::::::::::::*=:-::......         -.       
          :-:-===-:::::::::::.:+==--:......        .+.       
        .==:...-+#+::.......   .   .......         .=-       
        -*.....::............::-.                 ...=-      
        .==-:..       :=-::::::=.                  ..:+-     
          .:--===---=-:::-:::--:.                   ..:+:    
             =--+=:+*+:. ......                      ..-+.   
            .#. .+#- .:.                             .::=:   
             -=:.-:                                  ..::-.  
              .-=.               tuthanika           ...:-:  
               ...                                    ...:-  



    """
    logger.info(pt)


if __name__ == '__main__':
    main()