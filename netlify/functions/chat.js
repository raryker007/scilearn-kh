// netlify/functions/chat.js
// Secure Netlify serverless function — proxies requests to Google Gemini API.
// Your GEMINI_API_KEY is stored as a Netlify environment variable (never in frontend code).

const SYSTEM_INSTRUCTION = `
You are Prof. Gemini, an expert science teacher specializing in Grade 11 high school curriculum in Cambodia.

YOUR ROLE:
- Teach Physics, Chemistry, Biology, and Mathematics at Grade 11 level.
- Give clear, structured, step-by-step explanations.
- Use simple language first, then introduce technical terms with definitions.
- Always show worked examples when solving problems.
- Encourage students with positive, supportive language.

TEACHING STYLE:
- Break down complex topics into numbered steps.
- Use analogies to real-world situations the student knows.
- When solving math/physics problems, show every step clearly.
- End explanations with a short summary or key takeaway.
- Ask a follow-up question to check understanding when appropriate.

STRICT BOUNDARIES:
- ONLY answer questions related to: Physics, Chemistry, Biology, Mathematics (Grade 11 curriculum).
- If asked about anything outside these subjects (politics, entertainment, coding unrelated to science, etc.), 
  politely decline: "I'm specialized for Grade 11 science subjects only. Please ask me about Physics, Chemistry, Biology, or Math!"
- Do not write essays, stories, or general knowledge content.
- Do not provide answers to exam questions without explanation — always teach, never just give answers.

FORMATTING:
- Use **bold** for key terms and important concepts.
- Use numbered lists for steps in problem-solving.
- Use simple formulas inline like: F = ma, E = mc²
- Keep responses concise but complete (aim for 150–400 words).
`;

exports.handler = async (event) => {
  // ── CORS headers ──────────────────────────────────────────────
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Content-Type': 'application/json',
  };

  // Handle preflight
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers, body: '' };
  }

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers, body: JSON.stringify({ error: 'Method not allowed' }) };
  }

  // ── Parse request ─────────────────────────────────────────────
  let subject, history;
  try {
    ({ subject, history } = JSON.parse(event.body));
  } catch {
    return { statusCode: 400, headers, body: JSON.stringify({ error: 'Invalid request body' }) };
  }

  // ── Build Gemini API request ───────────────────────────────────
  const API_KEY = process.env.GEMINI_API_KEY;
  if (!API_KEY) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'API key not configured. Add GEMINI_API_KEY to Netlify environment variables.' }) };
  }

  const MODEL = 'gemini-1.5-flash'; // fast + free tier
  const API_URL = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${API_KEY}`;

  // Inject subject context into the last user message
  const enrichedHistory = history.map((msg, idx) => {
    if (idx === history.length - 1 && msg.role === 'user') {
      return {
        ...msg,
        parts: [{ text: `[Subject: ${subject}]\n\n${msg.parts[0].text}` }]
      };
    }
    return msg;
  });

  const geminiPayload = {
    system_instruction: {
      parts: [{ text: SYSTEM_INSTRUCTION }]
    },
    contents: enrichedHistory,
    generationConfig: {
      temperature: 0.7,
      topP: 0.85,
      maxOutputTokens: 1024,
    },
    safetySettings: [
      { category: 'HARM_CATEGORY_HARASSMENT', threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
      { category: 'HARM_CATEGORY_HATE_SPEECH', threshold: 'BLOCK_MEDIUM_AND_ABOVE' },
    ],
  };

  // ── Call Gemini ────────────────────────────────────────────────
  try {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(geminiPayload),
    });

    const data = await response.json();

    if (!response.ok) {
      const errMsg = data?.error?.message || 'Gemini API error';
      return { statusCode: response.status, headers, body: JSON.stringify({ error: errMsg }) };
    }

    const reply = data?.candidates?.[0]?.content?.parts?.[0]?.text || 'No response from AI.';
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ reply }),
    };

  } catch (err) {
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: `Network error: ${err.message}` }),
    };
  }
};
