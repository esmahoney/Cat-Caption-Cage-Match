#!/bin/bash
# Interactive API test script for Cat Caption Cage Match
# Usage: ./test_api.sh

BASE_URL="http://localhost:8000"
echo "🐱 Cat Caption Cage Match API Test"
echo "=================================="
echo ""

# Check if server is running
echo "1. Checking server health..."
HEALTH=$(curl -s "$BASE_URL/api/health")
echo "   Response: $HEALTH"
echo ""

# Create a session
echo "2. Creating a new session..."
CREATE_RESPONSE=$(curl -s -X POST "$BASE_URL/api/sessions" \
  -H "Content-Type: application/json" \
  -d '{"host_display_name": "TestHost", "settings": {"rounds_total": 3}}')
echo "   Response: $CREATE_RESPONSE"

# Extract session code and host token
SESSION_CODE=$(echo $CREATE_RESPONSE | grep -o '"session_code":"[^"]*"' | cut -d'"' -f4)
HOST_TOKEN=$(echo $CREATE_RESPONSE | grep -o '"player_token":"[^"]*"' | cut -d'"' -f4)
HOST_ID=$(echo $CREATE_RESPONSE | grep -o '"player_id":"[^"]*"' | head -1 | cut -d'"' -f4)

echo ""
echo "   📋 Session Code: $SESSION_CODE"
echo "   🔑 Host Token: $HOST_TOKEN"
echo ""

# Get session state
echo "3. Getting session state..."
STATE=$(curl -s "$BASE_URL/api/sessions/$SESSION_CODE")
echo "   Players: $(echo $STATE | grep -o '"display_name":"[^"]*"' | cut -d'"' -f4)"
echo ""

# Join as another player
echo "4. Joining as Player2..."
JOIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/sessions/$SESSION_CODE/players" \
  -H "Content-Type: application/json" \
  -d '{"display_name": "Player2"}')
PLAYER2_TOKEN=$(echo $JOIN_RESPONSE | grep -o '"player_token":"[^"]*"' | cut -d'"' -f4)
PLAYER2_ID=$(echo $JOIN_RESPONSE | grep -o '"player_id":"[^"]*"' | cut -d'"' -f4)
echo "   Player2 joined!"
echo ""

# Start a round
echo "5. Starting round 1 (as host)..."
ROUND_RESPONSE=$(curl -s -X POST "$BASE_URL/api/sessions/$SESSION_CODE/rounds" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $HOST_TOKEN" \
  -d '{}')
ROUND_ID=$(echo $ROUND_RESPONSE | grep -o '"round_id":"[^"]*"' | cut -d'"' -f4)
IMAGE_URL=$(echo $ROUND_RESPONSE | grep -o '"image_url":"[^"]*"' | cut -d'"' -f4)
echo "   🐱 Cat image: $IMAGE_URL"
echo "   Round ID: $ROUND_ID"
echo ""

# Submit captions
echo "6. Submitting captions..."
echo "   Host caption: 'When the WiFi goes down for 5 seconds'"
curl -s -X POST "$BASE_URL/api/sessions/$SESSION_CODE/rounds/$ROUND_ID/captions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $HOST_TOKEN" \
  -d '{"text": "When the WiFi goes down for 5 seconds"}' > /dev/null

echo "   Player2 caption: 'Me watching my human work from home'"
curl -s -X POST "$BASE_URL/api/sessions/$SESSION_CODE/rounds/$ROUND_ID/captions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $PLAYER2_TOKEN" \
  -d '{"text": "Me watching my human work from home"}' > /dev/null
echo "   Both captions submitted!"
echo ""

# Reveal results
echo "7. Revealing round results..."
REVEAL_RESPONSE=$(curl -s -X POST "$BASE_URL/api/sessions/$SESSION_CODE/rounds/$ROUND_ID/reveal" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $HOST_TOKEN")
echo ""
echo "   📊 Results:"
echo "$REVEAL_RESPONSE" | grep -o '"display_name":"[^"]*","text":"[^"]*"[^}]*"score":{[^}]*}' | while read line; do
  NAME=$(echo $line | grep -o '"display_name":"[^"]*"' | cut -d'"' -f4)
  TEXT=$(echo $line | grep -o '"text":"[^"]*"' | cut -d'"' -f4)
  TOTAL=$(echo $line | grep -o '"total":[0-9]*' | cut -d':' -f2)
  ROAST=$(echo $line | grep -o '"roast":"[^"]*"' | cut -d'"' -f4)
  echo "   - $NAME ($TOTAL pts): \"$TEXT\""
  echo "     🔥 $ROAST"
done
echo ""

# Final leaderboard
echo "8. Final Leaderboard:"
echo "$REVEAL_RESPONSE" | grep -o '"leaderboard":\[[^]]*\]' | grep -o '"display_name":"[^"]*","total_score":[0-9]*' | while read line; do
  NAME=$(echo $line | grep -o '"display_name":"[^"]*"' | cut -d'"' -f4)
  SCORE=$(echo $line | grep -o '"total_score":[0-9]*' | cut -d':' -f2)
  echo "   🏆 $NAME: $SCORE pts"
done
echo ""

echo "✅ API test complete!"
echo ""
echo "Try it yourself:"
echo "  - Swagger UI: $BASE_URL/docs"
echo "  - Session: $BASE_URL/api/sessions/$SESSION_CODE"

