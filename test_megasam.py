import os
import json
import argparse
import time

import requests
from dotenv import load_dotenv


def main():
    # Load environment variables from .env (in current working directory)
    load_dotenv()

    api_key = os.getenv("RUNPOD_API_KEY")
    endpoint_id = os.getenv("ENDPOINT_ID")

    if not api_key or not endpoint_id:
        raise SystemExit(
            "Missing RUNPOD_API_KEY or ENDPOINT_ID. "
            "Set them in your environment or in a .env file."
        )

    parser = argparse.ArgumentParser(description="Test MegaSaM RunPod serverless endpoint.")
    parser.add_argument(
        "--video-url",
        required=True,
        help="Public URL to an MP4 video (e.g. on S3/HTTPS).",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Target FPS for frame extraction (default: 30.0).",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
        help="Seconds between status polls (default: 10.0).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3600.0,
        help="Stop polling after this many seconds (default: 3600).",
    )
    args = parser.parse_args()

    base_url = f"https://api.runpod.ai/v2/{endpoint_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "input": {
            "video_url": args.video_url,
            "fps": args.fps,
        }
    }

    # 1) Submit async job via /run
    run_url = f"{base_url}/run"
    print(f"Submitting job to {run_url} ...")
    response = requests.post(run_url, headers=headers, json=payload, timeout=60)
    try:
        response.raise_for_status()
    except requests.HTTPError:
        print("Submit failed:")
        print("Status code:", response.status_code)
        print("Body:", response.text)
        raise

    run_data = response.json()
    job_id = run_data.get("id")
    if not job_id:
        raise SystemExit("No job id in response: " + json.dumps(run_data, indent=2))
    print(f"Job id: {job_id}")
    print(f"Initial status: {run_data.get('status', 'unknown')}")

    # 2) Poll /status until terminal state
    status_url = f"{base_url}/status/{job_id}"
    terminal_states = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}
    start = time.monotonic()

    while True:
        elapsed = time.monotonic() - start
        if elapsed >= args.timeout:
            raise SystemExit(f"Polling timed out after {args.timeout}s. Job id: {job_id}")

        time.sleep(args.poll_interval)
        resp = requests.get(status_url, headers=headers, timeout=60)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            print("Status request failed:", resp.status_code, resp.text)
            raise

        data = resp.json()
        status = data.get("status", "UNKNOWN")
        print(f"[{elapsed:.0f}s] status: {status}")

        if status not in terminal_states:
            continue

        # 3) Output result or error
        if status == "COMPLETED":
            output = data.get("output")
            if output is not None:
                if isinstance(output, dict) and output.get("error"):
                    print("Worker returned error:", output["error"])
                print("Output:")
                print(json.dumps(output, indent=2))
            else:
                print("Completed with no output:", json.dumps(data, indent=2))
            return

        # FAILED, CANCELLED, TIMED_OUT
        err = data.get("error") or data.get("output")
        print(f"Job ended with status {status}.")
        if err is not None:
            print("Error/details:", err if isinstance(err, str) else json.dumps(err, indent=2))
        else:
            print("Full response:", json.dumps(data, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()