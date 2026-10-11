# orig-dl（三平台原画下载）

抖音 / 微博 / 小红书原图（真原画）下载脚本合集，纯 Python。

## 目录结构

```
common/
  headers.py     # 各平台统一 UA + Referer
  config.py      # 可配置限流间隔
  retry.py       # 429/403 指数退避重试
douyin/
  dy_img.py      # 图文 q75（--urls 模式）
  dy_video.py    # 作品视频真原画（ratio=default，v0d00/v0300 双链路）
  dy_story.py    # 日常视频真原画（App 保存视频提 URI，v0d00/v0300 双链路）
weibo/
  wb_img.py      # 图片 large 原图
  wb_video.py    # 视频 1440p（playback_list 最高档，转码）
xiaohongshu/
  xhs_img.py     # 图片原格式直存（零转码）
  xhs_video.py   # 视频原画（originVideoKey）
```

## 通用特性

- 🛡️ **反爬防护**：统一浏览器 UA + Referer，可配置限流间隔，429/403 指数退避重试
- ⏰ **自动时间戳**：下载后自动用 exiftool 写入发布时间
  - JPEG/HEIC：`-DateTimeOriginal` / `-CreateDate` + 时区偏移
  - PNG：`-XMP:CreateDate`（带时区）
  - `touch -t` 保底 mtime

## 各平台说明

### 抖音 (`douyin/`)

- 作品视频：真原画（`ratio=default`，v0d00/v0300 双链路，免登录）
- 日常视频：真原画（App 保存视频提 URI，v0d00/v0300 双链路，免登录）
- 图文：q75（服务器公开最高档，`--urls` 模式）

### 微博 (`weibo/`)

- 图片：`large` 原图（= original，微博天花板）
- 视频：1440p（`playback_list` 最高档，转码）

### 小红书 (`xiaohongshu/`)

- 图片：原格式直存（零转码，魔数判格式）
- 视频：真原画（`originVideoKey`，MD5 验证）

## 用法

```bash
# 小红书图片 / 视频
python3 xiaohongshu/xhs_img.py "https://xhslink.cn/o/xxx" --out-dir ./out
python3 xiaohongshu/xhs_video.py "https://xhslink.cn/o/xxx" --out-dir ./out

# 抖音作品视频 / 日常视频 / 图文
python3 douyin/dy_video.py "https://v.douyin.com/xxxx/" --out-dir ./out
python3 douyin/dy_story.py --file 保存的日常视频.mp4 --out-dir ./out
python3 douyin/dy_img.py --urls urls.txt --out-dir ./out

# 微博图片 / 视频
python3 weibo/wb_img.py "https://weibo.com/..." --out-dir ./out
python3 weibo/wb_video.py "https://weibo.com/..." --out-dir ./out
```
