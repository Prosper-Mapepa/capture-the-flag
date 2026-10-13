# Chippewa Squirrel Rescue

A beginner club game. CTFd (`ctfd/ctfd`) keeps the scoreboard, teams, and flags. A second page plays Acorn Hall: a student runs up, the door opens, and the snack closet either frees the trapped Chippewa squirrels or the acorn alarm sends them scattering.

Red and Blue are scoreboard lanes in a race. Both lanes solve the same rescue. This is not a live network attack-defense range.

The closet box is a labeled game prop. Do not try this on a real building, and do not give players this folder. The answer key is printed when you seed the scoreboard.

## Start

Docker Desktop needs to be running.

```bash
cp .env.example .env
docker compose up -d --build
python3 ctfd/seed.py
```

- Scoreboard: http://localhost:8000
- Rescue simulator: http://localhost:8080
- Organizer login: the user and password in `.env` (`CTFD_ADMIN_USER`, `CTFD_ADMIN_PASSWORD`)

`python3 ctfd/seed.py` prints the door PIN, closet code, and flags. Run it before players are looking at the screen.

## How a player moves through it

1. Open the scoreboard. It walks through how the game works, your name, Red or Blue, and Start.
2. Solve **Squirrel Door Note** (Caesar cipher) and type the PIN on the simulator.
3. Copy the door flag back to that challenge.
4. Solve **Snack Closet Log** (read the log, decode base64) before walking inside.
5. Type the closet code. Three wrong full codes, or the five-minute timer, plays the squirrels-scattered scene. The right code frees the squirrels and shows the second flag.

The jersey buttons only change the runner's color.

## Room laptops

`localhost` works on the machine running Docker. For other laptops, set `SCENARIO_URL` and `SCOREBOARD_URL` in `.env` to this computer's LAN address, then:

```bash
docker compose up -d
python3 ctfd/seed.py
```

Keep the scoreboard on the club network. The database password is only inside Docker and port 3306 is not published.

## Change the codes

Edit `DOOR_CODE` and `DISARM_CODE` in `.env`. Both values are 4 to 8 digits. Then recreate the simulator and seed again:

```bash
docker compose up -d --build
python3 ctfd/seed.py
```

## Start the event over

This deletes teams, scores, and the CTFd database volume.

```bash
docker compose down -v
docker compose up -d --build
python3 ctfd/seed.py
```
