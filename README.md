# 飞书邮箱信息提取工具

通过 IMAP 协议连接飞书邮箱（也支持 QQ / 163 / Gmail / Outlook / 阿里云等），按时间范围获取邮件，自动提取邮件中的联系信息（邮箱、电话、地址），并导出为 Excel。

## 功能特性

- **IMAP 邮箱直连**：无需管理员审批，使用邮箱账号 + 授权码即可连接
- **自动识别邮箱服务商**：根据邮箱后缀自动选择 IMAP 服务器
- **多种时间范围**：今天、最近 3 天、最近一周、最近一月、自定义起止日期
- **自动提取联系信息**：邮箱地址、电话号码（中/美/英/德/日/韩等）、联系地址
- **Excel 导出**：单文件输出，包含发件邮箱、标题、正文链接、收件时间等列
- **正文本地归档**：每封邮件的正文另存为 `.txt`，Excel 中"邮件链接"列可一键跳转
- **配置记忆**：邮箱、服务器、输出目录等自动保存到 `config.json`
- **macOS 原生体验**：自绘圆角按钮 + 居中式双栏布局

## 文件结构

```
.
├── email_extractor_gui.py   # 主程序（图形界面与业务逻辑）
├── imap_client.py           # IMAP 邮箱客户端（连接、搜索、解析）
├── contact_extractor.py     # 全球联系信息提取器（邮箱/电话/地址）
├── excel_exporter.py        # Excel 导出模块
├── feishu_email.py          # 飞书开放平台 API 客户端（备用模块，当前 GUI 未启用）
├── gui.py                   # 图形界面启动入口（等价于 email_extractor_gui.main）
├── requirements.txt         # Python 运行时依赖
├── github-windows-build.command # Windows 打包脚本（触发 GitHub Actions 并下载产物）
├── .github/workflows/windows-build.yml # GitHub Actions Windows 打包配置
├── mac-build.command        # 跨平台打包入口（双击进菜单，或命令行 `mac|win|all`）
├── 启动工具.command          # macOS 一键启动脚本（双击运行）
└── config.json              # 配置文件（首次运行后自动生成）
```

## 快速开始（macOS）

### 方式一：一键启动（推荐）

1. 双击 `启动工具.command`
2. 脚本会自动：检查 Python → 创建 `.venv` 虚拟环境 → 安装 `openpyxl`、`requests`
3. 等待启动完成后即可使用

### 方式二：手动运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python email_extractor_gui.py
```

## 使用步骤

1. 在左侧 **IMAP 邮箱配置** 中填入：
   - 邮箱地址
   - 授权密码（QQ / 163 / Gmail 等需要使用授权码，不是登录密码）
   - 服务器与端口（默认 `imap.feishu.cn:993`，可手动修改）
2. 可选：点击 **测试连接** 验证配置是否正确
3. 选择 **邮件时间范围**（今天 / 最近 3 天 / 最近一周 / 最近一月 / 自定义）
4. 设置 **输出目录**（默认 `~/Desktop/飞书邮件导出`）
5. 点击 **获取邮件**，右侧日志区会显示处理进度
6. 拉取完成后点击 **导出表格**，导出结束后会询问是否打开输出目录
7. 任何时候可点击 **清空数据** 重新开始

## IMAP 支持的邮箱类型

| 邮箱类型 | 服务器 | 说明 |
|---------|--------|------|
| 飞书邮箱 | `imap.feishu.cn` | 自动检测（`@feishu.cn` / `@larkoffice.com` 等） |
| QQ 邮箱 | `imap.qq.com` | 需要授权码 |
| 163 邮箱 | `imap.163.com` | 需要授权码 |
| Gmail | `imap.gmail.com` | 需要应用专用密码 |
| Outlook / Hotmail | `outlook.office365.com` | 自动检测 |
| 阿里云邮箱 | `imap.aliyun.com` | 自动检测 |
| 其他邮箱 | 自定义 | 在"服务器"输入框中手动填写 |

> 单次最多拉取 500 封邮件（取最新 500 封）。

## Excel 输出格式

导出目录结构：

```
飞书邮件导出/
└── 2026-06-22 10-12-30/                       # 时间戳文件夹（避免覆盖）
    ├── 2026-06-22 10-12-30.xlsx               # 主 Excel
    └── 邮件内容 2026-06-22 10-12-30/          # 正文目录
        ├── 邮件_1.txt
        ├── 邮件_2.txt
        └── ...
```

Excel 列定义：

| 列 | 名称 | 说明 |
|----|------|------|
| 1 | 序号 | 自增编号 |
| 2 | 发件邮箱 | 解析出的发件人邮箱 |
| 3 | 邮件标题 | 邮件 Subject |
| 4 | 邮件链接 | `=HYPERLINK(...)`，点击打开本地 `邮件_N.txt` |
| 5 | 联系信息 | 当前版本暂未填充，预留列 |
| 6 | 收件时间 | 形如 `2026-06-22 10:12:30` |

正文 `.txt` 文件内容包含发件人、主题、时间和完整正文。

## 全球格式支持

### 电话号码
- 中国：`+86 138xxxxxxxx`、`0086-xxx-xxxx-xxxx`
- 美国：`+1 (xxx) xxx-xxxx`
- 英国：`+44 xxxx xxxxxx`
- 德国：`+49 xxx-xxxxxxx`
- 日本：`+81 xxx-xxxx-xxxx`
- 韩国：`+82 xxx-xxxx-xxxx`
- 通用国际格式：`+xx xxx xxx xxxx`

### 邮箱
支持所有标准邮箱格式，自动过滤 `example.com`、`@feishu.cn`、`@larkoffice.com` 等无效/自身域。

### 地址
- 中文地址（含省/市/区/县/街/路/号等行政区划关键词）
- 英文地址（Street / Avenue / Road / Suite 等）
- 带邮编的地址

## 配置文件

运行后会在脚本所在目录生成 `config.json`，保存以下字段：

| 字段 | 说明 |
|------|------|
| `email_addr` | 邮箱地址 |
| `email_password` | 授权密码 |
| `custom_server` | 自定义 IMAP 服务器 |
| `custom_port` | IMAP 端口（默认 `993`） |
| `output_dir` | Excel 输出目录 |

> 配置文件以明文保存密码，请勿在公共电脑上勾选保存密码，或定期清理 `config.json`。

## 跨平台打包（推荐入口）

> 在 Mac 上同时打出 macOS `.app` 和 Windows `.exe` 只需双击一个 `.command` 文件。

### 一键打包（双击 mac-build.command）

```
双击 mac-build.command
   ├─ 1) macOS   →  本机直接打 release/飞书邮箱提取工具.app
   ├─ 2) Windows →  GitHub Actions 云端打 release_windows_github/邮件小助手.exe
   └─ 3) 两个平台都打
```

脚本会逐步引导。第一次执行时会自动完成：
- 找带 `tkinter` 的 Python（Homebrew 优先）
- 创建 `venv` 虚拟环境并安装依赖
- 触发 GitHub Actions Windows runner 打包并下载产物

> **前置条件**
> - Mac 端：`brew install python-tk@3.x`（x 与 `python3` 主版本一致）
> - Windows 打包：本机已安装并登录 GitHub CLI（`gh auth login`），并已将代码 push 到 GitHub 默认分支

### 单独打包（命令行）

```bash
# macOS 应用（macOS 打包逻辑已并入 mac-build.command，参数 mac / m 即可）
./mac-build.command mac
# 产物: release/飞书邮箱提取工具.app

# Windows 单文件 .exe
./github-windows-build.command
# 产物: release_windows_github/邮件小助手.exe
```

## 打包为 .app（macOS 详细）

```bash
./mac-build.command mac
# 等价于：./mac-build.command m
# 双击运行则进入交互菜单
```

脚本会自动：
1. 找到带 `tkinter` 的 Python（Homebrew 优先）
2. 创建 `venv` 虚拟环境并安装依赖
3. 安装 `pyinstaller`
4. 用 PyInstaller 打包为 `release/飞书邮箱提取工具.app`（arm64）
5. 复制 TCL/TK 库到 `Contents/Resources`（解决 Homebrew Python 打包后 tkinter 报错）
6. 写入 `Info.plist` 的 `LSArchitecturePriority=arm64`，避免在 Apple Silicon 上走 x86_64 兼容层

> 打包前请确保已执行 `brew install python-tk@3.x`（与 `python3` 版本一致）。

## 打包为 .exe（Windows 详细）

```bash
./github-windows-build.command
```

脚本会自动：
1. 检查当前目录是否为 Git 仓库
2. 检查 GitHub CLI（`gh`）是否已安装并登录
3. 确认当前分支已推送到 GitHub
4. 触发 `.github/workflows/windows-build.yml`
5. 等待云端 Windows runner 用 PyInstaller 打包
6. 下载 `windows-exe` artifact 到 `release_windows_github/邮件小助手.exe`

> GitHub Actions 只会使用已经 push 到 GitHub 的代码。打包前请确认相关改动已经 commit 并 push。
> 产出的 `.exe` 是单文件版本，复制到任何 Windows 电脑双击即可运行（首次启动约 5-10 秒解压）。

## 常见问题

### Q: IMAP 连接失败？
1. 确认邮箱地址和授权码正确
2. 确认邮箱已在网页/客户端设置中开启 IMAP 服务
3. QQ / 163 等邮箱必须使用 **授权码**，不是登录密码
4. Gmail 需要开启两步验证后生成的 **应用专用密码**
5. 检查网络与防火墙（IMAP 使用 993 端口）

### Q: 如何获取邮箱授权码？
- **QQ 邮箱**：设置 → 账户 → POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务 → 开启 IMAP/SMTP → 生成授权码
- **163 邮箱**：设置 → POP3/SMTP/IMAP → 开启 IMAP/SMTP → 生成授权码
- **飞书邮箱**：联系企业管理员开启 IMAP 权限
- **Gmail**：Google 账户 → 安全性 → 两步验证 → 应用专用密码

### Q: 飞书开放平台 API 在哪里？
代码中已包含 `feishu_email.py` 模块（基于 `https://open.feishu.cn/open-apis`），但当前图形界面只启用了 IMAP 方式。如需使用 API 方式，可联系管理员在 [飞书开放平台](https://open.feishu.cn/) 创建应用并开通 `mail:message:readonly` / `mail:message:read` 权限。

### Q: 打包后的 .app 双击闪退？
通常是 Homebrew Python 的 TCL/TK 路径问题。`mac-build.command` 已自动复制 `/opt/homebrew/lib/tcl8.6` 与 `tk8.6` 到 app 的 `Resources/`，如仍闪退可在终端中执行 `release/飞书邮箱提取工具.app/Contents/MacOS/飞书邮箱提取工具` 查看详细错误。

### Q: Windows 端是单文件 .exe 还是文件夹？
采用 `--onefile` 单文件形式，便于复制分发。首次启动会花 5-10 秒在临时目录解压，之后启动正常。如希望启动更快，可将 `.github/workflows/windows-build.yml` 里的 `--onefile` 改为 `--onedir` 改为文件夹形式。

### Q: 能否在 Windows 机器上直接打 Windows 包？
可以。在 Windows 上直接在 PowerShell 中执行：
```powershell
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pyinstaller --onefile --windowed --name=邮件小助手 --hidden-import=tkinter email_extractor_gui.py
```
产物在 `dist\邮件小助手.exe`。
