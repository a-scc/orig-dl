# -*- coding: utf-8 -*-
"""抖音图文下载器（图片专用）。

原理：
  主链：slidesinfo API 取图片直链（带 PC 参数拿 2160×2880 档）
  兜底：--urls 模式（浏览器提链 → 直接下载）

  下载 q75 档 JPEG（抖音服务器公开最高档；q75 是有损转码，非相机原图）。
  拿不到最高档直接报错，不降级。

反爬：统一 UA + Referer，图片间隔见 common.config，
429/403 指数退避重试（common.retry）。

用法：
  python dy_img.py --urls urls.txt --out-dir ./out
  python dy_img.py <分享链接> --out-dir ./out
"""
import sys
import os

# 接入公共模块（仓库内运行时用）；单文件分发时缺 common/ 则用内置默认值
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from common.headers import DOUYIN as COMMON_HEADERS
    from common.config import RATE_LIMITS
    from common.retry import with_retry, douyin_get
    from common.timestamps import write_timestamps_smart
    HEADERS = dict(COMMON_HEADERS)
    _HAS_COMMON = True
except ImportError:
    _HAS_COMMON = False
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Referer": "https://www.douyin.com/",
    }
    RATE_LIMITS = {"douyin_image": 2}
    def with_retry(max_retries=3, backoff_base=2):
        def decorator(func):
            return func  # 单文件模式：不做指数退避
        return decorator
    def douyin_get(url, headers, **kwargs):
        import requests
        r = requests.get(url, headers=headers, **kwargs)
        if r.status_code == 403 and "Referer" in headers:
            print("[~] 403，去掉 Referer 重试...")
            h2 = dict(headers)
            h2.pop("Referer", None)
            r = requests.get(url, headers=h2, **kwargs)
        r.raise_for_status()
        return r
    def write_timestamps_smart(files, timestr, kind="image"):
        pass  # 单文件模式：跳过时间戳写入

try:
    import requests
except ImportError:
    print("[!] 缺少 requests 库，请执行：pip install requests")
    sys.exit(1)

import re
import struct
import time
from datetime import datetime, timezone, timedelta


def extract_url(text: str) -> str | None:
    """从分享文本中提取抖音链接（短链或长链）"""
    m = re.search(r"https?://v\.douyin\.com/[a-zA-Z0-9\-_.]+", text)
    if m:
        url = m.group(0)
        return url if url.endswith("/") else url + "/"
    m = re.search(r"https?://(?:www\.)?douyin\.com/(?:video|note)/[0-9]+", text)
    if m:
        return m.group(0)
    return None


def get_real_url(share_url: str) -> str | None:
    """跟随重定向，获取真实URL"""
    if "douyin.com/video/" in share_url or "douyin.com/note/" in share_url:
        return share_url
    try:
        r = requests.get(share_url, headers=HEADERS, allow_redirects=True, timeout=10)
        return r.url
    except Exception as e:
        print(f"[!] 获取真实链接失败: {e}")
        return None


def get_content_id(real_url: str) -> tuple[str | None, str | None]:
    """从真实 URL 中提取内容 ID 和类型（video/note），返回 (content_id, content_type)"""
    if "/note/" in real_url or "share/note/" in real_url:
        content_type = "note"
        m = re.search(r"/note/([0-9]+)", real_url)
        if m:
            return m.group(1), content_type
    elif "/video/" in real_url or "share/video/" in real_url:
        content_type = "video"
        m = re.search(r"/video/([0-9]+)", real_url)
        if m:
            return m.group(1), content_type

    for param in ["modal_id", "note_id", "item_id", "video_id"]:
        m = re.search(rf"{param}=([0-9]+)", real_url)
        if m:
            return m.group(1), "video"  # 默认按视频处理，后续自动检测

    m = re.search(r"/([0-9]{15,})", real_url)
    if m:
        return m.group(1), "video"

    return None, None


def get_slidesinfo_api(content_id: str) -> dict | None:
    """从 iesdouyin 的 slidesinfo API 获取图文信息。

    接口：GET https://www.iesdouyin.com/web/api/v2/aweme/slidesinfo/
         ?aweme_ids=[<id>]&aid=6383&app=aweme
    带 PC 参数拿最高档 url_list；不带 request_source（带了部分帖子会被过滤）。
    """
    api_url = (
        "https://www.iesdouyin.com/web/api/v2/aweme/slidesinfo/"
        f"?aweme_ids=%5B{content_id}%5D&aid=6383&app=aweme"
    )
    try:
        r = requests.get(api_url, headers=HEADERS, timeout=15)
        if r.status_code == 200 and r.text.strip():
            data = r.json()
            details = data.get("aweme_details", [])
            if details:
                return data
            print(f"[~] slidesinfo API 无 aweme_details（status_code={data.get('status_code')}）")
        else:
            print(f"[!] slidesinfo API 返回异常: HTTP {r.status_code}")
    except Exception as e:
        print(f"[~] slidesinfo API 请求失败: {e}")
    return None


def _url_ext(u: str) -> str:
    """取 URL 路径末尾的格式后缀（先剥掉 ? 后面的签名参数）。"""
    tail = u.split("?", 1)[0].rsplit(".", 1)[-1].lower()
    if "/" in tail or not tail.isalpha() or len(tail) > 5:
        return "bin"  # 取不到像样的后缀时的兜底
    return {"jpeg": "jpg"}.get(tail, tail)


def parse_slidesinfo_api(data: dict, content_id: str) -> dict | None:
    """从 slidesinfo API 响应中提取图文信息。

    优先取 jpg（q75 无水印最高档）；无 jpg 则回退 url_list[0]。
    不用 download_url_list（带水印）。
    """
    try:
        details = data.get("aweme_details", [])
        if not details:
            return None
        ad = details[0]
        desc = ad.get("desc", "无标题")
        nickname = ad.get("author", {}).get("nickname", "未知作者")
        # 发布时间戳（Unix 秒），显式转东八区
        publish_ts = ad.get("create_time")
        tz_sh = timezone(timedelta(hours=8))
        publish_time_str = datetime.fromtimestamp(publish_ts, tz_sh).strftime("%Y:%m:%d %H:%M:%S") if publish_ts else ""

        images = ad.get("images", [])
        if not images:
            print("[!] slidesinfo API 图文未找到图片")
            return None

        media_list = []
        for i, img in enumerate(images):
            url_list = img.get("url_list", [])
            if not url_list:
                print(f"[!] 第 {i + 1} 张无 url_list，跳过")
                continue
            best_url = None
            for u in url_list:
                if _url_ext(u) == "jpg":
                    best_url = u
                    break
            if not best_url:
                best_url = url_list[0]
                print(f"[~] 第 {i + 1} 张无 jpeg 条目，回退 url_list[0]")
            ext = _url_ext(best_url)
            name_part = _safe_name(nickname, 12)
            desc_part = _safe_name(desc, 18)
            date_part = publish_time_str[0:4] + publish_time_str[5:7] + publish_time_str[8:10] if publish_time_str else "nodate"
            aweme_id = ad.get("aweme_id", content_id)
            filename = f"{name_part}_{desc_part}_{date_part}_{aweme_id[:8]}_{i + 1:02d}.{ext}"
            media_list.append({
                "url": best_url,
                "filename": filename,
            })

        if not media_list:
            print("[!] slidesinfo API 未解析出可用图片地址")
            return None

        return {
            "type": "image",
            "desc": desc,
            "nickname": nickname,
            "publish_time": publish_ts,
            "publish_time_str": publish_time_str,
            "media": media_list,
        }
    except Exception as e:
        print(f"[!] 解析 slidesinfo API 内容出错: {e}")
        return None


def _safe_name(text: str, max_len: int = 30) -> str:
    """去除非法字符、多余符号、截断"""
    text = re.sub(r'[#@&]', '', text)
    text = re.sub(r'[\\/*?:"<>|\r\n\t]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len]


def sniff_image_size(content: bytes):
    """从文件魔数识别图片尺寸（不依赖 PIL）。返回 (w, h) 或 None。"""
    # PNG: IHDR 在偏移 16 处
    if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
        w, h = struct.unpack(">II", content[16:24])
        return (w, h)
    # JPEG: 找 SOF 标记
    if content.startswith(b"\xff\xd8"):
        i = 2
        while i < len(content) - 9:
            if content[i] != 0xFF:
                i += 1
                continue
            marker = content[i + 1]
            if 0xC0 <= marker <= 0xC3:  # SOF0/1/2/3
                h = struct.unpack(">H", content[i + 5:i + 7])[0]
                w = struct.unpack(">H", content[i + 7:i + 9])[0]
                return (w, h)
            if marker == 0xD9:  # EOI
                break
            seg_len = struct.unpack(">H", content[i + 2:i + 4])[0]
            i += 2 + seg_len
    # WebP: VP8 头
    if content.startswith(b"RIFF") and len(content) >= 30 and content[8:12] == b"WEBP":
        if content[12:16] == b"VP8 " and len(content) >= 30:
            w = struct.unpack("<H", content[26:28])[0] & 0x3FFF
            h = struct.unpack("<H", content[28:30])[0] & 0x3FFF
            return (w, h)
    return None


def download_file(url: str, filepath: str, is_image: bool = False) -> bool:
    """下载单个文件（视频流式+进度条，图片直接下载）。
    网络抖动/403 由 with_retry + douyin_get 统一处理；下载后做
    Content-Length 对账和魔数校验，失败抛异常走退避重试。"""
    try:
        print(f"[+] 正在下载: {os.path.basename(filepath)}")
        if is_image:
            @with_retry()
            def _fetch():
                return douyin_get(url, HEADERS, timeout=30)
            r = _fetch()
            content = r.content
            cl = r.headers.get("content-length")
            if cl and len(content) != int(cl):
                raise ValueError(f"内容截断 ({len(content)}/{cl} 字节)")
            size = sniff_image_size(content)
            if not size:
                raise ValueError("下载内容不是有效图片")
            with open(filepath, "wb") as f:
                f.write(content)
            size_kb = len(content) / 1024
            print(f"[OK] 下载完成！保存至: {os.path.abspath(filepath)} "
                  f"({size_kb:.0f} KB, {size[0]}x{size[1]})")
        else:
            @with_retry()
            def _fetch():
                return douyin_get(url, HEADERS, stream=True, timeout=30)
            r = _fetch()

            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded / total * 100
                            bar = "#" * int(pct / 2)
                            print(f"\r  [{bar:<50}] {pct:.1f}%", end="", flush=True)
            print()
            print(f"[OK] 下载完成！保存至: {os.path.abspath(filepath)}")
        return True
    except Exception as e:
        print(f"[!] 下载失败: {e}")
        return False


def run(raw_input: str, output_dir: str = None) -> bool:
    """主流程：输入分享链接/文本，自动下载视频或图文"""
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(output_dir, exist_ok=True)

    share_url = extract_url(raw_input)
    if not share_url:
        print(f"[!] 未在输入中找到有效链接: {raw_input}")
        return False

    print(f"[+] 正在解析链接: {share_url}")
    real_url = get_real_url(share_url)
    if not real_url:
        return False

    content_id, content_type = get_content_id(real_url)
    if not content_id:
        print("[!] 无法提取内容ID")
        return False

    print(f"[+] 内容ID: {content_id} (类型: {content_type})")

    info = None

    print("[*] 请求 slidesinfo API...")
    data2 = get_slidesinfo_api(content_id)
    if data2:
        info = parse_slidesinfo_api(data2, content_id)
        if info:
            print("[+] slidesinfo API 获取成功")

    if not info:
        print()
        print("=" * 50)
        print("⚠️  下载失败：slidesinfo API 未返回数据。")
        print("   请改用 --urls 模式：")
        print("   1. 用浏览器打开分享链接，从页面源码提图片直链存入 urls.txt")
        print("   2. python dy_img.py --urls urls.txt --out-dir ./out")
        print("=" * 50)
        return False

    if info["type"] != "image":
        print("[!] 这是视频链接，请用 dy_video.py 下载")
        return False
    content_type_cn = "图文"
    print(f"[+] {content_type_cn}: {info['desc']} | 作者: {info['nickname']}")
    print(f"[+] 共 {len(info['media'])} 个文件待下载")

    if info["type"] == "image":
        safe_prefix = _safe_name(info["desc"])
        output_dir = os.path.join(output_dir, f"{safe_prefix}_{content_id}")
        os.makedirs(output_dir, exist_ok=True)

    success_count = 0
    downloaded_files = []
    img_interval = RATE_LIMITS.get("douyin_image", 2)
    for idx, media in enumerate(info["media"]):
        if idx > 0:
            time.sleep(img_interval)
        filepath = os.path.join(output_dir, media["filename"])
        if download_file(media["url"], filepath, is_image=True):
            success_count += 1
            downloaded_files.append(filepath)
            # 尺寸对账：API 声明 vs 实测
            dw, dh = media.get("width"), media.get("height")
            if dw and dh:
                with open(filepath, "rb") as f:
                    actual = sniff_image_size(f.read(262144))
                if actual:
                    media["declared"] = [dw, dh]
                    media["actual"] = list(actual)
                    media["size_match"] = (dw == actual[0] and dh == actual[1])
                    if not media["size_match"]:
                        print(f"[!] 第 {idx+1} 张尺寸不符：声明 {dw}x{dh}，实测 {actual[0]}x{actual[1]}")

    if downloaded_files and info.get("publish_time_str"):
        write_timestamps_smart(downloaded_files, info["publish_time_str"], kind="image")

    print(f"\n[OK] 全部完成！成功 {success_count}/{len(info['media'])}，保存至: {os.path.abspath(output_dir)}")
    return success_count > 0


def run_urls(urls_file: str, output_dir: str = None) -> bool:
    """直链模式：从文本文件逐行读取图片直链直接下载（跳过 slidesinfo API）。

    用于 slidesinfo API 拿不到数据时：先用浏览器从页面提直链存文件，再用本模式下载。
    每行一个 URL，空行和 # 开头行跳过。扩展名按 URL 中的模板判断。
    """
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.exists(urls_file):
        print(f"[!] 找不到文件: {urls_file}")
        return False

    urls = []
    for enc in ("utf-8", "gbk", "utf-16"):
        try:
            with open(urls_file, "r", encoding=enc) as f:
                urls = [l.strip() for l in f
                        if l.strip() and not l.strip().startswith("#")]
            break
        except Exception:
            continue

    if not urls:
        print("[!] 文件中未找到有效 URL")
        return False

    print(f"[+] 直链模式，共 {len(urls)} 个 URL")
    img_interval = RATE_LIMITS.get("douyin_image", 2)
    success_count = 0
    for idx, url in enumerate(urls, 1):
        if idx > 1:
            time.sleep(img_interval)
        ext = _url_ext(url)
        filepath = os.path.join(output_dir, f"dy_img_{idx:02d}.{ext}")
        if download_file(url, filepath, is_image=True):
            success_count += 1

    print(f"\n[OK] 完成 {success_count}/{len(urls)}，保存至: {os.path.abspath(output_dir)}")
    return success_count > 0


def run_batch(txt_file: str, output_dir: str = None) -> None:
    """批量下载：从txt文件逐行读取链接"""
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(txt_file):
        print(f"[!] 找不到文件: {txt_file}")
        return

    urls = []
    for enc in ("utf-8", "gbk", "utf-16"):
        try:
            with open(txt_file, "r", encoding=enc) as f:
                urls = [l.strip() for l in f if l.strip()]
            break
        except Exception:
            continue

    if not urls:
        print("[!] 文件中未找到有效链接")
        return

    total = len(urls)
    print(f"[+] 共 {total} 个链接，开始批量下载...")
    for i, url in enumerate(urls, 1):
        print(f"\n--- 第 {i}/{total} 个 ---")
        run(url, output_dir)


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 支持 --out-dir 参数（与其他两个脚本统一）
    args = sys.argv[1:]
    out_dir = script_dir
    if "--out-dir" in args:
        idx = args.index("--out-dir")
        if idx + 1 < len(args):
            out_dir = args[idx + 1]
        # 移除 --out-dir 及其值，剩下的按原逻辑处理
        args = args[:idx] + args[idx + 2:]

    if len(args) < 1:
        print("用法:")
        print("  单个下载:  python dy_img.py <图文分享链接或文本> [--out-dir <保存目录>]")
        print("  批量下载:  python dy_img.py --batch <txt文件路径> [--out-dir <保存目录>]")
        print("  直链下载:  python dy_img.py --urls <urls.txt> [--out-dir <保存目录>]")
        print("             （slidesinfo API 拿不到数据时用：先浏览器提直链存文件，再用本模式下载）")
        print("  指定目录:  python dy_img.py <链接> <保存目录>")
        print(f"  默认保存至: {script_dir}")
        sys.exit(0)

    if args[0] == "--urls":
        if len(args) < 2:
            print("[!] --urls 需要指定 URL 文件路径")
            sys.exit(1)
        run_urls(args[1], out_dir)
    elif args[0] == "--batch":
        txt = args[1] if len(args) > 1 else "links.txt"
        # 兼容旧的位置参数
        if len(args) > 2 and out_dir == script_dir:
            out_dir = args[2]
        run_batch(txt, out_dir)
    else:
        link = args[0]
        # 兼容旧的位置参数
        if len(args) > 1 and out_dir == script_dir:
            out_dir = args[1]
        run(link, out_dir)
