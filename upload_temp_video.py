import argparse
import os

import requests


def upload_0x0(file_path: str) -> str:
    url = "https://0x0.st"
    with open(file_path, "rb") as f:
        resp = requests.post(url, files={"file": f}, timeout=600)
    resp.raise_for_status()
    return resp.text.strip()


def upload_tmpfiles(file_path: str) -> str:
    url = "https://tmpfiles.org/api/v1/upload"
    with open(file_path, "rb") as f:
        resp = requests.post(url, files={"file": f}, timeout=600)
    resp.raise_for_status()
    data = resp.json()
    # Typical shape: {"status":"ok","data":{"url":"https://tmpfiles.org/..."}}
    return (
        data.get("data", {}).get("url")
        or data.get("url")
        or data.get("link")
        or ""
    )


def main():
    parser = argparse.ArgumentParser(
        description="Upload a local MP4 to a temp file host and print its URL."
    )
    parser.add_argument("video_path", help="Path to local .mp4 file")
    parser.add_argument(
        "--service",
        choices=["0x0", "tmpfiles"],
        default="0x0",
        help="Temp host to use (default: 0x0)",
    )
    args = parser.parse_args()

    video_path = os.path.abspath(args.video_path)
    if not os.path.isfile(video_path):
        raise SystemExit(f"File not found: {video_path}")

    if args.service == "0x0":
        temp_url = upload_0x0(video_path)
    else:
        temp_url = upload_tmpfiles(video_path)

    if not temp_url:
        raise SystemExit("Upload appeared to succeed but no URL was returned.")

    print(temp_url)


if __name__ == "__main__":
    main()

