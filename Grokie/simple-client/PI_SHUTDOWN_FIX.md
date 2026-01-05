# Fix Raspberry Pi Shutdown During Model Loading

## What Happened

Your Pi shut down while loading the Whisper model. This is almost always caused by:

1. **Insufficient Power Supply** (most common)
   - Pi needs 2.5A+ for heavy workloads
   - Model loading is CPU/RAM intensive
   - Voltage drops cause shutdown

2. **Overheating**
   - Pi throttles at 80°C, shuts down at 85°C
   - Model loading generates heat
   - No cooling = thermal shutdown

3. **Memory Issues**
   - Running out of RAM
   - System kills processes or crashes

## Immediate Solutions

### 1. Check Power Supply (CRITICAL)

**Use a proper power supply:**
- Official Raspberry Pi power supply (5V, 2.5A minimum)
- Quality USB-C power adapter (for Pi 4/5)
- Avoid USB power from computers (usually insufficient)

**Check power status:**
```bash
# After rebooting, check for low voltage warnings
dmesg | grep -i "under-voltage"
vcgencmd get_throttled
```

If you see under-voltage warnings, **you need a better power supply!**

### 2. Add Cooling

**Add a heatsink and/or fan:**
- Passive heatsinks (cheap, helps a bit)
- Active cooling fan (best solution)
- Pi case with built-in fan

**Check temperature:**
```bash
vcgencmd measure_temp
```

If it's above 70°C, you need cooling!

### 3. Reduce Model Size

Use the smallest Whisper model possible:

```bash
# In your .env file or environment
export WHISPER_MODEL=tiny
```

The "tiny" model is already the default on Pi, but make sure it's set.

### 4. Add Swap Space

If running out of RAM, add swap:

```bash
# Check current swap
free -h

# Add 1GB swap (if not enough)
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Change CONF_SWAPSIZE=100 to CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### 5. Close Other Applications

Free up resources:
```bash
# Check what's running
top

# Stop unnecessary services
sudo systemctl stop bluetooth  # if not needed
sudo systemctl stop cups  # if not needed
```

## Prevention Script

Run this before starting the voice agent:

```bash
# Check system health
./check-pi-health.sh
```

## Recommended Setup

For reliable operation:

1. **Power Supply**: Official Pi power supply (5V, 3A recommended)
2. **Cooling**: Active fan or good heatsink
3. **Model**: Use "tiny" Whisper model (already default)
4. **Swap**: 1GB swap space
5. **Close apps**: Stop unnecessary services

## Quick Fix Commands

After rebooting:

```bash
# 1. Check power status
vcgencmd get_throttled

# 2. Check temperature
vcgencmd measure_temp

# 3. Check memory
free -h

# 4. If all looks good, try again with monitoring
watch -n 1 'vcgencmd measure_temp && vcgencmd get_throttled && free -h'
# In another terminal, run your script
```

## If It Keeps Shutting Down

1. **Get a better power supply** (this fixes 90% of cases)
2. **Add active cooling** (fan)
3. **Use ethernet instead of WiFi** (less power draw)
4. **Reduce model size** (already using tiny)
5. **Consider using a Pi 4 with 4GB+ RAM** (if using older model)



