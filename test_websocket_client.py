#!/usr/bin/env python
"""
Simple WebSocket test client for testing real-time preview functionality

Usage:
    python test_websocket_client.py [step_file_path]
"""

import asyncio
import websockets
import json
import base64
import sys
import os
from pathlib import Path

async def test_websocket_connection(step_file_path: str = None):
    """Test WebSocket connection and message handling"""
    
    uri = "ws://localhost:8001/ws/preview"
    
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected successfully!")
            
            # Wait for connection status message
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📥 Received: {data['type']}")
            
            if data['type'] == 'connection_status':
                print(f"   Client ID: {data['data']['client_id']}")
                print(f"   OpenCASCADE: {data['data']['opencascade_available']}")
            
            # Test ping-pong
            print("\n🏓 Testing ping...")
            await websocket.send(json.dumps({
                "type": "ping",
                "data": {}
            }))
            
            response = await websocket.recv()
            data = json.loads(response)
            if data['type'] == 'pong':
                print("✅ Pong received!")
            
            # If STEP file provided, test model update
            if step_file_path and os.path.exists(step_file_path):
                print(f"\n📁 Loading STEP file: {step_file_path}")
                
                with open(step_file_path, 'rb') as f:
                    step_data = f.read()
                    encoded_data = base64.b64encode(step_data).decode('utf-8')
                
                print("📤 Sending model update...")
                await websocket.send(json.dumps({
                    "type": "update_model",
                    "data": {
                        "model": encoded_data,
                        "parameters": {
                            "scale_factor": 10.0,
                            "layout_mode": "canvas",
                            "page_format": "A4",
                            "max_faces": 20
                        }
                    }
                }))
                
                # Wait for processing status
                while True:
                    response = await websocket.recv()
                    data = json.loads(response)
                    print(f"📥 Received: {data['type']}")
                    
                    if data['type'] == 'status':
                        print(f"   Status: {data['data']['status']}")
                        print(f"   Message: {data['data'].get('message', '')}")
                    
                    elif data['type'] == 'preview_update':
                        print("✅ SVG preview received!")
                        print(f"   Stats: {data['data']['stats']}")
                        
                        # Save SVG to file
                        output_path = "websocket_test_output.svg"
                        with open(output_path, 'w') as f:
                            f.write(data['data']['svg'])
                        print(f"   SVG saved to: {output_path}")
                        
                        # Test parameter update
                        print("\n🔄 Testing parameter update...")
                        await websocket.send(json.dumps({
                            "type": "update_parameters",
                            "data": {
                                "parameters": {
                                    "scale_factor": 20.0,
                                    "layout_mode": "paged",
                                    "page_format": "A3"
                                }
                            }
                        }))
                    
                    elif data['type'] == 'error':
                        print(f"❌ Error: {data['data']['message']}")
                        break
                    
                    # Check for parameter update response
                    if data['type'] == 'preview_update' and data['data'].get('cached'):
                        print("✅ Cached parameter update successful!")
                        break
            
            else:
                print("\n⚠️  No STEP file provided. Skipping model test.")
                print("   Usage: python test_websocket_client.py [step_file_path]")
            
            print("\n🔌 Closing connection...")
    
    except websockets.exceptions.ConnectionRefused:
        print("❌ Connection refused. Is the server running?")
        print("   Run: python main.py")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main entry point"""
    # Get STEP file path from command line argument
    step_file_path = None
    if len(sys.argv) > 1:
        step_file_path = sys.argv[1]
        if not os.path.exists(step_file_path):
            print(f"❌ File not found: {step_file_path}")
            return
    else:
        # Try to find a test STEP file
        test_files = list(Path("core/debug_files").glob("*.step"))
        if test_files:
            step_file_path = str(test_files[0])
            print(f"📁 Using test file: {step_file_path}")
    
    # Run the test
    asyncio.run(test_websocket_connection(step_file_path))

if __name__ == "__main__":
    main()