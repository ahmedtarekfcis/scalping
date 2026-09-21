#!/bin/bash
echo "Starting Backend and Frontend in Windows Terminal..."
# Uses Windows Terminal (wt.exe) to open tabs
wt -w 0 nt -d "$(pwd)/backend" cmd /k "python main.py" \; nt -d "$(pwd)/frontend" cmd /k "npm run dev"
