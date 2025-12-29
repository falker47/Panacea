from PIL import Image
import os

try:
    img = Image.open("panacea_icon.png")
    # Windows icons should include multiple sizes
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save("panacea_icon.ico", format='ICO', sizes=icon_sizes)
    print("Success: Multi-size Panacea.ico created.")
except Exception as e:
    print(f"Error: {e}")
