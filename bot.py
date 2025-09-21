import discord
from discord.ext import commands
import aiohttp
import asyncio
from datetime import datetime
import json
import os
import sys
import re
from bs4 import BeautifulSoup

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
    
    async def get_name_history_mojang(self, uuid):
        """Get name history from Mojang API (Note: This endpoint was removed by Mojang)"""
        session = await self.get_session()
        try:
            # This endpoint was removed by Mojang in 2022
            # Keeping for reference but will return appropriate message
            return {
                'status': 'info',
                'message': 'Mojang removed the name history API in 2022',
                'names': []
            }
        except Exception as e:
            return {'status': 'error', 'message': f'Error: {str(e)}'}
    
    async def get_namemc_history(self, username):
        """Get name history from NameMC using web scraping"""
        session = await self.get_session()
        try:
            # First, get UUID from Mojang
            uuid = await self.get_uuid_from_username(username)
            if not uuid:
                return {'status': 'error', 'message': 'Username not found in Mojang database'}
            
            # Format UUID with dashes for NameMC
            formatted_uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
            
            # Use different headers to avoid detection
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            async with session.get(f'https://namemc.com/profile/{formatted_uuid}', headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    
                    # Try to extract name history from NameMC
                    name_history = []
                    
                    # Look for name history in the HTML structure
                    name_elements = soup.find_all('div', class_='row no-gutters my-1')
                    for element in name_elements:
                        name_text = element.get_text(strip=True)
                        if name_text and not any(x in name_text.lower() for x in ['skin', 'cape', 'server']):
                            name_history.append(name_text)
                    
                    # If no specific structure found, try alternative method
                    if not name_history:
                        # Look for any text that might be usernames
                        profile_content = soup.find('div', class_='container')
                        if profile_content:
                            text_content = profile_content.get_text()
                            # Extract potential usernames (basic pattern matching)
                            potential_names = re.findall(r'\b[a-zA-Z0-9_]{1,16}\b', text_content)
                            # Filter out common words and keep likely usernames
                            name_history = [name for name in potential_names[:5] if len(name) >= 3 and name != username]
                    
                    return {
                        'status': 'success',
                        'message': f'Profile found on NameMC',
                        'uuid': formatted_uuid,
                        'profile_url': f'https://namemc.com/profile/{formatted_uuid}',
                        'name_history': name_history or [username]
                    }
                elif resp.status == 403:
                    return {'status': 'error', 'message': 'NameMC blocked the request (403 Forbidden). Try using a VPN or wait before retrying.'}
                elif resp.status == 404:
                    return {'status': 'error', 'message': 'Profile not found on NameMC'}
                elif resp.status == 429:
                    return {'status': 'error', 'message': 'Rate limited by NameMC, try again later'}
                else:
                    return {'status': 'error', 'message': f'NameMC returned status {resp.status}'}
        except Exception as e:
            return {'status': 'error', 'message': f'Error accessing NameMC: {str(e)}'}
    
    async def get_laby_history(self, username):
        """Get profile data and name history from Laby.net"""
        session = await self.get_session()
        try:
            # Get UUID first
            uuid = await self.get_uuid_from_username(username)
            if not uuid:
                return {'status': 'error', 'message': 'Username not found in Mojang database'}
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            # Try Laby.net profile page
            async with session.get(f'https://laby.net/@{username}', headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    
                    # Try to extract name history from Laby.net
                    name_history = [username]  # Current name
                    
                    # Look for name history section
                    history_section = soup.find('div', string=re.compile('Name History', re.I))
                    if history_section:
                        # Find the parent container and extract names
                        parent = history_section.find_parent()
                        if parent:
                            names = parent.find_all('span', class_=re.compile('name|username'))
                            name_history.extend([name.get_text(strip=True) for name in names if name.get_text(strip=True) != username])
                    
                    return {
                        'status': 'success',
                        'message': f'Profile found on Laby.net',
                        'profile_url': f'https://laby.net/@{username}',
                        'uuid': uuid,
                        'name_history': list(dict.fromkeys(name_history))  # Remove duplicates while preserving order
                    }
                elif resp.status == 404:
                    return {'status': 'error', 'message': 'Profile not found on Laby.net'}
                elif resp.status == 429:
                    return {'status': 'error', 'message': 'Rate limited by Laby.net'}
                else:
                    return {'status': 'error', 'message': f'Laby.net returned status {resp.status}'}
        except Exception as e:
            return {'status': 'error', 'message': f'Error accessing Laby.net: {str(e)}'}
    
    async def get_crafty_history(self, username):
        """Get profile data and name history from Crafty.gg"""
        session = await self.get_session()
        try:
            # Get UUID first
            uuid = await self.get_uuid_from_username(username)
            if not uuid:
                return {'status': 'error', 'message': 'Username not found in Mojang database'}
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            # Try Crafty.gg profile page
            async with session.get(f'https://crafty.gg/@{username}', headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    
                    # Try to extract name history from Crafty.gg
                    name_history = []
                    
                    # Look for name history section (similar to your example)
                    history_elements = soup.find_all('div', string=re.compile(r'\d+\.\s*\w+'))
                    for element in history_elements:
                        # Extract the name from patterns like "4. Fastlyy - May 6, 2025, 5 months ago"
                        text = element.get_text(strip=True)
                        match = re.search(r'\d+\.\s*(\w+)', text)
                        if match:
                            name_history.append({
                                'name': match.group(1),
                                'details': text
                            })
                    
                    # If the specific structure isn't found, try alternative methods
                    if not name_history:
                        # Look for any structured name data
                        name_elements = soup.find_all('span', class_=re.compile('name|username'))
                        for elem in name_elements:
                            name_text = elem.get_text(strip=True)
                            if name_text and len(name_text) <= 16 and name_text.replace('_', '').isalnum():
                                name_history.append({
                                    'name': name_text,
                                    'details': name_text
                                })
                    
                    return {
                        'status': 'success',
                        'message': f'Profile found on Crafty.gg',
                        'profile_url': f'https://crafty.gg/@{username}',
                        'uuid': uuid,
                        'name_history': name_history or [{'name': username, 'details': f'Current: {username}'}]
                    }
                elif resp.status == 404:
                    return {'status': 'error', 'message': 'Profile not found on Crafty.gg'}
                elif resp.status == 403:
                    return {'status': 'error', 'message': 'Access forbidden by Crafty.gg (possible rate limiting or bot detection)'}
                elif resp.status == 429:
                    return {'status': 'error', 'message': 'Rate limited by Crafty.gg'}
                else:
                    return {'status': 'error', 'message': f'Crafty.gg returned status {resp.status}'}
        except Exception as e:
            return {'status': 'error', 'message': f'Error accessing Crafty.gg: {str(e)}'}
    
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
        namemc_text += f"**UUID:** `{namemc_data.get('uuid', 'N/A')}`\n"
        
        # Display name history if available
        if 'name_history' in namemc_data and namemc_data['name_history']:
            history_list = namemc_data['name_history'][:5]  # Limit to 5 names
            namemc_text += f"**Name History:** {' → '.join(reversed(history_list))}\n"
        
        namemc_text += f"**Profile:** [View on NameMC]({namemc_data.get('profile_url', '#')})"
    else:
        namemc_text = f"❌ **Error:** {namemc_data['message']}"
    
    embed.add_field(name="🔍 NameMC", value=namemc_text, inline=False)
    
    # Laby.net Section
    if laby_data['status'] == 'success':
        laby_text = f"✅ **Status:** Found\n"
        laby_text += f"**UUID:** `{laby_data.get('uuid', 'N/A')}`\n"
        
        # Display name history if available
        if 'name_history' in laby_data and len(laby_data['name_history']) > 1:
            history_list = laby_data['name_history'][:5]  # Limit to 5 names
            laby_text += f"**Name History:** {' → '.join(reversed(history_list))}\n"
        
        laby_text += f"**Profile:** [View on Laby.net]({laby_data.get('profile_url', '#')})"
    else:
        laby_text = f"❌ **Error:** {laby_data['message']}"
    
    embed.add_field(name="🌐 Laby.net", value=laby_text, inline=False)
    
    # Crafty.gg Section
    if crafty_data['status'] == 'success':
        crafty_text = f"✅ **Status:** Found\n"
        crafty_text += f"**UUID:** `{crafty_data.get('uuid', 'N/A')}`\n"
        
        # Display name history if available
        if 'name_history' in crafty_data and crafty_data['name_history']:
            history_items = crafty_data['name_history'][:5]  # Limit to 5 names
            if len(history_items) > 1 or (len(history_items) == 1 and 'details' in history_items[0] and '-' in history_items[0]['details']):
                history_text = '\n'.join([f"**{item.get('details', item.get('name', 'Unknown'))}**" for item in history_items[:3]])
                crafty_text += f"**Name History:**\n{history_text}\n"
        
        crafty_text += f"**Profile:** [View on Crafty.gg]({crafty_data.get('profile_url', '#')})"
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
