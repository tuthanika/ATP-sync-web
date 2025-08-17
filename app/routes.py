from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, session, flash
from app.utils.sync_manager import SyncManager
from app.utils.version_checker import get_current_version, has_new_version
import importlib.util
import os
import sys
import logging
from datetime import datetime
import json
import time
from werkzeug.utils import secure_filename
from app.utils.data_manager import DataManager
from app.alist_sync import AlistSync
import pytz
from functools import wraps

main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__)
auth_bp = Blueprint('auth', __name__)

# Bộ xử lý ngữ cảnh toàn cầu，Cung cấp thông tin phiên bản cho tất cả các mẫu
@main_bp.context_processor
def inject_version_info():
    has_update, current_version, latest_version = has_new_version()
    return {
        'current_version': current_version,
        'latest_version': latest_version if has_update else None,
        'has_update': has_update,
        'github_url': 'https://github.com/xjxjin/alist-sync',
        'gitee_url': 'https://gitee.com/xjxjin/alist-sync'
    }

# Định tuyến liên quan đến xác thực
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Trang đăng nhập"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Vui lòng nhập tên người dùng và mật khẩu của bạn', 'danger')
            return render_template('login.html')
        
        data_manager = current_app.config['DATA_MANAGER']
        user = data_manager.authenticate_user(username, password)
        
        if user:
            # Đặt dữ liệu phiên
            session['logged_in'] = True
            session['username'] = user['username']
            session['user_id'] = user['id']
            
            # Đăng nhập nhật ký
            data_manager.add_log({
                "level": "INFO",
                "message": f"Đăng nhập người dùng thành công: {username}",
                "details": {"ip": request.remote_addr}
            })
            
            return redirect(url_for('main.index'))
        else:
            flash('Tên người dùng hoặc mật khẩu không chính xác', 'danger')
            return render_template('login.html')
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """Đăng xuất"""
    if 'username' in session:
        username = session['username']
        # Đăng xuất nhật ký
        data_manager = current_app.config['DATA_MANAGER']
        data_manager.add_log({
            "level": "INFO",
            "message": f"Đăng xuất người dùng: {username}",
            "details": None
        })
    
    # Xóa phiên
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    """Trang hồ sơ người dùng"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'POST':
        action = request.form.get('action')
        username = session.get('username')
        
        if action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # Xác minh mật khẩu hiện tại
            if not data_manager.authenticate_user(username, current_password):
                flash('Mật khẩu hiện tại không chính xác', 'danger')
                return redirect(url_for('auth.profile'))
            
            # Xác minh mật khẩu mới
            if new_password != confirm_password:
                flash('Mật khẩu mới được nhập hai lần không nhất quán', 'danger')
                return redirect(url_for('auth.profile'))
            
            # Cập nhật mật khẩu
            data_manager.update_user_password(username, new_password)
            flash('Mật khẩu đã được cập nhật thành công', 'success')
            
        elif action == 'change_username':
            new_username = request.form.get('new_username')
            password = request.form.get('password')
            
            # Xác minh mật khẩu
            if not data_manager.authenticate_user(username, password):
                flash('Mật khẩu không chính xác', 'danger')
                return redirect(url_for('auth.profile'))
            
            # Cập nhật tên người dùng
            if data_manager.update_username(username, new_username):
                session['username'] = new_username
                flash('Tên người dùng đã được cập nhật thành công', 'success')
            else:
                flash('Cập nhật tên người dùng không thành công，Có lẽ tên người dùng đã tồn tại', 'danger')
    
    return render_template('profile.html')

@main_bp.route('/')
def index():
    """Trang chủ - Tổng quan và Bảng điều khiển giám sát"""
    # Thêm nhật ký kiểm tra
    data_manager = current_app.config['DATA_MANAGER']
    try:
        data_manager.add_log({
            "level": "INFO",
            "message": "Truy cập Trang chủ",
            "details": {"ip": request.remote_addr, "user_agent": request.user_agent.string}
        })
    except Exception as e:
        current_app.logger.error(f"Ghi nhật ký không thành công: {str(e)}")
    return render_template('index.html')

@main_bp.route('/connections')
def connections():
    """Trang quản lý kết nối"""
    data_manager = current_app.config['DATA_MANAGER']
    connections = data_manager.get_connections()
    return render_template('connections.html', connections=connections)

@main_bp.route('/tasks')
def tasks():
    """Trang quản lý nhiệm vụ"""
    data_manager = current_app.config['DATA_MANAGER']
    tasks = data_manager.get_tasks()
    return render_template('tasks.html', tasks=tasks)

@main_bp.route('/task-instances')
def task_instances():
    """Trang phiên bản tác vụ"""
    data_manager = current_app.config['DATA_MANAGER']
    instances = data_manager.get_task_instances(None, 100)  # Hiển thị 100 bản ghi phiên bản mới nhất
    return render_template('task_instances.html', instances=instances)

@main_bp.route('/settings')
def settings():
    """Trang Cài đặt"""
    data_manager = current_app.config['DATA_MANAGER']
    settings = data_manager.get_settings()
    return render_template('settings.html', settings=settings)

@main_bp.route('/logs')
def logs():
    """Trang xem Nhật ký"""
    data_manager = current_app.config['DATA_MANAGER']
    logs = data_manager.get_logs()
    return render_template('logs.html', logs=logs)

# API lộ trình
@api_bp.route('/connections', methods=['GET', 'POST'])
def api_connections():
    """kết nối API"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'POST':
        connection_data = request.json
        data_manager.add_connection(connection_data)
        return jsonify({"status": "success", "message": "Kết nối được Thêm "})
    
    return jsonify(data_manager.get_connections())

@api_bp.route('/connections/<int:conn_id>', methods=['GET', 'PUT', 'DELETE'])
def api_connection(conn_id):
    """Kết nối đơn API"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'PUT':
        connection_data = request.json
        # Nhật ký gỡ lỗi：Dữ liệu kết nối cập nhật đầu ra
        current_app.logger.debug(f"Cập nhật dữ liệu kết nối: {json.dumps(connection_data)}")
        
        # Đảm bảo trường trạng thái tồn tại
        if 'status' not in connection_data:
            connection_data['status'] = 'offline'
            current_app.logger.debug("Không có trạng thái kết nối được chỉ định，Đặt nhưoffline")
        
        data_manager.update_connection(conn_id, connection_data)
        return jsonify({"status": "success", "message": "Kết nối đã được cập nhật"})
    
    elif request.method == 'DELETE':
        data_manager.delete_connection(conn_id)
        return jsonify({"status": "success", "message": "Kết nối đã bị xóa"})
    
    # Phương thức GET - Lấy thông tin kết nối
    connection = data_manager.get_connection(conn_id)
    if connection:
        # Tạo đối tượng dữ liệu được trả về，Bao gồm tất cả thông tin（Bao gồm cả mật khẩu）
        return jsonify(connection)
    
    return jsonify({"status": "error", "message": "Kết nối không tồn tại"}), 404

@api_bp.route('/test-connection', methods=['POST'])
def test_connection():
    """Kiểm tra giao diện kết nối"""
    try:
        data = request.get_json()
        conn_id = data.get('connection_id') # Lấy ID kết nối, nếu có
        
        # Nhật ký nhật ký kết nối nhật ký
        data_manager = current_app.config['DATA_MANAGER']
        
        # Ghi lại dữ liệu yêu cầu để ghi nhật ký（Để gỡ lỗi）
        current_app.logger.debug(f"Kiểm tra dữ liệu yêu cầu kết nối: {json.dumps(data)}")
        
        data_manager.add_log({
            "level": "INFO",
            "message": f"Kết nối kiểm tra: {data.get('server', '')}",
            "details": {"username": data.get('username')}
        })
        
        # Tạo một phiên bản AlistSync để kiểm tra kết nối
        alist = AlistSync(
            data.get('server'),
            data.get('username'),
            data.get('password'),
            data.get('token')
        )
        
        # Thử đăng nhập để xác minh kết nối
        login_success = alist.login()
        
        if login_success:
            # Nhận mã thông báo sau khi thử nghiệm thành công
            token = alist.token
            
            # Cập nhật trạng thái kết nối lên trực tuyến，Và lưu mã thông báo
            if conn_id:
                conn = data_manager.get_connection(int(conn_id))
                if conn:
                    conn['status'] = 'online'
                    conn['token'] = token  # gia hạntoken
                    data_manager.update_connection(int(conn_id), conn)
                    current_app.logger.debug(f"Cập nhật trạng thái kết nối lên trực tuyến: {conn_id}")
            
            # Kết nối thành công
            data_manager.add_log({
                "level": "INFO",
                "message": f"Kiểm tra kết nối thành công: {data.get('server', '')}",
                "details": {"username": data.get('username')}
            })
            
            response_data = {
                "status": "success",
                "message": "Kiểm tra kết nối thành công",
                "data": {
                    "token": token,
                    "connection_status": "online"
                }
            }
            current_app.logger.debug(f"Kiểm tra dữ liệu phản hồi kết nối: {json.dumps(response_data)}")
            return jsonify(response_data)
        else:
            # Cập nhật trạng thái kết nối như ngoại tuyến
            if conn_id:
                conn = data_manager.get_connection(int(conn_id))
                if conn:
                    conn['status'] = 'offline'
                    data_manager.update_connection(int(conn_id), conn)
                    current_app.logger.debug(f"Cập nhật trạng thái kết nối như ngoại tuyến: {conn_id}")
            
            # Kết nối không thành công
            data_manager.add_log({
                "level": "ERROR",
                "message": f"Kiểm tra kết nối không thành công: {data.get('server', '')}",
                "details": {"username": data.get('username'), "error": "Xác minh đăng nhập không thành công"}
            })
            
            response_data = {
                "status": "error",
                "message": "Kiểm tra kết nối không thành công：Lỗi xác minh，Vui lòng kiểm tra địa chỉ máy chủ、Tên người dùng、Mật khẩu hoặc mã thông báo",
                "data": {
                    "connection_status": "offline"
                }
            }
            current_app.logger.debug(f"Kiểm tra dữ liệu phản hồi kết nối: {json.dumps(response_data)}")
            return jsonify(response_data)
    except Exception as e:
        # Nếu có kết nốiID，Cập nhật trạng thái của nó như ngoại tuyến
        if 'data' in locals() and 'conn_id' in data and data['conn_id']:
            if 'data_manager' in locals():
                conn = data_manager.get_connection(int(data['conn_id']))
                if conn:
                    conn['status'] = 'offline'
                    data_manager.update_connection(int(data['conn_id']), conn)
        
        # Một ngoại lệ đã xảy ra
        if 'data_manager' in locals():
            data_manager.add_log({
                "level": "ERROR",
                "message": f"Ngoại lệ kiểm tra kết nối: {data.get('server', '') if 'data' in locals() else 'unknown'}",
                "details": {"error": str(e)}
            })
        
        return jsonify({
            "status": "error",
            "message": f"Kiểm tra kết nối không thành công: {str(e)}",
            "data": {
                "connection_status": "offline"
            }
        }), 500
    finally:
        # Đảm bảo đóng kết nối
        if 'alist' in locals():
            alist.close()

@api_bp.route('/tasks', methods=['GET', 'POST'])
def api_tasks():
    """Nhiệm vụ API"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'POST':
        task_data = request.json
        
        # Hãy chắc chắnconnection_idĐó là một loại số nguyên
        if 'connection_id' in task_data:
            try:
                task_data['connection_id'] = int(task_data['connection_id'])
            except (ValueError, TypeError):
                # Nếu nó không thể được chuyển đổi thành số nguyên，Thử cài đặt vào kết nối có sẵn đầu tiênID
                connections = data_manager.get_connections()
                if connections:
                    task_data['connection_id'] = connections[0].get('connection_id')
                else:
                    task_data['connection_id'] = None
        
        data_manager.add_task(task_data)
        
        # Nếu nhiệm vụ được thêm thành công，Thêm tác vụ vào Lập lịch
        if 'SYNC_MANAGER' in current_app.config and task_data.get("schedule"):
            task_id = task_data.get("id")
            if not task_id:
                # Nếu không có dữ liệu nhiệm vụID，Nhận các nhiệm vụ mới nhất
                tasks = data_manager.get_tasks()
                if tasks:
                    task_id = tasks[-1].get("id")
            
            if task_id:
                sync_manager = current_app.config['SYNC_MANAGER']
                updated_task = data_manager.get_task(task_id)
                if updated_task:
                    # Thêm tác vụ vào Lập lịch
                    sync_manager.schedule_task(updated_task)
                    current_app.logger.info(f"Nhiệm vụ mới {task_id} Thêm  lịch trình")
        
        return jsonify({"status": "success", "message": "Nhiệm vụ được Thêm "})
    
    return jsonify(data_manager.get_tasks())

@api_bp.route('/tasks/<int:task_id>', methods=['GET', 'PUT', 'DELETE'])
def api_task(task_id):
    """Nhiệm vụ duy nhất API"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'PUT':
        task_data = request.json
        
        # Hãy chắc chắnconnection_idĐó là một loại số nguyên
        if 'connection_id' in task_data:
            try:
                task_data['connection_id'] = int(task_data['connection_id'])
            except (ValueError, TypeError):
                # Nếu nó không thể được chuyển đổi thành số nguyên，Thử cài đặt vào kết nối có sẵn đầu tiênID
                connections = data_manager.get_connections()
                if connections:
                    task_data['connection_id'] = connections[0].get('connection_id')
                else:
                    task_data['connection_id'] = None
        
        data_manager.update_task(task_id, task_data)
        return jsonify({"status": "success", "message": "Nhiệm vụ được cập nhật"})
    
    elif request.method == 'DELETE':
        data_manager.delete_task(task_id)
        return jsonify({"status": "success", "message": "Nhiệm vụ đã xóa"})
    
    return jsonify(data_manager.get_task(task_id))

@api_bp.route('/tasks/<int:task_id>/run', methods=['POST'])
def api_run_task(task_id):
    """Chạy nhiệm vụ ngay bây giờ"""
    try:
        # Nhận thông tin nhiệm vụ
        data_manager = current_app.config['DATA_MANAGER']
        task = data_manager.get_task(task_id)
        
        if not task:
            return jsonify({
                "status": "error", 
                "message": f"Nhiệm vụ không tồn tại: {task_id}"
            }), 404
        
        # Nhật ký nhật ký khởi động tác vụ
        data_manager.add_log({
            "level": "INFO",
            "message": f"Bắt đầu nhiệm vụ theo cách thủ công: {task.get('name', f'Nhiệm vụ {task_id}')}",
            "details": {"task_id": task_id, "from": request.remote_addr}
        })
        
        # Tạo trình quản lý đồng bộ hóa và chạy các tác vụ
        sync_manager = SyncManager()
        result = sync_manager.run_task(task_id)
        
        # Ghi lại kết quả hoạt động nhiệm vụ
        if result.get("status") == "success":
            data_manager.add_log({
                "level": "INFO",
                "message": f"Nhiệm vụ bắt đầu thành công: {task.get('name', f'Nhiệm vụ {task_id}')}",
                "details": {"task_id": task_id, "instance_id": result.get("instance_id")}
            })
        else:
            data_manager.add_log({
                "level": "ERROR",
                "message": f"Nhiệm vụ không bắt đầu: {task.get('name', f'Nhiệm vụ {task_id}')}",
                "details": {"task_id": task_id, "error": result.get("message")}
            })
        
        return jsonify(result)
    except Exception as e:
        # Ghi lại ngoại lệ
        if 'data_manager' in locals() and 'task' in locals():
            data_manager.add_log({
                "level": "ERROR",
                "message": f"Nhiệm vụ bắt đầu ngoại lệ: {task.get('name', f'Nhiệm vụ {task_id}')}",
                "details": {"task_id": task_id, "error": str(e)}
            })
        
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Nhiệm vụ bắt đầu ngoại lệ: {error_details}")
        
        return jsonify({
            "status": "error",
            "message": f"Nhiệm vụ không chạy: {str(e)}"
        }), 500

@api_bp.route('/task-instances', methods=['GET'])
def api_task_instances():
    """Nhận danh sách các phiên bản nhiệm vụ"""
    data_manager = current_app.config['DATA_MANAGER']
    task_id = request.args.get('task_id')
    limit = request.args.get('limit', 50, type=int)
    
    if task_id:
        # Nhận một thể hiện của tác vụ được chỉ định
        instances = data_manager.get_task_instances(int(task_id), limit)
    else:
        # Nhận các trường hợp của tất cả các nhiệm vụ
        instances = data_manager.get_task_instances(None, limit)
    
    return jsonify(instances)

@api_bp.route('/task-instances/<int:instance_id>', methods=['GET'])
def api_task_instance(instance_id):
    """Nhận một phiên bản tác vụ duy nhất"""
    data_manager = current_app.config['DATA_MANAGER']
    instance = data_manager.get_task_instance(instance_id)
    
    if not instance:
        return jsonify({"status": "error", "message": "Phiên bản nhiệm vụ không tồn tại"}), 404
    
    return jsonify(instance)

@api_bp.route('/task-instances/<int:instance_id>/logs', methods=['GET'])
def api_task_instance_logs(instance_id):
    """Nhận nhật ký của phiên bản tác vụ"""
    data_manager = current_app.config['DATA_MANAGER']
    instance = data_manager.get_task_instance(instance_id)
    
    if not instance:
        return jsonify({"status": "error", "message": "Phiên bản nhiệm vụ không tồn tại"}), 404
    
    task_id = instance.get('task_id')
    logs = data_manager.get_task_log(task_id, instance_id)
    
    return jsonify({
        "status": "success",
        "instance_id": instance_id,
        "task_id": task_id,
        "logs": logs
    })

@api_bp.route('/settings', methods=['GET', 'PUT'])
def api_settings():
    """cài đặt API"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'PUT':
        settings_data = request.json
        data_manager.update_settings(settings_data)
        return jsonify({"status": "success", "message": "Cài đặt được cập nhật"})
    
    return jsonify(data_manager.get_settings())

@api_bp.route('/storages', methods=['GET'])
def get_storages():
    """Nhận danh sách lưu trữ"""
    try:
        conn_id = request.args.get('conn_id')
        if not conn_id:
            return jsonify({"status": "error", "message": "Thiếu kết nốiIDtham số"}), 400
        
        #Nhật ký yêu cầu ghi âm
        data_manager = current_app.config['DATA_MANAGER']
        data_manager.add_log({
            "level": "INFO",
            "message": f"Nhận kết nối {conn_id} Danh sách lưu trữ",
            "details": {"request_from": request.remote_addr}
        })
        
        # Hãy thử chuyển đổi conn_id thành số nguyên
        try:
            conn_id = int(conn_id)
        except (ValueError, TypeError):
            data_manager.add_log({
                "level": "ERROR",
                "message": f"Định dạng ID kết nối không đúng",
                "details": {"error": f"ID kết nối không hợp lệ: {conn_id}"}
            })
            return jsonify({"status": "error", "message": f"ID kết nối không hợp lệ: {conn_id}"}), 400
        
        # Nhận thông tin kết nối, sử dụng trường connection_id
        connection = data_manager.get_connection(conn_id)
        
        if not connection:
            data_manager.add_log({
                "level": "ERROR",
                "message": f"Không nhận được danh sách lưu trữ",
                "details": {"error": f"Không tìm thấy kết nối có ID {conn_id}"}
            })
            return jsonify({"status": "error", "message": f"Không tìm thấy kết nối có ID {conn_id}"}), 404
        
        # Tạo một phiên bản AlistSync
        alist = AlistSync(
            connection.get('server'),
            connection.get('username'),
            connection.get('password'),
            connection.get('token')
        )
        
        # Cố gắng đăng nhập
        login_success = alist.login()
        if not login_success:
            data_manager.add_log({
                "level": "ERROR",
                "message": f"Không nhận được danh sách lưu trữ",
                "details": {"error": "Đăng nhập không thành công", "connection_id": conn_id}
            })
            return jsonify({"status": "error", "message": "Đăng nhập không thành công，Không thể có được danh sách lưu trữ"}), 401
        
        try:
            # Nhận danh sách lưu trữ
            storage_list = alist.get_storage_list()
            
            # Nếu kết quả không phải là danh sách，Chuyển thành
            if not isinstance(storage_list, list):
                storage_list = []
            
            # Danh sách lưu trữ định dạng
            formatted_storages = []
            for storage in storage_list:
                # Nếu đó là định dạng từ điển
                if isinstance(storage, dict):
                    if 'mount_path' in storage:
                        formatted_storages.append({
                            'id': storage.get('mount_path', ''),
                            'name': storage.get('mount_path', '') + (f" ({storage.get('remark', '')})" if storage.get('remark') else '')
                        })
                    elif 'id' in storage and 'name' in storage:
                        formatted_storages.append(storage)
                    else:
                        # Sử dụng giá trị đầu tiên của từ điển làIDvà tên
                        storage_id = next(iter(storage.values()), '')
                        formatted_storages.append({
                            'id': storage_id,
                            'name': storage_id
                        })
                # Nếu đó là định dạng chuỗi
                elif isinstance(storage, str):
                    formatted_storages.append({
                        'id': storage,
                        'name': storage
                    })
            
            if not formatted_storages:
                data_manager.add_log({
                    "level": "WARNING",
                    "message": f"Nhận kết nối {conn_id} Danh sách lưu trữ trống",
                    "details": {"connection_id": conn_id}
                })
                return jsonify({
                    "status": "success", 
                    "data": [],
                    "message": "Danh sách lưu trữ trống"
                })
            
            # Ghi lại nhật ký thành công
            data_manager.add_log({
                "level": "INFO",
                "message": f"Nhận kết nối {conn_id} Danh sách lưu trữ thành công",
                "details": {"count": len(formatted_storages)}
            })
            
            return jsonify({
                "status": "success", 
                "data": formatted_storages
            })
        except Exception as e:
            data_manager.add_log({
                "level": "ERROR",
                "message": f"Không xử lý dữ liệu danh sách được lưu trữ",
                "details": {"error": str(e), "connection_id": conn_id}
            })
            import traceback
            error_details = traceback.format_exc()
            current_app.logger.error(f"Xử lý các trường hợp ngoại lệ danh sách lưu trữ: {error_details}")
            return jsonify({"status": "error", "message": f"Không xử lý dữ liệu danh sách được lưu trữ: {str(e)}"}), 500
            
    except Exception as e:
        # Ghi lại lỗi
        if 'data_manager' in locals():
            data_manager.add_log({
                "level": "ERROR",
                "message": f"Không nhận được danh sách lưu trữ",
                "details": {"error": str(e), "connection_id": conn_id if 'conn_id' in locals() else None}
            })
        
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Nhận danh sách lưu trữ ngoại lệ: {error_details}")
        
        return jsonify({"status": "error", "message": f"Không nhận được danh sách lưu trữ: {str(e)}"}), 500
    finally:
        # Đảm bảo đóng kết nối
        if 'alist' in locals():
            alist.close()

@api_bp.route('/storages_all', methods=['GET'])
def get_all_storages():
    """Nhận danh sách lưu trữ cho tất cả các kết nối"""
    try:
        data_manager = current_app.config['DATA_MANAGER']
        
        #Nhật ký yêu cầu ghi âm
        data_manager.add_log({
            "level": "INFO",
            "message": "Nhận danh sách lưu trữ cho tất cả các kết nối",
            "details": {"request_from": request.remote_addr}
        })
        
        # Nhận tất cả các kết nối
        connections = data_manager.get_connections()
        
        if not connections:
            data_manager.add_log({
                "level": "WARNING",
                "message": "Không có kết nối có sẵn"
            })
            return jsonify({
                "status": "success",
                "data": [],
                "message": "Không có kết nối có sẵn"
            })
        
        # Lưu trữ tất cả các kết nối trong danh sách lưu trữ
        all_storages = []
        
        # Lặp lại thông qua tất cả các kết nối
        for connection in connections:
            conn_id = connection.get('connection_id')
            
            # Tạo một phiên bản AlistSync
            alist = None
            try:
                alist = AlistSync(
                    connection.get('server'),
                    connection.get('username'),
                    connection.get('password'),
                    connection.get('token')
                )
                
                # Cố gắng đăng nhập
                login_success = alist.login()
                if not login_success:
                    data_manager.add_log({
                        "level": "WARNING",
                        "message": f"kết nối {conn_id} Đăng nhập không thành công",
                        "details": {"connection_id": conn_id, "name": connection.get('name')}
                    })
                    continue
                
                # Nhận danh sách lưu trữ
                storage_list = alist.get_storage_list()
                
                # Nếu kết quả không phải là danh sách, hãy bỏ qua
                if not isinstance(storage_list, list) or not storage_list:
                    continue
                
                # Thêm  tổng số danh sách
                for storage in storage_list:
                    if isinstance(storage, str):
                        all_storages.append({
                            'id': storage,
                            'name': storage,
                            'connection_id': conn_id,
                            'connection_name': connection.get('name')
                        })
            except Exception as e:
                data_manager.add_log({
                    "level": "WARNING",
                    "message": f"Nhận kết nối {conn_id} Danh sách lưu trữ không thành công",
                    "details": {"error": str(e), "connection_id": conn_id}
                })
                continue
            finally:
                # Đảm bảo đóng kết nối
                if alist:
                    alist.close()
        
        # Ghi lại nhật ký thành công
        data_manager.add_log({
            "level": "INFO",
            "message": "Nhận danh sách lưu trữ của tất cả các kết nối thành công",
            "details": {"count": len(all_storages)}
        })
        
        return jsonify({
            "status": "success",
            "data": all_storages
        })
            
    except Exception as e:
        # Ghi lại lỗi
        if 'data_manager' in locals():
            data_manager.add_log({
                "level": "ERROR",
                "message": "Không nhận được tất cả các danh sách lưu trữ",
                "details": {"error": str(e)}
            })
        
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Nhận tất cả các ngoại lệ danh sách lưu trữ: {error_details}")
        
        return jsonify({"status": "error", "message": f"Không nhận được tất cả các danh sách lưu trữ: {str(e)}"}), 500

@api_bp.route('/dashboard/stats', methods=['GET'])
def dashboard_stats():
    """Nhận thống kê bảng điều khiển"""
    try:
        data_manager = current_app.config['DATA_MANAGER']
        
        # Nhận số lượng kết nối
        connections = data_manager.get_connections()
        connection_count = len(connections)
        
        # Nhận số và trạng thái của các tác vụ
        tasks = data_manager.get_tasks()
        task_count = len(tasks)
        
        # Đếm số lượng nhiệm vụ ở các tiểu bang khác nhau
        completed_task_count = sum(1 for task in tasks if task.get('status') == 'completed')
        running_task_count = sum(1 for task in tasks if task.get('status') == 'running')
        failed_task_count = sum(1 for task in tasks if task.get('status') == 'failed')
        pending_task_count = task_count - completed_task_count - running_task_count - failed_task_count
        
        # Nhận số lượng các tác vụ hoạt động
        active_task_count = running_task_count
        
        # Nhận số lượng các tệp được đồng bộ hóa（Thống kê từ phiên bản tác vụ）
        synced_files_count = 0
        task_instances = data_manager.get_task_instances(None, 100)
        for instance in task_instances:
            if instance.get('status') == 'completed':
                result = instance.get('result', {})
                if result.get('details') and 'total' in result.get('details', {}):
                    synced_files_count += result.get('details', {}).get('total', 0)
        
        # Phân phối loại kết nối thống kê
        connection_types = []
        connection_type_counts = []
        connection_type_map = {}
        
        for conn in connections:
            server_url = conn.get('server', '')
            if '/dav/aliyundrive' in server_url or 'alipan' in server_url:
                conn_type = 'Alibaba Cloud Drive'
            elif '/dav/baidu' in server_url or 'pan.baidu' in server_url:
                conn_type = 'Baidu Netdisk'
            elif '/dav/quark' in server_url or 'quark' in server_url:
                conn_type = 'Quark Netdisk'
            elif '/dav/189cloud' in server_url or '189' in server_url:
                conn_type = 'Đĩa đám mây Tianyi'
            elif '/dav/onedrive' in server_url or 'onedrive' in server_url:
                conn_type = 'OneDrive'
            else:
                conn_type = 'khác'
            
            if conn_type in connection_type_map:
                connection_type_map[conn_type] += 1
            else:
                connection_type_map[conn_type] = 1
        
        for conn_type, count in connection_type_map.items():
            connection_types.append(conn_type)
            connection_type_counts.append(count)
        
        # Thời gian thực hiện nhiệm vụ thống kê
        task_duration_labels = ['Ít hơn 1phút', '1-5phút', '5-15phút', '15-30phút', '30phút以上']
        task_duration_counts = [0, 0, 0, 0, 0]
        
        for instance in task_instances:
            if instance.get('status') == 'completed' and instance.get('start_time') and instance.get('end_time'):
                duration_seconds = instance.get('end_time') - instance.get('start_time')
                if duration_seconds < 60:
                    task_duration_counts[0] += 1
                elif duration_seconds < 300:
                    task_duration_counts[1] += 1
                elif duration_seconds < 900:
                    task_duration_counts[2] += 1
                elif duration_seconds < 1800:
                    task_duration_counts[3] += 1
                else:
                    task_duration_counts[4] += 1
        
        # Thống kê tỷ lệ thành công của từng nhiệm vụ
        success_rate_labels = []
        success_rate_values = []
        
        task_success_map = {}
        task_total_map = {}
        
        for instance in task_instances:
            task_id = instance.get('task_id')
            task_name = instance.get('task_name')
            
            if task_id not in task_total_map:
                task_total_map[task_id] = 0
                task_success_map[task_id] = 0
            
            task_total_map[task_id] += 1
            if instance.get('status') == 'completed':
                task_success_map[task_id] += 1
        
        # Nhận danh sách nhiệm vụ và sắp xếp theo tỷ lệ thành công
        task_success_rate = []
        for task in tasks[:5]:  # Chỉ thực hiện 5 nhiệm vụ đầu tiên
            task_id = task.get('id')
            if task_id in task_total_map and task_total_map[task_id] > 0:
                success_rate = round((task_success_map.get(task_id, 0) / task_total_map[task_id]) * 100)
                task_success_rate.append({
                    'name': task.get('name'),
                    'rate': success_rate
                })
        
        # Sắp xếp theo tỷ lệ thành công và chuẩn bị dữ liệu
        task_success_rate.sort(key=lambda x: x['rate'], reverse=True)
        for item in task_success_rate:
            success_rate_labels.append(item['name'])
            success_rate_values.append(item['rate'])
        
        # Nhận các nhiệm vụ mới nhất
        recent_tasks = sorted(tasks, key=lambda x: x.get('last_run', ''), reverse=True)[:5]
        
        return jsonify({
            "status": "success",
            "data": {
                "connection_count": connection_count,
                "task_count": task_count,
                "active_task_count": active_task_count,
                "synced_files_count": synced_files_count,
                "completed_task_count": completed_task_count,
                "running_task_count": running_task_count,
                "failed_task_count": failed_task_count,
                "pending_task_count": pending_task_count,
                "connection_types": connection_types,
                "connection_type_counts": connection_type_counts,
                "task_duration_labels": task_duration_labels,
                "task_duration_counts": task_duration_counts,
                "success_rate_labels": success_rate_labels,
                "success_rate_values": success_rate_values,
                "recent_tasks": recent_tasks
            }
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Việc lấy dữ liệu bảng điều khiển là bất thường: {error_details}")
        
        return jsonify({
            "status": "error",
            "message": f"Không nhận được dữ liệu bảng điều khiển: {str(e)}"
        }), 500

@api_bp.route('/scheduler/status', methods=['GET'])
def scheduler_status():
    """Nhận trạng thái Lập lịch"""
    try:
        # Kiểm tra xem bộ lập lịch có tồn tại trong cấu hình ứng dụng không
        sync_manager = current_app.config.get('SYNC_MANAGER')
        if not sync_manager:
            return jsonify({
                "status": "error",
                "message": "Bộ lập lịch không được khởi tạo",
                "running": False,
                "jobs": []
            })
        
        # Nhận nhiệm vụ trong lịch trình
        scheduler = sync_manager.scheduler
        jobs = scheduler.get_jobs()
        
        job_info = []
        for job in jobs:
            job_info.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        
        return jsonify({
            "status": "success",
            "message": "Bộ lập lịch đang chạy",
            "running": scheduler.running,
            "job_count": len(jobs),
            "jobs": job_info
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Nhận ngoại lệ trạng thái Lập lịch: {error_details}")
        
        return jsonify({
            "status": "error",
            "message": f"Không nhận được trạng thái Lập lịch trình: {str(e)}",
            "running": False,
            "jobs": []
        }), 500

@api_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def api_update_task(task_id):
    """Cập nhật nhiệm vụ"""
    data_manager = current_app.config['DATA_MANAGER']
    task_data = request.json
    
    # Cập nhật nhiệm vụ
    if data_manager.update_task(task_id, task_data):
        # Nếu tác vụ được cập nhật thành công，Tải lại tác vụ cho Trình lập lịch
        if 'SYNC_MANAGER' in current_app.config:
            sync_manager = current_app.config['SYNC_MANAGER']
            
            # Nhận các nhiệm vụ cập nhật
            updated_task = data_manager.get_task(task_id)
            if updated_task:
                # Sắp xếp lại nhiệm vụ
                sync_manager.schedule_task(updated_task)
                current_app.logger.info(f"Nhiệm vụ {task_id} Lên lịch lại")
                
                # Đăng nhập
                data_manager.add_log({
                    "level": "INFO",
                    "message": f"Các nhiệm vụ đã được cập nhật và sắp xếp lại: {updated_task.get('name')}",
                    "details": {"task_id": task_id}
                })
        
        return jsonify({"status": "success", "message": "Nhiệm vụ được cập nhật"})
    
    return jsonify({"status": "error", "message": "Cập nhật nhiệm vụ không thành công"}), 404

@api_bp.route('/scheduler/reload', methods=['POST'])
def api_reload_scheduler():
    """Tải lại tất cả các tác vụ cho Trình lập lịch"""
    try:
        # Nhận trình quản lý đồng bộ
        if 'SYNC_MANAGER' not in current_app.config:
            return jsonify({
                "status": "error", 
                "message": "Bộ lập lịch không được khởi tạo"
            }), 500
            
        sync_manager = current_app.config['SYNC_MANAGER']
        
        # Reinitialize bộ lập lịch
        sync_manager.is_initialized = False  # Tái tạo bắt buộc
        sync_manager.initialize_scheduler()
        
        # Đăng nhập
        data_manager = current_app.config['DATA_MANAGER']
        data_manager.add_log({
            "level": "INFO",
            "message": "Trình lập lịch đã tải lại tất cả các tác vụ",
            "details": {"from": request.remote_addr}
        })
        
        # Nhận tất cả thông tin nhiệm vụ
        jobs = sync_manager.scheduler.get_jobs()
        job_info = []
        for job in jobs:
            job_info.append({
                "id": job.id,
                "next_run": str(job.next_run_time) if job.next_run_time else None
            })
        
        return jsonify({
            "status": "success",
            "message": "Bộ lập lịch đã được tải lại",
            "jobs_count": len(jobs),
            "jobs": job_info
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Tải lại lịch trình không thành công: {str(e)}")
        current_app.logger.error(error_details)
        
        return jsonify({
            "status": "error",
            "message": f"Tải lại lịch trình không thành công: {str(e)}"
        }), 500

@api_bp.route('/logs', methods=['GET'])
def api_logs():
    """Nhận danh sách nhật ký，Hỗ trợ lọc"""
    data_manager = current_app.config['DATA_MANAGER']
    
    # Nhận tham số bộ lọc
    level = request.args.get('level')
    task_id = request.args.get('task_id')
    search = request.args.get('search')
    timestamp = request.args.get('timestamp')
    limit = request.args.get('limit', 100, type=int)
    
    # Nhận tất cả các bản ghi
    logs = data_manager.get_logs(limit=limit)
    
    # Áp dụng tiêu chí lọc
    if level:
        logs = [log for log in logs if log.get('level') == level]
    
    if task_id:
        try:
            task_id = int(task_id)
            logs = [log for log in logs if log.get('task_id') == task_id]
        except (ValueError, TypeError):
            pass
    
    if timestamp:
        try:
            timestamp = int(timestamp)
            logs = [log for log in logs if log.get('timestamp') == timestamp]
        except (ValueError, TypeError):
            pass
    
    if search:
        search = search.lower()
        filtered_logs = []
        for log in logs:
            # Tìm kiếm trong tin nhắn
            if search in log.get('message', '').lower():
                filtered_logs.append(log)
                continue
                
            # Tìm kiếm chi tiết
            details = log.get('details', {})
            if isinstance(details, dict):
                details_str = json.dumps(details, ensure_ascii=False).lower()
                if search in details_str:
                    filtered_logs.append(log)
                    continue
            elif isinstance(details, str) and search in details.lower():
                filtered_logs.append(log)
                
        logs = filtered_logs
    
    # Đảm bảo tất cả các nhật ký có ID trường
    for i, log in enumerate(logs):
        if 'id' not in log:
            log['id'] = i + 1
    
    return jsonify({
        "status": "success",
        "logs": logs
    })

@api_bp.route('/logs/<int:log_id>', methods=['GET'])
def api_log_detail(log_id):
    """Nhận chi tiết nhật ký cá nhân"""
    data_manager = current_app.config['DATA_MANAGER']
    
    # Nhận tất cả các bản ghi
    logs = data_manager.get_logs(limit=1000)
    
    # Tìm các quy định ID Nhật ký
    log = None
    for i, item in enumerate(logs):
        # Nếu nhật ký không ID，Sử dụng chỉ mục như ID
        if 'id' not in item:
            item['id'] = i + 1
            
        if item.get('id') == log_id:
            log = item
            break
    
    if not log:
        return jsonify({"status": "error", "message": "Nhật ký không tồn tại"}), 404
    
    return jsonify({
        "status": "success",
        "log": log
    })

@api_bp.route('/logs/clear', methods=['POST'])
def api_clear_logs():
    """Xóa nhật ký"""
    data_manager = current_app.config['DATA_MANAGER']
    
    try:
        # Hoạt động nhật ký nhật ký
        data_manager.add_log({
            "level": "INFO",
            "message": "Xóa thủ công tất cả các bản ghi",
            "details": {"ip": request.remote_addr}
        })
        
        # Xóa nhật ký
        data_manager._write_json(data_manager.logs_file, [])
        
        return jsonify({
            "status": "success",
            "message": "Đăng nhập Xóa"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Không thể xóa nhật ký: {str(e)}"
        }), 500

# Hàm nhập và xuất
@api_bp.route('/export', methods=['GET'])
def api_export_data():
    """Xuất tất cả dữ liệu dưới dạng mộtJSONtài liệu"""
    data_manager = current_app.config['DATA_MANAGER']
    try:
        export_data = data_manager.export_data()
        response = {
            "status": "success",
            "message": "Xuất dữ liệu thành công",
            "data": export_data
        }
        return jsonify(response)
    except Exception as e:
        current_app.logger.error(f"Xảy ra lỗi trong khi xuất dữ liệu: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Không xuất dữ liệu: {str(e)}"
        }), 500

@api_bp.route('/import', methods=['POST'])
def api_import_data():
    """Nhập dữ liệu cấu hình"""
    try:
        if not request.json:
            return jsonify({"status": "error", "message": "Không có dữ liệu cấu hình hợp lệ được cung cấp"}), 400
            
        data_manager = current_app.config['DATA_MANAGER']
        # Thử hai cách để nhận dữ liệu đã nhập
        import_data = request.json.get('data')
        
        # Nếu khôngdatatrường，Sau đó, toàn bộ cơ quan yêu cầu có thể là dữ liệu nhập
        if not import_data and isinstance(request.json, dict) and ('users' in request.json or 'connections' in request.json or 'tasks' in request.json or 'settings' in request.json):
            import_data = request.json
        
        if not import_data:
            return jsonify({"status": "error", "message": "Dữ liệu cấu hình trống"}), 400
        
        # Thực hiện hoạt động nhập
        import_result = data_manager.import_data(import_data)
        
        # Nếu nhập thành công và cấu hình đồng bộ，Tải lại Lập lịch
        if import_result.get("success") and import_result.get("details", {}).get("format") == "alist_sync_sync_config":
            sync_manager = current_app.config.get('SYNC_MANAGER')
            if sync_manager:
                try:
                    reload_result = sync_manager.reload_scheduler()
                    import_result["details"]["scheduler"] = f"Bộ lập lịch đã được tải lại，{reload_result.get('loaded_tasks', 0)}Nhiệm vụ đã được Thêm "
                except Exception as e:
                    import_result["details"]["scheduler_error"] = str(e)
                    current_app.logger.error(f"Tải lại lịch trình không thành công: {str(e)}")
        
        return jsonify({"status": "success" if import_result.get("success") else "error", 
                        "message": import_result.get("message"), 
                        "details": import_result.get("details")})
    
    except Exception as e:
        current_app.logger.error(f"Xảy ra lỗi trong khi nhập dữ liệu: {str(e)}")
        return jsonify({"status": "error", "message": f"Không nhập dữ liệu: {str(e)}"}), 500

@api_bp.route('/version', methods=['GET'])
def api_version():
    """Nhận thông tin phiên bản hệ thống"""
    has_update, current_version, latest_version = has_new_version()
    
    return jsonify({
        "current_version": current_version,
        "latest_version": latest_version,
        "has_update": has_update,
        "github_url": "https://github.com/xjxjin/alist-sync",
        "gitee_url": "https://gitee.com/xjxjin/alist-sync"
    })

# Thêm WebNhập và xuất giao diện
@main_bp.route('/import-export')
def import_export_page():
    """Nhập và xuất trang"""
    return render_template('import_export.html')

@api_bp.route('/logs/repair', methods=['POST'])
def api_repair_logs():
    """Sửa chữa tập tin nhật ký"""
    try:
        data_manager = current_app.config['DATA_MANAGER']
        
        # Đọc nhật ký cũ
        try:
            with open(data_manager.logs_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                old_logs = json.loads(content) if content else []
                if not isinstance(old_logs, list):
                    old_logs = []
        except Exception:
            old_logs = []
        
        # Tạo nhật ký kiểm tra
        timestamp = int(time.time())
        test_log = {
            "level": "INFO",
            "message": "Hệ thống nhật ký đã được sửa",
            "timestamp": timestamp,
            "timestamp_formatted": data_manager.format_timestamp(timestamp),
            "details": {"triggered_by": "repair_api"}
        }
        
        # Viết lại tệp nhật ký
        logs = old_logs + [test_log]
        data_manager._write_json(data_manager.logs_file, logs)
        
        # Xác minh tệp nhật ký
        try:
            new_logs = data_manager.get_logs()
            if len(new_logs) > 0:
                success = True
                message = f"Các tệp nhật ký đã được sửa，Hiện tại ở đó {len(new_logs)} Đăng nhập"
            else:
                success = False
                message = "Sửa chữa tệp nhật ký không thành công，Vẫn không thể đọc nhật ký"
        except Exception as e:
            success = False
            message = f"Sửa chữa tệp nhật ký không thành công: {str(e)}"
        
        return jsonify({
            "status": "success" if success else "error",
            "message": message,
            "logs_count": len(logs)
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Xảy ra lỗi trong khi sửa chữa tệp nhật ký: {error_details}")
        
        return jsonify({
            "status": "error",
            "message": f"Xảy ra lỗi trong khi sửa chữa tệp nhật ký: {str(e)}"
        }), 500

# Đăng ký một kế hoạch chi tiết
# ... existing code ... 