"""
高级联系信息提取器
采用多层提取 + 交叉验证策略，从邮件文本中高精度提取结构化联系信息
"""

import re
import html
import phonenumbers
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ExtractionConfidence(Enum):
    """提取置信度"""
    HIGH = "high"      # 高置信度
    MEDIUM = "medium"  # 中置信度
    LOW = "low"        # 低置信度
    UNKNOWN = "unknown"


@dataclass
class StructuredContact:
    """结构化联系信息"""
    name: str = ""
    phone: str = ""
    country: str = ""
    province: str = ""
    city: str = ""
    street: str = ""
    postal_code: str = ""

    # 置信度分数 (0-100)
    name_confidence: int = 0
    phone_confidence: int = 0
    address_confidence: int = 0

    # 原始提取结果（用于调试）
    raw_name: List[str] = field(default_factory=list)
    raw_phones: List[str] = field(default_factory=list)
    raw_addresses: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """检查是否所有字段都为空"""
        return not any([self.name, self.phone, self.country, self.province,
                        self.city, self.street, self.postal_code])

    def to_display_string(self) -> str:
        """转换为指定格式的显示字符串"""
        parts = []
        if self.name:
            parts.append(f"姓名: {self.name}")
        if self.phone:
            parts.append(f"电话: [{self.phone}]")
        if self.country:
            parts.append(f"国家: {self.country}")
        if self.province:
            parts.append(f"省份: {self.province}")
        if self.city:
            parts.append(f"城市: {self.city}")
        if self.street:
            parts.append(f"街道: {self.street}")
        if self.postal_code:
            parts.append(f"邮编: {self.postal_code}")
        return "\n".join(parts) if parts else ""


class AdvancedContactExtractor:
    """高级联系信息提取器 - 多层提取 + 交叉验证"""

    def __init__(self):
        self.plain_text = ""

    def clean_html(self, text: str) -> str:
        """清理 HTML 标签，提取纯文本"""
        if not text:
            return ""

        text = html.unescape(text)

        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', text)

        # 规范化空白字符
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def extract(self, content: str) -> StructuredContact:
        """
        从邮件内容中提取结构化联系信息

        Args:
            content: 邮件内容 (可能是 HTML 或纯文本)

        Returns:
            StructuredContact 对象
        """
        # 清理内容
        if '<' in content:
            self.plain_text = self.clean_html(content)
        else:
            self.plain_text = content

        # 提取各类信息
        result = StructuredContact()

        # 1. 提取姓名 (高优先级)
        name, name_conf = self._extract_name()
        result.name = name
        result.name_confidence = name_conf
        result.raw_name = self._extract_name_candidates()

        # 2. 提取电话 (高优先级，使用 phonenumbers 库验证)
        phone, phone_conf = self._extract_phone()
        result.phone = phone
        result.phone_confidence = phone_conf
        result.raw_phones = self._extract_phone_candidates()

        # 3. 提取地址信息 (中优先级)
        addr_result = self._extract_address()
        result.country = addr_result['country']
        result.province = addr_result['province']
        result.city = addr_result['city']
        result.street = addr_result['street']
        result.postal_code = addr_result['postal_code']
        result.address_confidence = addr_result['confidence']
        result.raw_addresses = addr_result['raw_candidates']

        return result

    def _extract_name_candidates(self) -> List[str]:
        """提取所有可能的姓名候选"""
        candidates = []
        text = self.plain_text

        # 模式1: Name: / Name: / Full Name: 等标签后
        name_label_patterns = [
            r'(?:Full\s+)?Name[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})',
            r'(?:Recipient|Contact|Person)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})',
            r'From[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})',
        ]

        for pattern in name_label_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            candidates.extend(matches)

        # 模式2: 邮件签名中的姓名 (大写字母开头的多词姓名)
        signature_patterns = [
            r'\n([A-Z][a-z]{1,15}\s+[A-Z][a-z]{1,15}(?:\s+[A-Z][a-z]{1,15})?)\s*(?:\n|[-=~])',
            r'(?<=\n)([A-Z][a-z]+\s+[A-Z][a-z]+)\s*(?:Best|Regards|Sincerely|Thanks|Yours)',
        ]

        for pattern in signature_patterns:
            matches = re.findall(pattern, text)
            candidates.extend(matches)

        # 去重并过滤
        seen = set()
        filtered = []
        for name in candidates:
            normalized = name.strip().lower()
            if normalized not in seen and len(name) > 3:
                seen.add(normalized)
                filtered.append(name.strip())

        return filtered

    def _extract_name(self) -> Tuple[str, int]:
        """提取最可能的姓名"""
        candidates = self._extract_name_candidates()

        if not candidates:
            return "", 0

        # 评分策略
        best_name = ""
        best_score = 0

        for name in candidates:
            score = 0
            words = name.split()

            # 2-3个词的名字最常见，得分更高
            if 2 <= len(words) <= 3:
                score += 30
            elif len(words) == 4:
                score += 20
            else:
                score -= 10

            # 检查是否包含常见名字
            common_first_names = {'john', 'james', 'mary', 'sarah', 'michael', 'david', 'emma',
                                  'chase', 'alex', 'charlie', 'jennifer', 'robert', 'william'}

            first_name = words[0].lower() if words else ""
            if first_name in common_first_names:
                score += 30

            # 检查是否全为首字母大写
            if all(w[0].isupper() for w in words):
                score += 15

            # 名字太短扣分
            if len(name) < 6:
                score -= 20

            if score > best_score:
                best_score = score
                best_name = name

        # 计算置信度
        confidence = min(100, max(0, best_score))

        return best_name, confidence

    def _extract_phone_candidates(self) -> List[str]:
        """提取所有可能的电话号码候选"""
        candidates = []
        text = self.plain_text

        # 使用 phonenumbers 库解析
        for match in phonenumbers.PhoneNumberMatcher(text, None):
            formatted = phonenumbers.format_number(
                match.number,
                phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )
            candidates.append(formatted)

        # 补充正则匹配（捕捉 phonenumbers 可能遗漏的）
        phone_patterns = [
            r'\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
            r'\d{4}[-\s]?\d{6}',  # 英国格式
            r'\d{5}[-\s]?\d{6}',  # 英国格式
        ]

        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # 验证格式
                digits = re.sub(r'[^\d]', '', match)
                if 7 <= len(digits) <= 15:
                    candidates.append(match)

        # 去重
        seen = set()
        filtered = []
        for phone in candidates:
            digits = re.sub(r'[^\d]', '', phone)
            if digits not in seen:
                seen.add(digits)
                filtered.append(phone)

        return filtered

    def _extract_phone(self) -> Tuple[str, int]:
        """提取最可能的电话号码"""
        candidates = self._extract_phone_candidates()

        if not candidates:
            return "", 0

        # 评分策略
        best_phone = ""
        best_score = 0

        for phone in candidates:
            score = 0

            try:
                # 使用 phonenumbers 验证
                parsed = phonenumbers.parse(phone, None)
                if phonenumbers.is_valid_number(parsed):
                    score += 50
                    # 获取地区信息
                    region = phonenumbers.region_code_for_number(parsed)
                    if region:
                        score += 20
            except:
                # 无法用 phonenumbers 解析
                pass

            # 有 + 号的更可能是国际号码
            if '+' in phone:
                score += 20

            # 长度适中 (10-15位) 更可能是真实电话
            digits = re.sub(r'[^\d]', '', phone)
            if 10 <= len(digits) <= 15:
                score += 15

            if score > best_score:
                best_score = score
                best_phone = phone

        return best_phone, min(100, max(0, best_score))

    def _extract_address(self) -> Dict:
        """提取地址信息"""
        text = self.plain_text
        result = {
            'country': '',
            'province': '',
            'city': '',
            'street': '',
            'postal_code': '',
            'confidence': 0,
            'raw_candidates': []
        }

        # 1. 提取邮政编码 (最容易识别)
        postal_code = self._extract_postal_code(text)
        result['postal_code'] = postal_code

        # 2. 提取国家
        country = self._extract_country(text)
        result['country'] = country

        # 3. 提取省份/州
        province = self._extract_province(text, country)
        result['province'] = province

        # 4. 提取城市
        city = self._extract_city(text, country, province)
        result['city'] = city

        # 5. 提取街道
        street = self._extract_street(text)
        result['street'] = street

        # 6. 收集原始候选
        result['raw_candidates'] = [
            postal_code, country, province, city, street
        ]

        # 计算地址置信度
        filled_fields = sum([
            bool(postal_code),
            bool(country),
            bool(province),
            bool(city),
            bool(street)
        ])
        result['confidence'] = min(100, filled_fields * 20)

        return result

    def _extract_postal_code(self, text: str) -> str:
        """提取邮政编码"""
        # 英国格式: MK41 0AQ
        uk_pattern = r'\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b'
        uk_match = re.search(uk_pattern, text, re.IGNORECASE)
        if uk_match:
            return uk_match.group(1).upper()

        # 美国格式: 12345 或 12345-6789
        us_pattern = r'\b(\d{5}(?:-\d{4})?)\b'
        us_match = re.search(us_pattern, text)
        if us_match:
            postal = us_match.group(1)
            # 排除日期等数字
            if not re.match(r'^\d{5}(-\d{4})?$', postal):
                pass
            else:
                return postal

        # 加拿大格式: A1A 1A1
        ca_pattern = r'\b([A-Z]\d[A-Z]\s?\d[A-Z]\d)\b'
        ca_match = re.search(ca_pattern, text, re.IGNORECASE)
        if ca_match:
            return ca_match.group(1).upper()

        # 澳大利亚格式: 2000
        au_pattern = r'\b(\d{4})\b'
        au_match = re.search(au_pattern, text)
        if au_match:
            postal = au_match.group(1)
            # 可能是邮编，排除明显不是的
            if postal in ['1234', '0000', '1111']:
                pass
            else:
                return postal

        # 通用格式: 数字+字母组合
        general_pattern = r'\b(\d{3,6}[A-Z]{0,2})\b'
        for match in re.finditer(general_pattern, text):
            postal = match.group(1)
            if 4 <= len(postal) <= 6:
                return postal

        return ""

    def _extract_country(self, text: str) -> str:
        """提取国家"""
        # 常见国家列表
        countries = [
            'United Kingdom', 'United States', 'United States of America',
            'Canada', 'Australia', 'Germany', 'France', 'Spain', 'Italy',
            'Netherlands', 'Belgium', 'Switzerland', 'Austria', 'Poland',
            'Sweden', 'Norway', 'Denmark', 'Finland', 'Ireland',
            'New Zealand', 'Japan', 'China', 'Singapore', 'Hong Kong',
            'South Korea', 'India', 'Brazil', 'Mexico', 'South Africa',
            'Russia', 'Ukraine', 'Turkey', 'Greece', 'Portugal'
        ]

        # 优先查找带有 Country: 标签的
        country_pattern = r'Country[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'

        # 检查地址相关上下文
        address_context = self._get_address_context(text)

        for country in countries:
            # 优先检查标签后的国家
            pattern = rf'Country[:\s]+{re.escape(country)}'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return country

            # 检查是否在地址上下文中
            if country.lower() in address_context.lower():
                return country

        # 缩写映射
        abbreviations = {
            'UK': 'United Kingdom',
            'USA': 'United States',
            'US': 'United States',
            'U.S.': 'United States',
            'U.S.A.': 'United States of America'
        }

        for abbr, full in abbreviations.items():
            if re.search(rf'\b{abbr}\b', text):
                return full

        return ""

    def _extract_province(self, text: str, country: str) -> str:
        """提取省份/州"""
        # 常见州/省
        provinces = {
            'United States': ['California', 'New York', 'Texas', 'Florida', 'Illinois',
                             'Pennsylvania', 'Ohio', 'Georgia', 'North Carolina', 'Michigan',
                             'New Jersey', 'Virginia', 'Washington', 'Arizona', 'Massachusetts'],
            'United Kingdom': ['Bedfordshire', 'London', 'Manchester', 'Birmingham', 'Leeds',
                             'Liverpool', 'Bristol', 'Oxfordshire', 'Cambridgeshire', 'Yorkshire'],
            'Canada': ['Ontario', 'Quebec', 'British Columbia', 'Alberta', 'Manitoba',
                      'Nova Scotia', 'New Brunswick'],
            'Australia': ['New South Wales', 'Victoria', 'Queensland', 'Western Australia',
                         'South Australia'],
        }

        # 优先查找标签
        province_patterns = [
            r'State[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'Province[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'County[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]

        for pattern in province_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        # 根据国家查找省份
        if country in provinces:
            address_context = self._get_address_context(text)
            for province in provinces[country]:
                if province.lower() in address_context.lower():
                    return province

        return ""

    def _extract_city(self, text: str, country: str, province: str) -> str:
        """提取城市"""
        # 优先查找标签
        city_patterns = [
            r'City[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'Town[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        ]

        for pattern in city_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        # 地址上下文中的城市
        address_context = self._get_address_context(text)

        # 常见城市
        common_cities = [
            'London', 'Manchester', 'Birmingham', 'Leeds', 'Liverpool',
            'New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix',
            'Toronto', 'Vancouver', 'Montreal', 'Calgary',
            'Sydney', 'Melbourne', 'Brisbane', 'Perth',
            'Paris', 'Berlin', 'Munich', 'Frankfurt',
            'Tokyo', 'Singapore', 'Hong Kong', 'Shanghai', 'Beijing'
        ]

        for city in common_cities:
            if city.lower() in address_context.lower():
                return city

        return ""

    def _extract_street(self, text: str) -> str:
        """提取街道地址"""
        # 优先查找标签
        street_patterns = [
            r'Address[:\s]+([^\n]{5,100})',
            r'Street[:\s]+([^\n]{5,100})',
            r'Street\s+([A-Z0-9][^\n]{5,100})',
            r'(?:^|\n)([0-9]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}(?:\s+(?:Street|St\.|Avenue|Ave\.|Road|Rd\.|Drive|Dr\.|Lane|Ln\.|Boulevard|Blvd\.))?)',
        ]

        # 常见街道类型
        street_types = [
            'Street', 'St.', 'St', 'Avenue', 'Ave.', 'Ave',
            'Road', 'Rd.', 'Rd', 'Drive', 'Dr.', 'Dr',
            'Lane', 'Ln.', 'Ln', 'Boulevard', 'Blvd.', 'Blvd',
            'Building', 'Floor', 'Suite', 'Ste.', 'Ste', 'Unit', '#'
        ]

        street_type_pattern = '|'.join(re.escape(t) for t in street_types)

        # 更通用的街道模式
        pattern = rf'(?:^|\n)\s*([0-9]+\s+[A-Z][a-z]{{0,20}}(?:\s+[A-Z][a-z]{{0,20}}){{0,4}}\s+(?:{street_type_pattern})[.,]?\s*[A-Z0-9]{{0,50}})'
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()

        # 备用: Address 标签
        address_pattern = r'Address[:\s]+([^\n]{10,150})'
        match = re.search(address_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return ""

    def _get_address_context(self, text: str) -> str:
        """获取地址可能出现的上下文区域"""
        # 查找包含地址关键词的区域
        address_keywords = [
            'address', 'street', 'avenue', 'road', 'floor', 'suite',
            'city', 'country', 'postal', 'zip', 'code'
        ]

        lines = text.split('\n')
        context_lines = []

        for i, line in enumerate(lines):
            line_lower = line.lower()
            # 当前行包含关键词
            if any(kw in line_lower for kw in address_keywords):
                # 收集当前行及前后各1行
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                context_lines.extend(lines[start:end])

        return ' '.join(context_lines)
