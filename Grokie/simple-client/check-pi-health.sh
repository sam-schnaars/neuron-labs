#!/bin/bash
# Check Raspberry Pi health before running intensive tasks

echo "🔍 Raspberry Pi Health Check"
echo "============================"
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "⚠️  Not running on Raspberry Pi"
    exit 1
fi

# Get Pi model
PI_MODEL=$(cat /proc/device-tree/model 2>/dev/null || echo "Unknown")
echo "📱 Pi Model: $PI_MODEL"
echo ""

# Check power/throttling status
echo "⚡ Power Status:"
THROTTLED=$(vcgencmd get_throttled 2>/dev/null || echo "0x0")
THROTTLED_VALUE=$(echo $THROTTLED | cut -d= -f2)

if [ "$THROTTLED_VALUE" != "0x0" ]; then
    echo "⚠️  WARNING: Throttling detected!"
    echo "   Value: $THROTTLED_VALUE"
    echo "   This indicates power or temperature issues!"
    
    # Decode throttling flags
    if [ "$((THROTTLED_VALUE & 0x1))" -ne 0 ]; then
        echo "   ❌ Under-voltage detected!"
        echo "   💡 SOLUTION: Use official Pi power supply (2.5A+)"
    fi
    if [ "$((THROTTLED_VALUE & 0x2))" -ne 0 ]; then
        echo "   ❌ Frequency capped (throttling)"
    fi
    if [ "$((THROTTLED_VALUE & 0x4))" -ne 0 ]; then
        echo "   ❌ Currently throttled"
    fi
    if [ "$((THROTTLED_VALUE & 0x8))" -ne 0 ]; then
        echo "   ❌ Soft temperature limit reached"
        echo "   💡 SOLUTION: Add cooling (fan/heatsink)"
    fi
else
    echo "✅ No throttling detected"
fi
echo ""

# Check temperature
echo "🌡️  Temperature:"
TEMP=$(vcgencmd measure_temp 2>/dev/null | cut -d= -f2 || echo "N/A")
echo "   Current: $TEMP"

# Extract numeric value
TEMP_NUM=$(echo $TEMP | cut -d\' -f1)

if [ ! -z "$TEMP_NUM" ]; then
    if (( $(echo "$TEMP_NUM > 80" | bc -l 2>/dev/null || echo 0) )); then
        echo "   ⚠️  WARNING: Temperature is very high!"
        echo "   💡 SOLUTION: Add cooling immediately"
    elif (( $(echo "$TEMP_NUM > 70" | bc -l 2>/dev/null || echo 0) )); then
        echo "   ⚠️  Temperature is high - consider adding cooling"
    else
        echo "   ✅ Temperature is acceptable"
    fi
fi
echo ""

# Check memory
echo "💾 Memory Status:"
free -h | grep -E "Mem|Swap"
echo ""

MEM_AVAIL=$(free -m | grep Mem | awk '{print $7}')
if [ ! -z "$MEM_AVAIL" ]; then
    if [ "$MEM_AVAIL" -lt 500 ]; then
        echo "⚠️  WARNING: Low available memory (< 500MB)"
        echo "   💡 SOLUTION: Close other applications or add swap"
    else
        echo "✅ Sufficient memory available"
    fi
fi
echo ""

# Check disk space
echo "💿 Disk Space:"
df -h / | tail -1
echo ""

# Check CPU frequency
echo "⚙️  CPU Frequency:"
CPU_FREQ=$(vcgencmd measure_clock arm 2>/dev/null | cut -d= -f2 || echo "N/A")
if [ "$CPU_FREQ" != "N/A" ]; then
    CPU_FREQ_MHZ=$((CPU_FREQ / 1000000))
    echo "   $CPU_FREQ_MHZ MHz"
    
    # Check if throttled (frequency lower than expected)
    if [ "$CPU_FREQ_MHZ" -lt 1000 ]; then
        echo "   ⚠️  CPU frequency is low (may be throttled)"
    fi
fi
echo ""

# Recommendations
echo "💡 Recommendations:"
echo "==================="

if [ "$THROTTLED_VALUE" != "0x0" ]; then
    echo "❌ DO NOT RUN INTENSIVE TASKS - Pi has power/temperature issues!"
    echo ""
    echo "Fix these issues first:"
    if [ "$((THROTTLED_VALUE & 0x1))" -ne 0 ]; then
        echo "1. Get official Raspberry Pi power supply (5V, 2.5A+)"
    fi
    if [ "$((THROTTLED_VALUE & 0x8))" -ne 0 ]; then
        echo "2. Add active cooling (fan) or better heatsink"
    fi
    echo ""
    echo "After fixing, reboot and run this script again."
else
    echo "✅ System looks healthy!"
    echo "   You can proceed with running the voice agent."
    echo ""
    echo "For best results:"
    echo "- Use official Pi power supply"
    echo "- Ensure adequate cooling"
    echo "- Close unnecessary applications"
fi
echo ""



