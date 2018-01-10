#!/usr/bin/env python3.6
import discord
import datetime as dt
import random

def calc_remaining(created_at, *args, **kwargs):
    delta = dt.timedelta(*args, **kwargs)
    return created_at + delta - dt.datetime.now()

def show_invites(invites, *args, **kwargs):
    for i in invites:
        remaining = calc_remaining(i.created_at, seconds=i.max_age)
        print(' ', i.inviter, i.url)
        print(' ', i.uses, i.max_uses, remaining)
    print(*args, **kwargs)

def show_roles(roles, *args, **kwargs):
    for role in roles:
        print(' ', role.id, role.name)
    print(*args, **kwargs)

def random_game():
    games = [ 'Amnesia', 'Outlast', 'Resident Evil', 
            'Little Nightmares', 'Silent Hill' ]
    return discord.Game(name=random.choice(games))

def find_by_id(items, e):
    return next((x for x in items if getattr(x, 'id', None) == e), None)

