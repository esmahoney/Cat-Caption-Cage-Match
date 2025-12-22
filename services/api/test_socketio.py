#!/usr/bin/env python3
"""
Test Socket.IO realtime events.

This script connects to the Socket.IO server and listens for events
while you interact with the REST API in another terminal.

Usage:
    1. Start the server: ./venv/bin/python run.py
    2. Run this test: ./venv/bin/python test_socketio.py
    3. In another terminal, run: ./test_api.sh
    4. Watch events appear in this terminal!
"""
import socketio
import asyncio
import sys

# Create Socket.IO client
sio = socketio.AsyncClient(logger=False)

SESSION_CODE = None


@sio.event
async def connect():
    print("✅ Connected to Socket.IO server")


@sio.event
async def disconnect():
    print("❌ Disconnected from server")


@sio.on("session:state")
async def on_session_state(data):
    """Fired when session state changes (player joins, status changes)."""
    players = [p["display_name"] for p in data.get("players", [])]
    status = data.get("session", {}).get("status", "?")
    print(f"\n📡 session:state")
    print(f"   Status: {status}")
    print(f"   Players: {', '.join(players)}")


@sio.on("round:started")
async def on_round_started(data):
    """Fired when host starts a new round."""
    round_data = data.get("round", {})
    print(f"\n🎬 round:started")
    print(f"   Round #{round_data.get('number')}")
    print(f"   Image: {round_data.get('image_url', '')[:50]}...")


@sio.on("caption:locked")
async def on_caption_locked(data):
    """Fired when a player submits their caption."""
    print(f"\n✍️  caption:locked")
    print(f"   Player: {data.get('playerId', '?')[:20]}...")
    print(f"   Submitted: {data.get('submitted')}")


@sio.on("round:revealed")
async def on_round_revealed(data):
    """Fired when host reveals round results."""
    print(f"\n🏆 round:revealed")
    captions = data.get("captions", [])
    for c in captions:
        score = c.get("score", {})
        print(f"   {c.get('display_name')}: {score.get('total', 0)} pts")
        print(f"      \"{c.get('text', '')}\"")
        print(f"      🔥 {score.get('roast', '')}")


@sio.on("error")
async def on_error(data):
    """Server error."""
    print(f"\n⚠️  error: {data}")


async def join_session(session_code: str):
    """Join a session room to receive events."""
    print(f"\n🚪 Joining session: {session_code}")
    response = await sio.call("session:join", {
        "sessionCode": session_code,
        "playerToken": "",  # Just observing, no auth needed
    })
    
    if response.get("ok"):
        state = response.get("state", {})
        players = [p["display_name"] for p in state.get("players", [])]
        print(f"   Joined! Current players: {', '.join(players)}")
        return True
    else:
        print(f"   Failed: {response.get('error')}")
        return False


async def main():
    global SESSION_CODE
    
    print("=" * 50)
    print("🐱 Cat Caption Cage Match - Socket.IO Test Client")
    print("=" * 50)
    
    # Get session code from command line or prompt
    if len(sys.argv) > 1:
        SESSION_CODE = sys.argv[1].upper()
    else:
        print("\nFirst, create a session with the REST API:")
        print("  curl -X POST http://localhost:8000/api/sessions \\")
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"host_display_name": "TestHost"}\'')
        print()
        SESSION_CODE = input("Enter session code to observe: ").strip().upper()
    
    if not SESSION_CODE:
        print("No session code provided. Exiting.")
        return
    
    try:
        # Connect to server
        print(f"\n🔌 Connecting to http://localhost:8000...")
        await sio.connect("http://localhost:8000", transports=["websocket"])
        
        # Join session room
        if not await join_session(SESSION_CODE):
            await sio.disconnect()
            return
        
        print("\n" + "=" * 50)
        print("👀 Listening for events... (Ctrl+C to quit)")
        print("   Try these in another terminal:")
        print(f"   - Join: curl -X POST localhost:8000/api/sessions/{SESSION_CODE}/players ...")
        print(f"   - Start round: curl -X POST localhost:8000/api/sessions/{SESSION_CODE}/rounds ...")
        print("=" * 50)
        
        # Keep running until interrupted
        await sio.wait()
        
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        if sio.connected:
            await sio.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

