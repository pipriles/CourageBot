#!/usr/bin/env python3.6
import discord
import asyncio
import re
import os

# For MongoDB
import pymongo as pm

import utils
import state

from bson.binary import Binary
import pickle

import signal
import sys

# Restore old state with pickle
# Check for user has permission to set role points
# Check race condition
# Fix regex

TOKEN = os.environ.get('TOKEN')

def from_uri():
    pattern = r'mongodb\:\/\/(\w+)\:(\w+)\@([^\:]+)\:(\d+)\/(\w+)'
    regex = re.compile(pattern)
    match = regex.match(os.environ.get('DB_URI'))
    return match.groups()

def connect_to_db():
    user, secret, host, port, db_name = from_uri()
    client = pm.MongoClient(host, int(port))
    db = client[db_name]
    db.authenticate(user, secret)
    return db

def recover_rick():
    try:
        db = connect_to_db()
        cl = db['states']
        st = cl.find_one()
        bot = pickle.loads(st['bot'])
        print('Bot state recovered!')
    except:
        bot = None

    return bot

def pickle_rick(state):
    try:
        db = connect_to_db()
        cl = db['states']
        st = pickle.dumps(state)
        cl.update_one({}, {'$set': { 'bot': Binary(st) }}, upsert=True)
        print('Bot state stored!')
    except:
        print('There was a problem with the database!')

# def to_dict(bot_state):
#	st = vars(bot_state)
#	servers = st['servers']
#	servers = { k: pickle.(v) for k, v in servers.items() }

def main():

    client = discord.Client()

    bot = recover_rick()

    if bot is None: 
        bot = state.BotState()

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

        playing = discord.Game(name='To the moon')
        await client.change_presence(game=playing)

    @client.event
    async def on_message(message: discord.Message):

        text: str = message.content
        channel: discord.Channel = message.channel

        if text.startswith('!test'):
            await client.send_message(channel, 'Hello!')
            return

        if text.startswith('!backup'):
            pickle_rick(bot)
            await client.send_message(channel, 'Bot state saved!')
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
            author_role = max(message.author.roles)

            if author_role != server.role_hierarchy[0]:
                print(message.author.name, 'is not an admin')
                await client.send_message(
                        channel, 'You are not an admin')
                return

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

    def dont_kill_me_so_fast(signum, frame):
        print('That hurts!')
        pickle_rick(bot)
        sys.exit(0)

    signal.signal(signal.SIGINT, dont_kill_me_so_fast)
    signal.signal(signal.SIGTERM, dont_kill_me_so_fast)

    try:
        client.run(TOKEN)
    finally:
        pickle_rick(bot)

if __name__ == '__main__':
    main()

