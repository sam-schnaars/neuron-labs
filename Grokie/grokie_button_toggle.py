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
use_polling = False  # Fallback to polling if event detection fails
last_button_state = None  # Will be initialized after GPIO setup

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
    
    # Remove event detection before cleanup (matching whisplay pattern)
    try:
        GPIO.remove_event_detect(BUTTON_PIN)
    except (RuntimeError, ValueError):
        # Event detection might not exist, that's fine
        pass
    
    try:
        GPIO.cleanup()
    except Exception as e:
        # GPIO might already be cleaned up or in use
        pass
    
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
        # Use subprocess.PIPE for stderr so we can capture errors
        # But let stdout go to terminal so we can see real-time output
        grok_process = subprocess.Popen(
            [sys.executable, str(CLIENT_SCRIPT)],
            cwd=str(SCRIPT_DIR),
            stdout=None,  # Let stdout go to terminal
            stderr=subprocess.PIPE,  # Capture stderr for error reporting
            preexec_fn=os.setsid  # Create new process group
        )
        is_connected = True
        print("✅ GROK connection started! (PID: {})".format(grok_process.pid))
        print("   Watch the output above for connection status and errors.")
        
        # Give it a moment to start, then check if it's still alive
        time.sleep(0.5)
        if grok_process.poll() is not None:
            # Process died immediately
            exit_code = grok_process.returncode
            print(f"❌ GROK connection failed immediately (exit code: {exit_code})")
            if grok_process.stderr:
                try:
                    stderr_output = grok_process.stderr.read().decode('utf-8', errors='ignore')
                    if stderr_output:
                        print("\n❌ Error output:")
                        print(stderr_output)
                except:
                    pass
            is_connected = False
            grok_process = None
            return
    except Exception as e:
        print(f"❌ Error starting GROK connection: {e}")
        import traceback
        traceback.print_exc()
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
    """Handle button press event (for interrupt-based detection)."""
    # Small debounce delay
    time.sleep(0.1)
    
    # Check if button is actually pressed (LOW = pressed with pull-up)
    if GPIO.input(channel) == GPIO.LOW:
        print("\n[Button Pressed] Toggling GROK connection...")
        toggle_connection()
    else:
        # Button was released, ignore
        pass


def check_button_polling():
    """Check button state using polling (fallback method)."""
    global last_button_state
    current_state = GPIO.input(BUTTON_PIN)
    
    # Detect falling edge (button press: HIGH -> LOW)
    if last_button_state == GPIO.HIGH and current_state == GPIO.LOW:
        print("\n[Button Pressed] Toggling GROK connection...")
        toggle_connection()
        time.sleep(0.3)  # Debounce
    
    last_button_state = current_state


def main():
    """Main function to set up button monitoring."""
    global grok_process, is_connected, use_polling, last_button_state
    
    print("=" * 50)
    print("GROK Voice Agent - Button Toggle")
    print("=" * 50)
    print(f"Button pin: {BUTTON_PIN}")
    print(f"Client script: {CLIENT_SCRIPT}")
    print("=" * 50)
    print("\nPress the button to toggle GROK connection on/off")
    print("Press Ctrl+C to exit\n")
    
    # Set up GPIO mode first (matching whisplay's approach)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    
    # Try to remove any existing event detection (must be done after setmode)
    try:
        GPIO.remove_event_detect(BUTTON_PIN)
        print("⚠️  Removed existing event detection on pin 11")
    except (RuntimeError, ValueError):
        # No existing event detection, that's fine
        pass
    
    # Set up the button pin
    try:
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    except RuntimeError as e:
        print(f"❌ Error setting up GPIO pin {BUTTON_PIN}: {e}")
        print("   The pin might be in use by another process (e.g., whisplay chatbot).")
        print("   Make sure the whisplay chatbot is not running.")
        print("   Try: pkill -f chatbot")
        sys.exit(1)
    
    # Set up button event detection
    # Use FALLING edge to detect button press (HIGH to LOW)
    # Note: whisplay uses GPIO.BOTH with bouncetime=50, but we use FALLING with 300ms
    try:
        GPIO.add_event_detect(
            BUTTON_PIN,
            GPIO.FALLING,
            callback=button_press_event,
            bouncetime=300  # 300ms debounce (whisplay uses 50ms)
        )
        print("✅ Button event detection set up successfully (interrupt mode)")
        use_polling = False
    except RuntimeError as e:
        print(f"⚠️  Event detection failed: {e}")
        print("   Falling back to polling mode (less efficient but more reliable)")
        print("   This is normal if another process is using GPIO.")
        # Initialize button state for polling
        last_button_state = GPIO.input(BUTTON_PIN)
        use_polling = True
    
    try:
        # Keep the script running
        while True:
            if use_polling:
                # Use polling mode (check button every 50ms)
                check_button_polling()
                time.sleep(0.05)
            else:
                # Event detection mode (just sleep)
                time.sleep(1)
            
            # Check if process is still running
            if grok_process and grok_process.poll() is not None:
                exit_code = grok_process.returncode
                print(f"\n⚠️  GROK connection process ended unexpectedly (exit code: {exit_code})")
                
                # Try to read stderr to show the error
                if grok_process.stderr:
                    try:
                        stderr_output = grok_process.stderr.read().decode('utf-8', errors='ignore')
                        if stderr_output:
                            print("\n❌ Error output from GROK client:")
                            print("=" * 50)
                            print(stderr_output)
                            print("=" * 50)
                    except Exception as e:
                        print(f"   (Could not read error output: {e})")
                
                grok_process = None
                is_connected = False
                print("\n💡 You can press the button again to retry the connection.")
                
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

