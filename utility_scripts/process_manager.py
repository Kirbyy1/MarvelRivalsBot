import subprocess
import psutil
from typing import Dict, Union
import time

def run_exe(file_path, args=None):
    """
    Runs an .exe file and captures its output.

    :param file_path: Path to the .exe file.
    :param args: Optional list of arguments.
    :return: Captured stdout and stderr combined as a string.
    """
    if args is None:
        args = []

    try:
        process = subprocess.Popen(
            [file_path] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # Ensures output is captured as a string (Python 3.7+)
            shell=True
        )

        stdout, stderr = process.communicate()  # Captures the output

        # Combine stdout and stderr into one string and return
        return stdout + (f"\nError: {stderr}" if stderr else "")

    except Exception as e:
        return f"Error: {e}"  # Return error message as string



def terminate_process_windows(
        process_name: str,
        force: bool = True,
        timeout: int = 5
) -> Dict[str, Union[bool, str, int]]:
    """
    Terminate processes by name on Windows with error returns.

    Returns:
        {
            'success': bool,
            'error': Optional[str],
            'message': Optional[str],
            'terminated_count': int,
            'remaining_count': int
        }
    """
    result = {
        'success': False,
        'error': None,
        'message': None,
        'terminated_count': 0,
        'remaining_count': 0
    }

    # Find initial processes
    try:
        initial_processes = list(find_processes(process_name))
        initial_count = len(initial_processes)
    except Exception as e:
        result['error'] = f"Process discovery failed: {str(e)}"
        return result

    if initial_count == 0:
        result.update({
            'success': True,
            'message': f"No processes found matching '{process_name}'"
        })
        return result

    # Build taskkill command
    cmd = ["taskkill", "/IM", process_name]
    if force:
        cmd.append("/F")

    # Execute termination command
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip()
        if "No tasks are running" in error_msg:
            result.update({
                'success': True,
                'terminated_count': initial_count,
                'message': "Processes already terminated"
            })
            return result

        result['error'] = f"Command failed: {error_msg}"
        return result
    except Exception as e:
        result['error'] = f"Execution error: {str(e)}"
        return result

    # Verify termination
    verification = verify_termination(process_name, initial_count, timeout)
    result.update(verification)
    result['success'] = verification['remaining_count'] == 0

    if result['success']:
        result['message'] = f"Terminated {initial_count} instance(s) of '{process_name}'"
    else:
        result['message'] = (f"Partial termination: {verification['terminated_count']} of "
                             f"{initial_count} instances terminated")

    return result


def find_processes(process_name: str):
    """Case-insensitive process finder"""
    target = process_name.lower()
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == target:
                yield proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def verify_termination(
        process_name: str,
        initial_count: int,
        timeout: int
) -> Dict[str, int]:
    """Verify process termination status"""
    remaining = initial_count
    for _ in range(timeout * 2):
        try:
            current_processes = list(find_processes(process_name))
            remaining = len(current_processes)
            if remaining == 0:
                break
        except Exception:
            pass
        time.sleep(0.5)

    return {
        'terminated_count': initial_count - remaining,
        'remaining_count': remaining
    }

def is_process_running(exe_name):
    """Check if there is any running process that contains the given name."""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] == exe_name:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

# Example usage:
# run_exe("C:\\path\\to\\your_program.exe", ["--arg1", "value"], wait=True)
