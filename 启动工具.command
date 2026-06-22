#!/bin/bash

# =====================================================
# 飞书邮箱信息提取工具 - 启动脚本
# =====================================================

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"
cd "$SCRIPT_DIR"

# 虚拟环境目录
VENV_DIR="$SCRIPT_DIR/.venv"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "  飞书邮箱信息提取工具"
echo "================================================"
echo ""

# 检查 Python 3
echo "检查 Python 环境..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}✓${NC} 找到 $PYTHON_VERSION"
else
    echo -e "${RED}✗${NC} 未找到 Python 3"
    echo ""
    echo "请先安装 Python 3:"
    echo "  macOS: brew install python3"
    echo "  或访问 https://www.python.org/downloads/"
    echo ""
    read -p "按 Enter 键退出..."
    exit 1
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "创建虚拟环境..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗${NC} 虚拟环境创建失败"
        read -p "按 Enter 键退出..."
        exit 1
    fi
    echo -e "${GREEN}✓${NC} 虚拟环境创建成功"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

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
    pip install --quiet openpyxl requests
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
