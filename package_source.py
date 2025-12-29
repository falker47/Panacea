import zipfile
import os

def create_zip():
    # Files and folders to include
    include_files = [
        "main.py",
        "panacea_ui.py",
        "BuildExe.bat",
        "requirements.txt",
        "panacea_icon.ico",
        "HOW_TO_INSTALL.txt"
    ]
    include_folders = ["modules"]
    
    output_filename = "Panacea_Source_Installer.zip"
    
    print(f"Creating {output_filename}...")
    
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add individual files
        for file in include_files:
            if os.path.exists(file):
                print(f"Adding {file}")
                zipf.write(file)
            else:
                print(f"WARNING: {file} not found!")
                
        # Add folders (recursive)
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
                        print(f"  Adding {file_path}")
                        zipf.write(file_path)
            else:
                print(f"WARNING: Folder {folder} not found!")

    print("\nZip created successfully!")
    print(f"Location: {os.path.abspath(output_filename)}")

if __name__ == "__main__":
    create_zip()
