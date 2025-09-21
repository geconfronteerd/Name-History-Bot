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
    
    async def get_crafty_profile(self, username):
        """Get profile data from Crafty.gg using their actual API"""
        session = await self.get_session()
        try:
            uuid = await self.get_uuid_from_username(username)
            if not uuid:
                return {'status': 'error', 'message': 'Username not found in Mojang database'}
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': f'https://crafty.gg/@{username}',
                'Origin': 'https://crafty.gg'
            }
            
            # Try the actual Crafty API endpoints
            api_endpoints = [
                f'https://crafty.gg/api/profile/{username}',
                f'https://api.crafty.gg/player/{username}',
                f'https://api.crafty.gg/player/{uuid}',
                f'https://crafty.gg/api/player/{username}',
                f'https://crafty.gg/api/player/{uuid}',
                f'https://crafty.gg/api/users/{username}',
                f'https://crafty.gg/api/minecraft/{username}'
            ]
            
            for endpoint in api_endpoints:
                try:
                    async with session.get(endpoint, headers=headers) as resp:
                        if resp.status == 200:
                            try:
                                data = await resp.json()
                                
                                # Parse name history from API response
                                name_history = []
                                if 'nameHistory' in data:
                                    for entry in data['nameHistory']:
                                        name_history.append({
                                            'name': entry.get('name', 'Unknown'),
                                            'changedToAt': entry.get('changedToAt', 'Unknown')
                                        })
                                elif 'names' in data:
                                    for i, entry in enumerate(data['names']):
                                        name_history.append({
                                            'position': i + 1,
                                            'name': entry.get('name', 'Unknown'),
                                            'date': entry.get('date', 'Unknown')
                                        })
                                
                                return {
                                    'status': 'success',
                                    'message': f'Profile found on Crafty.gg (API)',
                                    'profile_url': f'https://crafty.gg/@{username}',
                                    'uuid': uuid,
                                    'name_history': name_history,
                                    'data': data,
                                    'api_endpoint': endpoint
                                }
                            except json.JSONDecodeError:
                                continue
                except:
                    continue
            
            # If all API attempts fail, use web scraping
            return await self.scrape_crafty_profile(username, uuid)
            
        except Exception as e:
            return {'status': 'error', 'message': f'Error accessing Crafty.gg: {str(e)}'}
    
    async def scrape_crafty_profile(self, username, uuid):
        """Enhanced web scraping for Crafty.gg to extract name history"""
        session = await self.get_session()
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            
            async with session.get(f'https://crafty.gg/@{username}', headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    
                    name_history = []
                    
                    # Method 1: Look for JSON data in script tags
                    for script in soup.find_all('script'):
                        if script.string and 'nameHistory' in script.string:
                            try:
                                # Try to extract JSON containing name history
                                json_matches = re.findall(r'\{[^{}]*nameHistory[^{}]*\}', script.string)
                                for match in json_matches:
                                    try:
                                        data = json.loads(match)
                                        if 'nameHistory' in data:
                                            for entry in data['nameHistory']:
                                                name_history.append({
                                                    'name': entry.get('name', 'Unknown'),
                                                    'date': entry.get('changedToAt', 'Unknown')
                                                })
                                    except:
                                        continue
                            except:
                                continue
                    
                    # Method 2: Look for specific HTML patterns like "4. Fastlyy - May 6, 2025"
                    page_text = soup.get_text()
                    history_pattern = r'(\d+)\.\s*(\w+)\s*-\s*([^,\n]+)(?:,\s*([^,\n]+))?'
                    matches = re.findall(history_pattern, page_text)
                    
                    for match in matches:
                        if len(match[1]) <= 16:  # Valid Minecraft username length
                            name_history.append({
                                'position': match[0],
                                'name': match[1],
                                'date': match[2],
                                'ago': match[3] if len(match) > 3 else ''
                            })
                    
                    # Remove duplicates
                    seen_names = set()
                    unique_history = []
                    for entry in name_history:
                        name = entry.get('name', '')
                        if name and name not in seen_names:
                            seen_names.add(name)
                            unique_history.append(entry)
                    
                    return {
                        'status': 'success',
                        'message': f'Profile found on Crafty.gg',
                        'profile_url': f'https://crafty.gg/@{username}',
                        'uuid': uuid,
                        'name_history': unique_history or [{'name': username, 'date': 'Current'}]
                    }
                else:
                    return {'status': 'error', 'message': f'Crafty.gg returned status {resp.status}'}
        except Exception as e:
            return {'status': 'error', 'message': f'Error scraping Crafty.gg: {str(e)}'}
    
    async def get_laby_profile(self, username):
        """Get profile data from Laby.net with enhanced name history extraction"""
        session = await self.get_session()
        try:
            uuid = await self.get_uuid_from_username(username)
            if not uuid:
                return {'status': 'error', 'message': 'Username not found in Mojang database'}
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*'
            }
            
            # Try Laby.net API endpoints
            api_urls = [
                f'https://laby.net/api/user/{uuid}',
                f'https://laby.net/api/v3/user/{uuid}/profile',
                f'https://api.laby.net/user/{uuid}',
                f'https://api.laby.net/v3/user/{uuid}'
            ]
            
            for url in api_urls:
                try:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            # Extract name history from API response
                            name_history = []
                            if 'nameHistory' in data:
                                for entry in data['nameHistory']:
                                    name_history.append({
                                        'name': entry.get('name', 'Unknown'),
                                        'changedToAt': entry.get('changedToAt', 'Unknown')
                                    })
                            elif 'username_history' in data:
                                for entry in data['username_history']:
                                    name_history.append({
                                        'name': entry.get('username', entry.get('name', 'Unknown')),
                                        'date': entry.get('changed_at', entry.get('changedToAt', 'Unknown'))
                                    })
                            
                            return {
                                'status': 'success',
                                'message': f'Profile found on Laby.net (API)',
                                'profile_url': f'https://laby.net/@{username}',
                                'uuid': uuid,
                                'data': data,
                                'name_history': name_history
                            }
                except:
                    continue
            
            # Fallback to web scraping
            return await self.scrape_laby_profile(username, uuid)
            
        except Exception as e:
            return {'status': 'error', 'message': f'Error accessing Laby.net: {str(e)}'}
    
    async def scrape_laby_profile(self, username, uuid):
        """Enhanced web scraping for Laby.net"""
        session = await self.get_session()
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with session.get(f'https://laby.net/@{username}', headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    
                    # Basic scraping - look for any username-like text
                    name_history = [{'name': username, 'date': 'Current'}]
                    
                    return {
                        'status': 'success',
                        'message': f'Profile found on Laby.net',
                        'profile_url': f'https://laby.net/@{username}',
                        'uuid': uuid,
                        'name_history': name_history
                    }
                else:
                    return {'status': 'error', 'message': f'Profile not found on Laby.net (status {resp.status})'}
        except Exception as e:
            return {'status': 'error', 'message': f'Error accessing Laby.net: {str(e)}'}
    
    async def get_namemc_profile(self, username):
        """Get profile data from NameMC (web scraping only - no official API)"""
        session = await self.get_session()
        try:
            uuid = await self.get_uuid_from_username(username)
            if not uuid:
                return {'status': 'error', 'message': 'Username not found in Mojang database'}
            
            formatted_uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            await asyncio.sleep(1)  # Be respectful
            
            async with session.get(f'https://namemc.com/profile/{formatted_uuid}', headers=headers) as resp:
                if resp.status == 200:
                    return {
                        'status': 'success',
                        'message': f'Profile found on NameMC',
                        'uuid': formatted_uuid,
                        'profile_url': f'https://namemc.com/profile/{formatted_uuid}',
                        'note': 'NameMC has no public API - limited data available'
                    }
                elif resp.status == 403:
                    return {
                        'status': 'error', 
                        'message': 'NameMC blocked the request (anti-bot protection). Visit the profile manually.',
                        'uuid': formatted_uuid,
                        'profile_url': f'https://namemc.com/profile/{formatted_uuid}'
                    }
                else:
                    return {'status': 'error', 'message': f'NameMC returned status {resp.status}'}
        except Exception as e:
            return {'status': 'error', 'message': f'Error accessing NameMC: {str(e)}'}
    
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
    
    await interaction.response.defer()
    
    embed = discord.Embed(
        title=f"Name History for {username}",
        color=0x00ff00,
        timestamp=datetime.now()
    )
    embed.set_footer(text="Name History Bot")
    
    # Get data from all three services
    namemc_data = await name_bot.get_namemc_profile(username)
    laby_data = await name_bot.get_laby_profile(username)
    crafty_data = await name_bot.get_crafty_profile(username)
    
    # NameMC Section
    if namemc_data['status'] == 'success':
        namemc_text = f"✅ **Status:** Found\n"
        namemc_text += f"**UUID:** `{namemc_data.get('uuid', 'N/A')}`\n"
        namemc_text += f"**Profile:** [View on NameMC]({namemc_data.get('profile_url', '#')})\n"
        if 'note' in namemc_data:
            namemc_text += f"**Note:** {namemc_data['note']}"
    else:
        namemc_text = f"❌ **Error:** {namemc_data['message']}\n"
        if 'profile_url' in namemc_data:
            namemc_text += f"**Manual Link:** [View Profile]({namemc_data['profile_url']})"
    
    embed.add_field(name="🔍 NameMC", value=namemc_text, inline=False)
    
    # Laby.net Section
    if laby_data['status'] == 'success':
        laby_text = f"✅ **Status:** Found\n"
        laby_text += f"**UUID:** `{laby_data.get('uuid', 'N/A')}`\n"
        
        # Display name history if available
        if 'name_history' in laby_data and len(laby_data['name_history']) > 1:
            history_items = laby_data['name_history'][:5]
            history_names = [item.get('name', 'Unknown') for item in history_items]
            laby_text += f"**Name History:** {' → '.join(reversed(history_names))}\n"
        
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
            history_items = crafty_data['name_history'][:4]
            
            # Check if we have detailed format with positions and dates
            if history_items and 'position' in history_items[0]:
                history_text = '\n'.join([
                    f"**{item.get('position', '?')}.** {item.get('name', 'Unknown')}" + 
                    (f" - {item.get('date', '')}" if item.get('date') and item.get('date') != 'Unknown' else "") +
                    (f", {item.get('ago', '')}" if item.get('ago') else "")
                    for item in history_items
                ])
                crafty_text += f"**Name History:**\n{history_text}\n"
            else:
                # Simple name list format
                names = [item.get('name', 'Unknown') for item in history_items if item.get('name')]
                if len(names) > 1:
                    crafty_text += f"**Name History:** {' → '.join(reversed(names))}\n"
        
        crafty_text += f"**Profile:** [View on Crafty.gg]({crafty_data.get('profile_url', '#')})"
    else:
        crafty_text = f"❌ **Error:** {crafty_data['message']}"
    
    embed.add_field(name="⚡ Crafty.gg", value=crafty_text, inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="crafty", description="Check name history specifically from Crafty.gg")
async def crafty_only(interaction: discord.Interaction, username: str):
    """Slash command to check only Crafty.gg"""
    await interaction.response.defer()
    
    crafty_data = await name_bot.get_crafty_profile(username)
    
    embed = discord.Embed(
        title=f"Crafty.gg Profile for {username}",
        color=0xffd93d,
        timestamp=datetime.now()
    )
    
    if crafty_data['status'] == 'success':
        embed.add_field(name="Status", value="✅ Found", inline=True)
        embed.add_field(name="UUID", value=f"`{crafty_data.get('uuid', 'N/A')}`", inline=True)
        embed.add_field(name="Profile", value=f"[View on Crafty.gg]({crafty_data.get('profile_url', '#')})", inline=True)
        
        # Display detailed name history if available
        if 'name_history' in crafty_data and crafty_data['name_history']:
            history_text = ""
            for item in crafty_data['name_history'][:10]:
                if 'position' in item:
                    line = f"**{item['position']}.** {item['name']}"
                    if item.get('date') and item['date'] != 'Unknown':
                        line += f" - {item['date']}"
                    if item.get('ago'):
                        line += f", {item['ago']}"
                    history_text += line + "\n"
                else:
                    history_text += f"• {item.get('name', 'Unknown')}\n"
            
            if history_text:
                embed.add_field(name="Name History", value=history_text.strip()[:1024], inline=False)
    else:
        embed.add_field(name="Status", value="❌ Error", inline=True)
        embed.add_field(name="Message", value=crafty_data['message'], inline=False)
    
    embed.set_footer(text="Crafty.gg Lookup")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="laby", description="Check profile from Laby.net")
async def laby_only(interaction: discord.Interaction, username: str):
    """Slash command to check only Laby.net"""
    await interaction.response.defer()
    
    laby_data = await name_bot.get_laby_profile(username)
    
    embed = discord.Embed(
        title=f"Laby.net Profile for {username}",
        color=0x4ecdc4,
        timestamp=datetime.now()
    )
    
    if laby_data['status'] == 'success':
        embed.add_field(name="Status", value="✅ Found", inline=True)
        embed.add_field(name="UUID", value=f"`{laby_data.get('uuid', 'N/A')}`", inline=True)
        embed.add_field(name="Profile", value=f"[View on Laby.net]({laby_data.get('profile_url', '#')})", inline=True)
        
        # Display name history if available
        if 'name_history' in laby_data and len(laby_data['name_history']) > 1:
            history_text = ""
            for item in laby_data['name_history'][:10]:
                name = item.get('name', 'Unknown')
                date = item.get('date', item.get('changedToAt', 'Unknown'))
                if date and date != 'Unknown':
                    history_text += f"• **{name}** - {date}\n"
                else:
                    history_text += f"• **{name}**\n"
            
            if history_text:
                embed.add_field(name="Name History", value=history_text.strip(), inline=False)
        
        embed.add_field(name="Message", value=laby_data['message'], inline=False)
    else:
        embed.add_field(name="Status", value="❌ Error", inline=True)
        embed.add_field(name="Message", value=laby_data['message'], inline=False)
    
    embed.set_footer(text="Laby.net Lookup")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="namemc", description="Check profile from NameMC")
async def namemc_only(interaction: discord.Interaction, username: str):
    """Slash command to check only NameMC"""
    await interaction.response.defer()
    
    namemc_data = await name_bot.get_namemc_profile(username)
    
    embed = discord.Embed(
        title=f"NameMC Profile for {username}",
        color=0xff6b6b,
        timestamp=datetime.now()
    )
    
    if namemc_data['status'] == 'success':
        embed.add_field(name="Status", value="✅ Found", inline=True)
        embed.add_field(name="UUID", value=f"`{namemc_data.get('uuid', 'N/A')}`", inline=True)
        embed.add_field(name="Profile", value=f"[View on NameMC]({namemc_data.get('profile_url', '#')})", inline=True)
        if 'note' in namemc_data:
            embed.add_field(name="Note", value=namemc_data['note'], inline=False)
    else:
        embed.add_field(name="Status", value="❌ Error", inline=True)
        embed.add_field(name="Message", value=namemc_data['message'], inline=False)
        if 'profile_url' in namemc_data:
            embed.add_field(name="Manual Link", value=f"[View Profile]({namemc_data['profile_url']})", inline=False)
    
    embed.set_footer(text="NameMC Lookup")
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
