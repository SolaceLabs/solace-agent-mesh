import sys
import platform

def check_python_version():
    version = sys.version_info
    print(f"Python Version: {version.major}.{version.minor}.{version.micro}")

    if version.major == 3 and version.minor >= 10:
        print("✅ Compatible Python version")
    else:
        print("⚠️ Python 3.10 or higher is recommended")

def system_info():
    print("\nSystem Information:")
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Processor: {platform.processor()}")

if __name__ == "__main__":
    print("🔍 Running System Check...\n")
    check_python_version()
    system_info()