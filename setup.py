import sys
import subprocess

def compile_with_nuitka():
    command = [
        sys.executable,
        "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--include-package=utility_scripts",
        "--include-data-file=test.png=test.png",  # Fixed destination
        # "--windows-console-mode=disable",  # Updated console option
        "--output-dir=build",
        "--remove-output",
        "main.py"
    ]

    try:
        subprocess.run(command, check=True)
        print("\nBuild successful! Executable is in 'build' folder.")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed: {e}")


if __name__ == "__main__":
    compile_with_nuitka()