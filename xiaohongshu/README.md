# 小红书下载器 / Xiaohongshu Downloader

一键下载小红书图文+视频，纯 Python 实现，无需外部工具。

## 功能

- 🖼️ **图片下载**：原格式直存（裸链按魔数判格式，零转码；支持 MPO 实况）
- 🎬 **视频下载**：真原画（originVideoKey 直连，MD5 验证）
- 🔗 **短链解析**：自动解析 xhslink.cn 短链
- ⏰ **自动时间戳**：下载后自动用 exiftool 写入发布时间（带 +08:00 时区）

## 使用方法

```bash
# 下载图片（单条笔记）
python3 xhs_img.py "https://xhslink.cn/o/xxx" --out-dir /tmp/xhs

# 下载视频（单条笔记）
python3 xhs_video.py "https://xhslink.cn/o/xxx" --out-dir /tmp/xhs
```

支持以下输入格式：
- 小红书短链：`https://xhslink.cn/o/xxx`
- 完整笔记链接：`https://www.xiaohongshu.com/explore/xxx`

## 输出

- **图片**：`{作者}_{标题}_{发布日期}_{note_id[:8]}_{序号}.{后缀}`（原格式直存：HEIF/PNG/JPEG/MPO 按魔数识别）
- **视频**：`{作者}_{标题}_{发布日期}_{note_id[:8]}_01.mov`（真原画，MD5 验证）
- **时间戳**：发布时间 → exiftool 自动写入（带 +08:00 时区）

## 技术说明

1. 短链解析 → 301 重定向 → 获取 note_id
2. 抓笔记页 → `__INITIAL_STATE__` 提 fileId / originVideoKey
3. 图片：`https://sns-img-hw.xhscdn.com/<fileId>` 裸链直取 → 魔数判格式原样保存，零转码
4. 视频：`https://sns-video-hw.xhscdn.com/<originVideoKey>`（免签名裸 key）→ 流式下载 + Content-Length 对账
5. 单域名（sns-img-hw / sns-video-hw），无备域；图片间隔 3 秒（保守起见）

## 注意事项

- **零转码**：任何格式都不转码，按原格式直存
- **MPO 实况**：按 MPF 标记识别，存 .mpo
- 依赖仅需 `requests` 库

## 文件结构

```
xiaohongshu/
├── README.md
├── requirements.txt
├── xhs_img.py      # 图片智能下载
└── xhs_video.py    # 视频原画下载
```

## 许可

MIT
