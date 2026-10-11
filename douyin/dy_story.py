#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抖音日常视频原画下载器（视频专用）。

原理：
  App 保存的日常视频元数据（Keys:Comment）藏着原始 URI（vid:v0d00/v0300...）
  → 取 URI 部分调 play API（ratio=default，免登录）
  → 302 拿 CDN 直链 → 下载源文件

域名：www.douyin.com 主，aweme.snssdk.com 备。

用法：
  python dy_story.py --file 保存的日常视频.mp4 --out-dir ./out
  python dy_story.py --uri v0300fg10000db1pc27og65sdjv9s7m0 --out-dir ./out
"""
import sys
import os
import re
import subprocess
import shutil
import hashlib

# 接入公共模块（仓库内运行时用）；单文件分发时缺 common/ 则用内置默认值
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from common.headers import DOUYIN as COMMON_HEADERS
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

try:
    import requests
except ImportError:
    print("[!] 缺少 requests 库，请执行：pip install requests")
    sys.exit(1)

EXIFTOOL = shutil.which("exiftool") or os.path.expanduser(
    "~/workspace/tools/Image-ExifTool-13.59/exiftool")

PLAY_DOMAINS = [
    "https://www.douyin.com",
    "https://aweme.snssdk.com",
]


def extract_uri_from_file(path: str) -> str | None:
    """从保存的视频元数据提取视频 URI（v0d00/v0300 双链路）"""
    if not os.path.exists(EXIFTOOL):
        print("[!] 找不到 exiftool，无法读取元数据")
        return None
    try:
        out = subprocess.run(
            [EXIFTOOL, "-s", "-s", "-s", "-Comment", path],
            capture_output=True, text=True, timeout=30).stdout
    except Exception as e:
        print(f"[!] exiftool 读取失败: {e}")
        return None
    m = re.search(r"vid:(v0d00[a-zA-Z0-9]+|v0300[a-zA-Z0-9]+)", out)
    if m:
        return m.group(1)
    # 兜底：全文搜双前缀
    m = re.search(r"v0d00[a-zA-Z0-9]{20,40}|v0300[a-zA-Z0-9]{20,40}", out)
    return m.group(0) if m else None


def resolve_cdn_url(uri: str) -> str | None:
    """调 play API 取 302 CDN 直链（免登录）"""
    for domain in PLAY_DOMAINS:
        url = f"{domain}/aweme/v1/play/?video_id={uri}&ratio=default&line=0"
        try:
            r = requests.get(url, headers=HEADERS,
                             allow_redirects=False, timeout=30)
            if r.status_code == 302 and r.headers.get("Location"):
                cdn = r.headers["Location"]
                # 原画校验：桶名 tos-cn-v-（转码在 tos-cn-ve-），无 br= 参数
                if "tos-cn-ve-" in cdn or "br=" in cdn:
                    print(f"[!] {domain} 返回的不是原画，换域名重试")
                    continue
                print(f"[+] {domain} 拿到原画直链")
                return cdn
            print(f"[!] {domain} 未返回 302（{r.status_code}），换域名重试")
        except Exception as e:
            print(f"[!] {domain} 请求失败（{e}），换域名重试")
    return None


def download(url: str, filepath: str) -> bool:
    """流式下载 + Content-Length 对账"""
    tmp = filepath + ".tmp"
    try:
        r = requests.get(url, headers=HEADERS, stream=True, timeout=60)
        r.raise_for_status()
        expected = int(r.headers.get("Content-Length", 0))
        md5 = hashlib.md5()
        downloaded = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    md5.update(chunk)
                    downloaded += len(chunk)
        if expected and downloaded != expected:
            os.remove(tmp)
            print(f"[!] 下载截断（{downloaded}/{expected}），已删除残缺文件")
            return False
        os.rename(tmp, filepath)
        print(f"[+] {os.path.basename(filepath)} ({downloaded:,} 字节，MD5 {md5.hexdigest()[:8]}...)")
        return True
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        print(f"[!] 下载失败: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="抖音日常原画下载（从 App 保存的视频提取视频 URI）")
    parser.add_argument("--file", help="App 保存的日常视频文件路径")
    parser.add_argument("--uri", help="直接指定视频 URI（v0d00/v0300，跳过元数据提取）")
    parser.add_argument("--out-dir", default=".", help="保存目录")
    args = parser.parse_args()

    if args.uri:
        uri = args.uri
        # 兼容带 vid: 前缀的输入
        m = re.search(r"v0d00[a-zA-Z0-9]+|v0300[a-zA-Z0-9]+", uri)
        uri = m.group(0) if m else uri
    elif args.file:
        print("[1/3] 从视频元数据提取视频 URI...")
        uri = extract_uri_from_file(args.file)
        if not uri:
            print("[!] 未在元数据中找到视频 URI")
            sys.exit(1)
        print(f"[+] URI: {uri[:20]}...")
    else:
        parser.print_help()
        sys.exit(1)

    print("[2/3] 请求 play API 拿原画直链...")
    cdn_url = resolve_cdn_url(uri)
    if not cdn_url:
        print("[!] 所有域名均未返回原画直链")
        sys.exit(1)

    print("[3/3] 下载原画...")
    os.makedirs(args.out_dir, exist_ok=True)
    filename = f"douyin_daily_{uri[5:13]}.mp4"
    filepath = os.path.join(args.out_dir, filename)
    if not download(cdn_url, filepath):
        sys.exit(1)
    print(f"\n[OK] {filepath}")


if __name__ == "__main__":
    main()
