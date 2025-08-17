import os
import re
import json
import requests
import logging
from datetime import datetime, timedelta

# Phiên bản tập tin cache
VERSION_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                               'data/config/version_cache.json')

# Github API URL
GITHUB_API_URL = "https://api.github.com/repos/xjxjin/alist-sync/releases/latest"

def get_current_version():
    """Nhận phiên bản hệ thống hiện tại"""
    try:
        version_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'VERSION')
        
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                version = f.read().strip()
                return version
    except Exception as e:
        logging.error(f"Không nhận được phiên bản hiện tại: {str(e)}")
    
    return "không xác định"

def get_latest_version():
    """từGitHubNhận phiên bản mới nhất"""
    # Kiểm tra xem có bộ đệm không
    if os.path.exists(VERSION_CACHE_FILE):
        try:
            with open(VERSION_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                
                # Kiểm tra xem bộ đệm có hết hạn không（24Giờ）
                cache_time = datetime.fromisoformat(cache_data.get('timestamp'))
                if datetime.now() - cache_time < timedelta(hours=24):
                    return cache_data.get('version'), cache_data.get('download_url', "")
        except Exception as e:
            logging.error(f"Không đọc được phiên bản bộ nhớ cache: {str(e)}")
    
    # Bộ đệm không tồn tại hoặc đã hết hạn，từGitHubLấy
    try:
        response = requests.get(GITHUB_API_URL, timeout=5)
        if response.status_code == 200:
            release_data = response.json()
            latest_version = release_data.get('tag_name', '').lstrip('v')
            download_url = release_data.get('html_url', '')
            
            # Cập nhật bộ đệm
            cache_data = {
                'version': latest_version,
                'download_url': download_url,
                'timestamp': datetime.now().isoformat()
            }
            
            os.makedirs(os.path.dirname(VERSION_CACHE_FILE), exist_ok=True)
            with open(VERSION_CACHE_FILE, 'w') as f:
                json.dump(cache_data, f)
            
            return latest_version, download_url
    except Exception as e:
        logging.error(f"LấyGitHubPhiên bản mới nhất không thành công: {str(e)}")
    
    # Nếu việc mua lại thất bại nhưng có bộ đệm，Trở lại phiên bản được lưu trong bộ nhớ cache
    if os.path.exists(VERSION_CACHE_FILE):
        try:
            with open(VERSION_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                return cache_data.get('version'), cache_data.get('download_url', "")
        except:
            pass
    
    return None, ""

def has_new_version():
    """Kiểm tra xem có phiên bản mới không"""
    current = get_current_version()
    latest, _ = get_latest_version()
    
    if not latest:
        return False, current, None
    
    # So sánh phiên bản
    current_parts = current.split('.')
    latest_parts = latest.split('.')
    
    for i in range(max(len(current_parts), len(latest_parts))):
        c_val = int(current_parts[i]) if i < len(current_parts) else 0
        l_val = int(latest_parts[i]) if i < len(latest_parts) else 0
        
        if l_val > c_val:
            return True, current, latest
        elif c_val > l_val:
            return False, current, latest
    
    return False, current, latest 