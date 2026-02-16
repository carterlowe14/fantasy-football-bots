import sys
import subprocess
import os

def check_and_install_dependencies():
    """Check if required packages are installed, install from requirements.txt if missing"""
    try:
        with open('requirements.txt', 'r') as f:
            requirements_exist = True
    except FileNotFoundError:
        print("⚠️  requirements.txt not found!")
        return
    
    print("Installing dependencies from requirements.txt...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "-r", "requirements.txt"
        ])
        print("✓ All dependencies installed!")
    except subprocess.CalledProcessError:
        print("✗ Error installing dependencies!")
        raise

# Run check before imports
check_and_install_dependencies()

import discord
from discord.ext import commands
import requests
import re
import difflib
from typing import List, Tuple, Dict
from dotenv import load_dotenv

load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable not found! Please set it in your .env file or Railway config.")

# League settings
LEAGUE_SETTINGS = {
    "isDynasty": "true",
    "numQbs": 2,        # Superflex
    "numTeams": 12,
    "ppr": 1            # Full PPR
}

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Cache for player values (refresh every 6 hours)
player_values_cache = {}
cache_timestamp = None

def get_player_values() -> Dict:
    """Fetch player values from FantasyCalc API"""
    global player_values_cache, cache_timestamp
    
    import datetime
    now = datetime.datetime.now()
    
    # Use cache if less than 6 hours old
    if cache_timestamp and (now - cache_timestamp).seconds < 21600:
        return player_values_cache
    
    print("Fetching player values from FantasyCalc...")
    response = requests.get(
        "https://api.fantasycalc.com/values/current",
        params=LEAGUE_SETTINGS
    )
    
    if response.status_code == 200:
        data = response.json()
        
        # DEBUG: Show breakdown
        positions = {}
        for player in data:
            pos = player['player'].get('position', 'UNKNOWN')
            positions[pos] = positions.get(pos, 0) + 1
        
        print(f"Loaded {len(data)} players:")
        for pos, count in sorted(positions.items()):
            print(f"  {pos}: {count}")
        # Create lookup dict: player name -> value
        player_values_cache = {
            player['player']['name'].lower(): {
                'name': player['player']['name'],
                'position': player['player'].get('position', 'UNKNOWN'),
                'value': player.get('value', 0),
                'rank': player.get('overallRank', 999)
            }
            for player in data
        }
        cache_timestamp = now
        print(f"Loaded {len(player_values_cache)} players")
        return player_values_cache
    else:
        print(f"Error fetching values: {response.status_code}")
        return player_values_cache

def find_player(player_name: str, values_dict: Dict) -> Dict:
    """Find player in values dict (fuzzy matching to handle typos and special characters)"""
    player_name = player_name.strip().lower()
    
    # Exact match
    if player_name in values_dict:
        return values_dict[player_name]
    
    # Normalize both input and keys by removing apostrophes/special chars for fuzzy matching
    normalized_input = re.sub(r"['\-\.]", "", player_name)
    normalized_keys = {re.sub(r"['\-\.]", "", key): key for key in values_dict.keys()}
    
    # Fuzzy match against normalized names (handles typos and special characters like apostrophes)
    matches = difflib.get_close_matches(normalized_input, normalized_keys.keys(), n=1, cutoff=0.6)
    if matches:
        original_key = normalized_keys[matches[0]]
        return values_dict[original_key]
    
    return None

def parse_trade(trade_text: str) -> Tuple[List[str], List[str]]:
    """Parse trade text into two lists of players"""
    # Split by 'for', 'gets', 'receives', etc.
    separators = [' for ', ' gets ', ' receives ', ' get ', ' receive ']
    
    split_text = trade_text.lower()
    for sep in separators:
        if sep in split_text:
            parts = trade_text.split(sep, 1)
            if len(parts) == 2:
                team_a_players = [p.strip() for p in parts[0].split(',')]
                team_b_players = [p.strip() for p in parts[1].split(',')]
                return team_a_players, team_b_players
    
    # If no separator found, assume comma-separated with | divider
    if '|' in trade_text:
        parts = trade_text.split('|')
        team_a_players = [p.strip() for p in parts[0].split(',')]
        team_b_players = [p.strip() for p in parts[1].split(',')]
        return team_a_players, team_b_players
    
    return None, None

@bot.event
async def on_ready():
    print(f'{bot.user} is online!')
    get_player_values()  # Preload values

@bot.command()
async def grade(ctx, *, trade_text: str):
    """
    Grade a fantasy football trade
    
    Usage: !grade Player1, Player2 for Player3, Player4
    Example: !grade Justin Jefferson, Bijan Robinson for CeeDee Lamb, Breece Hall
    """
    
    values_dict = get_player_values()
    
    if not values_dict:
        await ctx.send("❌ Error loading player values. Please try again.")
        return
    
    # Parse trade
    team_a_names, team_b_names = parse_trade(trade_text)
    
    if not team_a_names or not team_b_names:
        await ctx.send(
            "❌ Invalid trade format!\n\n"
            "**Usage:** `!grade Player1, Player2 for Player3, Player4`\n"
            "**Example:** `!grade Justin Jefferson for CeeDee Lamb, 2025 1st`"
        )
        return
    
    # Look up player values
    team_a_players = []
    team_a_total = 0
    team_a_not_found = []
    
    for name in team_a_names:
        player = find_player(name, values_dict)
        if player:
            team_a_players.append(player)
            team_a_total += player['value']
        else:
            # Add with 0 value
            team_a_not_found.append(name)
            team_a_players.append({
                'name': name,
                'position': '???',
                'value': 0,
                'rank': 999
            })
    
    team_b_players = []
    team_b_total = 0
    team_b_not_found = []
    
    for name in team_b_names:
        player = find_player(name, values_dict)
        if player:
            team_b_players.append(player)
            team_b_total += player['value']
        else:
            # Add with 0 value
            team_b_not_found.append(name)
            team_b_players.append({
                'name': name,
                'position': '???',
                'value': 0,
                'rank': 999
            })
    
    # Build response
    embed = discord.Embed(
        title="📊 TRADE ANALYSIS",
        color=discord.Color.blue()
    )
    
    # Team A section
    team_a_text = ""
    for p in team_a_players:
        if p['value'] == 0 and p['position'] == '???':
            team_a_text += f"• **{p['name']}** - ⚠️ NOT FOUND (Value: 0)\n"
        else:
            team_a_text += f"• **{p['name']}** ({p['position']}) - Value: {p['value']:,}\n"
    team_a_text += f"\n**Total: {team_a_total:,}**"
    embed.add_field(name="Team A Receives", value=team_a_text, inline=False)
    
    # Team B section
    team_b_text = ""
    for p in team_b_players:
        if p['value'] == 0 and p['position'] == '???':
            team_b_text += f"• **{p['name']}** - ⚠️ NOT FOUND (Value: 0)\n"
        else:
            team_b_text += f"• **{p['name']}** ({p['position']}) - Value: {p['value']:,}\n"
    team_b_text += f"\n**Total: {team_b_total:,}**"
    embed.add_field(name="Team B Receives", value=team_b_text, inline=False)
    
    # Winner
    if team_a_total > team_b_total:
        diff = team_a_total - team_b_total
        pct = (diff / team_b_total * 100) if team_b_total > 0 else 0
        winner_text = f"🏆 **WINNER: Team A** (+{diff:,} value, +{pct:.1f}%)"
        embed.color = discord.Color.green()
    elif team_b_total > team_a_total:
        diff = team_b_total - team_a_total
        pct = (diff / team_a_total * 100) if team_a_total > 0 else 0
        winner_text = f"🏆 **WINNER: Team B** (+{diff:,} value, +{pct:.1f}%)"
        embed.color = discord.Color.green()
    else:
        winner_text = "⚖️ **EVEN TRADE** - Equal value!"
        embed.color = discord.Color.gold()
    
    embed.add_field(name="Result", value=winner_text, inline=False)
    
    # Add warning if players not found
    if team_a_not_found or team_b_not_found:
        warning_text = "⚠️ **Note:** Players not found are valued at 0. These may be deep roster players not tracked by FantasyCalc."
        embed.add_field(name="Warning", value=warning_text, inline=False)
        embed.color = discord.Color.orange()
    
    embed.set_footer(text="Powered by FantasyCalc • 12tm SF Dynasty PPR")
    
    await ctx.send(embed=embed)


@bot.command()
async def value(ctx, *, player_name: str):
    """
    Look up a single player's value
    
    Usage: !value Justin Jefferson
    """
    values_dict = get_player_values()
    
    if not values_dict:
        await ctx.send("❌ Error loading player values. Please try again.")
        return
    
    player = find_player(player_name, values_dict)
    
    if player:
        embed = discord.Embed(
            title=f"💎 {player['name']}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Position", value=player['position'], inline=True)
        embed.add_field(name="Value", value=f"{player['value']:,}", inline=True)
        embed.add_field(name="Overall Rank", value=f"#{player['rank']}", inline=True)
        embed.set_footer(text="Powered by FantasyCalc • 12tm SF Dynasty PPR")
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Player not found: **{player_name}**\n\nTry checking the spelling!")

# Run the bot
bot.run(BOT_TOKEN)