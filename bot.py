import discord
from discord.ext import commands
import aiohttp
import asyncio
from datetime import datetime
import json
import os
import sys

# Load configuration
def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found!")
        print("Please create a config.json file with your bot token.")
        print("Example config.json:")
        print('{')
        print('    "token": "YOUR_BOT_TOKEN_HERE"')
        print('}')
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Invalid JSON in config.json")
        sys.exit(1)

config = load_config()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

class NameHistoryBot:
    def __init__(self):
        self.session = None
    
    async def get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def get_uuid_from_username(self, username):
        """Get UUID from username using Mojang API"""
        session = await self.get_session()
        try:
            async with session.get(f'https://api.mojang.com/users/profiles/minecraft/{username}') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('id')
                return None
        except Exception as e:
            print(f"Error getting UUID: {e}")
            return None
    
    async def get_namemc_history(self, username):
        """Get name history from NameMC"""
        session = await self.get_session()
        try:
            # NameMC doesn't have a public API, so we'll simulate the response structure
            # In a real implementation, you'd need to scrape or use their unofficial methods
            async with session.get(f'https://namemc.com/profile/{username}') as resp:
                if resp.status == 200:
                    # This is a placeholder - NameMC requires web scraping
                    return {
                        'status': 'success',
                        'message': 'NameMC data would be scraped here',
                        'names': ['ExampleName1', 'ExampleName2', username]
                    }
                else:
                    return {'status': 'error', 'message': 'Profile not found on NameMC'}
        except Exception as e:
            return {'status': 'error', 'message': f'Error fetching NameMC data: {str(e)}'}
    
    async def get_laby_history(self, username):
        """Get name history from Laby.net"""
        session = await self.get_session()
        try:
            # Get UUID first
            uuid = await self.get_uuid_from_username(username)
            if not uuid:
                return {'status': 'error', 'message': 'Could not find UUID for username'}
            
            # Laby.net API endpoint (this may need adjustment based on actual API)
            async with session.get(f'https://laby.net/api/user/{uuid}/profile') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        'status': 'success',
                        'data': data,
                        'message': 'Successfully fetched Laby.net data'
                    }
                else:
                    return {'status': 'error', 'message': f'Laby.net API returned status {resp.status}'}
        except Exception as e:
            return {'status': 'error', 'message': f'Error fetching Laby.net data: {str(e)}'}
    
    async def get_crafty_history(self, username):
        """Get name history from Crafty.gg"""
        session = await self.get_session()
        try:
            # Crafty.gg API endpoint (this may need adjustment based on actual API)
            async with session.get(f'https://api.crafty.gg/user/{username}') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        'status': 'success',
                        'data': data,
                        'message': 'Successfully fetched Crafty.gg data'
                    }
                else:
                    return {'status': 'error', 'message': f'Crafty.gg API returned status {resp.status}'}
        except Exception as e:
            return {'status': 'error', 'message': f'Error fetching Crafty.gg data: {str(e)}'}
    
    async def close_session(self):
        if self.session:
            await self.session.close()

# Initialize the name history handler
name_bot = NameHistoryBot()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

@bot.tree.command(name="namehistory", description="Check name history from NameMC, Laby.net, and Crafty.gg")
async def name_history(interaction: discord.Interaction, username: str):
    """Slash command to check name history across all three services"""
    
    # Defer the response as this might take a while
    await interaction.response.defer()
    
    # Create embed
    embed = discord.Embed(
        title=f"Name History for {username}",
        color=0x00ff00,
        timestamp=datetime.now()
    )
    embed.set_footer(text="Name History Bot")
    
    # Get data from all three services
    namemc_data = await name_bot.get_namemc_history(username)
    laby_data = await name_bot.get_laby_history(username)
    crafty_data = await name_bot.get_crafty_history(username)
    
    # NameMC Section
    if namemc_data['status'] == 'success':
        namemc_text = f"✅ **Status:** Found\n"
        if 'names' in namemc_data:
            namemc_text += f"**Previous Names:** {', '.join(namemc_data['names'])}\n"
        namemc_text += f"**Note:** {namemc_data['message']}"
    else:
        namemc_text = f"❌ **Error:** {namemc_data['message']}"
    
    embed.add_field(name="🔍 NameMC", value=namemc_text, inline=False)
    
    # Laby.net Section
    if laby_data['status'] == 'success':
        laby_text = f"✅ **Status:** Found\n**Message:** {laby_data['message']}"
        if 'data' in laby_data:
            laby_text += f"\n**Data:** Profile information retrieved"
    else:
        laby_text = f"❌ **Error:** {laby_data['message']}"
    
    embed.add_field(name="🌐 Laby.net", value=laby_text, inline=False)
    
    # Crafty.gg Section
    if crafty_data['status'] == 'success':
        crafty_text = f"✅ **Status:** Found\n**Message:** {crafty_data['message']}"
        if 'data' in crafty_data:
            crafty_text += f"\n**Data:** Profile information retrieved"
    else:
        crafty_text = f"❌ **Error:** {crafty_data['message']}"
    
    embed.add_field(name="⚡ Crafty.gg", value=crafty_text, inline=False)
    
    # Send the embed
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="namemc", description="Check name history specifically from NameMC")
async def namemc_only(interaction: discord.Interaction, username: str):
    """Slash command to check only NameMC"""
    await interaction.response.defer()
    
    namemc_data = await name_bot.get_namemc_history(username)
    
    embed = discord.Embed(
        title=f"NameMC History for {username}",
        color=0xff6b6b,
        timestamp=datetime.now()
    )
    
    if namemc_data['status'] == 'success':
        embed.add_field(name="Status", value="✅ Found", inline=True)
        if 'names' in namemc_data:
            embed.add_field(name="Previous Names", value=', '.join(namemc_data['names']), inline=False)
        embed.add_field(name="Note", value=namemc_data['message'], inline=False)
    else:
        embed.add_field(name="Status", value="❌ Error", inline=True)
        embed.add_field(name="Message", value=namemc_data['message'], inline=False)
    
    embed.set_footer(text="NameMC Lookup")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="laby", description="Check name history specifically from Laby.net")
async def laby_only(interaction: discord.Interaction, username: str):
    """Slash command to check only Laby.net"""
    await interaction.response.defer()
    
    laby_data = await name_bot.get_laby_history(username)
    
    embed = discord.Embed(
        title=f"Laby.net History for {username}",
        color=0x4ecdc4,
        timestamp=datetime.now()
    )
    
    if laby_data['status'] == 'success':
        embed.add_field(name="Status", value="✅ Found", inline=True)
        embed.add_field(name="Message", value=laby_data['message'], inline=False)
    else:
        embed.add_field(name="Status", value="❌ Error", inline=True)
        embed.add_field(name="Message", value=laby_data['message'], inline=False)
    
    embed.set_footer(text="Laby.net Lookup")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="crafty", description="Check name history specifically from Crafty.gg")
async def crafty_only(interaction: discord.Interaction, username: str):
    """Slash command to check only Crafty.gg"""
    await interaction.response.defer()
    
    crafty_data = await name_bot.get_crafty_history(username)
    
    embed = discord.Embed(
        title=f"Crafty.gg History for {username}",
        color=0xffd93d,
        timestamp=datetime.now()
    )
    
    if crafty_data['status'] == 'success':
        embed.add_field(name="Status", value="✅ Found", inline=True)
        embed.add_field(name="Message", value=crafty_data['message'], inline=False)
    else:
        embed.add_field(name="Status", value="❌ Error", inline=True)
        embed.add_field(name="Message", value=crafty_data['message'], inline=False)
    
    embed.set_footer(text="Crafty.gg Lookup")
    await interaction.followup.send(embed=embed)

@bot.event
async def on_close():
    await name_bot.close_session()

# Run the bot
if __name__ == "__main__":
    token = config.get('token')
    if not token:
        print("Error: No token found in config.json")
        sys.exit(1)
    
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("Error: Invalid bot token in config.json")
    except Exception as e:
        print(f"Error starting bot: {e}")
