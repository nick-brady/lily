import { useState, useEffect, useRef } from 'react';

const WS_URL = import.meta.env.DEV
  ? 'ws://localhost:8000/ws'
  : `wss://${window.location.host}/ws`;

export function useWebSocket(onMessage, onReconnect) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const reconnectAttemptRef = useRef(0);
  const hasConnectedBeforeRef = useRef(false);
  const onMessageRef = useRef(onMessage);
  const onReconnectRef = useRef(onReconnect);

  // Keep refs updated
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    onReconnectRef.current = onReconnect;
  }, [onReconnect]);

  useEffect(() => {
    let mounted = true;

    const connect = () => {
      if (!mounted) return;
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      // Clean up any existing connection
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      try {
        const ws = new WebSocket(WS_URL);

        ws.onopen = () => {
          if (!mounted) return;
          setIsConnected(true);

          // If this is a reconnection, trigger data refresh
          if (hasConnectedBeforeRef.current) {
            onReconnectRef.current?.();
          }
          hasConnectedBeforeRef.current = true;
          reconnectAttemptRef.current = 0;

          // Start ping interval to keep connection alive
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send('ping');
            }
          }, 30000);
        };

        ws.onclose = () => {
          if (!mounted) return;
          setIsConnected(false);
          clearInterval(pingIntervalRef.current);

          // Reconnect with exponential backoff
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), 30000);
          reconnectAttemptRef.current += 1;

          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          // Don't close here - onclose will be called automatically
        };

        ws.onmessage = (event) => {
          if (event.data === 'pong') return;

          try {
            const data = JSON.parse(event.data);
            onMessageRef.current?.(data);
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
          }
        };

        wsRef.current = ws;
      } catch (e) {
        console.error('WebSocket connection failed:', e);
        // Try to reconnect
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), 30000);
        reconnectAttemptRef.current += 1;
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      }
    };

    connect();

    return () => {
      mounted = false;
      clearTimeout(reconnectTimeoutRef.current);
      clearInterval(pingIntervalRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []); // Empty dependency array - only run once

  return { isConnected };
}
