import sys
print("Python:", sys.version)
mods = [
    "fastapi",
    "uvicorn",
    "asyncpg",
    "multipart",
    "psutil",
    "bcrypt",
    "jose",
    "httpx",
]
for name in mods:
    __import__(name)
    print("OK", name)
print("All imports OK")
