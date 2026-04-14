// netlify/functions/chat.js
// SciLearn KH — Gemini 2.0 Flash API with 10-Key Rotation

// ─────────────────────────────────────────────
// SYSTEM INSTRUCTION — Define the AI's personality here
// ─────────────────────────────────────────────
const SYSTEM_INSTRUCTION = `You are SciLearn, an expert and friendly Science teacher 
for Grade 11 students in Cambodia. You specialize in Mathematics, Physics, Chemistry, 
and Biology. Always explain concepts clearly using simple language, real-world examples 
relevant to Cambodian students, and step-by-step reasoning. If a student seems confused, 
encourage them warmly and try a different explanation approach. Never give direct answers 
to homework — guide students to discover the answer themselves through Socratic questioning.
Respond in the same language the student uses (Khmer or English).`;

// ─────────────────────────────────────────────
// CORS HEADERS — Allow your frontend to call this function
// ─────────────────────────────────────────────
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",        // Replace * with your domain in production
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

// ─────────────────────────────────────────────
// LOAD ALL 10 API KEYS from Netlify environment variables
// ─────────────────────────────────────────────
const apiKeys = [
  process.env.GEMINI_API_KEY_1,
  process.env.GEMINI_API_KEY_2,
  process.env.GEMINI_API_KEY_3,
  process.env.GEMINI_API_KEY_4,
  process.env.GEMINI_API_KEY_5,
  process.env.GEMINI_API_KEY_6,
  process.env.GEMINI_API_KEY_7,
  process.env.GEMINI_API_KEY_8,
  process.env.GEMINI_API_KEY_9,
  process.env.GEMINI_API_KEY_10,
].filter(Boolean); // Removes any undefined keys (e.g. if you have fewer than 10)

const GEMINI_MODEL = "gemini-2.0-flash";
const GEMINI_API_URL = (apiKey) =>
  `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`;

// ─────────────────────────────────────────────
// MAIN HANDLER
// ─────────────────────────────────────────────
exports.handler = async (event) => {

  // Handle preflight CORS request from the browser
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers: CORS_HEADERS, body: "" };
  }

  // Only allow POST requests
  if (event.httpMethod !== "POST") {
    return {
      statusCode: 405,
      headers: CORS_HEADERS,
      body: JSON.stringify({ error: "Method Not Allowed. Use POST." }),
    };
  }

  // Parse the request body from your frontend
  let userMessage;
  let conversationHistory = []; // Optional: for multi-turn chat support

  try {
    const body = JSON.parse(event.body);
    userMessage = body.message;
    conversationHistory = body.history || []; // Pass previous turns if needed
  } catch {
    return {
      statusCode: 400,
      headers: CORS_HEADERS,
      body: JSON.stringify({ error: "Invalid JSON in request body." }),
    };
  }

  if (!userMessage || typeof userMessage !== "string" || !userMessage.trim()) {
    return {
      statusCode: 400,
      headers: CORS_HEADERS,
      body: JSON.stringify({ error: "Request body must include a non-empty 'message' field." }),
    };
  }

  // Build enrichedHistory — combines past conversation turns with the new user message
  const enrichedHistory = [
    ...conversationHistory, // Previous messages: [{ role: "user", parts: [...] }, ...]
    { role: "user", parts: [{ text: userMessage }] },
  ];

  // ─────────────────────────────────────────────
  // KEY ROTATION LOOP — for...of iterates the apiKeys array
  // ─────────────────────────────────────────────
  // Each iteration tries one key. On any failure (429, 500, network error),
  // `continue` skips to the next key automatically.
  // A successful response triggers an immediate `return`, exiting the loop.
  // If every key fails, execution falls through to the final 503 fallback below.

  let lastError = null;
  let keyIndex = 0;

  for (const currentKey of apiKeys) {
    keyIndex++;
    const keyLabel = `GEMINI_API_KEY_${keyIndex}`; // For readable logging

    try {
      console.log(`[SciLearn] Attempting request with ${keyLabel}...`);

      const response = await fetch(GEMINI_API_URL(currentKey), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          system_instruction: {
            parts: [{ text: SYSTEM_INSTRUCTION }],
          },
          contents: enrichedHistory,
          generationConfig: {
            temperature: 0.7,       // Balanced: creative but accurate
            maxOutputTokens: 1024,  // Adjust as needed
            topP: 0.9,
          },
        }),
      });

      // If the API returned an HTTP error (e.g. 429 Quota, 500, 403 Invalid Key)
      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        const errorMessage = errorBody?.error?.message || `HTTP ${response.status}`;
        console.warn(`[SciLearn] ${keyLabel} failed (${response.status}): ${errorMessage}`);

        // Save the error and continue to the next key in apiKeys
        lastError = new Error(`${keyLabel} → ${errorMessage}`);
        continue; // ← Jump to next key in for...of
      }

      // ✅ SUCCESS — Parse and return the response
      const data = await response.json();
      const replyText = data?.candidates?.[0]?.content?.parts?.[0]?.text;

      if (!replyText) {
        // The API responded but with no usable content (e.g. safety filter block)
        const finishReason = data?.candidates?.[0]?.finishReason || "UNKNOWN";
        console.warn(`[SciLearn] ${keyLabel} returned empty content. Reason: ${finishReason}`);
        return {
          statusCode: 200,
          headers: CORS_HEADERS,
          body: JSON.stringify({
            reply: "I'm sorry, I wasn't able to generate a response for that. Please try rephrasing your question.",
            finishReason: finishReason,
          }),
        };
      }

      console.log(`[SciLearn] ✅ Success with ${keyLabel}`);
      return {
        statusCode: 200,
        headers: CORS_HEADERS,
        body: JSON.stringify({ reply: replyText }),
      };

    } catch (networkError) {
      // Catches network/DNS/timeout failures
      console.error(`[SciLearn] Network error with ${keyLabel}:`, networkError.message);
      lastError = networkError;
      continue; // ← Jump to next key in for...of
    }
  }

  // ─────────────────────────────────────────────
  // ALL KEYS EXHAUSTED — Return a friendly error
  // ─────────────────────────────────────────────
  console.error("[SciLearn] ❌ All API keys have been exhausted.", lastError?.message);
  return {
    statusCode: 503,
    headers: CORS_HEADERS,
    body: JSON.stringify({
      error: "The service is temporarily unavailable due to high demand. Please try again in a moment.",
      detail: lastError?.message || "All API keys exhausted.",
    }),
  };
};
