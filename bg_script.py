import logging
import fcntl
import time
from main_script import is_filesystem_busy, unmount_filesystem, append_filesystem, remount_filesystem

lock_file_path = "/tmp/extension_lock.lock"
file_systems_to_extend_path = "/tmp/filesystems_to_extend.txt"

def unlock_lock_file():
    try:
        with open(lock_file_path, 'w') as lock_file:
            fcntl.lockf(lock_file, fcntl.LOCK_UN)
        logging.info("Treatement script : Lock file released.")
    except Exception as e:
        logging.error(f"Treatement script : Error releasing lock file: {e}")

def acquire_lock():
    try:
        with open(lock_file_path, 'w') as lock_file:
            fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
    except BlockingIOError:
        logging.warning("Treatement script : Lock file is already in use. Exiting.")
        return False
    except Exception as e:
        logging.error(f"Treatement script : Error acquiring lock file: {e}")
        return False

def process_filesystems(file_path):
    with open(file_path, "r+") as extension_file:
        lines = extension_file.readlines()
        extension_file.seek(0)
        extension_file.truncate()

        processed_filesystems = 0
        for line in lines:
            lv_name, filesystem_type, mount_point = line.strip().split(',')
            # Unmount the filesystem gracefully
            if is_filesystem_busy(mount_point):
                logging.warning(f"Treatement script : Filesystem at {mount_point} is in use. Skipping unmount.")
                extension_file.write(line)  # Write back the line as it's not processed
            elif unmount_filesystem(mount_point):
                # Resize and remount the filesystem
                append_filesystem(lv_name, filesystem_type, mount_point)
                remount_filesystem(lv_name, mount_point)
                processed_filesystems += 1
                if processed_filesystems % 5 == 0:
                    # Release the lock every 5 processed filesystems and acquire it again
                    unlock_lock_file()
                    # Wait for a short period to allow other processes to acquire the lock
                    time.sleep(5)
                    if not acquire_lock():
                        break
            else:
                logging.error(f"Treatement script : Error handling filesystem at {mount_point}.")

def main():
    try:
        # Check if the lock file is already in use
        lock_acquired = acquire_lock()
        if lock_acquired:
            # The lock is acquired, proceed with treating filesystems
            while True:
                # Read filesystem information from the file
                with open(file_systems_to_extend_path, "r") as extension_file:
                    lines = extension_file.readlines()
                    if not lines:
                        logging.info("Treatement script : No more filesystems to extend. Exiting.")
                        break

                # Process filesystems
                process_filesystems(file_systems_to_extend_path)

                # Sleep for a while before checking the file again
                time.sleep(60)  # Sleep for 1 minute (adjust as needed)

        else:
            logging.warning("Treatement script : Another instance (possibly the main script) is already running. Exiting.")
    except Exception as e:
        logging.error(f"Treatement script : An unexpected error occurred: {e}")
    finally:
        # Make sure to unlock the lock file in case of an exception
        unlock_lock_file()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s] %(levelname)s : %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filename=f'logs/treatment_script.log'
    )
    main()
