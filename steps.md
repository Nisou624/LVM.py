- [ ]  Script LVM
    - Init
        - [ ]  create a script to init
        
        To simulate LVM (Logical Volume Management) without installing a virtual machine, you can create virtual storage using loop devices. Loop devices allow you to create files that act as block devices, which can then be used as physical volumes (PVs) in your LVM setup. Here's how you can do it:
        
        1. **Create a Virtual Disk File**:
        First, create a file that will serve as your virtual disk. You can do this using the `dd` command or any other method you prefer. For example, to create a 1GB file named `my_virtual_disk.img`, run:
            
            ```bash
            dd if=/dev/zero of=my_virtual_disk.img bs=1M count=1024
            
            ```
            
        2. **Setup a Loop Device**:
        You can use the `losetup` command to associate the virtual disk file with a loop device. For example:
            
            ```bash
            sudo losetup -f my_virtual_disk.img
            
            ```
            
            The `-f` option finds the first available loop device.
            
        3. **Create a Physical Volume (PV)**:
        Now, create a physical volume on the loop device using the `pvcreate` command:
            
            ```bash
            sudo pvcreate /dev/loopX  # Replace X with the appropriate loop device number.
            
            ```
            
        4. **Create a Volume Group (VG)**:
        After creating the PV, create a volume group using the `vgcreate` command:
            
            ```bash
            sudo vgcreate myvg /dev/loopX  # Replace X with the appropriate loop device number.
            
            ```
            
            Replace `myvg` with the desired name for your volume group.
            
        5. **Create Logical Volumes (LVs)**:
        Finally, you can create logical volumes within your volume group using the `lvcreate` command:
            
            ```bash
            sudo lvcreate -L 500M -n mylv myvg
            
            ```
            
            This creates a logical volume named `mylv` with a size of 500MB. You can adjust the size and name as needed.
            
        
        Now, you have a simulated LVM setup using a virtual storage device without the need for a virtual machine. You can proceed to use this simulated LVM for your project. Just make sure to clean up by running `lvremove`, `vgremove`, and `pvremove` to remove the logical volumes, volume group, and physical volume when you're done with the simulation. Also, don't forget to detach the loop device using `losetup -d /dev/loopX` when you're finished.
        
        - reActivating LVs:
            
            ```bash
            sudo lvchange --activate y /dev/vg_name/lv_name
            ```
            
        - Assign a file system to the LV (partition):
            
            ```bash
            mkfs -t ext4 /dev/vg_name/lv_name
            ```
            
        - Make directory for the partition:
            
            ```bash
            mkdir path/to/partitionName #partitionName = lv_name
            ```
            
        - link the directory to the partition:
            
            ```bash
            mount /dev/vg_name/lv_name path/to/partitionName 
            	#or: /dev/mapper/vg_name-lv_name
            ```
            
    - Useful commands
        - show a list of logical volumes (easy to parse):
            
            ```bash
            sudo lvs --noheadings -o lv_name,vg_name,lv_size
            ```
            
        - show a list of volume groups (easy to parse):
            
            ```bash
            sudo vgs --noheadings --units g --o vg_name,vg_size,vg_free
            ```
            
        - show a list of physical volumes (easy to parse):
            
            ```bash
            sudo pvs --noheadings --units g -o pv_name,,pv_size,pv_free
            ```
            
        
- [ ]  watch CCNA playlist
- [ ]  C-NEAT (GUI branch)(UI/UX)