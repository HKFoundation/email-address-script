#!/bin/bash
# 飞书邮箱提取工具 - Windows 打包脚本（Docker 版）
# 在 macOS 上用 Docker 容器跨平台编译出 Windows 单文件 .exe
# 前置条件：本机已安装并启动 Docker

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DOCKER_IMAGE="feishu-email-win-builder:latest"
DOCKER_PLATFORM="linux/amd64"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  飞书邮箱提取工具 - Windows 打包${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1) 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ 未检测到 Docker${NC}"
    echo "请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}✗ Docker 未运行${NC}"
    echo "请启动 Docker Desktop 后重试"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker 已就绪"

# 2) 校验必要文件
REQUIRED_FILES=("email_extractor_gui.py" "contact_extractor.py"
                "excel_exporter.py" "imap_client.py" "feishu_email.py"
                "requirements.txt" "Dockerfile.windows")
for f in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$SCRIPT_DIR/$f" ]; then
        echo -e "${RED}✗ 缺少文件: $f${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓${NC} 项目文件齐全"

# 3) 清理旧产物
echo ""
echo -e "${YELLOW}[1/5]${NC} 清理旧文件..."
rm -rf release_windows build_windows .pyinstaller_cache __pycache__ */__pycache__ *.spec
mkdir -p release_windows

# 4) 构建 Docker 镜像（首次较慢，约 3-5 分钟；之后秒级缓存）
echo ""
echo -e "${YELLOW}[2/5]${NC} 构建 Docker 镜像（首次会下载约 2-3GB，请耐心等待）..."
docker build --platform "$DOCKER_PLATFORM" -f Dockerfile.windows -t "$DOCKER_IMAGE" . || {
    echo -e "${RED}✗ Docker 镜像构建失败${NC}"
    exit 1
}
echo -e "${GREEN}✓${NC} 镜像构建完成"

echo ""
echo -e "${YELLOW}[3/5]${NC} 检查 Windows Python/Wine 运行环境..."
if ! docker run --rm --platform "$DOCKER_PLATFORM" --entrypoint /bin/bash "$DOCKER_IMAGE" -lc 'python --version >/dev/null'; then
    echo ""
    echo -e "${RED}✗ Windows Python/Wine 无法在当前 Docker 环境中启动${NC}"
    echo ""
    echo "当前基础镜像是 linux/amd64。Apple Silicon Mac 需要 Docker Desktop 能稳定运行 amd64 + Wine。"
    echo "可以尝试："
    echo "  1. Docker Desktop → Settings → General，开启 Rosetta x86/amd64 emulation 后重试"
    echo "  2. 在 Intel Mac / x86_64 Linux 机器上运行本脚本"
    echo "  3. 在 Windows 机器或 GitHub Actions Windows runner 上用 PyInstaller 打包"
    exit 1
fi
echo -e "${GREEN}✓${NC} Windows Python/Wine 可启动"

# 5) 在容器内执行 PyInstaller
# cdrx 镜像的入口点会自动处理 Wine 调起 Windows 版 PyInstaller
echo ""
echo -e "${YELLOW}[4/5]${NC} 在容器内打包 Windows .exe（首次约 2-5 分钟）..."

# 把源码和构建产物用 bind mount 挂进容器，避免镜像臃肿
docker run --rm \
    --platform "$DOCKER_PLATFORM" \
    --entrypoint /bin/bash \
    -v "$SCRIPT_DIR:/src" \
    -v "$SCRIPT_DIR/release_windows:/src/release_windows" \
    -e PYTHONHASHSEED=random \
    "$DOCKER_IMAGE" \
    -lc '
        set -e
        cd /src
        # 升级 pip 并安装项目依赖
        python -m pip install --upgrade pip --quiet
        python -m pip install -r requirements.txt --quiet
        python -m pip install pyinstaller --quiet

        # 清理旧构建
        rm -rf build .pyinstaller_cache *.spec

        # PyInstaller 打 Windows 单文件 .exe
        # --onefile: 单文件
        # --windowed: 无控制台（GUI 程序）
        # --name: 产物文件名
        # --hidden-import=tkinter: tkinter 是隐式导入，需要显式声明
        python -m PyInstaller \
            --name="FeishuEmailExtractor" \
            --onefile \
            --windowed \
            --distpath=release_windows \
            --workpath=build_windows \
            --specpath=. \
            --hidden-import=tkinter \
            email_extractor_gui.py
    '

# 6) 校验产物
echo ""
echo -e "${YELLOW}[5/5]${NC} 校验产物..."
EXE_PATH="release_windows/FeishuEmailExtractor.exe"
if [ ! -f "$EXE_PATH" ]; then
    echo -e "${RED}✗ 打包失败，未找到 $EXE_PATH${NC}"
    exit 1
fi

EXE_SIZE=$(du -h "$EXE_PATH" | awk '{print $1}')
echo -e "${GREEN}✓${NC} 打包成功"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Windows 打包完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "产物: $SCRIPT_DIR/$EXE_PATH"
echo "大小: $EXE_SIZE"
echo ""
echo "将 .exe 复制到 Windows 电脑双击即可运行"
echo "（首次启动可能需要 5-10 秒解压，请耐心等待）"
