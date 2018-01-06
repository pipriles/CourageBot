#!/usr/bin/env python3.6
import discord

class ServerState:

    def __init__(self, server=None, invites=None,
            runaway=None, points=None, role_points=None):
        self.id = server.id if server else None
        self.members = server.member_count if server else None

        self.invites = {} if invites is None else invites
        self.runaway = {} if runaway is None else runaway
        self.points = {} if points is None else points
        self.role_points = {} if role_points is None else role_points

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

        if server.id in self.servers:
            state = self.servers[server.id]
        else:
            state = ServerState(server)
            self.servers[server.id] = state

        return state

    def get_server(self, server: discord.Server) -> ServerState:
        return self.servers.get(server.id, None)

