#!/bin/bash
# Fix "No space left on device" error for pip on Raspberry Pi
# This usually happens when /tmp (tmpfs) is full, not the SD card

echo "🔍 Diagnosing 'No space left on device' issue..."
echo "================================================"
echo ""

# Check disk space
echo "📊 Disk Space Usage:"
df -h
echo ""

# Check inode usage
echo "📊 Inode Usage:"
df -i
echo ""

# Check /tmp space (this is often the culprit)
echo "📊 /tmp Directory Space:"
df -h /tmp
echo ""

# Check pip cache size
echo "📊 Pip Cache Size:"
if [ -d ~/.cache/pip ]; then
    du -sh ~/.cache/pip
else
    echo "No pip cache found"
fi
echo ""

# Check available space in /tmp
TMP_SPACE=$(df /tmp | tail -1 | awk '{print $4}')
TMP_SPACE_MB=$((TMP_SPACE / 1024))

echo "💡 Diagnosis:"
echo "   Available space in /tmp: ${TMP_SPACE_MB} MB"
echo ""

if [ $TMP_SPACE_MB -lt 100 ]; then
    echo "⚠️  /tmp is running low on space (less than 100MB)"
    echo "   This is likely the cause of your pip error!"
    echo ""
    echo "🔧 Solutions:"
    echo ""
    echo "Option 1: Clean /tmp directory (safest)"
    echo "   sudo find /tmp -type f -atime +7 -delete"
    echo ""
    echo "Option 2: Use a different temp directory for pip"
    echo "   export TMPDIR=/home/pi/tmp"
    echo "   mkdir -p /home/pi/tmp"
    echo "   pip install -r requirements.txt"
    echo ""
    echo "Option 3: Clear pip cache"
    echo "   pip cache purge"
    echo ""
    echo "Option 4: Install with no cache"
    echo "   pip install --no-cache-dir -r requirements.txt"
    echo ""
else
    echo "✅ /tmp has sufficient space"
    echo ""
    echo "🔧 Other solutions to try:"
    echo ""
    echo "1. Clear pip cache:"
    echo "   pip cache purge"
    echo ""
    echo "2. Install with no cache:"
    echo "   pip install --no-cache-dir -r requirements.txt"
    echo ""
    echo "3. Use a different temp directory:"
    echo "   export TMPDIR=/home/pi/tmp"
    echo "   mkdir -p /home/pi/tmp"
    echo "   pip install -r requirements.txt"
    echo ""
fi

echo "🚀 Quick Fix Commands:"
echo "======================"
echo ""
echo "# Clean /tmp (remove files older than 7 days)"
echo "sudo find /tmp -type f -atime +7 -delete"
echo ""
echo "# Clear pip cache"
echo "pip cache purge"
echo ""
echo "# Install with custom temp directory"
echo "export TMPDIR=/home/pi/tmp"
echo "mkdir -p /home/pi/tmp"
echo "pip install -r requirements.txt"
echo ""
echo "# Or install with no cache"
echo "pip install --no-cache-dir -r requirements.txt"
echo ""

