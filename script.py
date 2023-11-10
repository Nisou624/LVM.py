import subprocess
import logging
from datetime import datetime

date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

logging.basicConfig(
    level= logging.DEBUG,
    format="%(asctime)s : %(levelname)s : %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=f'logs/{date}.log'
)

"""
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
        self.lv_size = float(lv_size.replace(',','.').rstrip('g'))
        self.vg_name = vg_name

class PV:
    def __init__(self, pv_name, pv_size, pv_free):
        self.pv_name = pv_name
        self.pv_size = float(pv_size.replace(',', '.').rstrip('g'))
        self.pv_free = float(pv_free.replace(',', '.').rstrip('g'))

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
        pv = PV(
            pv_name=values[0],
            pv_size=values[1],
            pv_free=values[2]
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

logging.basicConfig(filename="./logs/test.log", level=logging.WARNING, format='%(asctime)s - %(message)s')
logging.warning(f'this is a test to see how logs will be printed in the file and see if the folder will be created')
#ls = subprocess.Popen(["sudo", "lvdisplay"], stdout= subprocess.PIPE, text=True)
#output, error =  ls.communicate()

command = ["sudo", "pvs", "--noheadings", "-o", "pv_name,pv_size,pv_free", "--units", "g"]
output = subprocess.check_output(command)
pvs = parse_pvs_output(output)

command = ["sudo", "vgs",  "--noheadings", "--units", "g"]
output = subprocess.check_output(command)
vgs = parse_vgs_output(output)

command = ["sudo", "lvs", "--noheadings", "-o", "lv_name,lv_size,vg_name", "--units", "g"]
output = subprocess.check_output(command)
lvs = parse_lvs_output(output)

for pv in pvs:
    print("------------------------------------")
    print(f"PV Name: {pv.pv_name}")
    print(f"PV Size: {pv.pv_size}")
    print(f"PV Remaining Space: {pv.pv_free}")

print("**********************************************")

for vg in vgs:
    print(f"VG Name: {vg.vg_name}")
    print(f"Number of PVs: {vg.num_pvs}")
    print(f"Number of LVs: {vg.num_lvs}")
    print(f"Number of SN: {vg.num_sn}")
    print(f"Attributes: {vg.attributes}")
    print(f"VSize: {vg.vsize}")
    print(f"VFree: {vg.vfree}")

print("**********************************************")

for lv in lvs:
    print(f"LV Name: {lv.lv_name}")
    print(f"LV Size: {lv.lv_size}")
    print(f"Virtual Group: {lv.vg_name}\n")
"""

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

        # Unmount the filesystem
        c = subprocess.call(["sudo", "umount", mount_point], capture_output=True, text=True)
        if c.returncode != 0:
            logging.error(c.stderr)
        else:
            logging.info(c.stdout)

        # Extend the LV by 1GB using the 'lvextend' command
        c = subprocess.call(["sudo", "lvextend", "-L", "+1G", "/dev/mapper/" + lv_name], capture_output=True, text=True)
        if c.returncode != 0:
            logging.error(c.stderr)
        else:
            logging.info(c.stdout)
        # Resize the filesystem to use the new space using 'resize2fs' or 'xfs_growfs' based on the filesystem type
        if "/xfs" in obj["Filesystem"]:
            c = subprocess.call(["sudo ", "xfs_growfs", mount_point], capture_output=True, text=True)
            if c.returncode != 0:
                logging.error(c.stderr)
            else:
                logging.info(c.stdout)
        else:
            c = subprocess.call(["sudo", "resize2fs", "/dev/mapper/" + lv_name], capture_output=True, text=True)
            if c.returncode != 0:
                logging.error(c.stderr)
            else:
                logging.info(c.stdout)
        # Remount the filesystem
        subprocess.call(["sudo", "mount", "/dev/mapper/" + lv_name, mount_point])


