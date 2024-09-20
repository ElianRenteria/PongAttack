import random
from fastapi import FastAPI, WebSocket
import json
import asyncio

app = FastAPI()

players = {}
enemies = [
    {"x": 200, "y": 200, "dx": 2, "dy": 2},
    {"x": 600, "y": 400, "dx": -3, "dy": -3},
]

def random_color():
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

async def move_enemies():
    while True:
        for enemy in enemies:
            # Update enemy position
            enemy["x"] += enemy["dx"]
            enemy["y"] += enemy["dy"]

            # Bounce off the walls
            if enemy["x"] <= 0 or enemy["x"] >= 780:  # Canvas width minus enemy radius
                enemy["dx"] *= -1  # Reverse horizontal direction

            if enemy["y"] <= 0 or enemy["y"] >= 580:  # Canvas height minus enemy radius
                enemy["dy"] *= -1  # Reverse vertical direction

        # Broadcast updated positions to all clients
        await broadcast_positions()
        await asyncio.sleep(0.016)  # Approx 60 updates per second


@app.websocket("/ws/{player_name}")
async def websocket_endpoint(websocket: WebSocket, player_name: str):
    await websocket.accept()

    # Initialize player
    player_id = id(websocket)
    players[player_id] = {
        "x": 100,
        "y": 100,
        "id": player_id,
        "color": random_color(),
        "name": player_name,
        "score": 0,
        "websocket": websocket
    }

    # Start a task to update the player's score
    asyncio.create_task(update_score(player_id))

    # Send initial positions to the player
    await send_initial_positions(websocket)

    try:
        while True:
            # Receive movement direction from the client
            data = await websocket.receive_text()
            move = json.loads(data)

            if move["direction"] == "left":
                players[player_id]["x"] -= 5
            elif move["direction"] == "right":
                players[player_id]["x"] += 5
            elif move["direction"] == "up":
                players[player_id]["y"] -= 5
            elif move["direction"] == "down":
                players[player_id]["y"] += 5
                
            players[player_id]["x"] = max(0, min(780, players[player_id]["x"]))  # 800 - player width (20)
            players[player_id]["y"] = max(0, min(580, players[player_id]["y"]))  # 600 - player height (20)


            # Check for collisions with enemy balls
            if check_collision(players[player_id]):
                # print(f"Collision detected for player: {player_name}")
                
                # Remove player from players dictionary
                if player_id in players:
                    del players[player_id]  # Remove player on collision

                # Send redirect message and close WebSocket
                await websocket.send_text(json.dumps({"action": "redirect", "url": "/index.html"}))
                await websocket.close()  # Close the WebSocket connection
                break  # Exit the loop to stop further processing

            # Broadcast updated positions to all clients
            await broadcast_positions()

    except Exception as e:
        print(f"Error: {e}")
        # Ensure player is removed from dictionary if an error occurs
        if player_id in players:
            del players[player_id]
        await websocket.close()



async def update_score(player_id):
    while player_id in players:
        players[player_id]["score"] += 1
        await asyncio.sleep(1)

async def send_initial_positions(websocket: WebSocket):
    safe_players = [
        {"x": player["x"], "y": player["y"], "color": player["color"], "name": player["name"], "score": player["score"]}
        for player in players.values()
    ]
    data = json.dumps({"players": safe_players, "enemies": enemies})
    await websocket.send_text(data)

async def broadcast_positions():
    safe_players = [
        {"x": player["x"], "y": player["y"], "color": player["color"], "name": player["name"], "score": player["score"]}
        for player in players.values()
    ]
    data = json.dumps({"players": safe_players, "enemies": enemies})

    for player in players.values():
        try:
            await player["websocket"].send_text(data)
        except Exception as e:
            print(f"Error sending data to player: {e}")

def check_collision(player):
    player_radius = 10  # Assuming the player is represented as a square of size 20x20
    for enemy in enemies:
        enemy_radius = 10  # Assuming the enemy is represented as a circle with radius 10
        if (abs((player["x"] + player_radius) - (enemy["x"])) <= (player_radius + enemy_radius) and
            abs((player["y"] + player_radius) - (enemy["y"])) <= (player_radius + enemy_radius)):
            return True
    return False

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(move_enemies())  # Start enemy movement when the server starts

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
