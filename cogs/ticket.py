import discord
from discord.ext import commands
from discord.commands import permissions, slash_command, Option
from utils.buttons import TicketPanelView, TicketResetView
import aiosqlite

async def cleanup(guild: discord.Guild):
    for channel in guild.channels:
        if channel.name.lower().startswith('ticket'):
            await channel.delete()


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group(name="panel")
    async def panel_(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(title="Panel", description="**--> `panel create`: Creates a panel\nUsage: `panel create <channel> [name]`\nExample: `panel create #ticket Get a ticket`\n\n--> `panel delete`: Deletes a panel\nUsage: `panel delete <channel> [panel_id]`\nExample: `panel delete #ticket 987654321123456789`\n\n--> `panel edit`: Edits the name of a panel\nUsage: `panel edit <channel> [panel_id] (name)`\nExample: `panel edit #ticket 987654321123456789 I just changed the name of the panel!`**", color=discord.Color.green())
            await ctx.send(embed=embed)
    
    @commands.group(name="ticket")
    async def ticket_(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(title="Ticket", description="**--> `ticket role add` Adds a role to ticket channel. By doing this the role you add can view tickets! By default it is available for only admins\nUsage: `ticket role add <role>`\nExample: `ticket role add @MODS`\n\n--> `ticket role remove` Just the vice versa of the one stated above. Removes a role from viewing ticket\nUsage: `ticket role remove <role>`\nExample: `ticket role remove @MODS`\n\n--> `ticket reset` Resets the ticket count!\nUsage: `ticket reset`**", color=discord.Color.green())
            await ctx.send(embed=embed)

    @panel_.command(name="create", aliases=['c', 'make', 'add'])
    async def create_(self, ctx: commands.Context, channel: discord.TextChannel = None, *, name = None):
        if not channel:
            embed = discord.Embed(
                description="**<:error:897382665781669908> Please enter a channel to make the panel in!**",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        if not name:
            embed = discord.Embed(
                description="**<:error:897382665781669908> Please enter a name!**",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        if not ctx.author.guild_permissions.manage_channels:
            embed = discord.Embed(
                description="**<:error:897382665781669908> You can't do that!**",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        if channel == ctx.channel:
            panel = discord.Embed(
                title=name,
                description="To create a ticket react with 📩",
                color=discord.Color.green(),
            )
            panel.set_footer(text=f"{self.bot.user.name} - Ticket Panel", icon_url=self.bot.user.avatar.url)

            message = await channel.send(embed=panel, view=TicketPanelView())
            await channel.send(f"Panel id of the panel you just created in <#{channel.id}>: {message.id}")
        if channel != ctx.channel:
            panel = discord.Embed(
                title=name,
                description="To create a ticket react with 📩",
                color=discord.Color.green(),
            )
            panel.set_footer(text=f"{self.bot.user.name} - Ticket Panel", icon_url=self.bot.user.avatar.url)

            message = await channel.send(embed=panel, view=TicketPanelView())
            embed2 = discord.Embed(description=f"**<:tick:897382645321850920> Successfully posted the panel in {channel.mention}\n\nPanel ID: `{message.id}`**", color=discord.Color.green())
            await ctx.send(embed=embed2)


    @panel_.command(name="delete", aliases=['del'])
    @commands.has_permissions(manage_channels=True)
    async def delete_(self, ctx: commands.Context, channel: discord.TextChannel, panel_id: int):
        message = await channel.fetch_message(panel_id)
        try:
            await message.delete()
            embed = discord.Embed(description="**<:tick:897382645321850920> Successfully deleted the panel!**", color=discord.Color.green())
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(description="**<:error:897382665781669908> I couldn't do that!**", color=discord.Color.green())
            await ctx.send(embed=embed)
        except discord.NotFound:
            embed = discord.Embed(description=f"**<:error:897382665781669908> I couldn't find a panel with id `{panel_id}`! Please try again after checking the id!**")
            await ctx.send(embed=embed)

    @panel_.command(name="edit", aliases=['e'])
    async def edit_(self, ctx: commands.Context, channel: discord.TextChannel, panel_id: int, *, name: str):
        message = await channel.fetch_message(panel_id)
        try:
            embed1 = discord.Embed(title=name, description="To create a ticket react with 📩", color=discord.Color.green())
            await message.edit(embed=embed1)
            embed = discord.Embed(description="**<:tick:897382645321850920> Successfully edited the panel!**", color=discord.Color.green())
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(description="**<:error:897382665781669908> I couldn't do that!**", color=discord.Color.green())
            await ctx.send(embed=embed)
        except discord.NotFound:
            embed = discord.Embed(description=f"**<:error:897382665781669908> I couldn't find a panel with id `{panel_id}`! Please try again after checking the id!**")
            await ctx.send(embed=embed)


    # @ticket_.command(name="role")
    # async def role_(self, ctx: commands.Context, type: str, *, role: discord.Role):
    #     if type.lower() == "add":
    #         async with aiosqlite.connect("utils/databases/main.db") as db:
    #             async with db.cursor() as cursor:
    #                 await cursor.execute(f'INSERT INTO ticket(roles) WHERE guild_id = {ctx.guild.id} VALUES(?)', (role.id))
    #             await db.commit()
    #             await cursor.close()
    #             await ctx.send("Done!")
    #     if type.lower() == "remove":
    #         async with aiosqlite.connect("utils/databases/main.db") as db:
    #             async with db.cursor() as cursor:
    #                 await cursor.execute(f'DELETE FROM ticket(role) WHERE guild_id = {ctx.guild.id} VALUES(?)', (role.id))
    #             await db.commit()
    #             await cursor.close()
    #             await ctx.send("Done!")

    @ticket_.command(name="reset")
    @commands.has_permissions(manage_channels=True)
    async def reset_(self, ctx: commands.Context):
        embed = discord.Embed(description=f"Are you sure you want to reset the **Ticket Count**?\n------------------------------------------------\nRespond Within **15** seconds!", color=discord.Color.orange())
        message = await ctx.send(embed=embed)
        await message.edit(embed=embed, view=TicketResetView(ctx, message))

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def clean(self, ctx: commands.Context):
        await cleanup(ctx.guild)
        await ctx.send("<:tick:897382645321850920> Cleaned up the server!")


def setup(bot):
    bot.add_cog(TicketCog(bot))