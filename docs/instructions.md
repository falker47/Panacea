# 🛠️ Project Prompt — Panacea: Windows System Optimizer (v1.0)

You are the most expert AI coding assistant in the whole world.
Your last assignment is to build a Windows desktop utility that performs safe system maintenance operations with a simple UI.

The application must implement the following features and constraints.

---

## 🎯 Goal

Create a small Windows utility that allows the user to:

- Clean temporary and unnecessary files  
- Optimize / manage disks using native Windows tools  
- Execute predefined maintenance commands via CMD  

Priorities:
- operations must be **safe and non-destructive**
- UI must be simple and clear
- request **administrator privileges** when required

---

## 🧩 Architecture

- Platform: **Windows desktop application**
- Preferred language: **C# .NET (WinForms or WPF)**
- Alternative acceptable: Python + tkinter/Qt
- All actions must rely on:
  - native Windows tools (`cleanmgr`, `defrag`, `dfrgui`, `cmd`, `dism`, `sfc`)
  - system APIs where necessary

---

## 🖥️ UI Structure

Create a main window with **3 functional sections**:

### 1️⃣ System Cleaning
Buttons:
- “Clean temporary files”
- “Empty recycle bin”
- “Open Disk Cleanup (preset mode)”

Display:
- operation log
- count of deleted files
- estimated freed space

---

### 2️⃣ Disk Optimization
The program must:
- detect available drives (C:, D:, …)
- detect drive type (**SSD / HDD**)

Per-drive actions:
- Open Windows Optimization GUI (`dfrgui.exe`)
- Run quick optimization CLI (only for HDD) using `defrag X: /O`

SSD must **not** be defragmented aggressively.

---

### 3️⃣ Advanced CMD Tools
Provide buttons that execute commands in a separate admin CMD window:

System integrity:
- `sfc /scannow`
- `DISM /Online /Cleanup-Image /CheckHealth`
- `DISM /Online /Cleanup-Image /ScanHealth`
- `DISM /Online /Cleanup-Image /RestoreHealth`

Network tools:
- `ipconfig /flushdns`
- `netsh winsock reset`

Rules:
- show confirmation for invasive actions
- commands must run via `cmd.exe /k "<command>"`

---

## 🔐 Permissions & Safety

- Detect whether the app is running as **administrator**
- If not, trigger UAC elevation
- Do not delete files outside:
  - `%TEMP%`
  - `C:\Windows\Temp`
  - recycle bin
- Avoid destructive automatic behaviors

---

## ⚙️ Cleaning Logic

Paths handled:
- `%TEMP%`
- `C:\Windows\Temp`

Behavior:
- recursive deletion of files and folders
- ignore locked files
- compute:
  - deleted file count
  - estimated freed space

Optional:
- execute `Clear-RecycleBin` via PowerShell
- allow launching `cleanmgr.exe`

---

## 💽 Disk Optimization Logic

Detect disk type via WMI or equivalent.

Rules:
- HDD → `defrag X: /O`
- SSD → only status check / Windows optimize
- allow opening `dfrgui.exe`

---

## 🧾 Logging

Generate a log file in:

`%USERPROFILE%\Documents\SystemOptimizer\log.txt`

Each entry must include:
- timestamp
- executed operation
- success / error status
- details where useful

---

## 🚧 Intentional Limitations (v1)

Do NOT implement:
- registry cleaners
- automatic driver updates
- service tuning
- aggressive background optimizations

Goal = **safety + transparency**

---

## 🧪 Testing Requirements

Validate on Windows 10 & 11:

- correct UAC behavior
- locked temp files don’t crash the app
- SSD never defragmented
- logs generated correctly
- CMD tools launch successfully

---

## 📦 Deliverables

- project scaffold + UI
- functional modules:
  - `CleanupManager`
  - `DiskOptimizer`
  - `CommandRunner`
  - `Logger`
- README including:
  - requirements
  - permissions
  - implemented functions
  - usage notes

---

Build the initial working version of this application now.
