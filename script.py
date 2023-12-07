import subprocess
import logging
import os
from datetime import datetime
from time import sleep


# Check if the logs directory exists
if not os.path.exists('logs'):
    # If not, create it
    os.makedirs('logs')

date = datetime.now().strftime('%Y-%m-%d %H:%M')

## Logging configuration ##
logging.basicConfig( 
    level=logging.DEBUG, # Set the logging level to DEBUG to log all messages
    format="[%(asctime)s] %(levelname)s : %(message)s", # Set the format of the log messages to include the date and time of the message and the level of the message
    datefmt="%Y-%m-%d %H:%M:%S", # Set the format of the date and time of the message to YYYY-MM-DD HH:MM:SS
    filename=f'logs/{date}.log' # Set the name of the log file to include the date and time of the message
)


def convert_to_bytes(size):
    """
    Convert a size string to bytes.
    
    Args:
        size (str): The size string to convert.
        
    Returns:
        int: The size in bytes.
    """
    size_str = size[:-1].replace(',', '.')
    unit = size[-1]
    if unit == 'G':
        return float(size_str) * 1024 * 1024 * 1024
    elif unit == 'M':
        return float(size_str) * 1024 * 1024
    elif unit == 'K':
        return float(size_str) * 1024
    else:
        return float(size_str)

def getUnit(size_in_bytes, with_unit=True):
    """
    Get the size in the most appropriate unit.
    
    Args:
        size_in_bytes (int): The size in bytes.
        with_unit (bool, optional): Whether to include the unit in the output. Defaults to True.
        
    Returns:
        str: The size in the most appropriate unit.
    """
    if size_in_bytes >= 1024 * 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024 * 1024)}G" if with_unit else size_in_bytes / (1024 * 1024 * 1024)
    elif size_in_bytes >= 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024)}M" if with_unit else size_in_bytes / (1024 * 1024)
    elif size_in_bytes >= 1024:
        return f"{size_in_bytes / 1024}K" if with_unit else size_in_bytes / 1024
    else:
        return f"{size_in_bytes}B" if with_unit else size_in_bytes


def is_potential_filesystem(fs, rstf, lvName):
    """
    check if the filesystem is not busy:
        1 -  if the filesystem is not busy
        2 -  if the filesystem has enough space to extend : available space - remaining space - (writing speed * 3600) > 80% of the filesystem size
        3 -  if the filesystem is not the filesystem of the LV to extend

    Args:
        fs (dict): filesystem to check
        rstf (int): remaining size to fetch
        lvName (str): name of the LV to extend
        
        Returns:
            bool: True if the filesystem is a potential filesystem to extend
    """
    return (not is_filesystem_busy(fs["Mount Point"])) and \
           (fs["Available"] - rstf - (get_writing_speed(fs["Filesystem"]) * 1024 * 3600) > fs["Size"] * 0.8) and \
           fs["Filesystem"].split("/")[-1] != lvName

def get_potential_filesystems(file_systems, rstf, lvName):
    """
    choose from a list of filesystems the ones that match certain criteria (see is_potential_filesystem)
    
    Args:
        file_systems (list): list of filesystems
        rstf (int): remaining size to fetch
        lvName (str): name of the LV to extend
        
        Returns:
            list: list of potential filesystems to extend
    """
    return [fs for fs in file_systems if is_potential_filesystem(fs, rstf, lvName)]

class VG:
    def __init__(self, vg_name, num_pvs, num_lvs, num_sn, attributes, vsize, vfree):
        self.vg_name = vg_name
        self.num_pvs = num_pvs
        self.num_lvs = num_lvs
        self.num_sn = num_sn
        self.attributes = attributes
        self.vsize = vsize
        self.vfree = vfree


class LV:
    def __init__(self, lv_name, lv_size, vg_name):
        self.lv_name = lv_name
        self.lv_size = lv_size
        self.vg_name = vg_name


class PV:
    def __init__(self, pv_name, vg_name, pv_size, pv_free):
        self.pv_name = pv_name
        self.vg_name = vg_name
        self.pv_size = pv_size
        self.pv_free = pv_free


def parse_vgs_output(output):
    lines = output.decode("utf-8").splitlines()
    vgs = []
    for line in lines[0:]:
        values = line.split()
        vg = VG(
            vg_name=values[0],
            num_pvs=int(values[1]),
            num_lvs=int(values[2]),
            num_sn=values[3],
            attributes=values[4],
            vsize=convert_to_bytes(values[5]),
            vfree=convert_to_bytes(values[6])
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
            pv_size=convert_to_bytes(values[2]),
            pv_free=convert_to_bytes(values[3])
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
            lv_size=convert_to_bytes(values[1]),
            vg_name=values[2]
        )
        lvs.append(lv)
    return lvs


def get_writing_speed(device, interval=1, count=2):
    """
    Get the writing speed of a device
    
    Args:
        device (str): device name
        interval (int, optional): interval between two checks. Defaults to 1.
        count (int, optional): number of checks. Defaults to 2.
        
        Returns:
            float: writing speed of the device
    """
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
    """
    calculate the writing speed of each filesystem and sort them by descending order

    Args:
        file_systems (list): list of filesystems

    Returns:
            list: sorted list of filesystems
    """
    for fs in file_systems:
        fs["writing_speed"] = get_writing_speed(fs["Filesystem"])

    sorted_file_systems = sorted(file_systems, key=lambda fs: fs.get("writing_speed", 0), reverse=True)
    return sorted_file_systems

def extendLV(lvName, Size="1G"):
    """
    Extends the logical volume (LV) with the specified name to the given size.

    Args:
        lvName (str): The name of the logical volume to extend.
        Size (str, optional): The size to extend the logical volume to. Defaults to "1G".

    Returns:
        bool: True if the logical volume was successfully extended, False otherwise.
    """
    c = subprocess.run(["sudo", "lvextend", "-L", f"+{getUnit(convert_to_bytes(Size))}", f"/dev/mapper/{lvName}"],
                       capture_output=True, text=True)
    if c.returncode != 0:
        if extendVG(lvName, Size):
            extendLV(lvName, Size)
        else:
            rstf = convert_to_bytes(Size)  # remaining size to fetch
            # Check if there are LVs without a linked filesystem
            unused_lvs = [lv for lv in lvs if f"{lv.vg_name}-{lv.lv_name}" not in [fs["Filesystem"].split("/")[-1] for fs in parsed_objects]]
            for lv in unused_lvs:
                if rstf <= 0 or len(unused_lvs) == 0:
                    break
                if round(getUnit(rstf, False)) < round(getUnit(lv.lv_size, False)): # if the remaining size is less than the size of the LV we reduce the LV by the remaining size
                    subprocess.run(["sudo", "lvreduce", "-L", f"-{getUnit(rstf)}", f"/dev/mapper/{lv.vg_name}-{lv.lv_name}"])
                    rstf -= rstf
                elif round(getUnit(rstf, False)) == round(getUnit(lv.lv_size, False)): # if the remaining size is equal to the size of the LV we remove the LV
                    subprocess.run(["sudo", "lvremove", "-f", f"/dev/mapper/{lv.vg_name}-{lv.lv_name}"])
                    extendLV(lvName)
                    rstf = 0
                    break
                else: # if the remaining size is greater than the size of the LV we reduce the LV by its size
                    subprocess.run(["sudo", "lvreduce", "-L", f"-{getUnit(lv.lv_size)}", f"/dev/mapper/{lv.vg_name}-{lv.lv_name}"])
                    rstf -= lv.lv_size
            if rstf != 0: # if there's still remaining size to fetch we check the filesystems
                potential_fs = get_potential_filesystems(parsed_objects, rstf, lvName)
                for fs in potential_fs: # we check the filesystems that match the criteria
                    if rstf <= 0: # if the remaining size is less than 0 we break the loop
                        break
                    asfe = (fs["Size"] * 0.7) - fs["Used"]  # 0.8 - 0.1  we take the threshold and we leave 10% for security (arbitrary values) // asfe = available size for extension
                    if not is_filesystem_busy(fs["Mount Point"]) and fs["Filesystem"].split("/")[-1] != lvName: # if the filesystem is not busy and it's not the filesystem of the LV to extend
                        if rstf <= asfe: # if the remaining size is less than the available size for extension we reduce the filesystem by the remaining size
                            unmount_filesystem(fs["Mount Point"])
                            reduce_filesystem(fs["Filesystem"].split("/")[-1], fs["Filesystem"], fs["Mount Point"], getUnit(round(fs["Size"] - rstf)))
                            remount_filesystem(fs["Filesystem"].split("/")[-1], fs["Mount Point"])
                            rstf -= rstf # rstf = 0
                        else: # if the remaining size is greater than the available size for extension we reduce the filesystem by its available size for extension
                            unmount_filesystem(fs["Mount Point"])
                            reduce_filesystem(lvName, fs["Filesystem"], fs["Mount Point"], getUnit(asfe))
                            remount_filesystem(lvName, fs["Mount Point"])
                            rstf -= asfe
                if rstf == 0: # if the remaining size is equal to 0 we extend the LV
                    extendLV(lvName, Size)
            
            if rstf != 0: # if there's still remaining size to fetch we log a critical error
                logging.critical(f"There's no available space for extending {lvName}.")
                return False
    else: # if the LV was successfully extended we log the output
        logging.info(c.stdout)
        return True


def extendVG(lvName, Size):
    """
    Extends the volume group (VG) with the specified name to the given size.
    
    Args:
        lvName (str): The name of the logical volume to extend.
        Size (str): The size to extend the logical volume to.
        
    Returns:
        bool: True if the volume group was successfully extended, False otherwise.
    """
    size_required = convert_to_bytes(Size)
    selected_pvs = [pv for pv in pvs if pv.vg_name == ""] # get the available physical volumes
    if len(selected_pvs) != 0: # if there are available physical volumes we sort them by ascending order and we choose the ones that match the size required
        selected_pvs = sorted(selected_pvs, key=lambda pv: pv.pv_size)
        chosen_pvs = [pv for pv in selected_pvs if pv.pv_free == size_required]
        if len(chosen_pvs) > 1: # if there are more than one physical volume that match the size required we choose the first one
            elu = chosen_pvs[0]
        else: # if there's only one physical volume that match the size required we choose it
            elu = []
            while size_required > 0:
                elu.append(chosen_pvs[0])
                subprocess.run(["sudo", "vgextend", lvName.split("-")[0], chosen_pvs[0].pv_name])
                size_required -= chosen_pvs[0].pv_size
                chosen_pvs.pop(0)
            return True
    else: # if there are no available physical volumes we log a critical error
        logging.critical(f"There's no available physical volumes for extending {lvName}.")
        return False


def is_filesystem_busy(mount_point):
    """
    Check if the filesystem at the given mount point is in use.
    
    Args:
        mount_point (str): The mount point of the filesystem.
        
    Returns:
        bool: True if the filesystem is in use, False otherwise.
    """
    sleep(1)  # Add a short delay to allow processes to be detected
    result = subprocess.run(f"sudo lsof {mount_point} 2>/dev/null", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout != b'' # if the stdout is not empty the filesystem is in use

        
def unmount_filesystem(mount_point):
    """
    Unmount the filesystem at the given mount point.
    
    Args:
        mount_point (str): The mount point of the filesystem.
        
    Returns:
        bool: True if the filesystem was successfully unmounted, False otherwise.
    """
    if is_filesystem_busy(mount_point): # if the filesystem is in use we log a warning
        logging.warning(f"Filesystem at {mount_point} is in use. Skipping unmount.")
        return False

    try: # if the filesystem is not in use we unmount it
        subprocess.run(["sudo", "umount", mount_point], check=True)
        logging.info(f"Unmounted filesystem at {mount_point}.")
        return True
    except subprocess.CalledProcessError as e: # if there's an error we log it
        logging.error(f"Error unmounting filesystem at {mount_point}: {e}")
        return False


def append_filesystem(lv_name, filesystem_type, mount_point):
    """
    Extend the filesystem at the given mount point.
    
    Args:
        lv_name (str): The name of the logical volume to extend.
        filesystem_type (str): The type of the filesystem.
        mount_point (str): The mount point of the filesystem.
        
    Returns:
        bool: True if the filesystem was successfully extended, False otherwise.
    """
    if extendLV(lv_name): # if the LV was successfully extended we resize the filesystem

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
    else:
        return False


def reduce_filesystem(lv_name, filesystem_type, mount_point, new_size="1G"):
    """
    Reduce the filesystem at the given mount point.
    
    Args:
        lv_name (str): The name of the logical volume to reduce.
        filesystem_type (str): The type of the filesystem.
        mount_point (str): The mount point of the filesystem.
        new_size (str, optional): The new size of the filesystem. Defaults to "1G".
        
    Returns:
        bool: True if the filesystem was successfully reduced, False otherwise.
    """

    # Run e2fsck before resizing
    check_result = subprocess.run(["sudo", "e2fsck", "-f", "-y", f"/dev/mapper/{lv_name}"], capture_output=True, text=True)
    if check_result.returncode != 0:# if there's an error we log it
        logging.error(f"Error running e2fsck: {check_result.stderr}")
        return False

    # Resize the filesystem based on the filesystem type
    subprocess.run(["sudo", "resize2fs", f"/dev/mapper/{lv_name}", new_size], capture_output=True, text=True)
    
    try: # if the filesystem is not in use we unmount it
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

    return resize_result.returncode == 0 # if the filesystem was successfully reduced we return True


def remount_filesystem(lv_name, mount_point):
    subprocess.call(["sudo", "mount", "/dev/mapper/" + lv_name, mount_point])

# Run the pvs and lvs commands and capture their output
pvs = parse_pvs_output(subprocess.check_output(["sudo", "pvs", "--noheadings", "-o", "pv_name,vg_name,pv_size,pv_free", "--units", "G"]))
lvs = parse_lvs_output(subprocess.check_output(["sudo", "lvs", "--noheadings", "-o", "lv_name,lv_size,vg_name", "--units", "G"]))


# Run the df command and capture its output
output = subprocess.check_output(["sudo", "df", "-H"]).decode("utf-8")

# Filter the output to show only lines containing '/dev/mapper' (i.e. the lines containing the logical volumes)
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
            "Size": convert_to_bytes(size),
            "Used": convert_to_bytes(used),
            "Available": convert_to_bytes(available),
            "Use%": int(use_percent.rstrip('%')),
            "Mount Point": mount_point,
        }
        parsed_objects.append(disk_info)

# Sort the filesystems by writing speed
sorted_file_systems = calculate_and_sort_filesystems(parsed_objects)

# Now you have a list of dictionaries where each dictionary represents the parsed information for a line
for obj in sorted_file_systems:
    if obj["Use%"] >= 80:
        lv_name = obj["Filesystem"].split("/")[-1]  # Extract the LV name from the filesystem path
        mount_point = obj["Mount Point"]

        # Unmount the filesystem gracefully
        if is_filesystem_busy(mount_point):
            logging.warning(f"Filesystem at {mount_point} is in use. Skipping unmount.")
        elif unmount_filesystem(mount_point):
            # Resize and remount the filesystem
            append_filesystem(lv_name, obj["Filesystem"], mount_point)
            remount_filesystem(lv_name, mount_point)
        else:
            logging.error(f"Error handling filesystem at {mount_point}.")
