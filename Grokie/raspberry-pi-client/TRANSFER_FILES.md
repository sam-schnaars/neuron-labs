# How to Transfer Files to Raspberry Pi

Since you're already on your Raspberry Pi, here are the correct ways to get the files:

## Option 1: Using SCP (from your Mac/PC)

On your **Mac/PC**, open a terminal and run:

```bash
cd ~/Desktop/neuron-labs
scp -r Grokie/raspberry-pi-client grokie@<your-pi-ip>:/home/grokie/neuron-labs/Grokie/
```

Replace `<your-pi-ip>` with your Pi's IP address. You'll be prompted for your password.

## Option 2: Using Git (if you have a repository)

If you have the code in a git repository (GitHub, GitLab, etc.):

```bash
# On your Raspberry Pi
cd ~/neuron-labs/Grokie
rm -rf raspberry-pi-client  # Remove old version if exists
git clone <your-repo-url>
cd raspberry-pi-client
```

Or if you're already in the directory and it's a git repo:

```bash
# Check if it's a git repository
git status

# If yes, pull the latest changes
git pull origin main
# or
git pull origin master
```

## Option 3: Using rsync (from Mac/PC)

```bash
# From your Mac/PC
rsync -avz --progress Grokie/raspberry-pi-client/ grokie@<your-pi-ip>:/home/grokie/neuron-labs/Grokie/raspberry-pi-client/
```

## Option 4: Manual Copy via USB Drive

1. Copy the `raspberry-pi-client` folder to a USB drive
2. Plug USB drive into Raspberry Pi
3. Copy files:
```bash
cp -r /media/usb/raspberry-pi-client ~/neuron-labs/Grokie/
```

## Option 5: Create Files Directly on Pi

If you can't transfer easily, you can recreate the files. The key files you need are:

1. `package.json`
2. `tsconfig.json`
3. `src/` directory with all TypeScript files
4. `run-pi-client.sh`

You can view the file contents from your Mac/PC and copy-paste them into files on the Pi.

## Quick Check: What's Currently on Your Pi?

Run this to see what you have:

```bash
cd ~/neuron-labs/Grokie/raspberry-pi-client
ls -la
pwd
```

This will show you what files are present and help determine the best transfer method.

