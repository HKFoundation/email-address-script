"""
高级联系信息提取器

面向 KOL 邮件线程的结构化信息提取：
1. 收货/联系人信息：Full Name、Phone Number、Country、Province、City、Street、Postal Code
2. 收款/银行信息：Account Name、Routing/Sort Code、Account Number、SWIFT/BIC、Bank Address、Company Address、Bank Zip Code

设计重点：先识别信息块，再在块内提取字段，避免把物流单号、银行地址、历史报价等误判成电话或收货地址。
"""

import re
import html
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

try:
    import phonenumbers
except ImportError:  # 运行环境缺少依赖时仍可退化为正则提取
    phonenumbers = None


class ExtractionConfidence(Enum):
    """提取置信度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass
class StructuredContact:
    """结构化联系信息"""
    # 收货/联系人信息
    name: str = ""
    phone: str = ""
    country: str = ""
    province: str = ""
    city: str = ""
    street: str = ""
    postal_code: str = ""

    # 收款/银行信息
    bank_account_name: str = ""
    bank_routing_number: str = ""
    bank_account_number: str = ""
    bank_swift_bic: str = ""
    bank_address: str = ""
    company_address: str = ""
    bank_zip_code: str = ""
    bank_iban: str = ""
    paypal: str = ""

    # 置信度分数 (0-100)
    name_confidence: int = 0
    phone_confidence: int = 0
    address_confidence: int = 0
    bank_confidence: int = 0

    # 原始提取结果（用于调试）
    raw_name: List[str] = field(default_factory=list)
    raw_phones: List[str] = field(default_factory=list)
    raw_addresses: List[str] = field(default_factory=list)
    raw_bank_info: List[str] = field(default_factory=list)

    SHIPPING_FIELDS = ("name", "phone", "country", "province", "city", "street", "postal_code")
    PAYMENT_FIELDS = (
        "bank_account_name", "bank_routing_number", "bank_account_number",
        "bank_swift_bic", "bank_address", "company_address", "bank_zip_code",
    )

    SHIPPING_LABELS = {
        "name": "姓名",
        "phone": "电话",
        "country": "国家",
        "province": "省份",
        "city": "城市",
        "street": "街道",
        "postal_code": "邮编",
    }

    PAYMENT_LABELS = {
        "bank_account_name": "账户名称",
        "bank_routing_number": "路由号码",
        "bank_account_number": "银行账号",
        "bank_swift_bic": "银行代码",
        "bank_address": "银行地址",
        "company_address": "公司地址",
        "bank_zip_code": "银行邮编",
    }

    def is_empty(self) -> bool:
        """检查是否所有字段都为空"""
        return not any([
            self.name, self.phone, self.country, self.province, self.city,
            self.street, self.postal_code, self.bank_account_name,
            self.bank_routing_number, self.bank_account_number,
            self.bank_swift_bic, self.bank_address, self.company_address,
            self.bank_zip_code, self.bank_iban, self.paypal,
        ])

    def to_display_string(self) -> str:
        """转换为指定格式的显示字符串"""
        sections = []

        shipping_info = self.to_shipping_display_string()
        if shipping_info:
            sections.append("收货信息:\n" + shipping_info)

        payment_info = self.to_payment_display_string()
        if payment_info:
            sections.append("收款信息:\n" + payment_info)

        return "\n\n".join(sections) if sections else ""

    def to_shipping_display_string(self) -> str:
        """转换为 Excel 收货信息列显示字符串。"""
        return "\n".join(self._display_parts(self.SHIPPING_FIELDS, self.SHIPPING_LABELS))

    def to_payment_display_string(self) -> str:
        """转换为 Excel 收款信息列显示字符串。"""
        return "\n".join(self._display_parts(self.PAYMENT_FIELDS, self.PAYMENT_LABELS))

    def shipping_field_count(self) -> int:
        """已提取到的收货信息字段数。"""
        return self._field_count(self.SHIPPING_FIELDS)

    def payment_field_count(self) -> int:
        """已提取到的收款信息字段数。"""
        return self._field_count(self.PAYMENT_FIELDS)

    def _field_count(self, fields) -> int:
        return sum(bool(getattr(self, field)) for field in fields)

    def _display_parts(self, fields, labels) -> List[str]:
        parts = []
        for field in fields:
            value = getattr(self, field)
            if value:
                parts.append(f"{labels[field]}: {value}")
        return parts


class AdvancedContactExtractor:
    """高级联系信息提取器 - 多层提取 + 交叉验证"""

    COUNTRY_ALIASES = {
        "united states": "United States",
        "united states of america": "United States",
        "usa": "United States",
        "u.s.a": "United States",
        "u.s.a.": "United States",
        "u.s.": "United States",
        "us": "United States",
        "united kingdom": "United Kingdom",
        "great britain": "United Kingdom",
        "england": "United Kingdom",
        "scotland": "United Kingdom",
        "wales": "United Kingdom",
        "uk": "United Kingdom",
        "gb": "United Kingdom",
        "netherlands": "Netherlands",
        "the netherlands": "Netherlands",
        "holland": "Netherlands",
        "nl": "Netherlands",
        "canada": "Canada",
        "ca": "Canada",
        "australia": "Australia",
        "au": "Australia",
        "new zealand": "New Zealand",
        "nz": "New Zealand",
        "germany": "Germany",
        "deutschland": "Germany",
        "de": "Germany",
        "france": "France",
        "fr": "France",
        "spain": "Spain",
        "es": "Spain",
        "italy": "Italy",
        "it": "Italy",
        "ireland": "Ireland",
        "ie": "Ireland",
        "belgium": "Belgium",
        "be": "Belgium",
        "switzerland": "Switzerland",
        "ch": "Switzerland",
        "austria": "Austria",
        "at": "Austria",
        "poland": "Poland",
        "pl": "Poland",
        "portugal": "Portugal",
        "pt": "Portugal",
        "sweden": "Sweden",
        "se": "Sweden",
        "norway": "Norway",
        "no": "Norway",
        "denmark": "Denmark",
        "dk": "Denmark",
        "finland": "Finland",
        "fi": "Finland",
        "czech republic": "Czech Republic",
        "czechia": "Czech Republic",
        "cz": "Czech Republic",
        "slovakia": "Slovakia",
        "sk": "Slovakia",
        "hungary": "Hungary",
        "hu": "Hungary",
        "romania": "Romania",
        "ro": "Romania",
        "greece": "Greece",
        "gr": "Greece",
        "turkey": "Turkey",
        "turkiye": "Turkey",
        "tr": "Turkey",
        "mexico": "Mexico",
        "mx": "Mexico",
        "brazil": "Brazil",
        "br": "Brazil",
        "south africa": "South Africa",
        "za": "South Africa",
        "singapore": "Singapore",
        "sg": "Singapore",
        "hong kong": "Hong Kong",
        "hk": "Hong Kong",
        "japan": "Japan",
        "jp": "Japan",
        "south korea": "South Korea",
        "korea": "South Korea",
        "kr": "South Korea",
    }

    COUNTRY_TO_REGION = {
        "United States": "US",
        "United Kingdom": "GB",
        "Netherlands": "NL",
        "Canada": "CA",
        "Australia": "AU",
        "New Zealand": "NZ",
        "Germany": "DE",
        "France": "FR",
        "Spain": "ES",
        "Italy": "IT",
        "Ireland": "IE",
        "Belgium": "BE",
        "Switzerland": "CH",
        "Austria": "AT",
        "Poland": "PL",
        "Portugal": "PT",
        "Sweden": "SE",
        "Norway": "NO",
        "Denmark": "DK",
        "Finland": "FI",
        "Mexico": "MX",
        "Brazil": "BR",
        "South Africa": "ZA",
        "Singapore": "SG",
        "Hong Kong": "HK",
        "Japan": "JP",
        "South Korea": "KR",
    }

    US_STATE_CODES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "IA",
        "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO",
        "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH", "OK",
        "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI",
        "WV", "WY", "DC",
    }

    STREET_TYPES = [
        "street", "st", "st.", "avenue", "ave", "ave.", "road", "rd", "rd.",
        "drive", "dr", "dr.", "lane", "ln", "ln.", "boulevard", "blvd", "blvd.",
        "court", "ct", "ct.", "circle", "cir", "cir.", "close", "way", "place",
        "pl", "pl.", "terrace", "terr", "parkway", "pkwy", "highway", "hwy",
        "trail", "row", "mews", "gardens", "garden", "grove", "park", "hill",
        "view", "walk", "rise", "square", "sq", "sq.", "loop", "crescent",
        "strada", "via", "rue", "chemin", "allee", "allée", "platz", "strasse",
        "straße", "straat", "weg", "laan", "dijk", "plein", "pad", "hof", "kade",
        "gracht", "singel",
    ]

    # 单独拆出来，避免上面的长字典可读性过差
    BANK_FIELD_PATTERNS = {
        "bank_account_name": [r"account\s+name", r"beneficiary\s+name", r"recipient\s+name"],
        "bank_routing_number": [
            r"routing\s+number", r"routing\s+no\.?", r"sort\s+code", r"aba\s+number",
            r"routing\s+transit\s+number", r"bsb",
        ],
        "bank_account_number": [
            r"bank\s+account\s+number", r"account\s+number", r"account\s+no\.?"
        ],
        "bank_swift_bic": [r"swift\s*(?:code)?\s*/?\s*bic", r"bic", r"swift\s+code", r"swift"],
        "bank_address": [r"bank\s+addres{1,2}"],
        "company_address": [r"company\s+addres{1,2}", r"business\s+addres{1,2}"],
        "bank_zip_code": [r"bank\s+(?:zip|postal)\s+code", r"bank\s+postcode"],
        "bank_iban": [r"iban"],
    }

    ADDRESS_FIELD_PATTERNS = {
        "name": [r"full\s+name", r"recipient\s+name", r"contact\s+name", r"receiver\s+name"],
        "phone": [r"phone\s+number", r"phone", r"mobile", r"telephone", r"tel", r"whats\s*app", r"contact\s+number"],
        "country": [r"country"],
        "province": [r"state\s*/\s*province", r"state\s+or\s+province", r"province", r"state", r"county", r"region"],
        "city": [r"city", r"town"],
        "street": [
            r"street\s+address", r"shipping\s+address", r"delivery\s+address",
            r"mailing\s+address", r"address\s+line\s*1", r"address",
        ],
        "postal_code": [r"postal\s+code", r"post\s+code", r"postcode", r"zip\s+code", r"zip"],
    }

    BANK_CONTEXT_WORDS = (
        "bank", "account", "routing", "sort code", "swift", "bic", "iban",
        "beneficiary", "wire", "payment", "tax form", "company address", "company addres",
    )

    JUNK_LINE_PREFIXES = (
        "from:", "to:", "cc:", "bcc:", "date:", "subject:", "on ", "sent from",
        "best regards", "kind regards", "regards", "thanks,", "thank you", "hi ", "hello ",
    )

    def __init__(self):
        self.plain_text = ""
        self.lines: List[str] = []

    def clean_html(self, text: str) -> str:
        """清理 HTML 标签，同时尽量保留换行边界。"""
        if not text:
            return ""

        text = html.unescape(text)
        text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
        text = re.sub(r"(?i)</\s*(?:p|div|li|tr|td|table|blockquote|h[1-6])\s*>", "\n", text)
        text = re.sub(r"(?i)<\s*(?:p|div|li|tr|td|table|blockquote|h[1-6])\b[^>]*>", "\n", text)
        text = re.sub(r"(?is)<\s*(?:script|style)\b.*?</\s*(?:script|style)\s*>", " ", text)
        text = re.sub(r"<[^>]+>", " ", text)
        return text

    def extract(self, content: str) -> StructuredContact:
        """
        从邮件内容中提取结构化联系信息

        Args:
            content: 邮件内容 (可能是 HTML 或纯文本)

        Returns:
            StructuredContact 对象
        """
        self.plain_text = self._prepare_text(content)
        self.lines = self._to_lines(self.plain_text)

        result = StructuredContact()

        bank_result = self._extract_bank_info()
        result.bank_account_name = bank_result["bank_account_name"]
        result.bank_routing_number = bank_result["bank_routing_number"]
        result.bank_account_number = bank_result["bank_account_number"]
        result.bank_swift_bic = bank_result["bank_swift_bic"]
        result.bank_address = bank_result["bank_address"]
        result.company_address = bank_result["company_address"]
        result.bank_zip_code = bank_result["bank_zip_code"]
        result.bank_iban = bank_result["bank_iban"]
        result.paypal = bank_result["paypal"]
        result.bank_confidence = bank_result["confidence"]
        result.raw_bank_info = bank_result["raw_candidates"]

        addr_result = self._extract_address()
        result.name = addr_result["name"]
        result.phone = addr_result["phone"]
        result.country = addr_result["country"]
        result.province = addr_result["province"]
        result.city = addr_result["city"]
        result.street = addr_result["street"]
        result.postal_code = addr_result["postal_code"]
        result.address_confidence = addr_result["confidence"]
        result.name_confidence = 95 if result.name and addr_result.get("name_source") == "label" else (70 if result.name else 0)
        result.phone_confidence = addr_result.get("phone_confidence", 0)
        result.raw_addresses = addr_result["raw_candidates"]
        result.raw_name = [result.name] if result.name else []
        result.raw_phones = addr_result.get("raw_phones", [])

        return result

    def _prepare_text(self, content: str) -> str:
        """统一清理正文、Markdown 链接、URL、引用符号和不可见字符。"""
        if not content:
            return ""

        text = html.unescape(content)
        if self._looks_like_html(text):
            text = self.clean_html(text)

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\xa0", " ").replace("\u202f", " ").replace("\u200b", "")
        text = text.replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")

        # Markdown 链接保留显示文本，移除 URL。
        text = re.sub(r"\[([^\]\n]{1,200})\]\((?:https?://|mailto:)[^)]+\)", r"\1", text, flags=re.IGNORECASE)
        text = re.sub(r"<\s*(?:https?://|mailto:)[^>]+>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"https?://\S+", "", text, flags=re.IGNORECASE)

        lines = self._to_lines(text)
        return "\n".join(lines)

    def _looks_like_html(self, text: str) -> bool:
        """避免把 From: Name <email> 或 <https://...> 误当成 HTML。"""
        return bool(re.search(
            r"(?i)</?\s*(?:html|body|br|p|div|span|table|tr|td|li|ul|ol|blockquote|a|strong|b|i)\b",
            text,
        ))

    def _to_lines(self, text: str) -> List[str]:
        """按行清理引用符、项目符号、编号和多余空白。"""
        result = []
        for raw in text.split("\n"):
            line = raw.strip()
            line = re.sub(r"^(?:>\s*)+", "", line).strip()
            line = re.sub(r"^[\s•·*\-–—]+", "", line).strip()
            line = re.sub(r"^\d{1,3}[\.)]\s*", "", line).strip()
            line = re.sub(r"\s+", " ", line).strip()
            line = self._strip_wrapping_punctuation(line)
            if line:
                result.append(line)
        return result

    def _strip_wrapping_punctuation(self, value: str) -> str:
        return value.strip().strip(" \t\n\r:：-–—=;,|[](){}")

    def _clean_value(self, value: str, keep_na: bool = False) -> str:
        if not value:
            return ""
        value = re.sub(r"<\s*(?:https?://|mailto:)[^>]+>", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\[([^\]]+)\]\((?:https?://|mailto:)[^)]+\)", r"\1", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+", " ", value).strip()
        value = self._strip_wrapping_punctuation(value)
        value = re.sub(r"^(?:is|are)\s+", "", value, flags=re.IGNORECASE).strip()
        if not keep_na and self._is_empty_value(value):
            return ""
        return value

    def _is_empty_value(self, value: str) -> bool:
        if not value:
            return True
        cleaned = value.strip().strip("[](){}:：-–—.,; ").lower()
        return cleaned in {
            "", "n/a", "na", "none", "null", "not applicable", "-", "--", "tbd", "unknown",
            "account name", "routing number", "bank account number", "swift code/bic",
            "bank address", "company address", "bank zip code", "full name", "phone number",
            "country", "state/province", "city", "street address", "postal code", "email",
        }

    def _compile_label_regex(self, pattern: str) -> re.Pattern:
        return re.compile(rf"(?i)(?:^|\b){pattern}\b\s*(?:[:：#=\-–—]+\s*)?")

    def _label_match(self, line: str, patterns: List[str]) -> Optional[re.Match]:
        for pattern in patterns:
            match = self._compile_label_regex(pattern).search(line)
            if match:
                return match
        return None

    def _line_has_any_label(self, line: str) -> bool:
        for patterns in list(self.ADDRESS_FIELD_PATTERNS.values()) + list(self.BANK_FIELD_PATTERNS.values()):
            if self._label_match(line, patterns):
                return True
        return False

    def _line_has_bank_label(self, line: str) -> bool:
        return any(self._label_match(line, patterns) for patterns in self.BANK_FIELD_PATTERNS.values())

    def _is_junk_line(self, line: str) -> bool:
        lower = line.lower().strip()
        if not lower:
            return True
        if any(lower.startswith(prefix) for prefix in self.JUNK_LINE_PREFIXES):
            return True
        if re.match(r"^[=@_\-\s]{4,}$", line):
            return True
        if "forwarded message" in lower:
            return True
        return False

    def _extract_bank_info(self) -> Dict[str, object]:
        result = {
            "bank_account_name": "",
            "bank_routing_number": "",
            "bank_account_number": "",
            "bank_swift_bic": "",
            "bank_address": "",
            "company_address": "",
            "bank_zip_code": "",
            "bank_iban": "",
            "paypal": "",
            "confidence": 0,
            "raw_candidates": [],
        }

        scalar_fields = [
            "bank_account_name", "bank_routing_number", "bank_account_number",
            "bank_swift_bic", "bank_zip_code", "bank_iban",
        ]
        multiline_fields = {"bank_address", "company_address"}

        for field in scalar_fields:
            value = self._extract_labeled_scalar(self.BANK_FIELD_PATTERNS[field], bank_mode=True, field=field)
            if value:
                result[field] = self._normalize_bank_field(field, value)

        for field in multiline_fields:
            value = self._extract_labeled_multiline(self.BANK_FIELD_PATTERNS[field], bank_mode=True, field=field)
            if value:
                result[field] = self._normalize_multiline_address(value, keep_na=(field == "company_address"))

        result["paypal"] = self._extract_paypal()

        # 如果没有 Bank Zip Code 标签，但银行地址里包含邮编，就从银行地址中补一个。
        if not result["bank_zip_code"] and result["bank_address"]:
            result["bank_zip_code"] = self._extract_postal_code(result["bank_address"], result.get("country", ""))

        raw = [str(v) for k, v in result.items() if k not in {"confidence", "raw_candidates"} and v]
        result["raw_candidates"] = raw
        filled = sum(bool(result[field]) for field in [
            "bank_account_name", "bank_routing_number", "bank_account_number",
            "bank_swift_bic", "bank_address", "company_address", "bank_zip_code",
            "bank_iban", "paypal",
        ])
        result["confidence"] = min(100, filled * 12)
        return result

    def _extract_labeled_scalar(self, patterns: List[str], bank_mode: bool, field: str = "") -> str:
        for idx, line in enumerate(self.lines):
            if bank_mode is False and self._is_bank_context(line):
                continue
            match = self._label_match(line, patterns)
            if not match:
                continue
            if not bank_mode and field == "street" and self._is_bank_context(line):
                continue

            value = self._clean_value(line[match.end():], keep_na=(field == "company_address"))
            if value and self._valid_labeled_value(field, value):
                return value

            next_value = self._next_scalar_value(idx, bank_mode=bank_mode, field=field)
            if next_value and self._valid_labeled_value(field, next_value):
                return next_value
        return ""

    def _extract_labeled_multiline(self, patterns: List[str], bank_mode: bool, field: str = "") -> str:
        for idx, line in enumerate(self.lines):
            if bank_mode is False and self._is_bank_context(line):
                continue
            match = self._label_match(line, patterns)
            if not match:
                continue
            if not bank_mode and field == "street" and self._is_bank_context(line):
                continue

            values = []
            same_line = self._clean_value(line[match.end():], keep_na=(field == "company_address"))
            if same_line and self._valid_labeled_value(field, same_line):
                values.append(same_line)

            for nxt in self._collect_following_lines(idx, bank_mode=bank_mode, field=field):
                if self._valid_labeled_value(field, nxt):
                    values.append(nxt)

            if values:
                return "\n".join(values)
        return ""

    def _next_scalar_value(self, idx: int, bank_mode: bool, field: str) -> str:
        for nxt in self._collect_following_lines(idx, bank_mode=bank_mode, field=field, max_lines=4):
            value = self._clean_value(nxt, keep_na=(field == "company_address"))
            if value:
                return value
        return ""

    def _collect_following_lines(self, idx: int, bank_mode: bool, field: str, max_lines: int = 7) -> List[str]:
        values = []
        for line in self.lines[idx + 1: idx + 1 + max_lines]:
            if self._is_junk_line(line):
                break
            if self._line_has_any_label(line):
                break
            if not bank_mode and self._is_bank_context(line):
                break
            if bank_mode and field not in {"bank_address", "company_address"} and len(values) >= 1:
                break
            if not bank_mode and field not in {"street"} and len(values) >= 1:
                break
            cleaned = self._clean_value(line, keep_na=(field == "company_address"))
            if cleaned:
                values.append(cleaned)
        return values

    def _valid_labeled_value(self, field: str, value: str) -> bool:
        if not value:
            return False
        lower = value.lower()
        if "provide" in lower and "details" in lower:
            return False
        if "please" in lower and len(value.split()) > 8:
            return False
        if field in {"bank_routing_number", "bank_account_number"}:
            return bool(re.search(r"\d", value))
        if field == "bank_swift_bic":
            return bool(re.search(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b", value.replace(" ", ""), re.IGNORECASE))
        if field == "bank_iban":
            return bool(re.search(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b", value.replace(" ", ""), re.IGNORECASE))
        if field == "phone":
            return bool(self._extract_phone_candidates(value))
        if field == "country":
            return bool(self._extract_country(value))
        if field == "postal_code":
            return bool(self._extract_postal_code(value))
        if field == "name":
            return self._looks_like_person_name(value, allow_single=False)
        if field == "street":
            return len(value) >= 4 and not self._is_bank_context(value)
        return True

    def _normalize_bank_field(self, field: str, value: str) -> str:
        value = self._clean_value(value, keep_na=(field == "company_address"))
        if field in {"bank_routing_number", "bank_account_number"}:
            match = re.search(r"[A-Z0-9][A-Z0-9\s\-]{2,34}[A-Z0-9]", value, re.IGNORECASE)
            return match.group(0).strip() if match else value
        if field == "bank_swift_bic":
            compact = re.sub(r"\s+", "", value).upper()
            match = re.search(r"[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?", compact)
            return match.group(0) if match else compact
        if field == "bank_iban":
            compact = re.sub(r"\s+", "", value).upper()
            match = re.search(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", compact)
            return match.group(0) if match else compact
        if field == "bank_zip_code":
            postal = self._extract_postal_code(value)
            return postal or value
        return value

    def _normalize_multiline_address(self, value: str, keep_na: bool = False) -> str:
        lines = []
        for line in value.split("\n"):
            cleaned = self._clean_value(line, keep_na=keep_na)
            if cleaned:
                lines.append(cleaned)
        return ", ".join(lines)

    def _extract_paypal(self) -> str:
        text = "\n".join(self.lines)
        match = re.search(r"(?i)\bpaypal\b[^\n\r]*?([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", text)
        if match:
            return match.group(1)
        return ""

    def _extract_address(self) -> Dict[str, object]:
        labeled = self._extract_labeled_address()
        unstructured = self._extract_unstructured_address()

        result = {
            "name": labeled.get("name") or unstructured.get("name", ""),
            "phone": labeled.get("phone") or unstructured.get("phone", ""),
            "country": labeled.get("country") or unstructured.get("country", ""),
            "province": labeled.get("province") or unstructured.get("province", ""),
            "city": labeled.get("city") or unstructured.get("city", ""),
            "street": labeled.get("street") or unstructured.get("street", ""),
            "postal_code": labeled.get("postal_code") or unstructured.get("postal_code", ""),
            "confidence": 0,
            "raw_candidates": [],
            "raw_phones": [],
            "name_source": "label" if labeled.get("name") else ("unstructured" if unstructured.get("name") else ""),
            "phone_confidence": 0,
        }

        result["country"] = self._extract_country(result["country"]) or result["country"]
        if result["phone"]:
            phone, confidence = self._choose_phone([result["phone"]], country=result["country"])
            result["phone"] = phone or result["phone"]
            result["phone_confidence"] = confidence

        if not result["postal_code"] and (result["street"] or result["city"] or result["country"]):
            context = "\n".join([result["street"], result["city"], result["province"], result["country"]])
            result["postal_code"] = self._extract_postal_code(context, result["country"])

        if result["country"] == "United States" and result["province"]:
            result["province"] = result["province"].upper() if len(result["province"]) == 2 else result["province"]

        raw = [result[k] for k in ["name", "phone", "country", "province", "city", "street", "postal_code"] if result[k]]
        result["raw_candidates"] = raw
        result["raw_phones"] = [result["phone"]] if result["phone"] else []

        weights = {
            "name": 10,
            "phone": 15,
            "country": 15,
            "province": 10,
            "city": 15,
            "street": 20,
            "postal_code": 15,
        }
        result["confidence"] = min(100, sum(weight for field, weight in weights.items() if result[field]))
        return result

    def _extract_labeled_address(self) -> Dict[str, str]:
        result = {"name": "", "phone": "", "country": "", "province": "", "city": "", "street": "", "postal_code": ""}

        for field in ["name", "phone", "country", "province", "city", "postal_code"]:
            value = self._extract_labeled_scalar(self.ADDRESS_FIELD_PATTERNS[field], bank_mode=False, field=field)
            if value:
                result[field] = self._normalize_address_field(field, value)

        street = self._extract_labeled_scalar(self.ADDRESS_FIELD_PATTERNS["street"], bank_mode=False, field="street")
        if street:
            result["street"] = self._normalize_address_field("street", street)

        if result["phone"]:
            phone, _ = self._choose_phone([result["phone"]], country=result.get("country", ""))
            result["phone"] = phone or result["phone"]

        return result

    def _normalize_address_field(self, field: str, value: str) -> str:
        value = self._clean_value(value)
        if field == "country":
            return self._extract_country(value) or value
        if field == "postal_code":
            return self._extract_postal_code(value) or value.upper()
        if field == "phone":
            candidates = self._extract_phone_candidates(value)
            return candidates[0] if candidates else value
        if field in {"name", "province", "city"}:
            return value.strip(" ,")
        if field == "street":
            street = self._extract_street_from_text(value)
            return street or value.strip(" ,")
        return value

    def _extract_unstructured_address(self) -> Dict[str, str]:
        sentence_candidate = self._extract_sentence_address()
        block_candidate = self._extract_best_address_block()
        if self._address_score(sentence_candidate) >= self._address_score(block_candidate):
            return sentence_candidate
        return block_candidate

    def _extract_sentence_address(self) -> Dict[str, str]:
        result = {"name": "", "phone": "", "country": "", "province": "", "city": "", "street": "", "postal_code": ""}
        text = " ".join(self.lines)

        patterns = [
            r"(?i)\bship(?:\s+the\s+products?)?\s+to\s+([A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'’-]{1,40})[’']s\s+address\s+in\s+(?:the\s+)?([A-Z][A-Za-z ]{2,40})\s*[:：]\s*([^\n.]{8,180})",
            r"(?i)\bto\s+([A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'’-]{1,40})[’']s\s+address\s+in\s+(?:the\s+)?([A-Z][A-Za-z ]{2,40})\s*[:：]\s*([^\n.]{8,180})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            result["name"] = self._clean_value(match.group(1))
            result["country"] = self._extract_country(match.group(2)) or self._extract_country(match.group(3))
            address_part = self._clean_value(match.group(3))
            parsed = self._parse_address_text(address_part, fallback_country=result["country"])
            for key, value in parsed.items():
                if value:
                    result[key] = value
            return result

        return result

    def _extract_best_address_block(self) -> Dict[str, str]:
        best = {"name": "", "phone": "", "country": "", "province": "", "city": "", "street": "", "postal_code": ""}
        best_score = 0

        for idx, line in enumerate(self.lines):
            if not self._looks_like_street(line):
                continue
            window_start = max(0, idx - 2)
            window_end = min(len(self.lines), idx + 6)
            block_lines = self.lines[window_start:window_end]
            block_text = "\n".join(block_lines)
            if self._is_bank_context(block_text):
                continue

            candidate = self._parse_address_text(block_text)
            if not candidate.get("street"):
                candidate["street"] = self._extract_street_from_text(line)

            name = self._find_name_near_street(idx)
            if name:
                candidate["name"] = name

            phone_candidates = self._extract_phone_candidates(block_text)
            phone, _ = self._choose_phone(phone_candidates, country=candidate.get("country", ""), context=block_text)
            if phone:
                candidate["phone"] = phone

            score = self._address_score(candidate)
            if score > best_score:
                best = candidate
                best_score = score

        return best

    def _parse_address_text(self, text: str, fallback_country: str = "") -> Dict[str, str]:
        result = {"name": "", "phone": "", "country": "", "province": "", "city": "", "street": "", "postal_code": ""}
        result["country"] = self._extract_country(text) or fallback_country
        result["street"] = self._extract_street_from_text(text)
        result["postal_code"] = self._extract_postal_code(text, result["country"])

        city, province = self._extract_city_province(text, result["postal_code"], result["country"])
        result["city"] = city
        result["province"] = province

        phone_candidates = self._extract_phone_candidates(text)
        phone, _ = self._choose_phone(phone_candidates, country=result["country"], context=text)
        result["phone"] = phone
        return result

    def _address_score(self, candidate: Dict[str, str]) -> int:
        weights = {
            "name": 8,
            "phone": 12,
            "country": 15,
            "province": 8,
            "city": 15,
            "street": 22,
            "postal_code": 20,
        }
        return sum(weight for field, weight in weights.items() if candidate.get(field))

    def _find_name_near_street(self, street_idx: int) -> str:
        for idx in range(street_idx - 1, max(-1, street_idx - 4), -1):
            if idx < 0:
                break
            line = self.lines[idx]
            if self._line_has_any_label(line) or self._is_junk_line(line) or self._is_bank_context(line):
                continue
            if self._looks_like_person_name(line, allow_single=False):
                return self._clean_value(line)
        return ""

    def _looks_like_person_name(self, value: str, allow_single: bool = True) -> bool:
        value = self._clean_value(value)
        if not value or len(value) > 80:
            return False
        lower = value.lower()
        bad_words = {
            "account", "number", "address", "street", "city", "country", "postal", "code",
            "email", "paypal", "bank", "swift", "iban", "instagram", "tiktok", "reel",
            "story", "campaign", "product", "details", "form", "shipping",
        }
        if any(word in lower for word in bad_words):
            return False
        if re.search(r"[@\d:/]", value):
            return False
        parts = value.replace("'", "’").split()
        if len(parts) == 1 and not allow_single:
            return False
        if not (1 <= len(parts) <= 5):
            return False
        return all(re.match(r"^[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.'’\-]{1,30}$", part) for part in parts)

    def _is_bank_context(self, text: str) -> bool:
        lower = text.lower()
        return any(word in lower for word in self.BANK_CONTEXT_WORDS)

    def _extract_country(self, text: str) -> str:
        if not text:
            return ""
        normalized = re.sub(r"[()\[\]{},.;:]", " ", text.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()

        # 先匹配长名称，避免 US/CA 等缩写误伤普通单词。
        for alias, canonical in sorted(self.COUNTRY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
            if len(alias) <= 2:
                continue
            if re.search(rf"(?<![A-Za-z]){re.escape(alias)}(?![A-Za-z])", normalized):
                return canonical

        original = text
        for alias, canonical in self.COUNTRY_ALIASES.items():
            if len(alias) > 2:
                continue
            alias_upper = alias.upper()
            # 两位国家缩写容易和普通英文词冲突（at/no/it/us）。只接受大写独立词或括号内缩写。
            if re.search(rf"(?<![A-Za-z]){re.escape(alias_upper)}(?![A-Za-z])", original):
                return canonical
            if re.search(rf"\({re.escape(alias)}\)", original, re.IGNORECASE):
                return canonical
        return ""

    def _extract_postal_code(self, text: str, country: str = "") -> str:
        if not text:
            return ""
        compact_text = re.sub(r"\s+", " ", text).strip()
        patterns_by_country = []

        if country == "United Kingdom":
            patterns_by_country.append(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b")
        elif country == "Canada":
            patterns_by_country.append(r"\b([ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z]\s?\d[ABCEGHJ-NPRSTV-Z]\d)\b")
        elif country == "Netherlands":
            patterns_by_country.append(r"\b([1-9]\d{3}\s?[A-Z]{2})\b")
        elif country == "United States":
            patterns_by_country.append(r"\b(\d{5}(?:-\d{4})?)\b")

        generic_patterns = [
            r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b",  # UK
            r"\b([ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z]\s?\d[ABCEGHJ-NPRSTV-Z]\d)\b",  # Canada
            r"\b([1-9]\d{3}\s?[A-Z]{2})\b",  # Netherlands
            r"\b(\d{4}-\d{3})\b",  # Portugal
            r"\b(\d{2}-\d{3})\b",  # Poland
            r"\b([A-Z]\d{2}\s?[A-Z0-9]{4})\b",  # Ireland
            r"\b(\d{3}\s?\d{2})\b",  # Sweden-like
            r"\b(\d{5}(?:-\d{4})?)\b",  # US / many EU countries
            r"\b(\d{4})\b",  # AU / BE / CH / AT / NL numeric part fallback
        ]

        for pattern in patterns_by_country + generic_patterns:
            for match in re.finditer(pattern, compact_text, re.IGNORECASE):
                raw_postal = match.group(1).strip()
                postal = raw_postal.upper()
                if self._postal_looks_valid(raw_postal, compact_text, match.start(), match.end()):
                    return re.sub(r"\s+", " ", postal)
        return ""

    def _postal_looks_valid(self, postal: str, text: str, start: int, end: int) -> bool:
        digits = re.sub(r"\D", "", postal)
        letters = re.sub(r"[^A-Za-z]", "", postal)
        if len(digits) < 4 and not (letters and len(digits) >= 2):
            return False
        window = text[max(0, start - 35): min(len(text), end + 35)].lower()
        address_words = ["postal", "postcode", "zip", "address", "street", "city", "ship"]
        bad_context = ["tracking", "shipment", "account", "iban", "routing", "sort", "swift", "phone", "tel"]
        date_context = re.search(r"\b(?:mon|tue|wed|thu|fri|sat|sun|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|am|pm)\b", window)
        if any(word in window for word in bad_context) and not any(word in window for word in address_words):
            return False
        if date_context and not any(word in window for word in address_words):
            return False
        if postal in {"0000", "1111", "1234", "00000", "11111", "12345"}:
            return False
        return True

    def _extract_city_province(self, text: str, postal_code: str, country: str) -> Tuple[str, str]:
        if not text:
            return "", ""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        one_line = re.sub(r"\s+", " ", text).strip()
        escaped_postal = re.escape(postal_code) if postal_code else ""

        if country == "United States" or re.search(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b", one_line):
            for line in lines:
                match = re.search(r"^([A-Za-z][A-Za-z .'-]{1,50})\s+([A-Z]{2})\s+\d{5}(?:-\d{4})?$", line)
                if match and match.group(2).upper() in self.US_STATE_CODES:
                    city = self._clean_city(match.group(1))
                    if city and not self._looks_like_street(city):
                        return city, match.group(2).upper()
            match = re.search(r"\b([A-Za-z][A-Za-z .'-]{1,50})\s+([A-Z]{2})\s+\d{5}(?:-\d{4})?\b", one_line)
            if match and match.group(2).upper() in self.US_STATE_CODES:
                city = self._clean_city(match.group(1))
                street = self._extract_street_from_text(city)
                if street:
                    city = self._clean_city(city.replace(street, ""))
                return city, match.group(2).upper()

        if postal_code:
            match = re.search(rf"{escaped_postal}\s*,?\s*([A-Za-zÀ-ÖØ-öø-ÿ .'’-]{{2,50}})(?:\s*\(([A-Z]{{2}})\))?", one_line, re.IGNORECASE)
            if match:
                city = self._clean_city(match.group(1))
                if city and not self._extract_country(city):
                    return city, ""

            match = re.search(rf"([A-Za-zÀ-ÖØ-öø-ÿ .'’-]{{2,50}})\s*,?\s*{escaped_postal}", one_line, re.IGNORECASE)
            if match:
                city = self._clean_city(match.group(1))
                if city and not self._looks_like_street(city):
                    return city, ""

        for i, line in enumerate(lines):
            if postal_code and postal_code.lower() in line.lower():
                if i > 0 and not self._looks_like_street(lines[i - 1]) and not self._extract_country(lines[i - 1]):
                    city = self._clean_city(lines[i - 1])
                    if city:
                        return city, ""
                if i + 1 < len(lines) and not self._extract_country(lines[i + 1]):
                    city = self._clean_city(lines[i + 1])
                    if city:
                        return city, ""

        return "", ""

    def _clean_city(self, value: str) -> str:
        value = self._clean_value(value)
        value = re.sub(r"\b(?:city|town|postal|postcode|zip|state|province)\b", "", value, flags=re.IGNORECASE)
        value = value.strip(" ,")
        words = value.split()
        # 取最后 1-4 个词，去掉街道或姓名前缀带来的噪音。
        if len(words) > 4:
            value = " ".join(words[-4:])
        return value

    def _looks_like_street(self, text: str) -> bool:
        return bool(self._extract_street_from_text(text))

    def _extract_street_from_text(self, text: str) -> str:
        if not text:
            return ""
        if self._is_bank_context(text):
            return ""
        street_type_pattern = "|".join(re.escape(item) for item in sorted(self.STREET_TYPES, key=len, reverse=True))
        patterns = [
            rf"\b(\d{{1,6}}[A-Za-z]?\s+[A-Za-zÀ-ÖØ-öø-ÿ0-9.'’\- ]{{2,70}}?\s+(?:{street_type_pattern})\.?[ \t]*(?:[#A-Za-z0-9\-/ ]{{0,20}}))\b",
            r"\b([A-Za-zÀ-ÖØ-öø-ÿ.'’\- ]{3,70}?(?:straat|weg|laan|dijk|plein|pad|hof|kade|gracht|singel)\s+\d{1,6}[A-Za-z]?(?:[-/][A-Za-z0-9]+)?)\b",
            r"\b([A-Za-zÀ-ÖØ-öø-ÿ.'’\- ]{3,70}?\s+\d{1,6}[A-Za-z]?(?:[-/][A-Za-z0-9]+)?)\b",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                street = self._clean_value(match.group(1))
                if self._street_candidate_valid(street):
                    return street
        return ""

    def _street_candidate_valid(self, street: str) -> bool:
        if not street or len(street) < 5 or len(street) > 120:
            return False
        lower = street.lower()
        bad_words = ["instagram", "tiktok", "story", "campaign", "package", "tracking", "account", "number", "june", "date"]
        if any(word in lower for word in bad_words):
            return False
        return bool(re.search(r"\d", street)) and bool(re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", street))

    def _extract_phone_candidates(self, text: str) -> List[str]:
        if not text:
            return []
        candidates = []
        cleaned_text = re.sub(r"\[[^\]]*\]", lambda m: " " + m.group(0).strip("[]") + " ", text)

        if phonenumbers:
            for region in [None, "US", "GB", "NL", "CA", "AU", "DE", "FR", "ES", "IT"]:
                try:
                    for match in phonenumbers.PhoneNumberMatcher(cleaned_text, region):
                        raw = cleaned_text[match.start:match.end]
                        if self._phone_context_valid(cleaned_text, match.start, match.end):
                            candidates.append(self._clean_phone(raw))
                except Exception:
                    continue

        phone_pattern = re.compile(
            r"(?<![A-Za-z0-9])(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4}(?![A-Za-z0-9])"
        )
        for match in phone_pattern.finditer(cleaned_text):
            phone = self._clean_phone(match.group(0))
            digits = re.sub(r"\D", "", phone)
            if 7 <= len(digits) <= 15 and self._phone_context_valid(cleaned_text, match.start(), match.end()):
                candidates.append(phone)

        seen = set()
        unique = []
        for phone in candidates:
            digits = re.sub(r"\D", "", phone)
            if digits and digits not in seen:
                seen.add(digits)
                unique.append(phone)
        return unique

    def _phone_context_valid(self, text: str, start: int, end: int) -> bool:
        window = text[max(0, start - 45): min(len(text), end + 45)].lower()
        bad_words = [
            "tracking", "shipment", "parcel", "order", "account", "iban", "routing", "sort code",
            "swift", "postcode", "postal", "zip", "campaign", "rate", "price", "£", "$", "eur",
        ]
        good_words = ["phone", "mobile", "tel", "telephone", "whatsapp", "contact", "address"]
        if any(word in window for word in bad_words) and not any(word in window for word in good_words):
            return False
        return True

    def _clean_phone(self, phone: str) -> str:
        phone = phone.strip().strip("[](){}.,;: ")
        phone = re.sub(r"\s+", " ", phone)
        return phone

    def _choose_phone(self, candidates: List[str], country: str = "", context: str = "") -> Tuple[str, int]:
        if not candidates:
            return "", 0
        region = self.COUNTRY_TO_REGION.get(country)
        best_phone = ""
        best_score = -1

        for phone in candidates:
            digits = re.sub(r"\D", "", phone)
            if not (7 <= len(digits) <= 15):
                continue
            score = 20
            if "+" in phone:
                score += 10
            if 9 <= len(digits) <= 12:
                score += 10
            if context and re.search(re.escape(phone), context):
                score += 5

            if phonenumbers:
                regions = [region, None, "US", "GB", "NL", "CA", "AU", "DE", "FR", "ES", "IT"]
                for reg in regions:
                    try:
                        parsed = phonenumbers.parse(phone, reg)
                        if phonenumbers.is_valid_number(parsed):
                            score += 45 if reg == region else 35
                            break
                        if phonenumbers.is_possible_number(parsed):
                            score += 20
                            break
                    except Exception:
                        continue

            if score > best_score:
                best_score = score
                best_phone = phone

        if not best_phone:
            return "", 0
        return best_phone, min(100, max(0, best_score))

    # 兼容旧接口：保留这些方法，供外部调试或旧代码直接调用。
    def _extract_name_candidates(self) -> List[str]:
        candidates = []
        for line in self.lines:
            if self._looks_like_person_name(line, allow_single=False):
                candidates.append(line)
        return candidates

    def _extract_name(self) -> Tuple[str, int]:
        addr = self._extract_address()
        if addr.get("name"):
            return addr["name"], 95 if addr.get("name_source") == "label" else 70
        return "", 0

    def _extract_phone(self) -> Tuple[str, int]:
        addr = self._extract_address()
        if addr.get("phone"):
            return addr["phone"], addr.get("phone_confidence", 0)
        return "", 0

    def _extract_address_legacy(self) -> Dict[str, object]:
        return self._extract_address()

    def _get_address_context(self, text: str) -> str:
        lines = self._to_lines(text)
        context = []
        for idx, line in enumerate(lines):
            lower = line.lower()
            if any(keyword in lower for keyword in ["address", "street", "city", "country", "postal", "zip", "phone"]):
                context.extend(lines[max(0, idx - 1): min(len(lines), idx + 2)])
        return " ".join(context)
