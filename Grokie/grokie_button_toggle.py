"""
GROK Voice Agent Button Toggle
Monitors button presses and toggles the GROK voice connection on/off.
"""

import RPi.GPIO as GPIO
import subprocess
import signal
import os
import sys
import time
from pathlib import Path

# Button pin (same as whisplay project)
BUTTON_PIN = 11

# Global state
grok_process = None
is_connected = False

# Get the directory of this script
SCRIPT_DIR = Path(__file__).parent.absolute()
CLIENT_SCRIPT = SCRIPT_DIR / "raspberry-pi-client" / "grok_pi_client.py"


def cleanup():
    """Clean up GPIO and terminate any running processes."""
    global grok_process
    if grok_process:
        try:
            print("Terminating GROK connection...")
            grok_process.terminate()
            grok_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Force killing GROK connection...")
            grok_process.kill()
            grok_process.wait()
        except Exception as e:
            print(f"Error terminating process: {e}")
        grok_process = None
    GPIO.cleanup()
    print("Cleanup complete.")


def start_grok_connection():
    """Start the GROK voice connection."""
    global grok_process, is_connected
    
    if is_connected:
        print("Already connected to GROK.")
        return
    
    print("Starting GROK voice connection...")
    try:
        # Start the client script
        grok_process = subprocess.Popen(
            [sys.executable, str(CLIENT_SCRIPT)],
            cwd=str(SCRIPT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Create new process group
        )
        is_connected = True
        print("✅ GROK connection started!")
    except Exception as e:
        print(f"❌ Error starting GROK connection: {e}")
        is_connected = False
        grok_process = None


def stop_grok_connection():
    """Stop the GROK voice connection."""
    global grok_process, is_connected
    
    if not is_connected or grok_process is None:
        print("Not connected to GROK.")
        return
    
    print("Stopping GROK voice connection...")
    try:
        # Terminate the process group
        os.killpg(os.getpgid(grok_process.pid), signal.SIGTERM)
        grok_process.wait(timeout=5)
        print("✅ GROK connection stopped!")
    except subprocess.TimeoutExpired:
        print("Force killing GROK connection...")
        os.killpg(os.getpgid(grok_process.pid), signal.SIGKILL)
        grok_process.wait()
        print("✅ GROK connection force stopped!")
    except Exception as e:
        print(f"❌ Error stopping GROK connection: {e}")
    finally:
        grok_process = None
        is_connected = False


def toggle_connection():
    """Toggle the GROK connection on/off."""
    if is_connected:
        stop_grok_connection()
    else:
        start_grok_connection()


def button_press_event(channel):
    """Handle button press event."""
    # Small debounce delay
    time.sleep(0.1)
    
    # Check if button is actually pressed (LOW = pressed with pull-up)
    if GPIO.input(channel) == GPIO.LOW:
        print("\n[Button Pressed] Toggling GROK connection...")
        toggle_connection()
    else:
        # Button was released, ignore
        pass


def main():
    """Main function to set up button monitoring."""
    global grok_process, is_connected
    
    print("=" * 50)
    print("GROK Voice Agent - Button Toggle")
    print("=" * 50)
    print(f"Button pin: {BUTTON_PIN}")
    print(f"Client script: {CLIENT_SCRIPT}")
    print("=" * 50)
    print("\nPress the button to toggle GROK connection on/off")
    print("Press Ctrl+C to exit\n")
    
    # Set up GPIO
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Set up button event detection
    # Use FALLING edge to detect button press (HIGH to LOW)
    GPIO.add_event_detect(
        BUTTON_PIN,
        GPIO.FALLING,
        callback=button_press_event,
        bouncetime=300  # 300ms debounce
    )
    
    try:
        # Keep the script running
        while True:
            time.sleep(1)
            
            # Check if process is still running
            if grok_process and grok_process.poll() is not None:
                print("\n⚠️  GROK connection process ended unexpectedly")
                grok_process = None
                is_connected = False
                
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()
        print("👋 Goodbye!")


def signal_handler(signum, frame):
    """Handle termination signals."""
    cleanup()
    sys.exit(0)


if __name__ == "__main__":
    # Handle signals for cleanup
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    main()

