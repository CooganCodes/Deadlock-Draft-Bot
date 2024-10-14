import os
import discord
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import re

# Load the bot token from .env file
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Global variables to keep track of the game state
game_in_progress = False
current_phase = None  # 'captain', 'ban', 'draft'
captains = {'Amber Hand': None, 'Sapphire Flame': None}
bans = {'Amber Hand': None, 'Sapphire Flame': None}
draft_picks = {'Amber Hand': [], 'Sapphire Flame': []}
available_characters = []
turn_order = []  # Will be populated based on the sequence
current_turn = None  # Will be 'Amber Hand' or 'Sapphire Flame'
draft_message = None  # Message object to edit during draft phase

# Corrected character list
characters = {
    "Abrams": "Abrams.png",
    "Bebop": "Bebop.png",
    "Dynamo": "Dynamo.png",
    "Grey Talon": "Grey_Talon.png",
    "Haze": "Haze.png",
    "Infernus": "Infernus.png",
    "Ivy": "Ivy.png",
    "Kelvin": "Kelvin.png",
    "Lady Geist": "Lady_Geist.png",
    "Lash": "Lash.png",
    "McGinnis": "McGinnis.png",
    "Mo & Krill": "Mo_and_Krill.png",
    "Paradox": "Paradox.png",
    "Pocket": "Pocket.png",
    "Seven": "Seven.png",
    "Shiv": "Shiv.png",
    "Vindicta": "Vindicta.png",
    "Viscous": "Viscous.png",
    "Warden": "Warden.png",
    "Wraith": "Wraith.png",
    "Yamato": "Yamato.png"
}

available_characters = list(characters.keys())

def sanitize_filename(name):
    # Replace spaces and special characters with underscores
    return re.sub(r'[^A-Za-z0-9]+', '_', name)

@bot.command()
async def start(ctx):
    global game_in_progress
    if game_in_progress:
        await ctx.send("A game is already in progress.")
        return

    reset_game()
    game_in_progress = True
    await ctx.send("Starting a new game! Captains, please select your teams.", view=CaptainSelectionView())
    print("Game started. Waiting for captains to select teams.")

def reset_game():
    global game_in_progress, current_phase, captains, bans, draft_picks, available_characters, turn_order, current_turn, draft_message
    game_in_progress = False
    current_phase = None
    captains = {'Amber Hand': None, 'Sapphire Flame': None}
    bans = {'Amber Hand': None, 'Sapphire Flame': None}
    draft_picks = {'Amber Hand': [], 'Sapphire Flame': []}
    available_characters[:] = list(characters.keys())
    turn_order = []
    current_turn = None
    draft_message = None
    print("Game state has been reset.")

    # Clean up temporary images
    for filename in os.listdir('.'):
        if filename.startswith('banned_') and filename.endswith('.png'):
            os.remove(filename)
            print(f"Deleted temporary file: {filename}")
    if os.path.exists('bans.png'):
        os.remove('bans.png')
        print("Deleted bans.png")
    if os.path.exists('picks_updated.png'):
        os.remove('picks_updated.png')
        print("Deleted picks_updated.png")

class CaptainSelectionView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Amber Hand Captain", style=discord.ButtonStyle.red)
    async def amber_captain(self, interaction: discord.Interaction, button: discord.ui.Button):
        if captains['Amber Hand'] is None:
            captains['Amber Hand'] = interaction.user
            await interaction.response.send_message(f"You are now the captain of Amber Hand!", ephemeral=True)
            print(f"Amber Hand captain selected: {interaction.user}")
            await self.check_captains(interaction)
        else:
            await interaction.response.send_message("Amber Hand already has a captain.", ephemeral=True)

    @discord.ui.button(label="Sapphire Flame Captain", style=discord.ButtonStyle.blurple)
    async def sapphire_captain(self, interaction: discord.Interaction, button: discord.ui.Button):
        if captains['Sapphire Flame'] is None:
            captains['Sapphire Flame'] = interaction.user
            await interaction.response.send_message(f"You are now the captain of Sapphire Flame!", ephemeral=True)
            print(f"Sapphire Flame captain selected: {interaction.user}")
            await self.check_captains(interaction)
        else:
            await interaction.response.send_message("Sapphire Flame already has a captain.", ephemeral=True)

    async def check_captains(self, interaction):
        if captains['Amber Hand'] and captains['Sapphire Flame']:
            await interaction.message.delete()
            await start_ban_phase(interaction.channel)

async def start_ban_phase(channel):
    global current_phase, current_turn
    current_phase = 'ban'
    current_turn = 'Amber Hand'
    print("Ban Phase started.")
    await send_ban_embed(channel)

async def send_ban_embed(channel):
    embed = discord.Embed(title="Ban Phase", color=0xff0000)
    embed.description = f"It's {current_turn}'s turn to ban."

    # Create composite image with bans
    await create_ban_image()

    file = discord.File("bans.png", filename="bans.png")
    embed.set_image(url="attachment://bans.png")

    view = BanSelectionView()
    await channel.send(embed=embed, view=view, file=file)

class BanSelectionView(View):
    def __init__(self):
        super().__init__(timeout=None)
        for character in available_characters:
            self.add_item(BanButton(character))

class BanButton(Button):
    def __init__(self, character):
        super().__init__(label=character, style=discord.ButtonStyle.secondary)
        self.character = character

    async def callback(self, interaction: discord.Interaction):
        global current_turn
        if interaction.user != captains[current_turn]:
            await interaction.response.send_message("It's not your turn to ban.", ephemeral=True)
            return
        if self.character not in available_characters:
            await interaction.response.send_message("Character not available.", ephemeral=True)
            return
        bans[current_turn] = self.character
        available_characters.remove(self.character)
        print(f"{current_turn} banned {self.character}")

        # Overlay 'X' on banned character images
        await create_banned_image(self.character)

        await interaction.response.send_message(f"{self.character} has been banned by {current_turn}.", ephemeral=True)
        if all(bans.values()):
            # Both bans are selected, show "Continue" button
            await interaction.message.delete()
            await show_ban_summary(interaction.channel)
        else:
            switch_turn()
            await interaction.message.delete()
            await send_ban_embed(interaction.channel)

async def show_ban_summary(channel):
    embed = discord.Embed(title="Ban Phase Complete", color=0xffa500)
    embed.description = "Both teams have selected their bans. Click 'Continue' to proceed to the Draft phase."

    # Create composite image with bans
    await create_ban_image()

    file = discord.File("bans.png", filename="bans.png")
    embed.set_image(url="attachment://bans.png")

    view = ContinueButtonView()
    await channel.send(embed=embed, view=view, file=file)

class ContinueButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.green)
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != captains['Amber Hand'] and interaction.user != captains['Sapphire Flame']:
            await interaction.response.send_message("Only the captains can proceed to the Draft phase.", ephemeral=True)
            return
        await interaction.message.delete()
        await start_draft_phase(interaction.channel)

async def create_banned_image(character):
    image_path = characters.get(character)
    if image_path and os.path.isfile(image_path):
        base_image = Image.open(image_path).convert("RGBA")
        overlay = Image.open("x.png").convert("RGBA")
        overlay = overlay.resize(base_image.size)
        combined = Image.alpha_composite(base_image, overlay)
        sanitized_name = sanitize_filename(character)
        combined.save(f"banned_{sanitized_name}.png")
        print(f"Created banned image for {character} as banned_{sanitized_name}.png")
    else:
        print(f"Image file for {character} not found at {image_path}")

async def create_ban_image():
    # Use bans_bg.png as the background image
    if os.path.isfile('bans_bg.png'):
        background_image = Image.open('bans_bg.png').convert('RGBA')
        width, height = background_image.size
        combined_image = background_image.copy()
    else:
        # If bans_bg.png doesn't exist, create a new image
        width = 800
        height = 300
        combined_image = Image.new('RGBA', (width, height), (255, 255, 255, 255))

    draw = ImageDraw.Draw(combined_image)
    font = ImageFont.truetype("arial.ttf", 24)  # Increase font size

    # Increase ban image sizes
    ban_image_size = (200, 200)
    ban_y_offset = 50  # Adjust as needed

    # Add banned character images
    for idx, team in enumerate(['Amber Hand', 'Sapphire Flame']):
        character = bans.get(team)
        x_offset = idx * width // 2 + (width // 4 - ban_image_size[0] // 2)
        if character:
            sanitized_name = sanitize_filename(character)
            banned_image_path = f"banned_{sanitized_name}.png"
            if os.path.isfile(banned_image_path):
                ban_image = Image.open(banned_image_path).convert("RGBA").resize(ban_image_size)
                combined_image.paste(ban_image, (x_offset, ban_y_offset), ban_image)
                text_x = x_offset + ban_image_size[0] // 2 - 50
                text_y = ban_y_offset + ban_image_size[1] + 10
                draw.text((text_x, text_y), character, fill="black", font=font)
                print(f"Added banned image for {team}: {banned_image_path}")
            else:
                draw.text((x_offset + 50, ban_y_offset + 100), "Image Not Found", fill="black", font=font)
                print(f"Banned image not found for {team}: {banned_image_path}")
        else:
            draw.text((x_offset + 50, ban_y_offset + 100), "No Ban", fill="black", font=font)
            print(f"No ban for {team}")

    # Save the combined image
    combined_image.save("bans.png")

def switch_turn():
    global current_turn
    current_turn = 'Sapphire Flame' if current_turn == 'Amber Hand' else 'Amber Hand'
    print(f"Turn switched. It's now {current_turn}'s turn.")

async def start_draft_phase(channel):
    global current_phase, turn_order, current_turn
    current_phase = 'draft'
    turn_order.extend([
        'Amber Hand', 'Sapphire Flame', 'Sapphire Flame', 'Amber Hand', 'Amber Hand', 'Sapphire Flame',
        'Sapphire Flame', 'Amber Hand', 'Amber Hand', 'Sapphire Flame', 'Sapphire Flame', 'Amber Hand'
    ])
    current_turn = turn_order.pop(0)
    print("Draft Phase started.")
    await send_draft_embed(channel)

async def send_draft_embed(channel):
    global draft_message
    embed = discord.Embed(title="Draft Phase", color=0x00ff00)
    embed.description = f"It's {current_turn}'s turn to pick."

    # Display picks and bans in the embed fields
    embed.add_field(
        name="Amber Hand",
        value=(
            f"**Captain:** {captains['Amber Hand'].mention}\n"
            f"**Ban:** {bans['Amber Hand'] or 'None'}\n"
            f"**Picks:** {', '.join(draft_picks['Amber Hand']) or 'None'}"
        ),
        inline=True
    )
    embed.add_field(
        name="Sapphire Flame",
        value=(
            f"**Captain:** {captains['Sapphire Flame'].mention}\n"
            f"**Ban:** {bans['Sapphire Flame'] or 'None'}\n"
            f"**Picks:** {', '.join(draft_picks['Sapphire Flame']) or 'None'}"
        ),
        inline=True
    )

    # Create composite image with picks and bans
    await create_picks_image()

    file = discord.File("picks_updated.png", filename="picks.png")
    embed.set_image(url="attachment://picks.png")

    view = DraftSelectionView()

    if draft_message is None:
        # Send a new message and store it
        draft_message = await channel.send(embed=embed, view=view, file=file)
    else:
        # Edit the existing message
        await draft_message.edit(embed=embed, view=view, attachments=[file])

class DraftSelectionView(View):
    def __init__(self):
        super().__init__(timeout=None)
        for character in available_characters:
            self.add_item(DraftButton(character))

class DraftButton(Button):
    def __init__(self, character):
        super().__init__(label=character, style=discord.ButtonStyle.secondary)
        self.character = character

    async def callback(self, interaction: discord.Interaction):
        global current_turn
        if interaction.user != captains[current_turn]:
            await interaction.response.send_message("It's not your turn to pick.", ephemeral=True)
            return
        if self.character not in available_characters:
            await interaction.response.send_message("Character not available.", ephemeral=True)
            return
        draft_picks[current_turn].append(self.character)
        available_characters.remove(self.character)
        print(f"{current_turn} picked {self.character}")
        await interaction.response.send_message(f"{self.character} has been picked by {current_turn}.", ephemeral=True)
        if not turn_order:
            await send_draft_embed(interaction.channel)
            await show_final_summary(interaction.channel)
        else:
            current_turn = turn_order.pop(0)
            await send_draft_embed(interaction.channel)

async def create_picks_image():
    # Use picks.png as the background image
    if os.path.isfile('picks.png'):
        background_image = Image.open('picks.png').convert('RGBA')
        width, height = background_image.size
        combined_image = background_image.copy()
    else:
        # If picks.png doesn't exist, create a new image
        width = 800
        height = 1000
        combined_image = Image.new('RGBA', (width, height), (255, 255, 255, 255))

    draw = ImageDraw.Draw(combined_image)
    font = ImageFont.truetype("arial.ttf", 24)  # Increase font size

    # Increase character image sizes
    ban_image_size = (200, 200)
    pick_image_size = (150, 150)

    # Adjust starting positions
    ban_y_offset = 50
    pick_y_offset = ban_y_offset + ban_image_size[1] + 50  # Adjust as needed

    # Add Banned Characters
    for idx, team in enumerate(['Amber Hand', 'Sapphire Flame']):
        character = bans.get(team)
        x_offset = idx * width // 2 + (width // 4 - ban_image_size[0] // 2)
        if character:
            sanitized_name = sanitize_filename(character)
            banned_image_path = f"banned_{sanitized_name}.png"
            if os.path.isfile(banned_image_path):
                ban_image = Image.open(banned_image_path).convert("RGBA").resize(ban_image_size)
                combined_image.paste(ban_image, (x_offset, ban_y_offset), ban_image)
                text_x = x_offset + ban_image_size[0] // 2 - 50
                text_y = ban_y_offset + ban_image_size[1] + 10
                draw.text((text_x, text_y), character, fill="black", font=font)
                print(f"Added banned image for {team}: {banned_image_path}")
            else:
                draw.text((x_offset + 50, ban_y_offset + 100), "Image Not Found", fill="black", font=font)
                print(f"Banned image not found for {team}: {banned_image_path}")
        else:
            draw.text((x_offset + 50, ban_y_offset + 100), "No Ban", fill="black", font=font)
            print(f"No ban for {team}")

    # Add Picks in 2 per row
    picks_per_row = 2
    for idx, team in enumerate(['Amber Hand', 'Sapphire Flame']):
        picks = draft_picks[team]
        for pick_idx, character in enumerate(picks):
            char_image_path = characters.get(character)
            if char_image_path and os.path.isfile(char_image_path):
                char_image = Image.open(char_image_path).convert("RGBA").resize(pick_image_size)
                col = pick_idx % picks_per_row
                row = pick_idx // picks_per_row
                x_offset = idx * width // 2 + (width // 4 - pick_image_size[0]) + col * (pick_image_size[0] + 20)
                y_offset = pick_y_offset + row * (pick_image_size[1] + 50)
                combined_image.paste(char_image, (x_offset, y_offset), char_image)
                text_x = x_offset + pick_image_size[0] // 2 - 50
                text_y = y_offset + pick_image_size[1] + 10
                draw.text((text_x, text_y), character, fill="black", font=font)
            else:
                print(f"Image not found for pick {character} of team {team}")

    # Save the combined image without overwriting the original picks.png
    combined_image.save("picks_updated.png")

async def show_final_summary(channel):
    global draft_message
    embed = discord.Embed(title="Draft Summary", color=0x0000ff)

    # Display final picks and bans in the embed fields
    embed.add_field(
        name="Amber Hand",
        value=(
            f"**Captain:** {captains['Amber Hand'].mention}\n"
            f"**Ban:** {bans['Amber Hand'] or 'None'}\n"
            f"**Picks:** {', '.join(draft_picks['Amber Hand'])}"
        ),
        inline=True
    )
    embed.add_field(
        name="Sapphire Flame",
        value=(
            f"**Captain:** {captains['Sapphire Flame'].mention}\n"
            f"**Ban:** {bans['Sapphire Flame'] or 'None'}\n"
            f"**Picks:** {', '.join(draft_picks['Sapphire Flame'])}"
        ),
        inline=True
    )

    # Create final summary image
    await create_picks_image()  # Reuse the picks image

    file = discord.File("picks_updated.png", filename="picks.png")
    embed.set_image(url="attachment://picks.png")

    await draft_message.edit(embed=embed, view=None, attachments=[file])
    reset_game()

bot.run(TOKEN)
