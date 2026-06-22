"""
飞书邮箱 API 集成模块
支持获取邮件列表和邮件详情
"""

import requests
import time
import re
from datetime import datetime
from typing import List, Dict, Optional


class FeishuEmailAPI:
    """飞书邮箱 API 客户端"""

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = None
        self.token_expires_at = 0

    def _get_access_token(self) -> str:
        """获取访问令牌"""
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        if data.get("code") != 0:
            raise Exception(f"获取访问令牌失败: {data.get('msg')}")

        self.access_token = data.get("tenant_access_token")
        self.token_expires_at = time.time() + data.get("expire", 7200) - 300
        return self.access_token

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """发送 API 请求"""
        url = f"{self.BASE_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._get_access_token()}"

        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_emails(self, receive_start_time: str = None, receive_end_time: str = None,
                   page_size: int = 50, page_token: str = None) -> Dict:
        """
        获取邮件列表

        Args:
            receive_start_time: 收件开始时间 (ISO格式)
            receive_end_time: 收件结束时间 (ISO格式)
            page_size: 每页数量
            page_token: 分页令牌

        Returns:
            邮件列表数据
        """
        params = {"page_size": page_size}
        if receive_start_time:
            params["receive_start_time"] = receive_start_time
        if receive_end_time:
            params["receive_end_time"] = receive_end_time
        if page_token:
            params["page_token"] = page_token

        return self._request("GET", "/mail/v1/messages", params=params)

    def get_email_detail(self, message_id: str) -> Dict:
        """
        获取邮件详情

        Args:
            message_id: 邮件ID

        Returns:
            邮件详情
        """
        return self._request("GET", f"/mail/v1/messages/{message_id}")

    def get_all_emails_in_range(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        获取时间范围内的所有邮件

        Args:
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            邮件列表
        """
        all_emails = []
        page_token = None

        start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S+08:00")

        while True:
            result = self.get_emails(
                receive_start_time=start_iso,
                receive_end_time=end_iso,
                page_token=page_token
            )

            messages = result.get("data", {}).get("messages", [])
            all_emails.extend(messages)

            page_token = result.get("data", {}).get("page_token")
            has_more = result.get("data", {}).get("has_more", False)

            if not has_more or not page_token:
                break

        return all_emails

    @staticmethod
    def extract_email_body(email_data: Dict) -> str:
        """
        从邮件数据中提取正文内容

        Args:
            email_data: 邮件数据

        Returns:
            邮件正文文本
        """
        body = email_data.get("body", {})

        # 尝试不同格式的邮件正文
        if "html" in body:
            return body["html"]
        elif "text" in body:
            return body["text"]
        elif "request_id" in email_data:
            # 可能需要从其他地方获取正文
            return ""

        return ""

    @staticmethod
    def get_email_link(message_id: str) -> str:
        """
        生成邮件链接

        Args:
            message_id: 邮件ID

        Returns:
            可点击的邮件链接
        """
        return f"https://applink.feishu.cn/client/message/{message_id}"
