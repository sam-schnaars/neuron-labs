/**
 * Headless Browser Runner for GROK Web Client
 * 
 * Runs the web-client in a headless Chromium browser on Raspberry Pi.
 * This avoids needing to rewrite the client in Python.
 * 
 * Requirements:
 * - Node.js (v18+)
 * - Chromium browser: sudo apt install chromium-browser
 * - Puppeteer: npm install puppeteer-core
 * 
 * Usage:
 *   node run_web_client_headless.js
 */

import puppeteer from 'puppeteer-core';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const WEB_CLIENT_DIR = join(__dirname, '..', 'web-client');

// Configuration
const LIVEKIT_URL = process.env.LIVEKIT_URL || 'ws://localhost:7880';
const LIVEKIT_API_KEY = process.env.LIVEKIT_API_KEY || 'devkey';
const LIVEKIT_API_SECRET = process.env.LIVEKIT_API_SECRET || 'secret';
const ROOM_NAME = process.env.LIVEKIT_ROOM || 'test-room';
const PARTICIPANT_NAME = process.env.PARTICIPANT_NAME || 'raspberry-pi';

let tokenServer = null;
let browser = null;
let page = null;

// Find Chromium executable (common locations on Raspberry Pi)
function findChromium() {
  const possiblePaths = [
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium',
    '/snap/bin/chromium',
    '/usr/bin/google-chrome',
  ];
  
  for (const path of possiblePaths) {
    try {
      if (fs.existsSync(path)) {
        return path;
      }
    } catch (e) {
      // Continue searching
    }
  }
  
  throw new Error(
    'Chromium not found. Install with: sudo apt install chromium-browser\n' +
    'Or set CHROMIUM_PATH environment variable'
  );
}

// Start the token server
async function startTokenServer() {
  return new Promise((resolve, reject) => {
    console.log('🚀 Starting token server...');
    
    tokenServer = spawn('node', ['server.js'], {
      cwd: WEB_CLIENT_DIR,
      env: {
        ...process.env,
        LIVEKIT_URL,
        LIVEKIT_API_KEY,
        LIVEKIT_API_SECRET,
        PORT: '8080',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    
    let serverReady = false;
    
    tokenServer.stdout.on('data', (data) => {
      const output = data.toString();
      console.log(`[Token Server] ${output.trim()}`);
      if (output.includes('Token server running')) {
        serverReady = true;
        resolve();
      }
    });
    
    tokenServer.stderr.on('data', (data) => {
      console.error(`[Token Server Error] ${data.toString().trim()}`);
    });
    
    tokenServer.on('error', (error) => {
      console.error('❌ Failed to start token server:', error);
      reject(error);
    });
    
    tokenServer.on('exit', (code) => {
      if (code !== 0 && !serverReady) {
        reject(new Error(`Token server exited with code ${code}`));
      }
    });
    
    // Give server a moment to start
    setTimeout(() => {
      if (!serverReady) {
        console.log('⚠️  Token server may not be ready, continuing anyway...');
        resolve();
      }
    }, 3000);
  });
}

// Launch headless browser
async function launchBrowser() {
  console.log('🌐 Launching headless browser...');
  
  const chromiumPath = process.env.CHROMIUM_PATH || findChromium();
  console.log(`   Using Chromium at: ${chromiumPath}`);
  
  browser = await puppeteer.launch({
    executablePath: chromiumPath,
    headless: true, // Set to false for debugging
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--no-first-run',
      '--no-zygote',
      '--disable-gpu',
      // Audio flags - critical for microphone/speaker access
      '--use-fake-ui-for-media-stream', // Auto-allow microphone
      '--use-fake-device-for-media-stream', // Use fake devices (for testing)
      // OR use real devices:
      // '--allow-file-access-from-files',
      // '--use-file-for-fake-audio-capture=/path/to/test.wav', // Optional: test audio
    ],
    ignoreDefaultArgs: ['--mute-audio'], // Don't mute audio
  });
  
  console.log('✅ Browser launched');
  return browser;
}

// Navigate to web client and connect
async function connectToAgent() {
  console.log('📱 Loading web client...');
  
  // Build the web client first (or serve it)
  // For dev mode, we'll use the Vite dev server
  // For production, build first: cd web-client && npm run build
  
  const devMode = process.env.DEV_MODE !== 'false';
  const url = devMode 
    ? 'http://localhost:5173' // Vite dev server
    : `file://${join(WEB_CLIENT_DIR, 'dist', 'index.html')}`;
  
  page = await browser.newPage();
  
  // Set viewport
  await page.setViewport({ width: 800, height: 600 });
  
  // Grant permissions for microphone
  const context = browser.defaultBrowserContext();
  await context.overridePermissions(url, ['microphone', 'camera']);
  
  // Listen for console messages
  page.on('console', (msg) => {
    const type = msg.type();
    const text = msg.text();
    if (type === 'error') {
      console.error(`[Browser Console Error] ${text}`);
    } else if (type === 'warning') {
      console.warn(`[Browser Console] ${text}`);
    } else {
      console.log(`[Browser Console] ${text}`);
    }
  });
  
  // Listen for page errors
  page.on('pageerror', (error) => {
    console.error(`[Page Error] ${error.message}`);
  });
  
  // Navigate to the page
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
  console.log('✅ Page loaded');
  
  // Wait for the connect button to be available
  await page.waitForSelector('#connectBtn', { timeout: 10000 });
  console.log('✅ UI ready');
  
  // Auto-click connect button
  console.log('🔌 Connecting to agent...');
  await page.click('#connectBtn');
  
  // Wait for connection status
  await page.waitForFunction(
    () => {
      const status = document.getElementById('status');
      return status && status.className.includes('connected');
    },
    { timeout: 30000 }
  );
  
  console.log('✅ Connected to agent!');
  console.log('🎤 Microphone is active - start speaking!');
  console.log('   Press Ctrl+C to disconnect\n');
}

// Cleanup
async function cleanup() {
  console.log('\n🛑 Shutting down...');
  
  if (page) {
    try {
      // Try to disconnect gracefully
      const disconnectBtn = await page.$('#disconnectBtn');
      if (disconnectBtn) {
        await disconnectBtn.click();
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    } catch (e) {
      // Ignore errors during cleanup
    }
    await page.close();
  }
  
  if (browser) {
    await browser.close();
  }
  
  if (tokenServer) {
    tokenServer.kill();
  }
  
  console.log('👋 Goodbye!');
  process.exit(0);
}

// Main function
async function main() {
  try {
    // Start token server
    await startTokenServer();
    
    // Launch browser
    await launchBrowser();
    
    // Connect to agent
    await connectToAgent();
    
    // Keep running until interrupted
    process.on('SIGINT', cleanup);
    process.on('SIGTERM', cleanup);
    
    // Keep the process alive
    await new Promise(() => {}); // Run forever
    
  } catch (error) {
    console.error('❌ Error:', error);
    await cleanup();
    process.exit(1);
  }
}

// Run
main();

