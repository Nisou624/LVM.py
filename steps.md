- [ ]  Script LVM
    - Init
        - [ ]  Create Physical Volumes (PVs)
            1. Create a virtual disk file using the `dd` command or any other method you prefer. For example:
                ```bash
                dd if=/dev/zero of=my_virtual_disk.img bs=1M count=1024
                ```
            2. Associate the virtual disk file with a loop device using the `losetup` command:
                ```bash
                sudo losetup -f my_virtual_disk.img
                ```
            3. Create a physical volume on the loop device using the `pvcreate` command:
                ```bash
                sudo pvcreate /dev/loopX  # Replace X with the appropriate loop device number.
                ```
        - [ ]  Create Volume Groups (VGs)
            1. Create a volume group using the `vgcreate` command:
                ```bash
                sudo vgcreate myvg /dev/loopX  # Replace X with the appropriate loop device number.
                ```
                Replace `myvg` with the desired name for your volume group.
        - [ ]  Create Logical Volumes (LVs)
            1. Create logical volumes within your volume group using the `lvcreate` command:
                ```bash
                sudo lvcreate -L 500M -n mylv myvg
                ```
                This creates a logical volume named `mylv` with a size of 500MB. You can adjust the size and name as needed.
        - [ ]  Make LVs as File Systems (Partitions)
            1. Assign a file system to the logical volume using the `mkfs` command:
                ```bash
                mkfs -t ext4 /dev/vg_name/lv_name
                ```
            2. Make a directory for the partition:
                ```bash
                mkdir path/to/partitionName  # partitionName = lv_name
                ```
            3. Link the directory to the partition using the `mount` command:
                ```bash
                mount /dev/vg_name/lv_name path/to/partitionName 
                # or: /dev/mapper/vg_name-lv_name
                ```
    - Useful commands
        - Show a list of logical volumes:
            ```bash
            sudo lvs --noheadings -o lv_name,vg_name,lv_size
            ```
        - Show a list of volume groups:
            ```bash
            sudo vgs --noheadings --units g --o vg_name,vg_size,vg_free
            ```
        - Show a list of physical volumes:
            ```bash
            sudo pvs --noheadings --units g -o pv_name,,pv_size,pv_free
            ```
        - Show a list of block devices:
            ```bash
            lsblk
            ```
        - Show disk space usage:
            ```bash
            df -h
            ```