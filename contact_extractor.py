"""
全球联系信息提取器
支持提取邮箱地址、联系电话和联系地址
"""

import re
import html
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ContactInfo:
    """联系信息数据类"""
    emails: List[str]
    phones: List[str]
    addresses: List[str]

    def is_empty(self) -> bool:
        """检查是否为空"""
        return not (self.emails or self.phones or self.addresses)

    def to_display_string(self) -> str:
        """转换为可读字符串"""
        parts = []
        if self.emails:
            parts.append("邮箱: " + ", ".join(self.emails))
        if self.phones:
            parts.append("电话: " + ", ".join(self.phones))
        if self.addresses:
            parts.append("地址: " + "; ".join(self.addresses))
        return "; ".join(parts) if parts else "未找到联系信息"


class GlobalContactExtractor:
    """全球联系信息提取器"""

    # 邮箱正则 - 支持常见顶级域名
    EMAIL_PATTERN = re.compile(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        re.IGNORECASE
    )

    # 电话号码正则 - 支持国际格式
    # 匹配格式: +86-xxx-xxxx-xxxx, 0086-xxx-xxxx-xxxx, (xxx) xxx-xxxx, xxx-xxx-xxxx, 手机号等
    PHONE_PATTERNS = [
        # 国际格式: +86, 0086, +1, +44 等
        re.compile(r'\+[\d\s\-().]{7,20}\d'),
        # 带国家代码的各种格式
        re.compile(r'(\+\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'),
        # 常见格式
        re.compile(r'\d{3,4}[-\s]?\d{3,4}[-\s]?\d{3,4}'),
        # 手机号 (中国)
        re.compile(r'1[3-9]\d{9}'),
        # 美国格式
        re.compile(r'\(\d{3}\)\s?\d{3}[-.]?\d{4}'),
        # 英国格式
        re.compile(r'\d{4}[-\s]?\d{6}'),
        # 德国格式
        re.compile(r'\d{3,5}[-\s]?\d{3,8}'),
        # 日本格式
        re.compile(r'\d{2,4}[-\s]?\d{3,4}[-\s]?\d{3,4}'),
        # 韩国格式
        re.compile(r'\d{2,3}[-\s]?\d{3,4}[-\s]?\d{4}'),
    ]

    # 地址关键词 (多语言)
    ADDRESS_KEYWORDS = {
        'zh': ['地址', '地址:', '地址：', '公司地址', '收货地址', '寄件地址', '办公地址',
               'street', 'st.', 'avenue', 'ave.', 'road', 'rd.', 'floor', 'suite',
               'building', '号', '路', '街', '弄', '栋', '单元', '室'],
        'en': ['address', 'street', 'st.', 'avenue', 'ave.', 'road', 'rd.', 'boulevard',
               'blvd.', 'lane', 'drive', 'dr.', 'floor', 'suite', 'ste.', 'building',
               'apartment', 'apt.', 'unit', '#', 'zip', 'postal', 'city', 'country']
    }

    # 常见的地址格式模式
    ADDRESS_PATTERNS = [
        # 国家/城市 + 详细地址
        re.compile(r'(?:Address|地址)[:：]?\s*([^\n<@"]{10,200})', re.IGNORECASE),
        # 邮箱中的地址
        re.compile(r'(\d+\s+[\w\s]+(?:street|st\.|avenue|ave\.|road|rd\.|drive|dr\.|boulevard|blvd\.)[^\n<@"]{0,100})', re.IGNORECASE),
        # 中国地址格式
        re.compile(r'([\u4e00-\u9fa5]+(?:省|市|区|县)[^\n<@"]{5,100})'),
        # 详细地址行
        re.compile(r'(\d+[号#][^\n<@"]{5,80})'),
    ]

    def __init__(self):
        self.html_text = None
        self.plain_text = None

    def clean_html(self, text: str) -> str:
        """清理 HTML 标签，提取纯文本"""
        if not text:
            return ""

        # 转义 HTML 实体
        text = html.unescape(text)

        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', text)

        # 规范化空白字符
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def extract_all(self, content: str) -> ContactInfo:
        """
        从内容中提取所有联系信息

        Args:
            content: 邮件内容 (可能是 HTML 或纯文本)

        Returns:
            ContactInfo 对象
        """
        # 清理内容
        if '<' in content:
            self.html_text = content
            self.plain_text = self.clean_html(content)
        else:
            self.plain_text = content
            self.html_text = None

        # 提取各种信息
        emails = self.extract_emails(self.plain_text)
        phones = self.extract_phones(self.plain_text)
        addresses = self.extract_addresses(self.plain_text)

        return ContactInfo(emails=emails, phones=phones, addresses=addresses)

    def extract_emails(self, text: str) -> List[str]:
        """从文本中提取邮箱地址"""
        if not text:
            return []

        matches = self.EMAIL_PATTERN.findall(text)

        # 过滤掉常见的无效邮箱
        filtered = []
        for email in matches:
            email_lower = email.lower()
            # 排除常见的无意义邮箱
            if any(skip in email_lower for skip in ['example.com', 'test.com', 'localhost']):
                continue
            # 排除自己域名的邮箱 (如果已知)
            if email_lower.endswith('@feishu.cn') or email_lower.endswith('@larkoffice.com'):
                continue
            if email not in filtered:
                filtered.append(email)

        return filtered

    def extract_phones(self, text: str) -> List[str]:
        """从文本中提取电话号码"""
        if not text:
            return []

        phones = set()

        for pattern in self.PHONE_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                # 清理电话号码
                phone = self._clean_phone(match)
                if self._is_valid_phone(phone):
                    phones.add(phone)

        return list(phones)

    def _clean_phone(self, phone: str) -> str:
        """清理电话号码格式"""
        # 移除多余空白
        phone = ' '.join(phone.split())

        # 确保以 + 开头或数字开头
        if not re.match(r'^[\+]?\d', phone):
            return phone

        return phone.strip()

    def _is_valid_phone(self, phone: str) -> bool:
        """验证电话号码是否有效"""
        if not phone:
            return False

        # 移除非数字字符（保留 + 号）
        digits = re.sub(r'[^\d+]', '', phone)

        # 检查是否有足够的数字
        digit_count = digits.replace('+', '').replace(' ', '')

        # 有效电话通常有 7-15 位数字
        if len(digit_count) < 7 or len(digit_count) > 15:
            return False

        # 排除太短的匹配
        if len(phone) < 7:
            return False

        # 排除全是相同数字的 (可能是日期等)
        if len(set(digit_count.replace('+', ''))) < 3:
            return False

        return True

    def extract_addresses(self, text: str) -> List[str]:
        """从文本中提取地址"""
        if not text:
            return []

        addresses = []

        for pattern in self.ADDRESS_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                addr = match.strip()
                # 进一步验证地址
                if self._is_valid_address(addr):
                    addresses.append(addr)

        # 去重
        seen = set()
        unique_addresses = []
        for addr in addresses:
            # 归一化比较
            normalized = addr.lower().replace(' ', '').replace('\n', '')
            if normalized not in seen and len(addr) > 10:
                seen.add(normalized)
                unique_addresses.append(addr)

        return unique_addresses

    def _is_valid_address(self, text: str) -> bool:
        """验证文本是否可能是有效地址"""
        if not text or len(text) < 10:
            return False

        # 检查是否包含地址相关关键词
        text_lower = text.lower()
        keywords = self.ADDRESS_KEYWORDS['zh'] + self.ADDRESS_KEYWORDS['en']

        has_keyword = any(kw.lower() in text_lower for kw in keywords)
        has_number = any(c.isdigit() for c in text)

        # 需要有数字和关键词，或足够长的中文字符串
        if has_keyword and has_number:
            return True

        # 中文字符串地址
        if re.search(r'[\u4e00-\u9fa5]', text) and len(text) >= 15:
            # 检查是否包含行政区划关键词
            regions = ['省', '市', '区', '县', '街', '路', '道', '号', '楼', '室', '栋', '幢']
            if any(r in text for r in regions):
                return True

        return False

    def extract_contact_from_sender(self, sender_info: str) -> ContactInfo:
        """
        从发件人信息中提取联系方式

        Args:
            sender_info: 发件人信息 (格式如 "姓名 <email@example.com>")

        Returns:
            ContactInfo 对象
        """
        emails = self.extract_emails(sender_info)
        return ContactInfo(emails=emails, phones=[], addresses=[])
