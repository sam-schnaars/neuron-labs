// Simple Express server for generating LiveKit access tokens
// Run with: node server.js

import express from 'express';
import { AccessToken } from 'livekit-server-sdk';
import { RoomConfiguration, RoomAgentDispatch } from '@livekit/protocol';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(cors());
app.use(express.json());

// Serve static files from parent directory (for keith-pic.jpeg)
app.use(express.static(path.join(__dirname, '..')));

const LIVEKIT_URL = process.env.LIVEKIT_URL || 'ws://localhost:7880';
const LIVEKIT_API_KEY = process.env.LIVEKIT_API_KEY || 'devkey';
const LIVEKIT_API_SECRET = process.env.LIVEKIT_API_SECRET || 'secret';

app.post('/api/token', async (req, res) => {
  try {
    const { room, name } = req.body;

    if (!room || !name) {
      return res.status(400).json({ error: 'Room and name are required' });
    }

    console.log(`Generating token for room: ${room}, name: ${name}`);
    console.log('API Key:', LIVEKIT_API_KEY.substring(0, 5) + '...');
    console.log('API Secret:', LIVEKIT_API_SECRET.substring(0, 5) + '...');

    const at = new AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET, {
      identity: name,
    });

    // Add grant using plain object (this is the correct format)
    at.addGrant({
      roomJoin: true,
      room: room,
      canPublish: true,
      canSubscribe: true,
    });

    // Dispatch agent on participant connection (docs: room_config is used when room is created;
    // use unique room name per connection so each connect gets a new room and agent dispatch)
    at.roomConfig = new RoomConfiguration({
      agents: [
        new RoomAgentDispatch({ agentName: 'investobot' }),
      ],
    });

    console.log('AccessToken created, calling toJwt()...');

    // Call toJwt() - it should return a string
    let token;
    try {
      token = at.toJwt();
      console.log('toJwt() returned, type:', typeof token);
      console.log('toJwt() value preview:', JSON.stringify(token).substring(0, 100));
      
      // If it returns a Promise, await it
      if (token && typeof token.then === 'function') {
        console.log('Token is a Promise, awaiting...');
        token = await token;
      }
      
      // Check if it's actually the token object instead of string
      if (token && typeof token === 'object' && !Array.isArray(token)) {
        console.error('toJwt() returned an object instead of string:', token);
        // Try accessing a property if it exists
        if (token.token) {
          console.log('Found token.token property, using that');
          token = token.token;
        } else {
          throw new Error('toJwt() returned an object but no token property found');
        }
      }
    } catch (jwtError) {
      console.error('Error calling toJwt():', jwtError);
      console.error('Error stack:', jwtError instanceof Error ? jwtError.stack : 'No stack');
      throw jwtError;
    }
    
    // Verify token is a string
    if (!token || typeof token !== 'string') {
      console.error('Token is not a string! Type:', typeof token, 'Value:', token);
      throw new Error(`Token generation failed: expected string, got ${typeof token}. Value: ${JSON.stringify(token)}`);
    }
    
    console.log('Token generated successfully, length:', token.length);
    console.log('Token preview:', token.substring(0, 30) + '...');

    // Ensure we're sending a proper JSON response
    res.setHeader('Content-Type', 'application/json');
    res.json({ token: token });
  } catch (error) {
    console.error('Error generating token:', error);
    console.error('Error stack:', error instanceof Error ? error.stack : 'No stack');
    res.status(500).json({ error: 'Failed to generate token: ' + (error instanceof Error ? error.message : 'Unknown error') });
  }
});

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', livekit_url: LIVEKIT_URL });
});

// Pitches: list all saved pitch transcripts (newest first)
const MEMORY_ROOT = path.join(__dirname, '..', 'conversation_memory');
app.get('/api/pitches', (req, res) => {
  try {
    const list = [];
    if (!fs.existsSync(MEMORY_ROOT)) {
      return res.json({ pitches: [] });
    }
    const sessionDirs = fs.readdirSync(MEMORY_ROOT, { withFileTypes: true })
      .filter(d => d.isDirectory())
      .map(d => d.name);
    for (const sessionId of sessionDirs) {
      const pitchesDir = path.join(MEMORY_ROOT, sessionId, sessionId, 'pitches');
      if (!fs.existsSync(pitchesDir)) continue;
      const files = fs.readdirSync(pitchesDir)
        .filter(f => f.endsWith('.md') && (f.startsWith('pitch_') || /^pitch \d+\.md$/.test(f)));
      for (const filename of files) {
        const filepath = path.join(pitchesDir, filename);
        const stat = fs.statSync(filepath);
        let description = '';
        let score = 0;
        try {
          const raw = fs.readFileSync(filepath, 'utf-8');
          const lines = raw.split('\n');
          const firstLine = lines[0]?.trim() || '';
          if (firstLine && !firstLine.startsWith('#') && firstLine.length < 200) {
            description = firstLine;
          }
          // Second line: "score: 0.75" (dynamic; a separate ranking algorithm can overwrite this in the file)
          const scoreLine = lines[1]?.trim() || '';
          const scoreMatch = scoreLine.match(/^score:\s*([\d.]+)/i);
          if (scoreMatch) score = parseFloat(scoreMatch[1], 10) || 0;
        } catch (_) { /* ignore */ }
        if (!description) description = filename.replace(/^pitch_|\.md$/g, '').replace(/_/g, ' ') || 'Pitch';
        list.push({
          id: `${sessionId}/${filename}`,
          sessionId,
          filename,
          description,
          score,
          savedAt: stat.mtime.toISOString(),
        });
      }
    }
    list.sort((a, b) => (b.score - a.score) || (new Date(b.savedAt) - new Date(a.savedAt)));
    res.json({ pitches: list });
  } catch (err) {
    console.error('Error listing pitches:', err);
    res.status(500).json({ error: 'Failed to list pitches', pitches: [] });
  }
});

// Pitches: get one pitch transcript content
app.get('/api/pitch', (req, res) => {
  try {
    const { session: sessionId, filename } = req.query;
    if (!sessionId || !filename || typeof sessionId !== 'string' || typeof filename !== 'string') {
      return res.status(400).json({ error: 'session and filename required' });
    }
    if (filename.includes('..') || sessionId.includes('..')) {
      return res.status(400).json({ error: 'Invalid path' });
    }
    const filepath = path.join(MEMORY_ROOT, sessionId, sessionId, 'pitches', filename);
    if (!fs.existsSync(filepath)) {
      return res.status(404).json({ error: 'Pitch not found' });
    }
    const content = fs.readFileSync(filepath, 'utf-8');
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.send(content);
  } catch (err) {
    console.error('Error reading pitch:', err);
    res.status(500).json({ error: 'Failed to read pitch' });
  }
});

// Serve Keith's image directly
app.get('/keith-pic.jpeg', (req, res) => {
  const imagePath = path.join(__dirname, '..', 'keith-pic.jpeg');
  if (fs.existsSync(imagePath)) {
    res.sendFile(imagePath);
  } else {
    res.status(404).json({ error: 'Image not found' });
  }
});

// Parse markdown to extract translations
function parseTranslations(markdownContent) {
  const translations = [];
  
  // Pattern 1: Match bullet points with Japanese and English in parentheses
  // Examples: "- Menu o kudasai (Menu, please)" or "• Menu o kudasai (Menu, please)"
  // This pattern matches: dash/bullet, optional whitespace, Japanese text, space, parentheses with English
  const bulletPattern = /[-•]\s+([^(\n]+?)\s+\(([^)]+)\)/g;
  
  // Pattern 2: Match quoted phrases with translations
  // Examples: "Menu o kudasai" (Menu, please) or "Menu o kudasai (Menu, please)"
  const quotedPattern = /["']([^"']+?)["']\s*\(([^)]+)\)/g;
  
  // Pattern 3: Match "Key Phrases" sections (including in code blocks)
  // This matches the entire code block or section containing "Key Phrases"
  const keyPhrasesPattern = /```[\s\S]*?\*\*Key.*?Phrases.*?:\*\*[\s\S]*?```/gi;
  
  // Pattern 4: Match "Key Phrases" sections outside code blocks
  const keyPhrasesOutsidePattern = /\*\*Key.*?Phrases.*?:\*\*\s*\n((?:[-•\s].*?\n)+)/gis;
  
  let match;
  
  // First, extract from code blocks containing "Key Phrases"
  while ((match = keyPhrasesPattern.exec(markdownContent)) !== null) {
    const block = match[0];
    // Remove the code block markers
    const content = block.replace(/```/g, '');
    let phraseMatch;
    // Reset regex lastIndex for bulletPattern
    bulletPattern.lastIndex = 0;
    while ((phraseMatch = bulletPattern.exec(content)) !== null) {
      const japanese = phraseMatch[1].trim();
      const english = phraseMatch[2].trim();
      if (japanese && english && japanese.length > 2) {
        translations.push({ japanese, english });
      }
    }
  }
  
  // Extract from regular "Key Phrases" sections (not in code blocks)
  while ((match = keyPhrasesOutsidePattern.exec(markdownContent)) !== null) {
    const phrasesBlock = match[1];
    bulletPattern.lastIndex = 0;
    let phraseMatch;
    while ((phraseMatch = bulletPattern.exec(phrasesBlock)) !== null) {
      const japanese = phraseMatch[1].trim();
      const english = phraseMatch[2].trim();
      if (japanese && english && japanese.length > 2) {
        translations.push({ japanese, english });
      }
    }
  }
  
  // Extract quoted phrases with translations
  quotedPattern.lastIndex = 0;
  while ((match = quotedPattern.exec(markdownContent)) !== null) {
    const japanese = match[1].trim();
    const english = match[2].trim();
    if (japanese && english && japanese.length > 2) {
      translations.push({ japanese, english });
    }
  }
  
  // Extract from progress notes (e.g., "User nailed: 'Ramen to ocha onegai shimasu'")
  const progressPattern = /(?:nailed|practiced|learned|mastered|repeated).*?["']([^"']{5,})["']/gi;
  while ((match = progressPattern.exec(markdownContent)) !== null) {
    const japanese = match[1].trim();
    if (japanese.length > 4) {
      // Try to find translation in nearby context (within 500 chars)
      const contextStart = Math.max(0, match.index - 500);
      const contextEnd = Math.min(markdownContent.length, match.index + match[0].length + 500);
      const context = markdownContent.substring(contextStart, contextEnd);
      
      // Look for translation patterns near the phrase
      const escapedJapanese = japanese.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const translationPatterns = [
        new RegExp(`"${escapedJapanese}"[^)]*\\(([^)]+)\\)`),
        new RegExp(`'${escapedJapanese}'[^)]*\\(([^)]+)\\)`),
        new RegExp(`[-•]\\s+${escapedJapanese}\\s+\\(([^)]+)\\)`),
      ];
      
      let foundTranslation = false;
      for (const pattern of translationPatterns) {
        const transMatch = context.match(pattern);
        if (transMatch) {
          translations.push({ japanese, english: transMatch[1].trim() });
          foundTranslation = true;
          break;
        }
      }
    }
  }
  
  // Extract standalone bullet points with translations (anywhere in the document)
  bulletPattern.lastIndex = 0;
  while ((match = bulletPattern.exec(markdownContent)) !== null) {
    const japanese = match[1].trim();
    const english = match[2].trim();
    if (japanese && english && japanese.length > 2) {
      translations.push({ japanese, english });
    }
  }
  
  // Remove duplicates and clean up
  const uniqueTranslations = [];
  const seen = new Set();
  for (const trans of translations) {
    // Clean up the Japanese text (remove extra quotes, trim)
    const cleanJapanese = trans.japanese.replace(/^["']|["']$/g, '').trim();
    const cleanEnglish = trans.english.trim();
    
    if (cleanJapanese.length > 2 && cleanEnglish.length > 2) {
      const key = cleanJapanese.toLowerCase();
      if (!seen.has(key)) {
        seen.add(key);
        uniqueTranslations.push({ 
          japanese: cleanJapanese, 
          english: cleanEnglish 
        });
      }
    }
  }
  
  // Sort by Japanese text
  uniqueTranslations.sort((a, b) => a.japanese.localeCompare(b.japanese));
  
  return uniqueTranslations;
}

// Get translations from markdown files
app.get('/api/translations', async (req, res) => {
  try {
    const { room = 'test-room' } = req.query;
    
    // Path to conversation memory directory
    // server.js is in web-client/, so go up one level to Grokie/, then into conversation_memory
    // Try multiple path resolutions in case __dirname doesn't work as expected
    let memoryPath = path.join(__dirname, '..', 'conversation_memory', room, room);
    
    // Fallback: try from process.cwd() if the first path doesn't exist
    if (!fs.existsSync(path.join(memoryPath, 'conversation_history.md'))) {
      const altPath = path.join(process.cwd(), '..', 'conversation_memory', room, room);
      if (fs.existsSync(path.join(altPath, 'conversation_history.md'))) {
        memoryPath = altPath;
      }
    }
    
    const conversationFile = path.join(memoryPath, 'conversation_history.md');
    const customNotesFile = path.join(memoryPath, 'custom_notes.md');
    
    console.log('Looking for translations in:');
    console.log('  __dirname:', __dirname);
    console.log('  process.cwd():', process.cwd());
    console.log('  Memory path:', memoryPath);
    console.log('  Conversation file:', conversationFile);
    console.log('  Custom notes file:', customNotesFile);
    console.log('  Conversation exists:', fs.existsSync(conversationFile));
    console.log('  Custom notes exists:', fs.existsSync(customNotesFile));
    
    let allTranslations = [];
    
    // Read conversation history
    if (fs.existsSync(conversationFile)) {
      try {
        const conversationContent = fs.readFileSync(conversationFile, 'utf-8');
        console.log('  Conversation file size:', conversationContent.length, 'chars');
        const convTranslations = parseTranslations(conversationContent);
        console.log('  Found', convTranslations.length, 'translations in conversation history');
        if (convTranslations.length > 0) {
          console.log('  Sample translations:', convTranslations.slice(0, 3));
        }
        allTranslations = allTranslations.concat(convTranslations);
      } catch (err) {
        console.error('  Error reading conversation file:', err);
        console.error('  Error stack:', err.stack);
      }
    } else {
      console.log('  Conversation file not found at:', conversationFile);
      // Try to list what's in the parent directory
      const parentDir = path.dirname(memoryPath);
      if (fs.existsSync(parentDir)) {
        console.log('  Parent directory exists, contents:', fs.readdirSync(parentDir));
      }
    }
    
    // Read custom notes
    if (fs.existsSync(customNotesFile)) {
      try {
        const notesContent = fs.readFileSync(customNotesFile, 'utf-8');
        console.log('  Custom notes file size:', notesContent.length, 'chars');
        const notesTranslations = parseTranslations(notesContent);
        console.log('  Found', notesTranslations.length, 'translations in custom notes');
        if (notesTranslations.length > 0) {
          console.log('  Sample translations:', notesTranslations.slice(0, 3));
        }
        allTranslations = allTranslations.concat(notesTranslations);
      } catch (err) {
        console.error('  Error reading custom notes file:', err);
        console.error('  Error stack:', err.stack);
      }
    } else {
      console.log('  Custom notes file not found at:', customNotesFile);
    }
    
    // Remove duplicates again after combining
    const uniqueTranslations = [];
    const seen = new Set();
    for (const trans of allTranslations) {
      const key = trans.japanese.toLowerCase();
      if (!seen.has(key)) {
        seen.add(key);
        uniqueTranslations.push(trans);
      }
    }
    
    console.log('  Total unique translations:', uniqueTranslations.length);
    res.json({ translations: uniqueTranslations });
  } catch (error) {
    console.error('Error fetching translations:', error);
    console.error('Stack:', error.stack);
    res.status(500).json({ error: 'Failed to fetch translations: ' + error.message, translations: [] });
  }
});

// Get markdown file
app.get('/api/markdown/:fileType', async (req, res) => {
  try {
    const { fileType } = req.params;
    const { room = 'test-room' } = req.query;
    
    if (!['lesson_plan', 'custom_notes', 'conversation_history'].includes(fileType)) {
      return res.status(400).json({ error: 'Invalid file type' });
    }
    
    // conversation_history is read-only via GET, but can be saved via POST
    
    // Map fileType to actual filename
    const fileMap = {
      'lesson_plan': 'lesson_plan.md',
      'custom_notes': 'custom_notes.md',
      'conversation_history': 'conversation_history.md'
    };
    
    const filename = fileMap[fileType];
    
    // Path to conversation memory directory
    let memoryPath = path.join(__dirname, '..', 'conversation_memory', room, room);
    
    // Fallback: try from process.cwd() if the first path doesn't exist
    if (!fs.existsSync(path.join(memoryPath, filename))) {
      const altPath = path.join(process.cwd(), '..', 'conversation_memory', room, room);
      if (fs.existsSync(path.join(altPath, filename))) {
        memoryPath = altPath;
      }
    }
    
    const filePath = path.join(memoryPath, filename);
    
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: 'File not found' });
    }
    
    const content = fs.readFileSync(filePath, 'utf-8');
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.send(content);
  } catch (error) {
    console.error('Error reading markdown file:', error);
    res.status(500).json({ error: 'Failed to read file: ' + error.message });
  }
});

// Save markdown file
app.post('/api/markdown/:fileType', async (req, res) => {
  try {
    const { fileType } = req.params;
    const { room = 'test-room' } = req.query;
    const { content } = req.body;
    
    if (!['lesson_plan', 'custom_notes', 'conversation_history'].includes(fileType)) {
      return res.status(400).json({ error: 'Invalid file type' });
    }
    
    if (typeof content !== 'string') {
      return res.status(400).json({ error: 'Content must be a string' });
    }
    
    // Map fileType to actual filename
    const fileMap = {
      'lesson_plan': 'lesson_plan.md',
      'custom_notes': 'custom_notes.md',
      'conversation_history': 'conversation_history.md'
    };
    
    const filename = fileMap[fileType];
    
    // Path to conversation memory directory
    let memoryPath = path.join(__dirname, '..', 'conversation_memory', room, room);
    
    // Fallback: try from process.cwd() if the first path doesn't exist
    const altPath = path.join(process.cwd(), '..', 'conversation_memory', room, room);
    if (!fs.existsSync(memoryPath) && fs.existsSync(altPath)) {
      memoryPath = altPath;
    }
    
    // Ensure directory exists
    if (!fs.existsSync(memoryPath)) {
      fs.mkdirSync(memoryPath, { recursive: true });
    }
    
    const filePath = path.join(memoryPath, filename);
    
    // Write file
    fs.writeFileSync(filePath, content, 'utf-8');
    
    console.log(`Saved ${fileType} for room ${room}`);
    res.json({ success: true, message: 'File saved successfully' });
  } catch (error) {
    console.error('Error saving markdown file:', error);
    res.status(500).json({ error: 'Failed to save file: ' + error.message });
  }
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`Token server running on http://localhost:${PORT}`);
  console.log(`LiveKit URL: ${LIVEKIT_URL}`);
});

