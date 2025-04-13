import { type ActionFunctionArgs } from '@remix-run/cloudflare';

export const PYTHON_BACKEND_URL = 'http://localhost:8000/api/chat';

export async function action({ request }: ActionFunctionArgs) {
    try {
      const pythonResponse = await fetch(PYTHON_BACKEND_URL, {
        method: 'POST',
        body: await request.text(),
        headers: { 
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
      });
  
      if (!pythonResponse.ok || !pythonResponse.body) {
        throw new Error(`Backend request failed: ${pythonResponse.status}`);
      }
  
      return new Response(pythonResponse.body, {
        status: pythonResponse.status,
        headers: { 
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
      });
    } catch (error) {
      console.error('Error in chat action:', error);
      return new Response(JSON.stringify({ error: 'Failed to process request' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  }