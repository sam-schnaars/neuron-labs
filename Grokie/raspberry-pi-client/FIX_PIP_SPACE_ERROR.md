# Fix "No space left on device" Error for pip

## The Problem

You're getting this error even though your SD card has plenty of space:
```
pip._vendor.urllib3.exceptions.ProtocolError: ("Connection broken: OSError(28, 'No space left on device')", OSError(28, 'No space left on device'))
```

## Why This Happens

On Raspberry Pi (and many Linux systems), the `/tmp` directory is often mounted as a **tmpfs** (RAM-based filesystem). This means:
- It's stored in RAM, not on your SD card
- It has limited space (usually 50-100MB on Pi)
- When pip downloads and extracts packages, it uses `/tmp` for temporary files
- If `/tmp` fills up, you get the "No space left on device" error

**Your SD card might have 10GB free, but `/tmp` only has 5MB free!**

## Quick Fixes

### Option 1: Use a Different Temp Directory (Recommended)

```bash
# Create a temp directory on your SD card
export TMPDIR=/home/pi/tmp
mkdir -p /home/pi/tmp

# Now run pip install
pip install -r requirements.txt
```

### Option 2: Install Without Cache

```bash
pip install --no-cache-dir -r requirements.txt
```

This prevents pip from storing downloaded packages in cache, reducing temporary file usage.

### Option 3: Clear /tmp Directory

```bash
# Remove old files from /tmp (older than 7 days)
sudo find /tmp -type f -atime +7 -delete

# Or clear everything (be careful!)
sudo rm -rf /tmp/*
```

### Option 4: Clear Pip Cache

```bash
# Clear pip's cache directory
pip cache purge
```

## Diagnostic Script

Run the diagnostic script to see what's causing the issue:

```bash
chmod +x fix-pip-space.sh
./fix-pip-space.sh
```

This will show you:
- Disk space usage
- `/tmp` space usage
- Pip cache size
- Recommended solutions

## Permanent Solution

Add this to your `~/.bashrc` or `~/.zshrc` to always use your home directory for temp files:

```bash
# Use home directory for temp files (more space than /tmp)
export TMPDIR="$HOME/tmp"
mkdir -p "$TMPDIR"
```

Then reload your shell:
```bash
source ~/.bashrc
```

## For Virtual Environments

If you're using a virtual environment, you can also set TMPDIR before activating it:

```bash
export TMPDIR=/home/pi/tmp
mkdir -p /home/pi/tmp
source venv/bin/activate
pip install -r requirements.txt
```

## Check Current Space

To see what's actually full:

```bash
# Check disk space
df -h

# Check /tmp specifically
df -h /tmp

# Check inode usage (sometimes this is the issue)
df -i
```

## Summary

The error is almost always caused by `/tmp` being full (RAM-based), not your SD card. The quickest fix is to use a different temp directory:

```bash
export TMPDIR=/home/pi/tmp && mkdir -p /home/pi/tmp && pip install -r requirements.txt
```

