# Discord Trade Bot

A Discord bot for grading fantasy football trades using real-time player valuations from FantasyCalc.

## Features

- **Trade Grading**: Compare player values between two teams in a trade
- **Player Lookup**: Check individual player valuations
- **Fuzzy Matching**: Handles typos and special characters in player names (e.g., "Jamar Chase" finds "Ja'mar Chase")
- **Auto Caching**: Caches player values for 6 hours to minimize API calls
- **Smart Dependency Management**: Automatically installs required packages on startup

## Requirements

- Python 3.8+
- Discord.py
- Requests
- Python-dotenv

## Setup

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/discord_trade_bot.git
   cd discord_trade_bot
   ```

2. **Create a `.env` file**
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` and add your Discord bot token:
   ```
   DISCORD_BOT_TOKEN=your_actual_bot_token_here
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the bot**
   ```bash
   python discrod_trade_bot.py
   ```

You should see `[BotName] is online!` in the console when the bot starts successfully.

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a **New Application**
3. Go to the **Bot** tab and click **Add Bot**
4. Copy your bot **TOKEN** and add it to your `.env` file
5. Go to **OAuth2** → **URL Generator**
   - Select scopes: `bot`
   - Select permissions: 
     - `Read Messages/View Channels`
     - `Send Messages`
     - `Embed Links`
6. Copy the generated URL and open it in your browser to invite the bot to your server

## Usage

### Grade a Trade
```
!grade Player1, Player2 for Player3, Player4
```

**Example:**
```
!grade Justin Jefferson, Bijan Robinson for CeeDee Lamb, Breece Hall
```

### Look Up a Player
```
!value Player Name
```

**Example:**
```
!value Justin Jefferson
```

## Deployment

### Deploy to Railway (Free & Easy)

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push
   ```

2. **Connect to Railway**
   - Go to [Railway.app](https://railway.app)
   - Click **New Project** → **Deploy from GitHub Repo**
   - Select your repository
   - Railway auto-deploys!

3. **Add Environment Variables**
   - In Railway dashboard, go to **Variables**
   - Add: `DISCORD_BOT_TOKEN=your_token_here`

Your bot now runs 24/7 for free! 🎉

## Configuration

Edit the `LEAGUE_SETTINGS` in `discrod_trade_bot.py` to match your league:

```python
LEAGUE_SETTINGS = {
    "isDynasty": "true",      # Dynasty league
    "numQbs": 2,              # Superflex (2 QB positions)
    "numTeams": 12,           # Number of teams
    "ppr": 1                  # Full PPR (0.5 for half-PPR)
}
```

## Player Value Source

Values are fetched from [FantasyCalc API](https://api.fantasycalc.com/values/current) and cached for 6 hours.

## Troubleshooting

**Bot won't start**
- Make sure `DISCORD_BOT_TOKEN` is set in your `.env` file
- Check that dependencies are installed: `pip install -r requirements.txt`

**Players not found**
- The fuzzy matcher has a 60% similarity threshold
- Deep roster players may not be in FantasyCalc's database

**API errors**
- FantasyCalc may be temporarily unavailable
- Check your internet connection

## License

MIT License
