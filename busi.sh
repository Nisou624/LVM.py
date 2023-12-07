#!/bin/bash

#busi = BUsy SImulator

# Check if a directory path is provided as an argument
if [ $# -eq 0 ]; then
    echo "Usage: $0 <directory_path>"
    exit 1
fi

# Specify the directory to simulate as busy
directory_to_simulate_busy="$1"


while true; do
    # Create a large number of empty files in the specified directory
    for i in {1..1000}; do
        touch "$directory_to_simulate_busy/file$i"
    done

    # Sleep for a short duration to keep the files in place for some time
    sleep 0.1

    # Remove the files created in the specified directory
    rm -rf "$directory_to_simulate_busy"/file*
done

