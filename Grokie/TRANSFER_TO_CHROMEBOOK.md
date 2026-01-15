# How to Transfer Grokie Project to Chromebook (Linux Fedora)

This guide explains how to copy the Grokie project from your Mac to a Chromebook running Linux Fedora.

**Note:** This guide uses Fedora-specific commands (`dnf` package manager). If you're using a different Linux distribution, replace `dnf` with the appropriate package manager (`apt` for Debian/Ubuntu, `pacman` for Arch, etc.).

## Prerequisites

1. **Enable Linux on your Chromebook** (if not already done):
   - Go to Settings → Advanced → Developers
   - Enable "Linux development environment"
   - Wait for Linux to install

2. **Find your Chromebook's IP address**:
   - On Chromebook: Open Terminal (Linux) and run:
     ```bash
     hostname -I
     ```
   - Or check in Chrome OS Settings → Network → Your connection

3. **Set up SSH on Chromebook** (recommended):
   ```bash
   # On Chromebook Linux terminal (Fedora)
   sudo dnf install openssh-server
   sudo systemctl enable sshd
   sudo systemctl start sshd
   ```

## Transfer Methods

### Option 1: Using SCP (Secure Copy) - Recommended

From your **Mac terminal**, run:

```bash
cd ~/Desktop/neuron-labs

# Transfer the entire Grokie directory
scp -r Grokie <your-chromebook-username>@<chromebook-ip>:/home/<your-chromebook-username>/neuron-labs/

# Example:
# scp -r Grokie sam@192.168.1.100:/home/sam/neuron-labs/
```

**Note:** You'll be prompted for your Chromebook Linux password. If you haven't set one, set it first:
```bash
# On Chromebook
passwd
```

### Option 2: Using rsync (Better for updates)

From your **Mac terminal**:

```bash
cd ~/Desktop/neuron-labs

# Transfer with progress and exclude unnecessary files
rsync -avz --progress \
  --exclude 'venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'node_modules/' \
  --exclude '.git/' \
  Grokie/ <your-chromebook-username>@<chromebook-ip>:/home/<your-chromebook-username>/neuron-labs/Grokie/
```

### Option 3: Using Git (If you have a repository)

**On your Chromebook Linux terminal:**

```bash
# Install git if needed (Fedora)
sudo dnf install git

# Clone or pull the repository
cd ~
mkdir -p neuron-labs
cd neuron-labs
git clone <your-repo-url>
# or if already cloned:
cd Grokie
git pull
```

### Option 4: Using USB Drive

1. **On Mac:**
   - Copy the `Grokie` folder to a USB drive
   - Eject the USB drive

2. **On Chromebook:**
   - Insert USB drive
   - Open Files app
   - Copy `Grokie` folder to Linux files (usually accessible in Files app)
   - Or use terminal:
     ```bash
     # Find USB mount point (usually /media/removable/USB-Name)
     ls /media/removable/
     
     # Copy files
     mkdir -p ~/neuron-labs
     cp -r /media/removable/USB-Name/Grokie ~/neuron-labs/
     ```

### Option 5: Using Google Drive / Cloud Storage

1. **On Mac:**
   - Zip the Grokie folder:
     ```bash
     cd ~/Desktop/neuron-labs
     zip -r Grokie.zip Grokie -x "*/venv/*" "*/node_modules/*" "*/.git/*"
     ```
   - Upload `Grokie.zip` to Google Drive

2. **On Chromebook:**
   - Download from Google Drive
   - Extract:
     ```bash
     cd ~/Downloads
     unzip Grokie.zip -d ~/neuron-labs/
     ```

## After Transfer: Setup on Chromebook

Once files are transferred, set up the project on your Chromebook:

### 1. Install Python and dependencies

```bash
# On Chromebook Linux terminal
cd ~/neuron-labs/Grokie

# Install Python 3 and pip if needed (Fedora)
sudo dnf install python3 python3-pip python3-venv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Set up environment variables

```bash
# Create .env file
nano .env
# or
vim .env
```

Add your API keys:
```
XAI_API_KEY=your_actual_api_key_here
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

### 3. Install Node.js (for web-client, if needed)

```bash
# Install Node.js (Fedora)
sudo dnf install nodejs npm

# Or for latest version, use NodeSource (optional):
# curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
# sudo dnf install -y nodejs
```

### 4. Test the installation

```bash
# Activate virtual environment
source venv/bin/activate

# Test Python import
python3 -c "import livekit.agents; print('LiveKit installed successfully')"
```

## Troubleshooting

### SSH Connection Issues

If you can't connect via SSH:

1. **Check SSH is running on Chromebook:**
   ```bash
   sudo systemctl status sshd
   ```

2. **Check firewall (Fedora uses firewalld):**
   ```bash
   sudo firewall-cmd --permanent --add-service=ssh
   sudo firewall-cmd --reload
   # Or if firewalld is not running, you may need to start it:
   sudo systemctl start firewalld
   ```

3. **Verify IP address:**
   ```bash
   hostname -I
   ```

### Permission Issues

If you get permission errors:

```bash
# Fix ownership
sudo chown -R $USER:$USER ~/neuron-labs
```

### Network Issues

- Make sure both devices are on the same Wi-Fi network
- Try using the Chromebook's hostname instead of IP:
  ```bash
  # Find hostname on Chromebook
  hostname
  
  # Use it in SCP
  scp -r Grokie user@chromebook-hostname.local:/home/user/neuron-labs/
  ```

## Quick Reference Commands

**From Mac to Chromebook:**
```bash
# Full transfer
scp -r ~/Desktop/neuron-labs/Grokie user@chromebook-ip:~/neuron-labs/

# Update existing files
rsync -avz --progress Grokie/ user@chromebook-ip:~/neuron-labs/Grokie/
```

**On Chromebook after transfer:**
```bash
cd ~/neuron-labs/Grokie
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
