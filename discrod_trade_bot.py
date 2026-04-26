import sys
import subprocess
import os
import audioop  

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
    raise ValueError("DISCORD_BOT_TOKEN environment variable not found!")

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

# Cache for player values
player_values_cache = {}
cache_timestamp = None

def get_player_values() -> Dict:
    """Fetch player values from FantasyCalc API"""
    global player_values_cache, cache_timestamp
    import datetime
    now = datetime.datetime.now()
    
    if cache_timestamp and (now - cache_timestamp).seconds < 21600:
        return player_values_cache
    
    print("Fetching player values from FantasyCalc...")
    response = requests.get(
        "https://api.fantasycalc.com/values/current",
        params=LEAGUE_SETTINGS
    )
    
    if response.status_code == 200:
        data = response.json()
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
        return player_values_cache
    return player_values_cache

def find_player(player_name: str, values_dict: Dict) -> Dict:
    """Find player with fuzzy matching, draft pick normalization, and food easter eggs"""
    clean_name = player_name.strip().lower()

    # --- HUMOR EASTER EGG (Food List) ---
    food_keywords = ["sandwich", "taco", "pizza", "hot dog", "burger", "burrito", "steak", "salad"]
    if any(food in clean_name for food in food_keywords):
        return {
            'name': player_name.strip().title(),
            'position': 'FOOD',
            'value': 0, 
            'rank': 999,
            'is_food': True
        }
    
    # --- DRAFT PICK FLEXIBILITY ---
    # Normalizes "2026 pick 1.01" -> "2026 1.01"
    clean_name = re.sub(r'\b(20\d{2})\s+pick\s+', r'\1 ', clean_name, flags=re.IGNORECASE)
    
    if clean_name in values_dict:
        return values_dict[clean_name]
    
    normalized_input = re.sub(r"['\-\.]", "", clean_name)
    normalized_keys = {re.sub(r"['\-\.]", "", key): key for key in values_dict.keys()}
    
    matches = difflib.get_close_matches(normalized_input, normalized_keys.keys(), n=1, cutoff=0.6)
    if matches:
        original_key = normalized_keys[matches[0]]
        return values_dict[original_key]
    
    return None

def parse_trade(trade_text: str) -> Tuple[List[str], List[str]]:
    """Parse trade text into two lists of players"""
    separators = [' for ', ' gets ', ' receives ', ' get ', ' receive ']
    split_text = trade_text.lower()
    for sep in separators:
        if sep in split_text:
            parts = trade_text.split(sep, 1)
            if len(parts) == 2:
                return [p.strip() for p in parts[0].split(',')], [p.strip() for p in parts[1].split(',')]
    
    if '|' in trade_text:
        parts = trade_text.split('|')
        return [p.strip() for p in parts[0].split(',')], [p.strip() for p in parts[1].split(',')]
    
    return None, None

@bot.event
async def on_ready():
    print(f'{bot.user} is online!')
    get_player_values()

@bot.command()
async def grade(ctx, *, trade_text: str):
    values_dict = get_player_values()
    if not values_dict:
        await ctx.send("❌ Error loading player values.")
        return
    
    team_a_names, team_b_names = parse_trade(trade_text)
    if not team_a_names or not team_b_names:
        await ctx.send("❌ Invalid trade format! Use: `!grade Player A for Player B`")
        return
    
    def process_team(names):
        players, total, not_found = [], 0, []
        for name in names:
            p = find_player(name, values_dict)
            if p:
                players.append(p)
                total += p['value']
            else:
                not_found.append(name)
                players.append({'name': name, 'position': '???', 'value': 0, 'rank': 999})
        return players, total, not_found

    team_a_players, team_a_total, _ = process_team(team_a_names)
    team_b_players, team_b_total, _ = process_team(team_b_names)

    # --- DYNAMIC FOOD LOGIC ---
    has_food_a = any(p.get('is_food') for p in team_a_players)
    has_food_b = any(p.get('is_food') for p in team_b_players)

    # If the other team is low value (< 2000), the food wins by 1 point
    if has_food_a and team_b_total < 2000:
        for p in team_a_players:
            if p.get('is_food'):
                p['value'] = (team_b_total - (team_a_total - p['value'])) + 1
        team_a_total = team_b_total + 1

    if has_food_b and team_a_total < 2000:
        for p in team_b_players:
            if p.get('is_food'):
                p['value'] = (team_a_total - (team_b_total - p['value'])) + 1
        team_b_total = team_a_total + 1

    embed = discord.Embed(title="📊 TRADE ANALYSIS", color=discord.Color.blue())
    
    def build_field_text(players, total):
        text = ""
        for p in players:
            if p.get('is_food'):
                text += f"• **🥡 {p['name']}** - Value: A full belly\n"
            else:
                val_str = f"{p['value']:,}" if p['value'] > 0 else "0 (NOT FOUND)"
                text += f"• **{p['name']}** ({p['position']}) - Value: {val_str}\n"
        return text + f"\n**Total: {total:,}**"

    embed.add_field(name="Team A Receives", value=build_field_text(team_a_players, team_a_total), inline=False)
    embed.add_field(name="Team B Receives", value=build_field_text(team_b_players, team_b_total), inline=False)
    
    # Sassy food messaging
    food_msg = ""
    if has_food_a or has_food_b:
        if (has_food_a and team_a_total > team_b_total) or (has_food_b and team_b_total > team_a_total):
            food_msg = "\n\n😋 *Better full than disappointed.*"
        else:
            food_msg = "\n\n⚖️ *This trade is unequal, but someone won't be going home hungry.*"

    if team_a_total > team_b_total:
        res = f"🏆 **WINNER: Team A** (+{team_a_total-team_b_total:,}){food_msg}"
        embed.color = discord.Color.green()
    elif team_b_total > team_a_total:
        res = f"🏆 **WINNER: Team B** (+{team_b_total-team_a_total:,}){food_msg}"
        embed.color = discord.Color.green()
    else:
        res = f"⚖️ **EVEN TRADE**{food_msg}"
        embed.color = discord.Color.gold()
    
    embed.add_field(name="Result", value=res, inline=False)
    embed.set_footer(text="Powered by FantasyCalc • 12tm SF Dynasty PPR")
    await ctx.send(embed=embed)

@bot.command()
async def value(ctx, *, player_name: str):
    values_dict = get_player_values()
    player = find_player(player_name, values_dict)
    if player:
        embed = discord.Embed(title=f"💎 {player['name']}", color=discord.Color.blue())
        display_val = "A full belly" if player.get('is_food') else f"{player['value']:,}"
        embed.add_field(name="Position", value=player['position'], inline=True)
        embed.add_field(name="Value", value=display_val, inline=True)
        embed.add_field(name="Rank", value=f"#{player['rank']}", inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Player not found: **{player_name}**")

bot.run(BOT_TOKEN)
