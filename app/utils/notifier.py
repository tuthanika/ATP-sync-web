import requests
import json
import logging
import base64
import hashlib
import hmac
import time
import urllib.parse
from flask import current_app

class Notifier:
    """
    Mô -đun thông báo，Hỗ trợ nhiều kênh thông báo
    """
    def __init__(self, settings=None):
        self.settings = settings or {}
        self.logger = logging.getLogger('notifier')
    
    def send_notification(self, title, content, task_info=None):
        """
        Gửi thông báo
        :param title: Tiêu đề thông báo
        :param content: Nội dung thông báo
        :param task_info: Thông tin liên quan đến nhiệm vụ
        """
        # Nhận cài đặt，Nếu không có cài đặt khởi tạo, hãy cố gắng lấy từ cấu hình ứng dụng
        if not self.settings and hasattr(current_app, 'config') and 'DATA_MANAGER' in current_app.config:
            data_manager = current_app.config['DATA_MANAGER']
            self.settings = data_manager.get_settings()
        
        # Kiểm tra xem thông báo có được bật không
        if not self.settings.get('enable_webhook', False):
            self.logger.debug("Thông báo không được bật")
            return False
        
        # Gửi thông báo theo loại thông báo đặt
        notification_type = self.settings.get('notification_type', 'feishu')
        
        try:
            # Gọi phương thức tương ứng theo loại thông báo
            if notification_type == 'feishu':
                return self.send_feishu(title, content, task_info)
            elif notification_type == 'dingtalk':
                return self.send_dingtalk(title, content, task_info)
            elif notification_type == 'wecom':
                return self.send_wecom(title, content, task_info)
            elif notification_type == 'bark':
                return self.send_bark(title, content, task_info)
            elif notification_type == 'pushplus':
                return self.send_pushplus(title, content, task_info)
            elif notification_type == 'telegram':
                return self.send_telegram(title, content, task_info)
            elif notification_type == 'webhook':
                return self.send_webhook(title, content, task_info)
            else:
                self.logger.error(f"Không hỗ trợ các loại thông báo: {notification_type}")
                return False
        except Exception as e:
            self.logger.error(f"Không gửi thông báo: {str(e)}")
            return False
    
    def format_task_message(self, title, content, task_info):
        """Định dạng tin nhắn nhiệm vụ"""
        if not task_info:
            return {'title': title, 'content': content}
        
        task_name = task_info.get('name', 'Nhiệm vụ không tên')
        task_id = task_info.get('id', 'không xác địnhID')
        status = task_info.get('status', 'Trạng thái không xác định')
        duration = task_info.get('duration', 'không xác định')
        
        # Được định dạng theo định dạng Markdown (phù hợp với hầu hết các nền tảng）
        formatted_content = f"""
### {title}

**Tên nhiệm vụ**: {task_name}
**Nhiệm vụ ID**: {task_id}
**Trạng thái thực thi**: {status}
**Thời gian thực hiện**: {duration}

{content}
"""
        return {'title': title, 'content': formatted_content}
    
    def send_feishu(self, title, content, task_info=None):
        """Gửi thông báo Lark/Feishu"""
        webhook_url = self.settings.get('webhook_url', '')
        if not webhook_url:
            self.logger.error("Lark/Feishu Webhook URL Không đặt")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # Định dạng tin nhắn thẻ Feishu
        message = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": formatted['title']
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "Lark/Feishu_md",
                            "content": formatted['content']
                        }
                    }
                ]
            }
        }
        
        try:
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(message)
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    self.logger.info("Thông báo Feishu đã được gửi thành công")
                    return True
                else:
                    self.logger.error(f"Không gửi được thông báo Feishu: {result.get('msg')}")
                    return False
            else:
                self.logger.error(f"Thông báo Feishu HTTPsai lầm: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Xảy ra lỗi trong khi gửi thông báo Feishu: {str(e)}")
            return False
    
    def send_dingtalk(self, title, content, task_info=None):
        """Gửi thông báo DingTalk"""
        webhook_url = self.settings.get('webhook_url', '')
        secret = self.settings.get('dingtalk_secret', '')
        
        if not webhook_url:
            self.logger.error("Móng tay Webhook URL Không đặt")
            return False
        
        # Nếu có khóa đăng ký，Chữ ký cần được tính toán
        if secret:
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{secret}"
            signature = base64.b64encode(
                hmac.new(
                    secret.encode('utf-8'),
                    string_to_sign.encode('utf-8'),
                    digestmod=hashlib.sha256
                ).digest()
            ).decode('utf-8')
            
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={urllib.parse.quote_plus(signature)}"
        
        formatted = self.format_task_message(title, content, task_info)
        
        # Định dạng tin nhắn DingTalk
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": formatted['title'],
                "text": formatted['content']
            }
        }
        
        try:
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(message)
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    self.logger.info("Thông báo DingTalk được gửi thành công")
                    return True
                else:
                    self.logger.error(f"Thông báo DingTalk không gửi: {result.get('errmsg')}")
                    return False
            else:
                self.logger.error(f"Thông báo DingTalkHTTPsai lầm: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Đã xảy ra lỗi trong khi gửi thông báo DingTalk: {str(e)}")
            return False
    
    def send_wecom(self, title, content, task_info=None):
        """Gửi thông báo WeChat của công ty"""
        webhook_url = self.settings.get('webhook_url', '')
        
        if not webhook_url:
            self.logger.error("Doanh nghiệp WeChat Webhook URL Không đặt")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # Định dạng tin nhắn WeChat của doanh nghiệp
        message = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"# {formatted['title']}\n{formatted['content']}"
            }
        }
        
        try:
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(message)
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    self.logger.info("Thông báo WeChat của Enterprise đã được gửi thành công")
                    return True
                else:
                    self.logger.error(f"Doanh nghiệp WeChat Thông báo không thành công: {result.get('errmsg')}")
                    return False
            else:
                self.logger.error(f"Thông báo WeChat của doanh nghiệpHTTPsai lầm: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Xảy ra lỗi trong khi gửi thông báo WeChat của công ty: {str(e)}")
            return False
    
    def send_bark(self, title, content, task_info=None):
        """gửiBarkthông báo"""
        bark_url = self.settings.get('webhook_url', '')
        bark_sound = self.settings.get('bark_sound', 'default')
        
        if not bark_url:
            self.logger.error("Bark URL Không đặt")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # kết cấuBark URL
        # nếu nhưURLKhông/Kết thúc，Thêm /
        if not bark_url.endswith('/'):
            bark_url += '/'
        
        # Tiêu đề và nội dung được mã hóa
        encoded_title = urllib.parse.quote_plus(formatted['title'])
        encoded_content = urllib.parse.quote_plus(formatted['content'])
        
        # Xây dựng một hoàn chỉnhBark URL
        full_url = f"{bark_url}{encoded_title}/{encoded_content}?sound={bark_sound}"
        
        try:
            response = requests.get(full_url)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 200:
                    self.logger.info("BarkThông báo đã được gửi thành công")
                    return True
                else:
                    self.logger.error(f"BarkThông báo gửi không thành công: {result.get('message')}")
                    return False
            else:
                self.logger.error(f"BarkThông báo lỗi HTTP: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"gửiBarkXảy ra lỗi trong khi thông báo: {str(e)}")
            return False
    
    def send_pushplus(self, title, content, task_info=None):
        """gửiPushPlusthông báo"""
        token = self.settings.get('webhook_url', '')
        
        if not token:
            self.logger.error("PushPlus Token Không đặt")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # PushPlusgiao diện
        api_url = "http://www.pushplus.plus/send"
        
        data = {
            "token": token,
            "title": formatted['title'],
            "content": formatted['content'],
            "template": "markdown"
        }
        
        try:
            response = requests.post(
                api_url,
                data=json.dumps(data),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 200:
                    self.logger.info("PushPlusThông báo đã được gửi thành công")
                    return True
                else:
                    self.logger.error(f"PushPlusThông báo gửi không thành công: {result.get('msg')}")
                    return False
            else:
                self.logger.error(f"PushPlusThông báo lỗi HTTP: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"gửiPushPlusXảy ra lỗi trong khi thông báo: {str(e)}")
            return False
    
    def send_telegram(self, title, content, task_info=None):
        """gửiTelegramthông báo"""
        bot_token = self.settings.get('telegram_bot_token', '')
        chat_id = self.settings.get('telegram_chat_id', '')
        
        if not bot_token or not chat_id:
            self.logger.error("TelegramCấu hình không đầy đủ: nhu cầubot_tokenVàchat_id")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # Telegram Bot API
        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # Hợp nhất tiêu đề và nội dung
        message_text = f"*{formatted['title']}*\n\n{formatted['content']}"
        
        data = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(api_url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    self.logger.info("TelegramThông báo đã được gửi thành công")
                    return True
                else:
                    self.logger.error(f"TelegramThông báo gửi không thành công: {result.get('description')}")
                    return False
            else:
                self.logger.error(f"TelegramThông báo lỗi HTTP: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"gửiTelegramXảy ra lỗi trong khi thông báo: {str(e)}")
            return False
    
    def send_webhook(self, title, content, task_info=None):
        """Gửi tùy chỉnhWebhookthông báo"""
        webhook_url = self.settings.get('webhook_url', '')
        
        if not webhook_url:
            self.logger.error("Webhook URL Không đặt")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # Xây dựng định dạng webhook chung
        payload = {
            "title": formatted['title'],
            "content": formatted['content'],
            "task_info": task_info
        }
        
        try:
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload)
            )
            
            if 200 <= response.status_code < 300:
                self.logger.info("WebhookThông báo đã được gửi thành công")
                return True
            else:
                self.logger.error(f"WebhookThông báo lỗi HTTP: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Lỗi khi gửi thông báo webhook: {str(e)}")
            return False 