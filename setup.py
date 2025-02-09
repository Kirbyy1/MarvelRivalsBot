import sys
import subprocess

def compile_with_nuitka():
    # command = [
    #     sys.executable,
    #     "-m", "nuitka",
    #     "--standalone",
    #     "--onefile",
    #     "--include-package=utility_scripts",
    #     "--include-data-file=test.png=test.png",  # Fixed destination
    #     # "--windows-console-mode=disable",  # Updated console option
    #     "--output-dir=build",
    #     "--remove-output",
    #     "--lto=yes",
    #     "--file-reference-choice=original"
    #     "main.py"
    # ]

    command = [
        sys.executable,
        "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--follow-imports",  # Follow all imports strictly
        "--enable-plugin=anti-bloat",  # Remove unnecessary code
        "--include-package=utility_scripts",
        "--include-data-file=test.png=test.png",
        # "--windows-icon=app.ico",  # Add application icon
        # "--disable-console" if sys.platform == "win32" else "--enable-console",  # Platform-specific
        "--output-dir=build",
        "--remove-output",
        "--lto=yes",  # Link-time optimization
        "--assume-yes-for-downloads",
        "--warn-implicit-exceptions",
        "--python-flag=no_site",  # Disable site module
        # "--file-reference-choice=original"  # Make reverse engineering harder
        "main.py"
    ]

    try:
        subprocess.run(command, check=True)
        print("\nBuild successful! Executable is in 'build' folder.")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed: {e}")


if __name__ == "__main__":
    compile_with_nuitka()