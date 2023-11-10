import os
import time
import argparse

def write_data_to_file(file_path, size_in_bytes, write_speed_kBps):
    try:
        with open(file_path, 'wb') as file:
            start_time = time.time()
            while os.path.getsize(file_path) < size_in_bytes:
                data = b' ' * write_speed_kBps
                file.write(data)
                elapsed_time = time.time() - start_time
                if elapsed_time > 0:
                    current_speed = int(os.path.getsize(file_path) / elapsed_time / 1024)
                    print(f"Current write speed: {current_speed} kB/s")

    except Exception as e:
        print(f"Error: {e}")

parser = argparse.ArgumentParser(description="Simulate writing to a file with a specified speed and size.")
parser.add_argument("file_path", type=str, help="Path to the output file")
parser.add_argument("--size", type=int, default=1024 * 1024 * 1024, help="Size in bytes (default: 1 GB)")
parser.add_argument("--speed", type=int, default=1024, help="Write speed in kB/s (default: 1 MB/s)")

args = parser.parse_args()
write_data_to_file(args.file_path, args.size, args.speed)