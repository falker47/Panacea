# Panacea: Windows System Optimizer

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Panacea** is a modern, lightweight, and safe Windows system utility designed to streamline maintenance and boost performance. Built with **Python** and **CustomTkinter**, it features a sleek dark-mode interface and powerful optimization tools.

## 🚀 Key Features

### 📊 Dashboard & Monitoring

- **Real-time Stats**: Monitor CPU, RAM, Disk usage, and Battery health live.
- **System Specs**: Instant view of your OS version and hardware details.

### ⚡ Turbo Mode (Gaming Profile)

- **Performance Boost**: One-click optimization to prioritize performance over battery life.
- **Power Plans**: Automatically switches to "High Performance" power plan.
- **Visual Effects**: Disables unnecessary window animations for snappier response.
- **Service Management**: Temporarily toggles background services like `SysMain` (Superfetch), `Windows Search`, and `Print Spooler` to free up resources.

### 🧹 System Cleaning

- **Junk Removal**: Safely deletes temporary files from `%TEMP%` and `C:\Windows\Temp`.
- **Deep Clean**: Triggers DISM Component Store cleanup to reclaim disk space.
- **Recycle Bin**: One-click empty.
- **Live Logs**: View cleaning progress in real-time within the app.

### 💾 Disk Optimization

- **Smart Defrag/TRIM**: Detects drive type (SSD vs HDD) and runs the appropriate Windows optimization command (`defrag /O`).
- **Seamless Integration**: Runs in the background with progress streaming to the UI.

### 🛠️ Advanced Tools

- **System Repair**: Quick access to `sfc /scannow` and `DISM` health checks.
- **Network Fixes**: Reset DNS (`flushdns`) and Winsock to resolve connection issues.
- **App Manager**: Shortcuts to uninstall programs and manage startup items.
- **System Restore**: Create restore points before making changes.

## 🔐 Permissions & Safety

- **Admin Privileges**: Panacea automatically requests Administrator rights on startup to perform deep cleaning and system optimizations.
- **Safe Operations**: Utilizes native Windows commands (DISM, Defrag, PowerCfg) and avoids risky registry hacks.

## 📦 How to Build & Run

### Method 1: Build from Source (Recommended)

Building locally is the safest way to run the app.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/falker47/panacea.git
    cd panacea
    ```
2.  **Run the Build Script**:
    Double-click `scripts\build_exe.bat` or run it from the terminal.
    ```cmd
    scripts\build_exe.bat
    ```
3.  **Launch**:
    Find `Panacea.exe` in the `dist` folder.

### Method 2: Run with Python

For developers who want to modify the code.

1.  **Install Python 3.10+**.
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Run**:
    ```bash
    python main.py
    ```

## 🧩 Requirements

- **OS**: Windows 10 or 11
- **Python**: 3.10+ (for source execution)
- **Libraries**: `customtkinter`, `pillow`, `pyinstaller`, `packaging`
