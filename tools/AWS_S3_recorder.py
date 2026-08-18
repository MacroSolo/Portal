import csv
import boto3
import cv2
from concurrent.futures import ThreadPoolExecutor
import io
from tools.global_vars import global_state


def open_s3_connection(credentials='/home/admin/Desktop/Merlin/credentials/s3-user_accessKeys.csv'):
    reader = csv.DictReader(open(credentials, encoding="utf-8-sig"))

    for row in reader:
        access_key = row['Access key ID']
        secret_key = row['Secret access key']
    s3_client = boto3.client('s3',
                             region_name='eu-central-1',
                             aws_access_key_id=access_key,
                             aws_secret_access_key=secret_key)
    return s3_client


def save_frame_series_s3(frames, label, s3_client, bucket, timestamp=0):

    if global_state["RECORDING"]:
        print("Recording is already in progress. Please wait until the current recording is finished.")
        return

    else:
        global_state["RECORDING"] = True
        frames_copy = frames.copy()

        def upload_frame(args):
            idx, frame = args
            success, buffer = cv2.imencode('.png', frame)
            if not success:
                print(f"Failed to encode frame {idx}")
                return

            key = f"{label}/{timestamp}_{idx}.png"
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=buffer.tobytes(),
                ContentType='image/png'
            )

        num_frames = len(frames_copy)
        optimal_workers = min(32, num_frames)

        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            executor.map(upload_frame, enumerate(frames_copy))

        global_state["RECORDING"] = False
        print(f"Saved {len(frames_copy)} frames to S3 bucket '{bucket}/{label}'")



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


