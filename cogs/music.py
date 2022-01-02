import re
import math
import discord
import lavalink
from discord.ext import commands
import asyncio

url_rx = re.compile(r"https?://(?:www\.)?.+")


class LavalinkVoiceClient(discord.VoiceClient):
    def __init__(self, bot: commands.Bot, channel: discord.abc.Connectable):
        self.client = bot
        self.channel = channel
        if hasattr(self.client, "lavalink"):
            self.lavalink = self.client.lavalink
        else:
            self.client.lavalink = lavalink.Client(919314151535419463)
            self.client.lavalink.add_node("localhost", 2333, "youshallnotpass", "in", "default-node")
            self.lavalink = self.client.lavalink

    async def on_voice_server_update(self, data):
        lavalink_data = {"t": "VOICE_SERVER_UPDATE", "d": data}
        await self.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(self, data):
        lavalink_data = {"t": "VOICE_STATE_UPDATE", "d": data}
        await self.lavalink.voice_update_handler(lavalink_data)

    async def connect(self, *, timeout: float, reconnect: bool) -> None:
        """
        Connect the bot to the voice channel and create a player_manager
        if it doesn't exist yet.
        """
        self.lavalink.player_manager.create(guild_id=self.channel.guild.id)
        await self.channel.guild.change_voice_state(channel=self.channel)

    async def disconnect(self, *, force: bool) -> None:
        """
        Handles the disconnect.
        Cleans up running player and leaves the voice client.
        """
        player = self.lavalink.player_manager.get(self.channel.guild.id)
        if not force and not player.is_connected:
            return

        await self.channel.guild.change_voice_state(channel=None)
        player.channel_id = None
        self.cleanup()


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        if not hasattr(
            bot, "lavalink"
        ):
            bot.lavalink = lavalink.Client(919314151535419463)
            bot.lavalink.add_node("localhost", 2333, "youshallnotpass", "in", "default-node")

        lavalink.add_event_hook(self.track_hook)

    def cog_unload(self):
        """Cog unload handler. This removes any event hooks that were registered."""
        self.bot.lavalink._event_hooks.clear()

    async def cog_before_invoke(self, ctx):
        """Command before-invoke handler."""
        guild_check = ctx.guild is not None

        if guild_check:
            await self.ensure_voice(ctx)

        return guild_check

    async def ensure_voice(self, ctx):
        """This check ensures that the bot and command author are in the same voice channel."""
        player = self.bot.lavalink.player_manager.create(
            ctx.guild.id, endpoint=str(ctx.guild.region)
        )

        should_connect = ctx.command.name in ("play",)

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(embed=discord.Embed(description="**<:error:897382665781669908> Join a voice channel first.**", color=discord.Color.red()))

        if not player.is_connected:
            if not should_connect:
                embed = discord.Embed(description="**<:error:897382665781669908> I am not connected to a voice channel**", color=discord.Color.red())

            player.store("channel", ctx.channel.id)
            await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                await ctx.send(embed=discord.Embed(description="**<:error:897382665781669908>You need to be in my voice channel.**", color=discord.Color.red()))

    async def track_hook(self, event):
        if isinstance(event, lavalink.events.QueueEndEvent):
            guild_id = int(event.player.guild_id)
            guild = self.bot.get_guild(guild_id)
            await guild.voice_client.disconnect(force=True)

    @commands.command(name="play", aliases=["p", "music"])
    async def play(self, ctx, *, query):
        """Play a song through an url or a query"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        query = query.strip("<>")

        if not query.startswith("http"):
            query = f"ytsearch:{query}"

        results = await player.node.get_tracks(query)

        if not results or not results["tracks"]:
            return await ctx.send(embed=discord.Embed(description="**<:error:897382665781669908> Sorry, No songs found please try again later.**", color=discord.Color.red()))

        em = discord.Embed(colour=discord.Color.green())

        if results["loadType"] == "PLAYLIST_LOADED":
            tracks = results["tracks"]

            for track in tracks:
                player.add(requester=ctx.author.id, track=track)

            em.title = "Playlist Enqueued!"
            em.description = f'{results["playlistInfo"]["name"]} - {len(tracks)} tracks'
        else:
            track = results["tracks"][0]
            em.title = "Track Enqueued"
            em.description = f'[{track["info"]["title"]}]({track["info"]["uri"]})'
            em.set_thumbnail(
                url=f"http://i.ytimg.com/vi/{track['info']['identifier']}/hqdefault.jpg"
            )

            em.add_field(name="Channel", value=track["info"]["author"])
            if track["info"]["isStream"]:
                duration = "Live"
            else:
                duration = lavalink.format_time(track["info"]["length"]).lstrip("00:")
            em.add_field(name="Duration", value=duration)

            track = lavalink.models.AudioTrack(track, ctx.author.id, recommended=True)
            player.add(requester=ctx.author.id, track=track)

        msg = await ctx.send(embed=em)

        if not player.is_playing:
            await player.play()
            await player.reset_equalizer()
            await msg.delete(delay=1)
            await self.now(ctx)

    @commands.command(aliases=["dc", "stop"])
    async def disconnect(self, ctx):
        """Disconnect the player from the voice channel and clear its queue"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_connected:
            return await ctx.send("Not connected.")

        if not ctx.author.voice or (
            player.is_connected
            and ctx.author.voice.channel.id != int(player.channel_id)
        ):
            return await ctx.send(embed=discord.Embed(description="**<:error:897382665781669908> You are not in my voice channel!**", color=discord.Color.red()))

        player.queue.clear()
        await player.stop()
        await ctx.voice_client.disconnect(force=True)
        await ctx.send(embed=discord.Embed(description="**<:tick:897382645321850920> Disconnected.**", color=discord.Color.green()))

    @commands.command(name="seek")
    async def seek(self, ctx, seconds=None):
        """Seek the song to a specific number of seconds"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send(embed=discord.Embed(description="Not playing anything :mute:", color=discord.Color.red()))

        if not seconds:
            return await ctx.send(
                embed=discord.Embed(description="**<:error:897382665781669908> You need to specify the amount of seconds to seek :fast_forward:", color=discord.Color.red())
            )
        try:
            track_time = player.position + int(seconds) * 1000
            await player.seek(track_time)
        except ValueError:
            return await ctx.send(embed=discord.Embed(description="**<:error:897382665781669908> Please Specify a valid amount of seconds :clock3:**", color=discord.Color.red()))

        await ctx.send(embed=discord.Embed(description=f"Moved track to **{lavalink.format_time(track_time)}**", color=discord.Color.green()))

    @commands.command(name="skip", aliases=["next"])
    async def skip(self, ctx):
        """Skip this song and play the next one in the queue"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send(embed=discord.Embed(description="Not playing anything :mute:", color=discord.Color.red()))

        await player.skip()
        await ctx.send(embed= discord.Embed(description=f"**⏭ | Skipped.**", color=discord.Color.green()))
        await asyncio.sleep(0.27)
        await self.now(ctx)

    @commands.command(name="now", aliases=["current", "currentsong", "playing", "np"])
    async def now(self, ctx):
        """View the current song playing"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        song = "Nothing"

        if player.current:
            if player.current.stream:
                dur = "LIVE"
                pos = ""
                count = total = 1
            else:
                count = player.position
                pos = lavalink.format_time(count)
                total = player.current.duration
                dur = lavalink.format_time(total)
                if pos == dur:
                    count = 0
                    pos = "00:00:00"
                dur = dur.lstrip("00:")
                pos = pos[-len(dur) :]
            bar_len = 30
            filled_len = int(bar_len * count // float(total))
            bar = "═" * filled_len + "◈" + "─" * (bar_len - filled_len)
            song = (
                f"[{player.current.title}]({player.current.uri})\n`{pos} {bar} {dur}`"
            )

            em = discord.Embed(color=discord.Color.og_blurple(), description=song)
            em.set_author(
                name="Now Playing 🎵", icon_url="https://i.ibb.co/DGsmTvh/star.gif"
            )
            em.set_thumbnail(
                url=f"http://i.ytimg.com/vi/{player.current.identifier}/hqdefault.jpg"
            )
            requester = ctx.guild.get_member(player.current.requester)
            em.set_footer(
                text=f"Requested by: {requester}", icon_url=requester.avatar.url
            )

            await ctx.send(embed=em)
        else:
            await ctx.send(embed=discord.Embed(description="**<:error:897382665781669908> Not playing anything :mute:**", color=discord.Color.red()))

    @commands.command(name="save", aliases=["star", "savesong"])
    async def savesong(self, ctx):
        """Save/Star the song!"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player.current:
            if player.current.stream:
                dur = "Live"
            else:
                dur = lavalink.format_time(player.current.duration).lstrip("00:")
            song = f"[{player.current.title}]({player.current.uri})"
            em = discord.Embed(color=discord.Color.og_blurple(), description=song)
            em.set_author(
                name="Now Playing 🎵", icon_url="https://i.ibb.co/DGsmTvh/star.gif"
            )
            em.set_thumbnail(
                url=f"http://i.ytimg.com/vi/{player.current.identifier}/hqdefault.jpg"
            )
            em.add_field(name="Channel", value=player.current.author)
            em.add_field(name="Duration", value=dur)

            user = ctx.author
            await user.send(embed=em)
            await ctx.send(
                embed=discord.Embed(description=f"**<:tick:897382645321850920> The current song has been sent to you {ctx.author.mention} :floppy_disk:**", color=discord.Color.green()))
        else:
            await ctx.send(embed=discord.Embed(description="**<:error:897382665781669908> Not playing anything :mute:**", color=discord.Color.red()))

    @commands.command(name="queue", aliases=["q", "playlist"])
    async def queue(self, ctx, page: int = 1):
        """View the queue of songs of the server"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.queue:
            return await ctx.send("Queue empty! Why not queue something? :cd:")

        items_per_page = 10
        pages = math.ceil(len(player.queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue_list = ""

        for i, track in enumerate(player.queue[start:end], start=start):
            queue_list += f"`{i + 1}.` [**{track.title}**]({track.uri})\n"

        embed = discord.Embed(
            color=discord.Color.green(),
            description=f"**{len(player.queue)} tracks**\n\n{queue_list}",
        )
        embed.set_footer(text=f"Viewing page {page}/{pages}")
        await ctx.send(embed=embed)

    @commands.command(name="pause")
    async def pause(self, ctx):
        """Pause the song"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send(embed=discord.Embed("Not playing anything :mute:", color=discord.Color.red()))

        if player.paused:
            embed = discord.Embed(description="<:error:897382665781669908> The player is already paused", color=discord.Color.red())
            await ctx.send(embed=embed)
        else:
            await player.set_pause(True)
            await ctx.message.add_reaction("⏸")

    @commands.command(name="resume", aliases=['start'])
    async def resume(self, ctx):
        """Resume the song"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send(embed=discord.Embed("Not playing anything :mute:", color=discord.Color.red()))

        if not player.paused:
            embed = discord.Embed(description="<:error:897382665781669908> The player is already playing", color=discord.Color.red())
            await ctx.send(embed=embed)
        else:
            await player.set_pause(False)
            await ctx.message.add_reaction("▶️")

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx, volume: int = None):
        """Set the volume of the player"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not volume:
            return await ctx.send(f"🔈 | {player.volume}%")

        await player.set_volume(volume)
        await ctx.send(embed=discord.Embed(description=f"🔈 | Set to {player.volume}%", color=discord.Color.green()))

    @commands.command(name="shuffle")
    async def shuffle(self, ctx):
        """Shuffle the queue"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send(embed=discord.Embed(description="Not playing anything :mute:", color=discord.Color.red()))

        player.shuffle = not player.shuffle

        await ctx.send(embed=discord.Embed(description="🔀 | Shuffle " + ("enabled" if player.shuffle else "disabled"), color=discord.Color.green()))

    @commands.command(name="repeat", aliases=['replay'])
    async def repeat(self, ctx):
        """Repeat a song | If the song is already on repeat, it cancels repeating"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send("Not playing anything :mute:")

        player.repeat = not player.repeat

        await ctx.send(embed=discord.Embed(description="🔁 | Repeat " + ("enabled" if player.repeat else "disabled"), color=discord.Color.green()))

    @commands.command(name="remove", aliases=["dequeue", "pop"])
    async def remove(self, ctx, index: int):
        """Remove a song from the queue | Use the index of the song\nEg: `{0}remove 1` - This removes the 1st song of the queue | Use `{0}queue` to view the queue for the server""".format(ctx.clean_prefix)
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.queue:
            return await ctx.send("Nothing queued :cd:")

        if index > len(player.queue) or index < 1:
            return await ctx.send("Index has to be >=1 and <=queue size")

        index = index - 1
        removed = player.queue.pop(index)

        await ctx.send(embed=discord.Embed(description="<:tick:897382645321850920> Removed **" + removed.title + "** from the queue.", color=discord.Color.green()))

    @commands.command(name="equalizer", aliases=["eq"])
    async def equalizer(self, ctx, *args):
        """Equalizer!\nUse `{0}equalizer list` for all equalizer options.""".format(ctx.clean_prefix)
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if len(args) == 0:
            await ctx.send(
                embed=discord.Embed(description="Please specify something to set in the equalizer. | Use `{0}equalizer list` for all equalizer options".format(ctx.clean_prefix), color=discord.Color.red())
            )
        elif len(args) == 1:

            presets ={
                        'reset': 'Default',
                        'bassboost': [0.08, 0.12, 0.2, 0.18, 0.15, 0.1, 0.05, 0.0, 0.02, -0.04, -0.06, -0.08, -0.10, -0.12, -0.14], 
                        'jazz': [-0.13, -0.11, -0.1, -0.1, 0.14, 0.2, -0.18, 0.0, 0.24, 0.22, 0.2, 0.0, 0.0, 0.0, 0.0], 
                        'pop': [-0.02, -0.01, 0.08, 0.1, 0.15, 0.1, 0.03, -0.02, -0.035, -0.05, -0.05, -0.05, -0.05, -0.05, -0.05], 
                        'treble': [-0.1, -0.12, -0.12, -0.12, -0.08, -0.04, 0.0, 0.3, 0.34, 0.4, 0.35, 0.3, 0.3, 0.3, 0.3],
                        "superbass":[0.2,0.3,0,0.8,0,0.5,0,0,0,0,0,0]
                        
            }



            preset = args[0].lower()
            if preset in ["reset", "default"]:
                await player.reset_equalizer()
            elif preset in presets:
                gain_list = enumerate(presets[preset])
                await player.set_gains(*gain_list)

            elif preset == "list":
                em = discord.Embed(
                    title=":control_knobs: EQ presets:",
                    color=discord.Color(0xFF6EFF),
                    description="\n".join(presets.keys()),
                )
                return await ctx.send(embed=em)

            else:
                return await ctx.send(
                    embed=discord.Embed(description="**<:error:897382665781669908> Invalid preset specified :control_knobs:\nUse `{0}equalizer list` for all presets**".format(ctx.clean_prefix), color=discord.Color.red()
                ))
        elif len(args) == 2:
            try:
                band = int(args[0])
                gain = float(args[1])
                await player.set_gain(band, gain)
            except ValueError:
                return await ctx.send(
                    "Specify valid `band gain` values :control_knobs:"
                )
        else:
            return await ctx.send(embed=discord.Embed(description="**<:error:897382665781669908> PLease specify what to do with the equalizer :control_knobs: | Use `{0}equalizer list` for more info**".format(ctx.clean_prefix), color=discord.Color.red()))
        eq_frequencies = [f"`{gain}`" for gain in player.equalizer]
        await ctx.send(embed=discord.Embed(description=":level_slider: Current Values:\n" + " ".join(eq_frequencies), color=discord.Color.random()))


def setup(bot):
    bot.add_cog(Music(bot))