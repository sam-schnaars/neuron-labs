// Simple Express server for generating LiveKit access tokens
// Run with: node server.js

import express from 'express';
import { AccessToken } from 'livekit-server-sdk';
import cors from 'cors';

const app = express();
app.use(cors());
app.use(express.json());

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

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`Token server running on http://localhost:${PORT}`);
  console.log(`LiveKit URL: ${LIVEKIT_URL}`);
});

