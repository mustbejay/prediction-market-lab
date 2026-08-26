#!/usr/bin/env python3
"""WebSocket client for Limitless Exchange real-time updates."""

import json
import asyncio
import websockets
import ssl
from datetime import datetime, timezone


class LimitlessWebSocket:
    """WebSocket client for Limitless Exchange market data."""
    
    WS_URL = "wss://ws.limitless.exchange/markets"
    
    def __init__(self):
        self.websocket = None
        self.connected = False
        self.callbacks = []
    
    async def connect(self):
        """Connect to WebSocket server."""
        try:
            ssl_context = ssl.create_default_context()
            self.websocket = await websockets.connect(
                self.WS_URL,
                ssl=ssl_context,
                ping_interval=30,
                ping_timeout=10,
            )
            self.connected = True
            print(f"[WS] Connected to {self.WS_URL}", flush=True)
            return True
        except Exception as e:
            print(f"[WS] Connection error: {e}", flush=True)
            return False
    
    async def disconnect(self):
        """Close WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            print("[WS] Disconnected", flush=True)
    
    async def subscribe(self, token_ids: list[str]):
        """Subscribe to market updates for specific tokens."""
        if not self.connected or not self.websocket:
            return False
        
        message = {
            "type": "subscribe",
            "assets_ids": token_ids,
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            print(f"[WS] Subscribed to {len(token_ids)} tokens", flush=True)
            return True
        except Exception as e:
            print(f"[WS] Subscribe error: {e}", flush=True)
            return False
    
    async def unsubscribe(self, token_ids: list[str]):
        """Unsubscribe from market updates."""
        if not self.connected or not self.websocket:
            return False
        
        message = {
            "type": "unsubscribe",
            "assets_ids": token_ids,
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            print(f"[WS] Unsubscribed from {len(token_ids)} tokens", flush=True)
            return True
        except Exception as e:
            print(f"[WS] Unsubscribe error: {e}", flush=True)
            return False
    
    def on_message(self, callback):
        """Register a message callback."""
        self.callbacks.append(callback)
    
    async def listen(self):
        """Listen for incoming messages."""
        if not self.connected:
            return
        
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    for cb in self.callbacks:
                        await cb(data)
                except json.JSONDecodeError:
                    print(f"[WS] Invalid JSON: {message}", flush=True)
        except websockets.exceptions.ConnectionClosed:
            print("[WS] Connection closed", flush=True)
            self.connected = False
        except Exception as e:
            print(f"[WS] Listen error: {e}", flush=True)
            self.connected = False


async def test_websocket():
    """Test WebSocket connection."""
    ws = LimitlessWebSocket()
    
    if await ws.connect():
        print("[TEST] Connection successful", flush=True)
        
        # Subscribe to a test token
        await ws.subscribe(["47208185759397782964540450098808759766808391005268026685955781381747593241293"])
        
        # Listen for messages
        async def handler(data):
            print(f"[TEST] Received: {json.dumps(data, indent=2)[:500]}", flush=True)
        
        ws.on_message(handler)
        
        # Keep connected for 10 seconds
        import time
        for _ in range(10):
            await asyncio.sleep(1)
            if not ws.connected:
                break
        
        await ws.disconnect()
    else:
        print("[TEST] Connection failed", flush=True)


if __name__ == "__main__":
    asyncio.run(test_websocket())
