"""
IMAP 邮箱连接模块
支持通过 IMAP 协议连接邮箱获取邮件
"""

import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import re
import html


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

    def _parse_date_to_iso(self, date_text: str) -> str:
        """尽量将邮件日期文本解析为 ISO 字符串，失败时保留原文。"""
        if not date_text:
            return ""

        cleaned = self._clean_header_value(date_text)
        normalized = cleaned.replace("\u202f", " ").replace("\xa0", " ")
        normalized = re.sub(r"\bat\b", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized).strip().rstrip(",")

        patterns = [
            "%a, %d %b %Y, %I:%M %p",
            "%a, %d %b %Y %I:%M %p",
            "%a, %d %b %Y, %H:%M",
            "%a, %d %b %Y %H:%M",
            "%d %b %Y, %I:%M %p",
            "%d %b %Y %I:%M %p",
            "%d %b %Y, %H:%M",
            "%d %b %Y %H:%M",
        ]
        for pattern in patterns:
            try:
                return datetime.strptime(normalized, pattern).isoformat()
            except Exception:
                pass

        for candidate in [cleaned, normalized]:
            try:
                return parsedate_to_datetime(candidate).isoformat()
            except Exception:
                pass

        return cleaned

    def _clean_header_value(self, value: str) -> str:
        """清理从正文回复块里解析出的头字段。"""
        value = html.unescape(value or "")
        value = value.replace("\u202f", " ").replace("\xa0", " ")
        value = re.sub(r"<\s*(https?://|mailto:)[^>]+>", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+", " ", value).strip()
        return value.strip(" \t\r\n:：")

    def _normalize_message_id(self, value: str) -> str:
        """规范化 Message-ID 头字段。"""
        value = self._clean_header_value(value)
        match = re.search(r"<([^>]+)>", value)
        if match:
            return f"<{match.group(1).strip()}>"
        return value

    def _parse_references(self, value: str) -> List[str]:
        """解析 References / In-Reply-To 里的 Message-ID 列表。"""
        if not value:
            return []
        ids = [f"<{item.strip()}>" for item in re.findall(r"<([^>]+)>", value)]
        if not ids:
            cleaned = self._normalize_message_id(value)
            ids = [cleaned] if cleaned else []

        result = []
        seen = set()
        for item in ids:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    def _html_to_text(self, text: str) -> str:
        """将 HTML 正文转成适合清理引用历史的纯文本。"""
        if not text:
            return ""

        text = html.unescape(text)
        text = re.sub(r"(?is)<\s*(?:script|style)\b.*?</\s*(?:script|style)\s*>", " ", text)
        text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
        text = re.sub(r"(?i)</\s*(?:p|div|li|tr|td|table|blockquote|h[1-6])\s*>", "\n", text)
        text = re.sub(r"(?i)<\s*(?:p|div|li|tr|td|table|blockquote|h[1-6])\b[^>]*>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
        return text

    def _prepare_thread_text(self, text: str) -> str:
        """统一正文文本，移除引用符号但保留换行结构。"""
        if not text:
            return ""

        text = html.unescape(text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\xa0", " ").replace("\u202f", " ")
        text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")

        lines = []
        blank_count = 0
        for raw_line in text.split("\n"):
            line = re.sub(r"^\s*(?:>\s*)+", "", raw_line).strip()
            line = re.sub(r"\s+", " ", line).strip()
            if not line:
                blank_count += 1
                if blank_count <= 1:
                    lines.append("")
                continue
            blank_count = 0
            lines.append(line)

        return "\n".join(lines).strip()

    def _normalize_actual_message(self, email_dict: Dict) -> Dict:
        """只保留 IMAP 真实邮件的当前正文，并去掉引用历史和签名。"""
        body_source = email_dict.get('body_text') or self._html_to_text(email_dict.get('body_html', ''))
        current_body = self._extract_current_body(body_source)
        current_body = self._strip_signature(current_body)

        result = email_dict.copy()
        result['body_text'] = current_body
        result['body_html'] = ''
        return result

    def _extract_current_body(self, text: str) -> str:
        """截掉正文里的历史回复/转发内容，仅保留当前这封邮件正文。"""
        prepared = self._prepare_thread_text(text)
        if not prepared:
            return ""

        lines = prepared.split("\n")
        current_lines = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if self._is_forwarded_marker(stripped):
                break
            if self._is_header_block_start(lines, idx):
                break
            if self._parse_wrote_marker(stripped, {}):
                break
            current_lines.append(line)

        return self._clean_thread_body(current_lines)

    def _strip_signature(self, text: str) -> str:
        """移除常见邮件签名，避免签名干扰信息提取。"""
        if not text:
            return ""

        signature_patterns = [
            r"^--\s*$",
            r"^(best|best regards|kind regards|regards|warm regards|sincerely|thanks|thank you|cheers)[,!.]?$",
            r"^sent from my .+",
            r"^发自我的.+",
            r"^此致[,，]?$",
            r"^祝好[,，]?$",
        ]

        kept = []
        for line in text.split("\n"):
            stripped = line.strip()
            if kept and any(re.match(pattern, stripped, re.IGNORECASE) for pattern in signature_patterns):
                break
            kept.append(line)

        return "\n".join(kept).strip()

    def _clean_thread_body(self, body_lines: List[str]) -> str:
        lines = []
        blank_count = 0
        for line in body_lines:
            stripped = line.strip()
            if self._is_forwarded_marker(stripped):
                continue
            if not stripped:
                blank_count += 1
                if blank_count <= 1:
                    lines.append("")
                continue
            blank_count = 0
            lines.append(stripped)
        return "\n".join(lines).strip()

    def _is_forwarded_marker(self, line: str) -> bool:
        return bool(re.search(r"^-+\s*Forwarded message\s*-+$", line, re.IGNORECASE))

    def _is_header_block_start(self, lines: List[str], idx: int) -> bool:
        if idx >= len(lines) or not re.match(r"(?i)^from\s*:", lines[idx].strip()):
            return False
        window = "\n".join(line.strip() for line in lines[idx: idx + 6])
        return bool(re.search(r"(?im)^(date|subject|to|cc)\s*:", window))

    def _parse_wrote_marker(self, line: str, inherited_meta: Dict) -> Optional[Dict]:
        match = re.match(r"(?is)^on\s+(.+),\s*(.+?)\s+wrote\s*:\s*$", line)
        if not match:
            return None

        date_text = match.group(1)
        sender_text = match.group(2)
        name, sender_email = self._parse_email_address(sender_text)
        if not sender_email:
            sender_text = self._clean_header_value(sender_text)
            name = sender_text.strip('"')

        meta = inherited_meta.copy()
        meta['sender_name'] = name
        meta['sender_email'] = sender_email
        meta['received_at'] = self._parse_date_to_iso(date_text)
        return meta

    def _parse_email(self, raw_email, message_id: str) -> Dict:
        """解析邮件内容"""
        result = {
            'message_id': message_id,
            'email_message_id': '',
            'in_reply_to': '',
            'references': [],
            'thread_root_message_id': '',
            'thread_parent_message_id': '',
            'thread_depth': 0,
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

        # 解析 IMAP/RFC 线程头。它们只能关联真实邮件，不能拆正文里复制出来的历史内容。
        result['email_message_id'] = self._normalize_message_id(raw_email.get('Message-ID', ''))
        references = self._parse_references(raw_email.get('References', ''))
        in_reply_to = self._parse_references(raw_email.get('In-Reply-To', ''))
        result['references'] = references
        result['in_reply_to'] = in_reply_to[-1] if in_reply_to else ''
        result['thread_parent_message_id'] = result['in_reply_to'] or (references[-1] if references else '')
        result['thread_root_message_id'] = references[0] if references else result['email_message_id']
        result['thread_depth'] = len(references)

        # 解析发件人
        sender = raw_email.get('From', '')
        name, email = self._parse_email_address(sender)
        result['sender_name'] = name
        result['sender_email'] = email

        # 解析收件时间
        received = raw_email.get('Date', '')
        result['received_at'] = self._parse_date_to_iso(received)

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
            # BEFORE 是排他的，所以需要给结束日期加一天来包含当天
            end_date_inclusive = end_date + timedelta(days=1)
            end_str = end_date_inclusive.strftime("%d-%b-%Y")

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
                                email_date = parsedate_to_datetime(email_dict['received_at'])
                                if start_date <= email_date <= end_date:
                                    emails.append(self._normalize_actual_message(email_dict))
                            except:
                                emails.append(self._normalize_actual_message(email_dict))

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
