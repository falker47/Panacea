# ZEROfilez catalog verification

12 October 2026. Repository left unchanged.

Source: js/data.js has Panacea, ICONS.panacea and the exact stable URL https://github.com/falker47/Panacea/releases/latest/download/Panacea.exe. js/array.js includes it in pc-programs; js/pc-categories.js includes it in shared Essentials.

Deployed site https://falker47.github.io/ZEROfilez/ was verified through a hidden in-app browser after the web fetch failed. The normal **PC Programs** catalog renders **Essentials → Panacea**, its Panacea image and Download control. **Build → PC Setup → Choose → Essentials** renders **Select Panacea / Panacea Manual**. No package selection, installation, download-script generation or remote catalog change was performed through the browser.

The currently published latest endpoint is tested separately in zero-latest-baseline.json by downloading bytes only. This confirms the old v1.47 delivery and is not a new-release acceptance pass. After final authorized stable publication, repeat the download and compare the new binary to the independently published Panacea.exe.sha256, then repeat both deployed catalog flows.
