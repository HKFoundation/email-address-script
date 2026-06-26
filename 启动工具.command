#!/bin/bash

# =====================================================
# 飞书邮箱信息提取工具 - 启动脚本
# =====================================================

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"
cd "$SCRIPT_DIR"

# 虚拟环境目录
VENV_DIR="$SCRIPT_DIR/.venv"
MIN_TK_VERSION="8.6"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

version_ge() {
    # usage: version_ge 9.0 8.6
    awk -v current="$1" -v minimum="$2" '
        BEGIN {
            split(current, a, ".")
            split(minimum, b, ".")
            for (i = 1; i <= 4; i++) {
                ai = (a[i] == "" ? 0 : a[i]) + 0
                bi = (b[i] == "" ? 0 : b[i]) + 0
                if (ai > bi) exit 0
                if (ai < bi) exit 1
            }
            exit 0
        }
    '
}

python_candidates() {
    for candidate in \
        /opt/homebrew/bin/python3.13 \
        /opt/homebrew/bin/python3.12 \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3.13 \
        /usr/local/bin/python3.12 \
        /usr/local/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
        if [ -x "$candidate" ]; then
            echo "$candidate"
        fi
    done
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
    fi
    if [ -x /usr/bin/python3 ]; then
        echo /usr/bin/python3
    fi
}

python_tk_version() {
    "$1" - <<'PY' 2>/dev/null
import tkinter as tk
print(tk.TkVersion)
PY
}

python_version() {
    "$1" - <<'PY' 2>/dev/null
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
}

find_python_with_modern_tk() {
    local candidate tk_version
    while IFS= read -r candidate; do
        [ -n "$candidate" ] || continue
        tk_version="$(python_tk_version "$candidate")"
        if [ -n "$tk_version" ] && version_ge "$tk_version" "$MIN_TK_VERSION"; then
            echo "$candidate"
            return 0
        fi
    done < <(python_candidates | awk '!seen[$0]++')
    return 1
}

venv_is_compatible() {
    [ -x "$VENV_DIR/bin/python" ] || return 1
    local expected_version current_version current_tk
    expected_version="$(python_version "$PYTHON_CMD")"
    current_version="$(python_version "$VENV_DIR/bin/python")"
    current_tk="$(python_tk_version "$VENV_DIR/bin/python")"

    [ "$current_version" = "$expected_version" ] || return 1
    [ -n "$current_tk" ] && version_ge "$current_tk" "$MIN_TK_VERSION"
}

echo "================================================"
echo "  飞书邮箱信息提取工具"
echo "================================================"
echo ""

# 检查 Python 3 + 可正常显示 Tkinter 的 Tk 版本
echo "检查 Python 图形界面环境..."
PYTHON_CMD="$(find_python_with_modern_tk)"
if [ -n "$PYTHON_CMD" ]; then
    PYTHON_VERSION=$("$PYTHON_CMD" --version 2>&1)
    TK_VERSION=$(python_tk_version "$PYTHON_CMD")
    echo -e "${GREEN}✓${NC} 使用 $PYTHON_CMD"
    echo -e "${GREEN}✓${NC} $PYTHON_VERSION / Tk $TK_VERSION"
else
    echo -e "${RED}✗${NC} 未找到可用的新版 Tkinter 环境"
    echo ""
    echo "当前系统自带 /usr/bin/python3 通常是 Tk 8.5，可能出现白屏。"
    echo "请安装 Homebrew Python/Tk 后再运行:"
    echo "  brew install python@3.13 python-tk@3.13"
    echo "  或访问 https://www.python.org/downloads/"
    echo ""
    read -p "按 Enter 键退出..."
    exit 1
fi

# 如果旧测试虚拟环境来自系统 Python/Tk 8.5，则备份后重建。
# 注意：mac-build.command 使用的是 venv/，这里不会修改打包环境。
if [ -d "$VENV_DIR" ] && ! venv_is_compatible; then
    BACKUP_DIR="$SCRIPT_DIR/.venv.bak.$(date '+%Y%m%d-%H%M%S')"
    echo ""
    echo -e "${YELLOW}!${NC} 当前测试虚拟环境不是新版 Tk，正在备份并重建..."
    echo "旧环境: $VENV_DIR"
    echo "备份到: $BACKUP_DIR"
    mv "$VENV_DIR" "$BACKUP_DIR"
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "创建虚拟环境..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗${NC} 虚拟环境创建失败"
        read -p "按 Enter 键退出..."
        exit 1
    fi
    echo -e "${GREEN}✓${NC} 虚拟环境创建成功"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓${NC} 测试环境: $(python -c 'import sys; print(sys.executable)') / Python $(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")') / Tk $(python -c 'import tkinter as tk; print(tk.TkVersion)')"

# 检查并安装依赖
echo ""
echo "检查依赖包..."
MISSING_PACKAGES=""

check_package() {
    if ! python -c "import $1" &> /dev/null; then
        MISSING_PACKAGES="$MISSING_PACKAGES $1"
    fi
}

check_package "openpyxl"
check_package "requests"

if [ -n "$MISSING_PACKAGES" ]; then
    echo -e "${YELLOW}!${NC} 缺少依赖包: $MISSING_PACKAGES"
    echo ""
    echo "安装依赖中..."
    python -m pip install --quiet openpyxl requests
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} 依赖安装完成"
    else
        echo -e "${RED}✗${NC} 依赖安装失败"
        read -p "按 Enter 键退出..."
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} 所有依赖已安装"
fi

# 运行程序
echo ""
echo "启动程序..."
echo ""

python email_extractor_gui.py

# 如果程序退出，显示提示
if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}程序异常退出${NC}"
fi

# 保持窗口（可选）
read -p "按 Enter 键退出..."
