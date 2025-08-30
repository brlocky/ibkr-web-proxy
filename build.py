import subprocess
import sys
import os
import platform

def get_platform_suffix():
    """Get platform-specific suffix for executable name"""
    system = platform.system().lower()
    if system == "windows":
        return "windows.exe"
    elif system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    else:
        return "unknown"

def build_executable():
    try:
        print(f"Building IBKR Proxy for {platform.system()} {platform.machine()}")
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        
        os.makedirs("dist", exist_ok=True)
        
        # Platform-specific executable name
        exe_name = f"ibkr-proxy-{get_platform_suffix()}"
        
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--name", exe_name,
            "--distpath", "dist",
            "--clean",
            "--noconfirm",
            "main.py"
        ]
        
        print(f"Building executable: {exe_name}")
        subprocess.check_call(cmd)
        
        # Also create a generic name for convenience
        generic_name = "ibkr-proxy.exe" if platform.system() == "Windows" else "ibkr-proxy"
        generic_path = os.path.join("dist", generic_name)
        platform_path = os.path.join("dist", exe_name)
        
        if os.path.exists(platform_path) and not os.path.exists(generic_path):
            import shutil
            shutil.copy2(platform_path, generic_path)
            print(f"Created generic executable: {generic_name}")
        
        print("\nBuild complete!")
        print(f"Platform-specific: dist/{exe_name}")
        print(f"Generic: dist/{generic_name}")
        print("\nRun with: ./dist/{} --help".format(generic_name))
        
    except subprocess.CalledProcessError as e:
        print(f"Build failed with exit code {e.returncode}")
        print("Try: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Build failed: {e}")
        print("Make sure you have Python and pip installed")
        sys.exit(1)

if __name__ == "__main__":
    build_executable()