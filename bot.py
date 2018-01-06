#!/usr/bin/env python3.6
import discord
import asyncio
import re
import os

# For MongoDB
import pymongo as pm

import utils

# Restore old state with pickle
# Check for user has permission to set role points

TOKEN = os.environ.get('TOKEN', None)

def main():

    client = discord.Client()
    bot = BotState()

    @client.event
    async def on_ready():

        print('Logged in as', client.user)
        print('--------------------')

        for server in client.servers:
            state = bot.add_server(server)
            invites = await client.invites_from(server)

            utils.show_roles(server.role_hierarchy)
            utils.show_invites(invites)

            state.track_invites(invites)
            state.init_points(server.members)
            
        await client.change_presence(game=utils.random_game())

    @client.event
    async def on_message(message: discord.Message):

        text: str = message.content
        channel: discord.Channel = message.channel

        if text.startswith('!test'):
            await client.send_message(channel, 'Hello!')
            return

        # Commands for server
        if message.server is None:
            return

        server = message.server
        state = bot.get_server(server)

        if text.startswith('!roles'):
            # Return list of roles with position
            rows = []
            for i, role in enumerate(server.role_hierarchy):
                row = '[{}] **{}** ({} points)'
                row = row.format(i, role.name, state.base_points(role))
                rows.append(row)
            await client.send_message(channel, '\n'.join(rows))
            return

        match = re.match(r'!role (\d+) (\d+)', text)
        if match:
            position, points = map(int, match.groups())

            role = server.role_hierarchy[position]
            state.set_base_points(role, points)

            reply = 'Role **{}** has been set to **{}** points'
            reply = reply.format(role.name, points)
            await client.send_message(channel, reply)
            return

    @client.event
    async def on_member_remove(member: discord.Member):

        print(member.name, 'has left but i will not forget it')
        server = member.server

        invites = await client.invites_from(server)

        state = bot.get_server(member.server)
        state.track_runaway(member)

        for invite in invites:
            if invite.inviter == member:
                await client.delete_invite(invite)
                print(' Removed', invite.url)
        print()

    @client.event
    async def on_member_join(member: discord.Member):

        server = member.server
        print('{} has joined to {}!'.format(member.name, server))

        invites = await client.invites_from(server)

        state = bot.get_server(server)
        result = state.calc_points(invites)
        new_member = state.add_member(member)
        joined = 0

        for invite, points in result:
            print('-> ', points, invite.url, invite.inviter)
            joined += points
        print()

        if joined > 1 or (joined == 1 and new_member):
            # Award everybody when the bot doesn't 
            # know what to do or if it a new member
            for invite, points in result:
                print('New member!')
                inviter = server.get_member(invite.inviter.id)
                await award_inviter_roles(inviter, points)
        else:
            print('Already counted!')

        # Track new invites
        state.track_invites(invites)
        utils.show_invites(invites)

        for invite in invites:
            state.show_points(invite.inviter)
        print()

        if member.id == '169907053022806016':
            roles = sorted(server.me.roles, reverse=True)
            await client.add_roles(member, roles[1]) 
            await client.send_message(
                    server.default_channel, 'Welcome my master!' )

    @client.event
    async def on_server_update(before, after):
        print('Something happened!')

    async def award_inviter_roles(inviter, points):

        server = inviter.server
        state = bot.get_server(server)
        current = state.award_member(inviter, points)

        for role in server.role_hierarchy:
            base = state.base_points(role)
            if base != -1 and current >= base:
                print(' {} awarded!'.format(role.name))
                try:
                    await client.add_roles(inviter, role)
                except discord.errors.Forbidden:
                    pass
        print()

    client.run(TOKEN)

if __name__ == '__main__':
    main()

