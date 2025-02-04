import random

import discord
import numpy as np
from discord import app_commands, ui
from discord.app_commands import Choice
from discord.ext import commands

from cryptomc import CryptoMC


class CoinFlipConfirmationView(ui.View):

    def __init__(self, author: discord.User, target: discord.User, amount: int) -> None:
        super().__init__(timeout=60.0)
        self.author = author
        self.target = target
        self.amount = amount

    async def _is_target(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("Cette demande de coinflip ne vous cible pas.", ephemeral=True)
            return False

        return True

    @discord.ui.button(label="Accepter", emoji="✅", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._is_target(interaction):
            return

        user_info = await interaction.client.mongo.fetch_user_data(self.author.id)
        if user_info["bank"] < self.amount:
            return await interaction.response.send_message(
                f"{self.author.mention} n'a pas assez d'argent sur son compte bancaire.", ephemeral=True
            )

        target_info = await interaction.client.mongo.fetch_user_data(self.target.id)
        if target_info["bank"] < self.amount:
            return await interaction.response.send_message(
                f"Vous n'avez pas assez d'argent sur votre compte bancaire.", ephemeral=True
            )

        participant = [self.author, self.target]
        winner = random.choices([self.author, self.target])[0]
        participant.remove(winner)
        loser = participant[0]

        await interaction.client.mongo.update_user_data_document(
            winner.id, {"$inc": {"bank": self.amount, "coinflip_won": 1}}
        )
        await interaction.client.mongo.update_user_data_document(
            loser.id, {"$inc": {"bank": -self.amount, "coinflip_won": 1}}
        )

        coinflip_embed = discord.Embed(
            title=f"**🪙 Pile ou face**",
            description=f"{winner.mention} est le gagnant du pile ou face, il gagne **{self.amount}** "
                        f"{interaction.client.config['coin']}.",
            color=interaction.client.color,
            timestamp=discord.utils.utcnow()
        )
        coinflip_embed.set_footer(text=interaction.client.user.name, icon_url=interaction.client.user.display_avatar)

        await interaction.response.edit_message(content=None, view=None, embed=coinflip_embed)


class Games(commands.Cog):
    """The Cog containing all the games commands."""

    JOBS = {
        "💻 Développeur": (50, 100),
        "⚽ Footballeur": (300, 500),
        "🕵 Détective": (70, 130),
        "🛠 Forgeron": (30, 50),
        "🧑‍🔬 Chimiste": (60, 120),
        "🧑‍🍳 Cuisinier": (40, 100),
    }
    JOBS_WEIGHTS = [50, 3, 20, 50, 20, 40]

    ROULETTE_COLORS = {"red": 1.25, "black": 1.25, "green": 3}
    ROULETTE_WEIGHTS = [0.48, 0.48, 0.04]
    ROULETTE_EMOJIS = {"red": "🔴", "black": "⚫", "green": "🟢"}

    SLOTS_EMOJIS = {"🍒": 3, "🍌": 3, "🍎": 2, "🍓": 1.5}
    SLOTS_WEIGHTS = [0.1, 0.1, 0.4, 0.5]

    def __init__(self, client: CryptoMC):
        self.client = client

    async def _is_bet_amount_valid(self, interaction: discord.Interaction, amount: int) -> bool:
        if amount < 1:
            await interaction.response.send_message("Votre mise ne peut pas être inférieure à 1.", ephemeral=True)
            return False

        user_data = await self.client.mongo.fetch_user_data(interaction.user.id)
        if user_data["bank"] < amount:
            await interaction.response.send_message(
                "Vous n'avez pas assez d'argent sur votre compte bancaire.", ephemeral=True
            )
            return False

        return True

    @app_commands.command(name="mine")
    @app_commands.checks.cooldown(1, 60 * 60 * 2, key=lambda i: i.user.id)
    async def mine(self, interaction: discord.Interaction):
        """Miner de la EndCrypto."""
        mined = random.randint(300, 600)

        await self.client.mongo.update_user_data_document(interaction.user.id, {"$inc": {"bank": mined}})

        await self.client.embed(
            interaction, "**⛏ Minage**", f"Vous venez de miner **{mined}** {self.client.config['coin']}."
        )

    @app_commands.command(name="work")
    @app_commands.checks.cooldown(1, 60 * 20, key=lambda i: i.user.id)
    async def work(self, interaction: discord.Interaction):
        """Travailler pour gagner de la EndCrypto."""
        job = random.choices(list(self.JOBS), self.JOBS_WEIGHTS)[0]
        earned = random.randint(self.JOBS[job][0], self.JOBS[job][1])

        await self.client.mongo.update_user_data_document(interaction.user.id, {"$inc": {"bank": earned}})

        await self.client.embed(
            interaction, "**💵 Travail**",
            f"Vous venez de travailler en tant que **{job}** et vous avez gagné **{earned}** "
            f"{self.client.config['coin']}."
        )

    @app_commands.command(name="roulette")
    @app_commands.rename(color="couleur", amount="montant")
    @app_commands.describe(color="Couleur sur laquelle vous misez", amount="Montant que vous misez")
    @app_commands.choices(
        color=[
            Choice(name="Rouge", value="red"), Choice(name="Noir", value="black"), Choice(name="Vert", value="green")
        ]
    )
    @app_commands.checks.cooldown(1, 3, key=lambda i: i.user.id)
    async def roulette(self, interaction: discord.Interaction, color: Choice[str], amount: int):
        """Jouer à la roulette afin de tenter de gagner de la EndCrypto."""
        if not await self._is_bet_amount_valid(interaction, amount):
            return

        winning_color = random.choices(list(self.ROULETTE_COLORS), self.ROULETTE_WEIGHTS)[0]
        if winning_color == color.value:
            amount_won = int(amount * self.ROULETTE_COLORS[winning_color])
            update_actions = {"$inc": {"bank": amount_won, "roulette_won": 1}}
            msg = f"Vous venez de gagner votre partie de roulette, vous remportez **{amount_won}** " \
                  f"{self.client.config['coin']}."
        else:
            update_actions = {"$inc": {"bank": -amount, "roulette_lost": 1}}
            msg = f"Vous venez de perdre votre partie de roulette, vous perdez **{amount}** " \
                  f"{self.client.config['coin']}."

        await self.client.mongo.update_user_data_document(interaction.user.id, update_actions)

        await self.client.embed(
            interaction,
            title="**💈 Roulette**",
            description=f"Résultat: {self.ROULETTE_EMOJIS[winning_color]}\n\n"
                        f"{msg}"
        )

    @app_commands.command(name="slots")
    @app_commands.rename(amount="montant")
    @app_commands.describe(amount="Montant que vous misez")
    @app_commands.checks.cooldown(1, 3, key=lambda i: i.user.id)
    async def slots(self, interaction: discord.Interaction, amount: int):
        """Jouer à la machine à sous afin de tenter de gagner de la EndCrypto."""
        if not await self._is_bet_amount_valid(interaction, amount):
            return

        slots_result = random.choices(list(self.SLOTS_EMOJIS), weights=self.SLOTS_WEIGHTS, k=9)
        slots_rows = np.array_split(slots_result, 3)

        if all(x == slots_rows[1][0] for x in slots_rows[1]):
            amount_won = int(amount * self.SLOTS_EMOJIS[slots_rows[1][0]])
            update_actions = {"$inc": {"bank": amount_won, "slots_won": 1}}
            msg = f"Vous venez de gagner votre partie de machine à sous, vous remportez **{amount_won}** " \
                  f"{self.client.config['coin']}."
        else:
            update_actions = {"$inc": {"bank": -amount, "slots_won": 1}}
            msg = f"Vous venez de perdre votre partie de machine à sous, vous perdez **{amount}** " \
                  f"{self.client.config['coin']}."

        await self.client.mongo.update_user_data_document(interaction.user.id, update_actions)

        await self.client.embed(
            interaction,
            title="**🎰 Machine à sous**",
            description=f"🎰 {''.join(d for d in slots_rows[0])} 🎰\n"
                        f"➡ {''.join(d for d in slots_rows[1])} ⬅\n"
                        f"🎰 {''.join(d for d in slots_rows[2])} 🎰\n\n"
                        f"{msg}"
        )

    @app_commands.command(name="coinflip")
    @app_commands.rename(target="utilisateur", amount="montant")
    @app_commands.describe(target="Utilisateur contre qui vous voulez jouer", amount="Montant du coinflip")
    @app_commands.checks.cooldown(1, 3, key=lambda i: i.user.id)
    async def coinflip(self, interaction: discord.Interaction, target: discord.User, amount: int):
        """Jouer une partie de coinflip contre un utilisateur."""
        if not await self._is_bet_amount_valid(interaction, amount):
            return

        if target.id == interaction.user.id:
            return await interaction.response.send_message("Vous ne pouvez pas jouer contre vous-même.", ephemeral=True)

        if target.id == self.client.user.id:
            return await interaction.response.send_message("Vous ne pouvez pas jouer contre le bot.", ephemeral=True)

        target_data = await self.client.mongo.fetch_user_data(target.id)
        if target_data["bank"] < amount:
            return await interaction.response.send_message(
                f"{target.mention} n'a pas assez d'argent sur son compte bancaire.", ephemeral=True
            )

        await interaction.response.send_message(
            f"{target.mention}, vous venez de recevoir une demande de pile ou face de {interaction.user.mention} pour "
            f"**{amount}** {self.client.config['coin']}.\n"
            f"Vous pouvez accepter la demande en réagissant à ce message avec ✅ et la refuser avec ❌.",
            view=CoinFlipConfirmationView(interaction.user, target, amount)
        )


async def setup(client):
    await client.add_cog(Games(client))
