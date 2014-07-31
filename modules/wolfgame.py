# Copyright (c) 2011, Jimmy Cao
# All rights reserved.

# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

# Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from oyoyo.parse import parse_nick
import settings.wolfgame as var
import botconfig
from tools.wolfgamelogger import WolfgameLogger
from tools import decorators
from datetime import datetime, timedelta
from operator import itemgetter
from collections import defaultdict
import threading
import random
import copy
import time
import re
import logging
import sys
import os
import imp
import math
import fnmatch
import random
import subprocess
from imp import reload

BOLD = "\u0002"
COMMANDS = {}
PM_COMMANDS = {}
HOOKS = {}

cmd = decorators.generate(COMMANDS)
pmcmd = decorators.generate(PM_COMMANDS)
hook = decorators.generate(HOOKS, raw_nick=True, permissions=False)

# Game Logic Begins:

var.LAST_PING = None  # time of last ping
var.LAST_STATS = None
var.LAST_VOTES = None
var.LAST_ADMINS = None
var.LAST_GSTATS = None
var.LAST_PSTATS = None
var.LAST_TIME = None

var.IS_ADMIN = {}
var.IS_OWNER = {}

var.USERS = {}

var.PINGING = False
var.ADMIN_PINGING = False
var.ROLES = {"person" : []}
var.ORIGINAL_ROLES = {}
var.SPECIAL_ROLES = {}
var.PLAYERS = {}
var.DCED_PLAYERS = {}
var.ADMIN_TO_PING = None
var.AFTER_FLASTGAME = None
var.PHASE = "none"  # "join", "day", or "night"
var.TIMERS = {}
var.DEAD = []
var.NO_LYNCH = []
var.TO_PING = []
var.CONNECT_OK = False
var.DCED_GRACE = []

var.ORIGINAL_SETTINGS = {}

var.LAST_SAID_TIME = {}

var.GAME_START_TIME = datetime.now()  # for idle checker only
var.CAN_START_TIME = 0
var.GRAVEYARD_LOCK = threading.RLock()
var.GAME_ID = 0
var.STARTED_DAY_PLAYERS = 0

var.DISCONNECTED = {}  # players who got disconnected

var.illegal_joins = defaultdict(int)

var.LOGGER = WolfgameLogger(var.LOG_FILENAME, var.BARE_LOG_FILENAME)
var.GOT_IT = False
var.OPS_PING = 0
var.OPS_TO_PING = []
var.PINGING_OPS = []
var.PING_CHAN = None
var.WHO_HOST = {}
var.IDLE_HOST = {}
var.AUTO_LOG_TOGGLED = False
var.NO_PING = False
var.AUTO_LOG_TOGGLED = False


if botconfig.DEBUG_MODE:
    var.NIGHT_LIMIT_WARN = 0
    var.NIGHT_TIME_WARN = 0
    var.NIGHT_TIME_LIMIT = 0  # 90
    var.DAY_TIME_LIMIT_WARN = 0
    var.DAY_TIME_LIMIT_CHANGE = 0
    var.KILL_IDLE_TIME = 0 #300
    var.WARN_IDLE_TIME = 0 #180
    var.JOIN_TIME_LIMIT = 0


def connect_callback(cli):
    to_be_devoiced = []
    cmodes = []
    if var.CONNECT_OK == True:
        return
    if botconfig.ADMIN_CHAN == "":
        var.LOG_CHAN = False

    @hook("quietlist", hookid=294)
    def on_quietlist(cli, server, botnick, channel, q, quieted, by, something):
        if re.match(".+\!\*@\*", quieted) and by == botnick:  # only unquiet people quieted by bot
            cmodes.append(("-q", quieted))

    @hook("whospcrpl", hookid=294)
    def on_whoreply(cli, server, nick, ident, cloak, user, status, acc):
        if user in var.USERS: return  # Don't add someone who is already there
        if user == botconfig.NICK:
            cli.nickname = user
            cli.ident = ident
            cli.hostmask = cloak
            var.FULL_ADDRESS = "{0}!{1}@{2}".format(user, ident, cloak)
        if acc == "0":
            acc = "*"
        if "+" in status and user not in to_be_devoiced:
            to_be_devoiced.append(user)
        var.USERS[user] = dict(cloak=cloak,account=acc)
        var.IS_OWNER[user] = False
        var.IS_ADMIN[user] = False
        if cloak in botconfig.ADMINS or cloak in botconfig.OWNERS or acc in botconfig.ADMINS_ACCOUNTS or acc in botconfig.OWNERS_ACCOUNTS:
            var.IS_ADMIN[user] = True
        if cloak in botconfig.OWNERS or acc in botconfig.OWNERS_ACCOUNTS:
            var.IS_OWNER[user] = True
       
    @hook("endofwho", hookid=294)
    def afterwho(*args):
        if var.CONNECT_OK == False:
            for nick in to_be_devoiced:
                cmodes.append(("-v", nick))
                var.CONNECT_OK = True
            # devoice all on connect

        @hook("mode", hookid=294)
        def on_give_me_ops(cli, modeapplier, chan, modeaction, target="", *other):
            if modeaction == "+o" and target == botconfig.NICK and var.PHASE == "none" and chan == botconfig.CHANNEL:
        
                @hook("quietlistend", 294)
                def on_quietlist_end(cli, svr, nick, chan, *etc):
                    if chan == botconfig.CHANNEL:
                        decorators.unhook(HOOKS, 294)
                        mass_mode(cli, cmodes)
                cli.mode(botconfig.CHANNEL, "q")  # unquiet all
                cli.mode(botconfig.CHANNEL, "-m")  # remove -m mode from channel
            elif modeaction == "+o" and target == botconfig.NICK and var.PHASE != "none":
                decorators.unhook(HOOKS, 294)  # forget about it


    cli.who(botconfig.CHANNEL, "%nuhaf")



def mass_mode(cli, md):
    """ Example: mass_mode(cli, (('+v', 'asdf'), ('-v','wobosd'))) """
    lmd = len(md)  # store how many mode changes to do
    for start_i in range(0, lmd, 4):  # 4 mode-changes at a time
        if start_i + 4 > lmd:  # If this is a remainder (mode-changes < 4)
            z = list(zip(*md[start_i:]))  # zip this remainder
            ei = lmd % 4  # len(z)
        else:
            z = list(zip(*md[start_i:start_i+4])) # zip four
            ei = 4 # len(z)
        # Now z equal something like [('+v', '-v'), ('asdf', 'wobosd')]
        arg1 = "".join(z[0])
        arg2 = " ".join(z[1])  # + " " + " ".join([x+"!*@*" for x in z[1]])
        cli.mode(botconfig.CHANNEL, arg1, arg2)

def reset_modes_timers(cli):
    # Reset game timers
    for x, timr in var.TIMERS.items():
        timr.cancel()
    var.TIMERS = {}

    # Reset modes
    cli.mode(botconfig.CHANNEL, "-m")
    cmodes = []
    for plr in var.list_players():
        cmodes.append(("-v", plr))
    for deadguy in var.DEAD:
        cmodes.append(("-q", deadguy+"!*@*"))
    mass_mode(cli, cmodes)
        
def pm(cli, target, message):  # message either privmsg or notice, depending on user settings
    if target in var.USERS and var.USERS[target]["cloak"] in var.SIMPLE_NOTIFY: # still need to make it work with the damn ident
        cli.notice(target, message)
    else:
        cli.msg(target, message)

def reset_settings():
    for attr in list(var.ORIGINAL_SETTINGS.keys()):
        setattr(var, attr, var.ORIGINAL_SETTINGS[attr])
    dict.clear(var.ORIGINAL_SETTINGS)


def reset(cli):
    chan = botconfig.CHANNEL
    var.PHASE = "none"

    for x, timr in var.TIMERS.items():
        timr.cancel()
    var.TIMERS = {}

    var.GAME_ID = 0

    cli.mode(chan, "-m")
    cmodes = []
    for plr in var.list_players():
        cmodes.append(("-v", plr))
    for deadguy in var.DEAD:
       cmodes.append(("-q", deadguy+"!*@*"))
    mass_mode(cli, cmodes)
    var.DEAD = []
    var.NO_LYNCH = []

    var.ROLES = {"person" : []}

    reset_settings()

    dict.clear(var.LAST_SAID_TIME)
    dict.clear(var.PLAYERS)
    dict.clear(var.DCED_PLAYERS)
    dict.clear(var.DISCONNECTED)

def make_stasis(nick, penalty):
    try:
        cloak = var.USERS[nick]['cloak']
        if cloak is not None:
            var.illegal_joins[cloak] += penalty
    except KeyError:
        pass

def chan_log(cli, nick, action):
    cli.msg(botconfig.ADMIN_CHAN, "processCommand (b'{0}')action(\"{1}\")".format(nick, action))

@pmcmd("fdie", "fbye", raw_nick=True)
@cmd("fdie", "fbye", raw_nick=True)
def forced_exit(cli, rnick, *rest):  # Admin Only
    """Forces the bot to close"""
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        if var.PHASE in ("day", "night"):
            stop_game(cli)
        else:
            reset(cli)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "forced_exit")
        cli.quit("Forced quit from "+nick)

@cmd("logging", "log", "toggle", raw_nick=True)
def toggle_logging(cli, rnick, chan, rest):
    """Toggles the logging option"""
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        if var.LOG_CHAN == True:
            var.LOG_CHAN = False
            chan_log(cli, rnick, "disable_logging")
            cli.msg(chan, "Logging has now been disabled by \u0002{0}\u0002".format(nick))
            cli.msg(botconfig.ADMIN_CHAN, "Logging is now \u0002off\u0002")
            if var.AUTO_LOG_TOGGLE == True:
                var.AUTO_LOG_TOGGLE == False
                chan_log(cli, rnick, "disable_auto_toggle")
                cli.msg(chan, "Automatic logging toggle has been disabled.")
                cli.msg(botconfig.ADMIN_CHAN, "Automatic logging toggle is now \u0002off\u0002.")
                var.AUTO_LOG_TOGGLED = True
            return
        if var.LOG_CHAN == False:
            var.LOG_CHAN = True
            chan_log(cli, rnick, "enable_logging")
            cli.msg(chan, "Logging has now been enabled by \u0002{0}\u0002".format(nick))
            cli.msg(botconfig.ADMIN_CHAN, "Logging is now \u0002on\u0002")
            if var.AUTO_LOG_TOGGLE == False and var.AUTO_LOG_TOGGLED == True:
                var.AUTO_LOG_TOGGLE == True
                chan_log(cli, rnick, "enable_auto_toggle")
                cli.msg(chan, "Automatic logging toggle has been enabled.")
                cli.msg(botconfig.ADMIN_CHAN, "Automatic logging toggle is now \u0002on\u0002.")
            return
    else:
        cli.notice(nick, "You are not an admin.")

@pmcmd("frestart", raw_nick=True)
@cmd("frestart", raw_nick=True)
def restart_program(cli, rnick, *rest):
    """Restarts the bot."""
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        try:
            if var.PHASE in ("day", "night"):
                stop_game(cli)
            else:
                reset(cli)
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "restart")
            cli.quit("Forced restart from "+nick)
            raise SystemExit
        finally:
            print("RESTARTING")
            python = sys.executable
            if rest[-1].strip().lower() == "debugmode":
                os.execl(python, python, sys.argv[0], "--debug")
            elif rest[-1].strip().lower() == "normalmode":
                os.execl(python, python, sys.argv[0])
            else:
                os.execl(python, python, *sys.argv)


@pmcmd("ping")
def pm_ping(cli, nick, rest):
    pm(cli, nick, 'Pong!')

@cmd("ping", "p", raw_nick=True)
def pinger(cli, rnick, chan, rest):
    """Pings the channel to get people's attention.  Rate-Limited."""
    nick, ident, mode, host = parse_nick(rnick)
    if (var.LAST_PING and
        var.LAST_PING + timedelta(seconds=var.PING_WAIT) > datetime.now()):
        cli.notice(nick, ("This command is rate-limited. " +
                          "Please wait a while before using it again."))
        return
        
    if var.PHASE in ('night','day'):
        cli.notice(nick, "Pong!")
        return
    if chan != botconfig.CHANNEL: return

    var.LAST_PING = datetime.now()
    if var.PINGING:
        return
    var.PINGING = True
    var.TO_PING = []
    if botconfig.PING_NOTICE == True:
        cli.notice(chan, "A game of Werewolf is starting in "+
                   "{1} : type {0}join to join!".format(botconfig.CMD_CHAR, chan))
        var.PINGING = False
        return



    @hook("whoreply", hookid=800)
    def on_whoreply(cli, server, dunno, chan, dunno1,
                    cloak, dunno3, user, status, dunno4):
        if not var.PINGING: return
        if user in (botconfig.NICK, nick): return  # Don't ping self.

        if (all((not botconfig.REVERSE_PING,
                 'G' not in status,  # not /away
                 '+' not in status,  # not already joined (voiced)
                 cloak not in var.AWAY)) or
            all((botconfig.REVERSE_PING, '+' not in status,
                 cloak in var.PING_IN))):

            var.TO_PING.append(user)


    @hook("endofwho", hookid=800)
    def do_ping(*args):
        if not var.PINGING: return

        var.TO_PING.sort(key=lambda x: x.lower())
        
        cli.msg(botconfig.CHANNEL, "PING! "+" ".join(var.TO_PING))
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "ping")
        var.PINGING = False
 
        minimum = datetime.now() + timedelta(seconds=var.PING_MIN_WAIT)
        if not var.CAN_START_TIME or var.CAN_START_TIME < minimum:
           var.CAN_START_TIME = minimum

        decorators.unhook(HOOKS, 800)

    cli.who(botconfig.CHANNEL)

@cmd("in", raw_nick=True)
@pmcmd("in", raw_nick=True)
def get_in(cli, rnick, *rest):
    """Get yourself in the ping list"""
    nick, mode, ident, cloak = parse_nick(rnick)
    if botconfig.REVERSE_PING == False:
        cli.notice(nick, "Invalid syntax. Use {0}away and {0}back instead".format(botconfig.CMD_CHAR))
        return
    if cloak in var.PING_IN and cloak not in botconfig.COMMON_HOSTS:
        cli.notice(nick, "You are already on the list")
        return
    if ident+"@"+cloak in var.PING_IN and cloak in botconfig.COMMON_HOSTS:
        cli.notice(nick, "You are already on the list")
        return
    if cloak not in botconfig.COMMON_HOSTS:
        var.PING_IN.append(cloak)
    if cloak in botconfig.COMMON_HOSTS:
        var.PING_IN.append(ident+"@"+cloak)
    if var.LOG_CHAN == True:
        chan_log(cli, rnick, "in")
    cli.notice(nick, "You are now on the list.")
    
@cmd("out", raw_nick=True)
@pmcmd("out", raw_nick=True)
def get_out(cli, rnick, *rest):
    """Removes yourself from the ping list"""
    nick, mode, ident, cloak = parse_nick(rnick)
    if botconfig.REVERSE_PING == False:
        cli.notice(nick, "Invalid syntax. Use {0}away and {0}back instead".format(botconfig.CMD_CHAR))
        return
    if cloak in var.PING_IN and cloak not in botconfig.COMMON_HOSTS:
        var.PING_IN.remove(cloak)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "out")
        cli.notice(nick, "You are no longer in the list.")
        return
    if ident+"@"+cloak in var.PING_IN and cloak in botconfig.COMMON_HOSTS:
        var.PING_IN.remove(ident+"@"+cloak)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "out")
        cli.notice(nick, "You are no longer in the list.")
        return
    cli.notice(nick, "You are not in the list.")


@cmd("away", raw_nick=True)
@pmcmd("away", raw_nick=True)
def away(cli, rnick, *rest):
    """Use this to activate your away status (so you aren't pinged)."""
    nick, mode, ident, cloak = parse_nick(rnick)
    if botconfig.REVERSE_PING == True:
        cli.notice(nick, "Invalid syntax. Use {0}in and {0}out instead".format(botconfig.CMD_CHAR))
        return
    if cloak in var.AWAY and cloak not in botconfig.COMMON_HOSTS:
        var.AWAY.remove(cloak)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "away_back")
        cli.notice(nick, "You are no longer marked as away.")
        return
    if ident+"@"+cloak in var.AWAY and cloak in botconfig.COMMON_HOSTS:
        var.AWAY.remove(ident+"@"+cloak)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "away_back")
        cli.notice(nick, "You are no longer marked as away.")
        return
    if cloak not in var.AWAY and cloak not in botconfig.COMMON_HOSTS:
        var.AWAY.append(cloak)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "away")
        cli.notice(nick, "You are now marked as away.")
        return
    if ident+"@"+cloak not in var.AWAY and cloak in botconfig.COMMON_HOSTS:
        var.AWAY.append(ident+"@"+cloak)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "away")
        cli.notice(nick, "You are now marked as away.")
    
@cmd("back", raw_nick=True)
@pmcmd("back", raw_nick=True)
def back_from_away(cli, rnick, *rest):
    """Unmarks away status"""
    nick, mode, ident, cloak = parse_nick(rnick)
    if botconfig.REVERSE_PING == True:
        cli.notice(nick, "Invalid syntax. Use {0}in and {0}out instead".format(botconfig.CMD_CHAR))
        return
    if cloak not in var.AWAY and cloak not in botconfig.COMMON_HOSTS:
        cli.notice(nick, "You are not marked as away.")
        return
    if ident+"@"+cloak not in var.AWAY and cloak in botconfig.COMMON_HOSTS:
        cli.notice(nick, "You are not marked as away.")
        return
    if cloak in var.AWAY and cloak not in botconfig.COMMON_HOSTS:
        var.AWAY.remove(cloak)
    if ident+"@"+cloak in var.AWAY and cloak in botconfig.COMMON_HOSTS:
        var.AWAY.remove(ident+"@"+cloak)
    if var.LOG_CHAN == True:
        chan_log(cli, rnick, "back")
    cli.notice(nick, "You are no longer marked as away.")
    
@cmd("simple", raw_nick = True)
@pmcmd("simple", raw_nick = True)
def mark_simple_notify(cli, rnick, *rest):
    """If you don't want to bot to send you role instructions"""
    
    nick, mode, ident, cloak = parse_nick(rnick)
    
    if cloak in var.SIMPLE_NOTIFY and cloak not in botconfig.COMMON_HOSTS:
        var.SIMPLE_NOTIFY.remove(cloak)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "simple_remove")
        cli.notice(nick, "You will no longer receive simple role instructions.")
        return
    if ident+"@"+cloak in var.SIMPLE_NOTIFY and cloak in botconfig.COMMON_HOSTS:
        var.SIMPLE_NOTIFY.remove(ident+"@"+cloak)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "simple_remove")
        cli.notice(nick, "You will no longer receive simple role instructions.")
        return
    if cloak not in var.SIMPLE_NOTIFY and cloak not in botconfig.COMMON_HOSTS:
        var.SIMPLE_NOTIFY.append(cloak)
    if ident+"@"+cloak not in var.SIMPLE_NOTIFY and cloak in botconfig.COMMON_HOSTS:
        var.SIMPLE_NOTIFY.append(ident+"@"+cloak)
    if var.LOG_CHAN == True:
        chan_log(cli, rnick, "simple")
    cli.notice(nick, "You will now receive simple role instructions.")

@cmd("fping", raw_nick=True)
def fpinger(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        var.LAST_PING = None
        pinger(cli, rnick, chan, rest)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "force_ping")

@hook("mode") # unsets any ban set by ChanServ (AKICK)
def unset_bans_akick(cli, rnick, chan, mode, *action):
    nick, mode, user, host = parse_nick(rnick)
    action = list(action)
    if mode == "+b" and "services." in host:
        if nick == "ChanServ" and len(action) == 1:
            ban = action.pop(0)
            cli.who(chan, "%fn")
            @hook("whospcrpl", hookid=126)
            def am_i_op_now(cli, server, you, nick, status):
                if you == nick and '@' in status:
                    cli.mode(chan, "-b", ban)
                    cli.msg(chan, "\u0001ACTION resets the trap...\u0001")
                @hook("endofwho", hookid=126)
                def unhook_after_ban(cli, server, you, chan, output):
                    decorators.unhook(HOOKS, 126)

@cmd("join", "j", raw_nick=True)
def join(cli, rnick, chan, rest):
    """Either starts a new game of Werewolf or joins an existing game that has not started yet."""
    nick, mode, user, cloak = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
        pl = var.list_players()
        try:
            cloak = var.USERS[nick]['cloak']
            if cloak is not None and var.illegal_joins[cloak] > 0:
                cli.notice(nick, "Sorry, but you are in stasis for {0} games.".format(var.illegal_joins[cloak]))
                return
        except KeyError:
            cloak = None
    
    
        if var.PHASE == "none":
            if var.LOG_CHAN == True and var.GOT_IT != True:
                chan_log(cli, rnick, "join_start")
            var.GOT_IT = False
            cli.mode(chan, "+v", nick)
            var.ROLES["person"].append(nick)
            var.PHASE = "join"
            var.WAITED = 0
            var.GAME_ID = time.time()
            var.CAN_START_TIME = datetime.now() + timedelta(seconds=var.MINIMUM_WAIT)
            cli.msg(chan, ('\u0002{0}\u0002 has started a game of Werewolf. '+
                           'Type "{1}join" to join. Type "{1}start" to start the game. '+
                           'Type "{1}wait" to increase join wait time.').format(nick, botconfig.CMD_CHAR))
            var.GOT_IT = False # reset that variable (used in different places)
            # Set join timer
        if var.JOIN_TIME_LIMIT:
            t = threading.Timer(var.JOIN_TIME_LIMIT, kill_join, [cli, chan])
            var.TIMERS['join'] = t
            t.daemon = True
            t.start()
        elif nick in pl:
            cli.notice(nick, "You're already playing!")
        elif len(pl) >= var.MAX_PLAYERS:
            cli.notice(nick, "Too many players!  Try again next time.")
        elif var.PHASE != "join":
            cli.notice(nick, "Sorry but the game is already running.  Try again next time.")
        else:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "join")
            cli.mode(chan, "+v", nick)
            var.ROLES["person"].append(nick)
            cli.msg(chan, '\u0002{0}\u0002 has joined the game. New player count: \u0002{1}\u0002'.format(nick, len(pl)+1))
        
            var.LAST_STATS = None # reset
            
def kill_join(cli, chan):
    pl = var.list_players()
    pl.sort(key=lambda x: x.lower())
    msg = 'PING! {0}'.format(", ".join(pl))
    reset_modes_timers(cli)
    reset(cli)
    cli.msg(chan, msg)
    cli.msg(chan, 'The current game took too long to start and ' +
                  'has been canceled. If you are still active, ' +
                  'please join again to start a new game.')
    if var.LOG_CHAN == True:
        chan_log(cli, var.FULL_ADDRESS, "cancel_game")
    var.LOGGER.logMessage('Game canceled.')


@cmd("fjoin", raw_nick=True)
def fjoin(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        noticed = False
        if chan == botconfig.CHANNEL:
            if not rest.strip():
                if var.LOG_CHAN == True:
                    chan_log(cli, rnick, "forced_join")
                    var.GOT_IT = True
                join(cli, nick, chan, "")

            for a in re.split(" +",rest):
                a = a.strip()
                if not a:
                    continue
                ul = list(var.USERS.keys())
                ull = [u.lower() for u in ul]
                if a.lower() not in ull:
                    if not is_fake_nick(a) or not botconfig.DEBUG_MODE:
                        if not noticed:  # important
                            cli.msg(chan, nick+(": You may only fjoin "+
                                            "people who are in this channel."))
                            noticed = True
                        continue
                if not is_fake_nick(a):
                    a = ul[ull.index(a.lower())]
                if a != botconfig.NICK:
                    join(cli, a.strip(), chan, "")
                else:
                    cli.notice(nick, "No, that won't be allowed.")

@cmd("fleave","fquit","fdel", raw_nick=True)
def fleave(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        if chan == botconfig.CHANNEL:
            if var.PHASE == "none":
                cli.notice(nick, "No game is running.")
            for a in re.split(" +",rest):
                a = a.strip()
                if not a:
                    continue
                pl = var.list_players()
                _pl = len(pl) - 1
                pll = [x.lower() for x in pl]
                if a.lower() in pll:
                    a = pl[pll.index(a.lower())]
                else:
                    cli.msg(chan, nick+": That person is not playing.")
                    return
                if var.LOG_CHAN == True:
                    chan_log(cli, rnick, "forced_leave")
                    var.GOT_IT = True
                cli.msg(chan, ("\u0002{0}\u0002 is forcing"+
                               " \u0002{1}\u0002 to leave.").format(nick, a))
                cli.msg(chan, "Appears (s)he was a \02{0}\02.".format(var.get_role(a)))
                cli.msg(chan, "New player count: {0}".format(_pl))
                if var.PHASE in ("day", "night"):
                    var.LOGGER.logMessage("{0} is forcing {1} to leave.".format(nick, a))
                    var.LOGGER.logMessage("Appears (s)he was a {0}.".format(var.get_role(a)))
                del_player(cli, a)


@cmd("fstart", raw_nick=True)
def fstart(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        if chan == botconfig.CHANNEL:
            var.CAN_START_TIME = datetime.now()
            cli.msg(botconfig.CHANNEL, "\u0002{0}\u0002 has forced the game to start.".format(nick))
            start(cli, chan, chan, rest)
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "forced_start")
                var.GOT_IT = True
    

@pmcmd("", raw_nick=True)
def version_reply(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    if rest == "\01VERSION\01":
        cli.notice(nick, "\u0001VERSION Wolfbot by jcao219 modified by Vgr using python 3.2\u0001")
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "version")

'''@pmcmd("", raw_nick=True)
def bot_uptime(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    if rest == "\01UPTIME\01":
        cli.notice(nick, "\01UPTIME Up for \02{0}\02 hours, \02{1}\02 minutes and \02{2}\02 seconds, or \02{3}\02 seconds.\01".format'''

@cmd("update", "upd", raw_nick=True)
@pmcmd("update", "upd", raw_nick=True)
def updating_bot(cli, rnick, *rest):
    """Restart for an update."""
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        rest = list(rest)
        try:
            if var.PHASE in ("day", "night"):
                stop_game(cli)
            else:
                reset(cli)
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "update")
            cli.quit("Updating database . . .")
            raise SystemExit
        finally:
            print("RESTARTING")
            python = sys.executable
            os.execl(python, python, sys.argv[0])

    
    
@hook("kick")
def on_kicked(cli, nick, chan, victim, reason):
    if chan == botconfig.CHANNEL:
        if victim == botconfig.NICK:
            cli.join(botconfig.CHANNEL)
            if var.AUTO_OP_FLAG == False:
                cli.msg("ChanServ", "op "+botconfig.CHANNEL)
        elif victim in var.IS_ADMIN and var.IS_ADMIN[victim] == True:
            var.IS_ADMIN[victim] = False # make sure no abuse can be made (it will be set back on join anyway)
            var.IS_OWNER[victim] = False # no need to check if True or False, as all owners are admins


@hook("account")
def on_account(cli, nick, acc):
    nick = parse_nick(nick)[0]    
    var.IS_ADMIN[nick] = False
    var.IS_OWNER[nick] = False # default all of them to False, then set to True if they're admins (later)
    if nick in var.USERS.keys():
        var.USERS[nick]["account"] = acc
    if acc in botconfig.ADMINS_ACCOUNTS or acc in botconfig.OWNERS_ACCOUNTS:
        var.IS_ADMIN[nick] = True
    if acc in botconfig.OWNERS_ACCOUNTS:
        var.IS_OWNER[nick] = True

@cmd("stats", "s", "players", raw_nick=True)
def stats(cli, rnick, chan, rest):
    """Display the player statistics"""
    nick, mode, user, host = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
        if var.PHASE == "none":
            cli.notice(nick, "No game is currently running.")
            return
        
        pl = var.list_players()
    
        if nick in pl or var.PHASE == "join":
            # only do this rate-limiting stuff if the person is in game
            if (var.LAST_STATS and
                var.LAST_STATS + timedelta(seconds=var.STATS_RATE_LIMIT) > datetime.now()):
                cli.msg(chan, nick+": This command is rate-limited.")
                return
            
            var.LAST_STATS = datetime.now()
    
        pl.sort(key=lambda x: x.lower())
        if len(pl) > 1:
            msg = '{0}: \u0002{1}\u0002 players: {2}'.format(nick,
                len(pl), ", ".join(pl))
        else:
            msg = '{0}: \u00021\u0002 player: {1}'.format(nick, pl[0])
    
        if nick in pl or var.PHASE == "join":
            cli.msg(chan, msg)
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "stats")
            var.LOGGER.logMessage(msg.replace("\02", ""))
        else:
            cli.notice(nick, msg)
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "stats_notice")
        
        if var.PHASE == "join":
            return

        message = []
        f = False  # set to true after the is/are verb is decided
        l1 = [k for k in var.ROLES.keys()
            if var.ROLES[k]]
        l2 = [k for k in var.ORIGINAL_ROLES.keys()
            if var.ORIGINAL_ROLES[k]]
        rs = list(set(l1+l2))
        
        # Due to popular demand, picky ordering
        if "wolf" in rs:
            rs.remove("wolf")
            rs.insert(0, "wolf")
        if "seer" in rs:
            rs.remove("seer")
            rs.insert(1, "seer")
        if "villager" in rs:
            rs.remove("villager")
            rs.append("villager")
        
        
        firstcount = len(var.ROLES[rs[0]])
        if firstcount > 1 or not firstcount:
            vb = "are"
        else:
            vb = "is"
        for role in rs:
            count = len(var.ROLES[role])
            if role == "traitor" and var.HIDDEN_TRAITOR:
                continue
            elif role == "villager" and var.HIDDEN_TRAITOR:
                count += len(var.ROLES["traitor"])
                
            if count > 1 or count == 0:
                message.append("\u0002{0}\u0002 {1}".format(count if count else "\u0002no\u0002", var.plural(role)))
            else:
                message.append("\u0002{0}\u0002 {1}".format(count, role))
        stats_mssg =  "{0}: It is currently {4}. There {3} {1}, and {2}.".format(nick,
                                                            ", ".join(message[0:-1]),
                                                            message[-1],
                                                            vb,
                                                            var.PHASE)
        if nick in pl or var.PHASE == "join":
            cli.msg(chan, stats_mssg)
            var.LOGGER.logMessage(stats_mssg.replace("\02", ""))
        else:
            cli.notice(nick, stats_mssg)
		
		
def hurry_up(cli, gameid, change):
    if var.PHASE != "day": return
    if gameid:
        if gameid != var.DAY_ID:
            return

    chan = botconfig.CHANNEL
    
    if not change:
        cli.msg(chan, ("\02As the sun sinks inexorably toward the horizon, turning the lanky pine " +
                      "trees into fire-edged silhouettes, the villagers are reminded that very little " +
                      "time remains for them to reach a decision; if darkness falls before they have done " +
                      "so, the majority will win the vote. No one will be lynched if there " +
                      "are no votes or an even split.\02"))
        if not var.DAY_TIME_LIMIT_CHANGE:
            return
        if var.LOG_CHAN == True:
            chan_log(cli, var.FULL_ADDRESS, "day_warn")
        if (len(var.list_players()) <= var.SHORT_DAY_PLAYERS):
            tmr = threading.Timer(var.SHORT_DAY_LIMIT_CHANGE, hurry_up, [cli, var.DAY_ID, True])
        else:
            tmr = threading.Timer(var.DAY_TIME_LIMIT_CHANGE, hurry_up, [cli, var.DAY_ID, True])
        tmr.daemon = True
        var.TIMERS["day"] = tmr
        tmr.start()
        return
        
    
    var.DAY_ID = 0
    
    pl = var.list_players()
    avail = len(pl) - len(var.WOUNDED)
    votesneeded = avail // 2 + 1

    found_dup = False
    maxfound = (0, "")
    for votee, voters in iter(var.VOTES.items()):
        if len(voters) > maxfound[0]:
            maxfound = (len(voters), votee)
            found_dup = False
        elif len(voters) == maxfound[0]:
            found_dup = True
    if maxfound[0] > 0 and not found_dup:
        if var.LOG_CHAN == True:
            chan_log(cli, var.FULL_ADDRESS, "forced_lynch")
        cli.msg(chan, "The sun sets.")
        var.LOGGER.logMessage("The sun sets.")
        var.VOTES[maxfound[1]] = [None] * votesneeded
        chk_decision(cli)  # Induce a lynch
    else:
        if var.LOG_CHAN == True:
            chan_log(cli, var.FULL_ADDRESS, "no_lynch")
        cli.msg(chan, ("As the sun sets, the villagers agree to "+
                      "retire to their beds and wait for morning."))
        var.LOGGER.logMessage(("As the sun sets, the villagers agree to "+
                               "retire to their beds and wait for morning."))
        transition_night(cli)
        



@cmd("fnight", raw_nick=True)
def fnight(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        if var.PHASE != "day":
            cli.notice(nick, "It is not daytime.")
        else:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "forced_night")
            hurry_up(cli, 0, True)


@cmd("fday", raw_nick=True)
def fday(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        if var.PHASE != "night":
            cli.notice(nick, "It is not nighttime.")
        else:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "forced_day")
            transition_day(cli)



def chk_decision(cli):
    chan = botconfig.CHANNEL
    pl = var.list_players()
    avail = len(pl) - len(var.WOUNDED) - len(var.NO_LYNCH)
    votesneeded = avail // 2 + 1
    not_lynching = len(var.NO_LYNCH)
    if not_lynching >= avail:
        cli.msg(botconfig.CHANNEL, "Too many players refrained from voting. No lynching occuring.")
        transition_night(cli)
        return
    for votee, voters in iter(var.VOTES.items()):
        if len(voters) >= votesneeded:
            lmsg = random.choice(var.LYNCH_MESSAGES).format(votee, var.get_role(votee))
            cli.msg(botconfig.CHANNEL, lmsg)
            var.LOGGER.logMessage(lmsg.replace("\02", ""))
            var.LOGGER.logBare(votee, "LYNCHED")
            if del_player(cli, votee, True):
                transition_night(cli)

@pmcmd("retract")
def wolfretract(cli, nick, rest):
    if var.PHASE in ("none", "join"):
        cli.notice(nick, "No game is currently running.")
        return
    elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
        cli.notice(nick, "You're not currently playing.")
        return

    role = var.get_role(nick)
    if role not in ('wolf', 'werecrow'):
        return
    if var.PHASE != "night":
        pm(cli, nick, "You may only retract at night.")
        return
    if role == "werecrow":  # Check if already observed
        if var.OBSERVED.get(nick):
            pm(cli, nick, ("You have already transformed into a crow, and "+
                           "cannot turn back until day."))
            return

    if nick in var.KILLS.keys():
        del var.KILLS[nick]
    pm(cli, nick, "You have retracted your vote.")
    #var.LOGGER.logBare(nick, "RETRACT", nick)

@cmd("votes", raw_nick=True)
def show_votes(cli, rnick, chan, rest):
    """Displays the voting statistics."""
    nick, mode, user, host = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
    
        if var.PHASE in ("none", "join"):
            cli.notice(nick, "No game is currently running.")
            return
        if var.PHASE != "day":
            cli.notice(nick, "Voting is only during the day.")
            return
    
        if (var.LAST_VOTES and
            var.LAST_VOTES + timedelta(seconds=var.VOTES_RATE_LIMIT) > datetime.now()):
            cli.msg(chan, nick+": This command is rate-limited.")
            return    
    
        pl = var.list_players()
    
        if nick in pl:
            var.LAST_VOTES = datetime.now()    
        
        if not var.VOTES.values():
            msg = nick+": No votes yet."
            if nick in pl:
                var.LAST_VOTES = None # reset
        else:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "votes")
            votelist = ["{0}: {1} ({2})".format(votee,
                                                len(var.VOTES[votee]),
                                                " ".join(var.VOTES[votee]))
                        for votee in var.VOTES.keys()]
            msg = "{0}: {1}".format(nick, ", ".join(votelist))
        
        if nick in pl:
            cli.msg(chan, msg)
        else:
            cli.notice(nick, msg)

        pl = var.list_players()
        avail = len(pl) - len(var.WOUNDED) - len(var.NO_LYNCH)
        votesneeded = avail // 2 + 1
        not_voting = len(var.NO_LYNCH)
        if not_voting == 1:
            plural = " isn't"
        else:
            plural = "s aren't"
        the_message = ("{0}: \u0002{1}\u0002 players, \u0002{2}\u0002 votes "+
                       "required to lynch, \u0002{3}\u0002 players available " +
                       "to vote. \u0002{4}\u0002 player{5} voting.").format(nick, len(pl), votesneeded, avail, not_voting, plural)
        if nick in pl:
            cli.msg(chan, the_message)
        else:
            cli.notice(nick, the_message)



def chk_traitor(cli):
    for tt in var.ROLES["traitor"]:
        var.ROLES["wolf"].append(tt)
        var.ROLES["traitor"].remove(tt)
        if var.LOG_CHAN == True:
            chan_log(cli, var.FULL_ADDRESS, "traitor_wolf")
        pm(cli, tt, ('HOOOOOOOOOWL. You have become... a wolf!\n'+
                     'It is up to you to avenge your fallen leaders!'))



def stop_game(cli, winner = ""):
    chan = botconfig.CHANNEL
    if var.DAY_START_TIME:
        now = datetime.now()
        td = now - var.DAY_START_TIME
        var.DAY_TIMEDELTA += td
    if var.NIGHT_START_TIME:
        now = datetime.now()
        td = now - var.NIGHT_START_TIME
        var.NIGHT_TIMEDELTA += td

    daymin, daysec = var.DAY_TIMEDELTA.seconds // 60, var.DAY_TIMEDELTA.seconds % 60
    nitemin, nitesec = var.NIGHT_TIMEDELTA.seconds // 60, var.NIGHT_TIMEDELTA.seconds % 60
    total = var.DAY_TIMEDELTA + var.NIGHT_TIMEDELTA
    tmin, tsec = total.seconds // 60, total.seconds % 60
    if var.LOG_CHAN == True:
        chan_log(cli, var.FULL_ADDRESS, "stop_game")
    gameend_msg = ("Game lasted \u0002{0:0>2}:{1:0>2}\u0002. " +
                   "\u0002{2:0>2}:{3:0>2}\u0002 was day. " +
                   "\u0002{4:0>2}:{5:0>2}\u0002 was night. ").format(tmin, tsec,
                                                                     daymin, daysec,
                                                                     nitemin, nitesec)
    cli.msg(chan, gameend_msg)
    var.LOGGER.logMessage(gameend_msg.replace("\02", "")+"\n")
    var.LOGGER.logBare("DAY", "TIME", str(var.DAY_TIMEDELTA.seconds))
    var.LOGGER.logBare("NIGHT", "TIME", str(var.NIGHT_TIMEDELTA.seconds))
    var.LOGGER.logBare("GAME", "TIME", str(total.seconds))

    roles_msg = []
    
    var.ORIGINAL_ROLES["cursed villager"] = var.CURSED  # A hack
    var.ORIGINAL_ROLES["gunner"] = list(var.GUNNERS.keys())

    lroles = list(var.ORIGINAL_ROLES.keys())
    lroles.remove("wolf")
    lroles.insert(0, "wolf")   # picky, howl consistency
    
    for role in lroles:
        if len(var.ORIGINAL_ROLES[role]) == 0 or role == "villager":
            continue
        playersinrole = list(var.ORIGINAL_ROLES[role])
        for i,plr in enumerate(playersinrole):
            if plr.startswith("(dced)"):  # don't care about it here
                playersinrole[i] = plr[6:]
        if len(playersinrole) == 2:
            msg = "The {1} were \u0002{0[0]}\u0002 and \u0002{0[1]}\u0002."
            roles_msg.append(msg.format(playersinrole, var.plural(role)))
        elif len(playersinrole) == 1:
            roles_msg.append("The {1} was \u0002{0[0]}\u0002.".format(playersinrole,
                                                                      role))
        else:
            msg = "The {2} were {0}, and \u0002{1}\u0002."
            nickslist = ["\u0002"+x+"\u0002" for x in playersinrole[0:-1]]
            roles_msg.append(msg.format(", ".join(nickslist),
                                                  playersinrole[-1],
                                                  var.plural(role)))
    cli.msg(chan, " ".join(roles_msg))
    if var.AUTO_LOG_TOGGLED == True:
        var.LOG_CHAN = True
        var.AUTO_LOG_TOGGLED = False
        cli.msg(botconfig.CHANNEL, "Logging has now been re-enabled.")
        cli.msg(botconfig.ADMIN_CHAN, "Game has ended, logging is now \u0002on\u0002.")

    plrl = []
    for role,ppl in var.ORIGINAL_ROLES.items():
        for x in ppl:
            plrl.append((x, role))
    
    var.LOGGER.saveToFile()
    
    for plr, rol in plrl:
        #if plr not in var.USERS.keys():  # he died TODO: when a player leaves, count the game as lost for him
        #    if plr in var.DEAD_USERS.keys():
        #        acc = var.DEAD_USERS[plr]["account"]
        #    else:
        #        continue  # something wrong happened
        #else:
        if plr.startswith("(dced)") and plr[6:] in var.DCED_PLAYERS.keys():
            acc = var.DCED_PLAYERS[plr[6:]]["account"]
        elif plr in var.PLAYERS.keys():
            acc = var.PLAYERS[plr]["account"]
        else:
            continue  #probably fjoin'd fake

        if acc == "*":
            continue  # not logged in during game start
        # determine if this player's team won
        if plr in (var.ORIGINAL_ROLES["wolf"] + var.ORIGINAL_ROLES["traitor"] +
                   var.ORIGINAL_ROLES["werecrow"]):  # the player was wolf-aligned
            if winner == "wolves":
                won = True
            elif winner == "villagers":
                won = False
            else:
                break  # abnormal game stop
        else:
            if winner == "wolves":
                won = False
            elif winner == "villagers":
                won = True
            else:
                break
                
        iwon = won and plr in var.list_players()  # survived, team won = individual win
                
        var.update_role_stats(acc, rol, won, iwon)
    
    reset(cli)
    
    # This must be after reset(cli)
    if var.AFTER_FLASTGAME:
        var.AFTER_FLASTGAME()
        var.AFTER_FLASTGAME = None
    if var.ADMIN_TO_PING:  # It was an flastgame
        cli.msg(chan, "PING! " + var.ADMIN_TO_PING)
        var.ADMIN_TO_PING = None
    
    return True                     
                     
                     

def chk_win(cli):
    """ Returns True if someone won """
    
    chan = botconfig.CHANNEL
    lpl = len(var.list_players())
    
    if lpl == 0:
        cli.msg(chan, "No more players remaining. Game ended.")
        reset(cli)
        return True
        
    if var.PHASE == "join":
        return False
        
        
    lwolves = (len(var.ROLES["wolf"])+
               len(var.ROLES["traitor"])+
               len(var.ROLES["werecrow"]))
    if var.PHASE == "day":
        lpl -= len([x for x in var.WOUNDED if x not in var.ROLES["traitor"]])
        lwolves -= len([x for x in var.WOUNDED if x in var.ROLES["traitor"]])
    
    if lwolves == lpl / 2:
        cli.msg(chan, ("Game over! There are the same number of wolves as "+
                       "villagers. The wolves eat everyone and win."))
        var.LOGGER.logMessage(("Game over! There are the same number of wolves as "+
                               "villagers. The wolves eat everyone, and win."))
        village_win = False
        var.LOGGER.logBare("WOLVES", "WIN")
    elif lwolves > lpl / 2:
        cli.msg(chan, ("Game over! There are more wolves than "+
                       "villagers. The wolves eat everyone, and win."))
        var.LOGGER.logMessage(("Game over! There are more wolves than "+
                               "villagers. The wolves eat everyone, and win."))
        village_win = False
        var.LOGGER.logBare("WOLVES", "WIN")
    elif (not var.ROLES["wolf"] and
          not var.ROLES["traitor"] and
          not var.ROLES["werecrow"]):
        cli.msg(chan, ("Game over! All the wolves are dead! The villagers "+
                       "chop them up, BBQ them, and have a hearty meal."))
        var.LOGGER.logMessage(("Game over! All the wolves are dead! The villagers "+
                               "chop them up, BBQ them, and have a hearty meal."))
        village_win = True
        var.LOGGER.logBare("VILLAGERS", "WIN")
    elif (not var.ROLES["wolf"] and not 
          var.ROLES["werecrow"] and var.ROLES["traitor"]):
        for t in var.ROLES["traitor"]:
            var.LOGGER.logBare(t, "TRANSFORM")
        chk_traitor(cli)
        cli.msg(chan, ('\u0002The villagers, during their celebrations, are '+
                       'frightened as they hear a loud howl. The wolves are '+
                       'not gone!\u0002'))
        var.LOGGER.logMessage(('The villagers, during their celebrations, are '+
                               'frightened as they hear a loud howl. The wolves are '+
                               'not gone!'))
        return chk_win(cli)
    else:
        return False
    stop_game(cli, "villagers" if village_win else "wolves")
    return True





def del_player(cli, nick, forced_death = False, devoice = True):
    """
    Returns: False if one side won.
    arg: forced_death = True when lynched or when the seer/wolf both don't act
    """
    t = time.time()  #  time
    
    var.LAST_STATS = None # reset
    var.LAST_VOTES = None
    
    with var.GRAVEYARD_LOCK:
        if not var.GAME_ID or var.GAME_ID > t:
            #  either game ended, or a new game has started.
            return False
        cmode = []
        if devoice:
            cmode.append(("-v", nick))
        var.del_player(nick)
        ret = True
        if var.PHASE == "join":
            # Died during the joining process as a person
            mass_mode(cli, cmode)
            return not chk_win(cli)
        if var.PHASE != "join" and ret:
            # Died during the game, so quiet!
            if not is_fake_nick(nick):
                cmode.append(("+q", nick+"!*@*"))
            mass_mode(cli, cmode)
            if nick not in var.DEAD:
                var.DEAD.append(nick)
            ret = not chk_win(cli)
        if var.PHASE in ("night", "day") and ret:
            # remove him from variables if he is in there
            for a,b in list(var.KILLS.items()):
                if b == nick:
                    del var.KILLS[a]
                elif a == nick:
                    del var.KILLS[a]
            for x in (var.OBSERVED, var.HVISITED, var.GUARDED):
                keys = list(x.keys())
                for k in keys:
                    if k == nick:
                        del x[k]
                    elif x[k] == nick:
                        del x[k]
            if nick in var.DISCONNECTED:
                del var.DISCONNECTED[nick]
        if var.PHASE == "day" and not forced_death and ret:  # didn't die from lynching
            if nick in var.VOTES.keys():
                del var.VOTES[nick]  #  Delete other people's votes on him
            for k in list(var.VOTES.keys()):
                if nick in var.VOTES[k]:
                    var.VOTES[k].remove(nick)
                    if not var.VOTES[k]:  # no more votes on that guy
                        del var.VOTES[k]
                    break # can only vote once
            if nick in var.NO_LYNCH:
                var.NO_LYNCH.remove(nick)
                    
            if nick in var.WOUNDED:
                var.WOUNDED.remove(nick)
            chk_decision(cli)
        elif var.PHASE == "night" and ret:
            chk_nightdone(cli)
        return ret  


def reaper(cli, gameid):
    # check to see if idlers need to be killed.
    var.IDLE_WARNED = []
    chan = botconfig.CHANNEL
    
    while gameid == var.GAME_ID:
        with var.GRAVEYARD_LOCK:
            if var.WARN_IDLE_TIME or var.KILL_IDLE_TIME:  # only if enabled
                to_warn = []
                to_kill = []
                for nick in var.list_players():
                    lst = var.LAST_SAID_TIME.get(nick, var.GAME_START_TIME)
                    tdiff = datetime.now() - lst
                    if (tdiff > timedelta(seconds=var.WARN_IDLE_TIME) and
                                            nick not in var.IDLE_WARNED):
                        if var.WARN_IDLE_TIME:
                            to_warn.append(nick)
                        var.IDLE_WARNED.append(nick)
                        var.LAST_SAID_TIME[nick] = (datetime.now() -
                            timedelta(seconds=var.WARN_IDLE_TIME))  # Give him a chance
                    elif (tdiff > timedelta(seconds=var.KILL_IDLE_TIME) and
                        nick in var.IDLE_WARNED):
                        if var.KILL_IDLE_TIME:
                            to_kill.append(nick)
                    elif (tdiff < timedelta(seconds=var.WARN_IDLE_TIME) and
                        nick in var.IDLE_WARNED):
                        var.IDLE_WARNED.remove(nick)  # he saved himself from death
                for nck in to_kill:
                    if nck not in var.list_players():
                        continue
                    if var.LOG_CHAN == True:
                        cli.send("whois", nck)
                        @hook("whoisuser", hookid=451)
                        def idle_fetch_host(cli, server, you, nick, ident, host, something, realname):
                            var.IDLE_HOST[nick] = "{0}!{1}@{2}".format(nick, ident, host)
                            chan_log(cli, var.IDLE_HOST[nick], "idle_die")
                            decorators.unhook(HOOKS, 451)
                    cli.msg(chan, ("\u0002{0}\u0002 didn't get out of bed "+
                        "for a very long time. S/He is declared dead. Appears "+
                        "(s)he was a \u0002{1}\u0002.").format(nck, var.get_role(nck)))
                    make_stasis(nck, var.IDLE_STASIS_PENALTY)
                    if not del_player(cli, nck):
                        return
                pl = var.list_players()
                x = [a for a in to_warn if a in pl]
                if x:
                    if var.LOG_CHAN == True:
                        cli.who(botconfig.CHANNEL, "%nuhaf")
                        @hook("whospcrpl", hookid=451)
                        def who_fetch_host(cli, server, you, ident, host, nick, status, account):
                            if nick in x:
                                var.WHO_HOST[nick] = "{0}!{1}@{2}".format(nick, ident, host)
                                chan_log(cli, var.WHO_HOST[nick], "idle_warn")
                    cli.msg(chan, ("{0}: \u0002You have been idling for a while. "+
                                   "Please say something soon or you "+
                                   "might be declared dead.\u0002").format(", ".join(x)))
            for dcedplayer in list(var.DISCONNECTED.keys()):
                _, timeofdc, what = var.DISCONNECTED[dcedplayer]
                if what == "quit" and (datetime.now() - timeofdc) > timedelta(seconds=var.QUIT_GRACE_TIME) and dcedplayer not in var.DCED_GRACE:
                    if var.LOG_CHAN == True:
                        cli.send("whowas", dcedplayer)
                        @hook("whowasuser", hookid=154)
                        def whowas_host(cli, server, you, nick, ident, host, dunno, realname):
                            var.WHOWAS_HOST = "{0}!{1}@{2}".format(nick, ident, host)
                            chan_log(cli, var.WHOWAS_HOST, "die_quit_wait")
                        decorators.unhook(HOOKS, 154)
                    cli.msg(chan, ("\02{0}\02 died due to a fatal attack by wild animals. Appears (s)he "+
                                   "was a \02{1}\02.").format(dcedplayer, var.get_role(dcedplayer)))
                    make_stasis(dcedplayer, var.PART_STASIS_PENALTY)
                    if not del_player(cli, dcedplayer, devoice = False):
                        return
                elif what == "quit" and (datetime.now() - timeofdc) > timedelta(seconds=var.QUIT_GRACE_TIME * 2) and dcedplayer in var.DCED_GRACE:
                    if var.LOG_CHAN == True:
                        cli.send("whowas", dcedplayer)
                        @hook("whowasuser", hookid=154)
                        def whowas_host(cli, server, you, nick, ident, host, dunno, realname):
                            var.WHOWAS_HOST = "{0}!{1}@{2}".format(nick, ident, host)
                            chan_log(cli, var.WHOWAS_HOST, "die_quit_wait")
                        decorators.unhook(HOOKS, 154)
                    cli.msg(chan, ("\02{0}\02 died due to a fatal attack by wild animals. Appears (s)he "+
                                   "was a \02{1}\02.").format(dcedplayer, var.get_role(dcedplayer)))
                    make_stasis(dcedplayer, var.PART_STASIS_PENALTY)
                    var.DCED_GRACE.remove(dcedplayer)
                    if not del_player(cli, dcedplayer, devoice = False):
                        return
                elif what == "part" and (datetime.now() - timeofdc) > timedelta(seconds=var.PART_GRACE_TIME) and dcedplayer not in var.DCED_GRACE:
                    if var.LOG_CHAN == True:
                        cli.send("whois", dcedplayer)
                        @hook("whoisuser", hookid=451)
                        def part_is_host(cli, server, you, nick, ident, host, dunno, realname):
                            if nick == dcedplayer:
                                var.PART = "{0}!{1}@{2}".format(nick, ident, host)
                                chan_log(cli, var.PART, "die_part_on")
                                decorators.unhook(HOOKS, 451)
                        @hook("nosuchnick", hookid=451)
                        def try_whowas(cli, server, you, action, output):
                            cli.send("whowas", dcedplayer)
                            @hook("whowasuser", hookid=451)
                            def part_was_host(cli, server, you, nick, ident, host, dunno, realname):
                                var.PART = "{0}!{1}@{2}".format(nick, ident, host)
                                chan_log(cli, var.PART, "die_part_off")
                                decorators.unhook(HOOKS, 451)
                    cli.msg(chan, ("\02{0}\02 died due to eating poisonous berries.  Appears (s)he was "+
                                   "a \02{1}\02.").format(dcedplayer, var.get_role(dcedplayer)))
                    make_stasis(dcedplayer, var.PART_STASIS_PENALTY)
                    if not del_player(cli, dcedplayer, devoice = False):
                        return
                elif what == "part" and (datetime.now() - timeofdc) > timedelta(seconds=var.PART_GRACE_TIME * 2) and dcedplayer in var.DCED_GRACE:
                    if var.LOG_CHAN == True:
                        cli.send("whois", dcedplayer)
                        @hook("whoisuser", hookid=451)
                        def part_is_host(cli, server, you, nick, ident, host, dunno, realname):
                            if nick == dcedplayer:
                                var.PART = "{0}!{1}@{2}".format(nick, ident, host)
                                chan_log(cli, var.PART, "die_part_on")
                                decorators.unhook(HOOKS, 451)
                        @hook("nosuchnick", hookid=451)
                        def try_whowas(cli, server, you, action, output):
                            cli.send("whowas", dcedplayer)
                            @hook("whowasuser", hookid=451)
                            def part_was_host(cli, server, you, nick, ident, host, dunno, realname):
                                var.PART = "{0}!{1}@{2}".format(nick, ident, host)
                                chan_log(cli, var.PART, "die_part_off")
                                decorators.unhook(HOOKS, 451)
                    cli.msg(chan, ("\02{0}\02 died due to eating poisonous berries.  Appears (s)he was "+
                                   "a \02{1}\02.").format(dcedplayer, var.get_role(dcedplayer)))
                    make_stasis(dcedplayer, var.PART_STASIS_PENALTY)
                    var.DCED_GRACE.remove(dcedplayer)
                    if not del_player(cli, dcedplayer, devoice = False):
                        return
        time.sleep(10)


@cmd("")  # update last said + git check
def update_last_said(cli, nick, chan, rest):
    if chan == botconfig.CHANNEL:
        if var.PHASE not in ("join", "none"):
            var.LAST_SAID_TIME[nick] = datetime.now()
    
        if var.PHASE not in ("none", "join"):
            var.LOGGER.logChannelMessage(nick, rest)

        fullstring = "".join(rest)
        if var.CARE_BOLD and BOLD in fullstring:
            if var.KILL_BOLD: 
                if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
                    if var.EXEMPT_ADMINS == True:
                        cli.msg(nick, "Remember, using bold is not allowed! (Exempted from kick)")
                        return
                cli.send("KICK {0} {1} :Using bold is not allowed".format(botconfig.CHANNEL, nick))
            else:
                cli.msg(botconfig.CHANNEL, nick + ": Using bold in the channel is not allowed.")
        if var.CARE_COLOR and any(code in fullstring for code in ["\x03", "\x16", "\x1f" ]):
            if var.KILL_COLOR: 
                if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
                    if var.EXEMPT_ADMINS == True:
                        cli.msg(nick, "Remember, using colors is not allowed! (Exempted from kick)")
                        return
                cli.send("KICK {0} {1} :Using colors is not allowed".format(botconfig.CHANNEL, nick))
            else:
                cli.msg(botconfig.CHANNEL, nick + ": Using colors in the channel is not allowed.")
        if var.CARE_ADVERTISING and '#' in fullstring and botconfig.CHANNEL not in fullstring: # don't kick if they mention the channel
            if var.KILL_ADVERTISING:
                if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
                    if var.EXEMPT_ADMINS == True:
                        cli.msg(nick, "Remember, advertising is not allowed! (Exempted from kick)")
                        return
                cli.send("KICK {0} {1} :Advertising is not allowed".format(botconfig.CHANNEL, nick))
                
            else:
                cli.msg(botconfig.CHANNEL, nick + ": Advertising is not allowed.")
    if chan == botconfig.DEV_CHAN and nick == botconfig.DEV_BOT:
        args = ['git', 'pull']
        if botconfig.BRANCH_NAME in rest and "/" in rest and "master" in rest and " pushed " not in rest:
            return

        if botconfig.BRANCH_NAME in rest and botconfig.GIT_OWNER in rest and " pushed " in rest:
            args += ["http://github.com:{0}/{1}.git".format(botconfig.GIT_OWNER, botconfig.PROJECT_NAME), botconfig.BRANCH_NAME]
        cli.msg(chan, "Pulling commit from Git . . .")
            

        child = subprocess.Popen(args,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        (out, err) = child.communicate()
        ret = child.returncode

        for line in (out + err).splitlines():
            cli.msg(chan, line.decode('utf-8'))

        if ret != 0:
            if ret < 0:
                cause = 'signal'
            else:
                cause = 'status'

            cli.msg(chan, 'Process {} exited with {} {}'.format(args,
                                                                cause,
                                                                abs(ret)))

@hook("join")
def on_join(cli, raw_nick, chan, acc="*", rname=""):
    nick,m,u,cloak = parse_nick(raw_nick)
    if nick != botconfig.NICK:
        var.IS_ADMIN[nick] = False
        var.IS_OWNER[nick] = False # have everyone in there to avoid errors
    if nick == botconfig.NICK:
        cli.who(chan, "%nuhaf")
        @hook("whospcrpl", hookid=121)
        def put_the_admins(cli, server, nick, ident, host, user, status, acc): # user is the nickname
            var.IS_ADMIN[user] = False
            var.IS_OWNER[user] = False
            if host in botconfig.ADMINS or acc in botconfig.ADMINS_ACCOUNTS:
                var.IS_ADMIN[user] = True
            if host in botconfig.OWNERS or acc in botconfig.OWNERS_ACCOUNTS:
                var.IS_ADMIN[user] = True
                var.IS_OWNER[user] = True
        @hook("endofwho", hookid=121)
        def unhook_admins(*stuff): # not important
            decorators.unhook(HOOKS, 121)

    if cloak in botconfig.ADMINS or cloak in botconfig.OWNERS or acc in botconfig.ADMINS_ACCOUNTS or acc in botconfig.OWNERS_ACCOUNTS:
        var.IS_ADMIN[nick] = True
    if cloak in botconfig.OWNERS or acc in botconfig.OWNERS_ACCOUNTS:
        var.IS_OWNER[nick] = True
    if nick not in var.USERS.keys() and nick != botconfig.NICK and chan == botconfig.CHANNEL:
        var.USERS[nick] = dict(cloak=cloak,account=acc)
    with var.GRAVEYARD_LOCK:
        if nick in var.DISCONNECTED.keys():
            clk = var.DISCONNECTED[nick][0]
            if cloak == clk:
                cli.mode(chan, "+v", nick, nick+"!*@*")
                del var.DISCONNECTED[nick]
                
                cli.msg(chan, "\02{0}\02 has returned to the village.".format(nick))
                for r,rlist in var.ORIGINAL_ROLES.items():
                    if "(dced)"+nick in rlist:
                        rlist.remove("(dced)"+nick)
                        rlist.append(nick)
                        break
                if nick in var.DCED_PLAYERS.keys():
                    var.PLAYERS[nick] = var.DCED_PLAYERS.pop(nick)
    if nick == botconfig.NICK or nick == botconfig.NICK+"_":
        return


@cmd("goat", "g", raw_nick=True)
def goat(cli, rnick, chan, rest):
    """Use a goat to interact with anyone in the channel during the day"""
    nick, mode, user, host = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
        if var.PHASE in ("none", "join"):
            cli.notice(nick, "No game is currently running.")
            return
        elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
            cli.notice(nick, "You're not currently playing.")
            return
        if var.PHASE != "day":
            cli.notice(nick, "You can only do that in the day.")
            return
        if var.GOATED and nick not in var.SPECIAL_ROLES["goat herder"]:
            cli.notice(nick, "You can only do that once per day.")
            return
        ul = list(var.USERS.keys())
        ull = [x.lower() for x in ul]
        rest = re.split(" +",rest)[0].strip().lower()
        if not rest:
            cli.notice(nick, "Not enough parameters.")
            return
        matches = 0
        for player in ull:
            if rest == player:
                victim = player
                break
            if player.startswith(rest):
                victim = player
                matches += 1
        else:
            if matches != 1:
                pm(cli, nick,"\u0002{0}\u0002 is not in this channel.".format(rest))
                return
        victim = ul[ull.index(victim)]
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "goat")
        goatact = random.choice(["kicks", "headbutts"])
        cli.msg(botconfig.CHANNEL, ("\u0002{0}\u0002's goat walks by "+
                                    "and {1} \u0002{2}\u0002.").format(nick,
                                                                       goatact, victim))
        var.LOGGER.logMessage("{0}'s goat walks by and {1} {2}.".format(nick, goatact,
                                                                        victim))
        var.GOATED = True
    
    

@hook("nick")
def on_nick(cli, rnick, nick):
    prefix,u,m,cloak = parse_nick(rnick)
    chan = botconfig.CHANNEL
    if prefix in var.IS_ADMIN and var.IS_ADMIN[prefix] == True:
        var.IS_ADMIN[prefix] = False
        var.IS_ADMIN[nick] = True
    if prefix in var.IS_OWNER and var.IS_OWNER[prefix] == True:
        var.IS_OWNER[prefix] = False
        var.IS_OWNER[nick] = True
    else:
        var.IS_ADMIN[nick] = False

    if prefix in var.USERS:
        var.USERS[nick] = var.USERS.pop(prefix)
        
    if prefix == var.ADMIN_TO_PING:
        var.ADMIN_TO_PING = nick
    
    if prefix in var.USERS and nick in var.DISCONNECTED.keys():
        var.DCED_GRACE.append(nick)
        leave(cli, "nick", prefix)
        return

    # for k,v in list(var.DEAD_USERS.items()):
        # if prefix == k:
            # var.DEAD_USERS[nick] = var.DEAD_USERS[k]
            # del var.DEAD_USERS[k]

    if prefix in var.NO_LYNCH:
        var.NO_LYNCH.remove(prefix)
        var.NO_LYNCH.append(nick)

    if prefix in var.list_players() and prefix not in var.DISCONNECTED.keys():
        r = var.ROLES[var.get_role(prefix)]
        r.append(nick)
        r.remove(prefix)

        if var.PHASE in ("night", "day"):
            for k,v in var.ORIGINAL_ROLES.items():
                if prefix in v:
                    var.ORIGINAL_ROLES[k].remove(prefix)
                    var.ORIGINAL_ROLES[k].append(nick)
                    break
            for k,v in list(var.PLAYERS.items()):
                if prefix == k:
                    var.PLAYERS[nick] = var.PLAYERS[k]
                    del var.PLAYERS[k]
            if prefix in var.GUNNERS.keys():
                var.GUNNERS[nick] = var.GUNNERS.pop(prefix)
            if prefix in var.CURSED:
                var.CURSED.append(nick)
                var.CURSED.remove(prefix)
            for dictvar in (var.HVISITED, var.OBSERVED, var.GUARDED, var.KILLS):
                kvp = []
                for a,b in dictvar.items():
                    if a == prefix:
                        a = nick
                    if b == prefix:
                        b = nick
                    kvp.append((a,b))
                dictvar.update(kvp)
                if prefix in dictvar.keys():
                    del dictvar[prefix]
            if prefix in var.SEEN:
                var.SEEN.remove(prefix)
                var.SEEN.append(nick)
            with var.GRAVEYARD_LOCK:  # to be safe
                if prefix in var.LAST_SAID_TIME.keys():
                    var.LAST_SAID_TIME[nick] = var.LAST_SAID_TIME.pop(prefix)
                if prefix in var.IDLE_WARNED:
                    var.IDLE_WARNED.remove(prefix)
                    var.IDLE_WARNED.append(nick)

        if var.PHASE == "day":
            if prefix in var.WOUNDED:
                var.WOUNDED.remove(prefix)
                var.WOUNDED.append(nick)
            if prefix in var.INVESTIGATED:
                var.INVESTIGATED.remove(prefix)
                var.INVESTIGATED.append(prefix)
            if prefix in var.VOTES:
                var.VOTES[nick] = var.VOTES.pop(prefix)
            for v in var.VOTES.values():
                if prefix in v:
                    v.remove(prefix)
                    v.append(nick)

    # Check if he was DC'ed
    if var.PHASE in ("night", "day"):
        with var.GRAVEYARD_LOCK:
            if nick in var.DISCONNECTED.keys():
                clk = var.DISCONNECTED[nick][0]
                if cloak == clk:
                    cli.mode(chan, "+v", nick, nick+"!*@*")
                    del var.DISCONNECTED[nick]
                    
                    if var.LOG_CHAN == True:
                        chan_log(cli, rnick, "return")
                    cli.msg(chan, ("\02{0}\02 has returned to "+
                                   "the village.").format(nick))

def leave(cli, what, rnick, why=""):
    nick, _, _, cloak = parse_nick(rnick)
    if what == "part" and why != botconfig.CHANNEL: return
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        var.IS_ADMIN[nick] = False
    if nick in var.IS_OWNER and var.IS_OWNER[nick] == True:
        var.IS_OWNER[nick] = False
    if nick not in var.IS_ADMIN:
        var.IS_ADMIN[nick] = False # just in case
        var.IS_OWNER[nick] = False # owner is admin anyway
        
    if why and why == botconfig.CHANGING_HOST_QUIT_MESSAGE:
        return
    if var.PHASE == "none":
        return
    if nick in var.PLAYERS:
        # must prevent double entry in var.ORIGINAL_ROLES
        for r,rlist in var.ORIGINAL_ROLES.items():
            if nick in rlist:
                var.ORIGINAL_ROLES[r].remove(nick)
                var.ORIGINAL_ROLES[r].append("(dced)"+nick)
                break
        var.DCED_PLAYERS[nick] = var.PLAYERS.pop(nick)
    if nick not in var.list_players() or nick in var.DISCONNECTED.keys():
        return
    
        
    #  the player who just quit was in the game
    killhim = True
    if what == "part" and (not var.PART_GRACE_TIME or var.PHASE == "join"):
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "die_part")
        msg = ("\02{0}\02 died due to eating poisonous berries. Appears "+
               "(s)he was a \02{1}\02.").format(nick, var.get_role(nick))
    elif what == "quit" and (not var.QUIT_GRACE_TIME or var.PHASE == "join"):
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "die_quit")
        msg = ("\02{0}\02 died due to a fatal attack by wild animals. Appears "+
               "(s)he was a \02{1}\02.").format(nick, var.get_role(nick))
    elif what == "nick":
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "nick")
        msg = "\02{0}\02 drowned in the lake. Appears (s)he was a \02{1}\02.".format(nick, var.get_role(nick))
    elif what != "kick":
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "leave_wait")
        msg = "\u0002{0}\u0002 has gone missing.".format(nick)
        killhim = False
    else:
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "die_kick")
        msg = ("\02{0}\02 died due to falling off a cliff. Appears "+
               "(s)he was a \02{1}\02.").format(nick, var.get_role(nick))
    cli.msg(botconfig.CHANNEL, msg)
    var.LOGGER.logMessage(msg.replace("\02", ""))
    make_stasis(nick, var.PART_STASIS_PENALTY)
    if killhim:
        del_player(cli, nick)
    else:
        var.DISCONNECTED[nick] = (cloak, datetime.now(), what)

#Functions decorated with hook do not parse the nick by default
hook("part")(lambda cli, nick, *rest: leave(cli, "part", nick, rest[0]))
hook("quit")(lambda cli, nick, *rest: leave(cli, "quit", nick, rest[0]))
hook("kick")(lambda cli, nick, *rest: leave(cli, "kick", rest[1]))


@cmd("quit", "leave", "q", raw_nick=True)
def leave_game(cli, rnick, chan, rest):
    """Quits the game."""
    nick, mode, user, host = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
        if var.PHASE == "none":
            cli.notice(nick, "No game is currently running.")
            return
        if nick not in var.list_players() or nick in var.DISCONNECTED.keys():  # not playing
            cli.notice(nick, "You're not currently playing.")
            return
        if var.LOG_CHAN == True and var.GOT_IT != True:
            chan_log(cli, rnick, "leave")
        var.GOT_IT = False
        _pl = len(var.list_players())
        pl = _pl - 1
        if pl == 0:
            cli.msg(chan, "\02{0}\02 died of an unknown disease. S/He was a \02{1}\02.".format(nick, var.get_role(nick)))
        if not pl == 0:
            cli.msg(chan, "\02{0}\02 died of an unknown disease. S/He was a \02{1}\02. New player count: \02{2}\02".format(nick, var.get_role(nick), pl))
        var.LOGGER.logMessage(("{0} died of an unknown disease. "+
                               "S/He was a {1}.").format(nick, var.get_role(nick)))
        make_stasis(nick, var.LEAVE_STASIS_PENALTY)
        del_player(cli, nick)

@hook("mode")
def mode(cli, nick, chan, mode, *params):
    params = list(params)
    if '-' in mode and 'o' in mode and chan == botconfig.CHANNEL:
        cli.send('whois', botconfig.NICK)
        @hook("whoischannels", hookid=267)
        def is_not_op_or_just_me(cli, server, you, nick, chans): # check if the bot is op in the channel
            if nick == you: # just make sure it's the right one
                if botconfig.CHANNEL in chans:
                    if "@{0}".format(botconfig.CHANNEL) in chans:
                        return
                    elif "{0}".format(botconfig.CHANNEL) in chans and botconfig.OP_NEEDED == True:
                        cli.msg(chan, "Error: OP Status is needed for the game to work")
                        @hook("cannotsendtochan", hookid=267)
                        def game_must_end(cli, server, you, action, output): # not op, end the game
                            stop_game(cli)
                            reset(cli)
                            cli.quit("An error has been encountered")
            decorators.unhook(HOOKS, 267)

def begin_day(cli):
    chan = botconfig.CHANNEL

    # Reset nighttime variables
    var.KILLS = {}  # nicknames of kill victim
    var.GUARDED = ""
    var.KILLER = ""  # nickname of who chose the victim
    var.SEEN = []  # list of seers that have had visions
    var.OBSERVED = {}  # those whom werecrows have observed
    var.HVISITED = {}
    var.GUARDED = {}

    msg = ("The villagers must now vote for whom to lynch. "+
           'Use "{0}lynch <nick>" to cast your vote. {1} votes '+
           'are required to lynch.').format(botconfig.CMD_CHAR, len(var.list_players()) // 2 + 1)
    cli.msg(chan, msg)
    var.LOGGER.logMessage(msg)
    var.LOGGER.logBare("DAY", "BEGIN")

    if var.DAY_TIME_LIMIT_WARN > 0:  # Time limit enabled
        var.DAY_ID = time.time()
        if len(var.list_players()) <= var.SHORT_DAY_PLAYERS:
            t = threading.Timer(var.SHORT_DAY_LIMIT_WARN, hurry_up, [cli, var.DAY_ID, False])
        else:
            t = threading.Timer(var.DAY_TIME_LIMIT_WARN, hurry_up, [cli, var.DAY_ID, False])
        var.TIMERS["day_warn"] = t
        t.daemon = True
        t.start()


def night_warn(cli, gameid):
    if gameid != var.NIGHT_ID:
        return

    if var.PHASE == "day":
        return

    if var.LOG_CHAN == True:
        chan_log(cli, var.FULL_ADDRESS, "night_warn")
    cli.msg(botconfig.CHANNEL, ("\02A few villagers awake early and notice it " +
                                "is still dark outside. " +
                                "The night is almost over and there are " +
                                "still whispers heard in the village.\02"))


def transition_day(cli, gameid=0):
    if gameid:
        if gameid != var.NIGHT_ID:
            return
    var.NIGHT_ID = 0
    
    if var.PHASE == "day":
        return
    
    var.PHASE = "day"
    var.GOATED = False
    chan = botconfig.CHANNEL
    
    # Reset daytime variables
    var.NO_LYNCH = []
    var.VOTES = {}
    var.INVESTIGATED = []
    var.WOUNDED = []
    var.DAY_START_TIME = datetime.now()

    if (not len(var.SEEN)+len(var.KILLS)+len(var.OBSERVED) # neither seer nor wolf acted
            and var.FIRST_NIGHT and var.ROLES["seer"] and not botconfig.DEBUG_MODE):
        if var.LOG_CHAN == True:
            chan_log(cli, var.FULL_ADDRESS, "wolf_die")
        cli.msg(botconfig.CHANNEL, "\02The wolves all die of a mysterious plague.\02")
        for x in var.ROLES["wolf"]+var.ROLES["werecrow"]+var.ROLES["traitor"]:
            if not del_player(cli, x, True):
                return
    
    var.FIRST_NIGHT = False

    td = var.DAY_START_TIME - var.NIGHT_START_TIME
    var.NIGHT_START_TIME = None
    var.NIGHT_TIMEDELTA += td
    min, sec = td.seconds // 60, td.seconds % 60

    found = {}
    for v in var.KILLS.values():
        if v in found:
            found[v] += 1
        else:
            found[v] = 1
    
    maxc = 0
    victim = ""
    dups = []
    for v, c in found.items():
        if c > maxc:
            maxc = c
            victim = v
            dups = []
        elif c == maxc:
            dups.append(v)

    if maxc:
        if dups:
            dups.append(victim)
            victim = random.choice(dups)
    
    message = [("Night lasted \u0002{0:0>2}:{1:0>2}\u0002. It is now daytime. "+
               "The villagers awake, thankful for surviving the night, "+
               "and search the village... ").format(min, sec)]
    dead = []
    crowonly = var.ROLES["werecrow"] and not var.ROLES["wolf"]
    if victim:
        var.LOGGER.logBare(victim, "WOLVESVICTIM", *[y for x,y in var.KILLS.items() if x == victim])
    for crow, target in iter(var.OBSERVED.items()):
        if ((target in list(var.HVISITED.keys()) and var.HVISITED[target]) or  # if var.HVISITED[target] is None, harlot visited self
            target in var.SEEN+list(var.GUARDED.keys())):
            if var.LOG_CHAN == True:
                cli.send("whois", crow)
                @hook("whoisuser", hookid=942)
                def crow_host(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == crow:
                        crow_ = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, crow_, "crow_away_{0}".format(get_role(target)))
                        decorators.unhook(HOOKS, 942)
            pm(cli, crow, ("As the sun rises, you conclude that \u0002{0}\u0002 was not in "+
                          "bed all night, and you fly back to your house.").format(target))
        else:
            if var.LOG_CHAN == True:
                cli.send("whois", crow)
                @hook("whoisuser", hookid=942)
                def crow_host2(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == crow:
                        crow_ = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, nick, "crow_bed_{0}".format(get_role(target)))
                        decorators.unhook(HOOKS, 942)
            pm(cli, crow, ("As the sun rises, you conclude that \u0002{0}\u0002 was sleeping "+
                          "all night long, and you fly back to your house.").format(target))
    if victim in var.GUARDED.values():
        if var.LOG_CHAN == True:
            cli.send("whois", victim)
            @hook("whoisuser", hookid=942)
            def angel_victim_host(cli, server, you, nick, ident, host, dunno, realname):
                if nick == victim:
                    victim_ = "{0}!{1}@{2}".format(nick, ident, host)
                    chan_log(cli, victim_, "saved_angel")
                    decorators.unhook(HOOKS, 942)
        message.append(("\u0002{0}\u0002 was attacked by the wolves last night, but luckily, the "+
                        "guardian angel protected him/her.").format(victim))
        victim = ""
    elif not victim:
        if var.LOG_CHAN == True:
            chan_log(cli, var.FULL_ADDRESS, "no_victim")
        message.append(random.choice(var.NO_VICTIMS_MESSAGES) +
                    " All villagers, however, have survived.")
    elif victim in var.ROLES["harlot"]:  # Attacked harlot, yay no kill
        if var.HVISITED.get(victim):
            if var.LOG_CHAN == True:
                cli.send("whois", victim)
                @hook("whoisuser", hookid=942)
                def harlot_victim_host(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == victim:
                        victim_ = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, victim_, "saved_harlot")
                        decorators.unhook(HOOKS, 942)
            message.append("The wolves' selected victim was a harlot, "+
                           "but she wasn't home.")
    if victim and (victim not in var.ROLES["harlot"] or   # not a harlot
                          not var.HVISITED.get(victim)):   # harlot stayed home
        if var.LOG_CHAN == True:
            cli.send("whois", victim)
            @hook("whoisuser", hookid=942)
            def wolf_victim_host(cli, server, you, nick, ident, host, dunno, realname):
                if nick == victim:
                    victim_ = "{0}!{1}@{2}".format(nick, ident, host)
                    chan_log(cli, victim_, "death")
                    decorators.unhook(HOOKS, 942)
        message.append(("The dead body of \u0002{0}\u0002, a "+
                        "\u0002{1}\u0002, is found. Those remaining mourn his/her "+
                        "death.").format(victim, var.get_role(victim)))
        dead.append(victim)
        var.LOGGER.logBare(victim, "KILLED")
    if victim in var.GUNNERS.keys() and var.GUNNERS[victim]:  # victim had bullets!
        if random.random() < var.GUNNER_KILLS_WOLF_AT_NIGHT_CHANCE:
            wc = var.ROLES["werecrow"]
            for crow in wc:
                if crow in var.OBSERVED.keys():
                    wc.remove(crow)
            # don't kill off werecrows that observed
            deadwolf = random.choice(var.ROLES["wolf"]+wc)
            if var.LOG_CHAN == True:
                cli.send("whois", deadwolf)
                @hook("whoisuser", hookid=942)
                def wolf_killed_host(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == deadwolf:
                        deadwolf_ = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, deadwolf_, "night_shot")
                        decorators.unhook(HOOKS, 942)
            message.append(("Fortunately, the victim, \02{0}\02, had bullets, and "+
                            "\02{1}\02, a \02{2}\02, was shot dead.").format(victim, deadwolf, var.get_role(deadwolf)))
            var.LOGGER.logBare(deadwolf, "KILLEDBYGUNNER")
            dead.append(deadwolf)
    if victim in var.HVISITED.values():  #  victim was visited by some harlot
        for hlt in var.HVISITED.keys():
            if var.HVISITED[hlt] == victim:
                if var.LOG_CHAN == True:
                    cli.send("whois", hlt)
                    @hook("whoisuser", hookid=942)
                    def double_victim_host(cli, server, you, nick, ident, host, dunno, realname):
                        if nick == hlt:
                            harlot_victim = "{0}!{1}@{2}".format(nick, ident, host)
                            chan_log(cli, harlot_victim, "dead_victim")
                            decorators.unhook(HOOKS, 942)
                message.append(("\02{0}\02, a \02harlot\02, made the unfortunate mistake of "+
                                "visiting the victim's house last night and is "+
                                "now dead.").format(hlt))
                dead.append(hlt)
    for harlot in var.ROLES["harlot"]:
        if var.HVISITED.get(harlot) in var.ROLES["wolf"]+var.ROLES["werecrow"]:
            if var.LOG_CHAN == True:
                cli.send("whois", harlot)
                @hook("whoisuser", hookid=942)
                def harlot_dead_wolf(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == harlot:
                        harlot_ = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, harlot_, "visit_wolf")
                        decorators.unhook(HOOKS, 942)
            message.append(("\02{0}\02, a \02harlot\02, made the unfortunate mistake of "+
                            "visiting a wolf's house last night and is "+
                            "now dead.").format(harlot))
            dead.append(harlot)
    for gangel in var.ROLES["guardian angel"]:
        if var.GUARDED.get(gangel) in var.ROLES["wolf"]+var.ROLES["werecrow"]:
            if victim == gangel:
                continue # already dead.
            r = random.random()
            if r < var.GUARDIAN_ANGEL_DIES_CHANCE:
                if var.LOG_CHAN == True:
                    cli.send("whois", gangel)
                    @hook("whoisuser", hookid=942)
                    def dead_guarding(cli, server, you, nick, ident, host, dunno, realname):
                        if nick == gangel:
                            _angel = "{0}!{1}@{2}".format(nick, ident, host)
                            chan_log(cli, _angel, "dead_angel")
                            decorators.unhook(HOOKS, 942)
                message.append(("\02{0}\02, a \02guardian angel\02, "+
                                "made the unfortunate mistake of guarding a wolf "+
                                "last night, attempted to escape, but failed "+
                                "and is now dead.").format(gangel))
                var.LOGGER.logBare(gangel, "KILLEDWHENGUARDINGWOLF")
                dead.append(gangel)
    cli.msg(chan, "\n".join(message))
    for msg in message:
        var.LOGGER.logMessage(msg.replace("\02", ""))
    for deadperson in dead:
        if not del_player(cli, deadperson):
            return
    
    if (var.WOLF_STEALS_GUN and victim in dead and 
        victim in var.GUNNERS.keys() and var.GUNNERS[victim] > 0):
        # victim has bullets
        guntaker = random.choice(var.ROLES["wolf"] + var.ROLES["werecrow"] 
                                 + var.ROLES["traitor"])  # random looter
        numbullets = var.GUNNERS[victim]
        var.WOLF_GUNNERS[guntaker] = numbullets  # transfer bullets to him/her
        if var.LOG_CHAN == True:
            cli.send("whois", guntaker)
            @hook("whoisuser", hookid=942)
            def guntaker_host(cli, server, you, nick, ident, host, dunno, realname):
                if nick == guntaker:
                    wolfgun = "{0}!{1}@{2}".format(nick, ident, host)
                    chan_log(cli, wolfgun, "wolf_gun")
                    decorators.unhook(HOOKS, 942)
        mmsg = ("While searching {2}'s belongings, You found " + 
                "a gun loaded with {0} silver bullet{1}! " + 
                "You may only use it during the day. " +
                "If you shoot at a wolf, you will intentionally miss. " +
                "If you shoot a villager, it is likely that they will be injured.")
        if numbullets == 1:
            mmsg = mmsg.format(numbullets, "", victim)
        else:
            mmsg = mmsg.format(numbullets, "s", victim)
        pm(cli, guntaker, mmsg)
        var.GUNNERS[victim] = 0  # just in case
    begin_day(cli)


def chk_nightdone(cli):
    if (len(var.SEEN) == len(var.ROLES["seer"]) and  # Seers have seen.
        len(var.HVISITED.keys()) == len(var.ROLES["harlot"]) and  # harlots have visited.
        len(var.GUARDED.keys()) == len(var.ROLES["guardian angel"]) and  # guardians have guarded
        len(var.ROLES["werecrow"]+var.ROLES["wolf"]) == len(var.KILLS)+len(var.OBSERVED) and
        var.PHASE == "night"):
        
        # check if wolves are actually agreeing
        if len(set(var.KILLS.values())) > 1:
            return
        
        for x, t in var.TIMERS.items():
            t.cancel()
            
        var.TIMERS = {}
        if var.PHASE == "night":  # Double check
            transition_day(cli)

@cmd("nolynch", "no_lynch", "nl", "novote", raw_nick=True)
def no_lynch(cli, rnick, chan, rest):
    """Allow someone to refrain from voting for the day"""
    nick, mode, user, host = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
        if var.PHASE in ("none", "join"):
            cli.notice(nick, "No game is currently running.")
            return
        elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
            cli.notice(nick, "You're not currently playing.")
            return
        if var.PHASE != "day":
            cli.notice(nick, "Lynching is only during the day. Please wait patiently for morning.")
            return
        if nick in var.WOUNDED:
            cli.msg(chan, "{0}: You are wounded and resting, thus you are unable to vote for the day.".format(nick))
            return
        if nick in var.NO_LYNCH:
            var.NO_LYNCH.remove(nick)
            cli.msg(chan, "{0}: You chose to vote for today.".format(nick))
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "voting")
            return
        candidates = var.VOTES.keys()
        for voter in list(candidates):
            if nick in var.VOTES[voter]:
                var.VOTES[voter].remove(nick)
                if not var.VOTES[voter]:
                    del var.VOTES[voter]
        var.NO_LYNCH.append(nick)
        cli.msg(chan, "{0}: You chose to refrain from voting.".format(nick))
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "not_lynching")
        
        chk_decision(cli)
        return
            

@cmd("lynch", "vote", "l", "v", raw_nick=True)
def vote(cli, rnick, chan, rest):
    """Use this to vote for a candidate to be lynched"""
    nick, mode, user, host = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
    
        if var.PHASE in ("none", "join"):
            cli.notice(nick, "No game is currently running.")
            return
        elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
            cli.notice(nick, "You're not currently playing.")
            return
        if var.PHASE != "day":
            cli.notice(nick, ("Lynching is only allowed during the day. "+
                              "Please wait patiently for morning."))
            return
        if nick in var.WOUNDED:
            cli.msg(chan, ("{0}: You are wounded and resting, "+
                           "thus you are unable to vote for the day.").format(nick))
            return
        pl = var.list_players()
        pl_l = [x.strip().lower() for x in pl]
        rest = re.split(" +",rest)[0].strip().lower()
    
        if not rest:
            cli.notice(nick, "Not enough parameters.")
            return
    
        matches = 0
        for player in pl_l:
            if rest == player:
                target = player
                break
            if player.startswith(rest):
                target = player
                matches += 1
        else:
            if matches != 1:
                pm(cli, nick, "\u0002{0}\u0002 is currently not playing.".format(rest))
                return
        
        voted = pl[pl_l.index(target)]
        
        if not var.SELF_LYNCH_ALLOWED:
            if nick == voted:
                cli.notice(nick, "Please try to save yourself.")
                return
        
        lcandidates = list(var.VOTES.keys())
        for voters in lcandidates:  # remove previous vote
            if nick in var.VOTES[voters]:
                var.VOTES[voters].remove(nick)
                if not var.VOTES.get(voters) and voters != voted:
                    del var.VOTES[voters]
                break
        if voted not in var.VOTES.keys():
            var.VOTES[voted] = [nick]
        else:
            var.VOTES[voted].append(nick)
        if nick in var.NO_LYNCH:
            var.NO_LYNCH.remove(nick)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "vote")
        cli.msg(chan, ("\u0002{0}\u0002 votes for "+
                       "\u0002{1}\u0002.").format(nick, voted))
        var.LOGGER.logMessage("{0} votes for {1}.".format(nick, voted))
        var.LOGGER.logBare(voted, "VOTED", nick)
    
        var.LAST_VOTES = None # reset
    
        chk_decision(cli)



@cmd("retract", "r", raw_nick=True)
def retract(cli, rnick, chan, rest):
    """Takes back your vote during the day (for whom to lynch)"""
    nick, mode, user, host = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
    
    
        if var.PHASE in ("none", "join"):
            cli.notice(nick, "No game is currently running.")
            return
        elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
            cli.notice(nick, "You're not currently playing.")
            return
        
        if var.PHASE != "day":
            cli.notice(nick, ("Lynching is only allowed during the day. "+
                              "Please wait patiently for morning."))
            return

        candidates = var.VOTES.keys()
        for voter in list(candidates):
            if nick in var.VOTES[voter]:
                var.VOTES[voter].remove(nick)
                if not var.VOTES[voter]:
                    del var.VOTES[voter]
                if var.LOG_CHAN == True:
                    chan_log(cli, rnick, "retract")
                cli.msg(chan, "\u0002{0}\u0002 retracted his/her vote.".format(nick))
                var.LOGGER.logBare(voter, "RETRACT", nick)
                var.LOGGER.logMessage("{0} retracted his/her vote.".format(nick))
                var.LAST_VOTES = None # reset
                break
        else:
            cli.notice(nick, "You haven't voted yet.")



@cmd("shoot", "sh", raw_nick=True)
def shoot(cli, rnick, chan, rest):
    """Use this to fire off a bullet at someone in the day if you have bullets"""
    nick, mode, user, host = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
    
        if var.PHASE in ("none", "join"):
            cli.notice(nick, "No game is currently running.")
            return
        elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
            cli.notice(nick, "You're not currently playing.")
            return
        
        if var.PHASE != "day":
            cli.notice(nick, ("Shooting is only allowed during the day. "+
                              "Please wait patiently for morning."))
            return
        if not (nick in var.GUNNERS.keys() or nick in var.WOLF_GUNNERS.keys()):
            pm(cli, nick, "You don't have a gun.")
            return
        elif ((nick in var.GUNNERS.keys() and not var.GUNNERS[nick]) or
              (nick in var.WOLF_GUNNERS.keys() and not var.WOLF_GUNNERS[nick])):
            pm(cli, nick, "You don't have any more bullets.")
            return
        victim = re.split(" +",rest)[0].strip().lower()
        if not victim:
            cli.notice(nick, "Not enough parameters")
            return
        pl = var.list_players()
        pll = [x.lower() for x in pl]
        matches = 0
        for player in pll:
            if victim == player:
                target = player
                break
            if player.startswith(victim):
                target = player
                matches += 1
        else:
            if matches != 1:
                pm(cli, nick, "\u0002{0}\u0002 is currently not playing.".format(victim))
                return
        victim = pl[pll.index(target)]
        if victim == nick:
            cli.notice(nick, "You are holding it the wrong way.")
            return
    
        wolfshooter = nick in var.ROLES["wolf"]+var.ROLES["werecrow"]+var.ROLES["traitor"]
    
        if wolfshooter and nick in var.WOLF_GUNNERS:
            var.WOLF_GUNNERS[nick] -= 1
        else:
            var.GUNNERS[nick] -= 1
    
        rand = random.random()
        if nick in var.ROLES["village drunk"]:
            chances = var.DRUNK_GUN_CHANCES
        else:
            chances = var.GUN_CHANCES
    
        wolfvictim = victim in var.ROLES["wolf"]+var.ROLES["werecrow"]
        if rand <= chances[0] and not (wolfshooter and wolfvictim):  # didn't miss or suicide
            # and it's not a wolf shooting another wolf
        
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "gun_shoot")
            cli.msg(chan, ("\u0002{0}\u0002 shoots \u0002{1}\u0002 with "+
                           "a silver bullet!").format(nick, victim))
            var.LOGGER.logMessage("{0} shoots {1} with a silver bullet!".format(nick, victim))
            victimrole = var.get_role(victim)
            if victimrole in ("wolf", "werecrow"):
                if var.LOG_CHAN == True:
                    chan_log(cli, rnick, "gun_wolf")
                cli.msg(chan, ("\u0002{0}\u0002 is a {1}, and is dying from "+
                               "the silver bullet.").format(victim, var.get_role(victim)))
                var.LOGGER.logMessage(("{0} is a {1}, and is dying from the "+
                                       "silver bullet.").format(victim, var.get_role(victim)))
                if not del_player(cli, victim):
                    return
            elif random.random() <= var.MANSLAUGHTER_CHANCE:
                if var.LOG_CHAN == True:
                    chan_log(cli, rnick, "gun_fatal")
                cli.msg(chan, ("\u0002{0}\u0002 is a not a wolf "+
                               "but was accidentally fatally injured.").format(victim))
                cli.msg(chan, "Appears (s)he was a \u0002{0}\u0002.".format(victimrole))
                var.LOGGER.logMessage("{0} is not a wolf but was accidentally fatally injured.".format(victim))
                var.LOGGER.logMessage("Appears (s)he was a {0}.".format(victimrole))
                if not del_player(cli, victim):
                    return
            else:
                if var.LOG_CHAN == True:
                    chan_log(cli, rnick, "gun_vill")
                cli.msg(chan, ("\u0002{0}\u0002 is a villager and is injured but "+
                               "will have a full recovery. S/He will be resting "+
                               "for the day.").format(victim))
                var.LOGGER.logMessage(("{0} is a villager and is injured but "+
                                "will have a full recovery.  S/He will be resting "+
                                "for the day").format(victim))
                if victim not in var.WOUNDED:
                    var.WOUNDED.append(victim)
                lcandidates = list(var.VOTES.keys())
                for cand in lcandidates:  # remove previous vote
                    if victim in var.VOTES[cand]:
                        var.VOTES[cand].remove(victim)
                        if not var.VOTES.get(cand):
                            del var.VOTES[cand]
                        break
                chk_decision(cli)
                chk_win(cli)
        elif rand <= chances[0] + chances[1]:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "gun_miss")
            cli.msg(chan, "\u0002{0}\u0002 is a lousy shooter.  S/He missed!".format(nick))
            var.LOGGER.logMessage("{0} is a lousy shooter.  S/He missed!".format(nick))
        else:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "gun_death")
            cli.msg(chan, ("\u0002{0}\u0002 should clean his/her weapons more often. "+
                           "The gun exploded and killed him/her!").format(nick))
            cli.msg(chan, "Appears that (s)he was a \u0002{0}\u0002.".format(var.get_role(nick)))
            var.LOGGER.logMessage(("{0} should clean his/her weapers more often. "+
                            "The gun exploded and killed him/her!").format(nick))
            var.LOGGER.logMessage("Appears that (s)he was a {0}.".format(var.get_role(nick)))
            if not del_player(cli, nick):
                return  # Someone won.

@pmcmd("kill", raw_nick=True)
def kill(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    if var.PHASE in ("none", "join"):
        cli.notice(nick, "No game is currently running.")
        return
    elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
        cli.notice(nick, "You're not currently playing.")
        return
    role = var.get_role(nick)
    if role == "traitor":
        return  # they do this a lot.
    if role not in ('wolf', 'werecrow'):
        pm(cli, nick, "Only a wolf may use this command.")
        return
    if var.PHASE != "night":
        pm(cli, nick, "You may only kill people at night.")
        return
    victim = re.split(" +",rest)[0].strip().lower()
    if not victim:
        pm(cli, nick, "Not enough parameters")
        return
    if role == "werecrow":  # Check if flying to observe
        if var.OBSERVED.get(nick):
            pm(cli, nick, ("You have already transformed into a crow; therefore, "+
                           "you are physically unable to kill a villager."))
            return
    pl = var.list_players()
    pll = [x.lower() for x in pl]
    
    matches = 0
    for player in pll:
        if victim == player:
            target = player
            break
        if player.startswith(victim):
            target = player
            matches += 1
    else:
        if matches != 1:
            pm(cli, nick, "\u0002{0}\u0002 is currently not playing.".format(victim))
            return
    
    victim = pl[pll.index(target)]
    if victim == nick:
        pm(cli, nick, "Suicide is bad.  Don't do it.")
        return
    if victim in var.ROLES["wolf"]+var.ROLES["werecrow"]:
        pm(cli, nick, "You may only kill villagers, not other wolves.")
        return
    var.KILLS[nick] = victim
    if var.LOG_CHAN == True:
        chan_log(cli, rnick, "kill")
    pm(cli, nick, "You have selected \u0002{0}\u0002 to be killed.".format(victim))
    var.KILLED = victim
    var.LOGGER.logBare(nick, "SELECT", victim)
    chk_nightdone(cli)


@pmcmd("guard", "protect", "save", raw_nick=True)
def guard(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    if var.PHASE in ("none", "join"):
        cli.notice(nick, "No game is currently running.")
        return
    elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
        cli.notice(nick, "You're not currently playing.")
        return
    role = var.get_role(nick)
    if role != 'guardian angel':
        pm(cli, nick, "Only a guardian angel may use this command.")
        return
    if var.PHASE != "night":
        pm(cli, nick, "You may only protect people at night.")
        return
    victim = re.split(" +",rest)[0].strip().lower()
    if not victim:
        pm(cli, nick, "Not enough parameters")
        return
    if var.GUARDED.get(nick):
        pm(cli, nick, ("You are already protecting "+
                      "\u0002{0}\u0002.").format(var.GUARDED[nick]))
        return
    pl = var.list_players()
    pll = [x.lower() for x in pl]
    matches = 0
    for player in pll:
        if victim == player:
            target = player
            break
        if player.startswith(victim):
            target = player
            matches += 1
    else:
        if matches != 1:
            pm(cli, nick, "\u0002{0}\u0002 is currently not playing.".format(victim))
            return
    victim = pl[pll.index(target)]
    if victim == nick:
        pm(cli, nick, "You may not guard yourself.")
        return
    var.GUARDED[nick] = victim
    if var.LOG_CHAN == True:
        cli.send("whois", victim)
        @hook("whoisuser", hookid=777)
        def guarding(cli, server, you, nick, ident, host, dunno, realname):
            if nick == victim:
                victim_ = "{0}!{1}@{2}".format(nick, ident, host)
                chan_log(cli, rnick, "guarding")
                chan_log(cli, victim_, "guarded")
                decorators.unhook(HOOKS, 777)
    pm(cli, nick, "You are protecting \u0002{0}\u0002 tonight. Farewell!".format(var.GUARDED[nick]))
    pm(cli, var.GUARDED[nick], "You can sleep well tonight, for a guardian angel is protecting you.")
    var.LOGGER.logBare(var.GUARDED[nick], "GUARDED", nick)
    chk_nightdone(cli)



@pmcmd("observe", raw_nick=True)
def observe(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    if var.PHASE in ("none", "join"):
        cli.notice(nick, "No game is currently running.")
        return
    elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
        cli.notice(nick, "You're not currently playing.")
        return
    if not var.is_role(nick, "werecrow"):
        pm(cli, nick, "Only a werecrow may use this command.")
        return
    if var.PHASE != "night":
        pm(cli, nick, "You may only transform into a crow at night.")
        return
    victim = re.split(" +", rest)[0].strip().lower()
    if not victim:
        pm(cli, nick, "Not enough parameters")
        return
    pl = var.list_players()
    pll = [x.lower() for x in pl]
    matches = 0
    for player in pll:
        if victim == player:
            target = player
            break
        if player.startswith(victim):
            target = player
            matches += 1
    else:
        if matches != 1:
            pm(cli, nick,"\u0002{0}\u0002 is currently not playing.".format(victim))
            return
    victim = pl[pll.index(target)]
    if victim == nick.lower():
        pm(cli, nick, "Instead of doing that, you should probably go kill someone.")
        return
    if nick in var.OBSERVED.keys():
        pm(cli, nick, "You are already flying to \02{0}\02's house.".format(var.OBSERVED[nick]))
        return
    if var.get_role(victim) in ("werecrow", "traitor", "wolf"):
        pm(cli, nick, "Flying to another wolf's house is a waste of time.")
        return
    var.OBSERVED[nick] = victim
    if nick in var.KILLS.keys():
        del var.KILLS[nick]
    if var.LOG_CHAN == True:
        cli.send("whois", victim)
        @hook("whoisuser", hookid=824)
        def crow_victim_host(cli, server, you, nick, ident, host, dunno, realname):
            if nick == victim:
                _victim = "{0}!{1}@{2}".format(nick, ident, host)
                chan_log(cli, rnick, "observe")
                chan_log(cli, _victim, "observed")
                decorators.unhook(HOOKS, 824)
    pm(cli, nick, ("You transform into a large crow and start your flight "+
                   "to \u0002{0}'s\u0002 house. You will return after "+
                  "collecting your observations when day begins.").format(victim))
    var.LOGGER.logBare(victim, "OBSERVED", nick)



@pmcmd("id", raw_nick=True)
def investigate(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    if var.PHASE in ("none", "join"):
        cli.notice(nick, "No game is currently running.")
        return
    elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
        cli.notice(nick, "You're not currently playing.")
        return
    if not var.is_role(nick, "detective"):
        pm(cli, nick, "Only a detective may use this command.")
        return
    if var.PHASE != "day":
        pm(cli, nick, "You may only investigate people during the day.")
        return
    if nick in var.INVESTIGATED:
        pm(cli, nick, "You may only investigate one person per round.")
        return
    victim = re.split(" +", rest)[0].strip().lower()
    if not victim:
        pm(cli, nick, "Not enough parameters")
        return
    pl = var.list_players()
    pll = [x.lower() for x in pl]
    matches = 0
    for player in pll:
        if victim == player:
            target = player
            break
        if player.startswith(victim):
            target = player
            matches += 1
    else:
        if matches != 1:
            pm(cli, nick,"\u0002{0}\u0002 is currently not playing.".format(victim))
            return
    victim = pl[pll.index(target)]

    var.INVESTIGATED.append(nick)
    if var.LOG_CHAN == True:
        cli.send("whois", victim)
        @hook("whoisuser", hookid=556)
        def det_vic_host(cli, server, you, nick, ident, host, dunno, realname):
            _check = "{0}!{1}@{2}".format(nick, ident, host)
            chan_log(cli, rnick, "checking")
            chan_log(cli, _check, "checked")
            decorators.unhook(HOOKS, 556)
    pm(cli, nick, ("The results of your investigation have returned. \u0002{0}\u0002"+
                   " is a... \u0002{1}\u0002!").format(victim, var.get_role(victim)))
    var.LOGGER.logBare(victim, "INVESTIGATED", nick)
    if random.random() < var.DETECTIVE_REVEALED_CHANCE:  # a 2/5 chance (should be changeable in settings)
        # Reveal his role!
        for badguy in var.ROLES["wolf"] + var.ROLES["werecrow"] + var.ROLES["traitor"]:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "revealed")
            pm(cli, badguy, ("\u0002{0}\u0002 accidentally drops a paper. The paper reveals "+
                            "that (s)he is the detective!").format(nick))
        var.LOGGER.logBare(nick, "PAPERDROP")



@pmcmd("visit", raw_nick=True)
def hvisit(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    if var.PHASE in ("none", "join"):
        cli.notice(nick, "No game is currently running.")
        return
    elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
        cli.notice(nick, "You're not currently playing.")
        return
    if not var.is_role(nick, "harlot"):
        pm(cli, nick, "Only a harlot may use this command.")
        return
    if var.PHASE != "night":
        pm(cli, nick, "You may only visit someone at night.")
        return
    if var.HVISITED.get(nick):
        pm(cli, nick, ("You are already spending the night "+
                      "with \u0002{0}\u0002.").format(var.HVISITED[nick]))
        return
    victim = re.split(" +",rest)[0].strip().lower()
    if not victim:
        pm(cli, nick, "Not enough parameters")
        return
    pll = [x.lower() for x in var.list_players()]
    matches = 0
    for player in pll:
        if victim == player:
            target = player
            break
        if player.startswith(victim):
            target = player
            matches += 1
    else:
        if matches != 1:
            pm(cli, nick,"\u0002{0}\u0002 is currently not playing.".format(victim))
            return
    victim = var.list_players()[pll.index(target)]
    if nick == victim:  # Staying home
        var.HVISITED[nick] = None
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "staying")
        pm(cli, nick, "You have chosen to stay home for the night.")
    else:
        var.HVISITED[nick] = victim
        if var.LOG_CHAN == True:
            cli.send("whois", victim)
            @hook("whoisuser", hookid=69)
            def hvisited_(cli, server, you, nick, ident, host, dunno, realname):
                if nick == victim:
                    hvisit_ = "{0}!{1}@{2}".format(nick, ident, host)
                    chan_log(cli, rnick, "visit")
                    chan_log(cli, hvisit_, "visited")
                    decorators.unhook(HOOKS, 69)
        pm(cli, nick, ("You are spending the night with \u0002{0}\u0002. "+
                      "Have a good time!").format(var.HVISITED[nick]))
        pm(cli, var.HVISITED[nick], ("You are spending the night with \u0002{0}"+
                                     "\u0002. Have a good time!").format(nick))
        var.LOGGER.logBare(var.HVISITED[nick], "VISITED", nick)
    chk_nightdone(cli)


def is_fake_nick(who):
    return not(re.search("^[a-zA-Z\\\_\]\[`]([a-zA-Z0-9\\\_\]\[`]+)?", who)) or who.lower().endswith("serv")



@pmcmd("see", raw_nick=True)
def see(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    if var.PHASE in ("none", "join"):
        cli.notice(nick, "No game is currently running.")
        return
    elif nick not in var.list_players() or nick in var.DISCONNECTED.keys():
        cli.notice(nick, "You're not currently playing.")
        return
    if not var.is_role(nick, "seer"):
        pm(cli, nick, "Only a seer may use this command")
        return
    if var.PHASE != "night":
        pm(cli, nick, "You may only have visions at night.")
        return
    if nick in var.SEEN:
        pm(cli, nick, "You may only have one vision per round.")
        return
    victim = re.split(" +",rest)[0].strip().lower()
    pl = var.list_players()
    pll = [x.lower() for x in pl]
    if not victim:
        pm(cli, nick, "Not enough parameters")
        return
    matches = 0
    for player in pll:
        if victim == player:
            target = player
            break
        if player.startswith(victim):
            target = player
            matches += 1
    else:
        if matches != 1:
            pm(cli, nick,"\u0002{0}\u0002 is currently not playing.".format(victim))
            return
    victim = pl[pll.index(target)]
    if victim in var.CURSED:
        role = "wolf"
    elif var.get_role(victim) == "traitor":
        role = "villager"
    else:
        role = var.get_role(victim)
    if var.LOG_CHAN == True:
        cli.send("whois", victim)
        @hook("whoisuser", hookid=820)
        def seen_host(cli, server, you, nick, ident, host, dunno, realname):
            if nick == victim:
                seen = "{0}!{1}@{2}".format(nick, ident, host)
                chan_log(cli, rnick, "see")
                chan_log(cli, seen, "seen")
                decorators.unhook(HOOKS, 820)
    pm(cli, nick, ("You have a vision; in this vision, "+
                    "you see that \u0002{0}\u0002 is a "+
                    "\u0002{1}\u0002!").format(victim, role))
    var.SEEN.append(nick)
    var.LOGGER.logBare(victim, "SEEN", nick)
    chk_nightdone(cli)

@cmd("kill", "guard", "protect", "save", "visit", "see", "id")
def wrong_window(cli, nick, chan, rest):
    if chan == botconfig.CHANNEL:
        if var.PHASE in ("night", "day"):
            cli.msg(chan, "{0}: Do you have a role? In any case, you should type that in a PM".format(nick))

@cmd("msg", raw_nick=True)
def msg_through_bot(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        cli.msg(rest, "")
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "msg_bot")
        

@cmd("say", raw_nick=True)
def say_through_bot(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        cli.msg(botconfig.CHANNEL, rest)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "say_bot")

@cmd("me", raw_nick=True)
def me_through_bot(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        cli.msg(botconfig.CHANNEL, "\u0001ACTION {0}\u0001".format(rest))
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "me_bot")

@cmd("act", raw_nick=True)
def act_through_bot(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        params = rest.split()
        cli.msg(params[0], "\u0001ACTION {0}\u0001".format(" ".join(params[1:])))
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "act_bot")

@hook("featurelist")  # For multiple targets with PRIVMSG
def getfeatures(cli, nick, *rest):
    for r in rest:
        if r.startswith("TARGMAX="):
            x = r[r.index("PRIVMSG:"):]
            if "," in x:
                l = x[x.index(":")+1:x.index(",")]
            else:
                l = x[x.index(":")+1:]
            l = l.strip()
            if not l or not l.isdigit():
                continue
            else:
                var.MAX_PRIVMSG_TARGETS = int(l)
                break



def mass_privmsg(cli, targets, msg, notice = False):
    while targets:
        if len(targets) <= var.MAX_PRIVMSG_TARGETS:
            bgs = ",".join(targets)
            targets = ()
        else:
            bgs = ",".join(targets[0:var.MAX_PRIVMSG_TARGETS])
            targets = targets[var.MAX_PRIVMSG_TARGETS:]
        if not notice:
            cli.msg(bgs, msg)
        else:
            cli.notice(bgs, msg)
                
                

@pmcmd("")
def relay(cli, nick, rest):
    """Let the wolves talk to each other through the bot"""
    if var.PHASE not in ("night", "day"):
        return

    badguys = var.ROLES["wolf"] + var.ROLES["traitor"] + var.ROLES["werecrow"]
    if len(badguys) > 1:
        if nick in badguys:
            badguys.remove(nick)  #  remove self from list
        
            if rest.startswith("\01ACTION"):
                rest = rest[7:-1]
                mass_privmsg(cli, [guy for guy in badguys 
                    if (guy in var.PLAYERS and
                        var.PLAYERS[guy]["cloak"] not in var.SIMPLE_NOTIFY)], nick+rest)
                mass_privmsg(cli, [guy for guy in badguys 
                    if (guy in var.PLAYERS and
                        var.PLAYERS[guy]["cloak"] in var.SIMPLE_NOTIFY)], nick+rest, True)
            else:
                mass_privmsg(cli, [guy for guy in badguys 
                    if (guy in var.PLAYERS and
                        var.PLAYERS[guy]["cloak"] not in var.SIMPLE_NOTIFY)], "\02{0}\02 says: {1}".format(nick, rest))
                mass_privmsg(cli, [guy for guy in badguys 
                    if (guy in var.PLAYERS and
                        var.PLAYERS[guy]["cloak"] in var.SIMPLE_NOTIFY)], "\02{0}\02 says: {1}".format(nick, rest), True)

@pmcmd("tellchan", raw_nick=True)
def chan_tell(cli, rnick, rest):
    """Allow wolves to send a message to the channel"""
    nick, mode, user, host = parse_nick(rnick)
    if var.PHASE not in ("night", "day"):
        return
    chan = botconfig.CHANNEL
    wolf = var.ROLES["wolf"]
    traitor = var.ROLES["traitor"]
    crow = var.ROLES["werecrow"]

    if nick not in wolf and nick not in traitor and nick not in crow:
        pm(cli, nick, "Only a wolf can do that")
        return
    if rest.startswith("/me "):
        rest = rest.replace("/me ", "")
        if nick in wolf:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "wolf_tell")
            if len(wolf) > 1:
                cli.msg(chan, ("* \02A wolf\02 {0}".format(rest)))
            elif len(wolf) == 1:
                cli.msg(chan, ("* \02The wolf\02 {0}".format(rest)))
            return
            
        if nick in traitor:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "traitor_tell")
            if len(traitor) > 1:
                cli.msg(chan, ("* \02A traitor\02 {0}".format(rest)))
            elif len(traitor) == 1:
                cli.msg(chan, ("* \02The traitor\02 {0}".format(rest)))
            return
            
        if nick in crow:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "crow_tell")
            if len(crow) > 1:
                cli.msg(chan, ("* \02A werecrow\02 {0}".format(rest)))
            elif len(crow) == 1:
                cli.msg(chan, ("* \02The werecrow\02 {0}".format(rest)))
            return
    else:
        if nick in wolf:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "wolf_tell")
            if len(wolf) > 1:
                cli.msg(chan, ("\02A wolf\02 says: {0}".format(rest)))
            elif len(wolf) == 1:
                cli.msg(chan, ("\02The wolf\02 says: {0}".format(rest)))
            return
            
        if nick in traitor:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "traitor_tell")
            if len(traitor) > 1:
                cli.msg(chan, ("\02A traitor\02 says: {0}".format(rest)))
            elif len(traitor) == 1:
                cli.msg(chan, ("\02The traitor\02 says: {0}".format(rest)))
            return
            
        if nick in crow:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "crow_tell")
            if len(crow) > 1:
                cli.msg(chan, ("\02A werecrow\02 says: {0}".format(rest)))
            elif len(crow) == 1:
                cli.msg(chan, ("\02The werecrow\02 says: {0}".format(rest)))
            return

    
def transition_night(cli):
    if var.PHASE == "night":
        return
    var.PHASE = "night"

    for x, tmr in var.TIMERS.items():  # cancel daytime timer
        tmr.cancel()
    var.TIMERS = {}

    # Reset nighttime variables
    var.KILLS = {}
    var.GUARDED = {}  # key = by whom, value = the person that is visited
    var.KILLER = ""  # nickname of who chose the victim
    var.SEEN = []  # list of seers that have had visions
    var.OBSERVED = {}  # those whom werecrows have observed
    var.HVISITED = {}
    var.NIGHT_START_TIME = datetime.now()

    daydur_msg = ""

    if var.NIGHT_TIMEDELTA or var.START_WITH_DAY:  #  transition from day
        td = var.NIGHT_START_TIME - var.DAY_START_TIME
        var.DAY_START_TIME = None
        var.DAY_TIMEDELTA += td
        min, sec = td.seconds // 60, td.seconds % 60
        daydur_msg = "Day lasted \u0002{0:0>2}:{1:0>2}\u0002. ".format(min,sec)

    chan = botconfig.CHANNEL

    if var.NIGHT_TIME_LIMIT > 0:
        var.NIGHT_ID = time.time()
        t = threading.Timer(var.NIGHT_TIME_LIMIT, transition_day, [cli, var.NIGHT_ID])
        var.TIMERS["night"] = t
        var.TIMERS["night"].daemon = True
        t.start()

    if var.NIGHT_TIME_WARN > 0:
        t2 = threading.Timer(var.NIGHT_TIME_WARN, night_warn, [cli, var.NIGHT_ID])
        var.TIMERS["night_warn"] = t2
        var.TIMERS["night_warn"].daemon = True
        t2.start()


    # send PMs
    ps = var.list_players()
    wolves = var.ROLES["wolf"]+var.ROLES["traitor"]+var.ROLES["werecrow"]
    for wolf in wolves:
        normal_notify = wolf in var.PLAYERS and var.PLAYERS[wolf]["cloak"] not in var.SIMPLE_NOTIFY
    
        if normal_notify:
            if wolf in var.ROLES["wolf"]:
                if var.LOG_CHAN == True:
                    cli.send("whois", wolf)
                    @hook("whoisuser", hookid=646)
                    def call_wolf(cli, server, you, nick, ident, host, dunno, realname):
                        if nick == wolf: # prevent multiple entries in logging (/whois result will only occur for wolf)
                            wolfy = "{0}!{1}@{2}".format(nick, ident, host)
                            chan_log(cli, wolfy, "call_wolf")
                pm(cli, wolf, ('You are a \u0002wolf\u0002. It is your job to kill all the '+
                               'villagers. Use "kill <nick>" to kill a villager.'))
            elif wolf in var.ROLES["traitor"]:
                if var.LOG_CHAN == True:
                    cli.send("whois", wolf)
                    @hook("whoisuser", hookid=646)
                    def call_traitor(cli, server, you, nick, ident, host, dunno, realname):
                        if nick == wolf:
                            traitor = "{0}!{1}@{2}".format(nick, ident, host)
                            chan_log(cli, traitor, "call_traitor")
                pm(cli, wolf, ('You are a \u0002traitor\u0002. You are exactly like a '+
                               'villager and not even a seer can see your true identity. '+
                               'Only detectives can. '))
            else:
                if var.LOG_CHAN == True:
                    cli.send("whois", wolf)
                    @hook("whoisuser", hookid=646)
                    def call_crow(cli, server, you, nick, ident, host, dunno, realname):
                        if nick == wolf:
                            werecrow = "{0}!{1}@{2}".format(nick, ident, host)
                            chan_log(cli, werecrow, "call_crow")
                pm(cli, wolf, ('You are a \u0002werecrow\u0002.  You are able to fly at night. '+
                               'Use "kill <nick>" to kill a a villager.  Alternatively, you can '+
                               'use "observe <nick>" to check if someone is in bed or not. '+
                               'Observing will prevent you from participating in a killing.'))
            pm(cli, wolf, 'You can use "tellchan message" to send a message to the channel, anonymously')
            if len(wolves) > 1:
                pm(cli, wolf, 'Also, if you PM me, your message will be relayed to other wolves.')
        else:
            if var.LOG_CHAN == True:
                cli.who(botconfig.CHANNEL, "%nuhaf")
                @hook("whospcrpl", hookid=646)
                def simple_call(cli, server, you, ident, host, nick, status, account):
                    if nick == wolf:
                        woffle = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, woffle, "simple_{0}".format(var.get_role(wolf)))
            pm(cli, wolf, "You are a \02{0}\02.".format(var.get_role(wolf)))  # !simple
        
            
        
        pl = ps[:]
        pl.sort(key=lambda x: x.lower())
        pl.remove(wolf)  # remove self from list
        for i, player in enumerate(pl):
            if player in var.ROLES["wolf"]:
                pl[i] = player + " (wolf)"
            elif player in var.ROLES["traitor"]:
                pl[i] = player + " (traitor)"
            elif player in var.ROLES["werecrow"]:
                pl[i] = player + " (werecrow)"
        pm(cli, wolf, "\u0002Players:\u0002 "+", ".join(pl))

    for seer in var.ROLES["seer"]:
        pl = ps[:]
        pl.sort(key=lambda x: x.lower())
        pl.remove(seer)  # remove self from list
        
        if seer in var.PLAYERS and var.PLAYERS[seer]["cloak"] not in var.SIMPLE_NOTIFY:
            len_seer = len(seer)
            if var.LOG_CHAN == True:
                cli.send("whois", seer)
                @hook("whoisuser", hookid=646)
                def call_seer(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == seer:
                        seer_ = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, seer_, "call_seer")
            pm(cli, seer, ('You are a \u0002seer\u0002. '+
                          'It is your job to detect the wolves, you '+
                          'may have a vision once per night. '+
                          'Use "see <nick>" to see the role of a player.'))
        else:
            if var.LOG_CHAN == True:
                cli.send("whois", seer)
                @hook("whoisuser", hookid=646)
                def simple_seer(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == seer:
                        seers = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, seers, "simple_seer")
            pm(cli, seer, "You are a \02seer\02.")  # !simple
        pm(cli, seer, "Players: "+", ".join(pl))

    for harlot in var.ROLES["harlot"]:
        pl = ps[:]
        pl.sort(key=lambda x: x.lower())
        pl.remove(harlot)
        if harlot in var.PLAYERS and var.PLAYERS[harlot]["cloak"] not in var.SIMPLE_NOTIFY:
            if var.LOG_CHAN == True:
                cli.send("whois", harlot)
                @hook("whoisuser", hookid=646)
                def call_harlot(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == harlot:
                        harl = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, harl, "call_harlot")
            cli.msg(harlot, ('You are a \u0002harlot\u0002. '+
                             'You may spend the night with one person per round. '+
                             'If you visit a victim of a wolf, or visit a wolf, '+
                             'you will die. Use "visit <nick>" to visit a player. '+
                             'Visiting yourself makes you stay home.'))
        else:
            if var.LOG_CHAN == True:
                cli.send("whois", harlot)
                @hook("whoisuser", hookid=646)
                def simple_harlot(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == harlot:
                        harl = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, harl, "simple_harlot")
            cli.notice(harlot, "You are a \02harlot\02.")  # !simple
        pm(cli, harlot, "Players: "+", ".join(pl))

    for g_angel in var.ROLES["guardian angel"]:
        pl = ps[:]
        pl.sort(key=lambda x: x.lower())
        pl.remove(g_angel)
        if g_angel in var.PLAYERS and var.PLAYERS[g_angel]["cloak"] not in var.SIMPLE_NOTIFY:
            if var.LOG_CHAN == True:
                cli.send("whois", g_angel)
                @hook("whoisuser", hookid=646)
                def call_angel(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == g_angel:
                        _gangel = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, _gangel, "call_angel")
            cli.msg(g_angel, ('You are a \u0002guardian angel\u0002. '+
                              'It is your job to protect the villagers. If you guard a'+
                              ' wolf, there is a 50/50 chance of you dying, if you guard '+
                              'a victim, they will live. Use "guard <nick>" to guard a player.'))
        else:
            if var.LOG_CHAN == True:
                cli.send("whois", g_angel)
                @hook("whoisuser", hookid=646)
                def simple_angel(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == g_angel:
                        s_angel = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, s_angel, "simple_angel")
            cli.notice(g_angel, "You are a \02guardian angel\02.")  # !simple
        pm(cli, g_angel, "Players: " + ", ".join(pl))
    
    for dttv in var.ROLES["detective"]:
        pl = ps[:]
        pl.sort(key=lambda x: x.lower())
        pl.remove(dttv)
        if dttv in var.PLAYERS and var.PLAYERS[dttv]["cloak"] not in var.SIMPLE_NOTIFY:
            if var.LOG_CHAN == True:
                cli.send("whois", dttv)
                @hook("whoisuser", hookid=646)
                def call_det(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == dttv:
                        det_ = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, det_, "call_det")
            cli.msg(dttv, ("You are a \u0002detective\u0002.\n"+
                          "It is your job to determine all the wolves and traitors. "+
                          "Your job is during the day, and you can see the true "+
                          "identity of all users, even traitors.\n"+
                          "But, each time you use your ability, you risk a 2/5 "+
                          "chance of having your identity revealed to the wolves. So be "+
                          "careful. Use \"id nick\" to identify any player during the day."))
        else:
            if var.LOG_CHAN == True:
                cli.send("whois", dttv)
                @hook("whoisuser", hookid=646)
                def simple_det(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == dttv:
                        s_det = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, s_det, "simple_det")
            cli.notice(dttv, "You are a \02detective\02.")  # !simple
        pm(cli, dttv, "Players: " + ", ".join(pl))
    for d in var.ROLES["village drunk"]:
        if var.FIRST_NIGHT:
            if var.LOG_CHAN == True:
                cli.send("whois", d)
                @hook("whoisuser", hookid=646)
                def call_drunk(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == d:
                        drunk = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, drunk, "call_drunk")
            pm(cli, d, 'You have been drinking too much! You are the \u0002village drunk\u0002.')

    for g in tuple(var.GUNNERS.keys()):
        if g not in ps:
            continue
        elif not var.GUNNERS[g]:
            continue
        norm_notify = g in var.PLAYERS and var.PLAYERS[g]["cloak"] not in var.SIMPLE_NOTIFY
        if norm_notify:
            if var.LOG_CHAN == True:
                cli.send("whois", g)
                @hook("whoisuser", hookid=646)
                def call_gunner(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == g:
                        gunner = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, gunner, "call_gunner")
            gun_msg =  ("You hold a gun that shoots special silver bullets. You may only use it "+
                        "during the day. If you shoot a wolf, (s)he will die instantly, but if you "+
                        "shoot a villager, that villager will likely survive. Use '"+botconfig.CMD_CHAR+
                        "shoot <nick>' in channel during the day to shoot a player. You get {0}.")
        else:
            if var.LOG_CHAN == True:
                cli.send("whois", g)
                @hook("whoisuser", hookid=646)
                def simple_gunner(cli, server, you, nick, ident, host, dunno, realname):
                    if nick == g:
                        gun_s = "{0}!{1}@{2}".format(nick, ident, host)
                        chan_log(cli, gun_s, "simple_gunner")
            gun_msg = ("You have a \02gun\02 with {0}.")
        if var.GUNNERS[g] == 1:
            gun_msg = gun_msg.format("1 bullet")
        elif var.GUNNERS[g] > 1:
            gun_msg = gun_msg.format(str(var.GUNNERS[g]) + " bullets")
        else:
            continue
        
        pm(cli, g, gun_msg)
    if var.LOG_CHAN == True:
        chan_log(cli, var.FULL_ADDRESS, "night_begin")
    dmsg = (daydur_msg + "It is now nighttime. All players "+
                   "check for PMs from me for instructions. "+
                   "If you did not receive one, simply sit back, "+
                   "relax, and wait patiently for morning.")
    cli.msg(chan, dmsg)
    var.LOGGER.logMessage(dmsg.replace("\02", ""))
    var.LOGGER.logBare("NIGHT", "BEGIN")

    # cli.msg(chan, "DEBUG: "+str(var.ROLES))
    if not var.ROLES["wolf"]:  # Probably something interesting going on.
        chk_nightdone(cli)
        chk_traitor(cli)
    if var.LOG_CHAN == True:
        decorators.unhook(HOOKS, 646)



def cgamemode(cli, *args):
    chan = botconfig.CHANNEL
    if var.ORIGINAL_SETTINGS:  # needs reset
        reset_settings()
    
    for arg in args:
        modeargs = arg.split("=", 1)
        
        if len(modeargs) < 2:  # no equal sign in the middle of the arg
            cli.msg(botconfig.CHANNEL, "Invalid syntax.")
            return False
        
        modeargs[0] = modeargs[0].strip()
        if modeargs[0] in var.GAME_MODES.keys():
            md = modeargs.pop(0)
            modeargs[0] = modeargs[0].strip()
            try:
                gm = var.GAME_MODES[md](modeargs[0])
                for attr in dir(gm):
                    val = getattr(gm, attr)
                    if (hasattr(var, attr) and not callable(val)
                                            and not attr.startswith("_")):
                        var.ORIGINAL_SETTINGS[attr] = getattr(var, attr)
                        setattr(var, attr, val)
                return True
            except var.InvalidModeException as e:
                cli.msg(botconfig.CHANNEL, "Invalid mode: "+str(e))
                return False
        else:
            cli.msg(chan, "Mode \u0002{0}\u0002 not found.".format(modeargs[0]))

            
@cmd("", raw_nick=True)
def outside_ping(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if var.EXT_PING.lower() in rest.lower() and var.EXT_PING != "" and nick.lower() != var.EXT_PING.lower():
        cli.msg(botconfig.SPECIAL_CHAN, "{3}: {0} pinged you in {1} : {2}".format(nick, chan, rest, var.EXT_PING))
        chan_log(cli, rnick, "external_ping")
    

@cmd("start", "st", "go", raw_nick=True)
def start(cli, rnick, chan, rest):
    """Starts a game of Werewolf"""
    nick, mode, user, host = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
    
        villagers = var.list_players()
        pl = villagers[:]

        if var.PHASE == "none":
            cli.notice(nick, "No game is currently running.")
            return
        if var.PHASE != "join":
            cli.notice(nick, "Werewolf is already in play.")
            return
        if nick not in villagers and nick != chan:
            cli.notice(nick, "You're currently not playing.")
            return

        
        now = datetime.now()
        var.GAME_START_TIME = now  # Only used for the idler checker
        dur = int((var.CAN_START_TIME - now).total_seconds())
        if dur > 0:
            cli.msg(chan, "Please wait at least {0} more seconds.".format(dur))
            return

        if len(villagers) < 4:
            cli.msg(chan, "{0}: Four or more players are required to play.".format(nick))
            return

        for pcount in range(len(villagers), 3, -1):
            addroles = var.ROLES_GUIDE.get(pcount)
            if addroles:
                break
    
        if var.ORIGINAL_SETTINGS:  # Custom settings
            while True:
                wvs = (addroles[var.INDEX_OF_ROLE["wolf"]] +
                    addroles[var.INDEX_OF_ROLE["traitor"]])
                if len(villagers) < (sum(addroles) - addroles[var.INDEX_OF_ROLE["gunner"]] -
                        addroles[var.INDEX_OF_ROLE["cursed villager"]]):
                    cli.msg(chan, "There are too few players in the "+
                                  "game to use the custom roles.")
                elif not wvs:
                    cli.msg(chan, "There has to be at least one wolf!")
                elif wvs > (len(villagers) / 2):
                    cli.msg(chan, "Too many wolves.")
                else:
                    break
                reset_settings()
                cli.msg(chan, "The default settings have been restored.  Please !start again.")
                var.PHASE = "join"
                return

            
        if var.ADMIN_TO_PING:
            if "join" in COMMANDS.keys():
                COMMANDS["join"] = [lambda *spam: cli.msg(chan, "This command has been disabled by an admin.")]
            if "start" in COMMANDS.keys():
                COMMANDS["start"] = [lambda *spam: cli.msg(chan, "This command has been disabled by an admin.")]

        var.ROLES = {}
        var.CURSED = []
        var.GUNNERS = {}
        var.WOLF_GUNNERS = {}

        villager_roles = ("gunner", "cursed villager")
        for i, count in enumerate(addroles):
            role = var.ROLE_INDICES[i]
            if role in villager_roles:
                var.ROLES[role] = [None] * count
                continue # We deal with those later, see below
            selected = random.sample(villagers, count)
            var.ROLES[role] = selected
            for x in selected:
                villagers.remove(x)

        # Now for the villager roles
        # Select cursed (just a villager)
        if var.ROLES["cursed villager"]:
            possiblecursed = pl[:]
            for cannotbe in (var.ROLES["wolf"] + var.ROLES["werecrow"] +
                             var.ROLES["seer"] + var.ROLES["village drunk"]):
                                              # traitor can be cursed
                possiblecursed.remove(cannotbe)
        
            var.CURSED = random.sample(possiblecursed, len(var.ROLES["cursed villager"]))
        del var.ROLES["cursed villager"]
    
        # Select gunner (also a villager)
        if var.ROLES["gunner"]:
                   
            possible = pl[:]
            for cannotbe in (var.ROLES["wolf"] + var.ROLES["werecrow"] +
                             var.ROLES["traitor"]):
                possible.remove(cannotbe)
            
            for csd in var.CURSED:  # cursed cannot be gunner
                if csd in possible:
                    possible.remove(csd)
                
            for gnr in random.sample(possible, len(var.ROLES["gunner"])):
                if gnr in var.ROLES["village drunk"]:
                    var.GUNNERS[gnr] = (var.DRUNK_SHOTS_MULTIPLIER * 
                                        math.ceil(var.SHOTS_MULTIPLIER * len(pl)))
                else:
                    var.GUNNERS[gnr] = math.ceil(var.SHOTS_MULTIPLIER * len(pl))
        del var.ROLES["gunner"]
        var.SPECIAL_ROLES["goat herder"] = []
        if var.GOAT_HERDER:
            var.SPECIAL_ROLES["goat herder"] = [ nick ]

        var.ROLES["villager"] = villagers
        if var.LOG_CHAN == True and var.GOT_IT != True:
            chan_log(cli, rnick, "game_start")
        var.GOT_IT = False
        if var.LOG_CHAN == True and var.LOG_AUTO_TOGGLE == True and len(pl) >= var.MIN_LOG_PLAYERS:
            cli.msg(chan, "There are more than \u0002{0}\u0002 players. Logging was automatically disabled to reduce lag.".format(var.MIN_LOG_PLAYERS))
            cli.msg(botconfig.ADMIN_CHAN, "Logging is now \u0002off\u0002 to reduce lag.")
            var.LOG_CHAN = False
            var.AUTO_LOG_TOGGLED = True
        cli.msg(chan, ("{0}: Welcome to Werewolf, the popular detective/social party "+
                       "game (a theme of Mafia).").format(", ".join(pl)))
        cli.mode(chan, "+m")

        var.ORIGINAL_ROLES = copy.deepcopy(var.ROLES)  # Make a copy
    
        var.DAY_TIMEDELTA = timedelta(0)
        var.NIGHT_TIMEDELTA = timedelta(0)
        var.DAY_START_TIME = None
        var.NIGHT_START_TIME = None
        var.LAST_PING = None
    
        var.LOGGER.log("Game Start")
        var.LOGGER.logBare("GAME", "BEGIN", nick)
        var.LOGGER.logBare(str(len(pl)), "PLAYERCOUNT")
    
        var.LOGGER.log("***")
        var.LOGGER.log("ROLES: ")
        for rol in var.ROLES:
            r = []
            for rw in var.plural(rol).split(" "):
                rwu = rw[0].upper()
                if len(rw) > 1:
                    rwu += rw[1:]
                r.append(rwu)
            r = " ".join(r)
            var.LOGGER.log("{0}: {1}".format(r, ", ".join(var.ROLES[rol])))
        
            for plr in var.ROLES[rol]:
                var.LOGGER.logBare(plr, "ROLE", rol)
    
        if var.CURSED:
            var.LOGGER.log("Cursed Villagers: "+", ".join(var.CURSED))
        
            for plr in var.CURSED:
                var.LOGGER.logBare(plr+" ROLE cursed villager")
        if var.GUNNERS:
            var.LOGGER.log("Villagers With Bullets: "+", ".join([x+"("+str(y)+")" for x,y in var.GUNNERS.items()]))
            for plr in var.GUNNERS:
                var.LOGGER.logBare(plr, "ROLE gunner")
    
        var.LOGGER.log("***")        
        
        var.PLAYERS = {plr:dict(var.USERS[plr]) for plr in pl if plr in var.USERS}    

        if not var.START_WITH_DAY:
            var.FIRST_NIGHT = True
            transition_night(cli)
        else:
            transition_day(cli)
        
        for cloak in var.illegal_joins:
            if var.illegal_joins[cloak] != 0:
                var.illegal_joins[cloak] -= 1

        # DEATH TO IDLERS!
        reapertimer = threading.Thread(None, reaper, args=(cli,var.GAME_ID))
        reapertimer.daemon = True
        reapertimer.start()
    
@pmcmd("fstasis", raw_nick=True)
def fstasis(cli, rnick, *rest):
    nick, mode, user, host = parse_nick(rnick)
    data = rest[0].split()
    if len(data) == 2:
        if data[0] in var.USERS:
            cloak = var.USERS[str(data[0])]['cloak']
        else:
            cloak = None
        amt = data[1]
        if cloak is not None:
            var.illegal_joins[cloak] = int(amt)
            cli.msg(nick, "{0} is now in stasis for {1} games".format(data[0], amt))
        else:
            cli.msg(nick, "Sorry, that user has a None cloak")
    else:
        cli.msg(nick, "current illegal joins: " + str(var.illegal_joins))

@cmd("wait", "w", raw_nick=True)
def wait(cli, rnick, chan, rest):
    """Increase the wait time (before !start can be used)"""
    nick, mode, user, host = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
        pl = var.list_players()
    
    
    
        if var.PHASE == "none":
            cli.notice(nick, "No game is currently running.")
            return
        if var.PHASE != "join":
            cli.notice(nick, "Werewolf is already in play.")
            return
        if nick not in pl:
            cli.notice(nick, "You're currently not playing.")
            return
        if var.WAITED >= var.MAXIMUM_WAITED:
            cli.msg(chan, "Limit has already been reached for extending the wait time.")
            return

        now = datetime.now()
        if now > var.CAN_START_TIME:
            var.CAN_START_TIME = now + timedelta(seconds=var.EXTRA_WAIT)
        else:
            var.CAN_START_TIME += timedelta(seconds=var.EXTRA_WAIT)
        var.WAITED += 1
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "wait")
        cli.msg(chan, ("\u0002{0}\u0002 increased the wait time by "+
                       "{1} seconds.").format(nick, var.EXTRA_WAIT))

@cmd("roles")
def listroles(cli, nick, chan, rest):
    """Display which roles are enabled and when"""

    old = var.ROLES_GUIDE.get(None)

    txt = ""

    pl = len(var.list_players()) + len(var.DEAD)
    if pl > 0:
        txt += '{0}: There are \u0002{1}\u0002 playing. '.format(nick, pl)

    for i,v in sorted({i:var.ROLES_GUIDE[i] for i in var.ROLES_GUIDE if i is not None}.items()):
        if (i <= pl):
            txt += BOLD
        txt += "[" + str(i) + "] "
        if (i <= pl):
            txt += BOLD
        for index, amt in enumerate(v):
            if amt - old[index] != 0:
                if amt > 1:
                    txt = txt + var.ROLE_INDICES[index] + "({0}), ".format(amt)
                else:
                    txt = txt + var.ROLE_INDICES[index] + ", "
        txt = txt[:-2] + " "
        old = v
    if chan == nick:
        pm(cli, nick, txt)
    else:
        cli.msg(chan, txt)

@cmd('gamestats', 'gstats', raw_nick=True)
def game_stats(cli, rnick, chan, rest):
    """Gets the game stats for a given game size or lists game totals for all game sizes if no game size is given."""
    nick, mode, user, host = parse_nick(rnick)
    if (chan != nick and var.LAST_GSTATS and var.GSTATS_RATE_LIMIT and
            var.LAST_GSTATS + timedelta(seconds=var.GSTATS_RATE_LIMIT) >
            datetime.now()):
        cli.notice(nick, ('This command is rate-limited. Please wait a while '
                          'before using it again.'))
        return

    if chan != nick:
        var.LAST_GSTATS = datetime.now()

    if var.PHASE not in ('none', 'join'):
        cli.notice(nick, 'Wait until the game is over to view stats.')
        return
    
    # List all games sizes and totals if no size is given
    if not rest:
        if chan == nick:
            pm(cli, nick, var.get_game_totals())
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "game_stats_pm")
        else:
            cli.msg(chan, var.get_game_totals())
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "game_stats")

        return

    # Check for invalid input
    rest = rest.strip()
    if not rest.isdigit() or int(rest) > var.MAX_PLAYERS or int(rest) < var.MIN_PLAYERS:
        cli.notice(nick, ('Please enter an integer between {} and '
                          '{}.').format(var.MIN_PLAYERS, var.MAX_PLAYERS))
        return
    
    # Attempt to find game stats for the given game size
    if chan == nick:
        pm(cli, nick, var.get_game_stats(int(rest)))
    else:
        cli.msg(chan, var.get_game_stats(int(rest)))


@pmcmd('gamestats', 'gstats', raw_nick=True)
def game_stats_pm(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    game_stats(cli, nick, rnick, rest)

    
@cmd('playerstats', 'pstats', 'player', raw_nick=True)
def player_stats(cli, rnick, chan, rest):
    """Gets the stats for the given player and role or a list of role totals if no role is given."""
    nick, mode, user, host = parse_nick(rnick)
    if (chan != nick and var.LAST_PSTATS and var.PSTATS_RATE_LIMIT and
            var.LAST_PSTATS + timedelta(seconds=var.PSTATS_RATE_LIMIT) >
            datetime.now()):
        cli.notice(nick, ('This command is rate-limited. Please wait a while '
                          'before using it again.'))
        return

    if chan != nick:
        var.LAST_PSTATS = datetime.now()

    if var.PHASE not in ('none', 'join'):
        cli.notice(nick, 'Wait until the game is over to view stats.')
        return
    
    params = rest.split()

    # Check if we have enough parameters
    if params:
        user = params[0]
    else:
        user = nick

    # Find the player's account if possible
    if user in var.USERS:
        acc = var.USERS[user]['account']
        if acc == '*':
            if user == nick:
                cli.notice(nick, 'You are not identified with NickServ.')
            else:  
                cli.notice(nick, user + ' is not identified with NickServ.')

            return
    else:
        acc = user
    
    # List the player's total games for all roles if no role is given
    if len(params) < 2:
        if chan == nick:
            pm(cli, nick, var.get_player_totals(acc))
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "player_stats_all_pm")
        else:
            cli.msg(chan, var.get_player_totals(acc))
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "player_stats_all")
    else:
        role = ' '.join(params[1:])  

        # Attempt to find the player's stats
        if chan == nick:
            pm(cli, nick, var.get_player_stats(acc, role))
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "player_stats_{0}_pm".format(role))
        else:
            cli.msg(chan, var.get_player_stats(acc, role))
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "player_stats_{0}".format(role))
    

@pmcmd('playerstats', 'pstats', 'player', raw_nick=True)
def player_stats_pm(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    player_stats(cli, nick, rnick, rest)

@cmd("time", raw_nick=True)
def timeleft(cli, rnick, chan, rest):
    """Returns the time left until the next day/night transition."""
    nick, mode, user, host = parse_nick(rnick)
    
    if var.PHASE not in ("day", "night"):
        cli.notice(nick, "No game is currently running.")
        return

    if (chan != nick and var.LAST_TIME and
            var.LAST_TIME + timedelta(seconds=var.TIME_RATE_LIMIT) > datetime.now()):
        cli.notice(nick, ("This command is rate-limited. Please wait a while "
                          "before using it again."))
        return

    if chan != nick:
        var.LAST_TIME = datetime.now()

    if var.PHASE == "day":
        if var.STARTED_DAY_PLAYERS <= var.SHORT_DAY_PLAYERS:
            remaining = int((var.SHORT_DAY_LIMIT_WARN +
                var.SHORT_DAY_LIMIT_CHANGE) - (datetime.now() -
                var.DAY_START_TIME).total_seconds())
        else:
            remaining = int((var.DAY_TIME_LIMIT_WARN +
                var.DAY_TIME_LIMIT_CHANGE) - (datetime.now() -
                var.DAY_START_TIME).total_seconds())
    else:
        remaining = int(var.NIGHT_TIME_LIMIT - (datetime.now() -
            var.NIGHT_START_TIME).total_seconds())
    
    #Check if timers are actually enabled
    if (var.PHASE == "day") and ((var.STARTED_DAY_PLAYERS <= var.SHORT_DAY_PLAYERS and 
            var.SHORT_DAY_LIMIT_WARN == 0) or (var.DAY_TIME_LIMIT_WARN == 0 and
            var.STARTED_DAY_PLAYERS > var.SHORT_DAY_PLAYERS)):
        msg = "Day timers are currently disabled."
    elif var.PHASE == "night" and var.NIGHT_TIME_LIMIT == 0:
        msg = "Night timers are currently disabled."
    else:
        msg = "There is \x02{0[0]:0>2}:{0[1]:0>2}\x02 remaining until {1}.".format(
            divmod(remaining, 60), "sunrise" if var.PHASE == "night" else "sunset")  
        

    if nick == chan:
        pm(cli, nick, msg)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "time_pm")
    else:
        cli.msg(chan, msg)
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "time")

@pmcmd("time", raw_nick=True)
def timeleft_pm(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    timeleft(cli, nick, rnick, rest)
    
@pmcmd("roles")
def listroles_pm(cli, nick, rest):
    listroles(cli, nick, nick, rest)
    
@cmd("myrole", raw_nick=True)
def myrole(cli, rnick, chan, rest):
    """Reminds you of which role you have."""
    nick, mode, user, host = parse_nick(rnick)
    if var.PHASE in ("none", "join"):
        cli.notice(nick, "No game is currently running.")
        return
    
    ps = var.list_players()
    if nick not in ps:
        cli.notice(nick, "You're currently not playing.")
        return
    
    pm(cli, nick, "You are a \02{0}\02.".format(var.get_role(nick)))
    if var.LOG_CHAN == True:
        chan_log(cli, rnick, "role")
    
    # Check for gun/bullets
    if nick in var.GUNNERS and var.GUNNERS[nick]:
        if var.GUNNERS[nick] == 1:
            pm(cli, nick, "You have a \02gun\02 with {0} {1}.".format(var.GUNNERS[nick], "bullet"))
        else:
            pm(cli, nick, "You have a \02gun\02 with {0} {1}.".format(var.GUNNERS[nick], "bullets"))
    elif nick in var.WOLF_GUNNERS and var.WOLF_GUNNERS[nick]:
        if var.WOLF_GUNNERS[nick] == 1:
            pm(cli, nick, "You have a \02gun\02 with {0} {1}.".format(var.WOLF_GUNNERS[nick], "bullet"))
        else:
            pm(cli, nick, "You have a \02gun\02 with {0} {1}.".format(var.WOLF_GUNNERS[nick], "bullets"))

@pmcmd("myrole", raw_nick=True)
def myrole_pm(cli, rnick, rest):
    myrole(cli, rnick, "", rest)

@cmd("fwait", raw_nick=True)
def fwait(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
    
        pl = var.list_players()
        
        
        
        if var.PHASE == "none":
            cli.notice(nick, "No game is currently running.")
            return
        if var.PHASE != "join":
            cli.notice(nick, "Werewolf is already in play.")
            return

        rest = re.split(" +", rest.strip(), 1)[0]
        if rest and rest.isdigit():
            if len(rest) < 4:
                extra = int(rest)
            else:
                cli.msg(botconfig.CHANNEL, "{0}: We don't have all day!".format(nick))
                return
        else:
            extra = var.EXTRA_WAIT
            
        now = datetime.now()
        if now > var.CAN_START_TIME:
            var.CAN_START_TIME = now + timedelta(seconds=extra)
        else:
            var.CAN_START_TIME += timedelta(seconds=extra)
        var.WAITED += 1
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "forced_wait")
        cli.msg(botconfig.CHANNEL, ("\u0002{0}\u0002 forcibly increased the wait time by "+
                                    "{1} seconds.").format(nick, extra))


@cmd("fstop", raw_nick=True)
def reset_game(cli, rnick, chan, rest):
    nick, mode, user, host = parse_nick(rnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        if var.PHASE == "none":
            cli.notice(nick, "No game is currently running.")
            return
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "forced_stop")
        cli.msg(botconfig.CHANNEL, "\u0002{0}\u0002 has forced the game to stop.".format(nick))
        var.LOGGER.logMessage("{0} has forced the game to stop.".format(nick))
        if var.PHASE != "join":
            stop_game(cli)
        else:
            reset(cli)


@pmcmd("rules", raw_nick=True)
def pm_rules(cli, rnick, rest):
    nick, mode, user, host = parse_nick(rnick)
    if var.LOG_CHAN == True:
        chan_log(cli, rnick, "pm_rules")
    cli.notice(nick, var.RULES)

@cmd("rules", raw_nick=True)
def show_rules(cli, rnick, chan, rest):
    """Displays the rules"""
    nick, mode, user, host = parse_nick(rnick)
    if var.PHASE in ("day", "night") and nick not in var.list_players() and chan == botconfig.CHANNEL:
        cli.notice(nick, var.RULES)
        return
    if var.LOG_CHAN == True:
        chan_log(cli, rnick, "rules")
    cli.msg(chan, var.RULES)
    var.LOGGER.logMessage(var.RULES)


@pmcmd("help", raw_nick = True)
def get_help(cli, rnick, rest):
    """Gets help."""
    if var.LOG_CHAN == True and var.GOT_IT != True:
        chan_log(cli, rnick, "pm_help")
    var.GOT_IT = False
    nick, mode, user, cloak = parse_nick(rnick)
    fns = []

    rest = rest.strip().replace(botconfig.CMD_CHAR, "", 1).lower()
    splitted = re.split(" +", rest, 1)
    cname = splitted.pop(0)
    rest = splitted[0] if splitted else ""
    found = False
    if cname:
        for c in (COMMANDS,PM_COMMANDS):
            if cname in c.keys():
                found = True
                for fn in c[cname]:
                    if fn.__doc__:
                        if callable(fn.__doc__):
                            pm(cli, nick, botconfig.CMD_CHAR+cname+": "+fn.__doc__(rest))
                            if nick == botconfig.CHANNEL:
                                var.LOGGER.logMessage(botconfig.CMD_CHAR+cname+": "+fn.__doc__(rest))
                        else:
                            pm(cli, nick, botconfig.CMD_CHAR+cname+": "+fn.__doc__)
                            if nick == botconfig.CHANNEL:
                                var.LOGGER.logMessage(botconfig.CMD_CHAR+cname+": "+fn.__doc__)
                        return
                    else:
                        continue
                else:
                    continue
        else:
            if not found:
                pm(cli, nick, "Command not found.")
            else:
                pm(cli, nick, "Documentation for this command is not available.")
            return
    # if command was not found, or if no command was given:
    for name, fn in COMMANDS.items():
        if (name and not fn[0].admin_only and 
            not fn[0].owner_only and name not in fn[0].aliases):
            fns.append("\u0002"+name+"\u0002")
    afns = []
    if is_admin(cloak) or cloak in botconfig.OWNERS: # todo - is_owner
        for name, fn in COMMANDS.items():
            if fn[0].admin_only and name not in fn[0].aliases:
                afns.append("\u0002"+name+"\u0002")
    cli.notice(nick, "Commands: "+", ".join(fns))
    if afns:
        cli.notice(nick, "Admin Commands: "+", ".join(afns))



@cmd("help", raw_nick = True)
def help2(cli, rnick, chan, rest):
    """Gets help"""
    if chan == botconfig.CHANNEL:
        if var.LOG_CHAN == True:
            chan_log(cli, rnick, "help")
            var.GOT_IT = True
        if rest.strip():  # command was given
            get_help(cli, chan, rest)
        else:
            get_help(cli, rnick, rest)


@hook("invite", raw_nick = False)
def on_invite(cli, nick, something, chan):
    if chan == botconfig.CHANNEL: # it'll be able to join the default if +i...
        cli.join(chan)
    if var.RAW_JOIN == True: # ...or any other if that's True
        cli.join(chan)
    if var.IS_ADMIN[nick] == True: # lets allow admins...
        cli.join(chan)

      
def is_admin(cloak):
    return bool([ptn for ptn in botconfig.OWNERS+botconfig.ADMINS if fnmatch.fnmatch(cloak.lower(), ptn.lower())])

@pmcmd("admins", "a", "admin", "ops")
def show_admins_pm(cli, nick, rest):
    show_admins(cli, nick, nick, rest)

@cmd("admins", "a", "admin", "ops", raw_nick=True)
def show_admins(cli, rnick, chan, rest):
    """Pings the admins that are available."""
    nick, mode, user, host = parse_nick(rnick)
    if chan == botconfig.CHANNEL:
        admins = []
        pl = var.list_players()
    
        if (var.LAST_ADMINS and
            var.LAST_ADMINS + timedelta(seconds=var.ADMINS_RATE_LIMIT) > datetime.now()):
            cli.notice(nick, ("This command is rate-limited. " +
                              "Please wait a while before using it again."))
            return
        
        if not (var.PHASE in ("day", "night") and nick not in pl):
            var.LAST_ADMINS = datetime.now()
    
        if var.ADMIN_PINGING:
            return
        var.ADMIN_PINGING = True

        for adm in var.IS_ADMIN:
            if var.IS_ADMIN[adm] == True:
                admins.append(adm)

        admins.sort(key=lambda x: x.lower())
        
        if var.PHASE in ("day", "night") and nick not in pl:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "pm_admins")
            cli.notice(nick, "Available admins: "+" ".join(admins))
        else:
            if var.LOG_CHAN == True:
                chan_log(cli, rnick, "admins")
            cli.msg(chan, "Available admins: "+" ".join(admins))

        var.ADMIN_PINGING = False




@cmd("coin", "c", raw_nick=True)
def coin(cli, rnick, chan, rest):
    """It's a bad idea to base any decisions on this command."""
    nick, mode, user, host = parse_nick(rnick)
    
    if var.PHASE in ("day", "night") and nick not in var.list_players():
        cli.notice(nick, "You may not use this command right now.")
        return
    if var.LOG_CHAN == True:
        chan_log(cli, rnick, "coin")
    cli.msg(chan, "\2{0}\2 tosses a coin into the air...".format(nick))
    var.LOGGER.logMessage("{0} tosses a coin into the air...".format(nick))
    coin = random.choice(["heads", "tails"])
    if random.randrange(0, 20) == 0:
        coin = "its side"
    cmsg = "The coin lands on \2{0}\2.".format(coin)
    cli.msg(chan, cmsg)
    var.LOGGER.logMessage(cmsg)
    


def aftergame(cli, rawnick, rest):
    """Schedule a command to be run after the game by someone."""
    chan = botconfig.CHANNEL
    nick = parse_nick(rawnick)[0]
    
    rst = re.split(" +", rest)
    cmd = rst.pop(0).lower().replace(botconfig.CMD_CHAR, "", 1).strip()

    if cmd in PM_COMMANDS.keys():
        def do_action():
            for fn in PM_COMMANDS[cmd]:
                fn(cli, rawnick, " ".join(rst))
    elif cmd in COMMANDS.keys():
        def do_action():
            for fn in COMMANDS[cmd]:
                fn(cli, rawnick, botconfig.CHANNEL, " ".join(rst))
    else:
        cli.notice(nick, "That command was not found.")
        return
        
    if var.PHASE == "none":
        do_action()
        return
    if var.LOG_CHAN == True:
        chan_log(cli, nick, "aftergame")
    cli.msg(chan, ("The command \02{0}\02 has been scheduled to run "+
                  "after this game by \02{1}\02.").format(cmd, nick))
    var.AFTER_FLASTGAME = do_action

    

@cmd("faftergame", raw_nick=True)
def _faftergame(cli, nick, chan, rest):
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        if not rest.strip():
            cli.notice(parse_nick(nick)[0], "Incorrect syntax for this command.")
            return
        aftergame(cli, nick, rest)
        
    
    
@pmcmd("faftergame", raw_nick=True)
def faftergame(cli, nick, rest):
    _faftergame(cli, nick, botconfig.CHANNEL, rest)
    
    
@pmcmd("flastgame", raw_nick=True)
def flastgame(cli, rawnick, rest):
    """This command may be used in the channel or in a PM, and it disables starting or joining a game. !flastgame <optional-command-after-game-ends>"""
    nick, mode, user, host = parse_nick(rawnick)
    if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
        
        chan = botconfig.CHANNEL
        if var.PHASE != "join":
            if "join" in COMMANDS.keys():
                COMMANDS["join"] = [lambda *spam: cli.msg(chan, "This command has been disabled by an admin.")]
            if "start" in COMMANDS.keys():
                COMMANDS["start"] = [lambda *spam: cli.msg(chan, "This command has been disabled by an admin.")]
        if var.LOG_CHAN == True:
            chan_log(cli, rawnick, "last_game")
        cli.msg(chan, "Starting a new game has now been disabled by \02{0}\02.".format(nick))
        var.ADMIN_TO_PING = nick
        
        if rest.strip():
            aftergame(cli, rawnick, rest)
			
			
@cmd("raw") # allows !exec out of debug mode
#@pmcmd("raw", owner_only = True) do NOT make this as a PM command... it breaks it
def raw_irc(cli, nick, chan, rest):
    if nick in var.IS_OWNER and var.IS_OWNER[nick] == True:
        try:
            cli.send(rest)
        except Exception as e:
            cli.msg(chan, str(type(e))+":"+str(e))
	
	
@cmd("flastgame", raw_nick=True)
def _flastgame(cli, rawnick, chan, rest):
    flastgame(cli, rawnick, rest)


before_debug_mode_commands = list(COMMANDS.keys())
before_debug_mode_pmcommands = list(PM_COMMANDS.keys())

if botconfig.DEBUG_MODE or botconfig.ALLOWED_NORMAL_MODE_COMMANDS:

    @cmd("eval", raw_nick=True)
    @pmcmd("eval", raw_nick=True)
    def pyeval(cli, rnick, *rest):
        rest = list(rest)
        nick, mode, user, host = parse_nick(rnick)
        if nick in var.IS_OWNER and var.IS_OWNER[nick] == True:
            if len(rest) == 2:
                chan = rest.pop(0)
            else:
                chan = nick
            try:
                a = str(eval(rest[0]))
                cli.msg(chan, a)
            except Exception as e:
                cli.msg(chan, str(type(e))+":"+str(e))
            
            
    
    @cmd("exec", raw_nick=True)
    @pmcmd("exec", raw_nick=True)
    def py(cli, rnick, *rest):
        rest = list(rest)
        nick, mode, user, host = parse_nick(rnick)
        if nick in var.IS_OWNER and var.IS_OWNER[nick] == True:
            if len(rest) == 2:
                chan = rest.pop(0)
            else:
                chan = nick
            try:
                if var.LOG_CHAN == True:
                    chan_log(cli, rnick, "exec")
                exec(rest[0])
            except Exception as e:
                cli.msg(chan, str(type(e))+":"+str(e))


if botconfig.ALLOWED_NORMAL_MODE_COMMANDS or botconfig.DEBUG_MODE:
    for comd in list(COMMANDS.keys()):
        if (comd not in before_debug_mode_commands and
            comd not in botconfig.ALLOWED_NORMAL_MODE_COMMANDS):
            del COMMANDS[comd]

    for pmcomd in list(PM_COMMANDS.keys()):
        if (pmcomd not in before_debug_mode_pmcommands and
            pmcomd not in botconfig.ALLOWED_NORMAL_MODE_COMMANDS):
            del PM_COMMANDS[pmcomd]

    @cmd("revealroles", raw_nick=True)
    def revroles(cli, rnick, chan, rest):
        nick, mode, user, host = parse_nick(rnick)
        if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
            if var.PHASE != "none":
                if var.LOG_CHAN == True:
                    chan_log(cli, rnick, "reveal_roles")
                cli.msg(chan, str(var.ROLES))
            if var.PHASE in ('night','day'):
                cli.msg(chan, "Cursed: "+str(var.CURSED))
                cli.msg(chan, "Gunners: "+str(list(var.GUNNERS.keys())))
            
    @pmcmd("revealroles", raw_nick=True)
    def pmrevroles(cli, rnick, rest):
        nick, mode, user, host = parse_nick(rnick)
        if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
            if var.PHASE != "none":
                if var.LOG_CHAN == True:
                    chan_log(cli, rnick, "pm_reveal_roles")
                cli.notice(nick, str(var.ROLES))
            if var.PHASE in ('night','day'):
                cli.notice(nick, "Cursed: "+str(var.CURSED))
                cli.notice(nick, "Gunners: "+str(list(var.GUNNERS.keys())))
        
        
    @cmd("fgame", raw_nick=True)
    def game(cli, rnick, chan, rest):
        nick, mode, user, host = parse_nick(rnick)
        if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
            pl = var.list_players()
            if var.PHASE == "none":
                cli.notice(nick, "No game is currently running.")
                return
            if var.PHASE != "join":
                cli.notice(nick, "Werewolf is already in play.")
                return
            if nick not in pl:
                cli.notice(nick, "You're currently not playing.")
                return
            rest = rest.strip().lower()
            if rest:
                if cgamemode(cli, *re.split(" +",rest)):
                    if var.LOG_CHAN == True:
                        chan_log(cli, rnick, "fgame")
                    cli.msg(chan, ("\u0002{0}\u0002 has changed the "+
                                    "game settings successfully.").format(nick))
    
    def fgame_help(args = ""):
        args = args.strip()
        if not args:
            return "Available game mode setters: "+ ", ".join(var.GAME_MODES.keys())
        elif args in var.GAME_MODES.keys():
            return var.GAME_MODES[args].__doc__
        else:
            return "Game mode setter {0} not found.".format(args)

    game.__doc__ = fgame_help


    # DO NOT MAKE THIS A PMCOMMAND ALSO
    @cmd("force", raw_nick=True)
    def forcepm(cli, rnick, chan, rest):
        nick, mode, user, host = parse_nick(rnick)
        if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
            rst = re.split(" +",rest)
            if len(rst) < 2:
                cli.msg(chan, "The syntax is incorrect.")
                return
            who = rst.pop(0).strip()
            if not who or who == botconfig.NICK:
                cli.msg(chan, "That won't work.")
                return
            if not is_fake_nick(who):
                ul = list(var.USERS.keys())
                ull = [u.lower() for u in ul]
                if who.lower() not in ull:
                    cli.msg(chan, "This can only be done on fake nicks.")
                    return
                else:
                    who = ul[ull.index(who.lower())]
            cmd = rst.pop(0).lower().replace(botconfig.CMD_CHAR, "", 1)
            did = False
            if PM_COMMANDS.get(cmd) and not PM_COMMANDS[cmd][0].owner_only:
                if (PM_COMMANDS[cmd][0].admin_only and nick in var.USERS and 
                    not is_admin(var.USERS[nick]["cloak"])):
                    # Not a full admin
                    cli.notice(nick, "Only full admins can force an admin-only command.")
                    return
                    
                for fn in PM_COMMANDS[cmd]:
                    if fn.raw_nick:
                        continue
                    fn(cli, who, " ".join(rst))
                    did = True
                if did:
                    if var.LOG_CHAN == True:
                        chan_log(cli, rnick, "force")
                    cli.msg(chan, "Operation successful.")
                else:
                    cli.msg(chan, "Not possible with this command.")
                #if var.PHASE == "night":   <-  Causes problems with night starting twice.
                #    chk_nightdone(cli)
                    
                for fn in COMMANDS[cmd]:
                    if fn.raw_nick:
                        continue
                    fn(cli, who, chan, " ".join(rst))
                    did = True
                if did:
                    cli.msg(chan, "Operation successful.")
                else:
                    cli.msg(chan, "Not possible with this command.")
            else:
                cli.msg(chan, "That command was not found.")
            
            
    @cmd("rforce", raw_nick=True)
    def rforcepm(cli, rnick, chan, rest):
        nick, mode, user, host = parse_nick(rnick)
        if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
            rst = re.split(" +",rest)
            if len(rst) < 2:
                cli.msg(chan, "The syntax is incorrect.")
                return
            who = rst.pop(0).strip().lower()
            who = who.replace("_", " ")
            
            if (who not in var.ROLES or not var.ROLES[who]) and (who != "gunner"
                or var.PHASE in ("none", "join")):
                cli.msg(chan, nick+": invalid role")
                return
            elif who == "gunner":
                tgt = list(var.GUNNERS.keys())
            else:
                tgt = var.ROLES[who]

            cmd = rst.pop(0).lower().replace(botconfig.CMD_CHAR, "", 1)
            if PM_COMMANDS.get(cmd) and not PM_COMMANDS[cmd][0].owner_only:
                if (PM_COMMANDS[cmd][0].admin_only and nick in var.USERS and 
                    not is_admin(var.USERS[nick]["cloak"])):
                    # Not a full admin
                    cli.notice(nick, "Only full admins can force an admin-only command.")
                    return
            
                for fn in PM_COMMANDS[cmd]:
                    for guy in tgt[:]:
                        fn(cli, guy, " ".join(rst))
                if var.LOG_CHAN == True:
                    chan_log(cli, rnick, "role_force")
                cli.msg(chan, "Operation successful.")
                #if var.PHASE == "night":   <-  Causes problems with night starting twice.
                #    chk_nightdone(cli)
            elif cmd.lower() in COMMANDS.keys() and not COMMANDS[cmd][0].owner_only:
                if (COMMANDS[cmd][0].admin_only and nick in var.USERS and 
                    not is_admin(var.USERS[nick]["cloak"])):
                    # Not a full admin
                    cli.notice(nick, "Only full admins can force an admin-only command.")
                    return
            
                for fn in COMMANDS[cmd]:
                    for guy in tgt[:]:
                        fn(cli, guy, chan, " ".join(rst))
                cli.msg(chan, "Operation successful.")
            else:
                cli.msg(chan, "That command was not found.")



    @cmd("frole", raw_nick=True)
    def frole(cli, rnick, chan, rest):
        nick, mode, user, host = parse_nick(rnick)
        if nick in var.IS_ADMIN and var.IS_ADMIN[nick] == True:
            rst = re.split(" +",rest)
            if len(rst) < 2:
                cli.msg(chan, "The syntax is incorrect.")
                return
            who = rst.pop(0).strip()
            rol = " ".join(rst).strip()
            ul = list(var.USERS.keys())
            ull = [u.lower() for u in ul]
            if who.lower() not in ull:
                if not is_fake_nick(who):
                    cli.msg(chan, "Could not be done.")
                    cli.msg(chan, "The target needs to be in this channel or a fake name.")
                    return
            if not is_fake_nick(who):
                who = ul[ull.index(who.lower())]
            if who == botconfig.NICK or not who:
                cli.msg(chan, "No.")
                return
            if rol not in var.ROLES.keys():
                pl = var.list_players()
                if var.PHASE not in ("night", "day"):
                    cli.msg(chan, "This is only allowed in game.")
                    return
                if rol.startswith("gunner"):
                    rolargs = re.split(" +",rol, 1)
                    if len(rolargs) == 2 and rolargs[1].isdigit():
                        if len(rolargs[1]) < 7:
                            var.GUNNERS[who] = int(rolargs[1])
                            var.WOLF_GUNNERS[who] = int(rolargs[1])
                        else:
                            var.GUNNERS[who] = 999
                            var.WOLF_GUNNERS[who] = 999
                    else:
                        var.GUNNERS[who] = math.ceil(var.SHOTS_MULTIPLIER * len(pl))
                    if who not in pl:
                        var.ROLES["villager"].append(who)
                elif rol == "cursed villager":
                    if who not in var.CURSED:
                        var.CURSED.append(who)
                    if who not in pl:
                        var.ROLES["villager"].append(who)
                else:
                    cli.msg(chan, "Not a valid role.")
                    return
                if var.LOG_CHAN == True:
                    chan_log(cli, rnick, "force_role")
                cli.msg(chan, "Operation successful.")
                return
            if who in var.list_players():
                var.del_player(who)
            var.ROLES[rol].append(who)
            cli.msg(chan, "Operation successful.")
            if var.PHASE not in ('none','join'):
                chk_win(cli)
