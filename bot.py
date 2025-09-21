import discord
from discord.ext import commands
import aiohttp
import asyncio
from datetime import datetime
import json
import sys
from bs4 import BeautifulSoup


# Load configuration
def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found!")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Invalid JSON in config.json")
        sys.exit(1)


config = load_config()

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

    # ---------------------- Mojang API ----------------------
    async def get_uuid_from_username(self, username):
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

    async def get_mojang_name_history(self, uuid):
        session = await self.get_session()
        try:
            async with session.get(f'https://api.mojang.com/user/profiles/{uuid}/names') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    history = []
                    for entry in data:
                        history.append({
                            'name': entry['name'],
                            'changedToAt': entry.get('changedToAt', 'Current')
                        })
                    return history
        except Exception as e:
            print(f"Error fetching Mojang name history: {e}")
        return []

    # ---------------------- Crafty.gg ----------------------
    async def get_crafty_profile(self, username):
        session = await self.get_session()
        uuid = await self.get_uuid_from_username(username)
        if not uuid:
            return {'status': 'error', 'message': 'Username not found'}

        headers = {'User-Agent': 'Mozilla/5.0'}

        try:
            # Try API endpoint first
            api_url = f'https://crafty.gg/api/profile/{username}'
            async with session.get(api_url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Extract name history
                    name_history = []
                    if 'nameHistory' in data:
                        for entry in data['nameHistory']:
                            name_history.append({
                                'name': entry.get('name', 'Unknown'),
                                'changedToAt': entry.get('changedToAt', 'Current')
                            })
                    return {
                        'status': 'success',
                        'profile_url': f'https://crafty.gg/@{username}',
                        'uuid': uuid,
                        'name_history': name_history or await self.get_mojang_name_history(uuid)
                    }
        except:
            pass

        # Fallback to web scraping
        try:
            async with session.get(f'https://crafty.gg/@{username}', headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    # Look for JSON in <script> tags
                    name_history = []
                    for script in soup.find_all('script'):
                        if script.string and 'nameHistory' in script.string:
                            try:
                                import re, json
                                json_texts = re.findall(r'\{.*"nameHistory".*?\}', script.string)
                                for jt in json_texts:
                                    jdata = json.loads(jt)
                                    for entry in jdata.get('nameHistory', []):
                                        name_history.append({
                                            'name': entry.get('name', 'Unknown'),
                                            'changedToAt': entry.get('changedToAt', 'Current')
                                        })
                            except:
                                continue
                    if not name_history:
                        name_history = await self.get_mojang_name_history(uuid)
                    return {
                        'status': 'success',
                        'profile_url': f'https://crafty.gg/@{username}',
                        'uuid': uuid,
                        'name_history': name_history
                    }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

        return {'status': 'error', 'message': 'Profile not found'}

    # ---------------------- Laby.net ----------------------
    async def get_laby_profile(self, username):
        session = await self.get_session()
        uuid = await self.get_uuid_from_username(username)
        if not uuid:
            return {'status': 'error', 'message': 'Username not found'}

        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            api_urls = [
                f'https://laby.net/api/user/{uuid}',
                f'https://laby.net/api/v3/user/{uuid}/profile'
            ]
            for url in api_urls:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        name_history = []
                        if 'username_history' in data:
                            for entry in data['username_history']:
                                name_history.append({
                                    'name': entry.get('username', 'Unknown'),
                                    'changedToAt': entry.get('changed_at', 'Current')
                                })
                        if not name_history:
                            name_history = await self.get_mojang_name_history(uuid)
                        return {
                            'status': 'success',
                            'profile_url': f'https://laby.net/@{username}',
                            'uuid': uuid,
                            'name_history': name_history
                        }
        except:
            pass

        # Fallback scraping
        try:
            async with session.get(f'https://laby.net/@{username}', headers=headers) as resp:
                if resp.status == 200:
                    return {
                        'status': 'success',
                        'profile_url': f'https://laby.net/@{username}',
                        'uuid': uuid,
                        'name_history': await self.get_mojang_name_history(uuid)
                    }
        except:
            pass

        return {'status': 'error', 'message': 'Profile not found'}

    # ---------------------- NameMC ----------------------
    async def get_namemc_profile(self, username):
        uuid = await self.get_uuid_from_username(username)
        if not uuid:
            return {'status': 'error', 'message': 'Username not found'}

        formatted_uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
        return {
            'status': 'success',
            'profile_url': f'https://namemc.com/profile/{formatted_uuid}',
            'uuid': uuid,
            'name_history': await self.get_mojang_name_history(uuid),
            'note': 'NameMC has no public API. Using Mojang history.'
        }

    async def close_session(self):
        if self.session:
            await self.session.close()


# Initialize handler
name_bot = NameHistoryBot()


# ---------------------- Discord Commands ----------------------
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')


# General name history command
@bot.tree.command(name="namehistory", description="Check name history")
async def name_history(interaction: discord.Interaction, username: str):
    await interaction.response.defer()
    embed = discord.Embed(title=f"Name History: {username}", color=0x00ff00, timestamp=datetime.now())

    # Fetch data
    nm_data = await name_bot.get_namemc_profile(username)
    laby_data = await name_bot.get_laby_profile(username)
    crafty_data = await name_bot.get_crafty_profile(username)

    # Helper to format history
    def format_history(data):
        if 'name_history' in data and data['name_history']:
            return ' → '.join([f"{entry['name']}" for entry in data['name_history']])
        return "No history found"

    # NameMC
    embed.add_field(name="🔍 NameMC",
                    value=f"✅ Status: Found\n**UUID:** `{nm_data['uuid']}`\n**Profile:** [Link]({nm_data['profile_url']})\n**History:** {format_history(nm_data)}",
                    inline=False)

    # Laby
    embed.add_field(name="🌐 Laby.net",
                    value=f"✅ Status: Found\n**UUID:** `{laby_data['uuid']}`\n**Profile:** [Link]({laby_data['profile_url']})\n**History:** {format_history(laby_data)}",
                    inline=False)

    # Crafty
    embed.add_field(name="⚡ Crafty.gg",
                    value=f"✅ Status: Found\n**UUID:** `{crafty_data['uuid']}`\n**Profile:** [Link]({crafty_data['profile_url']})\n**History:** {format_history(crafty_data)}",
                    inline=False)

    await interaction.followup.send(embed=embed)


# Close session on shutdown
@bot.event
async def on_close():
    await name_bot.close_session()


# Run bot
if __name__ == "__main__":
    token = config.get('token')
    if not token:
        print("Error: No token found in config.json")
        sys.exit(1)
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("Error: Invalid token")
