#!/bin/bash
# MinerU 本地文档解析（VLM 后端）
# 用法: bash start_mineru.sh <输入文件> [输入文件2 ...]
# 输出: /mnt/d/Antigravity-Hub/temp/MinerU转换/<路径编码文件夹>/<文件名>.md + .assets/

set -euo pipefail

# === 环境配置 ===
source "${MINERU_VENV:-$HOME/mineru-env}/bin/activate"
export MINERU_MODEL_SOURCE=local
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_DISABLE_FLASHINFER=1

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
OUTPUT_BASE="${MINERU_OUTPUT_DIR:-${LEARNING_TOOLS_DATA_DIR:-$SCRIPT_DIR/../../../.local}/mineru-local}"

# === 路径编码函数（匹配 API 脚本的 path_to_folder_name） ===
path_to_folder_name() {
    local fpath="$1"
    # 取绝对路径，去掉扩展名
    local resolved
    resolved=$(realpath "$fpath")
    resolved="${resolved%.*}"
    # 去掉 /mnt/X/ 前缀（对应 Windows 盘符）
    resolved=$(echo "$resolved" | sed 's|^/mnt/[a-zA-Z]/||')
    # 路径分隔符 → 下划线，清理非法字符
    echo "$resolved" | tr '/' '_' | sed 's/[<>:"|?*]//g'
}

# === 后处理函数：将 MinerU 原始输出转为 Typora 风格 ===
postprocess() {
    local raw_dir="$1"   # MinerU 原始输出目录（含 vlm/ 子目录）
    local stem="$2"      # 文件名（不含扩展名）
    local dest_dir="$3"  # 最终目标文件夹

    # 找到 md 文件
    local src_md
    src_md=$(find "$raw_dir" -name "*.md" -type f | head -1)
    if [ -z "$src_md" ]; then
        echo "  ⚠️ 未找到 md 输出"
        return 1
    fi

    mkdir -p "$dest_dir"

    # 复制 md，替换图片路径 images/ → stem.assets/
    sed "s|images/|${stem}.assets/|g" "$src_md" > "$dest_dir/${stem}.md"

    # 复制图片到 .assets 目录
    local src_imgs
    src_imgs=$(find "$raw_dir" -name "images" -type d | head -1)
    if [ -n "$src_imgs" ] && [ -d "$src_imgs" ]; then
        mkdir -p "$dest_dir/${stem}.assets"
        cp "$src_imgs"/* "$dest_dir/${stem}.assets/" 2>/dev/null || true
    fi

    echo "  ✅ $dest_dir/${stem}.md"
}

# === 主逻辑 ===
if [ $# -eq 0 ]; then
    echo "用法: $0 <文件1> [文件2 ...]"
    echo "支持: PDF / 图片 / DOCX / PPTX / XLSX"
    echo "输出: $OUTPUT_BASE/<路径编码>/<文件名>.md + .assets/"
    exit 1
fi

TEMP_OUT=$(mktemp -d)
trap "rm -rf '$TEMP_OUT'" EXIT

for INPUT_PATH in "$@"; do
    if [ ! -f "$INPUT_PATH" ]; then
        echo "⚠️ 文件不存在: $INPUT_PATH"
        continue
    fi

    STEM=$(basename "${INPUT_PATH%.*}")
    FOLDER_NAME=$(path_to_folder_name "$INPUT_PATH")
    DEST_DIR="$OUTPUT_BASE/$FOLDER_NAME"

    # 缓存检查
    if [ -d "$DEST_DIR" ] && ls "$DEST_DIR"/*.md 1>/dev/null 2>&1; then
        echo "⏭️ 已缓存: $STEM"
        continue
    fi

    echo "📄 解析: $INPUT_PATH"
    BATCH_OUT="$TEMP_OUT/$STEM"

    mineru -p "$INPUT_PATH" -o "$BATCH_OUT" -b vlm-auto-engine 2>&1 | tee "$TEMP_OUT/mineru.log"

    # 后处理
    postprocess "$BATCH_OUT" "$STEM" "$DEST_DIR"
done
