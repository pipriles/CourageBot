#!/usr/bin/env python3.6
import discord
import asyncio
import datetime as dt
import random
import re
import os

# Restore old state with pickle
# Check for user has permission to set role points

TOKEN = os.environ.get('TOKEN', None)

def calc_remaining(created_at, *args, **kwargs):
    delta = dt.timedelta(*args, **kwargs)
    return created_at + delta - dt.datetime.now()

def show_invites(invites, *args, **kwargs):
    for i in invites:
        remaining = calc_remaining(i.created_at, seconds=i.max_age)
        print(' ', i.inviter, i.url)
        print(' ', i.uses, i.max_uses, remaining)
    print(*args, **kwargs)

def show_points(members, *args, **kwargs):
    for key, value in members.items():
        print('-> {}: {}'.format(key, value))
    print(*args, **kwargs)

def show_roles(roles, *args, **kwargs):
    for role in roles:
        print(' ', role.id, role.name)
    print(*args, **kwargs)

def random_game():
    games = [ 'Amnesia', 'Outlast', 'Resident Evil', 
            'Little Nightmares', 'Silent Hill' ]
    return discord.Game(name=random.choice(games))

class ServerState:

    def __init__(self, server: discord.Server):
        self.id = server.id
        self.members = server.member_count

        self.invites = {}
        self.runaway = {}
        self.points = {}
        self.role_points = {}

    def track_invites(self, invites):
        self.invites = { x.id: x for x in invites }
        return self.invites

    # Get member current points from database
    # def member_points(self,):
    def base_points(self, role: discord.Role):
        return self.role_points.get(role.id, -1)

    # Role update, update user points which has this role
    def set_base_points(self, role: discord.Role, points):
        self.role_points[role.id] = points
        return points

    def init_points(self, members):

        for member in members:
            role = max(member.roles)
            base = self.role_points.get(role.id, 0)

            if member.id not in self.points:
                self.points[member.id] = base

    def show_points(self, member: discord.Member):
        current = self.points[member.id]
        print(' - {}: {}'.format(member.name, current))

    def award_member(self, member, points):
        current = self.points.get(member.id, 0) 
        current += points
        self.points[member.id] = current        
        return current

    def calc_points(self, invites):

        result = []
        for invite in invites:
            before = self.invites.get(invite.id, None)
            points = invite.uses
            points -= before.uses if before else 0

            if points > 0:
                result.append((invite, points))

        return result

    def track_runaway(self, member: discord.Member):
        self.runaway[member.id] = member
        return member

    def is_runaway(self, member: discord.Member):
        return self.runaway.get(member.id, None)

    def add_member(self, member: discord.Member) -> int:
        if self.is_runaway(member) is None:
            self.members += 1
            self.points[member.id] = 0
            return True
        return False    

class BotState:
    
    def __init__(self):
        self.servers = {}

    def add_server(self, server: discord.Server):
        state = ServerState(server)
        self.servers[server.id] = state
        return state

    def get_server(self, server: discord.Server) -> ServerState:
        return self.servers.get(server.id, None)

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

            show_roles(server.role_hierarchy)
            show_invites(invites)

            state.track_invites(invites)
            state.init_points(server.members)
            
        await client.change_presence(game=random_game())

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
        show_invites(invites)

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

