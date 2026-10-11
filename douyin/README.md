# 抖音下载器 (Douyin Downloader)

下载抖音作品视频（真原画）、日常视频（真原画）和图文（q75 原图），纯 Python 实现。

## 功能

- 🎬 **作品视频**：真原画（detail API 取 v0d00/v0300 URI + ratio=default，免登录），单链路无降级
- 📱 **日常视频**：真原画（App 保存视频元数据提 v0d00/v0300 URI + ratio=default，免登录）
- 🖼️ **图文**：q75 原图（服务器公开最高档；--urls 模式，浏览器提链后下载）
- 📋 **批量下载**：支持从 txt 文件批量导入
- ⏰ **自动时间戳**：下载后自动用 exiftool 写入发布时间（带 +08:00 时区，touch -t 保底）

## 使用方法

```bash
# 作品视频（从分享链接）
python3 dy_video.py "https://v.douyin.com/xxxx/" --out-dir /tmp/douyin

# 日常视频（从 App 保存的视频文件提取 URI）
python3 dy_story.py --file 保存的日常视频.mp4 --out-dir /tmp/douyin
# 或直接指定 URI
python3 dy_story.py --uri v0300fg10000db1pc27og65sdjv9s7m0 --out-dir /tmp/douyin

# 图文（--urls 模式：先用浏览器提链存入 urls.txt）
python3 dy_img.py --urls urls.txt --out-dir /tmp/douyin

# 批量下载
python3 dy_video.py --batch links.txt --out-dir /tmp/douyin
```

支持以下输入格式：
- 抖音短链：`https://v.douyin.com/xxxx/`
- 完整分享文本：`0.28 复制打开抖音... https://v.douyin.com/xxxx/ b@a.NJ ...`
- 长链接：`https://www.douyin.com/video/xxxx`

## 输出

- **作品视频**：`{作者}_{标题}_{日期}_{id}_{序号}.mp4`（真原画）
- **日常视频**：`douyin_daily_{uri片段}.mp4`（真原画）
- **图文**：`dy_img_{序号}.webp/jpg`（q75，--urls 模式无元数据故用通用名）
- **时间戳**：自动写入（带 +08:00 时区）

## 技术说明

### 作品视频（单链路真原画）

1. 分享链接 → 301 重定向 → 真实 URL → 提取 content_id
2. `www.douyin.com/aweme/v1/web/aweme/detail/` 取元数据 + 视频 URI（v0d00/v0300 双链路）
3. `aweme/v1/play/?video_id={uri}&ratio=default&line=0`（www.douyin.com 主 / aweme.snssdk.com 备，免登录）→ 302 跳 CDN → 下载源文件
4. 原画校验：桶名 `tos-cn-v-`（转码在 `tos-cn-ve-`），URL 无 `br=` 参数
5. 失败即判 WAF，等 1 小时，不降级

### 日常视频（v0d00/v0300 双链路）

1. App 保存日常视频 → exiftool 读 `Keys:Comment` 提 `vid:v0d00...` / `vid:v0300...`
2. 同作品视频第 3 步（ratio=default，免登录）
3. 免 Cookie、免 X-Gorgon

### 图文（q75）

1. detail API 被 WAF 硬拦（全网 403），走 `--urls` 模式
2. 浏览器渲染笔记页提 q75 直链 → 写入 urls.txt → 脚本下载
3. q75 为服务器公开最高档（有损转码，非相机原图）；签名 URL 会过期

## 注意事项

- **图文 detail API 已死**：全网 403（uifid 硬门槛），只能走 `--urls` 模式
- **WAF 判停**：detail API 被拦时等 1 小时再试，期间不探测
- `story_25_filter`：被服务端内容过滤的视频直接跳过（永久拦死，不重试）
- 依赖仅需 `requests` 库

## 文件结构

```
douyin/
├── README.md
├── requirements.txt
├── dy_img.py           # 图文 q75（--urls 模式）
├── dy_video.py         # 作品视频真原画
└── dy_story.py         # 日常视频真原画
```

## 许可

MIT

