# 微博下载器 / Weibo Downloader

📱 一键下载微博图文+视频，纯 Python 实现，无需外部工具。

## 功能

- 🖼️ **图片下载** — 原图 .jpg，自动选最大尺寸（large=original，微博天花板）
- 🎬 **视频下载** — 1440p .mp4（playback_list 最高档，转码；单链路，拿不到就报错）
- 🔗 **链接格式** — 仅支持 weibo.com 状态链接
- 📋 **批量下载** — 支持从 txt 文件批量导入
- 🍃 **零外部依赖** — 仅 `requests`，不依赖 gallery-dl/yt-dlp 等工具
- ⏰ **自动时间戳** — 下载后自动用 exiftool 写入发布时间（带 +08:00 时区）

## 使用方法

```bash
# 安装依赖
pip install requests

# 下载单条微博（图片）
python3 wb_img.py "https://weibo.com/USER/STATUS_ID"

# 下载单条微博（视频）
python3 wb_video.py "https://weibo.com/USER/STATUS_ID"

# 指定保存目录
python3 wb_img.py "https://weibo.com/USER/123456" /tmp/output

# 批量下载
python3 wb_img.py --batch links.txt --out-dir /tmp/weibo
```

仅支持 weibo.com 状态链接。

## 输出

- **图片**：`{作者}_{标题}_{序号}.jpg`（原图，large 档）
- **视频**：`{作者}_{标题}_{序号}.mp4`（1440p 最高档，转码）
- **时间戳**：publish_time_str（"2026:07:05 15:33:12"，exiftool 直接可用，自动写入文件）

```
./author_name_statusid/
├── prefix_01.jpg
├── prefix_02.jpg
├── prefix_03.mp4
├── ...
```

## 技术说明

1. 访客绕过 — 自动调用 `passport.weibo.com/visitor/genvisitor2` 获取访客凭证
2. Cookie 管理 — 首次获取后保存到 `storage/weibo_cookies.json`，365 天有效
3. API 调用 — `weibo.com/ajax/statuses/show?id=xxx` 获取微博详情
4. 媒体解析 — 支持新版 `mix_media_info` 和旧版 `pic_ids` 两种数据格式
5. 图片：`wx1.sinaimg.cn/large/{fileId}.jpg`（large=original，微博天花板）
6. 视频：`playback_list` 取 1440p 最高档（转码，非原画）

## 注意事项（坑点）

- **必须用 HTTP**：`https://wx*.sinaimg.cn` 会被 CDN 拒（ACCESS DENIED），改 `http://`
- **水印去不掉**：微博图片水印焊死在像素里，无解
- 依赖仅需 `requests` 库

## 文件结构

```
weibo/
├── README.md
├── requirements.txt
├── wb_img.py       # 图片原图下载
└── wb_video.py     # 视频 1440p 下载
```

## 许可

MIT
