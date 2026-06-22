"""
IMAP 邮箱连接模块
支持通过 IMAP 协议连接邮箱获取邮件
"""

import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import re


class IMAPEmailClient:
    """IMAP 邮箱客户端"""

    # 飞书邮箱 IMAP 配置
    FEISHU_IMAP = {
        'server': 'imap.feishu.cn',
        'port': 993,
        'ssl': True
    }

    # 常见邮箱的 IMAP 配置
    COMMON_PROVIDERS = {
        'feishu': {
            'server': 'imap.feishu.cn',
            'port': 993,
            'ssl': True
        },
        'qq': {
            'server': 'imap.qq.com',
            'port': 993,
            'ssl': True
        },
        '163': {
            'server': 'imap.163.com',
            'port': 993,
            'ssl': True
        },
        'gmail': {
            'server': 'imap.gmail.com',
            'port': 993,
            'ssl': True
        },
        'outlook': {
            'server': 'outlook.office365.com',
            'port': 993,
            'ssl': True
        },
        'aliyun': {
            'server': 'imap.aliyun.com',
            'port': 993,
            'ssl': True
        },
        'custom': None  # 自定义服务器
    }

    def __init__(self, email_addr: str, password: str,
                 server: str = None, port: int = 993, ssl: bool = True):
        self.email_addr = email_addr
        self.password = password
        self.server = server
        self.port = port
        self.ssl = ssl
        self.connection: Optional[imaplib.IMAP4_SSL] = None

    @classmethod
    def detect_provider(cls, email_addr: str, password: str) -> 'IMAPEmailClient':
        """自动检测邮箱服务商并连接"""
        domain = email_addr.split('@')[1].lower() if '@' in email_addr else ''

        # 飞书邮箱检测
        if 'feishu' in domain or 'lark' in domain:
            return cls.from_provider('feishu', email_addr, password)

        # QQ 邮箱
        if 'qq.com' in domain:
            return cls.from_provider('qq', email_addr, password)

        # 163 邮箱
        if '163.com' in domain:
            return cls.from_provider('163', email_addr, password)

        # Gmail
        if 'gmail.com' in domain:
            return cls.from_provider('gmail', email_addr, password)

        # Outlook
        if 'outlook' in domain or 'hotmail' in domain:
            return cls.from_provider('outlook', email_addr, password)

        # 阿里云邮箱
        if 'aliyun' in domain:
            return cls.from_provider('aliyun', email_addr, password)

        # 默认尝试飞书
        return cls.from_provider('feishu', email_addr, password)

    @classmethod
    def from_provider(cls, provider: str, email_addr: str, password: str) -> 'IMAPEmailClient':
        """从已知服务商创建连接"""
        if provider == 'custom':
            raise ValueError("自定义服务器需要提供 server, port 参数")

        config = cls.COMMON_PROVIDERS.get(provider)
        if not config:
            raise ValueError(f"未知的服务商: {provider}")

        return cls(email_addr, password, config['server'], config['port'], config['ssl'])

    def connect(self) -> bool:
        """建立 IMAP 连接"""
        try:
            if self.ssl:
                self.connection = imaplib.IMAP4_SSL(self.server, self.port)
            else:
                self.connection = imaplib.IMAP4(self.server, self.port)

            # 登录
            result, _ = self.connection.login(self.email_addr, self.password)
            if result != 'OK':
                raise Exception("登录失败")

            return True
        except imaplib.IMAP4.error as e:
            raise Exception(f"IMAP 连接失败: {e}")
        except Exception as e:
            raise Exception(f"连接错误: {e}")

    def disconnect(self):
        """断开连接"""
        if self.connection:
            try:
                self.connection.logout()
            except:
                pass
            self.connection = None

    def _decode_email_header(self, header_str: str) -> str:
        """解码邮件标题"""
        if not header_str:
            return ""

        decoded_parts = []
        try:
            parts = decode_header(header_str)
            for content, charset in parts:
                if isinstance(content, bytes):
                    charset = charset or 'utf-8'
                    try:
                        decoded_parts.append(content.decode(charset, errors='replace'))
                    except:
                        decoded_parts.append(content.decode('utf-8', errors='replace'))
                else:
                    decoded_parts.append(content)
        except:
            return header_str

        return ''.join(decoded_parts)

    def _parse_email_address(self, addr_str: str) -> Tuple[str, str]:
        """解析邮件地址字符串"""
        if not addr_str:
            return ("", "")

        # 格式: "姓名 <email@example.com>"
        match = re.search(r'<([^>]+)>', addr_str)
        if match:
            email = match.group(1)
            name = addr_str[:match.start()].strip().strip('"')
            return (name, email)

        # 纯邮箱
        if '@' in addr_str:
            return ("", addr_str.strip())

        return ("", "")

    def _parse_email(self, raw_email, message_id: str) -> Dict:
        """解析邮件内容"""
        result = {
            'message_id': message_id,
            'subject': '',
            'sender_name': '',
            'sender_email': '',
            'received_at': '',
            'body_text': '',
            'body_html': '',
            'contact_info': ''
        }

        # 解析标题
        subject = raw_email.get('Subject', '')
        result['subject'] = self._decode_email_header(subject)

        # 解析发件人
        sender = raw_email.get('From', '')
        name, email = self._parse_email_address(sender)
        result['sender_name'] = name
        result['sender_email'] = email

        # 解析收件时间
        received = raw_email.get('Date', '')
        try:
            # 尝试解析日期
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(received)
            result['received_at'] = dt.isoformat()
        except:
            result['received_at'] = received

        # 解析邮件正文
        if raw_email.is_multipart():
            for part in raw_email.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition', ''))

                # 获取纯文本
                if content_type == 'text/plain' and 'attachment' not in content_disposition:
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        result['body_text'] = part.get_payload(decode=True).decode(charset, errors='replace')
                    except:
                        pass

                # 获取 HTML
                elif content_type == 'text/html' and 'attachment' not in content_disposition:
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        result['body_html'] = part.get_payload(decode=True).decode(charset, errors='replace')
                    except:
                        pass
        else:
            content_type = raw_email.get_content_type()
            try:
                charset = raw_email.get_content_charset() or 'utf-8'
                content = raw_email.get_payload(decode=True).decode(charset, errors='replace')
                if content_type == 'text/plain':
                    result['body_text'] = content
                elif content_type == 'text/html':
                    result['body_html'] = content
            except:
                pass

        return result

    def get_emails(self, start_date: datetime, end_date: datetime,
                   folder: str = 'INBOX', limit: int = 500) -> List[Dict]:
        """
        获取指定日期范围内的邮件

        Args:
            start_date: 开始日期
            end_date: 结束日期
            folder: 邮箱文件夹 (默认 INBOX)
            limit: 最大邮件数量

        Returns:
            邮件列表
        """
        if not self.connection:
            raise Exception("未连接邮箱服务器")

        try:
            # 选择文件夹
            result, _ = self.connection.select(folder)
            if result != 'OK':
                raise Exception(f"无法打开文件夹: {folder}")

            # 搜索邮件
            start_str = start_date.strftime("%d-%b-%Y")
            end_str = end_date.strftime("%d-%b-%Y")

            search_criteria = f'SINCE {start_str} BEFORE {end_str}'
            result, message_ids = self.connection.search(None, search_criteria)

            if result != 'OK':
                raise Exception("搜索邮件失败")

            all_ids = message_ids[0].split()
            if not all_ids:
                return []

            # 限制数量（取最新的）
            ids_to_fetch = all_ids[-limit:] if len(all_ids) > limit else all_ids

            emails = []
            for msg_id in reversed(ids_to_fetch):
                try:
                    result, data = self.connection.fetch(msg_id, '(RFC822)')
                    if result == 'OK' and data and data[0]:
                        raw_email = email.message_from_bytes(data[0][1])
                        email_dict = self._parse_email(raw_email, msg_id.decode())

                        # 检查日期是否在范围内
                        if email_dict['received_at']:
                            try:
                                from email.utils import parsedate_to_datetime
                                email_date = parsedate_to_datetime(email_dict['received_at'])
                                if start_date <= email_date <= end_date:
                                    emails.append(email_dict)
                            except:
                                emails.append(email_dict)

                except Exception as e:
                    # 单封邮件解析失败不影响其他邮件
                    continue

            return emails

        except Exception as e:
            raise Exception(f"获取邮件失败: {e}")

    def get_folders(self) -> List[str]:
        """获取邮箱文件夹列表"""
        if not self.connection:
            raise Exception("未连接邮箱服务器")

        try:
            result, folders = self.connection.list()
            if result != 'OK':
                return []

            folder_list = []
            for folder in folders:
                if isinstance(folder, bytes):
                    folder = folder.decode('utf-8', errors='replace')
                # 提取文件夹名称
                parts = folder.split('"')
                if len(parts) >= 2:
                    folder_list.append(parts[-2])

            return folder_list
        except:
            return []

    def test_connection(self) -> Tuple[bool, str]:
        """测试连接是否成功"""
        try:
            self.connect()
            self.disconnect()
            return True, "连接成功"
        except Exception as e:
            return False, str(e)
