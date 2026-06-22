#!/bin/bash
# =====================================================
# 飞书邮箱信息提取工具 - 跨平台打包
# =====================================================
# 双击 = 进入交互菜单
# 命令行调用：
#   mac-build.command mac    只打 macOS
#   mac-build.command win    通过 GitHub Actions 打 Windows
#   mac-build.command all    两个都打
#   mac-build.command        弹出菜单

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 防止 GUI 弹窗抢焦点
trap '' SIGINT SIGTSTP

show_banner() {
    clear
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN}    飞书邮箱信息提取工具 - 跨平台打包${NC}"
    echo -e "${CYAN}================================================${NC}"
    echo ""
}

wait_for_key() {
    echo ""
    echo -e "${YELLOW}按任意键返回菜单...${NC}"
    if [ -t 0 ]; then
        read -n 1 -s _
    else
        sleep 3
    fi
}

# ============================================================
# macOS 打包（PyInstaller + Homebrew Python，arm64）
# 依赖: brew install python-tk@3.x (x 与 python3 主版本一致)
# ============================================================
build_mac() {
    show_banner
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  开始打包 macOS 应用${NC}"
    echo -e "${BLUE}  目标架构: Apple Silicon (arm64)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    if [ "$(uname -m)" != "arm64" ]; then
        echo -e "${YELLOW}警告: 当前架构是 $(uname -m)，与 arm64 不匹配${NC}"
        echo "如需 x86_64 构建，请使用 Rosetta 2 或在 Intel Mac 上执行"
        echo ""
    fi

    VENV_DIR="venv"

    python_candidates() {
        for candidate in \
            /opt/homebrew/bin/python3.13 \
            /opt/homebrew/bin/python3.12 \
            /opt/homebrew/bin/python3 \
            /usr/local/bin/python3.13 \
            /usr/local/bin/python3.12 \
            /usr/local/bin/python3; do
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

    check_tkinter() {
        local candidate
        while IFS= read -r candidate; do
            if [ -n "$candidate" ] && "$candidate" -c "import _tkinter, tkinter" >/dev/null 2>&1; then
                echo "$candidate"
                return 0
            fi
        done < <(python_candidates | awk '!seen[$0]++')
        echo ""
    }

    PYTHON_BIN=$(check_tkinter)
    if [ -z "$PYTHON_BIN" ]; then
        echo -e "${RED}✗ 错误: 系统没有可用的 tkinter${NC}"
        echo "运行: brew install python-tk@3.13"
        return 1
    fi
    PYTHON_VERSION=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo -e "${GREEN}使用 Python: $PYTHON_BIN (Python $PYTHON_VERSION)${NC}"

    echo -e "${YELLOW}[1/6]${NC} 创建虚拟环境..."
    if [ -d "$VENV_DIR" ]; then
        VENV_VERSION=$("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")
        if [ "$VENV_VERSION" = "$PYTHON_VERSION" ]; then
            echo "虚拟环境已存在，跳过创建"
        else
            echo "虚拟环境 Python 版本为 ${VENV_VERSION:-未知}，重新创建"
            rm -rf "$VENV_DIR"
            "$PYTHON_BIN" -m venv "$VENV_DIR" || return 1
        fi
    else
        "$PYTHON_BIN" -m venv "$VENV_DIR" || return 1
    fi

    echo -e "${YELLOW}[2/6]${NC} 激活虚拟环境..."
    source "$VENV_DIR/bin/activate"

    echo -e "${YELLOW}[3/6]${NC} 安装依赖..."
    python -m pip install --upgrade pip >/dev/null || { deactivate; return 1; }
    python -m pip install -r requirements.txt || { deactivate; return 1; }

    echo -e "${YELLOW}[4/6]${NC} 安装 PyInstaller..."
    python -m pip install "pyinstaller>=6.6.0,<7.0" || { deactivate; return 1; }

    echo -e "${YELLOW}[5/6]${NC} 清理旧文件..."
    # nullglob 让无匹配的 glob 静默展开为空，避免 zsh 兼容模式或 set -e 下意外中断
    shopt -s nullglob
    rm -rf release build __pycache__ */__pycache__ *.spec
    shopt -u nullglob

    echo "打包中（可能需要数十秒）..."
    "$VENV_DIR/bin/python" -m PyInstaller \
        --name="飞书邮箱提取工具" \
        --windowed \
        --onedir \
        --distpath="release" \
        --hidden-import=tkinter \
        email_extractor_gui.py || { deactivate; return 1; }

    deactivate

    echo ""
    echo -e "${YELLOW}配置启动脚本（修复 Homebrew Python 的 TCL/TK 路径）...${NC}"

    APP_PATH="release/飞书邮箱提取工具.app"
    BIN_PATH="$APP_PATH/Contents/MacOS"

    if [ ! -d "$APP_PATH" ]; then
        echo -e "${RED}✗ 错误: 打包失败，未找到 $APP_PATH${NC}"
        return 1
    fi

    mv "$BIN_PATH/飞书邮箱提取工具" "$BIN_PATH/飞书邮箱提取工具-bin"

    cat > "$BIN_PATH/飞书邮箱提取工具" << 'LAUNCHER'
#!/bin/bash

# 获取脚本所在目录
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOURCES="$SELF_DIR/../Resources"

# 设置 TCL/TK 环境（解决 Homebrew Python 打包后 tkinter 找不到 tcl 的问题）
for TCL_VER in tcl9.0 tcl9 tcl8.6 tcl8.5; do
    if [ -f "$RESOURCES/$TCL_VER/init.tcl" ]; then
        export TCL_LIBRARY="$RESOURCES/$TCL_VER"
        break
    fi
done
for TK_VER in tk9.0 tk8.6 tk8.5; do
    if [ -f "$RESOURCES/$TK_VER/tk.tcl" ]; then
        export TK_LIBRARY="$RESOURCES/$TK_VER"
        break
    fi
done

# 运行主程序
exec "$SELF_DIR/飞书邮箱提取工具-bin" "$@"
LAUNCHER

    chmod +x "$BIN_PATH/飞书邮箱提取工具"

    echo "复制 TCL/TK 库..."
    copy_tcl_tk() {
        local base tcl_dir tk_dir
        for base in /opt/homebrew /usr/local; do
            for pair in "tcl9.0 tk9.0" "tcl9 tk9.0" "tcl8.6 tk8.6" "tcl8.5 tk8.5"; do
                tcl_dir=${pair%% *}
                tk_dir=${pair##* }
                if [ -f "$base/lib/$tcl_dir/init.tcl" ] && [ -f "$base/lib/$tk_dir/tk.tcl" ]; then
                    mkdir -p "$APP_PATH/Contents/Resources/$tcl_dir" "$APP_PATH/Contents/Resources/$tk_dir"
                    cp -R "$base/lib/$tcl_dir/." "$APP_PATH/Contents/Resources/$tcl_dir/"
                    cp -R "$base/lib/$tk_dir/." "$APP_PATH/Contents/Resources/$tk_dir/"
                    echo -e "${GREEN}已从 $base 复制 TCL/TK (${tcl_dir}/${tk_dir})${NC}"
                    return 0
                fi
            done
        done
        return 1
    }

    if ! copy_tcl_tk; then
        echo -e "${YELLOW}警告: 未找到可复制的 TCL/TK 库，打包后可能无法运行${NC}"
        echo "请执行: brew install python-tk@3.13 tcl-tk"
    fi

    # 标记 app 为 arm64-only（重要：避免 Gatekeeper 在 Apple Silicon 上跑 x86_64 兼容层）
    echo "设置 app 架构标记为 arm64..."
    ARCH_FLAGS_PATH="$APP_PATH/Contents/Info.plist"
    if [ -f "$ARCH_FLAGS_PATH" ]; then
        /usr/libexec/PlistBuddy -c "Delete :LSArchitecturePriority" "$ARCH_FLAGS_PATH" 2>/dev/null || true
        /usr/libexec/PlistBuddy -c "Add :LSArchitecturePriority array" "$ARCH_FLAGS_PATH" 2>/dev/null || true
        /usr/libexec/PlistBuddy -c "Add :LSArchitecturePriority: string arm64" "$ARCH_FLAGS_PATH" 2>/dev/null || true
    fi

    echo "重新签名 app..."
    codesign --force --deep --sign - "$APP_PATH" || return 1

    echo -e "${YELLOW}[6/6]${NC} 清理 PyInstaller 中间产物..."
    shopt -s nullglob
    rm -rf build __pycache__ */__pycache__ *.spec
    shopt -u nullglob
    echo "已清理 build/、*.spec，产物 release/ 保留"

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  macOS 打包完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "输出文件: $APP_PATH"
    echo "双击运行，或在终端执行: open '$APP_PATH'"
    return 0
}

# ============================================================
# Windows 打包（通过 GitHub Actions 云端构建）
# 具体逻辑在 github-windows-build.command，这里只做编排
# ============================================================
build_windows() {
    show_banner
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  开始打包 Windows 应用 (GitHub Actions)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    if [ ! -f "github-windows-build.command" ]; then
        echo -e "${RED}✗ 缺少 github-windows-build.command${NC}"
        return 1
    fi

    chmod +x github-windows-build.command
    if bash ./github-windows-build.command; then
        echo ""
        echo -e "${GREEN}✓ Windows 打包成功！${NC}"
        echo "产物: $SCRIPT_DIR/release_windows_github/邮件小助手.exe"
        return 0
    else
        echo ""
        echo -e "${RED}✗ Windows 打包失败${NC}"
        return 1
    fi
}

# ============================================================
# 命令行参数: 无参进菜单，mac/win/all 直接执行
# ============================================================
case "${1:-}" in
    mac|m)
        build_mac
        exit $?
        ;;
    win|w)
        build_windows
        exit $?
        ;;
    all|a)
        build_mac
        MAC_RESULT=$?
        echo ""
        if [ $MAC_RESULT -eq 0 ]; then
            build_windows
            WIN_RESULT=$?
        else
            WIN_RESULT=1
        fi
        show_banner
        if [ $MAC_RESULT -eq 0 ] && [ $WIN_RESULT -eq 0 ]; then
            echo -e "${GREEN}✓ 两个平台均打包成功${NC}"
            echo ""
            echo "Mac 产物:    $SCRIPT_DIR/release/飞书邮箱提取工具.app"
            echo "Windows 产物: $SCRIPT_DIR/release_windows_github/邮件小助手.exe"
        else
            echo -e "${YELLOW}部分平台打包失败 (macOS=$MAC_RESULT, Windows=$WIN_RESULT)${NC}"
        fi
        exit 0
        ;;
    help|-h|--help)
        echo "用法: $0 [mac|win|all|help]"
        echo "  mac    只打 macOS（生成 release/飞书邮箱提取工具.app）"
        echo "  win    只打 Windows（通过 GitHub Actions 生成 release_windows_github/邮件小助手.exe）"
        echo "  all    两个平台都打"
        echo "  无参   弹出交互菜单（默认 10 秒后选 3=两个都打）"
        echo "  help   显示此帮助"
        exit 0
        ;;
esac

# ============================================================
# 交互菜单
# ============================================================
CHOICE=""
prompt_choice() {
    show_banner
    echo -e "${GREEN}请选择打包目标:${NC}"
    echo ""
    echo -e "  ${BLUE}1${NC}) macOS   → 生成 ${YELLOW}飞书邮箱提取工具.app${NC} (本机直接打包)"
    echo -e "  ${BLUE}2${NC}) Windows → 生成 ${YELLOW}邮件小助手.exe${NC} (GitHub Actions)"
    echo -e "  ${BLUE}3${NC}) 两个平台都打"
    echo -e "  ${BLUE}0${NC}) 退出"
    echo ""
    if [ -n "$1" ]; then
        echo -e "${YELLOW}提示: ${NC}$1"
        echo ""
    fi
    printf "请输入选项 [0-3] (默认回车 = 3): "
    if [ -t 0 ]; then
        read -t 10 CHOICE
        CHOICE=${CHOICE:-3}
    else
        CHOICE=3
    fi
}

while true; do
    prompt_choice
    case "$CHOICE" in
        1)
            build_mac
            wait_for_key
            ;;
        2)
            build_windows
            wait_for_key
            ;;
        3)
            show_banner
            echo -e "${BLUE}开始依次打包 macOS + Windows${NC}"
            echo ""
            build_mac
            MAC_RESULT=$?
            echo ""
            if [ $MAC_RESULT -eq 0 ]; then
                build_windows
                WIN_RESULT=$?
            else
                WIN_RESULT=1
            fi

            show_banner
            if [ $MAC_RESULT -eq 0 ] && [ $WIN_RESULT -eq 0 ]; then
                echo -e "${GREEN}✓ 两个平台均打包成功${NC}"
                echo ""
                echo "Mac 产物:    $SCRIPT_DIR/release/飞书邮箱提取工具.app"
                echo "Windows 产物: $SCRIPT_DIR/release_windows_github/邮件小助手.exe"
            else
                echo -e "${YELLOW}部分平台打包失败 (macOS=$MAC_RESULT, Windows=$WIN_RESULT)${NC}"
            fi
            wait_for_key
            ;;
        0|q|Q)
            show_banner
            echo -e "${GREEN}再见！${NC}"
            exit 0
            ;;
        *)
            prompt_choice "无效选项 '$CHOICE'，请重新选择"
            ;;
    esac
done
