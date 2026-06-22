#!/bin/bash
# Trigger the GitHub Actions Windows build and download the exe artifact.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

WORKFLOW_FILE="windows-build.yml"
ARTIFACT_NAME="windows-exe"
DOWNLOAD_DIR="release_windows_github"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  GitHub Actions - Windows 打包${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo -e "${RED}✗ 当前目录不是 Git 仓库${NC}"
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    echo -e "${RED}✗ 未检测到 GitHub CLI: gh${NC}"
    echo "安装: brew install gh"
    echo "登录: gh auth login"
    exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
    echo -e "${RED}✗ GitHub CLI 尚未登录${NC}"
    echo "请先运行: gh auth login"
    exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
    echo -e "${RED}✗ 当前仓库没有 origin 远端${NC}"
    echo "请先在 GitHub 创建仓库，并执行:"
    echo "  git remote add origin <你的 GitHub 仓库地址>"
    echo "  git push -u origin <当前分支>"
    exit 1
fi

BRANCH="$(git branch --show-current)"
if [ -z "$BRANCH" ]; then
    echo -e "${RED}✗ 当前不在普通分支上，无法触发 workflow_dispatch${NC}"
    exit 1
fi

DEFAULT_BRANCH="$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name' 2>/dev/null || echo "")"
if [ -n "$DEFAULT_BRANCH" ] && [ "$BRANCH" != "$DEFAULT_BRANCH" ]; then
    echo -e "${YELLOW}提示: 当前分支是 $BRANCH，仓库默认分支是 $DEFAULT_BRANCH。${NC}"
    echo "GitHub 要求 workflow_dispatch 文件先存在于默认分支，首次使用请先把 .github/workflows/windows-build.yml 合入默认分支。"
    echo ""
fi

if [ -n "$(git status --porcelain .github/workflows/windows-build.yml requirements.txt email_extractor_gui.py contact_extractor.py excel_exporter.py imap_client.py feishu_email.py)" ]; then
    echo -e "${YELLOW}提示: 有未提交的打包相关改动。GitHub Actions 只会使用已经 push 到 GitHub 的代码。${NC}"
    echo "请确认已经 commit 并 push 后再继续。"
    echo ""
fi

echo -e "${YELLOW}[1/4]${NC} 检查远端分支..."
git fetch origin "$BRANCH" >/dev/null 2>&1 || {
    echo -e "${RED}✗ GitHub 上找不到分支: $BRANCH${NC}"
    echo "请先执行: git push -u origin $BRANCH"
    exit 1
}

echo -e "${YELLOW}[2/4]${NC} 触发 GitHub Actions workflow..."
gh workflow run "$WORKFLOW_FILE" --ref "$BRANCH"

echo "等待 GitHub 创建运行记录..."
sleep 8

RUN_ID="$(gh run list --workflow "$WORKFLOW_FILE" --branch "$BRANCH" --limit 1 --json databaseId --jq '.[0].databaseId')"
if [ -z "$RUN_ID" ] || [ "$RUN_ID" = "null" ]; then
    echo -e "${RED}✗ 未找到刚触发的 workflow run${NC}"
    exit 1
fi

echo -e "${YELLOW}[3/4]${NC} 等待云端 Windows 打包完成..."
gh run watch "$RUN_ID" --exit-status

echo -e "${YELLOW}[4/4]${NC} 下载产物..."
rm -rf "$DOWNLOAD_DIR"
mkdir -p "$DOWNLOAD_DIR"
gh run download "$RUN_ID" --name "$ARTIFACT_NAME" --dir "$DOWNLOAD_DIR"

EXE_PATH="$DOWNLOAD_DIR/邮件小助手.exe"
if [ ! -f "$EXE_PATH" ]; then
    echo -e "${RED}✗ 下载失败，未找到 $EXE_PATH${NC}"
    exit 1
fi

EXE_SIZE="$(du -h "$EXE_PATH" | awk '{print $1}')"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Windows 打包完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "产物: $SCRIPT_DIR/$EXE_PATH"
echo "大小: $EXE_SIZE"
