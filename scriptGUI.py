import subprocess
import logging
from datetime import datetime
from tkinter import *
from tkinter import scrolledtext
from tkinter import messagebox
from tkinter.ttk import Progressbar
from tkinter import filedialog
from tkinter import Menu

date = datetime.now().strftime('%Y-%m-%d %H:%M')

logging.basicConfig(
    level= logging.DEBUG,
    format="%(asctime)s : %(levelname)s : %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=f'logs/{date}.log'
)


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
    def __init__(self, pv_name, vg_name, pv_size, pv_free):
        self.pv_name = pv_name
        self.vg_name = vg_name
        self.pv_size = float(pv_size.replace(',', '.').rstrip('g')) if pv_size and ',' in pv_size else float(pv_size.rstrip('g'))
        self.pv_free = float(pv_free.replace(',', '.').rstrip('g')) if pv_free and ',' in pv_free else float(pv_free.rstrip('g'))

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


def extendLV(lvName, Size = "1G") -> None:
    c = subprocess.run(["sudo", "lvextend", "-L", "+1G", f"sudo lvextend -L +1G /dev/mapper/{lvName}"], capture_output=True, text=True)
    if c.returncode != 0:
        if extendVG(lvName, Size) : 
            extendLV(lvName, Size)
    else:
        logging.info(c.stdout)

def extendVG(lvName, Size):
    selected_pvs = [pv for pv in pvs if pv.vg_name == ""]
    if len(selected_pvs) != 0:   
        selected_pvs = sorted(selected_pvs, key=lambda pv: pv.pv_size)
        chosen_pvs = [pv for pv in selected_pvs if pv.pv_size == Size]
        if chosen_pvs.len() != 0 : 
            elu = chosen_pvs[0]
        else:
            while Size >0:
                elu.append(chosen_pvs[0])
                subprocess.run(["sudo", "vgextend", {lvName.split("-")[0]}, chosen_pvs[0].pv_name])
                Size -= chosen_pvs[0]
                chosen_pvs.pop(0)
        return True
    else:
        logging.CRITICAL("There's no available physical volumes for extending.")
        return False

 


    
#ls = subprocess.Popen(["sudo", "lvdisplay"], stdout= subprocess.PIPE, text=True)
#output, error =  ls.communicate()

command = ["sudo", "pvs", "--noheadings", "-o", "pv_name,vg_name,pv_size,pv_free", "--units", "g"]
output = subprocess.check_output(command)
pvs = parse_pvs_output(output)

command = ["sudo", "vgs",  "--noheadings", "--units", "g"]
output = subprocess.check_output(command)
vgs = parse_vgs_output(output)

command = ["sudo", "lvs", "--noheadings", "-o", "lv_name,lv_size,vg_name", "--units", "g"]
output = subprocess.check_output(command)
lvs = parse_lvs_output(output)

'''
for pv in pvs:
    print(f"PV Name: {pv.pv_name}")
    print(f"VG Name: {pv.vg_name}")
    print(f"PV Size: {pv.pv_size}")
    print(f"PV Remaining Space: {pv.pv_free}")
    print("------------------------------------")

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
'''

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

print(parsed_objects)

root = Tk()
root.title("GUI")

lbl = Label(root, text = "Hello", font = ("Arial Bold",20))
lbl.grid(column = 0, row = 0)

for obj in parsed_objects:
    print(f"the use of the disk is {obj}\n")
    print(f"the index of the disks: {parsed_objects.index(obj)}")
    bar = Progressbar(root, length=600)
    bar["value"] = obj["Use%"]
    bar.grid(column=0, row=(parsed_objects.index(obj) + 1) * 10)


# Use root instead of window
#bar = Progressbar(root, length=200)
#bar['value'] = 70
#bar.grid(column=0, row=8)
#
#bar = Progressbar(root, length=200)
#bar['value'] = 70
#bar.grid(column=1, row=8)

root.mainloop()

''' Now you have a list of dictionaries where each dictionary represents the parsed information for a line
for obj in parsed_objects:
    if obj["Use%"] > 80:
        lv_name = obj["Filesystem"].split("/")[-1]  # Extract the LV name from the filesystem path
        mount_point = obj["Mount Point"]

        # Unmount the filesystem
        c = subprocess.run(["sudo", "umount", mount_point], capture_output=True, text=True)
        if c.returncode != 0:
            logging.error(c.stderr)
        else:
            logging.info(c.stdout)

        # Extend the LV by 1GB using the 'lvextend' command
        extendLV(lv_name)
        # Resize the filesystem to use the new space using 'resize2fs' or 'xfs_growfs' based on the filesystem type
        if "/xfs" in obj["Filesystem"]:
            c = subprocess.run(["sudo ", "xfs_growfs", mount_point], capture_output=True, text=True)
            if c.returncode != 0:
                logging.error(c.stderr)
            else:
                logging.info(c.stdout)
        else:
            c = subprocess.run(["sudo", "resize2fs", "/dev/mapper/" + lv_name], capture_output=True, text=True)
            if c.returncode != 0:
                logging.error(c.stderr)
            else:
                logging.info(c.stdout)
        # Remount the filesystem
        subprocess.call(["sudo", "mount", "/dev/mapper/" + lv_name, mount_point])
'''



