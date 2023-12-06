import subprocess
import logging
import re
import os
from datetime import datetime
import fcntl

date = datetime.now().strftime('%Y-%m-%d %H:%M')

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s : %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=f'logs/{date}.log'
)



# Lock file path
lock_file_path = "/tmp/extension_lock.lock"
queue_file = "/tmp/filesystems_to_extend.txt"


if not os.path.exists(queue_file):
    with open(queue_file, 'w') as file:
        pass

if not os.path.exists(lock_file_path):
    with open(lock_file_path, 'w') as file:
        pass


# Function to check if the treatment script is running
def is_treatment_script_running():
    with open(lock_file_path, 'w') as lock_file:
        try:
            fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_acquired = True
        except IOError:
            lock_acquired = False

    return not lock_acquired


def add_to_file_if_not_exists(file_path, entry):
    with open(file_path, 'r') as file:
        lines = file.readlines()
        if entry not in lines:
            with open(file_path, 'a') as file:
                file.write(entry + '\n')


def convert_to_float(value):
    match = re.match(r'^([\d.,]+)([GMK]?)$', value, re.IGNORECASE)
    if match:
        number, suffix = match.groups()
        # Replace commas with periods and then convert to float
        number = number.replace(',', '.')
        multiplier = {'g': 1, 'm': 1e-3, 'k': 1e-6}.get(suffix.lower(), 1)
        return float(number) * multiplier
    else:
        # Check for 'k', 'm', or 'g' suffix separately
        if value.lower().endswith('k'):
            return float(value[:-1]) * 1e-6  # Convert kilobytes to gigabytes
        elif value.lower().endswith('m'):
            return float(value[:-1]) * 1e-3  # Convert megabytes to gigabytes
        elif value.lower().endswith('g'):
            return float(value[:-1])  # Already in gigabytes
        else:
            return float(value.replace(',', '.'))

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

        writing_speed = float(lines[4].split()[7].replace(',', '.'))
        return writing_speed
    except subprocess.CalledProcessError as e:
        logging.error(f"Error retrieving writing speed for {device}: {e}")
        return None


def calculate_and_sort_filesystems(file_systems):
    for fs in file_systems:
        fs["writing_speed"] = get_writing_speed(fs["Filesystem"])

    sorted_file_systems = sorted(file_systems, key=lambda fs: fs.get("writing_speed", 0), reverse=True)
    return sorted_file_systems


#todo : add taking space from LV that are not used aka: that doesn't have a fs linked to it / doesn't have a partition linked to it.
# for exmple : check in the parsed_objects if there's a LV that doesn't have a fs linked to it and take space from it.
# to see if a lv doesn't have a fs linked to it : check if the lv name is in the fs name
def extendLV(lvName, Size="1G") -> None:
    c = subprocess.run(["sudo", "lvextend", "-L", f"+{Size}", f"/dev/mapper/{lvName}"],
                       capture_output=True, text=True)
    if c.returncode != 0:
        if extendVG(lvName, Size):
            extendLV(lvName, Size)
        else:
            rstf = float(Size.rstrip('G'))  # remaining size to fetch
            potential_fs = [fs for fs in parsed_objects if (fs["Available"] - (get_writing_speed(fs["Filesystem"]) * 1024 * 1024 * 3600) > fs["Size"] * 0.8) and fs["Filesystem"].split("/")[-1] != lvName]
            for fs in potential_fs:
                if rstf <= 0:
                    break
                asfe = (fs["Size"] * 0.7) - fs["Used"]  # 0.8 - 0.1  we take the threshold and we leave 10% for security (arbitrary values) // asfe = available size for extension
                if not is_filesystem_busy(fs["Mount Point"]) and fs["Filesystem"].split("/")[-1] != lvName:
                    if rstf <= asfe:
                        unmount_filesystem(fs["Mount Point"])
                        reduce_filesystem(fs["Filesystem"].split("/")[-1], fs["Filesystem"], fs["Mount Point"], str(int(round(fs["Size"] -rstf))) + 'G')
                        remount_filesystem(fs["Filesystem"].split("/")[-1], fs["Mount Point"])
                        rstf -= rstf
                    else:
                        unmount_filesystem(fs["Mount Point"])
                        reduce_filesystem(lvName, fs["Filesystem"], fs["Mount Point"], str(asfe) + 'G')
                        remount_filesystem(lvName, fs["Mount Point"])
                        rstf -= asfe
            extendLV(lvName, Size)  # check the logic of this
            if c.returncode != 0:
                logging.critical("There's no available space for extending")
    else:
        logging.info(c.stdout)


def extendVG(lvName, Size):
    size_required = float(Size.rstrip('G'))
    selected_pvs = [pv for pv in pvs if pv.vg_name == ""]
    print(len(selected_pvs))
    if len(selected_pvs) != 0:
        print(selected_pvs)
        selected_pvs = sorted(selected_pvs, key=lambda pv: pv.pv_size)
        chosen_pvs = [pv for pv in selected_pvs if pv.pv_free == size_required]
        if len(chosen_pvs) > 1:
            elu = chosen_pvs[0]
        else:
            elu = []
            while size_required > 0:
                elu.append(chosen_pvs[0])
                subprocess.run(["sudo", "vgextend", lvName.split("-")[0], chosen_pvs[0].pv_name])
                size_required -= chosen_pvs[0].pv_size
                chosen_pvs.pop(0)
            return True
    else:
        logging.critical("There's no available physical volumes for extending.")
        return False

'''
def is_filesystem_busy(mount_point):
    try:
        result = subprocess.run(["fuser", "-m", mount_point], capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        if output:
            logging.debug(f"Filesystem at {mount_point} is busy. Processes: {output}")
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        logging.debug(f"Error checking filesystem usage at {mount_point}: {e}")
        return True
'''

def is_filesystem_busy(mount_point):
    try:
        # The 'lsof' command lists the processes that are using the filesystem.
        # If no processes are using it, 'lsof' will return a non-zero exit code.
        subprocess.run(["lsof", "+D", mount_point], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

        
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


def append_filesystem(lv_name, filesystem_type, mount_point):
    extendLV(lv_name)  # Extend the LV by 1GB using the 'lvextend' command

    # Run e2fsck before resizing
    check_result = subprocess.run(["sudo", "e2fsck", "-f", "-y", f"/dev/mapper/{lv_name}"], capture_output=True, text=True)
    if check_result.returncode != 0:
        logging.error(f"Error running e2fsck: {check_result.stderr}")
        return False

    # Resize the filesystem based on the filesystem type
    if "/xfs" in filesystem_type:
        resize_result = subprocess.run(["sudo", "xfs_growfs", mount_point], capture_output=True, text=True)
    else:
        resize_result = subprocess.run(["sudo", "resize2fs", f"/dev/mapper/{lv_name}"], capture_output=True, text=True)

    if resize_result.returncode != 0:
        logging.error(f"Error resizing filesystem at {mount_point}: {resize_result.stderr}")
    else:
        logging.info(f"Resized filesystem at {mount_point}.")

    return resize_result.returncode == 0

"""
todo :
- reduce the LV (size passed as param)
- resize the FS

steps:
    -lvreduce
    -resize2fs with precise size
"""
def reduce_filesystem(lv_name, filesystem_type, mount_point, new_size="1G"):

    # Run e2fsck before resizing
    check_result = subprocess.run(["sudo", "e2fsck", "-f", "-y", f"/dev/mapper/{lv_name}"], capture_output=True, text=True)
    if check_result.returncode != 0:
        logging.error(f"Error running e2fsck: {check_result.stderr}")
        return False

    # Reduce the FS before
    subprocess.run(["sudo", "resize2fs", f"/dev/mapper/{lv_name}", new_size], capture_output=True, text=True)
    
    # Reduce the LV size using the 'lvreduce' command
    try:
        lvreduce_result = subprocess.run(["sudo", "lvreduce", "-f", "-L", new_size, f"/dev/mapper/{lv_name}"], capture_output=True, text=True, check=True)
        lvreduce_output = lvreduce_result.stdout.strip().splitlines()[-1]  # Extract the last line of the stdout
        logging.info(lvreduce_output)  # Log the last line as info
    except subprocess.CalledProcessError as e:
        logging.error(f"Error reducing logical volume: {e.stderr}")

    # Resize the filesystem based on the filesystem type
    if "/xfs" in filesystem_type:
        resize_result = subprocess.run(["sudo", "xfs_growfs", mount_point], capture_output=True, text=True)
    else:
        resize_result = subprocess.run(["sudo", "resize2fs", f"/dev/mapper/{lv_name}"], capture_output=True, text=True)

    if resize_result.returncode != 0:
        logging.error(f"Error resizing filesystem at {mount_point}: {resize_result.stderr}")
    else:
        logging.info(f"Resized filesystem at {mount_point}.")

    return resize_result.returncode == 0


def remount_filesystem(lv_name, mount_point):
    subprocess.call(["sudo", "mount", "/dev/mapper/" + lv_name, mount_point])

pvs = parse_pvs_output(subprocess.check_output(["sudo", "pvs", "--noheadings", "-o", "pv_name,vg_name,pv_size,pv_free", "--units", "g"]))
# Run the df command and capture its output
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
            "Size": convert_to_float(size),
            "Used": convert_to_float(used),
            "Available": convert_to_float(available),
            "Use%": int(use_percent.rstrip('%')),
            "Mount Point": mount_point,
        }
        parsed_objects.append(disk_info)


sorted_file_systems = calculate_and_sort_filesystems(parsed_objects)

# Now you have a list of dictionaries where each dictionary represents the parsed information for a line
for obj in sorted_file_systems:
    if obj["Use%"] >= 80:
        lv_name = obj["Filesystem"].split("/")[-1]  # Extract the LV name from the filesystem path
        mount_point = obj["Mount Point"]

        # Unmount the filesystem gracefully
        if is_filesystem_busy(mount_point):
            if not is_treatment_script_running():
                add_to_file_if_not_exists(queue_file, f"{lv_name},{obj['Filesystem']},{mount_point}")
                logging.info(f"Filesystem at {mount_point} is in use. added to the queue")
            else:
                logging.warning(f"Filesystem at {mount_point} is in use. Skipping unmount.")
        elif unmount_filesystem(mount_point):
            # Resize and remount the filesystem
            append_filesystem(lv_name, obj["Filesystem"], mount_point)
            remount_filesystem(lv_name, mount_point)
        else:
            logging.error(f"Error handling filesystem at {mount_point}.")

if not is_treatment_script_running():
    subprocess.Popen(["python3", "bg_script.py"])
