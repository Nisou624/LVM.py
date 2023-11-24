#!/bin/bash

disks_count=$( ls -l ..| grep disk | wc -l)

LVS=(ActiveDirectory DB Logs)
VG="ASR"

for ((i = 1 ; i <= $disks_count ; i++)); do
  disk_name="disk$i.img"
  sudo losetup -f ../$disk_name
done

for i in "${LVS[@]}"; do
  #echo "/dev/$VG/$i"
  sudo lvchange --activate y /dev/$VG/$i
  sudo mount /dev/$VG/$i ../$i/
done