import os
import re

from flask import Flask, jsonify, render_template_string, request
from groq import Groq

app = Flask(__name__)

# Klucz API pobieramy ze zmiennej środowiskowej.
# Lokalnie możesz ustawić:
#   Linux/macOS: export GROQ_API_KEY="..."
#   Windows PowerShell: $env:GROQ_API_KEY="..."
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("Brak zmiennej środowiskowej GROQ_API_KEY.")

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_TEMPLATE = """Jesteś Mistrzem Gry RPG w uniwersum {uniwersum}.

W grze bierze udział wielu graczy: {gracze}. Każdy z nich wykonuje ruchy po kolei.

{instrukcja_wieku}

Zasady główne:

1. Reaguj na decyzje konkretnych graczy. Nie pisz dialogów ani akcji za graczy.
2. Odpowiedzi muszą być zwięzłe (maksymalnie 1 krótki akapit, 2-3 zdania).
3. Na SAMEGO KOŃCA swojej odpowiedzi MUSISZ podać dokładnie 3 sugerowane opcje wyboru dla graczy, zapisane dokładnie w takim formacie:

[OPCJA 1] Tutaj krótka akcja do wyboru A
[OPCJA 2] Tutaj krótka akcja do wyboru B
[OPCJA 3] Tutaj krótka akcja do wyboru C

4. Po opcjach, w nowej linii wyświetl prosty pasek zdrowia (HP startowe każdego gracza to 100) i złota (startowe 50 monet):

STATYSTYKI: Gracz1 (HP: 100, Złoto: 50) | Gracz2...
"""

HTML = """
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Sztuczny Mistrz Gry RPG</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            background: #202124;
            color: #f5f5f5;
            font-family: Arial, sans-serif;
        }
        .container {
            max-width: 900px;
            margin: 30px auto;
            padding: 20px;
        }
        .card {
            background: #2c2c2c;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
        }
        h1 { margin-top: 0; }
        label { display: block; margin: 12px 0 6px; }
        input, select, button {
            width: 100%;
            padding: 10px;
            border-radius: 6px;
            border: 1px solid #555;
            font-size: 15px;
        }
        button {
            cursor: pointer;
            background: #4caf50;
            color: white;
            border: none;
            margin-top: 10px;
        }
        button:hover { opacity: 0.9; }
        .message {
            padding: 12px;
            margin: 10px 0;
            border-radius: 8px;
            background: #383838;
            white-space: pre-wrap;
        }
        .gm { border-left: 4px solid #ffd700; }
        .player { border-left: 4px solid #2196f3; }
        .options button {
            background: #444;
            text-align: left;
        }
        .hidden { display: none; }
        .hud {
            background: #1b1b1b;
            padding: 12px;
            border-radius: 8px;
            margin: 12px 0;
            font-family: monospace;
        }
        .custom {
            display: flex;
            gap: 8px;
        }
        .custom input { flex: 1; }
        .custom button { width: 120px; margin-top: 0; }
        .error { color: #ff8a80; }
    </style>
</head>
<body>
<div class="container">
    <div id="setup" class="card">
        <h1>🎲 Sztuczny Mistrz Gry RPG</h1>

        <label>Liczba graczy</label>
        <select id="playerCount" onchange="renderNames()">
            <option>1</option>
            <option>2</option>
            <option>3</option>
            <option>4</option>
        </select>

        <div id="names"></div>

        <label>Kategoria wiekowa</label>
        <select id="age">
            <option>Do 10 lat</option>
            <option>Do 18 lat</option>
            <option selected>18+</option>
        </select>

        <label>Uniwersum gry</label>
        <select id="setting">
            <option>Dark Fantasy</option>
            <option>Cyberpunk</option>
            <option>Sci-Fi / Kosmos</option>
        </select>

        <button onclick="startGame()">ROZPOCZNIJ PRZYGODĘ</button>
        <p id="setupError" class="error"></p>
    </div>

    <div id="game" class="card hidden">
        <h1>🎲 Sztuczny Mistrz Gry RPG</h1>
        <div id="turn"></div>
        <div id="history"></div>
        <div id="hud" class="hud"></div>

        <div id="options" class="options"></div>

        <div class="custom">
            <input id="customAction" placeholder="Wpisz własną akcję...">
            <button onclick="sendCustom()">Wyślij</button>
        </div>
    </div>
</div>

<script>
let state = null;

function renderNames() {
    const count = Number(document.getElementById("playerCount").value);
    const container = document.getElementById("names");
    container.innerHTML = "";

    for (let i = 0; i < count; i++) {
        container.innerHTML += `
            <label>Imię gracza ${i + 1}</label>
            <input id="player-${i}" value="Bohater ${i + 1}">
        `;
    }
}

function addMessage(author, text, type) {
    const history = document.getElementById("history");
    const div = document.createElement("div");
    div.className = "message " + type;
    div.textContent = author + ": " + text;
    history.appendChild(div);
    window.scrollTo(0, document.body.scrollHeight);
}

function renderResponse(data) {
    if (data.error) {
        addMessage("Błąd", data.error, "error");
        return;
    }

    state = data.state;

    document.getElementById("turn").textContent =
        "TERAZ RUCH WYKONUJE: " + state.players[state.current_player].toUpperCase();

    document.getElementById("hud").textContent = data.stats || "";

    addMessage("Mistrz Gry", data.story, "gm");

    const options = document.getElementById("options");
    options.innerHTML = "";

    data.options.forEach((option, index) => {
        const button = document.createElement("button");
        button.textContent = option;
        button.onclick = () => sendAction(option);
        options.appendChild(button);
    });
}

async function startGame() {
    const count = Number(document.getElementById("playerCount").value);
    const players = [];

    for (let i = 0; i < count; i++) {
        players.push(document.getElementById("player-" + i).value.trim());
    }

    const payload = {
        players,
        age: document.getElementById("age").value,
        setting: document.getElementById("setting").value
    };

    document.getElementById("setupError").textContent = "";

    const response = await fetch("/api/start", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (data.error) {
        document.getElementById("setupError").textContent = data.error;
        return;
    }

    document.getElementById("setup").classList.add("hidden");
    document.getElementById("game").classList.remove("hidden");
    renderResponse(data);
}

async function sendAction(action) {
    addMessage(state.players[state.current_player], action, "player");

    const response = await fetch("/api/action", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({action, state})
    });

    renderResponse(await response.json());
}

function sendCustom() {
    const input = document.getElementById("customAction");
    const action = input.value.trim();

    if (!action) return;

    input.value = "";
    sendAction(action);
}

renderNames();
</script>
</body>
</html>
"""


def age_instruction(age):
    if age == "Do 10 lat":
        return (
            "Gra jest dla dzieci do lat 10. Styl musi być baśniowy, bezpieczny, "
            "pozbawiony brutalności, krwi i strachu. Przyjazny klimat."
        )
    if age == "Do 18 lat":
        return (
            "Gra dla młodzieży. Klasyczna przygoda fantasy/sci-fi, ekscytująca, "
            "akcja i walka, ale bez skrajnej wulgarności i gore."
        )
    return (
        "Gra dla dorosłych (18+). Świat może być brutalny, mroczny, krwawy, "
        "opisy mogą być dosadne i przerażające."
    )


def parse_response(text):
    options = []
    for number in (1, 2, 3):
        match = re.search(
            rf"\[OPCJA {number}\]\s*(.*?)(?=\n\[OPCJA|\nSTATYSTYKI:|$)",
            text,
            re.DOTALL,
        )
        options.append(match.group(1).strip() if match else f"Opcja {number}")

    stats_match = re.search(r"STATYSTYKI:(.*)", text, re.DOTALL)
    stats = f"STATYSTYKI:{stats_match.group(1).strip()}" if stats_match else ""

    story = text.split("[OPCJA 1]")[0].split("STATYSTYKI:")[0].strip()

    return story, options, stats


def ask_ai(messages):
    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        temperature=0.7,
        max_tokens=400,
    )
    return completion.choices[0].message.content


def build_response(state, ai_text):
    story, options, stats = parse_response(ai_text)
    return jsonify(
        {
            "story": story,
            "options": options,
            "stats": stats,
            "state": state,
        }
    )


@app.get("/")
def index():
    return render_template_string(HTML)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/start")
def start_game():
    data = request.get_json(silent=True) or {}

    players = [p.strip() for p in data.get("players", []) if p.strip()]
    age = data.get("age", "18+")
    setting = data.get("setting", "Dark Fantasy")

    if not 1 <= len(players) <= 4:
        return jsonify({"error": "Wybierz od 1 do 4 graczy."}), 400

    system_prompt = SYSTEM_TEMPLATE.format(
        uniwersum=setting,
        gracze=", ".join(players),
        instrukcja_wieku=age_instruction(age),
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Wszyscy gracze ({', '.join(players)}) budzą się razem "
                "w lokacji początkowej. Przedstaw sytuację i podaj opcje."
            ),
        },
    ]

    ai_text = ask_ai(messages)

    state = {
        "players": players,
        "current_player": 0,
        "messages": messages + [{"role": "assistant", "content": ai_text}],
    }

    return build_response(state, ai_text)


@app.post("/api/action")
def action():
    data = request.get_json(silent=True) or {}
    state = data.get("state")
    action_text = (data.get("action") or "").strip()

    if not state or not action_text:
        return jsonify({"error": "Brak danych akcji."}), 400

    players = state.get("players", [])
    current_player = int(state.get("current_player", 0))

    if not players:
        return jsonify({"error": "Brak graczy."}), 400

    player = players[current_player]
    messages = state.get("messages", [])

    messages.append(
        {
            "role": "user",
            "content": f"Gracz {player} wykonuje akcję: {action_text}",
        }
    )

    ai_text = ask_ai(messages)
    messages.append({"role": "assistant", "content": ai_text})

    state["current_player"] = (current_player + 1) % len(players)
    state["messages"] = messages

    return build_response(state, ai_text)


if __name__ == "__main__":
    # 0.0.0.0 jest ważne dla Dockera/AWS.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
