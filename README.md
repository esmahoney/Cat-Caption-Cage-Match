# 🐈‍⬛🎤 Cat Caption Cage Match

An AI-powered party game where players write meme captions for random cat pictures and have them judged by Google's Gemini AI. Perfect for Zoom calls, parties, or any time you need some competitive cat comedy!

## 🎮 How It Works

1. **Round Start**: A random cat image appears
2. **Caption Time**: Players write funny captions (15 words max)
3. **AI Judgment**: Gemini rates each caption 0-10 for humor and relevance
4. **Scoreboard**: Points accumulate across rounds
5. **Victory**: Whoever has the most points after 5 rounds wins!

## 🚀 Quick Start

### Prerequisites
- Python 3.13.4 (or compatible version)
- Google API Key for Gemini AI
- TheCatAPI key (optional but recommended)

### Installation

1. **Activate the virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Get your API keys:**
   - **Google GenAI API Key**: Get it from [AI Studio](https://makersuite.google.com/app/apikey)
   - **TheCatAPI Key**: Get it from [TheCatAPI](https://thecatapi.com/) (optional)

### Usage

Run the Cat Caption Cage Match game:
```bash
python main.py
```

This launches a web interface that you can share with friends!

## 🎯 Game Features

- **Real-time web interface** powered by Gradio
- **AI-powered judging** using Gemini 2.5 Pro
- **Live scoreboard** with DuckDB backend
- **Random cat images** from TheCatAPI
- **Multiplayer support** - share the link with friends
- **Mobile-friendly** interface

## 📁 Project Structure

```
Cat Caption Cage Match/
├── venv/                # Virtual environment
├── main.py              # Cat Caption Cage Match game
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## 🎭 Game Rules

- **Caption Length**: 15 words maximum
- **Scoring**: AI rates 0-10 based on humor and relevance
- **Rounds**: Typically 5 rounds (customizable)
- **Players**: Unlimited (just share the web link)
- **Judging**: AI is ruthless but fair - "Cat Meme Gordon Ramsay" style

## 🔧 Technical Details

- **Frontend**: Gradio web interface
- **Backend**: Python with DuckDB for scoring
- **AI Model**: Google Gemini 2.5 Pro for text, Gemini Pro Vision for image analysis
- **Image Source**: TheCatAPI for random cat pictures
- **Deployment**: Can run locally or in Google Colab

## 🚨 Troubleshooting

- **"No API key"**: Make sure to set your `GOOGLE_API_KEY` environment variable
- **Images not loading**: Check your internet connection or TheCatAPI key
- **AI scoring issues**: The game includes fallback scoring to keep things moving

## 🎉 Perfect For

- Virtual team building
- Zoom party games
- Ice breakers
- Cat lovers
- Anyone who enjoys competitive creativity!

Ready to find out who's the ultimate cat caption champion? Let the cage match begin! 🏆