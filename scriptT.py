import subprocess
import logging
from datetime import datetime
import threading
import queue
import time

date = datetime.now().strftime('%Y-%m-%d %H:%M')

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s : %(message)s",
    datefmt="%H:%M:%S",
    filename=f'logs/{date}.log'
)

# Queue to communicate between the main thread and the background thread
extension_queue = queue.Queue()

class VG:
    def __init__(self, vg_name, num_pvs, num_lvs, num_sn, attributes, vsize, vfree):
        self.vg_name = vg_name
        self.num_pvs = num_pvs
        self.num_lvs = num_lvs
        self.num_sn = num_sn
        self.attributes = attributes
        self.vsize = float(vsize.replace(',', '.').rstrip('g'))
        self.vfree = float(vfree.replace(',', '.').rstrip('g'))

class LV:
    def __init__(self, lv_name, lv_size, vg_name):
        self.lv_name = lv_name
        self.lv_size = float(lv_size.replace(',', '.').rstrip('g'))
        self.vg_name = vg_name

class PV:
    def __init__(self, pv_name, vg_name, pv_size, pv_free):
        self.pv_name = pv_name
        self.vg_name = vg_name
        self.pv_size = float(pv_size.replace(',', '.').rstrip('g')) if pv_size and ',' in pv_size else float(
            pv_size.rstrip('g'))
        self.pv_free = float(pv_free.replace(',', '.').rstrip('g')) if pv_free and ',' in pv_free else float(
            pv_free.rstrip('g'))

def parse_vgs_output(output):
    lines = output.decode("utf-8").splitlines()
    vgs = []
    for line in lines[0:]:
        values = line.split()
        vg = VG(
            vg_name=values[0],
            num_pvs=int(values[1]),
            num_lvs=int(values[2]),
            num_sn=int(values[3]),
            attributes=values[4],
            vsize=values[5],
            vfree=values[6]
        )
        vgs.append(vg)
    return vgs

def parse_pvs_output(output):
    lines = output.decode("utf-8").splitlines()
    pvs = []
    for line in lines[0:]:
        values = line.split()
        if len(values) < 4:
            values.insert(1, '')
        pv = PV(
            pv_name=values[0],
            vg_name=values[1],
            pv_size=values[2],
            pv_free=values[3]
        )
        pvs.append(pv)
    return pvs

def parse_lvs_output(output):
    lines = output.decode("utf-8").splitlines()
    lvs = []
    for line in lines[0:]:
        values = line.split()
        lv = LV(
            lv_name=values[0],
            lv_size=values[1],
            vg_name=values[2]
        )
        lvs.append(lv)
    return lvs

def get_writing_speed(device, interval=1, count=2):
    try:
        command = ["iostat", "-d", "-k", "-x", "-y", device, str(interval), str(count)]
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
        lines = output.splitlines()

        writing_speed = float(lines[-1].split()[7])
        return writing_speed
    except subprocess.CalledProcessError as e:
        logging.error(f"Error retrieving writing speed for {device}: {e}")
        return None

def calculate_and_sort_filesystems(file_systems):
    for fs in file_systems:
        fs["writing_speed"] = get_writing_speed(fs["device"])

    sorted_file_systems = sorted(file_systems, key=lambda fs: fs.get("writing_speed", 0), reverse=True)
    return sorted_file_systems

def extendLV(lvName, Size="1G") -> None:
    c = subprocess.run(["sudo", "lvextend", "-L", Size, f"sudo lvextend -L +1G /dev/mapper/{lvName}"],
                       capture_output=True, text=True)
    if c.returncode != 0:
        if extendVG(lvName, Size):
            extendLV(lvName, Size)
    else:
        logging.info(c.stdout)

def extendVG(lvName, Size):
    selected_pvs = [pv for pv in pvs if pv.vg_name == ""]
    if len(selected_pvs) != 0:
        selected_pvs = sorted(selected_pvs, key=lambda pv: pv.pv_size)
        chosen_pvs = [pv for pv in selected_pvs if pv.pv_size == Size]
        if len(chosen_pvs) != 0:
            elu = chosen_pvs[0]
        else:
            while Size > 0:
                elu.append(chosen_pvs[0])
                subprocess.run(["sudo", "vgextend", {lvName.split("-")[0]}, chosen_pvs[0].pv_name])
                Size -= chosen_pvs[0]
                chosen_pvs.pop(0)
        return True
    else:
        logging.CRITICAL("There's no available physical volumes for extending.")
        return False

def is_filesystem_busy(mount_point):
    try:
        subprocess.run(["fuser", "-m", mount_point], check=True)
        return False
    except subprocess.CalledProcessError:
        return True

def unmount_filesystem(mount_point):
    if is_filesystem_busy(mount_point):
        logging.warning(f"Filesystem at {mount_point} is in use. Skipping unmount.")
        return False

    try:
        subprocess.run(["sudo", "umount", mount_point], check=True)
        logging.info(f"Unmounted filesystem at {mount_point}.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error unmounting filesystem at {mount_point}: {e}")
        return False

def resize_filesystem(lv_name, filesystem_type, mount_point):
    extendLV(lv_name)  # Extend the LV by 1GB using the 'lvextend' command

    # Resize the filesystem based on the filesystem type
    if "/xfs" in filesystem_type:
        c = subprocess.run(["sudo", "xfs_growfs", mount_point], capture_output=True, text=True)
    else:
        c = subprocess.run(["sudo", "resize2fs", "/dev/mapper/" + lv_name], capture_output=True, text=True)

    if c.returncode != 0:
        logging.error(f"Error resizing filesystem at {mount_point}: {c.stderr}")
    else:
        logging.info(f"Resized filesystem at {mount_point}.")

    return c.returncode == 0

def remount_filesystem(lv_name, mount_point):
    subprocess.call(["sudo", "mount", "/dev/mapper/" + lv_name, mount_point])

def update_filesystems():
    output = subprocess.check_output(["sudo", "df", "-H"]).decode("utf-8")

    # Filter the output to show only lines containing '/dev/mapper'
    filtered_output = [line for line in output.splitlines() if '/dev/mapper' in line]

    # Define a list to store the parsed objects (in this case, dictionaries)
    parsed_objects = []

    # Iterate through the filtered output and parse each line
    for line in filtered_output:
        fields = line.split()  # Split the line into fields using whitespace as the delimiter
        if len(fields) >= 6:
            filesystem, size, used, available, use_percent, mount_point = fields
            # Create a dictionary to store the information for each line
            disk_info = {
                "Filesystem": filesystem,
                "Size": size,
                "Used": used,
                "Available": available,
                "Use%": int(use_percent.rstrip('%')),
                "Mount Point": mount_point,
            }
            parsed_objects.append(disk_info)

    # Now you have a list of dictionaries where each dictionary represents the parsed information for a line
    for obj in parsed_objects:
        if obj["Use%"] > 80:
            lv_name = obj["Filesystem"].split("/")[-1]  # Extract the LV name from the filesystem path
            mount_point = obj["Mount Point"]

            # Unmount the filesystem gracefully
            if is_filesystem_busy(mount_point):
                logging.warning(f"Filesystem at {mount_point} is in use. Skipping unmount.")
            elif unmount_filesystem(mount_point):
                # Resize and remount the filesystem
                if resize_filesystem(lv_name, obj["Filesystem"], mount_point):
                    remount_filesystem(lv_name, mount_point)
                else:
                    logging.error(f"Error handling filesystem at {mount_point}.")
            else:
                logging.error(f"Error handling filesystem at {mount_point}.")

def main_thread():
    while True:
        # Run the main script
        update_filesystems()

        # Check if there are busy filesystems that need extension
        for fs in sorted_file_systems:
            if fs["Use%"] > 80 and is_filesystem_busy(fs["Mount Point"]):
                if  not any(q_fs["Mount Point"] == mount_point for q_fs in list(extension_queue.queue)):
                    # Add the filesystem to the extension queue
                    extension_queue.put(fs)

        # Sleep for one hour (adjust as needed)
        time.sleep(3600)

def background_thread():
    while True:
        try:
            # Try to get a filesystem from the extension queue
            fs = extension_queue.get(timeout=1)

            # Check and extend the filesystem
            if not is_filesystem_busy(fs["Mount Point"]):
                lv_name = fs["Filesystem"].split("/")[-1]
                mount_point = fs["Mount Point"]

                # Unmount the filesystem gracefully
                if unmount_filesystem(mount_point):
                    # Resize and remount the filesystem
                    if resize_filesystem(lv_name, fs["Filesystem"], mount_point):
                        remount_filesystem(lv_name, mount_point)

        except queue.Empty:
            pass  # No items in the queue

        # Sleep for a short interval (adjust as needed)
        time.sleep(1)

if __name__ == "__main__":
    # Your existing main script code here
    # Example usage:
    file_systems = [
        {"name": "DB", "device": "/dev/sda1", "mount_point": "/mnt/db"},
        # Add more filesystems as needed
    ]

    pvs = parse_pvs_output(subprocess.check_output(["sudo", "pvs", "--units", "g", "--separator", ",", "--noheadings", "-o",  "pv_name,vg_name,pv_size,pv_free"]))
    sorted_file_systems = calculate_and_sort_filesystems(file_systems)

    busy_filesystems = []  # Define this variable as needed

    # Iterate through the sorted list of filesystems and perform necessary actions
    for fs in sorted_file_systems:
        if fs["Use%"] > 80:
            lv_name = fs["Filesystem"].split("/")[-1]  # Extract the LV name from the filesystem path
            mount_point = fs["Mount Point"]

            # Unmount the filesystem gracefully
            if mount_point in busy_filesystems:
                logging.warning(f"Filesystem at {mount_point} cannot be unmounted at the moment. Skipping unmount.")
            elif unmount_filesystem(mount_point):
                # Resize and remount the filesystem
                if resize_filesystem(lv_name, fs["Filesystem"], mount_point):
                    remount_filesystem(lv_name, mount_point)
                else:
                    busy_filesystems.append(mount_point)
            else:
                busy_filesystems.append(mount_point)

    # Sort the list of blocked filesystems based on predicted need for extension
    busy_filesystems = calculate_and_sort_filesystems(busy_filesystems)

    # Print the sorted list of blocked filesystems
    print("Sorted list of blocked filesystems based on predicted need for extension:")
    for fs in busy_filesystems:
        print(f"{fs['name']} - Writing Speed: {fs.get('writing_speed', 'N/A')} KB/s")

    # Create and start the main thread
    main_thread = threading.Thread(target=main_thread)
    main_thread.start()

    # Create and start the background thread
    background_thread = threading.Thread(target=background_thread)
    background_thread.start()
