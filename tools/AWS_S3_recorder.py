import csv
import boto3
import cv2
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
from tools.global_vars import global_state


def open_s3_connection(config=None):
    """S3 client with AWS_S3_ACCESS_KEY_ID / AWS_S3_SECRET_ACCESS_KEY / AWS_REGION from config/secrets.env."""
    if config is None:
        from config import load_env
        config = load_env()
    key_id = config.get("AWS_S3_ACCESS_KEY_ID")
    secret = config.get("AWS_S3_SECRET_ACCESS_KEY")
    if not (key_id and secret):
        raise RuntimeError("AWS_S3_ACCESS_KEY_ID / AWS_S3_SECRET_ACCESS_KEY empty in config/secrets.env")
    return boto3.client('s3',
                        region_name=config.get("AWS_REGION") or "eu-central-1",
                        aws_access_key_id=key_id,
                        aws_secret_access_key=secret)


def save_frame_series_s3(frames, label, s3_client, bucket, timestamp=0):

    if global_state["RECORDING"]:
        print("Recording is already in progress. Please wait until the current recording is finished.")
        return

    global_state["RECORDING"] = True
    try:
        frames_copy = list(frames)
        if not frames_copy:
            print(f"No frames to save for '{label}' (camera buffer is empty)")
            return

        def upload_frame(args):
            idx, frame = args
            success, buffer = cv2.imencode('.png', frame)
            if not success:
                raise RuntimeError(f"Failed to encode frame {idx}")

            key = f"{label}/{timestamp}_{idx}.png"
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=buffer.tobytes(),
                ContentType='image/png'
            )
            return key

        optimal_workers = min(32, len(frames_copy))
        ok, failed = 0, 0
        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            futures = {executor.submit(upload_frame, item): item[0]
                       for item in enumerate(frames_copy)}
            for future in as_completed(futures):
                try:
                    future.result()
                    ok += 1
                except Exception as e:
                    failed += 1
                    print(f"S3 upload of frame {futures[future]} failed: {type(e).__name__}: {e}")

        print(f"Saved {ok}/{len(frames_copy)} frames to S3 bucket '{bucket}/{label}'"
              + (f", {failed} failed" if failed else ""))
    except Exception as e:
        print(f"S3 recording '{label}' failed: {type(e).__name__}: {e}")
    finally:
        global_state["RECORDING"] = False



def save_frame_series_s3_0(frames, label, s3_client, bucket, timestamp=0):
    """Save frames to S3 bucket in folder {label}/."""
    frames_copy = frames.copy()

    for idx, frame in enumerate(frames_copy):
        # Encode the frame as PNG in memory
        success, buffer = cv2.imencode('.png', frame)
        if not success:
            print(f"Failed to encode frame {idx}")
            continue

        # Generate the S3 object key
        key = f"{label}/{timestamp}_{idx}.png"

        # Upload the frame to S3
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=buffer.tobytes(),
            ContentType='image/png'
        )

    print(f"Saved {len(frames_copy)} frames to S3 bucket '{bucket}/{label}'")

if __name__ == "__main__":
    s3 = open_s3_connection()
    print(s3.list_buckets())


