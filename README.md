# Panacea: Windows System Optimizer

Panacea is a lightweight, safe, and modern Windows desktop utility designed to perform essential system maintenance operations. It is built with Python and CustomTkinter, featuring a sleek dark-mode interface.

<div align="center">
  <img src="panacea_icon.png" alt="Panacea Icon" width="128"/>
</div>

## 🎯 Features

### 1. Dashboard & Monitoring
- **Live Monitoring**: Real-time stats for CPU, RAM, Disk, and Battery.
- **System Specs**: Displays basic OS and Hardware information.

### 2. System Cleaning
- **Clean Temporary Files**: Recursively deletes files in `%TEMP%` and `C:\Windows\Temp`. Safely skips locked files.
- **Empty Recycle Bin**: Quickly clears the recycle bin.
- **Deep Clean**: Can trigger DISM Component Store cleanup.
- **Log Tab**: All cleaning actions log their output directly in the UI.

### 3. Disk Optimization
- **Drive Detection**: Detects and lists available drives (C:, D:, etc.).
- **Smart Optimization**:
    - Uses Windows built-in `defrag /O` command which automatically performs the correct action based on drive type (Defragment for HDD, TRIM for SSD).
    - **Integrated Log**: Optimization progress is streamed directly to an in-app log tab, so no external command windows pop up.
    - Can launch the full Windows "Defragment and Optimize Drives" GUI.

### 4. Advanced Tools
- **System Integrity**: Easy access to `sfc /scannow` and various `DISM` health checks to repair Windows image corruption.
- **Network Reset**: Tools to `flushdns` and `reset winsock` to fix network connectivity issues.
- **App Management**: Quick links to uninstall programs or manage startup apps.

## 🔐 Permissions & Safety
- **Administrator Required**: The application checks for Admin privileges on startup and attempts to restart itself as Administrator if needed. This is required for accessing system temp folders and running maintenance commands.
- **Safety First**: Panacea only runs native Windows commands and deletes files in designated temporary locations. It does not touch the Registry manually or install drivers.

## 🚀 How to Build & Run

### Method 1: Build from Source (Recommended)
Use the included build script to compile the application locally. This is the best way to share the app with friends to avoid antivirus false positives associated with unknown executables.

1.  Extract the source code zip.
2.  Double-click **`BuildExe.bat`**.
3.  Wait for the script to install dependencies and compile the executable.
4.  Run the generated `Panacea.exe` from the `dist` folder.

### Method 2: Run with Python 
If you are a developer:

1.  Install Python 3.x.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the application:
    ```bash
    python main.py
    ```

## 🧩 Requirements
- Windows 10 or 11
- Python 3.x (for building or direct execution)
- Dependencies: `customtkinter`, `packaging`, `pillow`, `pyinstaller`
