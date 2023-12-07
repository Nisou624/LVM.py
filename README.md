# LVM.py
A python script to automate LVM
## Description
A python script to automate Logical Volume Management (LVM).

## Project Structure
- `script.py`: This script treats the filesystems without queueing the ones that are busy.
- `main_script.py`: This script works together with `bg_script.py` to treat all the filesystems.
- `bg_script.py`: This script is used in conjunction with `main_script.py` to treat all the filesystems.

## How it Works
**disclaimer**: the parameters were chosen intuitively, this is not a script that can be used professionally but more of a experimentation or as a starting point for a more serious implementation.
- `script.py`: This script performs the LVM operations on the filesystems. It checks if a filesystem is busy before treating it.
- `main_script.py`: This script coordinates the execution of `script.py` and `bg_script.py` to ensure all filesystems are treated.
- `bg_script.py`: This script runs in the background and assists `main_script.py` in treating the filesystems.

Please refer to the individual script files for more detailed explanations of their functionality and how they interact with each other.  

