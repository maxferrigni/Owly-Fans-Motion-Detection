# File: _front_end.py
# Purpose: Entry point for the Owl Monitoring System GUI
# Version: 1.5.5

import tkinter as tk
import sys
import os
import traceback
from utilities.logging_utils import get_logger

# Lock file path - defined here to ensure it's released on error
lock_file_path = os.path.join(os.path.expanduser("~"), ".owl_monitor.lock")

def acquire_lock():
    """Try to acquire a lock file"""
    try:
        if os.path.exists(lock_file_path):
            # Check if the lock file is stale
            try:
                with open(lock_file_path, 'r') as f:
                    pid = int(f.read().strip())
                
                # Check if the process is still running
                try:
                    # On Unix-like systems, sending signal 0 checks if process exists
                    if sys.platform != "win32":
                        os.kill(pid, 0)
                        print(f"Lock file exists and process {pid} is still running")
                        return False
                    else:
                        # On Windows, assume it's stale
                        print(f"Assuming stale lock file on Windows. Removing.")
                        os.remove(lock_file_path)
                except OSError:
                    # Process doesn't exist
                    print(f"Stale lock file found (PID {pid} not running). Removing.")
                    os.remove(lock_file_path)
            except Exception as e:
                print(f"Error checking lock file: {e}. Removing lock file.")
                os.remove(lock_file_path)
        
        # Create a new lock file with current PID
        with open(lock_file_path, 'w') as f:
            f.write(str(os.getpid()))
            
        print(f"Lock file created: {lock_file_path}")
        return True
    except Exception as e:
        print(f"Error acquiring lock: {e}")
        return False

def release_lock():
    """Release the lock file"""
    try:
        if os.path.exists(lock_file_path):
            os.remove(lock_file_path)
            print(f"Lock file removed: {lock_file_path}")
    except Exception as e:
        print(f"Error releasing lock: {e}")

def main():
    try:
        print("Starting application initialization...")
        
        # Register a function to release lock on unexpected exit
        import atexit
        atexit.register(release_lock)
        
        # Try to acquire lock
        if not acquire_lock():
            print("Could not acquire lock. Another instance may be running.")
            sys.exit(1)
        
        # Initialize root window
        root = tk.Tk()
        
        # Initialize logger
        try:
            logger = get_logger()
            logger.info("Tkinter root window created")
        except Exception as e:
            print(f"WARNING: Could not initialize logger: {e}")
        
        # Short delay for window manager
        root.after(100)
        
        # Import the OwlApp class with proper error handling
        try:
            from _front_end_app import OwlApp
            
            # Create application
            app = OwlApp(root)
            
            # Log final window geometry
            print(f"Final window geometry: {root.geometry()}")
            logger.info(f"Final window geometry: {root.geometry()}")
            
            # Start main loop
            print("Starting Tkinter main loop...")
            root.mainloop()
            
            # Clean shutdown
            print("Application closed normally")
            release_lock()
            
        except ImportError as e:
            print(f"Failed to import OwlApp: {e}")
            traceback.print_exc()
            release_lock()
            sys.exit(1)
            
    except Exception as e:
        print(f"Fatal error in GUI: {e}")
        traceback.print_exc()
        # Clean up lock on error
        release_lock()
        # Show error message
        try:
            tk.messagebox.showerror("Fatal Error", f"The application encountered a fatal error:\n\n{e}")
        except:
            pass
        raise

if __name__ == "__main__":
    main()