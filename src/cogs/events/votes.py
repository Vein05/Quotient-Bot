from discord import Webhook
from datetime import datetime, timedelta
from core import Cog, Quotient
from contextlib import suppress
import constants
import models, discord

from utils.time import strtime


class Votes(Cog):
    def __init__(self, bot: Quotient):
        self.bot = bot
        self.hook = Webhook.from_url(self.bot.config.PUBLIC_LOG, session=self.bot.session)

    @property
    def reminders(self):
        return self.bot.get_cog("Reminders")

    @Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """we grant users voter, premium role if they join later."""
        if not member.guild or not member.guild.id == self.bot.server.id:
            return

        if await models.Votes.get(user_id=member.id, is_voter=True).exists():
            await member.add_roles(discord.Object(id=self.bot.config.VOTER_ROLE))

        if await models.User.get(pk=member.id, is_premium=True).exists():
            await member.add_roles(discord.Object(id=self.bot.config.PREMIUM_ROLE))

    @Cog.listener()
    async def on_vote(self, record: models.Votes):
        await models.Votes.filter(user_id=record.user_id).update(notified=True)
        await self.reminders.create_timer(record.expire_time, "vote", user_id=record.user_id)
        member = self.bot.server.get_member(record.user_id)
        if member is not None:
            await member.add_roles(discord.Object(id=self.bot.config.VOTER_ROLE), reason="They voted for me.")

        member = member if member is not None else await self.bot.fetch_user(record.user_id)
        with suppress(discord.HTTPException, AttributeError):
            record = await models.Votes.get(pk=record.user_id)
            embed = discord.Embed(color=discord.Color.green(), description=f"Thanks **{member}** for voting.")
            embed.set_image(url=constants.random_thanks())
            embed.set_footer(text=f"Your total votes: {record.total_votes}")
            await self.hook.send(embed=embed, username="vote-logs", avatar_url=self.bot.user.avatar.url)

    @Cog.listener()
    async def on_vote_timer_complete(self, timer: models.Timer):
        user_id = timer.kwargs["user_id"]
        vote = await models.Votes.filter(user_id=user_id).first()

        member = self.bot.server.get_member(user_id)
        if member is not None:
            await member.remove_roles(discord.Object(id=self.bot.config.VOTER_ROLE), reason="Their vote expired.")

        member = member if member is not None else await self.bot.fetch_user(user_id)
        if vote.reminder:

            embed = discord.Embed(
                color=self.bot.color,
                description=f"{constants.random_greeting()}, You asked me to remind you to vote.",
                title="Vote Expired!",
                url="https://quotientbot.xyz/vote",
            )
            try:
                await member.send(embed=embed)
            except:
                pass

        await models.Votes.filter(user_id=user_id).update(is_voter=False, notified=False)

    @Cog.listener()
    async def on_premium_purchase(self, record: models.Premium):
        await models.Premium.filter(order_id=record.order_id).update(is_notified=True)
        member = self.bot.server.get_member(record.user_id)
        if member is not None:
            await member.add_roles(discord.Object(id=self.bot.config.PREMIUM_ROLE), reason="They purchased premium.")

        member = member if member is not None else await self.bot.fetch_user(record.user_id)

        with suppress(discord.HTTPException, AttributeError):
            embed = discord.Embed(
                color=discord.Color.gold(), description=f"Thanks **{member}** for purchasing Quotient Premium."
            )
            embed.set_image(url=constants.random_thanks())
            await self.hook.send(
                embed=embed,
                username="premium-logs",
                avatar_url=self.bot.config.PREMIUM_AVATAR,
            )

        embed = discord.Embed(
            color=discord.Color.gold(),
            title="Premium Purchase Successful",
            description=f"{constants.random_greeting()} {member.mention},\nThanks for purchasing Quotient Premium.\nYou have now access to all Premium Perks and A special role in our server.",
        )
        if member not in self.bot.server.members:
            embed.description += f"\n\nI notice you are not in our support server. Join it by [clicking here]({self.bot.config.SERVER_LINK}) to get special role."

        embed.description += f"You can upgrade a server by using `qboost` command in that server or you can use `qhelp premium` command to get a list of commands related to Quotient Premium."

        try:
            await member.send(embed=embed)
        except:
            pass

        await self.reminders.create_timer(
            datetime.now(tz=constants.IST) + timedelta(days=30), "user_premium", user_id=record.user_id
        )
