# %% [markdown]
# # Cat-Caption Cage-Match 🐈‍⬛🎤
#
# A lightweight, browser-based party game that lets players write meme captions for random cat
# pictures and have them judged by Gemini 2.5 Pro.  Designed to run entirely from a single
# Google Colab notebook (or Jupytext‑synced .py file).  Keep the scope surgical: five rounds,
# one winner, then nuke the VM.
#
# ---
# **Quick‑start**
# 1. Run the first two cells to install deps and set your API keys.
# 2. Press ▶️ on every remaining cell *once*.
# 3. When the Gradio UI pops, share the public link in Zoom / Slack.
# 4. Click **Next Round** → everyone types a caption → AI scores → scoreboard updates.
#
# Rage‑quit factor minimal; laughs mandatory.
# ---

# %% [markdown]
# ## 0  Install dependencies
# (Colab resets every 12 h, so this cell runs each session.)

# %%
!pip install --quiet google-genai-sdk==0.3.2 gradio duckdb pillow requests

# %% [markdown]
# ## 1  Environment setup
# Put secrets in RAM, never in Git.

# %%
import os, getpass, textwrap, io, requests, random, duckdb
from urllib.parse import urlparse

# Gemini / Dev API key
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("🔑  Enter Google GenAI API key: ")

# TheCatAPI key is optional for public endpoints, but safer to add one.
if "THECATAPI_KEY" not in os.environ:
    os.environ["THECATAPI_KEY"] = getpass.getpass("🔑  Enter TheCatAPI key (or hit Enter to skip): ")

# %% [markdown]
# ## 2  Imports & helpers

# %%
import gradio as gr
from google.genai import GenerativeModel
from PIL import Image

model   = GenerativeModel("gemini-2.5-pro")    # text judge
vision  = GenerativeModel("gemini-pro-vision") # multimodal judge

con = duckdb.connect()
con.execute("""
CREATE TABLE IF NOT EXISTS scores (
    round INT,
    player VARCHAR,
    caption VARCHAR,
    score INT
);
""")

# --- Image utilities ---------------------------------------------------------
CAT_API = "https://api.thecatapi.com/v1/images/search?size=med&mime_types=jpg"

def fetch_random_cat() -> Image.Image:
    """Grab a cat picture and return as PIL.Image."""
    headers = {"x-api-key": os.environ.get("THECATAPI_KEY", "")}
    data = requests.get(CAT_API, headers=headers, timeout=10).json()[0]
    url = data["url"]
    img_bytes = requests.get(url, timeout=10).content
    return Image.open(io.BytesIO(img_bytes))

# --- Scoring -----------------------------------------------------------------
judge_prompt = textwrap.dedent(
    """
    You are Cat Meme Gordon Ramsay. Rate the caption below on a scale of 0–10 for humour and relevance to the picture.
    Be ruthless. Reply **only** with the integer score. No additional text.
    """
)

def score_caption(image: Image.Image, caption: str) -> int:
    """Call Gemini to get a numeric score."""
    try:
        resp = vision.generate_content([
            image,
            judge_prompt + "\\nCAPTION: " + caption
        ])
        # Extract first integer 0‑10
        for tok in resp.text.split():
            if tok.isdigit():
                return max(0, min(10, int(tok)))
    except Exception as e:
        print("Gemini error:", e)
    return random.randint(1, 5)  # fallback so game never stalls

# %% [markdown]
# ## 3  Gradio interface

# %%
current_round = 0
current_image = None

def new_round():
    global current_round, current_image
    current_round += 1
    current_image = fetch_random_cat()
    buf = io.BytesIO()
    current_image.save(buf, format="JPEG")
    buf.seek(0)
    return current_round, buf

round_num, img_buf = new_round()

def submit_caption(player_name, caption):
    score = score_caption(current_image, caption)
    con.execute(
        "INSERT INTO scores VALUES (?, ?, ?, ?)",
        [round_num, player_name.strip() or "Anon", caption.strip(), score]
    )
    df = con.execute("SELECT player, SUM(score) AS total FROM scores GROUP BY player ORDER BY total DESC").df()
    leaderboard_md = "\\n".join([f"**{p}** – {s}" for p, s in df.values]) or "_No scores yet_"
    return f"Gemini gave you **{score}/10**", leaderboard_md

with gr.Blocks(title="Cat-Caption Cage-Match") as demo:
    gr.Markdown("## 🐱 Cat-Caption Cage-Match")
    image_comp = gr.Image(value=img_buf, label="Fresh feline – craft your meme!")
    with gr.Row():
        player_name = gr.Textbox(label="Your name", placeholder="e.g. Alice")
        caption_box = gr.Textbox(label="Caption", placeholder="15 words max…")
    submit_btn = gr.Button("Submit 🏹")
    result = gr.Markdown()
    leaderboard = gr.Markdown("_Scores will appear here_", elem_id="board")
    next_btn = gr.Button("Next Round 🔄")

    submit_btn.click(submit_caption, inputs=[player_name, caption_box], outputs=[result, leaderboard])

    def advance_round():
        rnd, buf = new_round()
        caption_box.value = ""
        result.value = ""
        return {image_comp: buf, leaderboard: leaderboard.value}

    next_btn.click(advance_round, outputs=[image_comp, leaderboard])

demo.launch(share=True)

# %% [markdown]
# ## 4  Shutdown / export (optional)
# Save the scoreboard to Drive or commit to Git if you care.
