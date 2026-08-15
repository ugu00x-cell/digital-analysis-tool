import os
d = "C:/Users/ugu00/my-secretary/mini_gpt"
for f in sorted(os.listdir(d)):
    if f.endswith(".pt"):
        size = os.path.getsize(os.path.join(d, f)) / 1024 / 1024
        print(f"{f:30s} {size:.1f} MB")
