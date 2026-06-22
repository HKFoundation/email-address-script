"""
飞书邮箱信息提取工具 - 主程序
图形界面版本（IMAP 邮箱直连方式）
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import threading

from contact_extractor import GlobalContactExtractor
from excel_exporter import ExcelExporter
from imap_client import IMAPEmailClient


class ConfigManager:
    """配置管理器"""

    CONFIG_FILE = "config.json"

    DEFAULT_CONFIG = {
        "email_addr": "",
        "email_password": "",
        "custom_server": "",
        "custom_port": "993",
        "output_dir": ""
    }

    @classmethod
    def load(cls) -> Dict:
        """加载配置"""
        try:
            if os.path.exists(cls.CONFIG_FILE):
                with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return {**cls.DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
        return cls.DEFAULT_CONFIG.copy()

    @classmethod
    def save(cls, config: Dict, parent=None):
        """保存配置"""
        try:
            with open(cls.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}", parent=parent)


class FeishuEmailExtractorGUI:
    """飞书邮箱提取工具主界面"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("飞书邮箱信息提取工具")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        # 加载配置
        self.config = ConfigManager.load()

        # 初始化组件
        self.imap_client: Optional[IMAPEmailClient] = None
        self.extractor = GlobalContactExtractor()
        self.exporter: Optional[ExcelExporter] = None
        self.all_emails: List[Dict] = []

        # 创建界面
        self._create_widgets()

        # 初始化输出目录
        if not self.config.get("output_dir"):
            default_dir = os.path.join(os.path.expanduser("~"), "Desktop", "飞书邮件导出")
            self.config["output_dir"] = default_dir
            self.output_dir_var.set(default_dir)

    def _create_widgets(self):
        """创建界面组件"""
        ui_font = ('微软雅黑', 9)
        style = ttk.Style()
        style.configure("App.TLabel", font=ui_font)
        style.configure("App.TEntry", font=ui_font)
        style.configure("App.TRadiobutton", font=ui_font)
        style.configure("App.TLabelframe.Label", font=('微软雅黑', 9, 'bold'))

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ========== 左右分栏布局 ==========
        # 左侧功能区 (290px)
        left_frame = ttk.Frame(main_frame, width=290)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_frame.pack_propagate(False)

        # 右侧日志区 (290px)
        right_frame = ttk.Frame(main_frame, width=290)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_frame.pack_propagate(False)

        # ========== 左侧: IMAP 配置框架 ==========
        config_frame = ttk.LabelFrame(left_frame, text="IMAP 邮箱配置", padding=16, style="App.TLabelframe")
        config_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # 邮箱、密码和测试连接按钮
        account_frame = ttk.Frame(config_frame)
        account_frame.pack(fill=tk.X, pady=4)
        account_frame.columnconfigure(1, weight=1)

        ttk.Label(account_frame, text="邮箱地址:", style="App.TLabel").grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        self.email_addr_var = tk.StringVar(value=self.config.get("email_addr", ""))
        ttk.Entry(account_frame, textvariable=self.email_addr_var, width=14, font=ui_font, style="App.TEntry").grid(
            row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=(0, 8)
        )

        ttk.Label(account_frame, text="授权密码:", style="App.TLabel").grid(row=1, column=0, sticky=tk.W)
        self.email_password_var = tk.StringVar(value=self.config.get("email_password", ""))
        ttk.Entry(account_frame, textvariable=self.email_password_var, width=14, show="*", font=ui_font, style="App.TEntry").grid(
            row=1, column=1, sticky=tk.EW, padx=(8, 0)
        )

        test_btn_size = 52
        test_btn_box = ttk.Frame(account_frame, width=test_btn_size, height=test_btn_size)
        test_btn_box.grid(row=0, column=2, rowspan=2, sticky=tk.E, padx=(8, 0))
        test_btn_box.pack_propagate(False)
        test_btn_box.grid_propagate(False)

        self.test_connection_btn = self._create_canvas_button(
            test_btn_box, "测试\n连接", self._test_imap_connection, test_btn_size, test_btn_size, ui_font
        )
        self.test_connection_btn.place(x=0, y=0, width=test_btn_size, height=test_btn_size)
        account_frame.rowconfigure(0, minsize=30)
        account_frame.rowconfigure(1, minsize=30)

        # 密码说明
        password_help = ttk.Label(config_frame,
            text="提示: 如果是 QQ/163 等邮箱，请使用授权码", font=('微软雅黑', 8), foreground='gray')
        password_help.pack(anchor=tk.W, pady=(2, 4))

        # 服务器/端口
        server_row = ttk.Frame(config_frame)
        server_row.pack(fill=tk.X, pady=4)
        server_row.columnconfigure(1, weight=1)

        ttk.Label(server_row, text="服务器:", style="App.TLabel").grid(row=0, column=0, sticky=tk.W)
        self.custom_server_var = tk.StringVar(value=self.config.get("custom_server", "imap.feishu.cn"))
        self.custom_server_entry = ttk.Entry(server_row, textvariable=self.custom_server_var, width=9, font=ui_font, style="App.TEntry")
        self.custom_server_entry.grid(row=0, column=1, sticky=tk.EW, padx=(8, 0))

        ttk.Label(server_row, text="端口:", style="App.TLabel").grid(row=0, column=2, sticky=tk.W, padx=(8, 0))
        self.custom_port_var = tk.StringVar(value=self.config.get("custom_port", "993"))
        ttk.Entry(server_row, textvariable=self.custom_port_var, width=5, font=ui_font, style="App.TEntry").grid(
            row=0, column=3, sticky=tk.EW, padx=(8, 0)
        )

        # ========== 左侧: 时间范围选择 ==========
        range_frame = ttk.LabelFrame(left_frame, text="邮件时间范围", padding=16, style="App.TLabelframe")
        range_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.time_range_var = tk.StringVar(value="recent_3_days")

        range_option_row1 = ttk.Frame(range_frame)
        range_option_row1.pack(anchor=tk.W)
        range_option_row2 = ttk.Frame(range_frame)
        range_option_row2.pack(anchor=tk.W, pady=(4, 0))

        ttk.Radiobutton(range_option_row1, text="今天", variable=self.time_range_var, style="App.TRadiobutton",
                       value="today", command=self._update_date_range).pack(side=tk.LEFT, padx=(0, 14))

        ttk.Radiobutton(range_option_row1, text="最近3天", variable=self.time_range_var, style="App.TRadiobutton",
                       value="recent_3_days", command=self._update_date_range).pack(side=tk.LEFT, padx=(0, 14))

        ttk.Radiobutton(range_option_row1, text="最近一周", variable=self.time_range_var, style="App.TRadiobutton",
                       value="recent_week", command=self._update_date_range).pack(side=tk.LEFT)

        ttk.Radiobutton(range_option_row2, text="最近一月", variable=self.time_range_var, style="App.TRadiobutton",
                       value="recent_month", command=self._update_date_range).pack(side=tk.LEFT, padx=(0, 14))

        ttk.Radiobutton(range_option_row2, text="自定义范围", variable=self.time_range_var, style="App.TRadiobutton",
                       value="custom", command=self._update_date_range).pack(side=tk.LEFT)

        # 自定义日期选择
        custom_frame = ttk.Frame(range_frame)
        custom_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(custom_frame, text="从:", style="App.TLabel").pack(side=tk.LEFT)
        self.start_date_var = tk.StringVar()
        self.start_date_entry = ttk.Entry(custom_frame, textvariable=self.start_date_var, width=10, font=ui_font, style="App.TEntry")
        self.start_date_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(custom_frame, text="到:", style="App.TLabel").pack(side=tk.LEFT, padx=(15, 5))
        self.end_date_var = tk.StringVar()
        self.end_date_entry = ttk.Entry(custom_frame, textvariable=self.end_date_var, width=10, font=ui_font, style="App.TEntry")
        self.end_date_entry.pack(side=tk.LEFT)

        # 初始化日期范围
        self._update_date_range()

        # ========== 左侧: 输出目录 ==========
        output_frame = ttk.LabelFrame(left_frame, text="输出设置", padding=16, style="App.TLabelframe")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        output_content = ttk.Frame(output_frame)
        output_content.pack(fill=tk.X)
        output_content.columnconfigure(1, weight=1)

        ttk.Label(output_content, text="目录:", style="App.TLabel").grid(row=0, column=0, sticky=tk.W)
        self.output_dir_var = tk.StringVar(value=self.config.get("output_dir", ""))
        ttk.Entry(output_content, textvariable=self.output_dir_var, width=12, font=ui_font, style="App.TEntry").grid(
            row=0, column=1, sticky=tk.EW, padx=(8, 8)
        )

        self.browse_btn = self._create_canvas_button(output_content, "浏览", self._browse_output_dir, 58, 34, ui_font)
        self.browse_btn.grid(row=0, column=2, sticky=tk.E)

        # ========== 左侧: 操作按钮 ==========
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        action_btn_frame = ttk.Frame(btn_frame)
        action_btn_frame.pack(anchor=tk.CENTER)

        self.fetch_btn = self._create_canvas_button(action_btn_frame, "获取邮件", self._fetch_emails, 76, 34, ui_font)
        self.fetch_btn.pack(side=tk.LEFT, padx=4)

        self.export_btn = self._create_canvas_button(action_btn_frame, "导出表格", self._export_to_excel, 76, 34, ui_font, enabled=False)
        self.export_btn.pack(side=tk.LEFT, padx=4)

        self.clear_btn = self._create_canvas_button(action_btn_frame, "清空数据", self._clear_data, 76, 34, ui_font)
        self.clear_btn.pack(side=tk.LEFT, padx=4)

        # ========== 右侧: 日志区域 ==========
        log_frame = ttk.LabelFrame(right_frame, text="日志", padding="10", style="App.TLabelframe")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, font=ui_font,
                                state=tk.DISABLED, bg='#F5F5F5', spacing3=4)
        self.log_text.tag_configure("log_line", lmargin2=18)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _create_rounded_rect(self, canvas, x1, y1, x2, y2, radius, **kwargs):
        """在 Canvas 上绘制圆角矩形。"""
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, splinesteps=16, **kwargs)

    def _create_canvas_button(self, parent, text, command, width, height, font, enabled=True):
        """创建统一样式的圆角阴影按钮。"""
        button = tk.Canvas(
            parent,
            width=width,
            height=height,
            bd=0,
            highlightthickness=0,
            background=self.root.cget("bg"),
            cursor="hand2",
        )
        radius = min(9, max(6, height // 4))
        shadow_id = self._create_rounded_rect(
            button, 4, 4, width - 1, height - 1, radius, fill="#D7D7D7", outline=""
        )
        face_id = self._create_rounded_rect(
            button, 1, 1, width - 4, height - 4, radius,
            fill="#F8F8F8", outline="#AFAFAF", width=1
        )
        text_id = button.create_text(
            (width - 3) / 2,
            (height - 3) / 2,
            text=text,
            justify=tk.CENTER,
            fill="#222222",
            font=font,
        )
        button._enabled = enabled

        def set_visual(is_enabled, pressed=False):
            if not is_enabled:
                button.itemconfig(shadow_id, fill="#E1E1E1")
                button.itemconfig(face_id, fill="#EFEFEF", outline="#C8C8C8")
                button.itemconfig(text_id, fill="#909090")
                button.configure(cursor="arrow")
                return

            button.itemconfig(shadow_id, fill="#D7D7D7")
            button.itemconfig(face_id, fill="#EDEDED" if pressed else "#F8F8F8", outline="#AFAFAF")
            button.itemconfig(text_id, fill="#222222")
            button.configure(cursor="hand2")

        def set_enabled(is_enabled):
            button._enabled = is_enabled
            set_visual(is_enabled)

        def press(_event):
            if button._enabled:
                set_visual(True, pressed=True)

        def leave(_event):
            set_visual(button._enabled)

        def release(event):
            set_visual(button._enabled)
            if button._enabled and 0 <= event.x <= width and 0 <= event.y <= height:
                command()

        button.set_enabled = set_enabled
        button.bind("<ButtonPress-1>", press)
        button.bind("<Leave>", leave)
        button.bind("<ButtonRelease-1>", release)
        set_visual(enabled)
        return button

    def _set_canvas_button_enabled(self, button, enabled: bool):
        """切换自绘按钮可用状态。"""
        button.set_enabled(enabled)

    def _update_date_range(self):
        """更新日期范围显示"""
        today = datetime.now().strftime("%Y-%m-%d")

        if self.time_range_var.get() == "today":
            self.start_date_var.set(today)
            self.end_date_var.set(today)
        elif self.time_range_var.get() == "recent_3_days":
            start = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
            self.start_date_var.set(start)
            self.end_date_var.set(today)
        elif self.time_range_var.get() == "recent_week":
            start = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
            self.start_date_var.set(start)
            self.end_date_var.set(today)
        elif self.time_range_var.get() == "recent_month":
            start = (datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d")
            self.start_date_var.set(start)
            self.end_date_var.set(today)

    def _browse_output_dir(self):
        """浏览选择输出目录"""
        directory = filedialog.askdirectory(title="选择输出目录", parent=self.root)
        if directory:
            self.output_dir_var.set(directory)

    def _log(self, message: str):
        """添加日志"""
        if set(message.strip()) == {"="}:
            return

        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        start_index = self.log_text.index(tk.END)
        self.log_text.insert(tk.END, f"[{timestamp}]  {message}\n")
        self.log_text.tag_add("log_line", start_index, self.log_text.index(tk.END))
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def _get_date_range(self) -> Tuple[datetime, datetime]:
        """获取选择的日期范围"""
        start_str = self.start_date_var.get()
        end_str = self.end_date_var.get()

        try:
            start = datetime.strptime(start_str, "%Y-%m-%d")
            end = datetime.strptime(end_str, "%Y-%m-%d")
            end = end.replace(hour=23, minute=59, second=59)
        except ValueError:
            raise ValueError("日期格式错误，请使用 YYYY-MM-DD 格式")

        if start > end:
            raise ValueError("开始日期不能晚于结束日期")

        return start, end

    def _set_buttons_state(self, fetching: bool):
        """设置按钮状态"""
        if fetching:
            self._set_canvas_button_enabled(self.fetch_btn, False)
            self._set_canvas_button_enabled(self.export_btn, False)
        else:
            self._set_canvas_button_enabled(self.fetch_btn, True)
            self._set_canvas_button_enabled(self.export_btn, bool(self.all_emails))

    def _save_config(self):
        """保存配置"""
        self.config["email_addr"] = self.email_addr_var.get()
        self.config["email_password"] = self.email_password_var.get()
        self.config["custom_server"] = self.custom_server_var.get()
        self.config["custom_port"] = self.custom_port_var.get()
        self.config["output_dir"] = self.output_dir_var.get()
        ConfigManager.save(self.config, parent=self.root)

    def _test_imap_connection(self):
        """测试 IMAP 连接"""
        email_addr = self.email_addr_var.get().strip()
        password = self.email_password_var.get().strip()

        if not email_addr or not password:
            messagebox.showerror("错误", "请填写邮箱地址和密码", parent=self.root)
            return

        self._log("正在测试 IMAP 连接...")

        thread = threading.Thread(target=self._test_imap_thread, args=(email_addr, password))
        thread.daemon = True
        thread.start()

    def _test_imap_thread(self, email_addr: str, password: str):
        """测试 IMAP 连接的线程"""
        try:
            # 创建 IMAP 客户端
            custom_server = self.custom_server_var.get().strip()
            custom_port = self.custom_port_var.get().strip()

            if custom_server:
                port = int(custom_port) if custom_port else 993
                self.imap_client = IMAPEmailClient(email_addr, password, custom_server, port)
            else:
                self.imap_client = IMAPEmailClient.detect_provider(email_addr, password)

            # 测试连接
            success, message = self.imap_client.test_connection()

            self.root.after(0, lambda: self._test_imap_result(success, message))

        except Exception as e:
            self.root.after(0, lambda: self._test_imap_result(False, str(e)))

    def _test_imap_result(self, success: bool, message: str):
        """IMAP 测试结果"""
        if success:
            self._log(f"✓ {message}")
        else:
            self._log(f"✗ {message}")
            messagebox.showerror("连接测试", f"连接失败:\n{message}", parent=self.root)

    def _fetch_emails(self):
        """获取邮件"""
        # 验证输入
        email_addr = self.email_addr_var.get().strip()
        password = self.email_password_var.get().strip()
        if not email_addr or not password:
            messagebox.showerror("错误", "请填写邮箱地址和密码", parent=self.root)
            return

        try:
            start, end = self._get_date_range()
        except ValueError as e:
            messagebox.showerror("错误", str(e), parent=self.root)
            return

        # 保存配置
        self._save_config()

        # 禁用按钮
        self._set_buttons_state(True)
        self._log("开始获取邮件...")
        self._log(f"{start.strftime('%Y-%m-%d')} 至 {end.strftime('%Y-%m-%d')}")

        # 后台线程执行
        thread = threading.Thread(target=self._fetch_emails_thread, args=(start, end))
        thread.daemon = True
        thread.start()

    def _fetch_emails_thread(self, start: datetime, end: datetime):
        """获取邮件的后台线程"""
        try:
            email_addr = self.email_addr_var.get().strip()
            password = self.email_password_var.get().strip()
            custom_server = self.custom_server_var.get().strip()
            custom_port = self.custom_port_var.get().strip()

            if custom_server:
                port = int(custom_port) if custom_port else 993
                self.imap_client = IMAPEmailClient(email_addr, password, custom_server, port)
            else:
                self.imap_client = IMAPEmailClient.detect_provider(email_addr, password)

            # 连接服务器
            self.imap_client.connect()
            self._log(f"IMAP 连接: {self.imap_client.server}")

            emails = self.imap_client.get_emails(start, end, limit=500)
            self._log(f"获取到 {len(emails)} 封邮件")

            # 提取联系信息
            for i, email in enumerate(emails):
                if i % 10 == 0:
                    self._log(f"处理进度: {i}/{len(emails)}")

                # 使用 HTML 正文提取联系信息
                body = email.get('body_html') or email.get('body_text') or ''
                contact_info = self.extractor.extract_all(body)
                email['contact_info'] = contact_info.to_display_string()

            self.root.after(0, lambda: self._fetch_complete(emails))

        except Exception as e:
            error_msg = str(e)
            self._log(f"错误: {error_msg}")
            self.root.after(0, lambda err=error_msg: self._fetch_error(err))

    def _fetch_complete(self, emails: List[Dict]):
        """获取完成回调"""
        self.all_emails = emails
        self._set_buttons_state(False)
        self._log(f"获取完成，共 {len(emails)} 封邮件")

    def _fetch_error(self, error: str):
        """获取错误回调"""
        self._set_buttons_state(False)
        messagebox.showerror("错误", f"获取邮件失败:\n{error}", parent=self.root)

    def _export_to_excel(self):
        """导出到 Excel"""
        if not self.all_emails:
            messagebox.showwarning("警告", "没有可导出的邮件数据", parent=self.root)
            return

        output_dir = self.output_dir_var.get()
        if not output_dir:
            messagebox.showerror("错误", "请选择输出目录", parent=self.root)
            return

        # 保存配置
        self._save_config()

        self.exporter = ExcelExporter(output_dir)
        self._log("开始导出 Excel...")

        try:
            files = self.exporter.export_all(self.all_emails)

            self._log(f"导出完成！共 {len(self.all_emails)} 封邮件")
            for name, filepath in files.items():
                self._log(f"{name}: {filepath}")

            self._log("导出完成")

            if messagebox.askyesno("导出完成", "邮件数据已导出到 Excel。\n是否打开输出目录？", parent=self.root):
                os.system(f'open "{output_dir}"')

        except Exception as e:
            messagebox.showerror("错误", f"导出失败:\n{e}", parent=self.root)
            self._log("导出失败: {e}")

    def _clear_data(self):
        """清空数据"""
        if self.all_emails:
            if messagebox.askyesno("确认", "确定要清空当前数据吗？", parent=self.root):
                self.all_emails = []
                self._set_canvas_button_enabled(self.export_btn, False)
                self._log("数据已清空")


def main():
    """主函数"""
    root = tk.Tk()
    app = FeishuEmailExtractorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
