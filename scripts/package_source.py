import zipfile
import os

def create_zip():
    # Change to root dir
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root_dir)

    # Files to place in root of zip
    special_files = {
        "scripts/build_exe.bat": "BuildExe.bat", 
        "docs/HOW_TO_INSTALL.txt": "HOW_TO_INSTALL.txt",
        "docs/instructions.md": "instructions.md"
    }

    # Direct include in root
    include_files = [
        "main.py",
        "panacea_ui.py", # Ensure this is included
        "README.md",
        "requirements.txt",
        "Panacea.spec"
    ]
    
    # Folders to include as-is
    include_folders = ["modules", "assets", "scripts", "docs"]
    
    output_filename = "Panacea_Source_Installer.zip"
    
    print(f"Creating {output_filename}...")
    
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 1. Handle special files (move to root, modify content if needed)
        for src, dest in special_files.items():
            if os.path.exists(src):
                print(f"Adding {src} as {dest}")
                if dest == "BuildExe.bat":
                    # Read and modify content to remove "cd /d ..." line for root usage
                    with open(src, 'r') as f:
                        content = f.read()
                    content = content.replace('cd /d "%~dp0.."', 'rem Running from root')
                    zipf.writestr(dest, content)
                else:
                    zipf.write(src, dest)
            else:
                print(f"WARNING: {src} not found!")

        # 2. Add individual files to root
        for file in include_files:
            if os.path.exists(file):
                print(f"Adding {file}")
                zipf.write(file)
            else:
                print(f"WARNING: {file} not found!")
                
        # 3. Add folders (recursive)
        for folder in include_folders:
            if os.path.exists(folder):
                print(f"Adding folder {folder}")
                for root, dirs, files in os.walk(folder):
                    # Filter out unwanted dirs like __pycache__
                    dirs[:] = [d for d in dirs if d != "__pycache__"]
                    
                    for file in files:
                        if file == "__pycache__" or file.endswith(".pyc"):
                            continue
                            
                        file_path = os.path.join(root, file)
                        # Avoid adding the special files again in their original location if desired?
                        # User said "others in folders", implying duplication is okay or redundancy.
                        # But for cleanliness, let's keep them in folders too so the structure is preserved.
                        # EXCEPT if it causes confusion.
                        # Let's just add them. The user wants the convenience of root access.
                        
                        print(f"  Adding {file_path}")
                        zipf.write(file_path)
            else:
                print(f"WARNING: Folder {folder} not found!")

    print("\nZip created successfully!")
    print(f"Location: {os.path.abspath(output_filename)}")

if __name__ == "__main__":
    create_zip()
