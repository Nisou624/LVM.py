import logging
import fcntl
import time
from main_script import is_filesystem_busy, unmount_filesystem, append_filesystem, remount_filesystem

lock_file_path = "/tmp/extension_lock.lock"
file_systems_to_extend_path = "/tmp/filesystems_to_extend.txt"

def unlock_lock_file():
    """
    Release the lock file.
    
    Args:
        None
        
    Returns:
        None
    """
    try: # Release the lock file if it's acquired by this process (if it exists)
        with open(lock_file_path, 'w') as lock_file:
            fcntl.lockf(lock_file, fcntl.LOCK_UN)
        logging.info("Treatement script : Lock file released.")
    except Exception as e: # Log the error if the lock file is not acquired by this process
        logging.error(f"Treatement script : Error releasing lock file: {e}")

def acquire_lock():
    """
    Acquire the lock file.
    
    Args:
        None
        
    Returns:
        bool: True if the lock file is acquired, False otherwise.
    """
    try: # Acquire the lock file if it's not already in use by another process (if it exists)
        with open(lock_file_path, 'w') as lock_file:
            fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True # Return True if the lock file is acquired
    except BlockingIOError: # Log a warning if the lock file is already in use by another process
        logging.warning("Treatement script : Lock file is already in use. Exiting.")
        return False
    except Exception as e: # Log the error if the lock file is not acquired
        logging.error(f"Treatement script : Error acquiring lock file: {e}")
        return False

def process_filesystems(file_path):
    """
    Process the filesystems listed in the file at the given file path.

    Args:
        file_path (str): The path to the file containing the filesystem information.

    Returns:
        None
    """
    with open(file_path, "r+") as extension_file: # Open the file in read/write mode to be able to read and write to it
        lines = extension_file.readlines() # Read the filesystem information from the file
        extension_file.seek(0) # Go back to the beginning of the file
        extension_file.truncate() # Clear the file

        processed_filesystems = 0
        for line in lines: # Process each filesystem listed in the file
            lv_name, filesystem_type, mount_point = line.strip().split(',') # Get the filesystem information from the line
            if is_filesystem_busy(mount_point): # Check if the filesystem is in use
                logging.warning(f"Treatement script : Filesystem at {mount_point} is in use. Skipping unmount.")
                extension_file.write(line)  # Write back the line as it's not processed
            elif unmount_filesystem(mount_point):
                # Resize and remount the filesystem
                if not append_filesystem(lv_name, filesystem_type, mount_point):
                    logging.critical(f"Treatement script : No possible way to append storage for filesystem at {mount_point}. Deleting from file.")
                    remount_filesystem(lv_name, mount_point)
                    continue # Skip the filesystem if there is no possible way to append storage
                remount_filesystem(lv_name, mount_point)
                processed_filesystems += 1
                if processed_filesystems % 5 == 0:
                    # Release the lock every 5 processed filesystems and acquire it again
                    unlock_lock_file()
                    # Wait for a short period to allow other processes to acquire the lock
                    time.sleep(5)
                    if not acquire_lock():
                        break
            else: # Log an error if the filesystem cannot be unmounted
                logging.error(f"Treatement script : Error handling filesystem at {mount_point}.")
                extension_file.write(line)  # Write back the line as it's not processed


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
                        break  # Exit the loop if there are no more filesystems
                    
                # Process filesystems
                process_filesystems(file_systems_to_extend_path)

        else:
            logging.warning("Treatement script : Another instance (possibly the main script) is already running. Exiting.")
    except Exception as e:
        logging.error(f"Treatement script : An unexpected error occurred: {e}")
    finally:
        # Make sure to unlock the lock file in case of an exception
        unlock_lock_file()
        logging.info("Treatement script : Exiting.")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s] %(levelname)s : %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filename=f'logs/treatment_script.log'
    )
    main()
